"""Exporta los resultados a CSV, JSON y un informe Markdown."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from .extract import PUBLIC_ROLES
from .models import Hit

CSV_COLUMNS = [
    ("platform", "plataforma"),
    ("creator_name", "canal"),
    ("handle", "handle"),
    ("followers", "seguidores"),
    ("email", "email"),
    ("role", "rol"),
    ("kind", "tipo"),
    ("score", "puntuacion"),
    ("source_url", "fuente"),
]


def write_csv(hits: list[Hit], path: str) -> None:
    rows = []
    for h in hits:
        rows.append(
            {
                "plataforma": h.platform,
                "canal": h.creator_name,
                "handle": h.handle,
                "seguidores": h.followers if h.followers is not None else "",
                "email": h.email,
                "rol": h.role,
                "tipo": h.kind,
                "puntuacion": h.score,
                "fuente": h.source_url,
            }
        )
    _ensure(path)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[label for _, label in CSV_COLUMNS])
        writer.writeheader()
        writer.writerows(rows)


def write_json(hits: list[Hit], path: str) -> None:
    _ensure(path)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(hits),
        "items": [
            {
                "platform": h.platform,
                "channel": h.creator_name,
                "handle": h.handle,
                "followers": h.followers,
                "email": h.email,
                "role": h.role,
                "kind": h.kind,
                "score": h.score,
                "source_url": h.source_url,
            }
            for h in hits
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def write_report(hits: list[Hit], path: str, summary: dict) -> None:
    _ensure(path)
    by_role: dict[str, int] = {}
    for h in hits:
        by_role[h.role] = by_role.get(h.role, 0) + 1

    lines = [
        f"# Contactos de colaboración — {datetime.now():%Y-%m-%d}",
        "",
        f"- Emails encontrados: **{len(hits)}**",
        f"- Canales analizados: **{summary.get('creators', 0)}**",
        f"- Páginas visitadas: **{summary.get('pages', 0)}**",
        f"- Dominios consultados: **{summary.get('domains', 0)}**",
        f"- Peticiones servidas desde caché: **{summary.get('cache_hits', 0)}**",
        "",
        "## Por rol",
        "",
    ]
    for role, count in sorted(by_role.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {role}: {count}")
    lines += ["", "## Contactos", "", "| Canal | Plataforma | Seguidores | Email | Rol | Fuente |",
              "|---|---|---|---|---|---|"]
    for h in hits:
        source = h.source_url
        if source.startswith("http"):
            source = f"[{source[:38]}…]({source})" if len(source) > 38 else f"[{source}]({source})"
        lines.append(
            f"| {h.creator_name} | {h.platform} | {h.followers or '-'} | "
            f"{h.email} | {h.role} | {source} |"
        )
    lines += [
        "",
        "> Los correos provienen de páginas públicas (descripciones, mailto:, "
        "páginas de contacto). Filtra los que sean personales antes de escribir.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def write_candidates(candidates: list, path: str) -> None:
    """Canales salidos de la búsqueda, antes de mirar si tienen email.

    Sirve para revisar la lista a mano y decidir a quién escribir, sin tener que
    esperar a que termine el rastreo.
    """
    _ensure(path)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["plataforma", "canal", "senal", "url"]
        )
        writer.writeheader()
        for c in candidates:
            writer.writerow(
                {
                    "plataforma": c.platform,
                    "canal": c.label,
                    "senal": c.signal,
                    "url": c.target,
                }
            )


def usable(hits: list[Hit]) -> list[Hit]:
    """Solo los que apuntan a un buzón de contacto o negocio."""
    return [h for h in hits if h.role in PUBLIC_ROLES]


def _ensure(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)