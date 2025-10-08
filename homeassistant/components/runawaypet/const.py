"""Constants for the runaway pet protection integration.

This module defines all constants used throughout the integration including:
- Configuration keys for storing user preferences
- Default values for configuration options
- State constants for the pet safety status
- Integration domain identifier
"""

# Integration domain identifier - must match the folder name
DOMAIN = "runawaypet"

# Configuration keys - used to store and retrieve user settings
CONF_GARAGE_DOOR = "garage_door"  # Entity ID of garage door to monitor
CONF_BARRIER_ENTITIES = "barrier_entities"  # List of barrier entity IDs to secure
CONF_AUTO_CLOSE_GARAGE = "auto_close_garage"  # Whether to close garage if barriers fail
CONF_NOTIFICATION_ENABLED = "notification_enabled"  # Whether to send notifications

# Default configuration values - used in config flow and initial setup
DEFAULT_AUTO_CLOSE_GARAGE = (
    True  # By default, close garage if barriers can't be secured
)
DEFAULT_NOTIFICATION_ENABLED = True  # By default, send notifications to user

# Pet safety states - used by coordinator and binary sensor
STATE_SECURE = "secure"  # Pets are safe (garage closed or all barriers secure)
STATE_AT_RISK = "at_risk"  # Pets at risk (garage open with unsecured barriers)
STATE_SECURING = "securing"  # Currently attempting to secure open barriers
