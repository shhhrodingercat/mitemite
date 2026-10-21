"""TMDB API client and response parsing for MiteMite."""

import logging
from datetime import date
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import DEFAULT_LANGUAGE, DEFAULT_REGION, TMDB_API_URL
from .models import (
    Episode,
    Provider,
    SearchResult,
    Series,
    SeriesStatus,
    WatchProviders,
)

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "Home Assistant MiteMite"
REQUEST_TIMEOUT = 30
SEARCH_MAX_PAGES = 3

ANIME_GENRE_ID = 16
ANIME_ORIGIN_COUNTRY = "JP"

_STATUS_MAP = {
    "Returning Series": SeriesStatus.RETURNING,
    "Ended": SeriesStatus.ENDED,
    "Canceled": SeriesStatus.CANCELED,
    "In Production": SeriesStatus.IN_PRODUCTION,
    "Planned": SeriesStatus.PLANNED,
    "Pilot": SeriesStatus.PILOT,
}

# Home Assistant language codes that TMDB spells differently.
_LANGUAGE_ALIASES = {"zh-Hans": "zh-CN", "zh-Hant": "zh-TW"}


class TMDBError(Exception):
    """Base error for TMDB requests."""


class TMDBConnectionError(TMDBError):
    """TMDB could not be reached."""


class TMDBAuthError(TMDBError):
    """TMDB rejected the API key."""


class TMDBNotFoundError(TMDBError):
    """The requested TMDB resource does not exist."""


class TMDBRateLimitError(TMDBError):
    """TMDB rate limit exceeded."""


def tmdb_language(language: str) -> str:
    """Convert a Home Assistant language code to a TMDB language code."""
    return _LANGUAGE_ALIASES.get(language, language)


def _text(value: Any) -> str | None:
    """Return a non-empty string, or None for empty or non-string values."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _parse_date(value: Any) -> date | None:
    """Parse an ISO date, treating empty or invalid values as unknown."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _positive_int(value: Any) -> int | None:
    """Return a positive integer, or None for null, zero and invalid values."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _float(value: Any) -> float | None:
    """Return a float, or None for missing and invalid values."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def is_anime(genre_ids: set[int], origin_country: tuple[str, ...]) -> bool:
    """TMDB has no anime flag: use Animation genre + Japanese origin."""
    return ANIME_GENRE_ID in genre_ids and ANIME_ORIGIN_COUNTRY in origin_country


def _origin_country(data: dict[str, Any]) -> tuple[str, ...]:
    return tuple(c for c in data.get("origin_country") or [] if isinstance(c, str))


def parse_episode(data: dict[str, Any] | None) -> Episode | None:
    """Parse a last/next episode to air, ignoring malformed data."""
    if not data:
        return None
    try:
        return Episode(
            id=int(data["id"]),
            season_number=int(data["season_number"]),
            number=int(data["episode_number"]),
            name=_text(data.get("name")),
            overview=_text(data.get("overview")),
            air_date=_parse_date(data.get("air_date")),
            episode_type=_text(data.get("episode_type")),
            runtime=_positive_int(data.get("runtime")),
            still_path=_text(data.get("still_path")),
        )
    except (KeyError, TypeError, ValueError):
        _LOGGER.debug("Ignoring malformed TMDB episode: %s", data)
        return None


def _parse_provider_list(items: Any) -> tuple[Provider, ...]:
    """Parse a provider list, ordered by TMDB display priority."""
    providers = [
        Provider(
            id=int(item["provider_id"]),
            name=str(item["provider_name"]),
            logo_path=_text(item.get("logo_path")),
            display_priority=item.get("display_priority"),
        )
        for item in items or []
        if isinstance(item, dict) and "provider_id" in item and "provider_name" in item
    ]
    return tuple(
        sorted(
            providers,
            key=lambda p: (p.display_priority is None, p.display_priority or 0),
        )
    )


def parse_watch_providers(data: dict[str, Any], region: str) -> WatchProviders:
    """Parse the appended watch/providers block for one region."""
    results = (data.get("watch/providers") or {}).get("results") or {}
    entry = results.get(region) or {}
    return WatchProviders(
        region=region,
        link=_text(entry.get("link")),
        flatrate=_parse_provider_list(entry.get("flatrate")),
        rent=_parse_provider_list(entry.get("rent")),
        buy=_parse_provider_list(entry.get("buy")),
    )


def count_episodes(
    data: dict[str, Any], last_episode: Episode | None
) -> tuple[int, int]:
    """Return (aired, total) episode counts without fetching any season.

    TMDB's ``number_of_episodes`` is unreliable: it includes scheduled episodes
    and can be off by one. The season list is consistent, so the total is the
    sum of regular seasons (season 0 holds specials) and the aired count is the
    episodes of earlier seasons plus the number of the last aired episode.
    """
    seasons = [
        season
        for season in data.get("seasons") or []
        if isinstance(season, dict)
        and isinstance(season.get("season_number"), int)
        and season["season_number"] > 0
    ]

    def episode_count(season: dict[str, Any]) -> int:
        count = season.get("episode_count")
        return count if isinstance(count, int) and count > 0 else 0

    total = sum(episode_count(season) for season in seasons)
    if not total:
        total = _positive_int(data.get("number_of_episodes")) or 0
    if last_episode is None:
        return 0, total
    earlier = sum(
        episode_count(season)
        for season in seasons
        if season["season_number"] < last_episode.season_number
    )
    return earlier + last_episode.number, total


