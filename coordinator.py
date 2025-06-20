"""
Coordinator for the Flashforge Adventurer 5M PRO integration.
"""

from __future__ import annotations

import asyncio
import logging
import re  # For parsing M114
from datetime import timedelta
from typing import Any, Optional, List # Added List

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_MCODE_PORT,
    ENDPOINT_DETAIL,
    TIMEOUT_API_CALL,
    TIMEOUT_COMMAND as COORDINATOR_COMMAND_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    BACKOFF_FACTOR,
    CONNECTION_STATE_UNKNOWN,
    CONNECTION_STATE_CONNECTED,
    CONNECTION_STATE_DISCONNECTED,
    REQUIRED_RESPONSE_FIELDS,
    REQUIRED_DETAIL_FIELDS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_PRINTING_SCAN_INTERVAL,
    PRINTING_STATES,
    API_ATTR_STATUS,
    TCP_CMD_PRINT_FILE_PREFIX_USER,
    TCP_CMD_PRINT_FILE_PREFIX_ROOT,
    API_ATTR_DETAIL,
    API_ATTR_X_ENDSTOP_STATUS,
    API_ATTR_Y_ENDSTOP_STATUS,
    API_ATTR_Z_ENDSTOP_STATUS,
    API_ATTR_FILAMENT_ENDSTOP_STATUS,
    API_ATTR_BED_LEVELING_STATUS,
    CONF_TCP_TIMEOUT, # Added
    TIMEOUT_COMMAND as DEFAULT_TCP_TIMEOUT, # Added - using TIMEOUT_COMMAND as the default
)
from .flashforge_tcp import FlashforgeTCPClient

_LOGGER = logging.getLogger(__name__)

# Maximum number of allowed consecutive failures before data is marked stale
MAX_TCP_DATA_FAILURES = 3


