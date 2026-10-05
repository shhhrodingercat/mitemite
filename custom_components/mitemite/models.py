"""Data models for MiteMite."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """A streaming provider."""

    id: int
    name: str
    logo_path: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Episode:
    """A TV episode."""

    id: int
    number: int
    name: str
    overview: str | None = None
    air_date: str | None = None


@dataclass(frozen=True)
class Season:
    """A TV season."""

    series_id: int
    number: int
    name: str
    episodes: tuple[Episode, ...] = ()


@dataclass(frozen=True)
class Series:
    """A TV series."""

    id: int
    name: str
    overview: str | None = None
    poster_path: str | None = None
    providers: tuple[Provider, ...] = ()
