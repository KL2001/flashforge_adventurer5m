import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import FlashforgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

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
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "camera"])

    # Register services
    hass.services.async_register(DOMAIN, "pause_print", handle_pause_print)
    hass.services.async_register(DOMAIN, "start_print", handle_start_print, schema=vol.Schema({
        vol.Required("file_path"): cv.string,
    }))
    hass.services.async_register(DOMAIN, "cancel_print", handle_cancel_print)
    hass.services.async_register(DOMAIN, "toggle_light", handle_toggle_light)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Handle removal/unloading of a config entry.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "camera"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def handle_pause_print(call):
    """Handle the service call to pause the print."""
    coordinator = hass.data[DOMAIN][call.data["entry_id"]]
    await coordinator.pause_print()

async def handle_start_print(call):
    """Handle the service call to start a print."""
    coordinator = hass.data[DOMAIN][call.data["entry_id"]]
    file_path = call.data["file_path"]
    await coordinator.start_print(file_path)

async def handle_cancel_print(call):
    """Handle the service call to cancel the print."""
    coordinator = hass.data[DOMAIN][call.data["entry_id"]]
    await coordinator.cancel_print()

async def handle_toggle_light(call):
    """Handle the service call to toggle the printer's light."""
    coordinator = hass.data[DOMAIN][call.data["entry_id"]]
    await coordinator.toggle_light()