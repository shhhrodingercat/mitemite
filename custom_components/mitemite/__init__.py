"""MiteMite: TV and anime release tracking for Home Assistant."""

from datetime import datetime

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import TMDBClient
from .const import (
    CONF_LANGUAGE,
    CONF_REGION,
    CONF_SERIES_IDS,
    DEFAULT_LANGUAGE,
    DEFAULT_REGION,
    DOMAIN,
    SYSTEM_DEVICE_ID,
)
from .coordinator import MiteMiteConfigEntry, MiteMiteCoordinator, MiteMiteRuntimeData

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up MiteMite."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MiteMiteConfigEntry) -> bool:
    """Set up MiteMite from a config entry."""
    client = TMDBClient(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        language=entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        region=entry.options.get(CONF_REGION, DEFAULT_REGION),
    )
    coordinator = MiteMiteCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MiteMiteRuntimeData(client=client, coordinator=coordinator)

    _async_remove_stale_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_refresh_after_midnight(_now: datetime) -> None:
        """Fetch fresh data once the local date changes.

        TMDB moves an episode from "next" to "latest" on its own schedule, and
        the New episode sensor depends on today's date.
        """
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(
            hass, async_refresh_after_midnight, hour=0, minute=5, second=0
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MiteMiteConfigEntry) -> bool:
    """Unload MiteMite."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: MiteMiteConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting the device of a series that is no longer followed."""
    keep = _identifiers_to_keep(entry)
    return not any(
        domain == DOMAIN and identifier in keep
        for domain, identifier in device_entry.identifiers
    )


def _identifiers_to_keep(entry: MiteMiteConfigEntry) -> set[str]:
    """Return the device identifiers of the diagnostics and followed series."""
    return {
        SYSTEM_DEVICE_ID,
        *(str(series_id) for series_id in entry.options.get(CONF_SERIES_IDS, [])),
    }


def _async_remove_stale_devices(
    hass: HomeAssistant, entry: MiteMiteConfigEntry
) -> None:
    """Remove devices, and with them entities, of series no longer followed."""
    keep = _identifiers_to_keep(entry)
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not any(
            domain == DOMAIN and identifier in keep
            for domain, identifier in device.identifiers
        ):
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
