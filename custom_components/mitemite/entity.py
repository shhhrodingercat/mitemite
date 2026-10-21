"""Base entities for MiteMite."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME, SYSTEM_DEVICE_ID
from .coordinator import MiteMiteCoordinator
from .models import Series


class MiteMiteEntity(CoordinatorEntity[MiteMiteCoordinator]):
    """Base class for the entities of one followed series."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: MiteMiteCoordinator, series_id: int, key: str
    ) -> None:
        super().__init__(coordinator)
        self.series_id = series_id
        self._attr_unique_id = f"{series_id}_{key}"
        series = coordinator.data[series_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(series_id))},
            name=series.display_name,
            manufacturer="TMDB",
            model="Anime" if series.is_anime else "TV series",
            configuration_url=series.tmdb_url,
        )

    @property
    def series(self) -> Series:
        """Return the latest data of the series."""
        return self.coordinator.data[self.series_id]

    @property
    def available(self) -> bool:
        """Become unavailable if TMDB no longer has the series."""
        return super().available and self.series_id in self.coordinator.data


class MiteMiteSystemEntity(CoordinatorEntity[MiteMiteCoordinator]):
    """Base class for the entities of the MiteMite diagnostics device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MiteMiteCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{SYSTEM_DEVICE_ID}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, SYSTEM_DEVICE_ID)},
            name=NAME,
            manufacturer=NAME,
            model="TMDB client",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Stay available when TMDB fails: that is when they are most useful."""
        return True
