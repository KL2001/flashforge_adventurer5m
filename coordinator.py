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

import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Type aliases for better code readability
PrinterData = Dict[str, Any]  # Top-level printer response data
PrinterDetail = Dict[str, Any]  # 'detail' field from printer response

# Constants for API endpoints, timeouts, and retry settings
API_PORT = 8898
API_BASE_URL = "http://{host}:{port}"
API_ENDPOINTS = {
    "detail": "/detail",
    "pause": "/pause",
    "start": "/start",
    "cancel": "/cancel",
    "command": "/command"
}

# Timeout settings (in seconds)
FETCH_TIMEOUT = 15  # Longer timeout for fetching status data
COMMAND_TIMEOUT = 10  # Shorter timeout for sending commands

# Retry settings
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 1.5  # Base for exponential backoff calculation
RETRY_INITIAL_DELAY = 2  # Initial delay before first retry (seconds)

# Default scan interval (in seconds) for polling the printer
DEFAULT_SCAN_INTERVAL = 30

# Connection state constants
CONNECTION_STATE_UNKNOWN = "unknown"
CONNECTION_STATE_CONNECTED = "connected"
CONNECTION_STATE_DISCONNECTED = "disconnected"
CONNECTION_STATE_AUTHENTICATING = "authenticating"

# Required fields in response for validation
REQUIRED_TOP_LEVEL_FIELDS = ["code", "message", "detail"]
REQUIRED_DETAIL_FIELDS = ["status", "ipAddr", "firmwareVersion"]  # Minimum required fields

class PrinterConnectionError(Exception):
    """Exception raised for printer connection errors."""
    pass

class PrinterAuthenticationError(Exception):
    """Exception raised for authentication failures."""
    pass

class PrinterResponseValidationError(Exception):
    """Exception raised for invalid or unexpected responses."""
    pass

class PrinterCommandError(Exception):
    """Exception raised for command execution failures."""
    pass

