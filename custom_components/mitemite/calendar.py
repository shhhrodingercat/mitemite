"""Calendar for MiteMite."""

import json
from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .attributes import release_attributes
from .const import CALENDAR_KEY, CONF_CALENDAR_IDS, DOMAIN
from .coordinator import MiteMiteConfigEntry, MiteMiteCoordinator
from .entity import MiteMiteSystemEntity
from .models import Episode, Series

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiteMiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MiteMite calendar, if any series is in it."""
    if entry.options.get(CONF_CALENDAR_IDS):
        async_add_entities([MiteMiteCalendar(entry.runtime_data.coordinator)])


def _build_event(series: Series, episode: Episode, air_date: date) -> CalendarEvent:
    """Build the all-day event of an episode: TMDB has dates, not times."""
    description = json.dumps(
        release_attributes(series, episode), indent=2, ensure_ascii=False
    )
    return CalendarEvent(
        start=air_date,
        end=air_date + timedelta(days=1),
        summary=series.name,
        description=description,
        uid=f"{DOMAIN}-{series.id}-S{episode.season_number}E{episode.number}",
    )


def _overlaps(event: CalendarEvent, start: datetime, end: datetime) -> bool:
    """Return True if an all-day event overlaps the requested time range."""
    event_start = dt_util.start_of_local_day(event.start)
    event_end = dt_util.start_of_local_day(event.end)
    return event_start < end and event_end > start


class MiteMiteCalendar(MiteMiteSystemEntity, CalendarEntity):
    """The upcoming episodes of every series that is in the calendar.

    One all-day event per episode. The title of an event is the series name;
    everything else is in its description, as JSON. The past is never listed.
    """

    # The calendar is the main entity of the MiteMite device and takes its name.
    _attr_name = None
    _attr_translation_key = CALENDAR_KEY
    # The description repeats the series metadata: no need to record it.
    _unrecorded_attributes = frozenset({"description"})

    def __init__(self, coordinator: MiteMiteCoordinator) -> None:
        super().__init__(coordinator, CALENDAR_KEY)

    def _events(self) -> list[CalendarEvent]:
        """Return the events from today on, in air order."""
        calendar_ids = set(
            self.coordinator.config_entry.options.get(CONF_CALENDAR_IDS, [])
        )
        today = dt_util.now().date()
        events = [
            _build_event(series, episode, episode.air_date)
            for series_id, series in (self.coordinator.data or {}).items()
            if series_id in calendar_ids
            for episode in series.known_episodes
            if episode.air_date is not None and episode.air_date >= today
        ]
        events.sort(key=lambda event: (event.start, event.summary, event.uid or ""))
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the ongoing or next event."""
        events = self._events()
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events that overlap a time range."""
        return [
            event for event in self._events() if _overlaps(event, start_date, end_date)
        ]
