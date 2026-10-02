"""MiteMite: TV and anime release tracking for Home Assistant."""

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up MiteMite services."""
    # Services will be added during MVP implementation.


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the MiteMite integration."""
    _async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up MiteMite from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a MiteMite config entry."""
    return True
