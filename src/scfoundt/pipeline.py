"""Orquesta: resuelve cada canal, recoge candidatos y visita sus sitios."""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict
from typing import Optional

from . import twitch, youtube
from .config import Settings
from .crawler import SiteCrawler
from .extract import classify_role, extract_emails
from .fetcher import Fetcher
from .models import Creator, Hit

# Constantes para puntuación de emails
SCORE_BIO = 30  # Puntuación base para emails encontrados en la bio
SCORE_DESC = 0  # Puntuación para emails extraídos de la descripción


def detect_platform(target: str) -> str:
    t = target.lower().strip()
    if twitch.is_twitch(t):
        return "twitch"
    if youtube.is_youtube(t):
        return "youtube"
    return "youtube"


async def resolve_creator(target: str, settings: Settings, f: Fetcher) -> Creator:
    platform = detect_platform(target)
    if platform == "twitch":
        return await twitch.resolve(target, settings, f)
    return await youtube.resolve(target, settings, f)


def hits_from_description(creator: Creator) -> list[Hit]:
    hits: list[Hit] = []
    for email, source in creator.declared_emails:
        role, score = classify_role(email)
        if role == "sin_clasificar":
            role = "contacto"
        hits.append(
            Hit(
                email=email,
                platform=creator.platform,
                handle=creator.handle,
                creator_name=creator.label,
                followers=creator.followers,
                role=role,
                kind="enlace_contacto",
                source_url=source,
                score=score + SCORE_BIO,
            )
        )

    if not creator.description.strip():
        return hits
    for addr in extract_emails(creator.description):
        if any(addr == e for e, _ in creator.declared_emails):
            continue
        role, score = classify_role(addr)
        hits.append(
            Hit(
                email=addr,
                platform=creator.platform,
                handle=creator.handle,
                creator_name=creator.label,
                followers=creator.followers,
                role=role,
                kind="descripcion",
                source_url=creator.url,
                score=score,
            )
        )
    return hits


def dedupe(hits: list[Hit], min_score: int = 0) -> list[Hit]:
    """Un email = una fila. Si aparece en varias fuentes gana la de mayor
    puntuación, y se conserva la forma original con la que lo publicó el
    creador ("Auron@youplanet.es" y "auron@youplanet.es" son la misma casilla).
    """
    best: dict[str, Hit] = {}
    for h in hits:
        if h.score < min_score:
            continue
        key = h.email.lower()
        prev = best.get(key)
        if prev is None or h.score > prev.score:
            best[key] = h
    return sorted(best.values(), key=lambda h: (-h.score, h.email))


async def process_one(
    target: str, settings: Settings, f: Fetcher, crawler: SiteCrawler
) -> list[Hit]:
    creator = await resolve_creator(target, settings, f)
    if creator.error:
        print(f"  ! {target}: {creator.error}")
        return []

    found = hits_from_description(creator)
    print(
        f"  - {creator.label} ({creator.handle}) "
        f"[{creator.followers or '?'} subs] · {len(creator.external_links)} enlaces · "
        f"{len(found)} email en bio"
    )

    if too_small(creator, settings):
        print(f"    . bajo el mínimo de {settings.min_subscribers} subs: no se rastrea")
        return []

    if settings.crawl and creator.external_links:
        found += await crawler.crawl(creator)

    return found


def too_small(creator: Creator, settings: Settings) -> bool:
    """Filtra por audiencia antes de gastar peticiones en sus webs.

    Si no sabemos los suscriptores (Twitch no los da sin API de pago) el canal
    pasa el filtro: no se descarta nada por falta de dato.
    """
    if settings.min_subscribers <= 0 or creator.followers is None:
        return False
    return creator.followers < settings.min_subscribers


async def run(targets: list[str], settings: Settings) -> tuple[list[Hit], SiteCrawler, Fetcher]:
    import asyncio
    
    f = Fetcher(settings)
    crawler = SiteCrawler(f, settings)
    sem = asyncio.Semaphore(max(1, settings.concurrency))

    async def guarded(target: str) -> list[Hit]:
        async with sem:
            try:
                return await process_one(target, settings, f, crawler)
            except asyncio.CancelledError:
                print(f"  ! {target}: cancelled")
                return []
            except Exception as exc:
                print(f"  ! {target}: {type(exc).__name__}: {exc}")
                return []

    try:
        results = await asyncio.gather(*(guarded(t) for t in targets))
    finally:
        await f.aclose()

    all_hits = dedupe([h for group in results for h in group], settings.min_score)
    return all_hits, crawler, f


def to_dicts(hits: list[Hit]) -> list[dict]:
    return [asdict(h) for h in hits]


def read_targets(source: str) -> list[str]:
    """Lee targets de un fichero o de un argumento inline."""
    import os

    lines: list[str] = []
    if os.path.isfile(source):
        with open(source, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    else:
        lines = re.split(r"[,\s]+", source)
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    seen: set[str] = set()
    unique: list[str] = []
    for target in out:
        key = target.lower()
        if key not in seen:
            seen.add(key)
            unique.append(target)
    return unique