class FlashforgeDataUpdateCoordinator(DataUpdateCoordinator[PrinterData]):
    """
    Data Coordinator for the Flashforge Adventurer 5M Pro printer.
    
    This coordinator handles communication with the printer API, fetching status data
    and sending commands. It ensures data is updated on a regular interval and
    shared between all sensors and entities.
    
    Expected JSON structure from printer API:
    {
        "code": int,          # Status code (0 for success)
        "message": str,       # Status message
        "detail": {
            # Printer information
            "status": str,                # Current printer status like "IDLE", "PRINTING", etc.
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
            
            # Temperature information
            "chamberTemp": float,         # Current chamber temperature (°C)
            "chamberTargetTemp": float,   # Target chamber temperature (°C)
            "leftTemp": float,            # Left nozzle temperature (°C)
            "leftTargetTemp": float,      # Target left nozzle temperature (°C)
            "rightTemp": float,           # Right nozzle temperature (°C)
            "rightTargetTemp": float,     # Target right nozzle temperature (°C)
            "platTemp": float,            # Platform/bed temperature (°C)
            "platTargetTemp": float,      # Target platform temperature (°C)
            
            # Print job information
            "printDuration": int,         # Current print duration in seconds
            "printFileName": str,         # Name of the currently printing file
            "printFileThumbUrl": str,     # URL to thumbnail of the printing file
            "printLayer": int,            # Current print layer
            "printProgress": float,       # Print progress (0.0 to 1.0)
            "estimatedTime": int,         # Estimated total print time in seconds
            "currentPrintSpeed": int,     # Current print speed percentage
            "printSpeedAdjust": int,      # Print speed adjustment percentage
            "targetPrintLayer": int,      # Total number of layers in the print
            
            # Filament information
            "cumulativeFilament": float,  # Total filament used historically (m)
            "cumulativePrintTime": int,   # Total print time historically (min)
            "fillAmount": float,          # Current fill amount
            "leftFilamentType": str,      # Type of filament in left extruder
            "rightFilamentType": str,     # Type of filament in right extruder
            "estimatedLeftLen": float,    # Estimated remaining left filament (mm)
            "estimatedLeftWeight": float, # Estimated remaining left filament weight (g)
            "estimatedRightLen": float,   # Estimated remaining right filament (mm)
            "estimatedRightWeight": float,# Estimated remaining right filament weight (g)
            
            # Fan information
            "chamberFanSpeed": float,     # Chamber fan speed
            "coolingFanSpeed": float,     # Cooling fan speed
            "externalFanStatus": str,     # External fan status
            "internalFanStatus": str,     # Internal fan status
            
            # Miscellaneous
            "tvoc": int,                  # Total Volatile Organic Compounds reading
            "cameraStreamUrl": str,       # URL for the camera stream
            "remainingDiskSpace": float,  # Remaining disk space in GB
            "zAxisCompensation": float,   # Z-axis compensation value
        }
    }
    """

    def __init__(self, hass: HomeAssistant, host: str, serial_number: str,
                 check_code: str, scan_interval: int = DEFAULT_SCAN_INTERVAL) -> None:
        """
        Initialize the Flashforge data coordinator.

        Args:
            hass: Home Assistant instance used for async tasks and services
            host: Printer's IP address or hostname (without http:// prefix)
            serial_number: Printer's serial number (used for authentication)
            check_code: Printer's check code (used for authentication)
            scan_interval: How often (in seconds) to poll the printer for updates

        The serial_number and check_code are required for authentication with the 
        printer's API. These can typically be found in the printer's information 
        screen or through the Flashforge mobile app.
        """
        self.hass = hass
        self.host = host
        self.serial_number = serial_number
        self.check_code = check_code
        
        # Error tracking
        self._error_count = 0
        self._consecutive_auth_errors = 0
        self._last_successful_update = None
        self._connection_state = CONNECTION_STATE_UNKNOWN
        self._last_errors = []  # Store last few error messages
        self._max_error_history = 10
        
        # Command history tracking
        self._command_history = []
        self._max_command_history = 20
        
        super().__init__(
            hass,
            _LOGGER,
            name="flashforge_data_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _fetch_data(self) -> PrinterData:
        """
        Perform the POST request to the printer API and return the parsed JSON response.
        
        This method implements retry logic with exponential backoff for transient errors,
        tracks connection state, and validates the response structure.

        Returns:
            A dictionary containing the printer's status data with the structure 
            documented in the class docstring.

        Raises:
            PrinterConnectionError: If the printer cannot be reached after retries
            PrinterAuthenticationError: If authentication fails
            PrinterResponseValidationError: If the response fails validation
            Exception: Other unexpected errors

        Note:
            All exceptions are caught in _async_update_data and converted to 
            appropriate UpdateFailed exceptions to maintain coordinator functionality.
        """
        url = f"{API_BASE_URL.format(host=self.host, port=API_PORT)}{API_ENDPOINTS['detail']}"
        payload = {
            "serialNumber": self.serial_number,
            "checkCode": self.check_code
        }

        _LOGGER.debug("Requesting printer data from %s", url)
        
        # Set initial state to authenticating
        self._connection_state = CONNECTION_STATE_AUTHENTICATING
        
        for retry_attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # Calculate backoff delay if this is a retry
                if retry_attempt > 0:
                    backoff_delay = RETRY_INITIAL_DELAY * (RETRY_DELAY_BASE ** (retry_attempt - 1))
                    _LOGGER.debug("Retry attempt %d of %d after %.1f seconds", 
                                 retry_attempt, MAX_RETRY_ATTEMPTS, backoff_delay)
                    await asyncio.sleep(backoff_delay)
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=FETCH_TIMEOUT) as resp:
                        # Handle authentication errors
                        if resp.status == 401 or resp.status == 403:
                            self._consecutive_auth_errors += 1
                            self._connection_state = CONNECTION_STATE_DISCONNECTED
                            self._add_error(f"Authentication failed with status {resp.status}")
                            raise PrinterAuthenticationError(
                                f"Authentication failed with status {resp.status}")
                            
                        # Handle other HTTP errors    
                        if resp.status != 200:
                            self._add_error(f"HTTP error {resp.status}")
                            resp.raise_for_status()  # Will raise an exception
                            
                        text_data = await resp.text()
                        
                        try:
                            data = json.loads(text_data)
                        except json.JSONDecodeError as e:
                            self._add_error(f"JSON decode error: {e}")
                            _LOGGER.error("JSON decode error: %s", e)
                            _LOGGER.debug("Response text: %s", text_data)
                            raise PrinterResponseValidationError(f"Invalid JSON response: {e}")
                
                # Validate the response structure
                validation_error = self._validate_response(data)
                if validation_error:
                    self._add_error(f"Response validation error: {validation_error}")
                    raise PrinterResponseValidationError(validation_error)
                
                # Reset error counters on successful fetch
                self._error_count = 0
                self._consecutive_auth_errors = 0
                self._connection_state = CONNECTION_STATE_CONNECTED
                self._last_successful_update = datetime.now()
                
                _LOGGER.debug("Successfully fetched printer data")
                return data
                
            except asyncio.TimeoutError:
                self._error_count += 1
                self._add_error("Request timed out")
                _LOGGER.warning("Request timed out (attempt %d of %d)", 
                               retry_attempt + 1, MAX_RETRY_ATTEMPTS)
                # Continue to next retry
                
            except aiohttp.ClientError as e:
                self._error_count += 1
                self._connection_state = CONNECTION_STATE_DISCONNECTED
                self._add_error(f"Connection error: {str(e)}")
                _LOGGER.error("HTTP request failed (attempt %d of %d): %s", 
                             retry_attempt + 1, MAX_RETRY_ATTEMPTS, e)
                # Continue to next retry
                
            except (PrinterAuthenticationError, PrinterResponseValidationError) as e:
                # Don't retry auth or validation errors
                raise
                
            except Exception as e:
                self._error_count += 1
                self._add_error(f"Unexpected error: {str(e)}")
                _LOGGER.exception("Unexpected error during data fetch (attempt %d of %d): %s", 
                                 retry_attempt + 1, MAX_RETRY_ATTEMPTS, e)
                # Continue to next retry
        
        # If we get here, all retries have failed
        self._connection_state = CONNECTION_STATE_DISCONNECTED
        raise PrinterConnectionError(f"Failed to connect to printer at {self.host} after {MAX_RETRY_ATTEMPTS} attempts")
    
    def _validate_response(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Validate the response structure from the printer API.
        
        Args:
            data: The parsed JSON response from the printer
            
        Returns:
            None if validation passed, error message string if validation failed
        """
        # Check for required top-level fields
        for field in REQUIRED_TOP_LEVEL_FIELDS:
            if field not in data:
                return f"Missing required field: {field}"
        
        # Check for detail dictionary
        if not isinstance(data.get("detail"), dict):
            return "Missing or invalid 'detail' object"
            
        # Check for required detail fields
        detail = data.get("detail", {})
        for field in REQUIRED_DETAIL_FIELDS:
            if field not in detail:
                return f"Missing required detail field: {field}"
        
        # Check that code field is an integer
        if not isinstance(data.get("code"), int):
            return "Field 'code' is missing or not an integer"
            
        # Check for error code in response
        if data.get("code") != 0:
            return f"Printer returned error code: {data.get('code')} - {data.get('message', 'Unknown error')}"
            
        return None

    async def _async_update_data(self) -> PrinterData:
        """
        Fetch data method required by DataUpdateCoordinator.
        
        This is called automatically by coordinator.async_refresh().
        
        Returns:
            Printer status data dictionary
            
        Raises:
            UpdateFailed: For all update failures, providing detailed error information
            ConfigEntryAuthFailed: For persistent authentication failures
        """
        from homeassistant.exceptions import ConfigEntryAuthFailed
        from homeassistant.helpers.update_coordinator import UpdateFailed
        
        try:
            return await self._fetch_data()
        except PrinterAuthenticationError as e:
            # If we've had multiple consecutive authentication errors, raise ConfigEntryAuthFailed
            if self._consecutive_auth_errors >= 3:
                _LOGGER.error("Persistent authentication failure: %s", e)
                raise ConfigEntryAuthFailed("Invalid credentials for Flashforge printer")
            _LOGGER.error("Authentication error: %s", e)
            raise UpdateFailed(f"Authentication failed: {e}")
        except PrinterConnectionError as e:
            _LOGGER.error("Connection error: %s", e)
            raise UpdateFailed(f"Could not connect to printer: {e}")
        except PrinterResponseValidationError as e:
            _LOGGER.error("Response validation error: %s", e)
            raise UpdateFailed(f"Invalid response from printer: {e}")
        except Exception as e:
            _LOGGER.exception("Unexpected error during update: %s", e)
            raise UpdateFailed(f"Update failed: {e}")
            
    def _add_error(self, error_message: str) -> None:
        """
        Add an error message to the error history.
        
        Args:
            error_message: The error message to add to the history
            
        This method maintains the error history limited to _max_error_history entries.
        """
        # Add error with timestamp to history
        self._last_errors.append({
            "timestamp": datetime.now(),
            "message": error_message
        })
        
        # Keep only the most recent errors
        if len(self._last_errors) > self._max_error_history:
            self._last_errors = self._last_errors[-self._max_error_history:]

    async def _send_command(self, command: str, payload: Optional[dict] = None) -> bool:
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

    async def toggle_light(self, state: bool) -> bool:
        """Toggle the printer's light."""
        command = "LED: 1" if state else "LED: 0"
        return await self._send_command("command", {"command": command})