"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from .config import PROJECT_ROOT, Settings
from .export import usable, write_candidates, write_csv, write_json, write_report
from .fetcher import Fetcher
from .pipeline import read_targets, run


def dedupe_targets(targets: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in targets:
        key = t.lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sc-found-t",
        description=(
            "Busca correos de contacto público de canales de YouTube y Twitch "
            "para proponer colaboraciones."
        ),
    )
    p.add_argument(
        "targets",
        nargs="?",
        help="Canales o fichero con un canal por línea (@handle, URL, ruta).",
    )
    p.add_argument("-s", "--search", default="",
                   help="Palabra clave: descubre canales en YouTube y/o Twitch.")
    p.add_argument("--search-platform", choices=["youtube", "twitch", "todos"],
                   default="todos", help="Dónde buscar la palabra clave (todos).")
    p.add_argument("--search-sort", choices=["relevancia", "vistas", "fecha"],
                   default="relevancia", help="Orden de los resultados de YouTube.")
    p.add_argument("--search-type", choices=["video", "canal"], default="video",
                   help="Buscar videos (y deduplicar por canal) o solo canales.")
    p.add_argument("--search-limit", type=int, default=40,
                   help="Máximo de canales por plataforma.")
    p.add_argument("--live-only", action="store_true",
                   help="En Twitch, solo canales que estén en directo.")
    p.add_argument("--min-subs", type=int, default=0,
                   help="Descarta canales por debajo de N suscriptores.")
    p.add_argument("-o", "--outdir", default=os.path.join(PROJECT_ROOT, "out"))
    p.add_argument("-c", "--concurrency", type=int, default=4)
    p.add_argument("--delay", type=float, default=1.5, help="Segundos entre peticiones al mismo dominio.")
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--max-pages", type=int, default=6, help="Páginas por dominio.")
    p.add_argument("--max-domains", type=int, default=5, help="Dominios por creador.")
    p.add_argument("--max-domains-total", type=int, default=60)
    p.add_argument("--no-crawl", action="store_true", help="Solo busca en la bio, sin visitar webs.")
    p.add_argument("--ignore-robots", action="store_true")
    p.add_argument("--min-score", type=int, default=0, help="Filtra por puntuación mínima.")
    p.add_argument("--only-business", action="store_true", help="Deja solo roles de contacto/negocios.")
    p.add_argument("--any-domain", action="store_true",
                   help="Acepta correos de terceros hallados en paginas de plataformas (mas ruido).")
    p.add_argument("--cache-ttl", type=int, default=168, help="Horas de caché.")
    p.add_argument("--contact-email", default=os.environ.get("SCF_EMAIL", ""),
                   help="Tu email; se incluye en el User-Agent para que te puedan identificar.")
    p.add_argument("--cookies-from-browser", default="", help="firefox|chrome|brave…")
    p.add_argument("--name", default="", help="Nombre base para los ficheros de salida.")
    return p


def settings_from(args: argparse.Namespace) -> Settings:
    return Settings(
        concurrency=max(1, args.concurrency),
        delay_per_domain=max(0.0, args.delay),
        timeout=args.timeout,
        max_pages_per_domain=max(1, args.max_pages),
        max_domains_per_creator=max(0, args.max_domains),
        max_domains_total=max(1, args.max_domains_total),
        cache_ttl_hours=args.cache_ttl,
        contact_email=args.contact_email,
        respect_robots=not args.ignore_robots,
        crawl=not args.no_crawl,
        cookies_from_browser=args.cookies_from_browser,
        min_score=args.min_score,
        min_subscribers=max(0, args.min_subs),
        require_domain_match=not args.any_domain,
    )


async def discover_targets(args: argparse.Namespace, settings: Settings) -> tuple[list[str], dict]:
    """Convierte una palabra clave en la lista de canales a analizar."""
    from . import discover

    fetcher = Fetcher(settings)
    try:
        found = await discover.run(
            args.search,
            settings,
            fetcher,
            platform=args.search_platform,
            sort=args.search_sort,
            kind=args.search_type,
            limit=max(1, args.search_limit),
            live_only=args.live_only,
        )
    finally:
        await fetcher.aclose()

    if not found:
        return [], {}

    os.makedirs(args.outdir, exist_ok=True)
    found_path = os.path.join(args.outdir, f"{args.name or 'busqueda'}_canales.csv")
    write_candidates(found, found_path)

    print(f"\n{len(found)} canales para «{args.search}»:\n")
    for c in found:
        print(f"  · {c.line()}")
    if settings.min_subscribers:
        print(f"\n  Aviso: --min-subs {settings.min_subscribers} se aplica al resolver "
              "cada canal, así que la lista de arriba aún lo incluye todo.\n")
    print(f"  Lista guardada en {found_path}\n")

    return [c.target for c in found], {"discovered": len(found)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from(args)

    if not args.targets and not args.search:
        print("Da un canal o una palabra clave con --search.", file=sys.stderr)
        return 2

    os.makedirs(args.outdir, exist_ok=True)
    targets = read_targets(args.targets) if args.targets else []
    search_summary: dict = {}

    if args.search:
        found, search_summary = asyncio.run(discover_targets(args, settings))
        targets = dedupe_targets(targets + found)

    if not targets:
        print("No hay canales que buscar.", file=sys.stderr)
        return 2

    print(f"Buscando en {len(targets)} canales · concurrencia {settings.concurrency} "
          f"· {settings.delay_per_domain}s/dominio\n")

    hits, crawler, fetcher = asyncio.run(run(targets, settings))

    final = usable(hits) if args.only_business else hits

    stem = args.name or datetime_stamp()
    csv_path = os.path.join(args.outdir, f"{stem}.csv")
    json_path = os.path.join(args.outdir, f"{stem}.json")
    md_path = os.path.join(args.outdir, f"{stem}.md")

    summary = {
        "creators": len(targets),
        "pages": crawler.pages_scanned,
        "domains": len(crawler.domains_used),
        "cache_hits": fetcher.hits,
        **search_summary,
    }

    write_csv(final, csv_path)
    write_json(final, json_path)
    write_report(final, md_path, summary)

    unique = len({h.email for h in final})
    print(f"\n{len(final)} contactos · {unique} casillas únicas")
    print(f"  CSV   {csv_path}")
    print(f"  JSON  {json_path}")
    print(f"  MD    {md_path}")
    print(f"  {summary['pages']} páginas, {summary['domains']} dominios, "
          f"{summary['cache_hits']} desde caché")
    return 0


def datetime_stamp() -> str:
    from datetime import datetime

    return f"contactos_{datetime.now():%Y%m%d_%H%M}"


if __name__ == "__main__":
    raise SystemExit(main())