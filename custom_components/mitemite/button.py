"""Buttons for MiteMite."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import ApiStatus, MiteMiteConfigEntry, MiteMiteCoordinator
from .entity import MiteMiteSystemEntity

PARALLEL_UPDATES = 1

REFRESH = ButtonEntityDescription(
    key="refresh",
    translation_key="refresh",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiteMiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MiteMite buttons."""
    async_add_entities([MiteMiteRefreshButton(entry.runtime_data.coordinator)])


class MiteMiteRefreshButton(MiteMiteSystemEntity, ButtonEntity):
    """Button that updates every followed series from TMDB right away."""

    entity_description = REFRESH

    def __init__(self, coordinator: MiteMiteCoordinator) -> None:
        super().__init__(coordinator, REFRESH.key)

    async def async_press(self) -> None:
        """Refresh now, and tell the user when TMDB could not be reached."""
        await self.coordinator.async_refresh()
        if self.coordinator.api_status is not ApiStatus.OK:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="refresh_failed"
            )
