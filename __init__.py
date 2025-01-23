import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

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

    # Forward setup to sensor and camera platforms
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    await hass.config_entries.async_forward_entry_setup(entry, "camera")

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
