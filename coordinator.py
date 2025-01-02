import logging
import requests
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch data from the Flashforge Adventurer 5M Pro printer."""

    def __init__(self, hass, host, serial_number, check_code, scan_interval=10):
        """Initialize the coordinator."""
        self.hass = hass
        self.host = host
        self.serial_number = serial_number
        self.check_code = check_code

        super().__init__(
            hass,
            _LOGGER,
            name="flashforge_data_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    def _fetch_data(self):
        """Perform the blocking POST request in a sync context."""
        url = f"http://{self.host}:8898/detail"
        payload = {
            "serialNumber": self.serial_number,
            "checkCode": self.check_code,
        }
        _LOGGER.debug("Requesting printer data from %s", url)

        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    async def _async_update_data(self):
        """Fetch data in the executor to avoid blocking the event loop."""
        return await self.hass.async_add_executor_job(self._fetch_data)
