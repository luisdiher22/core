"""Test fixtures for runawaypet integration."""

import pytest

from homeassistant.components.runawaypet.const import (
    CONF_AUTO_CLOSE_GARAGE,
    CONF_BARRIER_ENTITIES,
    CONF_GARAGE_DOOR,
    CONF_NOTIFICATION_ENABLED,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Test Pet Safety",
        domain=DOMAIN,
        data={
            CONF_NAME: "Test Pet Safety",
            CONF_GARAGE_DOOR: "cover.test_garage",
            CONF_BARRIER_ENTITIES: [
                "input_boolean.test_pet_gate",
                "input_boolean.test_pet_door",
            ],
            CONF_AUTO_CLOSE_GARAGE: False,
            CONF_NOTIFICATION_ENABLED: True,
        },
        unique_id="test_pet_safety",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the runawaypet integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up test entities first
    hass.states.async_set("cover.test_garage", "closed")
    hass.states.async_set("input_boolean.test_pet_gate", "off")
    hass.states.async_set("input_boolean.test_pet_door", "off")

    # Register mock services that the integration needs
    async def mock_turn_off(call):
        """Mock turning off input_boolean entities."""
        entity_id = call.data.get("entity_id")
        if entity_id:
            hass.states.async_set(entity_id, "off")

    hass.services.async_register("input_boolean", "turn_off", mock_turn_off)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
