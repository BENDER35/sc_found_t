"""Resuelve canales de Twitch leyendo su descripción pública.

Twitch renderiza /about en cliente, así que se usa su endpoint GraphQL público,
el mismo que usa la web para pintar la descripción del canal. No hay login.
"""

from __future__ import annotations

import re

from .config import TWITCH_PUBLIC_CLIENT_ID, Settings
from .extract import DEFAULT_SKIP, external_links, text_to_links
from .fetcher import Fetcher
from .models import Creator

GQL_URL = "https://gql.twitch.tv/gql"

QUERY = """
query {
  user(login: "%s") {
    id
    login
    displayName
    description
    profileImageURL(width: 300)
  }
}
"""


def is_twitch(target: str) -> bool:
    return "twitch.tv" in target.lower()


def normalize_input(target: str) -> str:
    t = target.strip().rstrip("/")
    m = re.search(r"(?:^|\/\/)(?:www\.|m\.)?twitch\.tv\/([^/?#]+)", t, re.IGNORECASE)
    if m:
        return m.group(1)
    if t.lower().startswith("twitch.tv/"):
        return t.split("/", 1)[1].split("/")[0].split("?")[0]
    return t.lstrip("@").split("/")[0]


async def resolve(target: str, settings: Settings, fetcher: Fetcher) -> Creator:
    login = normalize_input(target)
    url = f"https://www.twitch.tv/{login}"

    headers = {"Client-ID": TWITCH_PUBLIC_CLIENT_ID}
    data = await fetcher.post_json(
        GQL_URL, {"query": QUERY % login.replace('"', "")}, headers
    )
    user = (data or {}).get("data", {}).get("user") if data else None

    if not user:
        return Creator("twitch", handle=login, url=url, error="canal no encontrado")

    description = user.get("description") or ""

    # La pagina /about de Twitch se pinta en cliente y no trae los enlaces del
    # canal en el HTML, asi que solo se trabaja con la bio que devuelve gql.
    return Creator(
        platform="twitch",
        handle=user.get("login") or login,
        url=url,
        name=user.get("displayName") or "",
        followers=None,
        description=description,
        external_links=external_links(
            text_to_links(description), settings.skip_domains or DEFAULT_SKIP
        ),
    )
