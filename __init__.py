import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_PRINTING_SCAN_INTERVAL,
    DEFAULT_PRINTING_SCAN_INTERVAL
)
from .coordinator import FlashforgeDataUpdateCoordinator
from homeassistant.core import ServiceCall

_LOGGER = logging.getLogger(__name__)

ATTR_FILE_PATH = "file_path"
ATTR_PERCENTAGE = "percentage"
ATTR_HOME_X = "x"
ATTR_HOME_Y = "y"
ATTR_HOME_Z = "z"

SERVICE_PAUSE_PRINT = "pause_print"
SERVICE_START_PRINT = "start_print"
SERVICE_CANCEL_PRINT = "cancel_print"
SERVICE_TOGGLE_LIGHT = "toggle_light"
SERVICE_RESUME_PRINT = "resume_print"
SERVICE_SET_EXTRUDER_TEMPERATURE = "set_extruder_temperature"
SERVICE_SET_BED_TEMPERATURE = "set_bed_temperature"
SERVICE_SET_FAN_SPEED = "set_fan_speed"
SERVICE_TURN_FAN_OFF = "turn_fan_off"
SERVICE_MOVE_AXIS = "move_axis"
SERVICE_DELETE_FILE = "delete_file"
SERVICE_DISABLE_STEPPERS = "disable_steppers"
SERVICE_ENABLE_STEPPERS = "enable_steppers"
SERVICE_SET_SPEED_PERCENTAGE = "set_speed_percentage"
SERVICE_SET_FLOW_PERCENTAGE = "set_flow_percentage"
SERVICE_HOME_AXES = "home_axes"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_LIST_FILES = "list_files"
SERVICE_REPORT_FIRMWARE_CAPABILITIES = "report_firmware_capabilities"
SERVICE_PLAY_BEEP = "play_beep"
SERVICE_START_BED_LEVELING = "start_bed_leveling"
SERVICE_SAVE_SETTINGS_TO_EEPROM = "save_settings_to_eeprom"
SERVICE_READ_SETTINGS_FROM_EEPROM = "read_settings_from_eeprom"
SERVICE_FILAMENT_CHANGE = "filament_change"
SERVICE_RESTORE_FACTORY_SETTINGS = "restore_factory_settings"
SERVICE_MOVE_RELATIVE = "move_relative"
SERVICE_SEND_GCODE = "send_gcode"

