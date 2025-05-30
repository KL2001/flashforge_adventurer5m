"""
Coordinator for the Flashforge Adventurer 5M PRO integration.

This module handles all communication with the printer's API and coordinates
data updates for all sensors and entities. It implements robust error handling,
retry logic with exponential backoff, and comprehensive data validation.

Printer API Response Structure (for HTTP /detail endpoint on port 8898):
{
    "code": int,          # Status code (0 for success)
    "message": str,       # Status message
    "detail": {
        # ... (various status fields) ...
        "lightStatus": str, # e.g., "open" or "close" (from HTTP API)
    }
}

Light control is handled via TCP M-code commands on port 8899.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    DEFAULT_PORT, # HTTP Port 8898
    DEFAULT_MCODE_PORT, # TCP M-code Port 8899
    ENDPOINT_DETAIL,
    # ENDPOINT_PAUSE, # Removed, functionality now uses TCP M-codes
    # ENDPOINT_START, # Removed, functionality now uses TCP M-codes
    # ENDPOINT_CANCEL, # Removed, functionality now uses TCP M-codes
    # ENDPOINT_COMMAND is not used by toggle_light anymore, and also not used by print controls.
    # It remains in const.py for now, but not imported here unless needed.
    TIMEOUT_API_CALL,
    TIMEOUT_COMMAND as COORDINATOR_COMMAND_TIMEOUT, # For HTTP commands
    MAX_RETRIES,
    RETRY_DELAY,
    BACKOFF_FACTOR,
    CONNECTION_STATE_UNKNOWN,
    CONNECTION_STATE_CONNECTED,
    CONNECTION_STATE_DISCONNECTED,
    REQUIRED_RESPONSE_FIELDS, # Used for HTTP /detail validation
    REQUIRED_DETAIL_FIELDS,   # Used for HTTP /detail validation
    DEFAULT_SCAN_INTERVAL,
)
from .flashforge_tcp import FlashforgeTCPClient # New import

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
        # self._sequence_id is removed as it was for the JSON RPC light attempt, not M-codes

    async def _async_update_data(self):
        """Fetch data from the printer via HTTP API for sensors."""
        return await self._fetch_data()

    async def _fetch_data(self):
        """Fetch data from HTTP /detail endpoint."""
        url = f"http://{self.host}:{DEFAULT_PORT}{ENDPOINT_DETAIL}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        retries = 0
        delay = RETRY_DELAY
        while retries < MAX_RETRIES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=TIMEOUT_API_CALL) as resp:
                        resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                        # Handle misspelled content type from printer for /detail status
                        data = await resp.json(content_type=None)
                        if self._validate_response(data):
                            self.connection_state = CONNECTION_STATE_CONNECTED
                            return data
                        else:
                            _LOGGER.warning("Invalid response structure from /detail: %s", data)
                            self.connection_state = CONNECTION_STATE_DISCONNECTED
                            return {} # Return empty if validation fails
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning("Fetch attempt %d for /detail failed: %s", retries + 1, e)
                retries += 1
                if retries < MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= BACKOFF_FACTOR
                else:
                    _LOGGER.error("Max retries exceeded for /detail fetching.")
                    self.connection_state = CONNECTION_STATE_DISCONNECTED
                    return {} # Return empty on max retries
        return {} # Should be unreachable if loop logic is correct, but as a fallback

    def _validate_response(self, data: dict[str, Any]) -> bool:
        """Validate the structure of the HTTP /detail response."""
        if not all(field in data for field in REQUIRED_RESPONSE_FIELDS):
            _LOGGER.warning(f"Missing one or more required top-level fields: {REQUIRED_RESPONSE_FIELDS} in data: {data}")
            return False
        detail = data.get("detail", {})
        if not isinstance(detail, dict) or not all(field in detail for field in REQUIRED_DETAIL_FIELDS):
            _LOGGER.warning(f"Missing one or more required detail fields: {REQUIRED_DETAIL_FIELDS} in detail: {detail}")
            return False
        return True

    async def _send_command(self, endpoint: str, extra_payload: dict = None, expect_json_response: bool = True):
        """Sends a command via HTTP POST, wrapped with auth details.
           Used for commands that expect serialNumber/checkCode in payload.
        """
        url = f"http://{self.host}:{DEFAULT_PORT}{endpoint}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        if extra_payload:
            payload.update(extra_payload)

        _LOGGER.debug(f"Sending HTTP command to {url} with payload: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=COORDINATOR_COMMAND_TIMEOUT) as resp:
                    response_text = await resp.text()
                    _LOGGER.debug(f"HTTP command to {endpoint} status: {resp.status}, response: {response_text}")
                    if resp.status == 200:
                        if expect_json_response:
                            # Handle misspelled content type from printer for command responses
                            return await resp.json(content_type=None)
                        return {"status": "success_http_200", "raw_response": response_text} # Or just True
                    else:
                        _LOGGER.error(
                            f"HTTP command to {endpoint} failed with status {resp.status}. Response: {response_text}"
                        )
                        return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Error sending HTTP command to {endpoint}: {e}")
            return None
        return None # Should not be reached if try/except is comprehensive

    async def pause_print(self):
        """Pauses the current print using TCP M-code ~M25."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M25\r\n"
        action = "PAUSE PRINT"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(f"Successfully sent {action} command. Response: {response}")
                # await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
                return False
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}")
            return False

    async def resume_print(self):
        """Resumes the current print using TCP M-code ~M24."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M24\r\n"
        action = "RESUME PRINT"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(f"Successfully sent {action} command. Response: {response}")
                # Consider an immediate refresh if printer status changes instantly
                # await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
                return False
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}")
            return False

    async def start_print(self, file_path: str):
        """Starts a new print using TCP M-code ~M23."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = f"~M23 0:/user/{file_path}\r\n"
        action = f"START PRINT ({file_path})"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(f"Successfully sent {action} command. Response: {response}")
                # Consider an immediate refresh if printer status changes instantly
                # await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
                return False
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}")
            return False

    async def cancel_print(self):
        """Cancels the current print using TCP M-code ~M26."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M26\r\n"
        action = "CANCEL PRINT"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(f"Successfully sent {action} command. Response: {response}")
                # await self.async_request_refresh()
                return True
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
                return False
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}")
            return False

    async def toggle_light(self, on: bool):
        """Toggles the printer light ON or OFF using TCP M-code commands."""
        # This now uses TCP on port DEFAULT_MCODE_PORT (8899)
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)

        if on:
            command = "~M146 r255 g255 b255 F0\r\n"  # Light ON (White)
            action = "ON"
        else:
            command = "~M146 r0 g0 b0 F0\r\n"     # Light OFF
            action = "OFF"

        _LOGGER.info(f"Attempting to turn light {action} using TCP command: {command.strip()}")

        try:
            # The send_command in FlashforgeTCPClient handles connect, send, receive, close
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(f"Successfully sent light {action} TCP command. Printer response: '{response.strip()}'")
                # Optionally, trigger a coordinator refresh to pick up the new state sooner
                # if the light status is part of the HTTP /detail endpoint.
                # The M119 response showed "LED: 1", the /detail showed "lightStatus":"open".
                # These might update independently or the HTTP one might lag.
                # For now, let's rely on the next scheduled update.
                # await self.async_request_refresh()
                return True # Indicate command was sent successfully
            else:
                _LOGGER.error(f"Failed to send light {action} TCP command. Details: {response}")
                return False
        except Exception as e:
            # This catches errors from tcp_client instantiation or if send_command itself raises an unexpected error
            _LOGGER.error(f"Exception during toggle_light TCP operation: {e}")
            return False
