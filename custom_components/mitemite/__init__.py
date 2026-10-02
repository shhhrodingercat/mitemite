from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import voluptuous as vol

from .const import DOMAIN


CONFIG_SCHEMA = vol.All(
    config_entries.config_entry_only_config_schema(DOMAIN)
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up MiteMite."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
) -> bool:
    """Set up MiteMite from a config entry."""
    return True
