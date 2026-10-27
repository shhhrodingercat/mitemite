"""Data models for MiteMite."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .const import (
    BACKDROP_SIZE,
    LOGO_SIZE,
    POSTER_SIZE,
    STILL_SIZE,
    TMDB_IMAGE_URL,
    TMDB_TV_URL,
)


def image_url(path: str | None, size: str) -> str | None:
    """Build a full TMDB image URL from an image path."""
    if not path:
        return None
    return f"{TMDB_IMAGE_URL}/{size}{path}"


class SeriesStatus(StrEnum):
    """Series status, as slugs usable as sensor enum options."""

    RETURNING = "returning"
    ENDED = "ended"
    CANCELED = "canceled"
    IN_PRODUCTION = "in_production"
    PLANNED = "planned"
    PILOT = "pilot"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Provider:
    """A streaming provider."""

    id: int
    name: str
    logo_path: str | None = None
    display_priority: int | None = None

    @property
    def logo_url(self) -> str | None:
        """Return the provider logo URL."""
        return image_url(self.logo_path, LOGO_SIZE)


@dataclass(frozen=True)
class WatchProviders:
    """Streaming availability of a series in one region."""

    region: str
    link: str | None = None
    flatrate: tuple[Provider, ...] = ()
    rent: tuple[Provider, ...] = ()
    buy: tuple[Provider, ...] = ()


@dataclass(frozen=True)
class Episode:
    """A TV episode as reported by TMDB.

    Anime are usually numbered in a single TMDB season with absolute episode
    numbers, so ``code`` can legitimately look like ``S01E1218``.
    """

    id: int
    season_number: int
    number: int
    name: str | None = None
    overview: str | None = None
    air_date: date | None = None
    episode_type: str | None = None
    runtime: int | None = None
    still_path: str | None = None

    @property
    def code(self) -> str:
        """Return the episode code, for example ``S01E52``."""
        return f"S{self.season_number:02d}E{self.number:02d}"

    @property
    def still_url(self) -> str | None:
        """Return the episode still URL."""
        return image_url(self.still_path, STILL_SIZE)


@dataclass(frozen=True)
class Series:
    """A TV series with everything MiteMite needs, from one TMDB request.

    ``episodes`` is filled by a second request, only for series in the calendar:
    it holds the episodes of the current season that have not aired yet.
    """

    id: int
    name: str
    original_name: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    first_air_date: date | None = None
    status: SeriesStatus = SeriesStatus.UNKNOWN
    in_production: bool = False
    is_anime: bool = False
    genres: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()
    origin_country: tuple[str, ...] = ()
    vote_average: float | None = None
    number_of_seasons: int = 0
    aired_episode_count: int = 0
    episodes_total: int = 0
    last_episode: Episode | None = None
    next_episode: Episode | None = None
    providers: WatchProviders | None = None
    episodes: tuple[Episode, ...] = ()

    @property
    def year(self) -> int | None:
        """Return the year of the first air date."""
        return self.first_air_date.year if self.first_air_date else None

    @property
    def display_name(self) -> str:
        """Return the name with the first air year, to tell remakes apart."""
        return f"{self.name} ({self.year})" if self.year else self.name

    @property
    def poster_url(self) -> str | None:
        """Return the poster URL."""
        return image_url(self.poster_path, POSTER_SIZE)

    @property
    def backdrop_url(self) -> str | None:
        """Return the backdrop URL."""
        return image_url(self.backdrop_path, BACKDROP_SIZE)

    @property
    def tmdb_url(self) -> str:
        """Return the TMDB page of the series."""
        return f"{TMDB_TV_URL}/{self.id}"

    @property
    def known_episodes(self) -> tuple[Episode, ...]:
        """Return the episodes with an air date TMDB tells us about, in air order.

        These are the last and next episode to air and, for series in the
        calendar, the episodes of the current season that have not aired yet.
        """
        known: dict[tuple[int, int], Episode] = {}
        for episode in (*self.episodes, self.last_episode, self.next_episode):
            if episode is not None and episode.air_date is not None:
                known.setdefault((episode.season_number, episode.number), episode)
        return tuple(
            sorted(
                known.values(),
                key=lambda e: (e.air_date, e.season_number, e.number),
            )
        )


@dataclass(frozen=True)
class SearchResult:
    """A series found by a TMDB search."""

    id: int
    name: str
    original_name: str | None = None
    first_air_date: date | None = None
    origin_country: tuple[str, ...] = ()
    is_anime: bool = False
