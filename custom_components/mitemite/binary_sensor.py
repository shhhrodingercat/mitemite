"""Binary sensors for MiteMite."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .attributes import UNRECORDED_ATTRIBUTES
from .const import CONF_NEW_EPISODE_DAYS, DEFAULT_NEW_EPISODE_DAYS
from .coordinator import MiteMiteConfigEntry, MiteMiteCoordinator
from .entity import MiteMiteEntity

PARALLEL_UPDATES = 0

NEW_EPISODE = BinarySensorEntityDescription(
    key="new_episode", translation_key="new_episode"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiteMiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MiteMite binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MiteMiteNewEpisodeSensor(coordinator, series_id)
        for series_id in coordinator.data
    )


class MiteMiteNewEpisodeSensor(MiteMiteEntity, BinarySensorEntity):
    """On for a few days after an episode airs.

    MiteMite does not track what you have watched, so "new" can only mean
    recent: the window is the ``new_episode_days`` option.
    """

    entity_description = NEW_EPISODE
    _unrecorded_attributes = UNRECORDED_ATTRIBUTES

    def __init__(self, coordinator: MiteMiteCoordinator, series_id: int) -> None:
        super().__init__(coordinator, series_id, NEW_EPISODE.key)

    @property
    def is_on(self) -> bool:
        """Return True if the latest episode aired within the window."""
        episode = self.series.last_episode
        if episode is None or episode.air_date is None:
            return False
        window = self.coordinator.config_entry.options.get(
            CONF_NEW_EPISODE_DAYS, DEFAULT_NEW_EPISODE_DAYS
        )
        return 0 <= (dt_util.now().date() - episode.air_date).days < window

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the episode that makes the series "new"."""
        episode = self.series.last_episode
        if episode is None:
            return None
        attributes: dict[str, Any] = {"episode": episode.code}
        if episode.air_date is not None:
            attributes["air_date"] = episode.air_date.isoformat()
        return attributes
