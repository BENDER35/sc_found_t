"""Descubre canales a partir de una palabra clave.

YouTube usa la búsqueda pública de resultados vía yt-dlp: una sola petición por
consulta y devuelve el canal de cada video, lo que permite deduplicar antes de
gastar nada en resolución.

Twitch no expone búsqueda pública sin credenciales. Su endpoint oficial
(/helix/search/channels) exige un app access token, que se obtiene con el flujo
client_credentials de una app registrada en dev.twitch.tv. Ese token es de
servidor a servidor: no es la cuenta de nadie ni pide login de usuario. Con el
token se consiguen los logins, y la bio se lee después con el resolver que ya
hay.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

import yt_dlp

from .config import Settings
from .fetcher import Fetcher

# Filtros "sp" de la página de resultados de YouTube. Son opacos, pero son los
# que usa el propio buscador; comprobados contra la web.
YT_SORTS = {
    "relevancia": "CAASAhAB",
    "vistas": "CAM%3D",
    "fecha": "CAI%3D",
}
YT_TYPE_CHANNEL = "EgIQAg%3D%3D"

HELIX_SEARCH = "https://api.twitch.tv/helix/search/channels"
HELIX_TOKEN = "https://id.twitch.tv/oauth2/token"


@dataclass
class Candidate:
    """Un canal que la búsqueda ha proposed y que falta por resolver."""

    platform: str
    target: str
    label: str
    signal: str = ""

    def line(self) -> str:
        extra = f" · {self.signal}" if self.signal else ""
        return f"{self.label}{extra} → {self.target}"


# ---------- caché de búsquedas ----------

def _cache_file(settings: Settings, key: str) -> str:
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return os.path.join(settings.cache_dir, "search", digest + ".json")


def _cache_load(settings: Settings, key: str) -> list[Candidate] | None:
    try:
        payload = json.loads(open(_cache_file(settings, key), encoding="utf-8").read())
    except (OSError, ValueError):
        return None
    if time.time() - payload.get("ts", 0) > settings.cache_ttl_hours * 3600:
        return None
    return [Candidate(**c) for c in payload.get("items", [])]


def _cache_save(settings: Settings, key: str, items: list[Candidate]) -> None:
    path = _cache_file(settings, key)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(
            json.dumps(
                {"ts": time.time(), "key": key, "items": [asdict(c) for c in items]},
                ensure_ascii=False,
            )
        )
    except OSError:
        pass


# ---------- YouTube ----------

def search_url(query: str, sort: str, kind: str) -> str:
    """URL de resultados con el filtro de orden y de tipo ya aplicado."""
    sp = YT_TYPE_CHANNEL if kind == "canal" else YT_SORTS.get(sort, YT_SORTS["relevancia"])
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={sp}"


def _flat_options(settings: Settings) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "socket_timeout": max(15, int(settings.timeout)),
        "retries": 2,
        "extractor_retries": 2,
    }
    if settings.cookies_from_browser:
        opts["cookiesfrombrowser"] = (settings.cookies_from_browser,)
    return opts


def _youtube_blocking(url: str, settings: Settings) -> list[Candidate]:
    try:
        with yt_dlp.YoutubeDL(_flat_options(settings)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        print(f"  ! búsqueda en YouTube: {type(exc).__name__}: {exc}")
        return []
    if not info:
        return []

    out: list[Candidate] = []
    seen: set[str] = set()
    for entry in info.get("entries") or []:
        if not entry:
            continue
        # Con el filtro de canal la entrada es el canal; con el de video la
        # entrada es un video y el canal llega en channel_id.
        channel_id = entry.get("channel_id")
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)

        name = (entry.get("channel") or entry.get("uploader") or "").strip()
        # Preferimos el @handle: las URLs /channel/UC… no se resuelven bien en
        # modo plano (yt-dlp las devuelve como stub sin datos del canal).
        handle = entry.get("uploader_id") or ""
        if not handle.startswith("@"):
            handle = ""
        target = (
            f"https://www.youtube.com/{handle}"
            if handle
            else entry.get("channel_url") or f"https://www.youtube.com/channel/{channel_id}"
        )
        views = entry.get("view_count")
        out.append(
            Candidate(
                platform="youtube",
                target=target,
                label=name or channel_id,
                signal=f"{views:,} vistas".replace(",", ".") if views else "",
            )
        )
    return out


async def search_youtube(
    query: str,
    settings: Settings,
    sort: str = "relevancia",
    kind: str = "video",
    limit: int = 40,
) -> list[Candidate]:
    key = f"youtube|{query.lower()}|{sort}|{kind}|{limit}"
    cached = _cache_load(settings, key)
    if cached is not None:
        print(f"  = {len(cached)} canales desde caché (YouTube: {query!r})")
        return cached

    found = await asyncio.to_thread(_youtube_blocking, search_url(query, sort, kind), settings)
    found = found[:limit]
    _cache_save(settings, key, found)
    return found


# ---------- Twitch ----------

class TwitchAuthError(Exception):
    pass


async def app_token(fetcher: Fetcher, client_id: str, client_secret: str) -> str:
    """App access token vía client_credentials."""
    data = await fetcher.post_form(
        HELIX_TOKEN,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )
    if not data or "access_token" not in data:
        raise TwitchAuthError(
            "Twitch no devolvió token. Revisa TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET."
        )
    return data["access_token"]


def _helix_page(data: dict, limit: int, seen: set[str]) -> tuple[list[Candidate], str]:
    """Convierte una página de Helix en candidatos. El cursor permite paginar."""
    out: list[Candidate] = []
    cursor = (data.get("pagination") or {}).get("cursor", "")
    for ch in data.get("data") or []:
        login = (ch.get("broadcaster_login") or "").lower()
        if not login or login in seen:
            continue
        seen.add(login)
        bits = []
        if ch.get("is_live"):
            bits.append("en directo")
        if ch.get("game_name"):
            bits.append(ch["game_name"])
        out.append(
            Candidate(
                platform="twitch",
                target=f"https://www.twitch.tv/{login}",
                label=(ch.get("display_name") or login).strip(),
                signal=" · ".join(bits),
            )
        )
        if len(out) >= limit:
            return out, ""
    return out, cursor


async def search_twitch(
    query: str,
    settings: Settings,
    fetcher: Fetcher,
    limit: int = 40,
    live_only: bool = False,
) -> list[Candidate]:
    client_id = settings.twitch_client_id
    if not client_id or not settings.twitch_client_secret:
        raise TwitchAuthError(
            "la búsqueda en Twitch necesita credenciales propias. Registra una app "
            "en dev.twitch.tv/console/apps y exporta TWITCH_CLIENT_ID y "
            "TWITCH_CLIENT_SECRET."
        )

    key = f"twitch|{query.lower()}|{limit}|{live_only}"
    cached = _cache_load(settings, key)
    if cached is not None:
        print(f"  = {len(cached)} canales desde caché (Twitch: {query!r})")
        return cached

    token = await app_token(fetcher, client_id, settings.twitch_client_secret)
    headers = {"Client-Id": client_id, "Authorization": f"Bearer {token}"}

    found: list[Candidate] = []
    seen: set[str] = set()
    cursor = ""
    while len(found) < limit:
        params = {
            "query": query,
            "first": min(100, limit),
            "live_only": str(live_only).lower(),
        }
        if cursor:
            params["after"] = cursor
        data = await fetcher.get_json(HELIX_SEARCH, params, headers)
        if not data:
            print("  ! la búsqueda de Twitch no devolvió datos")
            break
        page, cursor = _helix_page(data, limit - len(found), seen)
        found.extend(page)
        if not cursor or not page:
            break

    _cache_save(settings, key, found)
    return found


# ---------- orquestación ----------

async def run(
    query: str,
    settings: Settings,
    fetcher: Fetcher,
    platform: str = "youtube",
    sort: str = "relevancia",
    kind: str = "video",
    limit: int = 40,
    live_only: bool = False,
) -> list[Candidate]:
    found: list[Candidate] = []

    if platform in ("youtube", "todos"):
        found += await search_youtube(query, settings, sort=sort, kind=kind, limit=limit)

    if platform in ("twitch", "todos"):
        try:
            found += await search_twitch(query, settings, fetcher, limit, live_only)
        except TwitchAuthError as exc:
            print(f"  ! {exc}")

    return dedupe(found)


def dedupe(items: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in items:
        key = c.target.lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out