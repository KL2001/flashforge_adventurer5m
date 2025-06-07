"""
Coordinator for the Flashforge Adventurer 5M PRO integration.
"""

from __future__ import annotations

import asyncio
import logging
import re  # For parsing M114
from datetime import timedelta
from typing import Any, Optional

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
    TCP_CMD_PRINT_FILE_PREFIX_USER,
    TCP_CMD_PRINT_FILE_PREFIX_ROOT,
    API_ATTR_DETAIL,
    # Import new Endstop constants
    API_ATTR_X_ENDSTOP_STATUS,
    API_ATTR_Y_ENDSTOP_STATUS,
    API_ATTR_Z_ENDSTOP_STATUS,
    API_ATTR_FILAMENT_ENDSTOP_STATUS,
    API_ATTR_BED_LEVELING_STATUS, # Added
    # API_ATTR_FIRMWARE_VERSION, # No longer needed for M115 test
)
from .flashforge_tcp import FlashforgeTCPClient

_LOGGER = logging.getLogger(__name__)


class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass,
        host: str,
        serial_number: str,
        check_code: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ):
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
        self.data: dict[str, Any] = (
            {}
        )  # This is first populated by the base class after _async_update_data

    async def _fetch_bed_leveling_status(self) -> dict:
        """Fetches and parses bed leveling status from M420 command."""
        status_data = {API_ATTR_BED_LEVELING_STATUS: None}
        command = "~M420 S0\r\n"
        action = "FETCH BED LEVELING STATUS (M420 S0)"

        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

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

        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

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

        return endstop_data

    async def _fetch_printable_files_list(self) -> list[str]:
        """
        Fetches the list of printable files using TCP M-code ~M661.
        Expected M661 response format (observed):
        CMD M661 Received.\r\nok\r\n  (optional prefix, may vary or be absent)
        DD\x00\x00\x00\x1b::\xa3\xa3\x00\x00\x00/data/user/filament_config/ASA.txt::\x00\x00\x00/data/user/filament_config/PETG.txt...
        (The "DD..." part might be specific to some firmware/printer responses, separator seems to be "::\x00\x00\x00")
        The actual file paths start with /data/
        """
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M661\r\n"
        action = "FETCH PRINTABLE FILES"
        files_list = []

        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(
                command, response_terminator="ok\r\n"
            )

            if success and response:
                _LOGGER.debug(f"Raw response for {action}: {response}")

                payload_str = response
                # Remove known prefixes like "CMD M661 Received.\r\nok\r\n"
                # The client might have already stripped some part of it if "ok\r\n" was found early.
                # A more robust way is to find where the actual data starts.
                # The Wireshark log showed "D\xaa\xaaD\x00\x00\x00\x1b::\xa3\xa3\x00\x00\x00//data/..."
                # and the first part of the logged payload was "DD\x00\x00\x00\x1b::\xa3\xa3\x00\x00\x00//data/..."
                # This suggests the actual file data starts after the first "ok\r\n".
                # Let's assume `payload_str` contains the data after "ok\r\n".

                prefix_to_strip = "CMD M661 Received.\r\nok\r\n"
                if response.startswith(prefix_to_strip):
                    payload_str = response[len(prefix_to_strip) :]
                elif response.startswith("ok\r\n"):
                    payload_str = response[len("ok\r\n") :]

                _LOGGER.debug(
                    f"Payload for M661 parsing after stripping initial 'ok': '{payload_str[:200]}...'"
                )  # Log start of payload

                # Separator after UTF-8 decoding with errors='ignore' (drops £)
                separator = "::\x00\x00\x00"  # Per observation
                parts = payload_str.split(separator)
                _LOGGER.debug(
                    f"Splitting M661 payload with separator '{repr(separator)}'. Number of parts: {len(parts)}. First few parts if any: {parts[:5]}"
                )

                if len(parts) <= 1 and payload_str:
                    _LOGGER.warning(
                        "M661 parsing: Separator '%s' not found or produced no splits in non-empty payload: %s",
                        repr(separator),
                        payload_str[:100] + "...",
                    )

                for part in parts:
                    path_start_index = part.find("/data/")
                    if path_start_index != -1:
                        file_path = part[path_start_index:]
                        _LOGGER.debug(
                            f"M661 parsing - Extracted file_path candidate: '{file_path}'"
                        )
                        if file_path:
                            cleaned_path = "".join(
                                filter(lambda x: x.isprintable(), file_path)
                            ).strip()
                            _LOGGER.debug(
                                f"M661 parsing - Cleaned path: '{cleaned_path}', Starts with /data/ and ends with .gcode/.gx: {cleaned_path.startswith('/data/') and cleaned_path.endswith(('.gcode', '.gx'))}"
                            )
                            if cleaned_path.startswith(
                                "/data/"
                            ) and cleaned_path.endswith((".gcode", ".gx")):
                                files_list.append(cleaned_path)
                    else:
                        if (
                            part.strip()
                        ):  # Log only if part contains something other than whitespace
                            _LOGGER.debug(
                                "M661 parsing: '/data/' not found in part: '%s'",
                                part[:100] + "...",
                            )

                if files_list:
                    _LOGGER.info(f"Successfully parsed file list: {files_list}")
                else:
                    _LOGGER.warning(
                        "File list parsing resulted in empty list. This may be due to an unexpected response format, "
                        "no files on printer, or parsing issues. Raw payload sample after prefix: %s",
                        payload_str[:200] + "...",
                    )

            elif (
                success
            ):  # Command sent, but response might be empty or not what we expected
                _LOGGER.warning(
                    f"{action} command sent, but no valid file list data in response: '{response[:200]}...'"
                )
            else:
                _LOGGER.error(
                    f"Failed to send {action} command. Response/Error: {response}"
                )

            return files_list
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)
            return []

    async def _fetch_coordinates(self) -> Optional[dict[str, float]]:
        """Fetches and parses the printer's X,Y,Z coordinates using M-code ~M114."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M114\r\n"
        action = "FETCH COORDINATES"
        coordinates = {}
        # conversion_factor = 2.54 # Removed, assuming M114 reports in mm

        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(
                command, response_terminator="ok\r\n"
            )
            if success and response:
                _LOGGER.debug(f"Raw response for {action}: {response}")

                match_x = re.search(r"X:([+-]?\d+\.?\d*)", response)
                match_y = re.search(r"Y:([+-]?\d+\.?\d*)", response)
                match_z = re.search(r"Z:([+-]?\d+\.?\d*)", response)

                if match_x:
                    coordinates["x"] = float(match_x.group(1))
                if match_y:
                    coordinates["y"] = float(match_y.group(1))
                if match_z:
                    coordinates["z"] = float(match_z.group(1))

                if "x" in coordinates and "y" in coordinates and "z" in coordinates:
                    _LOGGER.debug(f"Successfully parsed coordinates: {coordinates}")
                    return coordinates
                else:
                    _LOGGER.warning(
                        f"Could not parse all X,Y,Z coordinates from M114 response: {response}. Parsed: {coordinates}"
                    )
                    return None
            else:
                _LOGGER.error(
                    f"Failed to send {action} command. Response/Error: {response}"
                )
                return None
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)
            return None
        return None  # Should not be reached, but linters might prefer it.

    async def _async_update_data(
        self,
    ):  # This is the method called by DataUpdateCoordinator
        """Fetch data from the printer via HTTP API for sensors, and TCP for files/coords."""
        return await self._fetch_data()

    async def _fetch_data(self):
        """Fetch data from HTTP /detail endpoint and, on subsequent updates, files/coords via TCP."""
        current_data = {}  # Data for this specific fetch run

        # Step 1: Fetch main status data via HTTP
        url = f"http://{self.host}:{DEFAULT_PORT}{ENDPOINT_DETAIL}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        retries = 0
        delay = RETRY_DELAY
        http_fetch_successful = False

        while retries < MAX_RETRIES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, json=payload, timeout=TIMEOUT_API_CALL
                    ) as resp:
                        resp.raise_for_status()
                        api_response_data = await resp.json(content_type=None)
                        if self._validate_response(api_response_data):
                            self.connection_state = CONNECTION_STATE_CONNECTED
                            current_data = api_response_data
                            http_fetch_successful = True
                            _LOGGER.debug(
                                "HTTP /detail data fetched and validated successfully."
                            )
                            break
                        else:
                            _LOGGER.warning(
                                "Invalid response structure from /detail: %s",
                                api_response_data,
                            )
                            self.connection_state = CONNECTION_STATE_DISCONNECTED
                            current_data = {}
                            http_fetch_successful = False
                            break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning(
                    "Fetch attempt %d for /detail failed: %s", retries + 1, e
                )
                retries += 1
                if retries < MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= BACKOFF_FACTOR
                else:
                    _LOGGER.error("Max retries exceeded for /detail fetching.")
                    self.connection_state = CONNECTION_STATE_DISCONNECTED
                    current_data = {}
                    http_fetch_successful = False
                    break

        # Initialize keys that will be populated by TCP calls or from previous data
        current_data["printable_files"] = (
            self.data.get("printable_files", []) if self.data else []
        )
        current_data["x_position"] = self.data.get("x_position") if self.data else None
        current_data["y_position"] = self.data.get("y_position") if self.data else None
        current_data["z_position"] = self.data.get("z_position") if self.data else None
        # Initialize endstop status keys
        current_data[API_ATTR_X_ENDSTOP_STATUS] = self.data.get(API_ATTR_X_ENDSTOP_STATUS)
        current_data[API_ATTR_Y_ENDSTOP_STATUS] = self.data.get(API_ATTR_Y_ENDSTOP_STATUS)
        current_data[API_ATTR_Z_ENDSTOP_STATUS] = self.data.get(API_ATTR_Z_ENDSTOP_STATUS)
        current_data[API_ATTR_FILAMENT_ENDSTOP_STATUS] = self.data.get(API_ATTR_FILAMENT_ENDSTOP_STATUS)
        # Initialize Bed Leveling status key
        current_data[API_ATTR_BED_LEVELING_STATUS] = self.data.get(API_ATTR_BED_LEVELING_STATUS)

        # Step 2: Fetch TCP data only if HTTP was successful and it's not the first run for the coordinator
        # self.data will be empty on the very first run initiated by async_refresh in __init__
        if http_fetch_successful and self.data:
            _LOGGER.debug(
                "Attempting to fetch TCP data (files, coordinates, endstops, bed leveling) on a subsequent update."
            )
            try:
                files_list = await self._fetch_printable_files_list()
                current_data["printable_files"] = files_list
            except Exception as e:
                _LOGGER.error(
                    f"Failed to fetch printable files list during update: {e}",
                    exc_info=True,
                )
                current_data["printable_files"] = self.data.get("printable_files", [])

            try:
                coords = await self._fetch_coordinates()
                if coords:
                    current_data["x_position"] = coords.get("x")
                    current_data["y_position"] = coords.get("y")
                    current_data["z_position"] = coords.get("z")
                else:
                    current_data["x_position"] = self.data.get("x_position")
                    current_data["y_position"] = self.data.get("y_position")
                    current_data["z_position"] = self.data.get("z_position")
            except Exception as e:
                _LOGGER.error(
                    f"Failed to fetch coordinates during update: {e}", exc_info=True
                )
                current_data["x_position"] = self.data.get("x_position")
                current_data["y_position"] = self.data.get("y_position")
                current_data["z_position"] = self.data.get("z_position")

            try:
                endstop_status = await self._fetch_endstop_status()
                current_data.update(endstop_status)
            except Exception as e:
                _LOGGER.error(f"Failed to fetch endstop status during update: {e}", exc_info=True)

            try:
                bed_level_status = await self._fetch_bed_leveling_status()
                current_data.update(bed_level_status)
            except Exception as e:
                _LOGGER.error(f"Failed to fetch bed leveling status during update: {e}", exc_info=True)

        elif http_fetch_successful and not self.data:
            _LOGGER.debug(
                "Initial successful HTTP data fetch. Deferring TCP data (files, coords, endstops, bed leveling) for next update."
            )
            # Keys already initialized to empty/None above

        if not http_fetch_successful:
            _LOGGER.debug(
                "HTTP data fetch failed, returning current_data which may be empty or partially filled with defaults."
            )
            # Ensure keys exist if current_data is {} due to total failure
            if not current_data:
                current_data = {
                    "printable_files": [],
                    "x_position": None,
                    "y_position": None,
                    "z_position": None,
                }

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
        extra_payload: Optional[Dict[str, Any]] = None, # Changed type hint
        expect_json_response: bool = True,
    ):
        """Sends a command via HTTP POST, wrapped with auth details."""
        url = f"http://{self.host}:{DEFAULT_PORT}{endpoint}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        if extra_payload:
            payload.update(extra_payload)

        _LOGGER.debug(f"Sending HTTP command to {url} with payload: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=COORDINATOR_COMMAND_TIMEOUT
                ) as resp:
                    response_text = await resp.text()
                    _LOGGER.debug(
                        f"HTTP command to {endpoint} status: {resp.status}, response: {response_text}"
                    )
                    if resp.status == 200:
                        if expect_json_response:
                            return await resp.json(content_type=None)
                        return {
                            "status": "success_http_200",
                            "raw_response": response_text,
                        }
                    else:
                        _LOGGER.error(
                            f"HTTP command to {endpoint} failed with status {resp.status}. Response: {response_text}"
                        )
                        return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(
                f"Error sending HTTP command to {endpoint}: {e}", exc_info=True
            )
            return None
        # return None # This line is unreachable due to the one above it.

    # Note: _send_tcp_command is defined below pause_print, ensure it's correctly placed or used.
    # For this temporary test, _test_m119_output instantiates its own client.

    async def pause_print(self):
        """Pauses the current print using TCP M-code ~M25."""
        return await self._send_tcp_command("~M25\r\n", "PAUSE PRINT")

    async def resume_print(self):
        """Resumes the current print using TCP M-code ~M24."""
        return await self._send_tcp_command("~M24\r\n", "RESUME PRINT")

    async def start_print(self, file_path: str):
        """Starts a new print using TCP M-code ~M23."""
        if file_path.startswith(TCP_CMD_PRINT_FILE_PREFIX_USER):
            command = f"~M23 {file_path}\r\n"
        elif file_path.startswith("/"):
            command = (
                f"~M23 {TCP_CMD_PRINT_FILE_PREFIX_ROOT}{file_path.lstrip('/')}\r\n"
            )
        else:
            command = f"~M23 {TCP_CMD_PRINT_FILE_PREFIX_USER}{file_path}\r\n"

        action = f"START PRINT ({file_path})"
        return await self._send_tcp_command(command, action)

    async def cancel_print(self):
        """Cancels the current print using TCP M-code ~M26."""
        return await self._send_tcp_command("~M26\r\n", "CANCEL PRINT")

    async def toggle_light(self, on: bool):
        """Toggles the printer light ON or OFF using TCP M-code commands."""
        if on:
            command = "~M146 r255 g255 b255 F0\r\n"
            action_desc = "TURN LIGHT ON"
        else:
            command = "~M146 r0 g0 b0 F0\r\n"
            action_desc = "TURN LIGHT OFF"
        return await self._send_tcp_command(command, action_desc)

    async def set_extruder_temperature(self, temperature: int):
        """Sets the extruder temperature using TCP M-code ~M104."""
        if not 0 <= temperature <= 300:  # Assuming max 300, adjust if different
            _LOGGER.error(
                f"Invalid extruder temperature: {temperature}. Must be between 0 and 300."
            )
            return False
        command = f"~M104 S{temperature}\r\n"
        action = f"SET EXTRUDER TEMPERATURE to {temperature}°C"
        return await self._send_tcp_command(command, action)

    async def set_bed_temperature(self, temperature: int):
        """Sets the bed temperature using TCP M-code ~M140."""
        if not 0 <= temperature <= 120:  # Assuming max 120, adjust if different
            _LOGGER.error(
                f"Invalid bed temperature: {temperature}. Must be between 0 and 120."
            )
            return False
        command = f"~M140 S{temperature}\r\n"
        action = f"SET BED TEMPERATURE to {temperature}°C"
        return await self._send_tcp_command(command, action)

    async def set_fan_speed(self, speed: int):
        """Sets the fan speed using TCP M-code ~M106."""
        if not 0 <= speed <= 255:
            _LOGGER.error(f"Invalid fan speed: {speed}. Must be between 0 and 255.")
            return False
        command = f"~M106 S{speed}\r\n"
        action = f"SET FAN SPEED to {speed}"
        return await self._send_tcp_command(command, action)

    async def turn_fan_off(self):
        """Turns the fan off using TCP M-code ~M107."""
        return await self._send_tcp_command("~M107\r\n", "TURN FAN OFF")

    async def move_axis(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        feedrate: Optional[int] = None,
    ):
        """Moves printer axes using TCP M-code G0 (or G1, G0 is usually rapid, G1 for controlled feed)."""
        # Using G0 for simplicity as per original. If feedrate control is critical, G1 might be better.
        command_parts = ["~G0"]
        action_parts = []

        if x is not None:
            command_parts.append(f"X{x}")
            action_parts.append(f"X to {x}")
        if y is not None:
            command_parts.append(f"Y{y}")
            action_parts.append(f"Y to {y}")
        if z is not None:
            command_parts.append(f"Z{z}")
            action_parts.append(f"Z to {z}")

        if not action_parts:  # No axis specified
            _LOGGER.error(
                "Move axis command called without specifying an axis (X, Y, or Z)."
            )
            return False

        if feedrate is not None:
            if feedrate > 0:
                command_parts.append(f"F{feedrate}")
                action_parts.append(f"at F{feedrate}")
            else:
                _LOGGER.warning(
                    f"Invalid feedrate for move axis: {feedrate}. Must be positive. Sending command without feedrate."
                )

        command = " ".join(command_parts) + "\r\n"
        action = f"MOVE AXIS ({', '.join(action_parts)})"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        try:
            success, response = await tcp_client.send_command(command)
            if success:
                _LOGGER.info(
                    f"Successfully sent {action} command. Response: {response}"
                )
                return True
            else:
                _LOGGER.error(
                    f"Failed to send {action} command. Response/Error: {response}"
                )
                return False
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)
            return False
