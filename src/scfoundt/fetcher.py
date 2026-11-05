"""Cliente HTTP educado: caché en disco, robots.txt, límite por dominio."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx

from .config import Settings

MAX_BODY_BYTES = 3_000_000


class RobotsDenied(Exception):
    pass


class Fetcher:
    """Descarga páginas respecting robots.txt y sin machacar un mismo host.

    Una instancia por ejecución. El límite por dominio es lo más importante:
    evita que 200 creadores golpeen el mismo sitio a la vez.
    """

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.timeout,
            headers={
                "User-Agent": settings.ua(),
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            },
            limits=httpx.Limits(max_connections=max(8, settings.concurrency * 2)),
        )
        self._sem = asyncio.Semaphore(settings.concurrency)
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._domain_last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.hits = 0
        self.misses = 0
        self.errors: dict[str, str] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---------- caché ----------

    def _cache_paths(self, url: str) -> tuple[str, str]:
        h = hashlib.sha256(url.encode()).hexdigest()[:32]
        d = os.path.join(self.s.cache_dir, h[:2])
        return os.path.join(d, h + ".meta"), os.path.join(d, h + ".body")

    def _cache_read(self, url: str) -> tuple[str, int] | None:
        meta_p, body_p = self._cache_paths(url)
        try:
            meta = json.loads(open(meta_p, encoding="utf-8").read())
        except (OSError, ValueError):
            return None
        if time.time() - meta.get("ts", 0) > self.s.cache_ttl_hours * 3600:
            return None
        try:
            return open(body_p, encoding="utf-8").read(), meta.get("status", 0)
        except OSError:
            return None

    def _cache_write(self, url: str, body: str, status: int) -> None:
        meta_p, body_p = self._cache_paths(url)
        try:
            os.makedirs(os.path.dirname(body_p), exist_ok=True)
            open(body_p, "w", encoding="utf-8").write(body)
            open(meta_p, "w", encoding="utf-8").write(
                json.dumps({"ts": time.time(), "status": status, "url": url})
            )
        except OSError:
            pass

    # ---------- robots ----------

    async def _robots_allows(self, url: str) -> bool:
        if not self.s.respect_robots:
            return True
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = origin + "/robots.txt"
            try:
                r = await self._client.get(robots_url)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    rp = None  # sin robots.txt -> todo permitido
            except (httpx.HTTPError, asyncio.TimeoutError):
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        if rp is None:
            return True
        try:
            return rp.can_fetch(self.s.ua(), url)
        except Exception:
            return True

    def _note_error(self, domain: str, kind: str) -> None:
        if domain not in self.errors:
            self.errors[domain] = kind
            print(f"    ! {domain}: {kind}")

    # ---------- descarga ----------

    async def _throttle(self, domain: str) -> None:
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())
        async with lock:
            last = self._domain_last.get(domain, 0.0)
            wait = self.s.delay_per_domain - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._domain_last[domain] = time.monotonic()

    async def get(
        self, url: str, *, headers: dict | None = None, check_robots: bool = True
    ) -> str | None:
        """Devuelve el cuerpo HTML de la URL, o None si no se pudo.

        check_robots=False se reserva para la ficha pública del propio canal en
        YouTube/Twitch: una única petición por canal, ya cacheada, que es la
        página que la plataforma muestra a cualquier visitante.
        """
        if not url.startswith(("http://", "https://")):
            return None
        url = url.strip()

        cached = self._cache_read(url)
        if cached is not None:
            self.hits += 1
            return cached[0]

        if check_robots and not await self._robots_allows(url):
            raise RobotsDenied(url)

        domain = urlparse(url).netloc
        async with self._sem:
            await self._throttle(domain)
            for attempt in range(3):
                try:
                    r = await self._client.get(
                        url, headers=headers, follow_redirects=True
                    )
                except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                    if attempt == 2:
                        self._note_error(domain, type(exc).__name__)
                        return None
                    await asyncio.sleep(2 ** attempt)
                    continue

                if r.status_code in (429, 503):
                    wait = float(r.headers.get("Retry-After") or 0) or (3 * (attempt + 1))
                    await asyncio.sleep(min(wait, 30))
                    continue
                if r.status_code >= 400:
                    self._cache_write(url, "", r.status_code)
                    return None

                ctype = r.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype and "json" not in ctype:
                    return None

                text = r.text[:MAX_BODY_BYTES]
                self._cache_write(url, text, r.status_code)
                self.misses += 1
                return text
        return None

    async def post_json(self, url: str, payload: dict, headers: dict) -> dict | None:
        """POST para APIs JSON (Twitch GraphQL). No pasa por robots ni caché."""
        async with self._sem:
            try:
                r = await self._client.post(url, json=payload, headers=headers)
            except (httpx.HTTPError, asyncio.TimeoutError):
                return None
            if r.status_code >= 400:
                return None
            try:
                return r.json()
            except ValueError:
                return None

    async def post_form(self, url: str, data: dict) -> dict | None:
        """POST con body x-www-form-urlencoded (OAuth de Twitch)."""
        async with self._sem:
            try:
                r = await self._client.post(url, data=data)
            except (httpx.HTTPError, asyncio.TimeoutError):
                return None
            if r.status_code >= 400:
                return None
            try:
                return r.json()
            except ValueError:
                return None

    async def get_json(
        self, url: str, params: dict, headers: dict | None = None
    ) -> dict | None:
        """GET a una API JSON (Helix de Twitch). No pasa por robots ni caché:
        las respuestas traen tokens y no tiene sentido guardarlas en disco.
        """
        async with self._sem:
            try:
                r = await self._client.get(url, params=params, headers=headers)
            except (httpx.HTTPError, asyncio.TimeoutError):
                return None
            if r.status_code >= 400:
                return None
            try:
                return r.json()
            except ValueError:
                return None


def root_of(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}"


def join(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))