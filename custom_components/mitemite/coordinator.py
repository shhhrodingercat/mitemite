"""Data update coordinator for MiteMite."""

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    TMDBAuthError,
    TMDBClient,
    TMDBError,
    TMDBNotFoundError,
    TMDBRateLimitError,
)
from .const import CONF_CALENDAR_IDS, CONF_SERIES_IDS, DOMAIN
from .models import Series

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=6)
# After a failed update, try again sooner than the regular interval.
RETRY_INTERVAL = timedelta(minutes=15)
MAX_CONCURRENT_REQUESTS = 5


class ApiStatus(StrEnum):
    """Outcome of the latest TMDB update."""

    OK = "ok"
    INVALID_AUTH = "invalid_auth"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


type MiteMiteConfigEntry = ConfigEntry[MiteMiteRuntimeData]


class MiteMiteCoordinator(DataUpdateCoordinator[dict[int, Series]]):
    """Fetch every followed series from TMDB, one request each.

    Series in the calendar cost a second request: the episodes of their current
    season, needed to list more than the next episode.
    """

    config_entry: MiteMiteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MiteMiteConfigEntry,
        client: TMDBClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.api_status = ApiStatus.OK
        self.last_error: str | None = None
        self.last_success: datetime | None = None

    async def _async_update_data(self) -> dict[int, Series]:
        """Fetch the followed series, keeping stale data on partial failures.

        Series TMDB no longer has are left out. A failure for a series that has
        no earlier data fails the whole update, so setup is retried instead of
        starting with missing entities.
        """
        options = self.config_entry.options
        series_ids: list[int] = list(options.get(CONF_SERIES_IDS, []))
        calendar_ids = set(options.get(CONF_CALENDAR_IDS, []))
        previous = self.data or {}
        today = dt_util.now().date()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def fetch(series_id: int) -> Series:
            async with semaphore:
                series = await self.client.get_series(series_id)
                if series_id in calendar_ids:
                    series = await self._async_add_season(
                        series, previous.get(series_id), today
                    )
                return series

        results = await asyncio.gather(
            *(fetch(series_id) for series_id in series_ids), return_exceptions=True
        )

        data: dict[int, Series] = {}
        failures: list[tuple[int, TMDBError]] = []
        for series_id, result in zip(series_ids, results, strict=True):
            if isinstance(result, Series):
                data[series_id] = result
            elif isinstance(result, TMDBAuthError):
                self._record_failure(result)
                raise ConfigEntryAuthFailed("TMDB rejected the API key") from result
            elif isinstance(result, TMDBNotFoundError):
                _LOGGER.warning("TMDB no longer has series %s", series_id)
            elif isinstance(result, TMDBError):
                failures.append((series_id, result))
            else:
                raise result

        if not failures:
            self._record_success()
            return data

        error = failures[0][1]
        self._record_failure(error)
        if any(series_id not in previous for series_id, _ in failures):
            raise UpdateFailed(f"Could not fetch series from TMDB: {error}") from error
        _LOGGER.warning(
            "TMDB request failed for %d series, keeping their last data: %s",
            len(failures),
            error,
        )
        for series_id, _ in failures:
            data[series_id] = previous[series_id]
        return data

    async def _async_add_season(
        self, series: Series, previous: Series | None, today: date
    ) -> Series:
        """Attach the episodes of the current season that have not aired yet.

        The current season is the one of the next episode, or of the last one when
        nothing is scheduled. Episodes before today are never kept: the calendar
        does not list the past. A failure here is not worth failing the update: the
        episodes of the previous update are kept.
        """
        anchor = series.next_episode or series.last_episode
        if anchor is None:
            return series
        try:
            episodes = await self.client.get_season(
                series.id, anchor.season_number, since=today
            )
        except TMDBNotFoundError:
            return series
        except TMDBError as err:
            _LOGGER.warning(
                "Could not fetch the season of TMDB series %s, keeping its last "
                "episodes: %s",
                series.id,
                err,
            )
            return replace(series, episodes=previous.episodes) if previous else series
        return replace(series, episodes=episodes)

    def _record_success(self) -> None:
        self.api_status = ApiStatus.OK
        self.last_error = None
        self.last_success = dt_util.utcnow()
        self.update_interval = UPDATE_INTERVAL

    def _record_failure(self, error: TMDBError) -> None:
        if isinstance(error, TMDBAuthError):
            self.api_status = ApiStatus.INVALID_AUTH
        elif isinstance(error, TMDBRateLimitError):
            self.api_status = ApiStatus.RATE_LIMITED
        else:
            self.api_status = ApiStatus.ERROR
        self.last_error = str(error)
        self.update_interval = RETRY_INTERVAL
        # A failed update does not always notify listeners: the diagnostics
        # entities need to see the new status.
        self.async_update_listeners()


@dataclass
class MiteMiteRuntimeData:
    """Runtime data of a MiteMite config entry."""

    client: TMDBClient
    coordinator: MiteMiteCoordinator
