import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import FlashforgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    This method is called when Home Assistant first loads your integration.
    For a purely config-flow-based integration, we often just return True.
    """
    # If you don't support legacy YAML, we don't do anything here
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up the Flashforge Adventurer 5M Pro integration from a config entry.

    This is called after the user has filled out your config flow form
    (see config_flow.py), or if an existing entry is reloaded.
    """
    _LOGGER.debug("Setting up flashforge_adventurer5m entry: %s", entry.data)

    # 1) Extract config data from the entry (provided by config_flow.py)
    host = entry.data["host"]
    serial_number = entry.data["serial_number"]
    check_code = entry.data["check_code"]
    scan_interval = entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    # 2) Create a coordinator for fetching data
    coordinator = FlashforgeDataUpdateCoordinator(
        hass,
        host=host,
        serial_number=serial_number,
        check_code=check_code,
        scan_interval=scan_interval,
    )

    # 3) Store coordinator under hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 4) Refresh once at startup
    await coordinator.async_refresh()

    # 5) Forward setup to sensor and camera platforms
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    await hass.config_entries.async_forward_entry_setup(entry, "camera")

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Handle removal/unloading of a config entry.
    """
    # 1) Unload the sensor and camera platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "camera"]
    )

    # 2) Remove coordinator from hass.data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