PLATFORMS = ["sensor", "camera", "binary_sensor", "number", "select", "button"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Flashforge Adventurer 5M PRO integration."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Flashforge Adventurer 5M PRO integration from a config entry."""
    host = entry.data["host"]
    serial_number = entry.data["serial_number"]
    check_code = entry.data["check_code"]

    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )
    printing_scan_interval = entry.options.get(
        CONF_PRINTING_SCAN_INTERVAL,
        entry.data.get(CONF_PRINTING_SCAN_INTERVAL, DEFAULT_PRINTING_SCAN_INTERVAL)
    )

    coordinator = FlashforgeDataUpdateCoordinator(
        hass,
        host=host,
        serial_number=serial_number,
        check_code=check_code,
        regular_scan_interval=scan_interval,
        printing_scan_interval=printing_scan_interval
    )

    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not entry.update_listeners:
        entry.add_update_listener(async_reload_entry)

    async def handle_pause_print(call: ServiceCall) -> None:
        await coordinator.pause_print()

    async def handle_start_print(call: ServiceCall) -> None:
        file_path = call.data.get(ATTR_FILE_PATH)
        if file_path is not None:
            await coordinator.start_print(file_path)

    async def handle_cancel_print(call: ServiceCall) -> None:
        await coordinator.cancel_print()

    async def handle_toggle_light(call: ServiceCall) -> None:
        state = call.data["state"] # Assuming 'state' is the correct key from services.yaml
        await coordinator.toggle_light(state)

    async def handle_resume_print(call: ServiceCall) -> None:
        await coordinator.resume_print()

    async def handle_set_extruder_temperature(call: ServiceCall) -> None:
        temperature = call.data.get("temperature")
        if temperature is not None:
            await coordinator.set_extruder_temperature(temperature)

    async def handle_set_bed_temperature(call: ServiceCall) -> None:
        temperature = call.data.get("temperature")
        if temperature is not None:
            await coordinator.set_bed_temperature(temperature)

    async def handle_set_fan_speed(call: ServiceCall) -> None:
        speed = call.data.get("speed")
        if speed is not None:
            await coordinator.set_fan_speed(speed)

    async def handle_turn_fan_off(call: ServiceCall) -> None:
        await coordinator.turn_fan_off()

    async def handle_move_axis(call: ServiceCall) -> None:
        x = call.data.get("x")
        y = call.data.get("y")
        z = call.data.get("z")
        feedrate = call.data.get("feedrate")
        await coordinator.move_axis(x=x, y=y, z=z, feedrate=feedrate)

    async def handle_delete_file(call: ServiceCall) -> None:
        file_path = call.data.get(ATTR_FILE_PATH)
        if not file_path:
            _LOGGER.error("Service 'delete_file' called without a file_path.")
            return
        await coordinator.delete_file(file_path)

    async def handle_disable_steppers(call: ServiceCall) -> None:
        await coordinator.disable_steppers()

    async def handle_enable_steppers(call: ServiceCall) -> None:
        await coordinator.enable_steppers()

    async def handle_set_speed_percentage(call: ServiceCall) -> None:
        percentage = call.data.get(ATTR_PERCENTAGE)
        if percentage is None:
            _LOGGER.error(f"Service '{SERVICE_SET_SPEED_PERCENTAGE}' called without percentage.")
            return
        await coordinator.set_speed_percentage(percentage)

    async def handle_set_flow_percentage(call: ServiceCall) -> None:
        percentage = call.data.get(ATTR_PERCENTAGE)
        if percentage is None:
            _LOGGER.error(f"Service '{SERVICE_SET_FLOW_PERCENTAGE}' called without percentage.")
            return
        await coordinator.set_flow_percentage(percentage)

    async def handle_home_axes(call: ServiceCall) -> None:
        axes_to_home = []
        if call.data.get(ATTR_HOME_X): axes_to_home.append("X")
        if call.data.get(ATTR_HOME_Y): axes_to_home.append("Y")
        if call.data.get(ATTR_HOME_Z): axes_to_home.append("Z")
        await coordinator.home_axes(axes_to_home if axes_to_home else None)

    async def handle_filament_change(call: ServiceCall) -> None:
        await coordinator.filament_change()

    async def handle_emergency_stop(call: ServiceCall) -> None:
        await coordinator.emergency_stop()

    async def handle_save_settings_to_eeprom(call: ServiceCall) -> None:
        await coordinator.save_settings_to_eeprom()

    async def handle_restore_factory_settings(call: ServiceCall) -> None:
        await coordinator.restore_factory_settings()

    async def handle_list_files(call: ServiceCall) -> None:
        await coordinator.list_files()

    async def handle_report_firmware_capabilities(call: ServiceCall) -> None:
        await coordinator.report_firmware_capabilities()

    SERVICE_PLAY_BEEP_SCHEMA = vol.Schema(
        {
            vol.Required("pitch"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
        }
    )
    async def handle_play_beep(call: ServiceCall) -> None:
        pitch = call.data["pitch"]
        duration = call.data["duration"]
        await coordinator.play_beep(pitch, duration)

    async def handle_start_bed_leveling(call: ServiceCall) -> None:
        await coordinator.start_bed_leveling()

    async def handle_read_settings_from_eeprom(call: ServiceCall) -> None:
        await coordinator.read_settings_from_eeprom()

    SERVICE_MOVE_RELATIVE_SCHEMA = vol.Schema(
        {
            vol.Optional("x"): vol.Coerce(float),
            vol.Optional("y"): vol.Coerce(float),
            vol.Optional("z"): vol.Coerce(float),
            vol.Optional("feedrate"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
    )
    async def handle_move_relative(call: ServiceCall) -> None:
        x = call.data.get("x")
        y = call.data.get("y")
        z = call.data.get("z")
        feedrate = call.data.get("feedrate")
        await coordinator.move_relative(x=x, y=y, z=z, feedrate=feedrate)

    SEND_GCODE_SCHEMA = vol.Schema(
        {
            vol.Required("gcode_command"): cv.string,
        }
    )
    async def handle_send_gcode(call: ServiceCall) -> None:
        gcode_command = call.data.get("gcode_command")
        if gcode_command is not None:
            await coordinator.async_send_gcode(gcode_command)
        else:
            _LOGGER.error(f"Service '{SERVICE_SEND_GCODE}' called without 'gcode_command'.")

    hass.services.async_register(DOMAIN, SERVICE_PAUSE_PRINT, handle_pause_print)
    hass.services.async_register(
        DOMAIN, SERVICE_START_PRINT, handle_start_print,
        schema=vol.Schema({vol.Required(ATTR_FILE_PATH): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_PRINT, handle_cancel_print)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE_LIGHT, handle_toggle_light,
        schema=vol.Schema({vol.Required("state"): cv.boolean}),
    )
    hass.services.async_register(DOMAIN, SERVICE_RESUME_PRINT, handle_resume_print)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_EXTRUDER_TEMPERATURE, handle_set_extruder_temperature,
        schema=vol.Schema({vol.Required("temperature"): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_BED_TEMPERATURE, handle_set_bed_temperature,
        schema=vol.Schema({vol.Required("temperature"): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FAN_SPEED, handle_set_fan_speed,
        schema=vol.Schema({vol.Required("speed"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))}),
    )
    hass.services.async_register(DOMAIN, SERVICE_TURN_FAN_OFF, handle_turn_fan_off)
    hass.services.async_register(
        DOMAIN, SERVICE_MOVE_AXIS, handle_move_axis,
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
        DOMAIN, SERVICE_DELETE_FILE, handle_delete_file,
        schema=vol.Schema({vol.Required(ATTR_FILE_PATH): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_DISABLE_STEPPERS, handle_disable_steppers)
    hass.services.async_register(DOMAIN, SERVICE_ENABLE_STEPPERS, handle_enable_steppers)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SPEED_PERCENTAGE, handle_set_speed_percentage,
        schema=vol.Schema({vol.Required(ATTR_PERCENTAGE): vol.All(vol.Coerce(int), vol.Range(min=10, max=500))}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_FLOW_PERCENTAGE, handle_set_flow_percentage,
        schema=vol.Schema({vol.Required(ATTR_PERCENTAGE): vol.All(vol.Coerce(int), vol.Range(min=50, max=200))}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_HOME_AXES, handle_home_axes,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_HOME_X, default=False): cv.boolean,
                vol.Optional(ATTR_HOME_Y, default=False): cv.boolean,
                vol.Optional(ATTR_HOME_Z, default=False): cv.boolean,
            }
        ),
    )
    hass.services.async_register(DOMAIN, SERVICE_FILAMENT_CHANGE, handle_filament_change)
    hass.services.async_register(DOMAIN, SERVICE_EMERGENCY_STOP, handle_emergency_stop)
    hass.services.async_register(DOMAIN, SERVICE_SAVE_SETTINGS_TO_EEPROM, handle_save_settings_to_eeprom)
    hass.services.async_register(DOMAIN, SERVICE_RESTORE_FACTORY_SETTINGS, handle_restore_factory_settings)
    hass.services.async_register(DOMAIN, SERVICE_LIST_FILES, handle_list_files)
    hass.services.async_register(DOMAIN, SERVICE_REPORT_FIRMWARE_CAPABILITIES, handle_report_firmware_capabilities)
    hass.services.async_register(DOMAIN, SERVICE_PLAY_BEEP, handle_play_beep, schema=SERVICE_PLAY_BEEP_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_START_BED_LEVELING, handle_start_bed_leveling)
    hass.services.async_register(DOMAIN, SERVICE_READ_SETTINGS_FROM_EEPROM, handle_read_settings_from_eeprom)
    hass.services.async_register(DOMAIN, SERVICE_MOVE_RELATIVE, handle_move_relative, schema=SERVICE_MOVE_RELATIVE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SEND_GCODE, handle_send_gcode, schema=SEND_GCODE_SCHEMA)

    return True

async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal/unloading of a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            _LOGGER.info("Last entry for domain %s unloaded; unregistering services.", DOMAIN)
            all_service_names = [
                SERVICE_PAUSE_PRINT, SERVICE_START_PRINT, SERVICE_CANCEL_PRINT,
                SERVICE_TOGGLE_LIGHT, SERVICE_RESUME_PRINT,
                SERVICE_SET_EXTRUDER_TEMPERATURE, SERVICE_SET_BED_TEMPERATURE,
                SERVICE_SET_FAN_SPEED, SERVICE_TURN_FAN_OFF, SERVICE_MOVE_AXIS,
                SERVICE_DELETE_FILE, SERVICE_DISABLE_STEPPERS, SERVICE_ENABLE_STEPPERS,
                SERVICE_SET_SPEED_PERCENTAGE, SERVICE_SET_FLOW_PERCENTAGE,
                SERVICE_HOME_AXES, SERVICE_EMERGENCY_STOP,
                SERVICE_FILAMENT_CHANGE,
                SERVICE_SAVE_SETTINGS_TO_EEPROM,
                SERVICE_RESTORE_FACTORY_SETTINGS,
                SERVICE_LIST_FILES,
                SERVICE_REPORT_FIRMWARE_CAPABILITIES,
                SERVICE_PLAY_BEEP,
                SERVICE_START_BED_LEVELING,
                SERVICE_READ_SETTINGS_FROM_EEPROM,
                SERVICE_MOVE_RELATIVE,
                SERVICE_SEND_GCODE,
            ]
            for service_name in all_service_names:
                if service_name:
                    _LOGGER.debug("Unregistering service: %s.%s", DOMAIN, service_name)
                    hass.services.async_remove(DOMAIN, service_name)
            hass.data.pop(DOMAIN)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
