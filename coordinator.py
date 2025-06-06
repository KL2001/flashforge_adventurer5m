"""
Coordinator for the Flashforge Adventurer 5M PRO integration.
"""

from __future__ import annotations

import asyncio
import logging
import re # For parsing M114
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
)
from .flashforge_tcp import FlashforgeTCPClient

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
        self.data: dict[str, Any] = {} # This is first populated by the base class after _async_update_data

    async def _fetch_printable_files_list(self) -> list[str]:
        """Fetches the list of printable files using TCP M-code ~M661."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M661\r\n"
        action = "FETCH PRINTABLE FILES"
        files_list = []

        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command, response_terminator="ok\r\n")

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
                    payload_str = response[len(prefix_to_strip):]
                elif response.startswith("ok\r\n"):
                     payload_str = response[len("ok\r\n"):]

                _LOGGER.debug(f"Payload for M661 parsing after stripping initial 'ok': '{payload_str[:200]}...'") # Log start of payload

                # Separator after UTF-8 decoding with errors='ignore' (drops £)
                separator = "::\x00\x00\x00"
                parts = payload_str.split(separator)
                _LOGGER.debug(f"Splitting M661 payload with separator '{separator}'. Number of parts: {len(parts)}. First few parts if any: {parts[:5]}")

                for part in parts:
                    path_start_index = part.find("//data/")
                    _LOGGER.debug(f"M661 parsing - Original part segment: '{part}', Found '//data/' at index {path_start_index}")
                    if path_start_index != -1:
                        file_path = part[path_start_index:]
                        _LOGGER.debug(f"M661 parsing - Extracted file_path: '{file_path}'")
                        if file_path:
                            cleaned_path = "".join(filter(lambda x: x.isprintable(), file_path)).strip()
                            _LOGGER.debug(f"M661 parsing - Cleaned path: '{cleaned_path}', Ends with .gcode/.gx: {cleaned_path.endswith(('.gcode', '.gx'))}")
                            if cleaned_path and cleaned_path.endswith((".gcode", ".gx")):
                                files_list.append(cleaned_path)

                if files_list:
                    _LOGGER.info(f"Successfully parsed file list: {files_list}")
                else:
                    _LOGGER.warning(f"File list parsing resulted in empty list. Raw payload part after prefix: {payload_str[:200]}...")


            elif success:
                 _LOGGER.warning(f"{action} command sent, but no valid file list data in response: {response}")
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")

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
        conversion_factor = 2.54 # Printer M114 reports in tenths-of-an-inch

        _LOGGER.debug(f"Attempting to {action} using TCP command: {command.strip()}")

        try:
            success, response = await tcp_client.send_command(command, response_terminator="ok\r\n")
            if success and response:
                _LOGGER.debug(f"Raw response for {action}: {response}")

                match_x = re.search(r"X:([+-]?\d+\.?\d*)", response)
                match_y = re.search(r"Y:([+-]?\d+\.?\d*)", response)
                match_z = re.search(r"Z:([+-]?\d+\.?\d*)", response)

                if match_x:
                    coordinates['x'] = float(match_x.group(1)) * conversion_factor
                if match_y:
                    coordinates['y'] = float(match_y.group(1)) * conversion_factor
                if match_z:
                    coordinates['z'] = float(match_z.group(1)) * conversion_factor

                if 'x' in coordinates and 'y' in coordinates and 'z' in coordinates:
                    _LOGGER.debug(f"Successfully parsed and converted coordinates: {coordinates}")
                    return coordinates
                else:
                    _LOGGER.warning(f"Could not parse all X,Y,Z coordinates from M114 response: {response}. Parsed: {coordinates}")
                    return None
            else:
                _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}")
                return None
        except Exception as e:
            _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True)
            return None
        return None # Should not be reached, but linters might prefer it.

    async def _async_update_data(self): # This is the method called by DataUpdateCoordinator
        """Fetch data from the printer via HTTP API for sensors, and TCP for files/coords."""
        return await self._fetch_data()

    async def _fetch_data(self):
        """Fetch data from HTTP /detail endpoint and, on subsequent updates, files/coords via TCP."""
        current_data = {} # Data for this specific fetch run

        # Step 1: Fetch main status data via HTTP
        url = f"http://{self.host}:{DEFAULT_PORT}{ENDPOINT_DETAIL}"
        payload = {"serialNumber": self.serial_number, "checkCode": self.check_code}
        retries = 0
        delay = RETRY_DELAY
        http_fetch_successful = False

        while retries < MAX_RETRIES:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=TIMEOUT_API_CALL) as resp:
                        resp.raise_for_status()
                        api_response_data = await resp.json(content_type=None)
                        if self._validate_response(api_response_data):
                            self.connection_state = CONNECTION_STATE_CONNECTED
                            current_data = api_response_data
                            http_fetch_successful = True
                            _LOGGER.debug("HTTP /detail data fetched and validated successfully.")
                            break
                        else:
                            _LOGGER.warning("Invalid response structure from /detail: %s", api_response_data)
                            self.connection_state = CONNECTION_STATE_DISCONNECTED
                            current_data = {}
                            http_fetch_successful = False
                            break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning("Fetch attempt %d for /detail failed: %s", retries + 1, e)
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
        current_data['printable_files'] = self.data.get('printable_files', []) if self.data else []
        current_data['x_position'] = self.data.get('x_position') if self.data else None
        current_data['y_position'] = self.data.get('y_position') if self.data else None
        current_data['z_position'] = self.data.get('z_position') if self.data else None

        # Step 2: Fetch TCP data only if HTTP was successful and it's not the first run for the coordinator
        # self.data will be empty on the very first run initiated by async_refresh in __init__
        if http_fetch_successful and self.data:
            _LOGGER.debug("Attempting to fetch TCP data (files and coordinates) on a subsequent update.")
            try:
                files_list = await self._fetch_printable_files_list()
                current_data['printable_files'] = files_list
            except Exception as e:
                _LOGGER.error(f"Failed to fetch printable files list during update: {e}", exc_info=True)
                # Keep previous list if current fetch fails
                current_data['printable_files'] = self.data.get('printable_files', [])

            try:
                coords = await self._fetch_coordinates()
                if coords:
                    current_data['x_position'] = coords.get('x')
                    current_data['y_position'] = coords.get('y')
                    current_data['z_position'] = coords.get('z')
                else: # Coords fetch failed or returned None, keep previous
                    current_data['x_position'] = self.data.get('x_position')
                    current_data['y_position'] = self.data.get('y_position')
                    current_data['z_position'] = self.data.get('z_position')
            except Exception as e:
                _LOGGER.error(f"Failed to fetch coordinates during update: {e}", exc_info=True)
                # Keep previous coords if current fetch fails
                current_data['x_position'] = self.data.get('x_position')
                current_data['y_position'] = self.data.get('y_position')
                current_data['z_position'] = self.data.get('z_position')
        elif http_fetch_successful and not self.data:
            _LOGGER.debug("Initial successful HTTP data fetch. Deferring TCP data (files and coords) for next update.")
            # Keys already initialized to empty/None above

        if not http_fetch_successful:
            _LOGGER.debug("HTTP data fetch failed, returning current_data which may be empty or partially filled with defaults.")
            # Ensure keys exist if current_data is {} due to total failure
            if not current_data:
                current_data = {
                    'printable_files': [],
                    'x_position': None, 'y_position': None, 'z_position': None
                }


        return current_data

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
        """Sends a command via HTTP POST, wrapped with auth details."""
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
                            return await resp.json(content_type=None)
                        return {"status": "success_http_200", "raw_response": response_text}
                    else:
                        _LOGGER.error(f"HTTP command to {endpoint} failed with status {resp.status}. Response: {response_text}")
                        return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Error sending HTTP command to {endpoint}: {e}", exc_info=True)
            return None
        return None

    async def pause_print(self):
        """Pauses the current print using TCP M-code ~M25."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M25\r\n"
        action = "PAUSE PRINT"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def resume_print(self):
        """Resumes the current print using TCP M-code ~M24."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M24\r\n"
        action = "RESUME PRINT"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def start_print(self, file_path: str):
        """Starts a new print using TCP M-code ~M23."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        # Ensure file_path does not start with / if "0:/user/" prefix is used,
        # or adjust prefix if file_path is absolute from a different root.
        # Assuming file_path is like "myprint.gcode" and should be under "0:/user/"
        if file_path.startswith("0:/user/"):
            command = f"~M23 {file_path}\r\n"
        elif file_path.startswith("/"): # If it's an absolute path starting with /
            command = f"~M23 0:{file_path}\r\n" # Assuming 0: is the drive/storage
        else: # Relative path
            command = f"~M23 0:/user/{file_path}\r\n"

        action = f"START PRINT ({file_path})"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def cancel_print(self):
        """Cancels the current print using TCP M-code ~M26."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M26\r\n"
        action = "CANCEL PRINT"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def toggle_light(self, on: bool):
        """Toggles the printer light ON or OFF using TCP M-code commands."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        if on: command = "~M146 r255 g255 b255 F0\r\n"; action = "ON"
        else: command = "~M146 r0 g0 b0 F0\r\n"; action = "OFF"
        _LOGGER.info(f"Attempting to turn light {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent light {action} TCP command. Printer response: '{response.strip()}'"); return True
            else: _LOGGER.error(f"Failed to send light {action} TCP command. Details: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during toggle_light TCP operation: {e}", exc_info=True); return False

    async def set_extruder_temperature(self, temperature: int):
        """Sets the extruder temperature using TCP M-code ~M104."""
        if not 0 <= temperature <= 300:
            _LOGGER.error(f"Invalid extruder temperature: {temperature}. Must be between 0 and 300.")
            return False
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = f"~M104 S{temperature}\r\n"
        action = f"SET EXTRUDER TEMPERATURE to {temperature}°C"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def set_bed_temperature(self, temperature: int):
        """Sets the bed temperature using TCP M-code ~M140."""
        if not 0 <= temperature <= 120:
            _LOGGER.error(f"Invalid bed temperature: {temperature}. Must be between 0 and 120.")
            return False
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = f"~M140 S{temperature}\r\n"
        action = f"SET BED TEMPERATURE to {temperature}°C"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def set_fan_speed(self, speed: int):
        """Sets the fan speed using TCP M-code ~M106."""
        if not 0 <= speed <= 255:
            _LOGGER.error(f"Invalid fan speed: {speed}. Must be between 0 and 255.")
            return False
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = f"~M106 S{speed}\r\n"
        action = f"SET FAN SPEED to {speed}"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def turn_fan_off(self):
        """Turns the fan off using TCP M-code ~M107."""
        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        command = "~M107\r\n"
        action = "TURN FAN OFF"
        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False

    async def move_axis(self, x: Optional[float] = None, y: Optional[float] = None, z: Optional[float] = None, feedrate: Optional[int] = None):
        """Moves printer axes using TCP M-code ~G0."""
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

        if not action_parts: # No axis specified
            _LOGGER.error("Move axis command called without specifying an axis (X, Y, or Z).")
            return False

        if feedrate is not None:
            if feedrate > 0:
                command_parts.append(f"F{feedrate}")
                action_parts.append(f"at F{feedrate}")
            else:
                _LOGGER.warning(f"Invalid feedrate for move axis: {feedrate}. Must be positive. Sending command without feedrate.")

        command = " ".join(command_parts) + "\r\n"
        action = f"MOVE AXIS ({', '.join(action_parts)})"

        _LOGGER.info(f"Attempting to {action} using TCP command: {command.strip()}")

        tcp_client = FlashforgeTCPClient(self.host, DEFAULT_MCODE_PORT)
        try:
            success, response = await tcp_client.send_command(command)
            if success: _LOGGER.info(f"Successfully sent {action} command. Response: {response}"); return True
            else: _LOGGER.error(f"Failed to send {action} command. Response/Error: {response}"); return False
        except Exception as e: _LOGGER.error(f"Exception during {action} TCP command: {e}", exc_info=True); return False
