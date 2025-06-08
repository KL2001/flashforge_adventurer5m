import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import FlashforgeDataUpdateCoordinator
from homeassistant.core import ServiceCall # For type hinting

_LOGGER = logging.getLogger(__name__)

# Service Attributes
ATTR_FILE_PATH = "file_path"
ATTR_PERCENTAGE = "percentage" # Added

# Services
SERVICE_DELETE_FILE = "delete_file"
SERVICE_DISABLE_STEPPERS = "disable_steppers"
SERVICE_ENABLE_STEPPERS = "enable_steppers"  # Added
SERVICE_SET_SPEED_PERCENTAGE = "set_speed_percentage" # Added


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the Flashforge Adventurer 5M PRO integration.
    """
    # If you don't support YAML configuration, do nothing here.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up the Flashforge Adventurer 5M PRO integration from a config entry.
    """
    host = entry.data["host"]
    serial_number = entry.data["serial_number"]
    check_code = entry.data["check_code"]
    scan_interval = entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    coordinator = FlashforgeDataUpdateCoordinator(
        hass,
        host=host,
        serial_number=serial_number,
        check_code=check_code,
        scan_interval=scan_interval,
    )

    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to sensor and camera platforms using the updated method
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "camera", "binary_sensor"]
    )

    # Register services
    async def handle_pause_print(call):
        """Handle the service call to pause the print."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.pause_print()

    async def handle_start_print(call):
        """Handle the service call to start a print."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        file_path = call.data.get("file_path")  # Schema ensures it's a string
        if (
            file_path is not None
        ):  # Good practice to check if required field is actually there
            await coordinator.start_print(file_path)

    async def handle_cancel_print(call):
        """Handle the service call to cancel the print."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.cancel_print()

    async def handle_toggle_light(call):
        """Handle the service call to toggle the printer's light."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        state = call.data["state"]
        await coordinator.toggle_light(state)

    async def handle_resume_print(call):
        """Handle the service call to resume the print."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.resume_print()

    async def handle_set_extruder_temperature(call):
        """Handle the service call to set the extruder temperature."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        temperature = call.data.get("temperature")  # Schema ensures it's a positive_int
        if temperature is not None:
            await coordinator.set_extruder_temperature(temperature)

    async def handle_set_bed_temperature(call):
        """Handle the service call to set the bed temperature."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        temperature = call.data.get("temperature")  # Schema ensures it's a positive_int
        if temperature is not None:
            await coordinator.set_bed_temperature(temperature)

    async def handle_set_fan_speed(call):
        """Handle the service call to set the fan speed."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        speed = call.data.get("speed")  # Schema ensures it's an int in range
        if speed is not None:
            await coordinator.set_fan_speed(speed)

    async def handle_turn_fan_off(call):
        """Handle the service call to turn the fan off."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.turn_fan_off()

    async def handle_move_axis(call):
        """Handle the service call to move printer axes."""
        coordinator = hass.data[DOMAIN][entry.entry_id]
        x = call.data.get("x")
        y = call.data.get("y")
        z = call.data.get("z")  # Schema ensures float or None
        feedrate = call.data.get("feedrate")  # Schema ensures int or None

        # No explicit conversion needed due to vol.Coerce in schema
        await coordinator.move_axis(x=x, y=y, z=z, feedrate=feedrate)

    async def handle_delete_file(call: ServiceCall) -> None:
        """Handle the delete_file service call."""
        # Simplified: using the first available coordinator.
        # Assumes only one printer is configured.
        # A more robust solution for multiple printers would involve targeting via device_id.
        if not hass.data.get(DOMAIN) or not list(hass.data[DOMAIN].keys()):
            _LOGGER.error("Service 'delete_file' called, but no coordinators found.")
            return

        entry_id = list(hass.data[DOMAIN].keys())[0]
        coordinator: FlashforgeDataUpdateCoordinator = hass.data[DOMAIN][entry_id]

        file_path = call.data.get(ATTR_FILE_PATH)
        if not file_path: # Should be caught by schema, but good to double check
            _LOGGER.error("Service 'delete_file' called without a file_path.")
            return

        _LOGGER.info(f"Service 'delete_file' called for file: {file_path}")
        await coordinator.delete_file(file_path)

    async def handle_disable_steppers(call: ServiceCall) -> None:
        """Handle the disable_steppers service call."""
        if not hass.data.get(DOMAIN) or not list(hass.data[DOMAIN].keys()):
            _LOGGER.error(f"Service '{SERVICE_DISABLE_STEPPERS}' called, but integration not ready or no coordinators found.")
            return
        entry_id = list(hass.data[DOMAIN].keys())[0]
        coordinator: FlashforgeDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
        _LOGGER.info(f"Service '{SERVICE_DISABLE_STEPPERS}' called.")
        await coordinator.disable_steppers()

    async def handle_enable_steppers(call: ServiceCall) -> None:
        """Handle the enable_steppers service call."""
        if not hass.data.get(DOMAIN) or not list(hass.data[DOMAIN].keys()):
            _LOGGER.error(f"Service '{SERVICE_ENABLE_STEPPERS}' called, but integration not ready or no coordinators found.")
            return
        entry_id = list(hass.data[DOMAIN].keys())[0]
        coordinator: FlashforgeDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
        _LOGGER.info(f"Service '{SERVICE_ENABLE_STEPPERS}' called.")
        await coordinator.enable_steppers()

    async def handle_set_speed_percentage(call: ServiceCall) -> None:
        """Handle the set_speed_percentage service call."""
        if not hass.data.get(DOMAIN) or not list(hass.data[DOMAIN].keys()):
            _LOGGER.error(f"Service '{SERVICE_SET_SPEED_PERCENTAGE}' called, but integration not ready or no coordinators found.")
            return
        entry_id = list(hass.data[DOMAIN].keys())[0]
        coordinator: FlashforgeDataUpdateCoordinator = hass.data[DOMAIN][entry_id]

        percentage = call.data.get(ATTR_PERCENTAGE)
        if percentage is None: # Schema ensures it's an int if present
            _LOGGER.error(f"Service '{SERVICE_SET_SPEED_PERCENTAGE}' called without percentage.")
            return

        _LOGGER.info(f"Service '{SERVICE_SET_SPEED_PERCENTAGE}' called with percentage: {percentage}%")
        await coordinator.set_speed_percentage(percentage)

    hass.services.async_register(DOMAIN, "pause_print", handle_pause_print)
    hass.services.async_register(
        DOMAIN,
        "start_print",
        handle_start_print,
        schema=vol.Schema(
            {
                vol.Required(ATTR_FILE_PATH): cv.string, # Use ATTR_FILE_PATH
            }
        ),
    )
    hass.services.async_register(DOMAIN, "cancel_print", handle_cancel_print)
    hass.services.async_register(
        DOMAIN,
        "toggle_light",
        handle_toggle_light,
        schema=vol.Schema(
            {
                vol.Required("state"): cv.boolean,
            }
        ),
    )
    hass.services.async_register(DOMAIN, "resume_print", handle_resume_print)
    hass.services.async_register(
        DOMAIN,
        "set_extruder_temperature",
        handle_set_extruder_temperature,
        schema=vol.Schema({vol.Required("temperature"): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN,
        "set_bed_temperature",
        handle_set_bed_temperature,
        schema=vol.Schema({vol.Required("temperature"): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN,
        "set_fan_speed",
        handle_set_fan_speed,
        schema=vol.Schema(
            {vol.Required("speed"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))}
        ),
    )
    hass.services.async_register(DOMAIN, "turn_fan_off", handle_turn_fan_off)
    hass.services.async_register(
        DOMAIN,
        "move_axis",
        handle_move_axis,
        schema=vol.Schema(
            {
                vol.Optional("x"): vol.Coerce(float),
                vol.Optional("y"): vol.Coerce(float),
                vol.Optional("z"): vol.Coerce(float),
                vol.Optional("feedrate"): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_FILE,
        handle_delete_file,
        schema=vol.Schema(
            {
                vol.Required(ATTR_FILE_PATH): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE_STEPPERS, handle_disable_steppers
    ) # No schema needed as there are no fields
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE_STEPPERS, handle_enable_steppers
    ) # No schema needed
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SPEED_PERCENTAGE,
        handle_set_speed_percentage,
        schema=vol.Schema({
            vol.Required(ATTR_PERCENTAGE): vol.All(vol.Coerce(int), vol.Range(min=10, max=500))
        })
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Handle removal/unloading of a config entry.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "camera", "binary_sensor"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
