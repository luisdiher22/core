"""The runaway pet protection integration.

This integration provides automated pet safety monitoring by watching garage doors
and securing potential escape routes when the garage opens. The integration:

1. Monitors a configured garage door for state changes
2. When the garage door opens, checks all configured barrier entities
3. Attempts to close/secure any open barriers automatically
4. If barriers can't be secured, optionally closes the garage door
5. Sends notifications when manual intervention is needed

The integration works with various entity types as barriers:
- Covers (doors, windows, pet doors)
- Switches (smart locks, automated gates)
- Input booleans (manual barriers)

This is a "helper" integration that orchestrates existing Home Assistant entities
rather than connecting to specific hardware devices.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OPEN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_AUTO_CLOSE_GARAGE,
    CONF_BARRIER_ENTITIES,
    CONF_GARAGE_DOOR,
    CONF_NOTIFICATION_ENABLED,
    DOMAIN,
    STATE_AT_RISK,
    STATE_SECURE,
    STATE_SECURING,
)

_LOGGER = logging.getLogger(__name__)

# List of platforms this integration provides
# Currently only provides a binary sensor for pet safety status
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

# Type alias for config entries that use our coordinator
# This allows type checking to know that entry.runtime_data is a RunawayPetCoordinator
type RunawayPetConfigEntry = ConfigEntry[RunawayPetCoordinator]


class RunawayPetCoordinator:
    """Coordinate pet safety monitoring and barrier management.

    This coordinator is the brain of the pet safety system. It:

    1. Listens for garage door state changes using Home Assistant's event system
    2. When the garage opens, evaluates all configured barrier entities
    3. Attempts to automatically secure any open barriers
    4. Manages fallback actions (closing garage) if barriers can't be secured
    5. Sends notifications to inform users of actions taken
    6. Maintains the current safety state for the binary sensor

    The coordinator uses event-driven logic to efficiently respond to changes
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator with configuration data.

        Args:
            hass: Home Assistant instance for accessing states and services
            entry: Config entry containing user configuration:
                - garage_door: Entity ID of garage door to monitor
                - barrier_entities: List of entity IDs that should be secured
                - auto_close_garage: Whether to close garage if barriers fail
                - notification_enabled: Whether to send notifications
        """
        self.hass = hass
        self.entry = entry

        # Store configuration from the config entry
        self._garage_door = entry.data[CONF_GARAGE_DOOR]
        self._barrier_entities = entry.data[CONF_BARRIER_ENTITIES]
        self._auto_close_garage = entry.data[CONF_AUTO_CLOSE_GARAGE]
        self._notification_enabled = entry.data[CONF_NOTIFICATION_ENABLED]

        # Current safety state (secure, at_risk, securing)
        self._current_state = STATE_SECURE

        # List to store event listeners for cleanup
        self._listeners: list = []

        # Callback for notifying entities when state changes
        self._state_changed_callback = None

    @property
    def garage_door(self) -> str:
        """Return the garage door entity ID being monitored."""
        return self._garage_door

    @property
    def barrier_entities(self) -> list[str]:
        """Return the list of barrier entity IDs that should be secured."""
        return self._barrier_entities

    @property
    def current_state(self) -> str:
        """Return the current pet safety state.

        States:
        - secure: Garage closed OR garage open with all barriers secured
        - at_risk: Garage open with one or more barriers open
        - securing: Currently attempting to close open barriers
        """
        return self._current_state

    def set_state_callback(self, callback) -> None:
        """Set callback to be called when coordinator state changes."""
        self._state_changed_callback = callback

    def _notify_state_change(self) -> None:
        """Notify subscribed entities that state has changed."""
        if self._state_changed_callback:
            self._state_changed_callback()

    async def async_setup(self) -> None:
        """Set up the coordinator and start monitoring.

        This method:
        1. Registers an event listener to monitor garage door state changes
        2. Performs an initial safety check in case garage is already open

        The event listener is stored so it can be cleaned up during unload.
        """
        # Register event listener for garage door state changes
        self._listeners.append(
            async_track_state_change_event(
                self.hass,
                self._garage_door,
                self._garage_door_changed,
            )
        )

        # Check initial state in case garage door is already open when integration starts
        await self._check_pet_safety()

    async def async_unload(self) -> None:
        """Clean up the coordinator when unloading.

        This removes all event listeners to prevent memory leaks and
        ensure the coordinator is properly disposed of.
        """
        # Remove all event listeners
        for listener in self._listeners:
            listener()  # Each listener returns a callable that removes itself
        self._listeners.clear()

    async def _garage_door_changed(self, event) -> None:
        """Handle garage door state change events.

        This is the main trigger for pet safety checks. It's called whenever
        the garage door state changes (opening, closing, etc.).

        Args:
            event: State change event containing old_state and new_state
        """
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        # Skip if we don't have valid state data
        if not new_state or not old_state:
            return

        # Only act when garage door transitions from any state TO open
        # This ensures we don't trigger on close->open transitions unnecessarily
        if old_state.state != STATE_OPEN and new_state.state == STATE_OPEN:
            _LOGGER.info("Garage door opened, checking pet safety")
            await self._check_pet_safety()

    async def _check_pet_safety(self) -> None:
        """Evaluate current pet safety status and take action if needed.

        This is the core safety logic that:
        1. Checks if garage door is currently open
        2. If closed, marks status as secure and exits
        3. If open, evaluates all barrier entities for open states
        4. If all barriers are secure, marks status as secure
        5. If any barriers are open, marks as at-risk and attempts to secure them

        This method is called both on initial setup and whenever the garage door opens.
        """
        garage_state = self.hass.states.get(self._garage_door)

        # If garage is closed or doesn't exist, pets are safe
        if not garage_state or garage_state.state != STATE_OPEN:
            self._current_state = STATE_SECURE
            self._notify_state_change()
            return

        # Garage is open - check all configured barrier entities
        open_barriers = []
        for entity_id in self._barrier_entities:
            state = self.hass.states.get(entity_id)
            if state and self._is_barrier_open(state):
                open_barriers.append(entity_id)

        # If no barriers are open, pets are safe even with garage open
        if not open_barriers:
            self._current_state = STATE_SECURE
            self._notify_state_change()
            return

        # Inform there is an issue if the garage is open AND barriers are open
        self._current_state = STATE_AT_RISK
        self._notify_state_change()
        _LOGGER.warning(
            "Pet escape risk detected - %d barriers open", len(open_barriers)
        )

        # Attempt to automatically secure the open barriers
        await self._secure_barriers(open_barriers)

    def _is_barrier_open(self, state: State) -> bool:
        """Determine if a barrier entity is in an 'open' or 'unsafe' state.

        This method interprets different entity types and their states to determine
        if they represent an open barrier that pets could escape through:

        - Covers (doors, windows, pet doors): 'open' state = unsafe
        - Switches (smart locks, gates): 'on' state = unlocked/open = unsafe
        - Input booleans (manual barriers): 'on' state = barrier down/open = unsafe
        - Binary sensors (door sensors): 'on' state = door detected open = unsafe

        Args:
            state: Home Assistant entity state object

        Returns:
            True if barrier is open/unsafe, False if closed/secure
        """
        # For covers: open state means open barrier (unsafe)
        if state.domain == "cover":
            return state.state == STATE_OPEN

        # For switches/input_booleans: on state means open/unlocked (unsafe)
        if state.domain in ["switch", "input_boolean"]:
            return state.state == "on"

        # For binary_sensors: on state usually means open/detected (unsafe)
        if state.domain == "binary_sensor":
            return state.state == "on"

        # Unknown entity type - assume safe
        return False

    async def _secure_barriers(self, open_barriers: list[str]) -> None:
        """Attempt to secure all open barriers automatically.

        This method:
        1. Sets status to 'securing' to indicate work in progress
        2. Attempts to close/secure each open barrier
        3. Tracks successes and failures
        4. Updates status based on results (secure if all worked, at-risk if failures)
        5. Handles failures with fallback actions (garage close, notifications)

        Args:
            open_barriers: List of entity IDs that are currently open/unsafe
        """
        self._current_state = STATE_SECURING
        self._notify_state_change()

        secured_count = 0
        failed_barriers = []

        # Attempt to secure each barrier individually
        for entity_id in open_barriers:
            try:
                if await self._close_barrier(entity_id):
                    secured_count += 1
                    _LOGGER.debug("Successfully secured barrier %s", entity_id)
                else:
                    failed_barriers.append(entity_id)
                    _LOGGER.warning("Failed to secure barrier %s", entity_id)
            except Exception:  # Broad exception allowed in background task
                _LOGGER.exception("Failed to secure barrier %s", entity_id)
                failed_barriers.append(entity_id)

        # Update status based on results
        if not failed_barriers:
            self._current_state = STATE_SECURE
            self._notify_state_change()
            _LOGGER.info("All %d barriers secured successfully", secured_count)
        else:
            # Some barriers couldn't be secured - escalate response
            _LOGGER.error("Failed to secure %d barriers", len(failed_barriers))
            await self._handle_security_failure(failed_barriers)

    async def _close_barrier(self, entity_id: str) -> bool:
        """Attempt to close/secure a specific barrier entity.

        This method determines the appropriate service call based on entity type:
        - Covers: Use cover.close_cover service
        - Switches/Input Booleans: Use turn_off service to "secure" them

        After calling the service, it waits briefly and verifies the barrier
        actually changed state to ensure the action was successful.

        Args:
            entity_id: The entity ID of the barrier to close

        Returns:
            True if barrier was successfully closed, False otherwise
        """
        state = self.hass.states.get(entity_id)
        if not state:
            _LOGGER.error("Barrier entity %s not found", entity_id)
            return False

        domain = state.domain
        service_data = {"entity_id": entity_id}

        try:
            # Call appropriate service based on entity type
            if domain == "cover":
                await self.hass.services.async_call(
                    "cover", "close_cover", service_data
                )
            elif domain in ["switch", "input_boolean"]:
                await self.hass.services.async_call(domain, "turn_off", service_data)
            else:
                _LOGGER.warning(
                    "Don't know how to close %s entity %s", domain, entity_id
                )
                return False

        except Exception:  # Broad exception allowed in background task
            _LOGGER.exception("Service call failed for %s", entity_id)
            return False
        else:
            # Wait a moment for the entity to update its state
            await asyncio.sleep(2)

            # Verify the barrier actually closed
            new_state = self.hass.states.get(entity_id)
            success = new_state and not self._is_barrier_open(new_state)

            if success:
                _LOGGER.debug("Successfully closed barrier %s", entity_id)
            else:
                _LOGGER.warning("Barrier %s did not close as expected", entity_id)

            return success

    async def _handle_security_failure(self, failed_barriers: list[str]) -> None:
        """Handle security failure when barriers cannot be secured.

        This is the escalation path when automatic barrier closing fails.
        The response depends on user configuration:

        1. If auto_close_garage is enabled:
           - Attempt to close the garage door as last resort
           - Send notification explaining what happened
           - If garage close also fails, send critical alert

        2. If auto_close_garage is disabled:
           - Send notification asking user to manually close barriers

        Args:
            failed_barriers: List of entity IDs that couldn't be secured
        """
        self._current_state = STATE_AT_RISK

        if self._auto_close_garage:
            # Last resort: close the garage door to prevent pet escape
            try:
                await self.hass.services.async_call(
                    "cover", "close_cover", {"entity_id": self._garage_door}
                )
                _LOGGER.info("Closed garage door due to unsecured barriers")

                if self._notification_enabled:
                    await self._send_notification(
                        "Pet safety: Garage closed",
                        f"Closed garage door because {len(failed_barriers)} barriers couldn't be secured. "
                        f"Please check: {', '.join(failed_barriers)}",
                    )
            except Exception:  # Broad exception allowed in background task
                _LOGGER.exception("Failed to close garage door")
                if self._notification_enabled:
                    await self._send_notification(
                        "Pet safety: Critical alert",
                        f"Unable to secure {len(failed_barriers)} barriers and couldn't close garage door. "
                        f"Please check immediately: {', '.join(failed_barriers)}",
                    )
        elif self._notification_enabled:
            # User disabled auto-close, so ask them to manually intervene
            await self._send_notification(
                "Pet safety: Manual action needed",
                f"Garage door is open but {len(failed_barriers)} barriers couldn't be secured. "
                f"Please close manually: {', '.join(failed_barriers)}",
            )

    async def _send_notification(self, title: str, message: str) -> None:
        """Send a persistent notification to the user.

        Creates a persistent notification that will appear in the Home Assistant
        UI and remain until the user dismisses it. Each notification has a unique
        ID based on the integration domain and config entry ID.

        Args:
            title: Short title for the notification
            message: Detailed message explaining the situation and any required actions
        """
        persistent_notification.create(
            self.hass,
            message,
            title,
            f"{DOMAIN}_{self.entry.entry_id}",
        )


async def async_setup_entry(hass: HomeAssistant, entry: RunawayPetConfigEntry) -> bool:
    """Set up runaway pet protection from a config entry.

    This is the main entry point called by Home Assistant when the integration
    is being loaded. It:

    1. Creates the coordinator that manages all pet safety logic
    2. Stores the coordinator in the config entry's runtime_data for platform access
    3. Initializes the coordinator (starts monitoring garage door)
    4. Sets up all platforms (currently just the binary sensor)

    Args:
        hass: Home Assistant instance
        entry: Config entry containing user configuration

    Returns:
        True if setup was successful, False otherwise
    """
    # Create the coordinator that will manage all pet safety logic
    coordinator = RunawayPetCoordinator(hass, entry)

    # Store coordinator in runtime_data so platforms can access it
    entry.runtime_data = coordinator

    # Initialize the coordinator (starts event monitoring)
    await coordinator.async_setup()

    # Set up all platforms (binary sensor, etc.)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RunawayPetConfigEntry) -> bool:
    """Unload a config entry and clean up resources.

    This is called when the integration is being removed or reloaded.
    It ensures proper cleanup of all resources to prevent memory leaks.

    Args:
        hass: Home Assistant instance
        entry: Config entry being unloaded

    Returns:
        True if unload was successful, False otherwise
    """
    # First unload all platform entities
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # If platform unload succeeded, clean up the coordinator
        await entry.runtime_data.async_unload()

    return unload_ok
