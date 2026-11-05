"""Busca correos en los sitios externos que declara el creador.

Solo visita páginas públicas: la home del dominio del creador y rutas típicas de
contacto (/contacto, /press, /colaboraciones...). No hay formularios, ni login,
ni adivinado de casillas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import CONSUMER_MAIL, CONTACT_HOSTS, CONTACT_PATHS, Settings
from .extract import (
    classify_role,
    external_links,
    extract_emails,
    html_to_links,
    html_to_text,
    mailto_emails,
    registrable_domain,
)
from .fetcher import Fetcher, RobotsDenied, join, root_of
from .models import Creator, Hit


@dataclass
class Finding:
    email: str
    source_url: str
    kind: str


class SiteCrawler:
    def __init__(self, fetcher: Fetcher, settings: Settings) -> None:
        self.f = fetcher
        self.s = settings
        self.domains_used: set[str] = set()
        self.pages_scanned = 0

    async def scan_page(self, url: str) -> list[Finding]:
        html = await self.f.get(url)
        if not html:
            return []
        self.pages_scanned += 1

        findings: list[Finding] = []
        seen: set[str] = set()

        for addr in mailto_emails(html):
            seen.add(addr)
            findings.append(Finding(addr, url, "mailto"))

        text = html_to_text(html)
        hrefs = [u for u in html_to_links(html) if not u.startswith("mailto:")]
        for addr in extract_emails(text, *hrefs):
            if addr in seen:
                continue
            seen.add(addr)
            if not self._trustworthy(addr, url):
                continue
            findings.append(Finding(addr, url, "pagina"))

        return findings

    def _trustworthy(self, email: str, page_url: str) -> bool:
        """Descarta correos de terceros que aparecen en páginas de plataformas.

        Patreon, Ko-fi y similares muestran en su /contact los correos de su
        soporte (Zendesk, CDN de fuentes...). Salvo que sea un mailto declarado o
        un proveedor consumer, solo aceptamos correos del dominio de la web que
        estamos leyendo.
        """
        if not self.s.require_domain_match:
            return True
        email_domain = email.rpartition("@")[2].lower()
        if email_domain in CONSUMER_MAIL:
            return True
        page_domain = registrable_domain(page_url)
        if re.fullmatch(r"[\d.]+", page_domain) or page_domain == "localhost":
            return True
        return registrable_domain(email_domain) == page_domain

    async def crawl_domain(self, seed_url: str) -> list[Finding]:
        base = root_of(seed_url)
        findings = list(await self.scan_page(seed_url))
        scanned = 1
        for path in CONTACT_PATHS:
            if scanned >= self.s.max_pages_per_domain:
                break
            page = join(base, path)
            if page.rstrip("/") == seed_url.rstrip("/"):
                continue
            findings.extend(await self.scan_page(page))
            scanned += 1
        return findings

    async def crawl(self, creator: Creator) -> list[Hit]:
        if not creator.external_links:
            return []

        seeds = external_links(creator.external_links, self.s.skip_domains)
        seeds.sort(key=lambda u: (0 if is_contact_host(u) else 1, len(u)))

        by_domain: dict[str, str] = {}
        for url in seeds:
            dom = registrable_domain(url)
            if dom in by_domain or dom in self.domains_used:
                continue
            by_domain[dom] = url
            if len(by_domain) >= self.s.max_domains_per_creator:
                break

        hits: list[Hit] = []
        for dom, url in list(by_domain.items())[: self.s.max_domains_per_creator]:
            if len(self.domains_used) >= self.s.max_domains_total:
                print("  ! alcanzado el tope global de dominios")
                break
            self.domains_used.add(dom)
            try:
                findings = await self.crawl_domain(url)
            except RobotsDenied:
                print(f"    . {dom}: robots.txt no permite /contact")
                continue
            except Exception as exc:
                print(f"    ! {dom}: {type(exc).__name__}")
                continue
            for f in findings:
                hits.append(self._to_hit(creator, f))
        return hits

    def _to_hit(self, creator: Creator, f: Finding) -> Hit:
        role, score = classify_role(f.email)
        if f.kind == "mailto":
            score += 25
        return Hit(
            email=f.email,
            platform=creator.platform,
            handle=creator.handle,
            creator_name=creator.label,
            followers=creator.followers,
            role=role,
            kind=f.kind,
            source_url=f.source_url,
            score=score,
        )


def is_contact_host(url: str) -> bool:
    dom = registrable_domain(url)
    return dom in CONTACT_HOSTS


def contact_path_priority(url: str) -> int:
    return 0 if is_contact_host(url) else 1