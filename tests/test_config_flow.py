"""Tests for the MiteMite config flow."""

from homeassistant import config_entries

from custom_components.mitemite.const import DOMAIN


async def test_form(hass, enable_custom_integrations):
    """Test the initial form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"tmdb_api_key": "test-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "MiteMite"
    assert result["data"] == {"tmdb_api_key": "test-key"}
