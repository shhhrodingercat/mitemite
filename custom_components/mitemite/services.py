"""Actions of MiteMite."""

from collections import Counter
from datetime import date, timedelta

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .attributes import release_attributes
from .const import (
    ATTR_DAYS,
    ATTR_LIMIT,
    ATTR_START_DATE,
    DEFAULT_RELEASE_DAYS,
    DEFAULT_UPCOMING_LIMIT,
    DOMAIN,
    MAX_RELEASE_DAYS,
    MAX_UPCOMING_LIMIT,
    SERVICE_GET_RELEASES,
    SERVICE_GET_UPCOMING,
)
from .coordinator import MiteMiteConfigEntry
from .models import Episode, Series

GET_RELEASES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_DAYS, default=DEFAULT_RELEASE_DAYS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_RELEASE_DAYS)
        ),
    }
)

GET_UPCOMING_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_LIMIT, default=DEFAULT_UPCOMING_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_UPCOMING_LIMIT)
        ),
    }
)

type Release = tuple[Series, Episode]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions of MiteMite."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RELEASES,
        _async_get_releases,
        schema=GET_RELEASES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_UPCOMING,
        _async_get_upcoming,
        schema=GET_UPCOMING_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def _followed_series(hass: HomeAssistant) -> list[Series]:
    """Return the followed series, or fail if MiteMite is not loaded."""
    entries: list[MiteMiteConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_loaded"
        )
    return list(entries[0].runtime_data.coordinator.data.values())


def _air_order(release: Release) -> tuple[date, str, int, int, int]:
    """Sort by day, then series (name, then id), then episode."""
    series, episode = release
    return (
        episode.air_date or date.min,
        series.name.casefold(),
        series.id,
        episode.season_number,
        episode.number,
    )


def _releases(
    series_list: list[Series], start: date, end: date | None
) -> list[Release]:
    """Return the known releases from ``start`` up to ``end``, in air order.

    ``end`` is excluded; ``None`` means no end.

    Series without a calendar only know their last and next episode.
    """
    releases = [
        (series, episode)
        for series in series_list
        for episode in series.known_episodes
        if episode.air_date is not None
        and episode.air_date >= start
        and (end is None or episode.air_date < end)
    ]
    releases.sort(key=_air_order)
    return releases


def _titles(releases: list[Release]) -> list[str]:
    """Return the series titles of the releases, once each, ready for a message.

    The title is the series name; the first air year is added only when two
    different series in the result share a name, for example a remake.
    """
    series_by_id: dict[int, Series] = {}
    for series, _ in releases:
        series_by_id.setdefault(series.id, series)
    names = Counter(series.name.casefold() for series in series_by_id.values())
    return [
        series.display_name if names[series.name.casefold()] > 1 else series.name
        for series in series_by_id.values()
    ]


def _response(releases: list[Release]) -> ServiceResponse:
    return {
        "count": len(releases),
        "titles": _titles(releases),
        "releases": [
            release_attributes(series, episode) for series, episode in releases
        ],
    }


async def _async_get_releases(call: ServiceCall) -> ServiceResponse:
    """Return the episodes airing in a range of days."""
    start: date = call.data.get(ATTR_START_DATE) or dt_util.now().date()
    end = start + timedelta(days=call.data[ATTR_DAYS])
    return _response(_releases(_followed_series(call.hass), start, end))


async def _async_get_upcoming(call: ServiceCall) -> ServiceResponse:
    """Return the next episodes to air, from today on."""
    releases = _releases(_followed_series(call.hass), dt_util.now().date(), None)
    return _response(releases[: call.data[ATTR_LIMIT]])
