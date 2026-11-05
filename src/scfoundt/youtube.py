"""Resuelve canales de YouTube: descripción pública, enlaces y suscriptores.

El email de "business inquiries" que YouTube esconde tras un botón no aparece en
la API, pero la descripción del canal sí es pública y suele contenerlo.
"""

from __future__ import annotations

import asyncio
import json
import re

import yt_dlp

from .config import Settings
from .extract import DEFAULT_SKIP, external_links, text_to_links
from .models import Creator

CHANNEL_RE = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/(?:c/|channel/|user/|@)?([^/?#]+)",
    re.IGNORECASE,
)
VIDEO_RE = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/(?:watch|shorts|live|embed|v)|youtu\.be/",
    re.IGNORECASE,
)


def is_email_address(value: str) -> bool:
    """El valor completo es una dirección de correo, no un handle con '@'."""
    from .extract import EMAIL_RE, is_junk, normalize

    if not EMAIL_RE.fullmatch(value):
        return False
    return not is_junk(normalize(value))


def is_youtube(target: str) -> bool:
    t = target.lower()
    return "youtube.com" in t or "youtu.be" in t or t.startswith("@")


def normalize_input(target: str) -> str:
    t = target.strip()
    if t.startswith("@"):
        return f"https://www.youtube.com/{t}"
    if not t.startswith("http"):
        return f"https://www.youtube.com/@{t.lstrip('@')}"
    return t


async def resolve(target: str, settings: Settings, fetcher=None) -> Creator:
    url = normalize_input(target)
    creator = await asyncio.to_thread(_extract_blocking, url, settings)
    if fetcher is not None and not creator.error:
        await merge_about_page(creator, fetcher)
    return creator


def about_url(creator: Creator) -> str:
    base = creator.url if "://" in creator.url else f"https://www.youtube.com/@{creator.handle}"
    # ucbcb=1 omite el muro de consentimiento (consent.youtube.com) sin
    # asumir cookies: es el parametro que usa la propia web de YouTube.
    return base.rstrip("/") + "/about?ucbcb=1&hl=es"


async def merge_about_page(creator: Creator, fetcher) -> None:
    """Lee la pestaña /about, donde YouTube publica la descripción completa y,
    sobre todo, el enlace de contacto que el creador declara ("Contacto:
    hola@midominio.com") junto al resto de su sección de enlaces.
    """
    html = await fetcher.get(
        about_url(creator), check_robots=False
    )
    if not html or "ytInitialData" not in html:
        return
    if "consent.youtube.com" in html[:5000]:
        return

    data = _extract_initial_data(html)
    if not data:
        return

    description, links = _parse_about(data)
    if description and len(description) > len(creator.description):
        creator.description = description

    emails, urls = [], []
    for _title, value in links:
        value = value.strip()
        # Un enlace declarado es un email solo si lo es entero: los handles de
        # redes ("tiktok.com/@fulano") también llevan "@" y no lo son.
        if is_email_address(value):
            emails.append(value)
        elif "." in value and " " not in value:
            if value.startswith("//"):
                value = "https:" + value
            elif not value.lower().startswith(("http://", "https://")):
                value = "https://" + value
            urls.append(value)

    for addr in emails:
        creator.declared_emails.append((addr, about_url(creator)))
    new = external_links(urls + creator.external_links, DEFAULT_SKIP)
    for u in new:
        if u not in creator.external_links:
            creator.external_links.append(u)


def _extract_initial_data(html: str) -> dict | None:
    for pattern in (
        r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>",
        r'ytInitialData"?\s*=\s*(\{.*?\});\s*</script>',
    ):
        m = re.search(pattern, html, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except ValueError:
                continue
    return None


def _parse_about(data: dict) -> tuple[str, list[tuple[str, str]]]:
    description = ""
    links: list[tuple[str, str]] = []

    def walk(node) -> None:
        nonlocal description
        if isinstance(node, dict):
            model = node.get("aboutChannelViewModel")
            if isinstance(model, dict):
                description = description or (model.get("description") or "")
                for item in model.get("links") or []:
                    ext = item.get("channelExternalLinkViewModel") or {}
                    title = (ext.get("title") or {}).get("content", "")
                    value = ((ext.get("link") or {}).get("content") or "").strip()
                    if value:
                        links.append((title, value))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return description, links


def _options(settings: Settings, flat: bool) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": max(15, int(settings.timeout)),
        "retries": 2,
        "extractor_retries": 2,
    }
    if flat:
        opts["extract_flat"] = True
        opts["playlist_items"] = "1"
    if settings.cookies_from_browser:
        opts["cookiesfrombrowser"] = (settings.cookies_from_browser,)
    return opts


def _extract_blocking(url: str, settings: Settings) -> Creator:
    is_video = bool(VIDEO_RE.match(url))
    try:
        with yt_dlp.YoutubeDL(_options(settings, flat=not is_video)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return Creator("youtube", handle=url, url=url, error=f"{type(exc).__name__}")

    if not info:
        return Creator("youtube", handle=url, url=url, error="sin datos")

    if is_video and info.get("_type") not in ("playlist", "multi_video"):
        info = {
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "uploader_id": info.get("uploader_id"),
            "uploader": info.get("uploader"),
            "channel_url": info.get("channel_url"),
            "channel_follower_count": info.get("channel_follower_count"),
            "description": info.get("channel") and "" or "",
        }
        return _creator_from(info, url)

    entries = [e for e in (info.get("entries") or []) if e]
    description = info.get("description") or ""
    followers = info.get("channel_follower_count")
    if entries:
        first = entries[0]
        followers = followers or first.get("channel_follower_count")
        if not description:
            description = first.get("description") or ""

    merged = dict(info)
    merged["description"] = description
    merged["channel_follower_count"] = followers
    return _creator_from(merged, url)


def _creator_from(info: dict, fallback_url: str) -> Creator:
    description = info.get("description") or ""
    return Creator(
        platform="youtube",
        handle=_handle_from(info, fallback_url),
        url=info.get("channel_url") or info.get("uploader_url") or fallback_url,
        name=info.get("channel") or info.get("uploader") or "",
        followers=info.get("channel_follower_count") or info.get("follower_count"),
        description=description,
        external_links=text_to_links(description),
    )


def _handle_from(info: dict, fallback_url: str) -> str:
    for key in ("uploader_id", "channel_id", "uploader", "channel"):
        val = info.get(key)
        if isinstance(val, str) and val:
            return val
    m = CHANNEL_RE.match(fallback_url)
    return m.group(1) if m else fallback_url