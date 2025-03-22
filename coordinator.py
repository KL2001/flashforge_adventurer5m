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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    resp.raise_for_status()
                    text_data = await resp.text()
                    try:
                        data = json.loads(text_data)
                    except json.JSONDecodeError as e:
                        _LOGGER.error("JSON decode error: %s", e)
                        _LOGGER.debug("Response Text: %s", text_data)
                        return {}
        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP request failed: %s", e)
            return {}
        except Exception as e:
            _LOGGER.exception("Unexpected error during data fetch: %s", e)
            return {}

        _LOGGER.debug("Received response data: %s", data)
        return data

    async def _async_update_data(self) -> dict:
        """
        Fetch data method required by DataUpdateCoordinator.
        This is called automatically by coordinator.async_refresh().
        """
        return await self._fetch_data()

    async def _send_command(self, command: str, payload: dict = None) -> bool:
        """Send a command to the printer."""
        url = f"http://{self.host}:8898/{command}"
        payload = payload or {}
        payload.update({
            "serialNumber": self.serial_number,
            "checkCode": self.check_code
        })

        _LOGGER.debug("Sending command %s to %s with payload: %s", command, url, payload)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 404:
                        _LOGGER.error("Command %s not found at URL: %s", command, url)
                        return False
                    resp.raise_for_status()
                    return True
        except aiohttp.ClientError as e:
            _LOGGER.error("HTTP request failed: %s", e)
            return False
        except Exception as e:
            _LOGGER.exception("Unexpected error during command send: %s", e)
            return False

    async def pause_print(self) -> bool:
        """Pause the current print job."""
        return await self._send_command("pause")

    async def start_print(self, file_path: str) -> bool:
        """Start a new print job."""
        return await self._send_command("start", {"filePath": file_path})

    async def cancel_print(self) -> bool:
        """Cancel the current print job."""
        return await self._send_command("cancel")

    async def toggle_light(self) -> bool:
        """Toggle the printer's light."""
        # Verify the correct endpoint for toggling the light
        return await self._send_command("toggle_light")