import logging
import aiohttp
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch data from the Flashforge Adventurer 5M Pro printer."""

    def __init__(self, hass, host, serial_number, check_code, scan_interval: int = 10):
        """Initialize."""
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

    async def _fetch_data(self):
        """Make the POST request asynchronously."""
        url = f"http://{self.host}:8898/detail"
        payload = {
            "serialNumber": self.serial_number,
            "checkCode": self.check_code
        }
        _LOGGER.debug("Requesting printer data from %s", url)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()

        """Fetch data using async_add_executor_job to run the blocking fetch_data method in an executor."""
        """Fetch data in executor to not block event loop."""
        return await self._fetch_data()
