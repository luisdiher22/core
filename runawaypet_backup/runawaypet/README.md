# Runaway Pet Protection Integration

A comprehensive Home Assistant integration that automatically monitors garage doors and secures potential pet escape routes to prevent pets from running away.

## Overview

This integration provides automated pet safety by:

1. **Monitoring**: Watches a configured garage door for state changes
2. **Detection**: When garage opens, immediately checks all configured barrier entities
3. **Response**: Automatically attempts to close/secure any open barriers
4. **Fallback**: If barriers can't be secured, optionally closes the garage door
5. **Notification**: Alerts users when manual intervention is needed

## Architecture

### Integration Type: Helper
This is a "helper" integration that orchestrates existing Home Assistant entities rather than connecting to specific hardware. It works with any garage door and barrier entities you already have configured.

### Files Structure

```
homeassistant/components/runawaypet/
├── __init__.py              # Main coordinator and entry points
├── binary_sensor.py         # Pet safety status sensor
├── config_flow.py          # User configuration interface
├── const.py                # Constants and configuration keys
├── manifest.json           # Integration metadata
├── strings.json            # User interface text
├── quality_scale.yaml      # Quality scale compliance tracking
└── translations/
    └── en.json             # English translations
```

### Key Components

#### 1. RunawayPetCoordinator (`__init__.py`)
The brain of the system that:
- Listens for garage door state changes using Home Assistant's event system
- Evaluates barrier entities when garage opens
- Attempts to automatically secure barriers
- Manages fallback actions and notifications
- Maintains current safety state

#### 2. RunawayPetSafetyBinarySensor (`binary_sensor.py`)
A binary sensor that shows pet safety status:
- **OFF (safe)**: Garage closed OR all barriers secure
- **ON (unsafe)**: Pets at risk or barriers being secured
- Provides detailed status in entity attributes

#### 3. RunawayPetConfigFlow (`config_flow.py`)
User interface for setup:
- Select garage door to monitor
- Choose barrier entities to secure
- Configure automation behavior
- Validate entity existence

## Configuration

### Supported Barrier Types

The integration can work with various entity types as barriers:

- **Covers**: Doors, windows, pet doors, etc.
- **Switches**: Smart locks, automated gates
- **Input Booleans**: Manual barrier indicators
- **Binary Sensors**: Door/window sensors (monitoring only)

### Configuration Options

1. **Garage Door**: Cover entity representing the garage door to monitor
2. **Barrier Entities**: List of entities that should be secured when garage opens
3. **Auto Close Garage**: Whether to close garage door if barriers can't be secured
4. **Notifications**: Whether to send persistent notifications to users

## State Management

### Pet Safety States

1. **SECURE**: Pets are safe
   - Garage door is closed, OR
   - Garage door is open but all barriers are secure

2. **AT_RISK**: Pets could escape
   - Garage door is open AND one or more barriers are open

3. **SECURING**: Actively securing barriers
   - Currently attempting to close open barriers
   - Temporary state during barrier closing operations

### State Transitions

```
SECURE → AT_RISK    : Garage opens with barriers open
AT_RISK → SECURING  : Starting to close barriers
SECURING → SECURE   : All barriers successfully closed
SECURING → AT_RISK  : Some barriers failed to close
```

## How It Works

### Event-Driven Architecture
- Uses Home Assistant's state change events (not polling)
- Only activates when garage door state changes to "open"
- Efficient and responsive

### Barrier Closing Logic
1. Identify entity type (cover, switch, etc.)
2. Call appropriate service (close_cover, turn_off, etc.)
3. Wait for state to update (2 second delay)
4. Verify barrier actually closed
5. Mark as success or failure

### Escalation Path
If barriers can't be secured:
1. **Auto-close enabled**: Close garage door + send notification
2. **Auto-close disabled**: Send notification requesting manual action
3. **Garage close fails**: Send critical alert

### Notification System
Uses persistent notifications that:
- Appear in Home Assistant UI
- Remain until user dismisses them
- Provide clear action instructions
- Include specific entity names

## Error Handling

### Validation
- Ensures selected entities exist before setup
- Prevents duplicate configurations
- Validates entity accessibility

### Runtime Resilience
- Graceful handling of entity state changes
- Service call failure recovery
- Broad exception handling in background tasks
- Detailed logging for troubleshooting

### User Feedback
- Clear error messages in config flow
- Informative log messages
- Persistent notifications for critical issues

## Integration Standards

### Home Assistant Compliance
- Follows Home Assistant integration quality standards
- Uses modern entity naming patterns
- Implements proper config entry lifecycle
- Supports translation system
- Bronze quality scale compliance

### Code Quality
- Comprehensive documentation
- Type hints throughout
- Proper exception handling
- Async/await patterns
- Event loop safety

## Example Use Cases

### Basic Pet Door Protection
- Garage door: `cover.garage_door`
- Barriers: `cover.pet_door`
- Result: Pet door closes when garage opens

### Multi-Barrier Security
- Garage door: `cover.main_garage`
- Barriers: `cover.pet_door`, `switch.back_gate`, `cover.side_door`
- Result: All barriers secured when garage opens

### Smart Lock Integration
- Garage door: `cover.garage_door`
- Barriers: `switch.smart_deadbolt`, `input_boolean.manual_gate`
- Result: Door locks and gate indicator is set when garage opens

## Technical Details

### Dependencies
- `persistent_notification`: For user alerts
- Home Assistant core APIs for entity management

### Performance
- Event-driven
- Minimal resource usage
- Only active during garage door transitions

### Compatibility
- Works with any Home Assistant installation
- No external services required
- Compatible with all entity types

### Future Enhancements
- Multi-garage support
- Schedule-based activation
- Advanced notification options
- Integration with security systems

