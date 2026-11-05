"""Ajustes por defecto del escaner."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# El cliente web público de Twitch. Se usa para leer la descripción del canal,
# que es información que el propio canal muestra públicamente.
TWITCH_PUBLIC_CLIENT_ID = os.environ.get(
    "TWITCH_PUBLIC_CLIENT_ID", "kimne78kx3ncx6brgo4mv6wki5h1ko"
)

# Credenciales de una app propia en dev.twitch.tv. Solo hacen falta para BUSCAR
# canales por palabra clave: la API oficial de búsqueda exige un app access
# token. No son la cuenta de nadie; el token es de servidor a servidor.
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")

# User-Agent identificable. Usa tu email para que el administrador del sitio sepa
# quién eres si decide contactarte.
DEFAULT_USER_AGENT = os.environ.get(
    "SCF_USER_AGENT",
    "sc-found-t/1.0 (+collaboration-outreach bot; contact: {email})",
)

# Hosts donde nunca vamos a buscar correos: no son contactos de negocio y
# borrarlos evita ruido y peticiones innecesarias.
SKIP_DOMAINS = {
    "youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com",
    "twitch.tv", "clips.twitch.tv", "m.twitch.tv",
    "twitter.com", "x.com", "t.co", "instagram.com", "t.me", "telegram.me",
    "facebook.com", "fb.com", "fb.me", "wa.me", "whatsapp.com",
    "discord.gg", "discord.com", "reddit.com", "redd.it",
    "google.com", "goo.gl", "youtube-nocookie.com", "bit.ly",
    "spotify.com", "open.spotify.com", "apple.com", "music.apple.com",
    "paypal.me", "paypal.com", "mercadopago.com", "mpago.la",
    "steamcommunity.com", "steam.tv", "epicgames.com", "epicgamescdn.com",
    "primer.link", "play.google.com", "apps.apple.com", "ko-fi.com",
    # infraestructura de las propias plataformas y CDNs de imagen
    "jtvnw.net", "ttvnw.net", "smoggy.com", "merchbar.com",
    "gstatic.com", "googleusercontent.com", "ggpht.com", "googleapis.com",
    "googletagmanager.com", "googlesyndication.com", "doubleclick.net",
    "jina.ai", "w3.org", "schema.org",
}

# Hosts donde el correo de contacto suele estar en la propia landing.
CONTACT_HOSTS = {
    "patreon.com", "ko-fi.com", "buymeacoffee.com", "about.me", "beacons.ai",
    "linktr.ee", "link.me", "gumroad.com", "boosty.to", "subscribebee.com",
    "fantrie.com", "pillar.rip", "snipfeed.co", "allmylinks.com",
    "solo.to", "stan.store", "shopify.com", "sellfy.com", "gumroad.com",
    "campsite.bio", "bio.fm", "milkshake.app", "beacons.com",
    "upgradedownsell.town", "instamojo.com", "tithe.com", "kofi.com",
    "tecioblanco.com", "donationalerts.com", "streamlabs.com",
    "my-free.website", "godaddy.com", "wixsite.com", "weebly.com",
}

# Rutas que se prueban en la raíz del sitio del creador, por orden de preferencia.
CONTACT_PATHS = [
    "/contacto", "/contact", "/contacts", "/contact-info",
    "/prensa", "/press", "/press-kit", "/presskit", "/kit-de-prensa", "/medios",
    "/negocios", "/business", "/colaboraciones", "/colaboracion", "/collab",
    "/partnerships", "/partnership", "/sponsors", "/sponsor", "/patrocinio",
    "/booking", "/management", "/manager", "/managers", "/agencia", "/agency",
    "/workwithus", "/work-with-us", "/hello", "/about", "/about-us", "/acercade",
]

# Extensiones que no son TLD aunque el regex las acepte (foo@2x.png, etc.).
FAKE_TLDS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tiff", "avif",
    "css", "js", "mjs", "json", "html", "htm", "php", "asp", "aspx", "jsp",
    "txt", "xml", "csv", "md", "pdf", "doc", "docx", "xls", "xlsx", "ppt",
    "mp3", "mp4", "webm", "m4a", "wav", "ogg", "avi", "mkv", "mov", "zip",
    "rar", "gz", "tar", "7z", "exe", "apk", "dmg", "woff", "woff2", "ttf",
    "eot", "otf", "scss", "less", "yml", "yaml", "epub", "psd", "ai", "ps",
}

# Dominios que casi nunca son el mail real del creador.
JUNK_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "domain.com",
    "yourdomain.com", "email.com", "mail.com", "youremail.com",
    "sentry.io", "wixpress.com", "cloudflare.com", "godaddy.com",
    "schema.org", "w3.org", "sentry.wixpress.com", "placeholder.com",
}

# Partes locales que indican que no es una casilla de contacto real.
# Casillas que nunca son un contacto: respuestas automaticas y avisos del sistema.
JUNK_LOCAL_PARTS = {
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "postmaster", "abuse", "hostmaster", "webmaster", "bounce", "bounces",
    "mailer-daemon", "sender", "returns", "undisclosed-recipients",
}

# Sufijos publicos de dos etiquetas: sin esta lista "canal.com.ar" se
# interpretaria mal y "canal.ar" pasaria por ser su dominio registrable.
MULTI_SUFFIXES = {
    "com.ar", "com.br", "com.mx", "com.co", "com.pe", "com.ve", "com.uy",
    "com.ec", "com.bo", "com.py", "com.cr", "com.pa", "com.do", "com.gt",
    "com.sv", "com.hn", "com.ni", "com.pr", "net.ar", "net.br", "net.mx",
    "org.ar", "org.br", "org.mx", "gob.es", "edu.es", "ac.uk", "gov.uk",
    "co.uk", "org.uk", "com.au", "com.tr", "com.pl", "com.ua", "co.jp",
    "co.nz", "co.kr", "com.sg", "com.hk", "com.tw", "co.in", "com.my",
}

CONSUMER_MAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.es", "outlook.com",
    "outlook.es", "live.com", "live.es", "msn.com", "yahoo.com", "yahoo.es",
    "icloud.com", "me.com", "mac.com", "protonmail.com", "proton.me",
    "pm.me", "fastmail.com", "zoho.com", "gmx.com", "gmx.es", "aol.com",
    "yandex.com", "yandex.ru", "mail.com", "tutanota.com", "hey.com",
}

PLACEHOLDER_LOCALS = {
    "tucorreo", "tunombre", "tuemail", "tumail", "tuusuario",
    "yourname", "yourmail", "youremail", "yourusername", "yourusername",
    "myemail", "mymail", "myname", "myusername",
    "nombre", "nombres", "apellido", "apellidos", "nombreapellido",
    "nombrecompleto", "fullname", "firstname", "lastname", "surname",
    "username", "emailaddress", "mailaddress", "ejemplo", "example",
    "placeholder", "dummy", "sample", "name", "names",
    "johndoe", "janedoe", "johnsmith", "fulanomengano", "fulanito",
    "correousuario", "usuariocorreo",
}

# TLDs usados para reconstruir correos ofuscados ("nombre (at) gmail (dot) com").
OBFUSCATED_TLDS = {
    "com", "net", "org", "io", "co", "ai", "app", "dev", "gg", "tv", "me",
    "xyz", "info", "biz", "es", "mx", "ar", "cl", "ve", "uy", "py", "pe",
    "br", "co", "ve", "ec", "bo", "cu", "do", "gt", "cr", "pa", "ni",
    "email", "online", "site", "store", "shop", "live", "pro", "cloud",
}


@dataclass
class Settings:
    """Ajustes de ejecución, todos sobrescribibles por CLI."""

    concurrency: int = 4
    delay_per_domain: float = 1.5
    timeout: float = 20.0
    max_pages_per_domain: int = 6
    max_domains_per_creator: int = 5
    max_domains_total: int = 60
    cache_ttl_hours: int = 168
    user_agent: str = DEFAULT_USER_AGENT
    contact_email: str = ""
    cache_dir: str = os.path.join(PROJECT_ROOT, ".cache")
    respect_robots: bool = True
    crawl: bool = True
    require_domain_match: bool = True
    cookies_from_browser: str = ""
    min_score: int = 0
    min_subscribers: int = 0
    twitch_client_id: str = TWITCH_CLIENT_ID
    twitch_client_secret: str = TWITCH_CLIENT_SECRET
    skip_domains: set = field(default_factory=lambda: set(SKIP_DOMAINS))

    def ua(self) -> str:
        return self.user_agent.format(email=self.contact_email or "TU-EMAIL-ACA")