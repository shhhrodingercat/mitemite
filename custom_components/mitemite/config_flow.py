"""Config flow for MiteMite."""

import asyncio
import logging
from collections.abc import Mapping
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TMDBAuthError,
    TMDBClient,
    TMDBConnectionError,
    TMDBError,
    TMDBRateLimitError,
)
from .const import (
    CONF_ANIME_ONLY,
    CONF_CALENDAR_IDS,
    CONF_LANGUAGE,
    CONF_NEW_EPISODE_DAYS,
    CONF_QUERY,
    CONF_REGION,
    CONF_SERIES_IDS,
    DEFAULT_LANGUAGE,
    DEFAULT_NEW_EPISODE_DAYS,
    DEFAULT_REGION,
    DOMAIN,
    MAX_NEW_EPISODE_DAYS,
    MIN_NEW_EPISODE_DAYS,
    NAME,
)
from .models import SearchResult, Series

_LOGGER = logging.getLogger(__name__)

# Concurrent TMDB requests when resolving the names of tracked series.
_NAME_LOOKUP_CONCURRENCY = 5


def _error_key(err: TMDBError) -> str:
    """Map a TMDB error to a form error key."""
    if isinstance(err, TMDBAuthError):
        return "invalid_auth"
    if isinstance(err, TMDBConnectionError | TMDBRateLimitError):
        return "cannot_connect"
    return "unknown"


def _api_key_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


def _region_selector() -> selector.CountrySelector:
    return selector.CountrySelector()


def _language_selector() -> selector.LanguageSelector:
    return selector.LanguageSelector(selector.LanguageSelectorConfig(native_name=True))


def _credentials_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): _api_key_selector(),
            vol.Required(CONF_REGION): _region_selector(),
            vol.Required(CONF_LANGUAGE): _language_selector(),
        }
    )


def _search_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_QUERY): str,
            vol.Optional(CONF_ANIME_ONLY, default=False): bool,
        }
    )


def _format_label(
    name: str, first_air_date: date | None, origin_country: tuple[str, ...]
) -> str:
    """Format a series for a selection list, for example ``Title · 2026 · JP``."""
    parts = [name]
    if first_air_date:
        parts.append(str(first_air_date.year))
    if origin_country:
        parts.append("/".join(origin_country))
    return " · ".join(parts)


