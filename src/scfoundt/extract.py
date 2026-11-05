"""Extracción de emails y enlaces desde texto plano o HTML."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from .config import (
    FAKE_TLDS,
    JUNK_EMAIL_DOMAINS,
    JUNK_LOCAL_PARTS,
    MULTI_SUFFIXES,
    OBFUSCATED_TLDS,
    PLACEHOLDER_LOCALS,
    SKIP_DOMAINS,
)

EMAIL_RE = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.){1,6}[A-Za-z]{2,24}"
    r"(?![\w.-])"
)

# "nombre (at) dominio (dot) com" / "nombre [at] dominio [dot] com" / "nombre at dominio dot com"
OBFUSC_RE = re.compile(
    r"(?<![\w@.-])([A-Za-z0-9][A-Za-z0-9._%+-]{0,63})"
    r"\s*[\(\[{<]?\s*(?:@|at|arroba|en)\s*[\)\]}>]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9.-]{0,62}[A-Za-z0-9])"
    r"\s*[\(\[{<]?\s*(?:dot|punto|punto\s+com|\.)\s*[\)\]}>]?\s*"
    r"([A-Za-z]{2,10})\b",
    re.IGNORECASE,
)

ROLE_PRIORITY = [
    (r"^(?:hola|hello|hi|hey|contacto|contact|info|informacion|general|mail|"
     r"email|ayuda|support|escribeme|write|dm)", "contacto", 60),
    (r"(?:colabor|colab|partnership|partnerships|business|negocios|negocio|"
     r"comercial|b2b|sponsor|sponsors|patrocinio|patrocinador|ads|advertising)",
     "colaboraciones", 70),
    (r"(?:press|prensa|media|medios|comunicacion|news)", "prensa", 55),
    (r"(?:manager|management|agente|agency|represent|book)", "gestión", 50),
    (r"(?:legal|abogado|law)", "legal", 10),
    (r"(?:factur|billing|invoice|facturación)", "facturación", 5),
]

PUBLIC_ROLES = {"contacto", "colaboraciones", "prensa", "gestión"}


def html_to_text(html: str) -> str:
    """Convierte HTML en texto legible, respetando los enlaces mailto:."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def html_to_links(html: str) -> list[str]:
    """URLs absolutas que aparecen como href/src en el documento."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for tag in soup.find_all(["a", "link", "img", "source", "meta"]):
        raw = None
        if tag.name == "meta" and tag.get("property") in (
            "og:url", "og:description"
        ):
            raw = tag.get("content")
        else:
            raw = tag.get("href") or tag.get("src") or tag.get("content")
        if not raw:
            continue
        raw = raw.strip()
        if raw.startswith("mailto:"):
            urls.append("mailto:" + unquote(raw[7:]).split("?")[0])
        elif raw.startswith(("http://", "https://", "//")):
            urls.append("https://" + raw[2:] if raw.startswith("//") else raw)
    return urls


def text_to_links(text: str) -> list[str]:
    """URLs escritas en texto plano (descripciones de YouTube/Twitch)."""
    found = re.findall(r"(?:https?://|www\.)[^\s<>\"'\)\]\},;|]+", text, re.IGNORECASE)
    out = []
    for u in found:
        u = u.rstrip(".,;:)]}")
        out.append("https://" + u[4:] if u.lower().startswith("www.") else u)
    return out


def is_junk(email: str) -> bool:
    local, _, domain = email.partition("@")
    local = local.lower()
    domain = domain.lower()
    if local in JUNK_LOCAL_PARTS:
        return True
    if re.sub(r"[^a-z0-9]", "", local) in PLACEHOLDER_LOCALS:
        return True
    if domain in JUNK_EMAIL_DOMAINS:
        return True
    if domain.rsplit(".", 1)[-1] in FAKE_TLDS:
        return True
    if any(part.startswith("-") or part.endswith("-") for part in domain.split(".")):
        return True
    if not re.search(r"[a-z]{2,}", local):
        return True  # 000123@... es un id de transacción, no un correo
    return False


def normalize(email: str) -> str:
    email = unquote(email).strip().strip(".,;:").lower()
    email = re.sub(r"^(?:mailto:)", "", email)
    email = re.sub(r"\s+", "", email)
    return email


def classify_role(email: str) -> tuple[str, int]:
    local, _, domain = email.partition("@")
    local = local.replace(".", " ").replace("_", " ").replace("-", " ")
    text = f"{local} {domain.rsplit('.', 1)[-1]}"
    for pattern, role, score in ROLE_PRIORITY:
        if re.search(pattern, local) or re.search(pattern, text):
            return role, score
    return "sin_clasificar", 20


def deobfuscate(text: str) -> list[str]:
    """Reconstruye correos escritos para evitar los scrapers."""
    out: list[str] = []
    for local, mid, tld in OBFUSC_RE.findall(text):
        tld = tld.lower()
        if tld not in OBFUSCATED_TLDS:
            continue
        mid = mid.strip(".-").lower()
        if not mid or not re.search(r"[a-z]", mid):
            continue
        candidate = f"{local.lower()}@{mid}.{tld}"
        if candidate not in out:
            out.append(candidate)
    return out


def extract_emails(*sources: str) -> list[str]:
    """Emails válidos y normalizados de varios textos (HTML o plano)."""
    seen: list[str] = []
    for src in sources:
        if not src:
            continue
        candidates = EMAIL_RE.findall(src)
        candidates += deobfuscate(src)
        for raw in candidates:
            email = normalize(raw)
            if not email or is_junk(email):
                continue
            if email not in seen:
                seen.append(email)
    return seen


def external_links(urls: list[str], skip_domains: set[str]) -> list[str]:
    """Filtra URLs: fuera de plataformas sociales y fuera de mailto."""
    out: list[str] = []
    for u in urls:
        if u.startswith("mailto:"):
            continue
        parts = urlparse(u)
        host = parts.netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
        if not host or "." not in host:
            continue
        registrable = ".".join(host.split(".")[-2:])
        if host in skip_domains or registrable in skip_domains:
            continue
        if any(host.endswith("." + d) or host == d for d in skip_domains):
            continue
        clean = u.split("#")[0].rstrip("/")
        if clean not in out:
            out.append(clean)
    return out


def registrable_domain(url_or_host: str) -> str:
    """Dominio registrable: 'www.a.com.ar' -> 'a.com.ar', IPs sin tocar."""
    host = url_or_host
    if "://" in host or host.startswith("//"):
        host = urlparse(host).netloc
    host = host.strip().lower().split("/")[0].split("@")[-1].split(":")[0]
    if not host or "." not in host:
        return host
    if re.fullmatch(r"[\d.]+", host) or ":" in host or host == "localhost":
        return host
    host = host[4:] if host.startswith("www.") else host
    labels = host.split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    tail2 = ".".join(labels[-2:])
    if tail2 in MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail2


def mailto_emails(html: str) -> list[str]:
    """Solo los href="mailto:" reales: señal fuerte de contacto publicado."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            addr = normalize(href[7:].split("?")[0])
            if addr and not is_junk(addr):
                out.append(addr)
    return out


DEFAULT_SKIP = set(SKIP_DOMAINS)