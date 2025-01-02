import logging
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.discovery import load_platform  # type: ignore

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import FlashforgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Flashforge Adventurer 5M Pro integration from configuration.yaml."""

    # 1) Look in configuration.yaml for 'flashforge_adventurer5m:' block
    if DOMAIN not in config:
        _LOGGER.warning("No '%s:' block found in configuration.yaml", DOMAIN)
        return True

    conf = config[DOMAIN]
    missing_keys = []
    host = conf.get("host")
    serial_number = conf.get("serial_number")
    check_code = conf.get("check_code")
    scan_interval = conf.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    if not host:
        missing_keys.append("host")
    if not serial_number:
        missing_keys.append("serial_number")
    if not check_code:
        missing_keys.append("check_code")
    if missing_keys:
        _LOGGER.error("Missing required config keys: %s", ", ".join(missing_keys))
        return False

    # 2) Create a coordinator for fetching data
    coordinator = FlashforgeDataUpdateCoordinator(
        hass,
        host=host,
        serial_number=serial_number,
        check_code=check_code,
        scan_interval=scan_interval,
    )

    # 3) Initialize the domain dict in hass.data, then store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["coordinator"] = coordinator

    # 4) Start first data refresh
    await coordinator.async_refresh()

    # 5) Load sensor platform once
    load_platform(hass, "sensor", DOMAIN, {}, config)

    return True
