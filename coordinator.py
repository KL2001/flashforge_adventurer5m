# coordinator.py

import logging
import aiohttp
import json
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch data from the Flashforge Adventurer 5M Pro printer."""

    def __init__(self, hass: HomeAssistant, host: str, serial_number: str,
                 check_code: str, scan_interval: int = DEFAULT_SCAN_INTERVAL) -> None:
        """
        Initialize the coordinator.

        :param hass: Home Assistant instance
        :param host: Printer's IP address or hostname
        :param serial_number: Printer's serial number
        :param check_code: Printer's check code
        :param scan_interval: How often (in seconds) to poll the printer
        """
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

    async def _fetch_data(self) -> dict:
        """Perform the POST request asynchronously and return the JSON response."""
        url = f"http://{self.host}:8898/detail"
        payload = {
            "serialNumber": self.serial_number,
            "checkCode": self.check_code
        }

        _LOGGER.debug("Requesting printer data from %s with payload: %s", url, payload)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()

        _LOGGER.debug("Received response data: %s", data)
        return data

    async def _async_update_data(self) -> dict:
        """
        Fetch data method required by DataUpdateCoordinator.
        This is called automatically by coordinator.async_refresh().
        """
        return await self._fetch_data()
