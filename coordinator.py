"""
Coordinator for the Flashforge Adventurer 5M PRO integration.

This module handles all communication with the printer's API and coordinates
data updates for all sensors and entities. It implements robust error handling,
retry logic with exponential backoff, and comprehensive data validation.

Printer API Response Structure:
{
    "code": int,          # Status code (0 for success)
    "message": str,       # Status message
    "detail": {
        # Printer Status Information
        "status": str,                # Current status ("IDLE", "PRINTING", etc.)
        "autoShutdown": bool,         # Auto shutdown enabled status
        "autoShutdownTime": int,      # Auto shutdown time in minutes
        "doorStatus": str,            # Door status ("CLOSED" or "OPEN")
        "lightStatus": str,           # Light status ("ON" or "OFF")
        "location": str,              # Printer's configured location name
        "ipAddr": str,                # Printer's IP address
        "macAddr": str,               # Printer's MAC address
        "firmwareVersion": str,       # Printer firmware version
        "nozzleModel": str,           # Model of the printer nozzle
        "nozzleCnt": int,             # Number of nozzles
        "nozzleStyle": str,           # Style/type of nozzle
        "pid": str,                   # Printer ID
        "errorCode": str,             # Current error code (if any)
        
        # Temperature Information
        "chamberTemp": float,         # Current chamber temperature (°C)
        "chamberTargetTemp": float,   # Target chamber temperature (°C)
        "leftTemp": float,            # Left nozzle temperature (°C)
        "leftTargetTemp": float,      # Target left nozzle temperature (°C)
        "rightTemp": float,           # Right nozzle temperature (°C)
        "rightTargetTemp": float,     # Target right nozzle temperature (°C)
        "platTemp": float,            # Platform/bed temperature (°C)
        "platTargetTemp": float,      # Target platform temperature (°C)
        
        # Print Job Information
        "printDuration": int,         # Current print duration in seconds
        "printFileName": str,         # Name of the currently printing file
        "printFileThumbUrl": str,     # URL to thumbnail of the printing file
        
}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_PORT,
    ENDPOINT_DETAIL,
    ENDPOINT_PAUSE,
    ENDPOINT_START,
    ENDPOINT_CANCEL,
    ENDPOINT_COMMAND,
    TIMEOUT_API_CALL,
    TIMEOUT_COMMAND as COORDINATOR_COMMAND_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    BACKOFF_FACTOR,
    CONNECTION_STATE_UNKNOWN,
    CONNECTION_STATE_CONNECTED,
    CONNECTION_STATE_DISCONNECTED,
    CONNECTION_STATE_AUTHENTICATING,
    REQUIRED_RESPONSE_FIELDS,
    REQUIRED_DETAIL_FIELDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host: str, serial_number: str, check_code: str, scan_interval: int = DEFAULT_SCAN_INTERVAL):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.serial_number = serial_number
        self.check_code = check_code
        self.connection_state = CONNECTION_STATE_UNKNOWN
        self.data: dict[str, Any] = {}

    async def _async_update_data(self):
        return await self._fetch_data()

    async def _fetch_data(self):
        url = f"http://{self.host}:{DEFAULT_PORT}{ENDPOINT_DETAIL}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        retries = 0
        delay = RETRY_DELAY
        while retries < MAX_RETRIES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=TIMEOUT_API_CALL) as resp:
                        resp.raise_for_status()
                        data = await resp.json(content_type=None)
                        if self._validate_response(data):
                            self.connection_state = CONNECTION_STATE_CONNECTED
                            return data
                        else:
                            _LOGGER.warning("Invalid response structure: %s", data)
                            self.connection_state = CONNECTION_STATE_DISCONNECTED
                            return {}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning("Fetch attempt %d failed: %s", retries + 1, e)
                retries += 1
                await asyncio.sleep(delay)
                delay *= BACKOFF_FACTOR
        self.connection_state = CONNECTION_STATE_DISCONNECTED
        return {}

    def _validate_response(self, data: dict[str, Any]) -> bool:
        if not all(field in data for field in REQUIRED_RESPONSE_FIELDS):
            return False
        detail = data.get("detail", {})
        if not all(field in detail for field in REQUIRED_DETAIL_FIELDS):
            return False
        return True

    async def _send_command(self, endpoint: str, extra_payload: dict = None):
        url = f"http://{self.host}:{DEFAULT_PORT}{endpoint}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        if extra_payload:
            payload.update(extra_payload)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=COORDINATOR_COMMAND_TIMEOUT) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        _LOGGER.error("Command %s failed with status %s", endpoint, resp.status)
                        return None
        except Exception as e:
            _LOGGER.error("Error sending command %s: %s", endpoint, e)
            return None

    async def pause_print(self):
        return await self._send_command(ENDPOINT_PAUSE)

    async def start_print(self, file_path: str):
        return await self._send_command(ENDPOINT_START, extra_payload={"file_path": file_path})

    async def cancel_print(self):
        return await self._send_command(ENDPOINT_CANCEL)

    async def toggle_light(self, on: bool):
        # Example: LED: 1 for on, LED: 0 for off
        command_str = f"LED: {1 if on else 0}"
        return await self._send_command(ENDPOINT_COMMAND, {"command": command_str})