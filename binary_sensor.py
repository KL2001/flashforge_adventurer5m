"""
Binary sensor platform for Flashforge Adventurer 5M PRO.

This module implements binary sensors for monitoring the printer's various
states including:
- Printer printing status
- Door open/closed status
- Light on/off status
- Connection status
- Error state
"""

import logging
import re
from typing import Any, Dict, Optional, List, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    PRINTING_STATES,
    ERROR_STATES,
    DOOR_OPEN,
    LIGHT_ON,
    CONNECTION_STATE_CONNECTED,
    ERROR_CODE_NONE,
    UNIT_PROGRESS_PERCENT,
    AUTO_SHUTDOWN_ENABLED_STATE, # Added
    FAN_STATUS_ON_STATE          # Added
)
from .coordinator import FlashforgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry,
    async_add_entities: Callable
) -> None:
    """
    Set up binary sensors for the Flashforge Adventurer 5M PRO.
    
    Args:
        hass: Home Assistant instance
        entry: The config entry
        async_add_entities: Callback to register entities
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create a list of entities to add
    entities = [
        # Printing status
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Printing",
            icon="mdi:printer-3d",
            device_class=BinarySensorDeviceClass.RUNNING,
            is_printing_sensor=True
        ),
        
        # Door status - Is the door open?
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Door Open",
            icon="mdi:door-open",
            device_class=BinarySensorDeviceClass.DOOR,
            detail_attribute="doorStatus",
            value_on=DOOR_OPEN
        ),
        
        # Light status - Is the light on?
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Light On",
            icon="mdi:lightbulb",
            device_class=BinarySensorDeviceClass.LIGHT,
            detail_attribute="lightStatus",
            value_on=LIGHT_ON
        ),
        
        # Connection status
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Connected",
            icon="mdi:connection",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
            connection_status_sensor=True
        ),
        
        # Error status
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Error",
            icon="mdi:alert-circle",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            error_sensor=True
        ),

        # Auto Shutdown Enabled
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Auto Shutdown Enabled",
            icon="mdi:timer-cog-outline", # Or mdi:power-settings
            device_class=None, # Or BinarySensorDeviceClass.POWER - using None for now
            entity_category=None, # Changed to None
            detail_attribute="autoShutdown",
            value_on=AUTO_SHUTDOWN_ENABLED_STATE
        ),

        # External Fan Active
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="External Fan Active",
            icon="mdi:fan",
            device_class=None, # Or BinarySensorDeviceClass.RUNNING - using None for now
            entity_category=EntityCategory.DIAGNOSTIC,
            detail_attribute="externalFanStatus",
            value_on=FAN_STATUS_ON_STATE
        ),

        # Internal Fan Active
        FlashforgeBinarySensor(
            coordinator=coordinator,
            name="Internal Fan Active",
            icon="mdi:fan-alert", # Using a different fan icon for variety, or mdi:fan
            device_class=None, # Or BinarySensorDeviceClass.RUNNING - using None for now
            entity_category=EntityCategory.DIAGNOSTIC,
            detail_attribute="internalFanStatus",
            value_on=FAN_STATUS_ON_STATE
        )
    ]
    
    # Register all entities with Home Assistant
    async_add_entities(entities)


class FlashforgeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """
    Binary sensor implementation for Flashforge Adventurer 5M PRO.
    
    These sensors represent boolean states from the printer API.
    """
    
    def __init__(
        self,
        coordinator: FlashforgeDataUpdateCoordinator,
        name: str,
        icon: str = None,
        device_class: str = None,
        entity_category: EntityCategory = None,
        detail_attribute: str = None,
        value_on: Any = None,
        is_printing_sensor: bool = False,
        connection_status_sensor: bool = False,
        error_sensor: bool = False
    ) -> None:
        """
        Initialize a binary sensor for Flashforge.
        
        Args:
            coordinator: The data update coordinator
            name: The sensor name
            icon: Icon to use for the sensor
            device_class: Binary sensor device class
            entity_category: Entity category (config, diagnostic, or None)
            detail_attribute: Attribute in detail dictionary to monitor
            value_on: Value that indicates the "on" state
            is_printing_sensor: Whether this is the printing status sensor
            connection_status_sensor: Whether this is the connection status sensor
            error_sensor: Whether this is the error state sensor
        """
        super().__init__(coordinator)
        
        self._attr_name = f"Flashforge {name}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        
        # Specific attribute settings
        self._detail_attribute = detail_attribute
        self._value_on = value_on
        self._is_printing_sensor = is_printing_sensor
        self._connection_status_sensor = connection_status_sensor
        self._error_sensor = error_sensor
        
        # Create unique_id
        sensor_key = name.lower().replace(" ", "_")
        self._attr_unique_id = f"flashforge_{coordinator.serial_number}_{sensor_key}"
    
    @property
    def is_on(self) -> bool:
        """
        Return True if the binary sensor is on.
        
        This method handles different types of binary sensors with different logic:
        - For printing sensor: Check if status is in the printing states list
        - For connection sensor: Check coordinator connection state
        - For error sensor: Check if error code exists or status is in error states
        - For attribute-based sensors: Compare to the expected "on" value
        
        Returns:
            bool: True if the sensor is in the "on" state, False otherwise
        """
        # If coordinator has no data, we can't determine state
        if not self.coordinator.data:
            return False
            
        detail = self.coordinator.data.get("detail", {})
        
        # Printing status sensor
        if self._is_printing_sensor:
            status = detail.get("status")
            return status in PRINTING_STATES if status else False
            
        # Connection status sensor
        if self._connection_status_sensor:
            # Use the connection_state property if available
            if hasattr(self.coordinator, "connection_state"):
                return self.coordinator.connection_state == CONNECTION_STATE_CONNECTED
            # Fallback to checking if we have data
            return self.coordinator.last_update_success
            
        # Error state sensor
        if self._error_sensor:
            # Check for error code
            error_code = detail.get("errorCode")
            if error_code and error_code != ERROR_CODE_NONE:
                return True
                
            # Check if status is an error state
            status = detail.get("status")
            return status in ERROR_STATES if status else False
            
        # For attribute-based sensors (door, light, etc.)
        if self._detail_attribute:
            return detail.get(self._detail_attribute) == self._value_on
            
        # Default
        return False
        
    @property
    def available(self) -> bool:
        """
        Return if entity is available.
        
        The connection status sensor should always be available, even when
        the coordinator has no data. Other sensors depend on coordinator data.
        
        Returns:
            bool: True if available, False otherwise
        """
        if self._connection_status_sensor:
            return True
        return self.coordinator.last_update_success
        
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """
        Return additional state attributes.
        
        For error sensors, include error details when available.
        For printing sensors, include print job information.
        
        Returns:
            dict: Additional attributes to expose
        """
        if not self.coordinator.data:
            return None
            
        detail = self.coordinator.data.get("detail", {})
        attributes = {}
        
        # Add error details for error sensor
        if self._error_sensor and self.is_on:
            attributes["error_code"] = detail.get("errorCode")
        
        # Add print job details for printing sensor
        if self._is_printing_sensor and self.is_on:
            # Include relevant print details
            for attr in ["printFileName", "printProgress", "printLayer", "targetPrintLayer", 
                        "printDuration", "estimatedTime"]:
                if attr in detail:
                    # Convert printProgress to percentage
                    if attr == "printProgress" and detail[attr] is not None:
                        attributes["print_progress"] = f"{float(detail[attr]) * 100:.1f}{UNIT_PROGRESS_PERCENT}"
                    else:
                        # Convert camelCase to snake_case for attribute names
                        snake_attr = re.sub(r'(?<!^)(?=[A-Z])', '_', attr).lower()
                        attributes[snake_attr] = detail[attr]
                        
        return attributes if attributes else None
    
    @property
    def device_info(self):
        """
        Return device info for this sensor.
        
        Ensures all entities for the printer are grouped under the same device.
        
        Returns:
            dict: Device information
        """
        if not self.coordinator.data:
            return None
            
        fw = self.coordinator.data.get("detail", {}).get("firmwareVersion")
        
        return {
            "identifiers": {(DOMAIN, self.coordinator.serial_number)},
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": fw,
        }
        
    async def async_added_to_hass(self):
        """Register callbacks when entity is added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