class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass,
        host: str,
        serial_number: str,
        check_code: str,
        regular_scan_interval: int = DEFAULT_SCAN_INTERVAL,
        printing_scan_interval: int = DEFAULT_PRINTING_SCAN_INTERVAL,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=regular_scan_interval),
        )
        self.host = host
        self.serial_number = serial_number
        self.check_code = check_code
        self.regular_scan_interval = regular_scan_interval
        self.printing_scan_interval = printing_scan_interval
        self.connection_state = CONNECTION_STATE_UNKNOWN
        self.data: dict[str, Any] = {}

        # Initialize consecutive failure counters
        self._consecutive_file_list_failures = 0
        self._consecutive_coords_failures = 0
        self._consecutive_endstop_failures = 0
        self._consecutive_bed_leveling_failures = 0

    async def _create_service_error_notification(self, action_description: str, error_details: str):
        """Helper method to create a persistent notification for service call errors."""
        _LOGGER.debug(f"Creating persistent notification for action: {action_description}, details: {error_details}")
        # Create a slug from the action description for the notification ID
        action_description_slug = re.sub(r'\W+', '_', action_description.lower()).strip('_')

        self.hass.services.call(
            "persistent_notification",
            "create",
            {
                "title": "Flashforge Printer Error",
                "message": f"Failed to {action_description}. Check printer connection and status. Details: {error_details}",
                "notification_id": f"{DOMAIN}_service_error_{action_description_slug}"
            },
            blocking=False,
        )

    async def _send_tcp_command(
        self, command: str, action: str, response_terminator: str = "ok\r\n", return_bytes: bool = False
    ) -> tuple[bool, str]:
        """Helper method to send a TCP command and handle common logic. Returns (success, response_or_error_message)."""
        configured_timeout = self.config_entry.options.get(CONF_TCP_TIMEOUT, DEFAULT_TCP_TIMEOUT)
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT, timeout=configured_timeout)
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()} with timeout {configured_timeout}s")
        try:
            # Pass return_bytes to the underlying client call if needed by the caller
            # (e.g., _fetch_printable_files_list)
            success, response = await tcp_client.send_command(
                command, response_terminator=response_terminator, return_bytes=return_bytes
            )
            if success:
                _LOGGER.info(
                    f"Successfully sent {action} command. Response: {response.strip() if isinstance(response, str) else '(bytes response)'}"
                )
                return True, response # response can be str or bytes
            else:
                # response here is an error message (str) from tcp_client.send_command
                _LOGGER.error(
                    f"Failed to send {action} command. Error: {response}"
                )
                return False, response
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)
            return False, str(e)

    async def _fetch_bed_leveling_status(self) -> dict:
        """Fetches and parses bed leveling status from M420 command."""
        status_data = {API_ATTR_BED_LEVELING_STATUS: None}
        command = "~M420 S0\r\n"
        action = "FETCH BED LEVELING STATUS (M420 S0)"

        configured_timeout = self.config_entry.options.get(CONF_TCP_TIMEOUT, DEFAULT_TCP_TIMEOUT)
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT, timeout=configured_timeout)
        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()} with timeout {configured_timeout}s")

        try:
            success, response = await tcp_client.send_command(command, response_terminator="ok\r\n")
            if success and response:
                _LOGGER.debug(f"Raw response for {action}: {response}")
                response_lower = response.lower()
                if "bed leveling is on" in response_lower:
                    status_data[API_ATTR_BED_LEVELING_STATUS] = True
                elif "bed leveling is off" in response_lower:
                    status_data[API_ATTR_BED_LEVELING_STATUS] = False
                else:
                    _LOGGER.warning(f"Could not determine bed leveling status from M420 response: {response[:200]}")
                _LOGGER.debug(f"Parsed bed leveling data: {status_data}")
            elif success:
                _LOGGER.warning(f"{action} command sent, but no parseable data in response: {response}")
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)

        if hasattr(tcp_client, '_writer') and tcp_client._writer and not tcp_client._writer.is_closing():
            tcp_client.close()

        return status_data

    async def _fetch_endstop_status(self) -> dict:
        """Fetches and parses endstop status from M119 command."""
        endstop_data = {
            API_ATTR_X_ENDSTOP_STATUS: None,
            API_ATTR_Y_ENDSTOP_STATUS: None,
            API_ATTR_Z_ENDSTOP_STATUS: None,
            API_ATTR_FILAMENT_ENDSTOP_STATUS: None, # Initialize, will remain None if not reported
        }
        action = "FETCH ENDSTOP STATUS (M119)"
        command = "~M119\r\n"

        configured_timeout = self.config_entry.options.get(CONF_TCP_TIMEOUT, DEFAULT_TCP_TIMEOUT)
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT, timeout=configured_timeout)
        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()} with timeout {configured_timeout}s")

        try:
            success, response = await tcp_client.send_command(command, response_terminator="ok\r\n")
            if success and response:
                _LOGGER.debug(f"Raw response for {action}: {response}")
                # Marlin typically responds with one line per endstop, e.g.:
                # x_min:open
                # y_min:open
                # z_min:TRIGGERED
                # filament:open (or some other key for filament sensor)
                lines = response.lower().split('\n')
                for line in lines:
                    line = line.strip()
                    if "x_min:" in line:
                        endstop_data[API_ATTR_X_ENDSTOP_STATUS] = "triggered" in line
                    elif "y_min:" in line:
                        endstop_data[API_ATTR_Y_ENDSTOP_STATUS] = "triggered" in line
                    elif "z_min:" in line:
                        endstop_data[API_ATTR_Z_ENDSTOP_STATUS] = "triggered" in line
                    # Adjust "filament" based on actual M119 output key for filament sensor
                    elif "filament" in line:
                        endstop_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = "triggered" in line

                _LOGGER.debug(f"Parsed endstop data: {endstop_data}")

            elif success:
                _LOGGER.warning(f"{action} command sent, but no parseable data in response: {response}")
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")

        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)

        # Ensure client is closed if send_command itself had an issue before its own finally
        # This check is a bit defensive as send_command should always close.
        if hasattr(tcp_client, '_writer') and tcp_client._writer and not tcp_client._writer.is_closing():
            tcp_client.close()
        # Return success status along with data for failure counting
        return endstop_data # Assuming this implies success if no exception, needs check if send_command failed

    async def _fetch_printable_files_list(self) -> list[str]: # Returns list on success, raises error on comm failure
        """
        Fetches the list of printable files using TCP M-code ~M661.
        Raises ConnectionError or similar on TCP communication failure.
        Returns an empty list if parsing fails or no files are found but communication was successful.
        """
        # tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT) # Client instantiated in _send_tcp_command
        command = "~M661\r\n"
        action = "FETCH PRINTABLE FILES"
        files_list = []
        file_path_regex = re.compile(r"(/data/(?:[^: ]+\/)*[^: ]+\.(?:gcode|gx))")

        # Use the class's _send_tcp_command which now returns (bool, str|bytes)
        # Request bytes for M661
        success, response_or_error = await self._send_tcp_command(
            command, action, return_bytes=True
        )

        if not success:
            # _send_tcp_command already logs the error.
            # Raise an exception to be caught by _fetch_data for failure counting.
            raise ConnectionError(f"Failed to send {action} command: {response_or_error}")

        response_bytes = response_or_error # Known to be bytes if success=True and return_bytes=True
        if response_bytes: # Should always be true if success
            _LOGGER.debug(f"Raw response for {action} (first 250 bytes): {response_bytes[:250]}")

            # Convert to string, replacing non-UTF-8 characters
            response_str = response_bytes.decode('utf-8', errors='replace')

            payload_start_index = response_str.rfind("ok\n")
            if payload_start_index != -1:
                payload_str = response_str[payload_start_index + len("ok\n"):]
            else:
                _LOGGER.warning(
                    f"M661 parsing: 'ok\\n' not found in response. Processing entire response as payload. Response: '{response_str[:200]}...'"
                )
                payload_str = response_str # Process what we got

            payload_str = payload_str.strip()

            if not payload_str:
                _LOGGER.warning("M661 parsing: Payload is empty after stripping prefixes and whitespace.")
                return [] # Successful communication, but no data or unparseable

            _LOGGER.debug(f"Payload for M661 parsing (first 200 chars): '{payload_str[:200]}...'")

            raw_paths = file_path_regex.findall(payload_str)

            if not raw_paths and payload_str:
                _LOGGER.warning(
                    f"M661 parsing: No file paths found via regex in non-empty payload. Payload sample: '{payload_str[:300]}...'"
                )

            for raw_path in raw_paths:
                cleaned_path = "".join(
                    filter(lambda x: x.isprintable(), raw_path)
                ).strip()
                if cleaned_path.startswith("/data/") and cleaned_path.endswith((".gcode", ".gx")):
                    files_list.append(cleaned_path)
                else:
                    _LOGGER.debug(
                        f"M661 parsing - Regex matched path '{raw_path}' but failed cleaning/validation: '{cleaned_path}'. Skipping."
                    )

            if files_list:
                _LOGGER.info(f"Successfully parsed file list: {files_list}")
            elif payload_str:
                _LOGGER.warning(
                    "M661 parsing: File list is empty after processing a non-empty payload. "
                    f"Payload sample: '{payload_str[:300]}...'"
                )
            return files_list
        else: # No response_bytes but success was true (should not happen with current _send_tcp_command)
             _LOGGER.warning(f"{action} command sent, but no data in response despite success.")
             return []


    async def _fetch_coordinates(self) -> Optional[dict[str, float]]: # Returns dict on success, None on parse fail, raises on comm fail
        """
        Fetches and parses the printer's X,Y,Z coordinates using M-code ~M114.
        Returns dict with 'x', 'y', 'z' on success.
        Returns None if parsing fails but communication was okay.
        Raises ConnectionError or similar on TCP communication failure.
        """
        command = "~M114\r\n"
        action = "FETCH COORDINATES"

        success, response_or_error = await self._send_tcp_command(command, action)

        if not success:
            raise ConnectionError(f"Failed to send {action} command: {response_or_error}")

        response_str = response_or_error # Known to be str if success=True and return_bytes=False (default)
        if response_str:
            _LOGGER.debug(f"Raw response for {action}: {response_str}")
            coordinates = {}
            match_x = re.search(r"X:([+-]?\d+\.?\d*)", response_str)
            match_y = re.search(r"Y:([+-]?\d+\.?\d*)", response_str)
            match_z = re.search(r"Z:([+-]?\d+\.?\d*)", response_str)

            if match_x: coordinates["x"] = float(match_x.group(1))
            if match_y: coordinates["y"] = float(match_y.group(1))
            if match_z: coordinates["z"] = float(match_z.group(1))

            if "x" in coordinates and "y" in coordinates and "z" in coordinates:
                _LOGGER.debug(f"Successfully parsed coordinates: {coordinates}")
                return coordinates
            else:
                _LOGGER.warning(
                    f"Could not parse all X,Y,Z coordinates from M114 response: {response_str}. Parsed: {coordinates}"
                )
                return None # Communication success, parsing failure
        else: # No response string but success was true
            _LOGGER.warning(f"{action} command sent, but no data in response despite success.")
            return None


    async def _async_update_data(self):
        fresh_data = await self._fetch_data() # This is the method we are modifying.

        if fresh_data: # Check if fresh_data is not None or empty
            # Update interval logic based on fresh_data
            printer_status_detail = fresh_data.get(API_ATTR_DETAIL, {})
            current_printer_status = printer_status_detail.get(API_ATTR_STATUS) if isinstance(printer_status_detail, dict) else None
            is_printing = current_printer_status in PRINTING_STATES
            desired_interval_seconds = self.printing_scan_interval if is_printing else self.regular_scan_interval

            if self.update_interval.total_seconds() != desired_interval_seconds:
                self.update_interval = timedelta(seconds=desired_interval_seconds)
                _LOGGER.info(f"FlashForge coordinator update interval changed to {desired_interval_seconds} seconds (Status: {current_printer_status})")
        else: # fresh_data is None (e.g. max HTTP retries exceeded)
            _LOGGER.warning("No fresh data from _fetch_data (HTTP fetch likely failed). Interval not changed, or reverting.")
            if self.update_interval.total_seconds() == self.printing_scan_interval:
                self.update_interval = timedelta(seconds=self.regular_scan_interval)
                _LOGGER.info(f"Reverting to regular scan interval ({self.regular_scan_interval}s) due to HTTP data fetch failure.")

        return fresh_data # This will be self.data in the DataUpdateCoordinator


    async def _fetch_data(self):
        """Fetch data from HTTP /detail endpoint and, on subsequent updates, files/coords/status via TCP."""
        current_data: dict[str, Any] = {} # Holds data for this fetch run. Will be merged from HTTP and TCP.
        http_fetch_successful = False

        # Step 1: Fetch main status data via HTTP
        url = f"http://{self.host}:{DEFAULT_PORT}{ENDPOINT_DETAIL}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        retries = 0
        delay = RETRY_DELAY
        while retries < MAX_RETRIES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=TIMEOUT_API_CALL) as resp:
                        resp.raise_for_status()
                        api_response_data = await resp.json(content_type=None)
                        if self._validate_response(api_response_data):
                            self.connection_state = CONNECTION_STATE_CONNECTED
                            current_data.update(api_response_data) # Start with HTTP data
                            http_fetch_successful = True
                            _LOGGER.debug("HTTP /detail data fetched and validated successfully.")
                            break
                        else:
                            _LOGGER.warning("Invalid response structure from /detail: %s", api_response_data)
                            # Keep http_fetch_successful as False, loop or break if max_retries
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning("Fetch attempt %d for /detail failed: %s", retries + 1, e)
            except Exception as e: # Catch any other unexpected errors during HTTP fetch
                _LOGGER.error("Unexpected error during /detail fetch: %s", e, exc_info=True)

            retries += 1
            if retries < MAX_RETRIES and not http_fetch_successful:
                await asyncio.sleep(delay)
                delay *= BACKOFF_FACTOR
            else: # Max retries or successful
                break

        if not http_fetch_successful:
            _LOGGER.error("Max retries exceeded or persistent error for /detail fetching. HTTP data unavailable.")
            self.connection_state = CONNECTION_STATE_DISCONNECTED
            # Initialize all expected keys to None or default if HTTP fails,
            # as TCP calls will be skipped.
            current_data[API_ATTR_DETAIL] = {} # Ensure detail key exists
            current_data["printable_files"] = None
            current_data["x_position"] = None
            current_data["y_position"] = None
            current_data["z_position"] = None
            current_data[API_ATTR_X_ENDSTOP_STATUS] = None
            current_data[API_ATTR_Y_ENDSTOP_STATUS] = None
            current_data[API_ATTR_Z_ENDSTOP_STATUS] = None
            current_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = None
            current_data[API_ATTR_BED_LEVELING_STATUS] = None
            return current_data # Return immediately, no TCP calls if HTTP failed.

        # Initialize TCP-derived data fields before attempting fetches
        # These will be updated on success or handled by stale logic on failure.
        current_data["printable_files"] = None
        current_data["x_position"] = None
        current_data["y_position"] = None
        current_data["z_position"] = None
        current_data[API_ATTR_X_ENDSTOP_STATUS] = None
        current_data[API_ATTR_Y_ENDSTOP_STATUS] = None
        current_data[API_ATTR_Z_ENDSTOP_STATUS] = None
        current_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = None
        current_data[API_ATTR_BED_LEVELING_STATUS] = None

        if not self.data: # This is the first successful HTTP fetch
            _LOGGER.debug("Initial successful HTTP data fetch. TCP data will be fetched on next update. Initializing TCP fields to None/empty.")
            # Values already initialized to None above, printable_files can be empty list for type consistency
            current_data["printable_files"] = []
            # Return current_data which only contains HTTP data and None/empty for TCP fields
            return current_data

        # --- Step 2: Fetch TCP data only if HTTP was successful AND it's a subsequent run (self.data exists) ---
        # --- Printable Files ---
        try:
            files_list = await self._fetch_printable_files_list() # Raises error on comm failure
            current_data["printable_files"] = files_list # Can be empty list if successful
            self._consecutive_file_list_failures = 0
        except Exception as e: # Catch ConnectionError from _fetch_printable_files_list or other exceptions
            _LOGGER.warning(f"Failed to fetch printable files list (attempt {self._consecutive_file_list_failures + 1}): {e}")
            self._consecutive_file_list_failures += 1
            if self._consecutive_file_list_failures >= MAX_TCP_DATA_FAILURES:
                current_data["printable_files"] = None # Mark as unavailable
                _LOGGER.error("Printable files list is now unavailable due to repeated fetch failures.")
            else:
                current_data["printable_files"] = self.data.get("printable_files", []) # Use old data

        # --- Coordinates ---
        try:
            coords = await self._fetch_coordinates() # Returns dict, None for parse fail, raises for comm fail
            if coords is not None: # Successfully fetched and parsed
                current_data["x_position"] = coords.get("x")
                current_data["y_position"] = coords.get("y")
                current_data["z_position"] = coords.get("z")
                self._consecutive_coords_failures = 0
            else: # Communication was okay, but parsing failed (coords is None)
                 # This counts as a failure for stale data purposes if coords are expected
                _LOGGER.warning(f"Coordinate parsing failed (attempt {self._consecutive_coords_failures + 1}), treating as fetch failure for stale logic.")
                # Increment explicitly here because _fetch_coordinates returning None doesn't mean a ConnectionError to be caught by generic Exception
                self._consecutive_coords_failures += 1
                # Fall through to the same stale logic as ConnectionError
                raise ValueError("Coordinate parsing returned None") # Re-raise to consolidate stale logic
        except Exception as e: # Catches ConnectionError from _fetch_coordinates or the ValueError from above
            if not isinstance(e, ValueError) or "Coordinate parsing returned None" not in str(e) :
                 _LOGGER.warning(f"Failed to fetch coordinates (attempt {self._consecutive_coords_failures + 1}): {e}")
                 self._consecutive_coords_failures += 1 # Increment only if not already incremented for parse failure

            if self._consecutive_coords_failures >= MAX_TCP_DATA_FAILURES:
                current_data["x_position"] = None
                current_data["y_position"] = None
                current_data["z_position"] = None
                _LOGGER.error("Coordinates are now unavailable due to repeated fetch failures.")
            else:
                current_data["x_position"] = self.data.get("x_position")
                current_data["y_position"] = self.data.get("y_position")
                current_data["z_position"] = self.data.get("z_position")

        # --- Endstop Status ---
        # _fetch_endstop_status itself calls _send_tcp_command. We need to know if _send_tcp_command failed.
        # For simplicity, let's assume _fetch_endstop_status raises an exception on comms failure.
        # If it returns a dict with all Nones, that's a successful parse of "nothing useful".
        try:
            # We need _fetch_endstop_status to reliably signal communication failure,
            # e.g. by re-raising an exception from _send_tcp_command if it fails.
            # For now, let's assume it might return a dict with default Nones on failure, or raise.
            # A more robust way: modify _fetch_endstop_status to return (bool, dict) or raise.
            # For now, we'll try to infer failure if the result is minimal and different from previous.
            # This is less ideal.
            # Let's assume for now it raises ConnectionError if _send_tcp_command fails.
            endstop_status_data = await self._fetch_endstop_status() # Assumed to raise on comms error
            current_data.update(endstop_status_data)
            self._consecutive_endstop_failures = 0
        except Exception as e: # Primarily catching ConnectionError if _fetch_endstop_status bubbles it up
            _LOGGER.warning(f"Failed to fetch endstop status (attempt {self._consecutive_endstop_failures + 1}): {e}")
            self._consecutive_endstop_failures += 1
            if self._consecutive_endstop_failures >= MAX_TCP_DATA_FAILURES:
                current_data[API_ATTR_X_ENDSTOP_STATUS] = None
                current_data[API_ATTR_Y_ENDSTOP_STATUS] = None
                current_data[API_ATTR_Z_ENDSTOP_STATUS] = None
                current_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = None
                _LOGGER.error("Endstop status is now unavailable due to repeated fetch failures.")
            else:
                current_data[API_ATTR_X_ENDSTOP_STATUS] = self.data.get(API_ATTR_X_ENDSTOP_STATUS)
                current_data[API_ATTR_Y_ENDSTOP_STATUS] = self.data.get(API_ATTR_Y_ENDSTOP_STATUS)
                current_data[API_ATTR_Z_ENDSTOP_STATUS] = self.data.get(API_ATTR_Z_ENDSTOP_STATUS)
                current_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = self.data.get(API_ATTR_FILAMENT_ENDSTOP_STATUS)

        # --- Bed Leveling Status ---
        try:
            # Similar assumption as endstops for _fetch_bed_leveling_status
            bed_level_status_data = await self._fetch_bed_leveling_status() # Assumed to raise on comms error
            current_data.update(bed_level_status_data)
            self._consecutive_bed_leveling_failures = 0
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch bed leveling status (attempt {self._consecutive_bed_leveling_failures + 1}): {e}")
            self._consecutive_bed_leveling_failures += 1
            if self._consecutive_bed_leveling_failures >= MAX_TCP_DATA_FAILURES:
                current_data[API_ATTR_BED_LEVELING_STATUS] = None
                _LOGGER.error("Bed leveling status is now unavailable due to repeated fetch failures.")
            else:
                current_data[API_ATTR_BED_LEVELING_STATUS] = self.data.get(API_ATTR_BED_LEVELING_STATUS)

        return current_data

    def _validate_response(self, data: dict[str, Any]) -> bool:
        """Validate the structure of the HTTP /detail response."""
        if not all(field in data for field in REQUIRED_RESPONSE_FIELDS):
            _LOGGER.warning(
                f"Missing one or more required top-level fields: {REQUIRED_RESPONSE_FIELDS} in data: {data}"
            )
            return False
        # API_ATTR_DETAIL is "detail"
        detail_data = data.get(
            API_ATTR_DETAIL, {}
        )  # Use constant if "detail" key was an API_ATTR_
        if not isinstance(detail_data, dict) or not all(
            field in detail_data for field in REQUIRED_DETAIL_FIELDS
        ):
            _LOGGER.warning(
                f"Missing one or more required detail fields: {REQUIRED_DETAIL_FIELDS} in detail: {detail_data}"
            )
            return False
        return True

    async def _send_http_command(
        self,
        endpoint: str,
        action_description: str, # Added for notification
        extra_payload: Optional[dict[str, Any]] = None,
        expect_json_response: bool = True,
    ) -> Optional[Any]: # Return type is Any if expect_json_response, else dict or None
        """
        Sends a command via HTTP POST, wrapped with auth details.
        Returns JSON response, a dict, or None on failure.
        Creates a notification on failure.
        """
        url = f"http://{self.host}:{DEFAULT_PORT}{endpoint}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        if extra_payload:
            payload.update(extra_payload)

        _LOGGER.debug(f"Sending HTTP command to {url} for action '{action_description}' with payload: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=COORDINATOR_COMMAND_TIMEOUT
                ) as resp:
                    response_text = await resp.text()
                    _LOGGER.debug(
                        f"HTTP command to {endpoint} for '{action_description}' status: {resp.status}, response: {response_text[:500]}"
                    )
                    if resp.status == 200:
                        if expect_json_response:
                            return await resp.json(content_type=None)
                        return {
                            "status": "success_http_200",
                            "raw_response": response_text,
                        }
                    else:
                        error_details = f"HTTP Status {resp.status}. Response: {response_text[:200]}"
                        _LOGGER.error(
                            f"HTTP command for '{action_description}' failed: {error_details}"
                        )
                        await self._create_service_error_notification(action_description, error_details)
                        return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error_details = f"ClientError/Timeout: {str(e)}"
            _LOGGER.error(
                f"Error sending HTTP command for '{action_description}': {error_details}", exc_info=True
            )
            await self._create_service_error_notification(action_description, error_details)
            return None
        except Exception as e: # Catch any other unexpected errors
            error_details = f"Unexpected error: {str(e)}"
            _LOGGER.error(
                f"Unexpected error sending HTTP command for '{action_description}': {error_details}", exc_info=True
            )
            await self._create_service_error_notification(action_description, error_details)
            return None

    async def pause_print(self) -> bool:
        """Pauses the current print using TCP M-code ~M25."""
        action = "PAUSE PRINT"
        success, response_or_error = await self._send_tcp_command("~M25\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def async_send_gcode(self, gcode_command: str) -> bool:
        """Sends a raw G-code command to the printer."""
        action = "SEND G-CODE" # Generic action for notification title if needed
        if not gcode_command or not gcode_command.strip():
            _LOGGER.error("Send G-code command was empty.")
            await self._create_service_error_notification(f"{action} (empty command)", "Command was empty.")
            return False

        command_to_send = gcode_command.strip()
        # Ensure command ends with \r\n, but avoid double \r\n if user already included it.
        if not command_to_send.endswith("\r\n"):
            command_to_send += "\r\n"

        # More specific action description for logging and potentially more detailed notification messages.
        action_description_log = f"SEND GCODE ({command_to_send[:30].strip()}...)"
        _LOGGER.info(f"Attempting to send G-code: {command_to_send.strip()}")

        # _send_tcp_command returns (success, response_or_error_message)
        success, response = await self._send_tcp_command(
            command_to_send,
            action_description_log # Use the more detailed description for the command sending log
        )

        if success:
            _LOGGER.info(f"G-code command '{command_to_send.strip()}' sent successfully. Response: {response.strip() if isinstance(response, str) else '(bytes response)'}")
            # Optionally, create a success notification if desired, but typically not done for G-code.
            # Example:
            # self.hass.services.call(
            #     "persistent_notification", "create",
            #     {"title": "Flashforge G-code Sent", "message": f"Command '{command_to_send.strip()}' sent. Response: {response.strip()}", "notification_id": f"{DOMAIN}_gcode_sent"},
            #     blocking=False,
            # )
        else:
            _LOGGER.error(f"Failed to send G-code command '{command_to_send.strip()}'. Response/Error: {response}")
            # Use the generic 'action' for the notification title, but provide specific command in message
            await self._create_service_error_notification(
                f"{action} ({command_to_send[:20].strip()}...)", # Short command snippet in title
                f"Command: {command_to_send.strip()} Failed. Details: {response}"
            )
        return success

    async def resume_print(self) -> bool:
        """Resumes the current print using TCP M-code ~M24."""
        action = "RESUME PRINT"
        success, response_or_error = await self._send_tcp_command("~M24\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def start_print(self, file_path: str) -> bool:
        """Starts a new print using TCP M-code ~M23."""
        action = f"START PRINT ({file_path})"
        if file_path.startswith(TCP_CMD_PRINT_FILE_PREFIX_USER):
            command = f"~M23 {file_path}\r\n"
        elif file_path.startswith("/"):
            command = (
                f"~M23 {TCP_CMD_PRINT_FILE_PREFIX_ROOT}{file_path.lstrip('/')}\r\n"
            )
        else:
            command = f"~M23 {TCP_CMD_PRINT_FILE_PREFIX_USER}{file_path}\r\n"

        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def cancel_print(self) -> bool:
        """Cancels the current print using TCP M-code ~M26."""
        action = "CANCEL PRINT"
        success, response_or_error = await self._send_tcp_command("~M26\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def toggle_light(self, on: bool) -> bool:
        """Toggles the printer light ON or OFF using TCP M-code commands."""
        if on:
            command = "~M146 r255 g255 b255 F0\r\n"
            action = "TURN LIGHT ON"
        else:
            command = "~M146 r0 g0 b0 F0\r\n"
            action = "TURN LIGHT OFF"

        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def set_extruder_temperature(self, temperature: int) -> bool:
        """Sets the extruder temperature using TCP M-code ~M104."""
        action = f"SET EXTRUDER TEMPERATURE to {temperature}°C"
        if not 0 <= temperature <= 300:  # Assuming max 300, adjust if different
            error_msg = f"Invalid extruder temperature: {temperature}. Must be between 0 and 300."
            _LOGGER.error(error_msg)
            # No TCP command sent, but we can still notify for this validation error
            await self._create_service_error_notification(action, error_msg)
            return False
        command = f"~M104 S{temperature}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def set_bed_temperature(self, temperature: int) -> bool:
        """Sets the bed temperature using TCP M-code ~M140."""
        action = f"SET BED TEMPERATURE to {temperature}°C"
        if not 0 <= temperature <= 120:  # Assuming max 120, adjust if different
            error_msg = f"Invalid bed temperature: {temperature}. Must be between 0 and 120."
            _LOGGER.error(error_msg)
            await self._create_service_error_notification(action, error_msg)
            return False
        command = f"~M140 S{temperature}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def set_fan_speed(self, speed: int) -> bool:
        """Sets the fan speed using TCP M-code ~M106."""
        action = f"SET FAN SPEED to {speed}"
        if not 0 <= speed <= 255:
            error_msg = f"Invalid fan speed: {speed}. Must be between 0 and 255."
            _LOGGER.error(error_msg)
            await self._create_service_error_notification(action, error_msg)
            return False
        command = f"~M106 S{speed}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def turn_fan_off(self) -> bool:
        """Turns the fan off using TCP M-code ~M107."""
        action = "TURN FAN OFF"
        success, response_or_error = await self._send_tcp_command("~M107\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def move_axis(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        feedrate: Optional[int] = None,
    ) -> bool:
        """Moves printer axes using TCP M-code G0 (or G1, G0 is usually rapid, G1 for controlled feed)."""
        command_parts = ["~G0"]
        action_log_parts = []

        if x is not None:
            command_parts.append(f"X{x}")
            action_log_parts.append(f"X to {x}")
        if y is not None:
            command_parts.append(f"Y{y}")
            action_log_parts.append(f"Y to {y}")
        if z is not None:
            command_parts.append(f"Z{z}")
            action_log_parts.append(f"Z to {z}")

        action = f"MOVE AXIS ({', '.join(action_log_parts)})"

        if not action_log_parts:
            error_msg = "Move axis command called without specifying an axis (X, Y, or Z)."
            _LOGGER.error(error_msg)
            await self._create_service_error_notification(action if action_log_parts else "MOVE AXIS (no axis specified)", error_msg)
            return False

        if feedrate is not None:
            if feedrate > 0:
                command_parts.append(f"F{feedrate}")
                action_log_parts.append(f"at F{feedrate}") # For logging only, action string already formed
            else:
                _LOGGER.warning(
                    f"Invalid feedrate for move axis: {feedrate}. Must be positive. Sending command without feedrate."
                )

        # Reconstruct action for more detail if feedrate was added to command_parts but not action_log_parts initially
        # This is a bit redundant if action_log_parts is kept in sync, but safe.
        current_action_detail = ', '.join(action_log_parts)
        action = f"MOVE AXIS ({current_action_detail})"


        command = " ".join(command_parts) + "\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def move_relative(self, x: Optional[float]=None, y: Optional[float]=None, z: Optional[float]=None, feedrate: Optional[int]=None) -> bool:
        """Moves printer axes by a relative amount using G91 then G0, then restores G90."""
        base_action = "MOVE RELATIVE"
        action_details_log = []
        if x is not None: action_details_log.append(f"X:{x}")
        if y is not None: action_details_log.append(f"Y:{y}")
        if z is not None: action_details_log.append(f"Z:{z}")
        if feedrate is not None and feedrate > 0 : action_details_log.append(f"F:{feedrate}")
        full_action_description = f"{base_action} ({', '.join(action_details_log)})" if action_details_log else base_action

        _LOGGER.info(f"Attempting: {full_action_description}")

        g91_action = "SET RELATIVE POSITIONING (G91) for relative move"
        success_g91, resp_g91 = await self._send_tcp_command("~G91\r\n", g91_action)
        if not success_g91:
            _LOGGER.error(f"{g91_action} failed. Aborting relative move. Details: {resp_g91}")
            # Attempt to restore absolute positioning
            g90_restore_action_fail = "RESTORE ABSOLUTE POSITIONING (G90) after G91 fail for relative move"
            await self._send_tcp_command("~G90\r\n", g90_restore_action_fail) # Fire and forget, main error is G91
            await self._create_service_error_notification(full_action_description, f"G91 failed: {resp_g91}")
            return False

        move_attempted = False
        success_move = True  # Default to true if no move is actually made

        resp_move = "No move executed." # Default response if no move parts

        move_command_parts = ["~G0"]
        # Use action_details_log which was already constructed for the full_action_description
        # Need to filter out non-axis/feedrate parts if any were added for logging only.
        # For G0, only X, Y, Z, F are relevant.
        if x is not None: move_command_parts.append(f"X{x}")
        if y is not None: move_command_parts.append(f"Y{y}")
        if z is not None: move_command_parts.append(f"Z{z}")
        if feedrate is not None and feedrate > 0:
            move_command_parts.append(f"F{feedrate}")
        elif feedrate is not None: # feedrate is 0 or negative
             _LOGGER.warning(f"Invalid feedrate for relative move: {feedrate}. Must be positive. Ignoring feedrate in G0 command.")

        if len(move_command_parts) > 1:  # More than just "~G0"
            move_attempted = True
            g0_command = " ".join(move_command_parts) + "\r\n"
            # Use a more specific action for the G0 part of the relative move for clarity in logs/notifications if it fails
            g0_action_description = f"EXECUTE RELATIVE MOVE ({', '.join(action_details_log)})"
            success_move, resp_move = await self._send_tcp_command(g0_command, g0_action_description)
            if not success_move:
                _LOGGER.error(f"Relative G0 move command ({g0_command.strip()}) failed. Details: {resp_move}")
                # Notification will be created before restoring G90
                await self._create_service_error_notification(full_action_description, f"G0 move failed: {resp_move}")
        else:
            _LOGGER.warning("No axis offset provided for relative move. Skipping G0 command.")
            # No move was attempted, success_move remains True

        g90_restore_action = "RESTORE ABSOLUTE POSITIONING (G90) after relative move"
        success_g90, resp_g90 = await self._send_tcp_command("~G90\r\n", g90_restore_action)
        if not success_g90:
            _LOGGER.error(f"Critical: {g90_restore_action} failed. Details: {resp_g90}")
            # This is a more critical failure for overall printer state.
            # If the move itself also failed, the earlier notification for that is already sent.
            # If the move succeeded but G90 failed, this is the primary error for this operation.
            if success_move: # Only create a new notification if the move part didn't already fail and notify
                await self._create_service_error_notification(full_action_description, f"G90 restore failed: {resp_g90}")
            return False # G90 is critical

        # Overall success depends on G91, the G0 move (if attempted), and G90 restoration
        final_success = success_g91 and success_move and success_g90
        if not final_success and success_move and success_g91 : # G90 was the point of failure, already notified
             pass # Avoid double notification if G90 was the sole failure point and already handled
        elif not final_success and not (success_g91 and success_move): # G91 or G0 failed, notification already sent
             pass

        return final_success

    async def delete_file(self, file_path: str) -> bool:
        """Deletes a file from the printer's storage using M30."""
        command_file_path = file_path
        if not (file_path.startswith(TCP_CMD_PRINT_FILE_PREFIX_ROOT) or \
                file_path.startswith(TCP_CMD_PRINT_FILE_PREFIX_USER) or \
                file_path.startswith("/data/")):
            # Default to user prefix if not specified and not an absolute-like /data/ path
            command_file_path = f"{TCP_CMD_PRINT_FILE_PREFIX_USER}{file_path}"
        elif file_path.startswith("/data/"): # This case implies "0:/data/..." for M30 if that's how printer expects it
            # The original code prepends "0:" for /data/ paths. Assuming this is correct.
            command_file_path = f"0:{file_path}"
            # If it should be just /data/..., then this needs adjustment.
            # For now, sticking to original logic for path construction.

        action = f"DELETE FILE ({command_file_path})" # Use the processed path for action description
        command = f"~M30 {command_file_path}\r\n"

        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def disable_steppers(self) -> bool:
        """Disables all stepper motors on the printer (M18)."""
        action = "DISABLE STEPPER MOTORS"
        success, response_or_error = await self._send_tcp_command("~M18\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def enable_steppers(self) -> bool:
        """Enables all stepper motors on the printer (M17)."""
        action = "ENABLE STEPPER MOTORS"
        success, response_or_error = await self._send_tcp_command("~M17\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def set_speed_percentage(self, percentage: int) -> bool:
        """Sets the printer's speed factor override (M220 S<percentage>)."""
        action = f"SET SPEED PERCENTAGE to {percentage}%"
        # Basic validation
        if not 10 <= percentage <= 500: # Example range, adjust if printer has different limits
            error_msg = f"Invalid speed percentage: {percentage}. Must be between 10 and 500 (example)."
            _LOGGER.error(error_msg)
            await self._create_service_error_notification(action, error_msg)
            return False
        command = f"~M220 S{percentage}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def set_flow_percentage(self, percentage: int) -> bool:
        """Sets the printer's flow rate percentage using M221."""
        action = f"SET FLOW PERCENTAGE to {percentage}%"
        if not 50 <= percentage <= 200: # Example range
            error_msg = f"Invalid flow percentage: {percentage}. Must be between 50 and 200."
            _LOGGER.error(error_msg)
            await self._create_service_error_notification(action, error_msg)
            return False
        command = f"~M221 S{percentage}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def home_axes(self, axes: Optional[List[str]] = None) -> bool:
        """Homes specified axes or all axes if None using G28."""
        command_str = "~G28"
        action_detail_str = "ALL AXES"
        if axes and isinstance(axes, list) and len(axes) > 0:
            valid_axes_to_home = "".join(ax.upper() for ax in axes if ax.upper() in ["X", "Y", "Z"])
            if valid_axes_to_home:
                command_str += f" {valid_axes_to_home}"
                action_detail_str = f"{valid_axes_to_home} AXES"

        command_str += "\r\n"
        action = f"HOME {action_detail_str}"

        success, response_or_error = await self._send_tcp_command(command_str, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def filament_change(self) -> bool:
        """Initiates filament change procedure using M600."""
        action = "FILAMENT CHANGE (M600)"
        success, response_or_error = await self._send_tcp_command("~M600\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def emergency_stop(self) -> bool:
        """Sends emergency stop command M112."""
        action = "EMERGENCY STOP (M112)"
        # M112 might not send an 'ok', printer might just halt or restart.
        # Using default response_terminator="ok\r\n" might lead to false negatives.
        # However, changing it might suppress actual errors if 'ok' is sometimes sent.
        # For now, stick to default and let notification handle timeout or error response.
        success, response_or_error = await self._send_tcp_command("~M112\r\n", action, response_terminator="ok\r\n") # Explicitly state default for clarity
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def list_files(self) -> bool: # Should this create notification on failure? Usually a background action.
        """Lists files on the printer's storage using M20.
        This is typically used for internal state, not direct user interaction leading to immediate notification.
        If it becomes a user-facing service that can fail, notifications might be added.
        For now, matching existing behavior of not creating a visible HA notification for this internal action.
        """
        command = "~M20\r\n"
        action = "LIST FILES (M20)" # Internal action description
        _LOGGER.info(f"Attempting to {action}") # Keep this log
        # Note: _send_tcp_command itself logs success/failure.
        # If this were a user-invoked service expecting feedback, notification would be here.
        success, response = await self._send_tcp_command(command, action) # response is str or bytes
        if success:
            response_str = response.decode(errors='replace') if isinstance(response, bytes) else response
            _LOGGER.info(f"M20 response snippet: {response_str[:200]}...")
        # No notification for this internal-like function's failure by design here.
        return success

    async def report_firmware_capabilities(self) -> bool: # Similar to list_files
        """Reports firmware capabilities using M115.
        Also typically an internal information gathering step.
        """
        command = "~M115\r\n"
        action = "REPORT FIRMWARE CAPABILITIES (M115)" # Internal action description
        _LOGGER.info(f"Attempting to {action}")
        success, response = await self._send_tcp_command(command, action) # response is str or bytes
        if success:
            response_str = response.decode(errors='replace') if isinstance(response, bytes) else response
            _LOGGER.info(f"M115 response snippet: {response_str[:200]}...")
        return success

    async def play_beep(self, pitch: int, duration: int) -> bool:
        """Plays a beep sound using M300."""
        action = f"PLAY BEEP (Pitch: {pitch}, Duration: {duration})"
        # Basic input validation (optional, but good practice)
        if not (0 <= pitch <= 10000):  # Example range
            _LOGGER.warning(f"Pitch {pitch} Hz is out of typical range (0-10000 Hz) for '{action}'. Proceeding.")
        if not (0 <= duration <= 10000):  # Example range
            _LOGGER.warning(f"Duration {duration} ms is out of typical range (0-10000 ms) for '{action}'. Proceeding.")

        command = f"~M300 S{pitch} P{duration}\r\n"
        success, response_or_error = await self._send_tcp_command(command, action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def start_bed_leveling(self) -> bool:
        """Starts the bed leveling process using G29."""
        action = "START BED LEVELING (G29)"
        success, response_or_error = await self._send_tcp_command("~G29\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def save_settings_to_eeprom(self) -> bool:
        """Saves settings to EEPROM using M500."""
        action = "SAVE SETTINGS TO EEPROM (M500)"
        success, response_or_error = await self._send_tcp_command("~M500\r\n", action)
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success

    async def read_settings_from_eeprom(self) -> bool: # Similar to list_files
        """Reads settings from EEPROM using M501.
        Primarily for internal/diagnostic use.
        """
        command = "~M501\r\n"
        action = "READ SETTINGS FROM EEPROM (M501)" # Internal action description
        _LOGGER.info(f"Attempting to {action}")
        success, response = await self._send_tcp_command(command, action) # response is str or bytes
        if success:
            response_str = response.decode(errors='replace') if isinstance(response, bytes) else response
            _LOGGER.info(f"M501 response snippet: {response_str[:200]}...")
        return success

    async def restore_factory_settings(self) -> bool:
        """Restores factory settings using M502."""
        action = "RESTORE FACTORY SETTINGS (M502)"
        # M502 might have non-standard response or cause a restart.
        success, response_or_error = await self._send_tcp_command("~M502\r\n", action, response_terminator="ok\r\n")
        if not success:
            await self._create_service_error_notification(action, response_or_error)
        return success
