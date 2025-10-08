"""Config flow for the runaway pet protection integration.

This module handles the user interface for setting up the pet safety integration.
The config flow allows users to:

1. Select which garage door to monitor for pet safety
2. Choose barrier entities (doors, covers, switches) that should be secured
3. Configure whether to automatically close the garage if barriers fail
4. Enable/disable notifications for manual intervention

The config flow validates entities exist and prevents duplicate configurations
for the same garage door.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CONF_AUTO_CLOSE_GARAGE,
    CONF_BARRIER_ENTITIES,
    CONF_GARAGE_DOOR,
    CONF_NOTIFICATION_ENABLED,
    DEFAULT_AUTO_CLOSE_GARAGE,
    DEFAULT_NOTIFICATION_ENABLED,
    DOMAIN,
)


def _get_cover_entities(hass: HomeAssistant) -> dict[str, str]:
    """Get all cover entities that could be garage doors.

    Searches the entity registry for cover entities that are enabled
    and have current states, which could potentially be garage doors.

    Args:
        hass: Home Assistant instance

    Returns:
        Dictionary mapping entity IDs to friendly names
    """
    entity_registry = er.async_get(hass)
    covers = {}

    for entity in entity_registry.entities.values():
        # Only include enabled cover entities
        if entity.domain == "cover" and entity.disabled_by is None:
            state = hass.states.get(entity.entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity.entity_id)
                covers[entity.entity_id] = friendly_name

    return covers


def _get_barrier_entities(hass: HomeAssistant) -> dict[str, str]:
    """Get all entities that could be barriers (doors, covers, switches).

    Searches for entities that could represent barriers that pets might
    escape through. Includes:
    - Covers: doors, windows, pet doors
    - Switches: smart locks, automated gates
    - Input booleans: manual barrier indicators
    - Binary sensors: door/window sensors

    Args:
        hass: Home Assistant instance

    Returns:
        Dictionary mapping entity IDs to friendly names
    """
    entity_registry = er.async_get(hass)
    barriers = {}

    # Entity domains that could represent barriers
    barrier_domains = ["cover", "switch", "input_boolean", "binary_sensor"]

    for entity in entity_registry.entities.values():
        # Only include enabled entities from barrier domains
        if entity.domain in barrier_domains and entity.disabled_by is None:
            state = hass.states.get(entity.entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity.entity_id)
                barriers[entity.entity_id] = friendly_name

    return barriers


class RunawayPetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Runaway Pet Protection.

    This config flow guides users through setting up pet safety monitoring
    by collecting the necessary configuration:

    1. Garage door entity to monitor
    2. Barrier entities that should be secured when garage opens
    3. Behavior preferences (auto-close garage, notifications)

    The flow includes validation to ensure selected entities exist and
    prevents duplicate configurations for the same garage door.
    """

    # Config flow version for handling future schema changes
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step where user configures pet safety.

        This presents a form asking the user to:
        - Select which garage door to monitor
        - Choose barrier entities to secure
        - Configure automation behavior options

        Args:
            user_input: Form data submitted by user (None on first display)

        Returns:
            ConfigFlowResult with form to display or entry creation result
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # User submitted the form - validate the input

            # Validate that garage door entity exists and is accessible
            garage_door = user_input[CONF_GARAGE_DOOR]
            if not self.hass.states.get(garage_door):
                errors[CONF_GARAGE_DOOR] = "entity_not_found"

            # Validate that all selected barrier entities exist
            barrier_entities = user_input[CONF_BARRIER_ENTITIES]
            for entity_id in barrier_entities:
                if not self.hass.states.get(entity_id):
                    errors[CONF_BARRIER_ENTITIES] = "entity_not_found"
                    break

            if not errors:
                # All validation passed - create the config entry

                # Use garage door entity as unique ID to prevent duplicates
                await self.async_set_unique_id(garage_door)
                self._abort_if_unique_id_configured()

                # Create a user-friendly title for the integration entry
                garage_name = self.hass.states.get(garage_door).attributes.get(
                    "friendly_name", garage_door
                )

                return self.async_create_entry(
                    title=f"Pet Safety - {garage_name}",
                    data=user_input,
                )

        # Get available entities for the form dropdowns
        cover_entities = _get_cover_entities(self.hass)
        barrier_entities = _get_barrier_entities(self.hass)

        # Abort if no garage doors are available to monitor
        if not cover_entities:
            return self.async_abort(reason="no_garage_doors")

        # Define the form schema with validation and defaults
        data_schema = vol.Schema(
            {
                # Required: Garage door to monitor (dropdown of available covers)
                vol.Required(CONF_GARAGE_DOOR): vol.In(cover_entities),
                # Required: Barrier entities to secure (multi-select from available entities)
                vol.Required(CONF_BARRIER_ENTITIES): cv.multi_select(barrier_entities),
                # Optional: Whether to auto-close garage if barriers fail (checkbox)
                vol.Optional(
                    CONF_AUTO_CLOSE_GARAGE, default=DEFAULT_AUTO_CLOSE_GARAGE
                ): bool,
                # Optional: Whether to send notifications (checkbox)
                vol.Optional(
                    CONF_NOTIFICATION_ENABLED, default=DEFAULT_NOTIFICATION_ENABLED
                ): bool,
            }
        )

        # Show the configuration form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
