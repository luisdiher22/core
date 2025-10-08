# 🧪 Runawaypet Integration Testing Scenarios

## Scenario 1: Basic Pet Safety Alert
**Expected Behavior**: When garage opens and barriers are not secured, pet should be "at risk"

### Steps:
1. Go to Developer Tools > Services
2. Call service: `input_boolean.turn_on`
   - Entity ID: `input_boolean.test_garage_door`
3. Check States page for: `binary_sensor.runaway_pet_safety_status`
   - **Expected**: Should be `on` (pet at risk)
4. Check for persistent notification about pet safety

## Scenario 2: Pet Secured Successfully
**Expected Behavior**: When barriers are activated, pet should be "secure"

### Steps:
1. With garage still open, call service: `input_boolean.turn_on`
   - Entity ID: `input_boolean.test_pet_gate`
2. Check States page for: `binary_sensor.runaway_pet_safety_status`
   - **Expected**: Should be `off` (pet secure)
3. Check for notification about barriers secured

## Scenario 3: Garage Closed
**Expected Behavior**: When garage closes, monitoring should deactivate

### Steps:
1. Call service: `input_boolean.turn_off`
   - Entity ID: `input_boolean.test_garage_door`
2. Check States page for: `binary_sensor.runaway_pet_safety_status`
   - **Expected**: Should be `off` (not monitoring)

## Scenario 4: Multiple Barriers
**Expected Behavior**: Test with multiple barrier entities

### Steps:
1. Reconfigure integration to use both barriers:
   - `input_boolean.test_pet_gate`
   - `input_boolean.test_pet_door`
2. Open garage, ensure both barriers need to be active for "secure" status

## Quick Test Commands:
```bash
# Open garage door
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "input_boolean.test_garage_door"}' \
  http://localhost:8123/api/services/input_boolean/turn_on

# Secure pet gate
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "input_boolean.test_pet_gate"}' \
  http://localhost:8123/api/services/input_boolean/turn_on

# Check pet safety status
curl -X GET -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/states/binary_sensor.runaway_pet_safety_status
```

## Expected Integration Behavior:
- ✅ Creates `binary_sensor.runaway_pet_safety_status` entity
- ✅ Shows "Pet at Risk" when garage open + barriers not secured
- ✅ Shows "Pet Secure" when garage open + barriers secured
- ✅ Shows "Not Monitoring" when garage closed
- ✅ Sends persistent notifications for status changes
- ✅ Integrates properly with Home Assistant UI