def parse_series(data: dict[str, Any], region: str) -> Series:
    """Parse a /tv/{id} response (with watch/providers appended)."""
    genres = [g for g in data.get("genres") or [] if isinstance(g, dict)]
    genre_ids = {g["id"] for g in genres if isinstance(g.get("id"), int)}
    origin_country = _origin_country(data)
    last_episode = parse_episode(data.get("last_episode_to_air"))
    aired, total = count_episodes(data, last_episode)
    return Series(
        id=int(data["id"]),
        name=_text(data.get("name")) or _text(data.get("original_name")) or "",
        original_name=_text(data.get("original_name")),
        overview=_text(data.get("overview")),
        poster_path=_text(data.get("poster_path")),
        backdrop_path=_text(data.get("backdrop_path")),
        first_air_date=_parse_date(data.get("first_air_date")),
        status=_STATUS_MAP.get(data.get("status"), SeriesStatus.UNKNOWN),
        in_production=bool(data.get("in_production")),
        is_anime=is_anime(genre_ids, origin_country),
        genres=tuple(name for g in genres if (name := _text(g.get("name")))),
        networks=tuple(
            name
            for n in data.get("networks") or []
            if isinstance(n, dict) and (name := _text(n.get("name")))
        ),
        origin_country=origin_country,
        vote_average=_float(data.get("vote_average")),
        number_of_seasons=_positive_int(data.get("number_of_seasons")) or 0,
        aired_episode_count=aired,
        episodes_total=total,
        last_episode=last_episode,
        next_episode=parse_episode(data.get("next_episode_to_air")),
        providers=parse_watch_providers(data, region),
    )


def parse_search_result(item: dict[str, Any]) -> SearchResult | None:
    """Parse one /search/tv result, ignoring malformed entries."""
    try:
        series_id = int(item["id"])
    except (KeyError, TypeError, ValueError):
        return None
    name = _text(item.get("name")) or _text(item.get("original_name"))
    if name is None:
        return None
    genre_ids = {g for g in item.get("genre_ids") or [] if isinstance(g, int)}
    origin_country = _origin_country(item)
    return SearchResult(
        id=series_id,
        name=name,
        original_name=_text(item.get("original_name")),
        first_air_date=_parse_date(item.get("first_air_date")),
        origin_country=origin_country,
        is_anime=is_anime(genre_ids, origin_country),
    )


class TMDBClient:
    """Minimal async client for the parts of TMDB that MiteMite uses."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        *,
        language: str = DEFAULT_LANGUAGE,
        region: str = DEFAULT_REGION,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._language = tmdb_language(language)
        self._region = region

    @property
    def _uses_bearer_token(self) -> bool:
        """v4 read access tokens are JWTs; v3 keys are short hex strings."""
        return self._api_key.startswith("eyJ")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a TMDB endpoint, mapping failures to TMDBError subclasses.

        Errors never include the request URL, which carries the API key.
        """
        query: dict[str, Any] = {"language": self._language, **(params or {})}
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self._uses_bearer_token:
            headers["Authorization"] = f"Bearer {self._api_key}"
        else:
            query["api_key"] = self._api_key

        try:
            async with self._session.get(
                f"{TMDB_API_URL}{path}",
                params=query,
                headers=headers,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                status = response.status
                if status == 401:
                    raise TMDBAuthError("TMDB rejected the API key")
                if status == 404:
                    raise TMDBNotFoundError(f"TMDB resource not found: {path}")
                if status == 429:
                    raise TMDBRateLimitError("TMDB rate limit exceeded")
                if status >= 400:
                    raise TMDBError(f"TMDB returned HTTP {status}")
                data = await response.json()
        except TimeoutError:
            raise TMDBConnectionError("Timed out contacting TMDB") from None
        except ClientError as err:
            raise TMDBConnectionError(
                f"Cannot reach TMDB ({type(err).__name__})"
            ) from None
        except ValueError:
            raise TMDBError("TMDB returned invalid JSON") from None

        if not isinstance(data, dict):
            raise TMDBError("Unexpected response from TMDB")
        return data

    async def validate_key(self) -> None:
        """Check the API key and the connection with a cheap request."""
        await self._get("/configuration")

    async def search_tv(
        self, query: str, *, anime_only: bool = False
    ) -> list[SearchResult]:
        """Search series by title.

        TMDB cannot filter anime server side, so with ``anime_only`` the results
        are filtered here and up to SEARCH_MAX_PAGES pages are read.
        """
        results: list[SearchResult] = []
        max_pages = SEARCH_MAX_PAGES if anime_only else 1
        page = 1
        while page <= max_pages:
            data = await self._get("/search/tv", {"query": query, "page": page})
            for item in data.get("results") or []:
                if not isinstance(item, dict):
                    continue
                result = parse_search_result(item)
                if result is None or (anime_only and not result.is_anime):
                    continue
                results.append(result)
            if page >= (_positive_int(data.get("total_pages")) or 1):
                break
            page += 1
        return results

    async def get_series(self, series_id: int) -> Series:
        """Fetch a series, its last/next episode and its providers."""
        data = await self._get(
            f"/tv/{series_id}", {"append_to_response": "watch/providers"}
        )
        try:
            return parse_series(data, self._region)
        except (KeyError, TypeError, ValueError) as err:
            raise TMDBError("Unexpected series data from TMDB") from err
