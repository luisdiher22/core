"""Binary sensor platform for runaway pet protection.

This module provides a binary sensor that shows the current pet safety status.
The sensor indicates whether pets are currently at risk of escaping through
an open garage door with unsecured barriers.

The binary sensor:
- Shows "unsafe" (on) when pets are at risk or barriers are being secured
- Shows "safe" (off) when all barriers are secure or garage is closed
- Provides detailed status information in entity attributes
- Uses the Safety device class for proper Home Assistant integration
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RunawayPetConfigEntry
from .const import STATE_AT_RISK, STATE_SECURING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RunawayPetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up runaway pet protection binary sensor.

    Creates a single binary sensor entity that displays the current
    pet safety status based on the coordinator's state.

    Args:
        hass: Home Assistant instance
        entry: Config entry containing the coordinator
        async_add_entities: Callback to add entities to Home Assistant
    """
    # Get the coordinator from the config entry's runtime data
    coordinator = entry.runtime_data

    # Create and add the pet safety status binary sensor
    async_add_entities([RunawayPetSafetyBinarySensor(coordinator, entry)])


class RunawayPetSafetyBinarySensor(BinarySensorEntity):
    """Binary sensor representing pet safety status.

    This sensor indicates whether pets are currently at risk of escaping.

    Binary sensor states:
    - OFF (safe): Garage closed OR garage open with all barriers secure
    - ON (unsafe): Garage open with barriers at risk OR actively securing barriers

    The sensor provides additional context through state attributes including:
    - Current detailed status (secure/at_risk/securing)
    - Which garage door is being monitored
    - Number of barriers being monitored
    - List of all barrier entity IDs
    """

    # Use modern entity naming pattern
    _attr_has_entity_name = True
    # Translation key for entity name (defined in strings.json)
    _attr_translation_key = "pet_safety_status"
    # Device class helps Home Assistant categorize and display the sensor appropriately
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator, entry: RunawayPetConfigEntry) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: The RunawayPetCoordinator managing pet safety logic
            entry: Config entry for generating unique IDs and getting configuration
        """
        self._coordinator = coordinator

        # Create a unique ID for this sensor based on the config entry
        self._attr_unique_id = f"{entry.entry_id}_pet_safety_status"

        # Create a user-friendly name based on the garage door being monitored
        garage_door_state = coordinator.hass.states.get(coordinator.garage_door)
        if garage_door_state:
            garage_name = garage_door_state.attributes.get("friendly_name", "Garage")
            self._attr_name = f"{garage_name} pet safety"
        else:
            self._attr_name = "Pet safety"

    @property
    def is_on(self) -> bool:
        """Return True if pets are at risk (unsafe).

        The binary sensor follows this logic:
        - ON (True): Pets are at risk - garage is open and barriers are unsecured,
          or we're actively trying to secure barriers
        - OFF (False): Pets are safe - garage is closed or all barriers are secure

        Returns:
            True when coordinator state is at_risk or securing, False otherwise
        """
        # Binary sensor is "on" when pets are at risk or being secured
        return self._coordinator.current_state in [STATE_AT_RISK, STATE_SECURING]

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        This sensor is always available since it reflects the coordinator's
        internal state rather than depending on external devices.

        Returns:
            Always True - sensor is always available
        """
        return True

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return additional state attributes for detailed information.

        Provides context beyond the simple on/off state including:
        - Detailed status (secure/at_risk/securing)
        - Which garage door is being monitored
        - Count and list of barrier entities being monitored

        Returns:
            Dictionary of attribute names to values
        """
        return {
            "status": self._coordinator.current_state,
            "garage_door": self._coordinator.garage_door,
            "monitored_barriers": len(self._coordinator.barrier_entities),
            "barrier_entities": self._coordinator.barrier_entities,
        }

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        # Register callback to get notified when coordinator state changes
        self._coordinator.set_state_callback(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Update the sensor state.

        This method is called by Home Assistant when it needs to refresh
        the entity state. Since our state comes from the coordinator,
        we just trigger a state write to update the UI.
        """
        # State comes from coordinator, just refresh the UI
        self.async_write_ha_state()
