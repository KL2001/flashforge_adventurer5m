import logging
from typing import Optional, Union
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfMass,
    PERCENTAGE
)
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up all Flashforge Adventurer 5M Pro sensors via the config entry.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    # Top-Level Fields
    sensors.append(FlashforgeSensor(coordinator, name="Flashforge Code", attribute="code", is_top_level=True))
    sensors.append(FlashforgeSensor(coordinator, name="Flashforge Message", attribute="message", is_top_level=True))

    # System Info (detail.*)
    detail_fields_system = [
        ("Flashforge Status", "status"),
        ("Flashforge Auto Shutdown", "autoShutdown"),
        ("Flashforge Auto Shutdown Time", "autoShutdownTime"),
        ("Flashforge Door Status", "doorStatus"),
        ("Flashforge Light Status", "lightStatus"),
        ("Flashforge Location", "location"),
        ("Flashforge IP Address", "ipAddr"),
        ("Flashforge MAC Address", "macAddr"),
        ("Flashforge Firmware Version", "firmwareVersion"),
        ("Flashforge Nozzle Model", "nozzleModel"),
        ("Flashforge Nozzle Count", "nozzleCnt"),
        ("Flashforge Nozzle Style", "nozzleStyle"),
        ("Flashforge PID", "pid"),
        ("Flashforge Error Code", "errorCode"),
        ("Flashforge Flash Register Code", "flashRegisterCode"),
        ("Flashforge Polar Register Code", "polarRegisterCode"),
        ("Flashforge Printer Name", "name"),
        ("Flashforge Measure (Build Volume)", "measure"),
    ]
    for name, attr in detail_fields_system:
        sensors.append(FlashforgeSensor(coordinator, name=name, attribute=attr))

    # Temperatures
    detail_fields_temps = [
        ("Chamber Temp", "chamberTemp", UnitOfTemperature.CELSIUS),
        ("Chamber Target Temp", "chamberTargetTemp", UnitOfTemperature.CELSIUS),
        ("Left Nozzle Temp", "leftTemp", UnitOfTemperature.CELSIUS),
        ("Left Nozzle Target Temp", "leftTargetTemp", UnitOfTemperature.CELSIUS),
        ("Right Nozzle Temp", "rightTemp", UnitOfTemperature.CELSIUS),
        ("Right Nozzle Target Temp", "rightTargetTemp", UnitOfTemperature.CELSIUS),
        ("Platform Temp", "platTemp", UnitOfTemperature.CELSIUS),
        ("Platform Target Temp", "platTargetTemp", UnitOfTemperature.CELSIUS),
    ]
    for name, attr, unit in detail_fields_temps:
        sensors.append(FlashforgeSensor(coordinator, name=name, attribute=attr, unit=unit))

    # Print Info
    detail_fields_print = [
        ("Print Duration", "printDuration", None),
        ("Print File Name", "printFileName", None),
        ("Print File Thumb URL", "printFileThumbUrl", None),
        ("Print Layer", "printLayer", None),
        ("Print Progress", "printProgress", PERCENTAGE),
        ("Estimated Time", "estimatedTime", None),
        ("Current Print Speed", "currentPrintSpeed", None),
        ("Print Speed Adjust", "printSpeedAdjust", None),
        ("Target Print Layer", "targetPrintLayer", None),
    ]
    for name, attr, unit in detail_fields_print:
        sensors.append(FlashforgeSensor(coordinator, name=name, attribute=attr, unit=unit))

    # Filament / Usage
    detail_fields_filament = [
        ("Cumulative Filament", "cumulativeFilament", "m"),
        ("Cumulative Print Time", "cumulativePrintTime", "min"),
        ("Fill Amount", "fillAmount", None),
        ("Left Filament Type", "leftFilamentType", None),
        ("Right Filament Type", "rightFilamentType", None),
        ("Estimated Left Length", "estimatedLeftLen", "mm"),
        ("Estimated Left Weight", "estimatedLeftWeight", UnitOfMass.GRAMS),
        ("Estimated Right Length", "estimatedRightLen", "mm"),
        ("Estimated Right Weight", "estimatedRightWeight", UnitOfMass.GRAMS),
    ]
    for name, attr, unit in detail_fields_filament:
        sensors.append(FlashforgeSensor(coordinator, name=name, attribute=attr, unit=unit))

    # Fans & Misc
    detail_fields_fans = [
        ("Chamber Fan Speed", "chamberFanSpeed", None),
        ("Cooling Fan Speed", "coolingFanSpeed", None),
        ("External Fan Status", "externalFanStatus", None),
        ("Internal Fan Status", "internalFanStatus", None),
        ("TVOC", "tvoc", None),
    ]
    for name, attr, unit in detail_fields_fans:
        sensors.append(FlashforgeSensor(coordinator, name=name, attribute=attr, unit=unit))

    async_add_entities(sensors, update_before_add=True)

class FlashforgeSensor(SensorEntity):
    def __init__(self, coordinator, name: str, attribute: str, unit: Optional[str] = None, is_top_level: bool = False):
        self._coordinator = coordinator
        self._name = name
        self._attribute = attribute
        self._unit = unit
        self._is_top_level = is_top_level
        self._attr_unique_id = f"flashforge_{coordinator.serial_number}_{attribute}"
        self._attr_name = name
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        fw = self._coordinator.data.get("detail", {}).get("firmwareVersion")
        return DeviceInfo(
            identifiers = {(DOMAIN, self._coordinator.serial_number)},
            name = "Flashforge Adventurer 5M PRO",
            manufacturer = "Flashforge",
            model = "Adventurer 5M PRO",
            sw_version = fw,
        )

    @property
    def native_value(self) -> Optional[Union[str, int, float]]:
        data = self._coordinator.data
        if self._is_top_level:
            return data.get(self._attribute)
        detail = data.get("detail", {})
        return detail.get(self._attribute)

    @property
    def available(self) -> bool:
        return self._coordinator.data is not None

    async def async_update(self) -> None:
        await self._coordinator.async_request_refresh()
