"""Estructuras de datos del escaner."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Creator:
    """Un canal ya resuelto, con su texto público y sus enlaces externos."""

    platform: str
    handle: str
    url: str
    name: str = ""
    followers: int | None = None
    description: str = ""
    external_links: list[str] = field(default_factory=list)
    declared_emails: list[tuple[str, str]] = field(default_factory=list)
    error: str = ""

    @property
    def label(self) -> str:
        return self.name or self.handle


@dataclass
class Hit:
    """Un email encontrado, con la evidencia de dónde salió."""

    email: str
    platform: str
    handle: str
    creator_name: str
    followers: int | None
    role: str
    kind: str
    source_url: str
    score: int
