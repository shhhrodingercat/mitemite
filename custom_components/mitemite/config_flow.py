"""Config flow for MiteMite."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class MiteMiteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the MiteMite config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is not None:
            return self.async_create_entry(title="MiteMite", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("tmdb_api_key"): str}),
        )
