"""Sensors for MiteMite."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .attributes import (
    UNRECORDED_ATTRIBUTES,
    count_attributes,
    episode_attributes,
    provider_attributes,
)
from .const import ATTRIBUTION, ATTRIBUTION_STREAMING
from .coordinator import ApiStatus, MiteMiteConfigEntry, MiteMiteCoordinator
from .entity import MiteMiteEntity, MiteMiteSystemEntity
from .models import Series, SeriesStatus

# Parallel updates are not needed: entities read the coordinator, never TMDB.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MiteMiteSensorDescription(SensorEntityDescription):
    """Describes a sensor of a followed series."""

    value_fn: Callable[[Series], StateType | date]
    attributes_fn: Callable[[Series], dict[str, Any]] | None = None
    uses_poster: bool = False
    attribution: str = ATTRIBUTION


@dataclass(frozen=True, kw_only=True)
class MiteMiteSystemSensorDescription(SensorEntityDescription):
    """Describes a diagnostic sensor of the MiteMite device."""

    value_fn: Callable[[MiteMiteCoordinator], StateType | datetime]
    attributes_fn: Callable[[MiteMiteCoordinator], dict[str, Any]] | None = None


def _next_episode_code(series: Series) -> str | None:
    return series.next_episode.code if series.next_episode else None


def _latest_episode_code(series: Series) -> str | None:
    return series.last_episode.code if series.last_episode else None


def _next_release(series: Series) -> date | None:
    return series.next_episode.air_date if series.next_episode else None


def _next_release_attributes(series: Series) -> dict[str, Any]:
    return {"episode": series.next_episode.code} if series.next_episode else {}


def _status(series: Series) -> str | None:
    # "unknown" would collide with Home Assistant's own unknown state.
    return None if series.status is SeriesStatus.UNKNOWN else series.status.value


def _upcoming_media_data(coordinator: MiteMiteCoordinator) -> list[dict[str, Any]]:
    """Build Upcoming Media Card items from all known future episodes."""
    today = dt_util.now().date()
    releases = [
        (episode.air_date, series.name.casefold(), episode.season_number,
         episode.number, series, episode)
        for series in coordinator.data.values()
        for episode in series.known_episodes
        if episode.air_date is not None and episode.air_date >= today
    ]
    # Keep the nearest upcoming release first.
    releases.sort(key=lambda item: item[:4])

    data: list[dict[str, Any]] = []
    for air_date, _, _, _, series, episode in releases:
        item = {
            "title": series.name,
            "episode": episode.name or episode.code,
            "number": episode.code,
            # The card expects an ISO 8601 timestamp, not just YYYY-MM-DD.
            "airdate": f"{air_date.isoformat()}T00:00:00Z",
            "poster": series.poster_url or "",
            "fanart": series.backdrop_url or "",
            "summary": episode.overview or "",
            "deep_link": series.tmdb_url or "",
        }
        # Empty optional values must be strings rather than null/missing.
        data.append(item)
    return data


SERIES_SENSORS: tuple[MiteMiteSensorDescription, ...] = (
    MiteMiteSensorDescription(
        key="next_episode",
        translation_key="next_episode",
        value_fn=_next_episode_code,
        attributes_fn=lambda series: episode_attributes(series, series.next_episode),
        uses_poster=True,
    ),
    MiteMiteSensorDescription(
        key="next_release",
        translation_key="next_release",
        device_class=SensorDeviceClass.DATE,
        value_fn=_next_release,
        attributes_fn=_next_release_attributes,
    ),
    MiteMiteSensorDescription(
        key="latest_episode",
        translation_key="latest_episode",
        value_fn=_latest_episode_code,
        attributes_fn=lambda series: episode_attributes(series, series.last_episode),
        uses_poster=True,
    ),
    MiteMiteSensorDescription(
        key="episodes_aired",
        translation_key="episodes_aired",
        value_fn=lambda series: series.aired_episode_count,
        attributes_fn=count_attributes,
    ),
    MiteMiteSensorDescription(
        key="series_status",
        translation_key="series_status",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in SeriesStatus if s is not SeriesStatus.UNKNOWN],
        value_fn=_status,
        attributes_fn=count_attributes,
    ),
    MiteMiteSensorDescription(
        key="streaming",
        translation_key="streaming",
        value_fn=lambda series: (
            len(series.providers.flatrate) if series.providers else 0
        ),
        attributes_fn=lambda series: provider_attributes(series.providers),
        attribution=ATTRIBUTION_STREAMING,
    ),
)

SYSTEM_SENSORS: tuple[MiteMiteSystemSensorDescription, ...] = (
    MiteMiteSystemSensorDescription(
        key="upcoming_media",
        translation_key="upcoming_media",
        icon="mdi:television-play",
        value_fn=lambda coordinator: len(_upcoming_media_data(coordinator)),
        attributes_fn=lambda coordinator: {
            "data": [
                {
                    "title_default": "$title",
                    "line1_default": "$episode",
                    "line2_default": "$number",
                    "line3_default": "$date",
                    "line4_default": "$empty",
                    "icon": "mdi:television-play",
                },
                *_upcoming_media_data(coordinator),
            ]
        },
    ),
    MiteMiteSystemSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.last_success,
    ),
    MiteMiteSystemSensorDescription(
        key="api_status",
        translation_key="api_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[status.value for status in ApiStatus],
        value_fn=lambda coordinator: coordinator.api_status.value,
        attributes_fn=lambda coordinator: (
            {"last_error": coordinator.last_error} if coordinator.last_error else {}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiteMiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MiteMite sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        MiteMiteSystemSensor(coordinator, description)
        for description in SYSTEM_SENSORS
    ]
    for series_id in coordinator.data:
        entities.extend(
            MiteMiteSensor(coordinator, series_id, description)
            for description in SERIES_SENSORS
        )
    async_add_entities(entities)


class MiteMiteSensor(MiteMiteEntity, SensorEntity):
    """A sensor of a followed series."""

    entity_description: MiteMiteSensorDescription
    _unrecorded_attributes = UNRECORDED_ATTRIBUTES

    def __init__(
        self,
        coordinator: MiteMiteCoordinator,
        series_id: int,
        description: MiteMiteSensorDescription,
    ) -> None:
        super().__init__(coordinator, series_id, description.key)
        self.entity_description = description
        self._attr_attribution = description.attribution

    @property
    def native_value(self) -> StateType | date:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.series)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the sensor attributes."""
        attributes_fn = self.entity_description.attributes_fn
        return attributes_fn(self.series) if attributes_fn else None

    @property
    def entity_picture(self) -> str | None:
        """Show the poster as the picture of episode sensors.

        Home Assistant asks for the picture even while the entity is
        unavailable, so a series TMDB dropped must not raise here.
        """
        if not self.entity_description.uses_poster:
            return None
        series = self.coordinator.data.get(self.series_id)
        return series.poster_url if series else None


class MiteMiteSystemSensor(MiteMiteSystemEntity, SensorEntity):
    """A diagnostic sensor of the MiteMite device."""

    entity_description: MiteMiteSystemSensorDescription

    def __init__(
        self,
        coordinator: MiteMiteCoordinator,
        description: MiteMiteSystemSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the sensor attributes."""
        attributes_fn = self.entity_description.attributes_fn
        return attributes_fn(self.coordinator) if attributes_fn else None