def _selection_schema(options: list[dict[str, str]]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SERIES_IDS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _calendar_schema(options: list[dict[str, str]]) -> vol.Schema:
    """Build the form that picks the series with a calendar: none by default."""
    return vol.Schema(
        {
            vol.Optional(CONF_CALENDAR_IDS, default=list): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _chosen_calendar_ids(user_input: dict[str, Any], allowed: list[int]) -> list[int]:
    """Return the series picked in a calendar form, in the order of ``allowed``."""
    picked = {int(series_id) for series_id in user_input.get(CONF_CALENDAR_IDS, [])}
    return [series_id for series_id in allowed if series_id in picked]


def _search_options(results: list[SearchResult]) -> list[dict[str, str]]:
    return [
        {
            "value": str(result.id),
            "label": _format_label(
                result.name, result.first_air_date, result.origin_country
            ),
        }
        for result in results
    ]


async def _search(
    client: TMDBClient, user_input: dict[str, Any]
) -> tuple[list[SearchResult], dict[str, str]]:
    """Run a search form submission, returning results or form errors."""
    query = str(user_input.get(CONF_QUERY, "")).strip()
    if not query:
        return [], {CONF_QUERY: "empty_query"}
    try:
        results = await client.search_tv(
            query, anime_only=bool(user_input.get(CONF_ANIME_ONLY, False))
        )
    except TMDBError as err:
        _LOGGER.warning("TMDB search failed: %s", err)
        return [], {"base": _error_key(err)}
    if not results:
        return [], {CONF_QUERY: "no_results"}
    return results, {}


class MiteMiteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the MiteMite config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key = ""
        self._region = DEFAULT_REGION
        self._language = DEFAULT_LANGUAGE
        self._results: list[SearchResult] = []
        self._selected: list[int] = []

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> "MiteMiteOptionsFlow":
        """Return the options flow for managing followed series."""
        return MiteMiteOptionsFlow()

    @property
    def _client(self) -> TMDBClient:
        return TMDBClient(
            async_get_clientsession(self.hass),
            self._api_key,
            language=self._language,
            region=self._region,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key, region and language, and validate the key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            self._region = user_input[CONF_REGION]
            self._language = user_input[CONF_LANGUAGE]
            try:
                await self._client.validate_key()
            except TMDBError as err:
                _LOGGER.warning("TMDB key validation failed: %s", err)
                errors["base"] = _error_key(err)
            else:
                return await self.async_step_search()

        suggested = user_input or {
            CONF_REGION: self.hass.config.country or DEFAULT_REGION,
            CONF_LANGUAGE: self.hass.config.language or DEFAULT_LANGUAGE,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _credentials_schema(), suggested
            ),
            errors=errors,
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for the first series to follow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            results, errors = await _search(self._client, user_input)
            if not errors:
                self._results = results
                return await self.async_step_select()
        return self.async_show_form(
            step_id="search", data_schema=_search_schema(), errors=errors
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the series to follow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = [int(series_id) for series_id in user_input[CONF_SERIES_IDS]]
            if selected:
                self._selected = selected
                return await self.async_step_calendars()
            errors["base"] = "select_at_least_one"
        return self.async_show_form(
            step_id="select",
            data_schema=_selection_schema(_search_options(self._results)),
            errors=errors,
        )

    async def async_step_calendars(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which of the selected series get a calendar, then create the entry."""
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={CONF_API_KEY: self._api_key},
                options={
                    CONF_SERIES_IDS: self._selected,
                    CONF_CALENDAR_IDS: _chosen_calendar_ids(user_input, self._selected),
                    CONF_REGION: self._region,
                    CONF_LANGUAGE: self._language,
                    CONF_NEW_EPISODE_DAYS: DEFAULT_NEW_EPISODE_DAYS,
                },
            )
        selected = [result for result in self._results if result.id in self._selected]
        return self.async_show_form(
            step_id="calendars",
            data_schema=_calendar_schema(_search_options(selected)),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when TMDB rejects the stored key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            client = TMDBClient(async_get_clientsession(self.hass), api_key)
            try:
                await client.validate_key()
            except TMDBError as err:
                _LOGGER.warning("TMDB key validation failed: %s", err)
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): _api_key_selector()}),
            errors=errors,
        )


class MiteMiteOptionsFlow(OptionsFlowWithReload):
    """Add or remove followed series, choose their calendars and change settings.

    Every step stores the full options dict: an options flow replaces it.
    """

    def __init__(self) -> None:
        self._results: list[SearchResult] = []
        self._added: list[int] = []
        self._tracked_options: list[dict[str, str]] | None = None

    @property
    def _client(self) -> TMDBClient:
        options = self.config_entry.options
        return TMDBClient(
            async_get_clientsession(self.hass),
            self.config_entry.data[CONF_API_KEY],
            language=options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            region=options.get(CONF_REGION, DEFAULT_REGION),
        )

    @property
    def _tracked_ids(self) -> list[int]:
        return list(self.config_entry.options.get(CONF_SERIES_IDS, []))

    @property
    def _calendar_ids(self) -> list[int]:
        return list(self.config_entry.options.get(CONF_CALENDAR_IDS, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what to change."""
        menu = ["add_search"]
        if self._tracked_ids:
            menu.extend(["remove", "calendars"])
        menu.append("settings")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for additional series."""
        errors: dict[str, str] = {}
        if user_input is not None:
            results, errors = await _search(self._client, user_input)
            if not errors:
                tracked = set(self._tracked_ids)
                self._results = [r for r in results if r.id not in tracked]
                if self._results:
                    return await self.async_step_add_select()
                errors = {CONF_QUERY: "already_tracked"}
        return self.async_show_form(
            step_id="add_search", data_schema=_search_schema(), errors=errors
        )

    async def async_step_add_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select series to add."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = [int(series_id) for series_id in user_input[CONF_SERIES_IDS]]
            if selected:
                self._added = selected
                return await self.async_step_add_calendars()
            errors["base"] = "select_at_least_one"
        return self.async_show_form(
            step_id="add_select",
            data_schema=_selection_schema(_search_options(self._results)),
            errors=errors,
        )

    async def async_step_add_calendars(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which of the added series get a calendar, then save both lists."""
        if user_input is not None:
            updated = list(dict.fromkeys([*self._tracked_ids, *self._added]))
            chosen = _chosen_calendar_ids(user_input, self._added)
            calendars = list(dict.fromkeys([*self._calendar_ids, *chosen]))
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_SERIES_IDS: updated,
                    CONF_CALENDAR_IDS: calendars,
                }
            )
        added = [result for result in self._results if result.id in self._added]
        return self.async_show_form(
            step_id="add_calendars",
            data_schema=_calendar_schema(_search_options(added)),
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select series to stop following."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = {int(series_id) for series_id in user_input[CONF_SERIES_IDS]}
            if selected:
                remaining = [i for i in self._tracked_ids if i not in selected]
                calendars = [i for i in self._calendar_ids if i in remaining]
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        CONF_SERIES_IDS: remaining,
                        CONF_CALENDAR_IDS: calendars,
                    }
                )
            errors["base"] = "select_at_least_one"
        return self.async_show_form(
            step_id="remove",
            data_schema=_selection_schema(await self._async_tracked_options()),
            errors=errors,
        )

    async def async_step_calendars(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Turn the calendar of each followed series on or off."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_CALENDAR_IDS: _chosen_calendar_ids(
                        user_input, self._tracked_ids
                    ),
                }
            )
        schema = _calendar_schema(await self._async_tracked_options())
        return self.async_show_form(
            step_id="calendars",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {CONF_CALENDAR_IDS: [str(i) for i in self._calendar_ids]},
            ),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change region, language and the new-episode window."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                    CONF_NEW_EPISODE_DAYS: int(user_input[CONF_NEW_EPISODE_DAYS]),
                }
            )
        schema = vol.Schema(
            {
                vol.Required(CONF_REGION): _region_selector(),
                vol.Required(CONF_LANGUAGE): _language_selector(),
                vol.Required(CONF_NEW_EPISODE_DAYS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_NEW_EPISODE_DAYS,
                        max=MAX_NEW_EPISODE_DAYS,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_REGION: DEFAULT_REGION,
                    CONF_LANGUAGE: DEFAULT_LANGUAGE,
                    CONF_NEW_EPISODE_DAYS: DEFAULT_NEW_EPISODE_DAYS,
                    **self.config_entry.options,
                },
            ),
        )

    async def _async_tracked_options(self) -> list[dict[str, str]]:
        """Return selection options labelled with the names of tracked series.

        Names come from the coordinator when the entry is loaded. Series it does
        not have (the entry is not loaded, or TMDB could not provide them) are
        looked up on TMDB, one request each with limited concurrency, and fall
        back to their id. The result is cached so that re-showing the form after
        an error costs nothing.
        """
        if self._tracked_options is None:
            runtime_data = getattr(self.config_entry, "runtime_data", None)
            known: dict[int, Series] = (
                dict(runtime_data.coordinator.data or {}) if runtime_data else {}
            )
            ids = self._tracked_ids
            missing = [series_id for series_id in ids if series_id not in known]
            if missing:
                client = self._client
                semaphore = asyncio.Semaphore(_NAME_LOOKUP_CONCURRENCY)

                async def lookup(series_id: int) -> Series:
                    async with semaphore:
                        return await client.get_series(series_id)

                results = await asyncio.gather(
                    *(lookup(series_id) for series_id in missing),
                    return_exceptions=True,
                )
                for series_id, result in zip(missing, results, strict=True):
                    if isinstance(result, Series):
                        known[series_id] = result
                    else:
                        _LOGGER.debug("Could not resolve TMDB series %s", series_id)
            options: list[dict[str, str]] = []
            for series_id in ids:
                series = known.get(series_id)
                if series:
                    label = _format_label(
                        series.name, series.first_air_date, series.origin_country
                    )
                else:
                    label = f"TMDB {series_id}"
                options.append({"value": str(series_id), "label": label})
            self._tracked_options = options
        return self._tracked_options
