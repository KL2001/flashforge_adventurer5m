# coordinator.py

import logging
import aiohttp
import json
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch data from the Flashforge Adventurer 5M Pro printer."""

    def __init__(self, hass: HomeAssistant, host: str, printer_name: str,
                 printer_id: str, scan_interval: int = 10) -> None:
        """
        Initialize the coordinator.

        :param hass: Home Assistant instance
        :param host: Printer's IP address or hostname
        :param printer_name: Printer's name
        :param printer_id: Printer's ID
        :param scan_interval: How often (in seconds) to poll the printer
        """
        self.hass = hass
        self.host = host
        self.printer_name = printer_name
        self.printer_id = printer_id

        super().__init__(
            hass,
            _LOGGER,
            name="flashforge_data_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _fetch_data(self) -> dict:
        """Perform the POST request asynchronously and return the JSON response."""
        url = f"http://{self.host}:8898/detail"
        payload = {
            "printerName": self.printer_name,
            "printerId": self.printer_id
        }

        _LOGGER.debug("Requesting printer data from %s with payload: %s", url, payload)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                text_data = await resp.text()
                data = json.loads(text_data)

        _LOGGER.debug("Received response data: %s", data)
        return data

    async def _async_update_data(self) -> dict:
        """
        Fetch data method required by DataUpdateCoordinator.
        This is called automatically by coordinator.async_refresh().

        We delegate the actual request to _fetch_data().
        """
        return await self._fetch_data()
