import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfMass,
    PERCENTAGE
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Example typed dict or class for storing printer info (if you need it).
class PrinterDefinition:
    def __init__(self, ip_address: str, port: int):
        self.ip_address = ip_address
        self.port = port


# Example mixin that sets a base name/unique_id
# Adjust to suit your actual usage.
class FlashforgeAdventurerCommonPropertiesMixin:
    @property
    def name(self) -> str:
        return "Flashforge Adventurer 5M PRO"

    @property
    def unique_id(self) -> str:
        return f"flashforge_{self.coordinator.serial_number}"


async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up all Flashforge Adventurer 5M Pro sensors via the config entry.
    Home Assistant will call this after you call:
    `await hass.config_entries.async_forward_entry_setup(entry, "sensor")`
    in your __init__.py.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    #
    #  A. Top-Level Fields
    #     The printer's JSON has top-level "code" and "message" keys.
    #
    sensors.append(FlashforgeSensor(
        coordinator,
        name="Flashforge Code",
        attribute="code",
        is_top_level=True,
    ))
    sensors.append(FlashforgeSensor(
        coordinator,
        name="Flashforge Message",
        attribute="message",
        is_top_level=True,
    ))

    #
    #  B. System Info (detail.*)
    #
    detail_fields_system = [
        ("Flashforge Status", "status", False),
        ("Flashforge Auto Shutdown", "autoShutdown", False),
        ("Flashforge Auto Shutdown Time", "autoShutdownTime", False),
        ("Flashforge Door Status", "doorStatus", False),
        ("Flashforge Light Status", "lightStatus", False),
        ("Flashforge Location", "location", False),
        ("Flashforge IP Address", "ipAddr", False),
        ("Flashforge MAC Address", "macAddr", False),
        ("Flashforge Firmware Version", "firmwareVersion", False),
        ("Flashforge Nozzle Model", "nozzleModel", False),
        ("Flashforge Nozzle Count", "nozzleCnt", False),
        ("Flashforge Nozzle Style", "nozzleStyle", False),
        ("Flashforge PID", "pid", False),
        ("Flashforge Error Code", "errorCode", False),
        ("Flashforge Flash Register Code", "flashRegisterCode", False),
        ("Flashforge Polar Register Code", "polarRegisterCode", False),
        ("Flashforge Printer Name", "name", False),
        ("Flashforge Measure (Build Volume)", "measure", False),
    ]
    for name, attr, top in detail_fields_system:
        sensors.append(FlashforgeSensor(coordinator, name, attr, is_top_level=top))

    #
    #  C. Temperatures
    #
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
    for (name, attr, unit) in detail_fields_temps:
        sensors.append(FlashforgeSensor(
            coordinator,
            name=f"Flashforge {name}",
            attribute=attr,
            is_top_level=False,
            unit=unit
        ))

    #
    #  D. Print Info
    #
    detail_fields_print = [
        ("Print Duration", "printDuration", None),
        ("Print File Name", "printFileName", None),
        ("Print File Thumb URL", "printFileThumbUrl", None),
        ("Print Layer", "printLayer", None),
        ("Print Progress", "printProgress", "progress"),  # We'll multiply by 100
        ("Estimated Time", "estimatedTime", None),
        ("Current Print Speed", "currentPrintSpeed", None),
        ("Print Speed Adjust", "printSpeedAdjust", None),
        ("Target Print Layer", "targetPrintLayer", None),
    ]
    for (name, attr, typehint) in detail_fields_print:
        if typehint == "progress":
            sensors.append(FlashforgeSensor(
                coordinator,
                name=f"Flashforge {name}",
                attribute=attr,
                is_top_level=False,
                is_percentage=True
            ))
        else:
            sensors.append(FlashforgeSensor(
                coordinator,
                name=f"Flashforge {name}",
                attribute=attr,
                is_top_level=False
            ))

    #
    #  E. Filament / Usage
    #
    detail_fields_filament = [
        ("Cumulative Filament", "cumulativeFilament", "m"),      # or "meter"
        ("Cumulative Print Time", "cumulativePrintTime", "min"), # or your best guess
        ("Fill Amount", "fillAmount", None),
        ("Left Filament Type", "leftFilamentType", None),
        ("Right Filament Type", "rightFilamentType", None),
        ("Estimated Left Length", "estimatedLeftLen", "mm"),
        ("Estimated Left Weight", "estimatedLeftWeight", UnitOfMass.GRAMS),
        ("Estimated Right Length", "estimatedRightLen", "mm"),
        ("Estimated Right Weight", "estimatedRightWeight", UnitOfMass.GRAMS),
    ]
    for (name, attr, unit) in detail_fields_filament:
        sensors.append(FlashforgeSensor(
            coordinator,
            name=f"Flashforge {name}",
            attribute=attr,
            is_top_level=False,
            unit=unit
        ))

    #
    #  F. Fans & Misc
    #
    detail_fields_fans = [
        ("Chamber Fan Speed", "chamberFanSpeed", None),
        ("Cooling Fan Speed", "coolingFanSpeed", None),
        ("External Fan Status", "externalFanStatus", None),
        ("Internal Fan Status", "internalFanStatus", None),
        ("TVOC", "tvoc", None),
    ]
    for (name, attr, unit) in detail_fields_fans:
        sensors.append(FlashforgeSensor(
            coordinator,
            name=f"Flashforge {name}",
            attribute=attr,
            is_top_level=False,
            unit=unit
        ))

    #
    #  G. Other
    #
    detail_fields_other = [
        ("Camera Stream URL", "cameraStreamUrl", None),
        ("Remaining Disk Space", "remainingDiskSpace", "GB"),
        ("Z Axis Compensation", "zAxisCompensation", None),
    ]
    for (name, attr, unit) in detail_fields_other:
        sensors.append(FlashforgeSensor(
            coordinator,
            name=f"Flashforge {name}",
            attribute=attr,
            is_top_level=False,
            unit=unit
        ))

    async_add_entities(sensors)


class FlashforgeSensor(SensorEntity):
    """A sensor for one JSON field from the printer."""

    def __init__(self, coordinator, name, attribute, is_top_level=False, unit=None, is_percentage=False):
        self.coordinator = coordinator
        self._attr_name = name
        self._attribute = attribute
        self._is_top_level = is_top_level
        self._unit = unit
        self._is_percentage = is_percentage
        # Build a unique ID using serial_number
        unique_part = attribute.replace("_", "").replace(" ", "").lower()
        self._attr_unique_id = f"flashforge_{self.coordinator.serial_number}_{unique_part}"

    @property
    def native_unit_of_measurement(self):
        if self._is_percentage:
            return PERCENTAGE
        return self._unit

    @property
    def device_info(self):
        """Group these sensors under one device."""
        if not self.coordinator.data:
            return None  # Or provide default values

        fw = self.coordinator.data.get("detail", {}).get("firmwareVersion")

        return {
            "identifiers": {(DOMAIN, self.coordinator.serial_number)},
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": fw,
        }

    @property
    def should_poll(self):
        """We rely on the DataUpdateCoordinator; no direct polling."""
        return False

    @property
    def available(self):
        """Available if last update from coordinator was successful."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Extract the relevant data from the coordinator's last fetch."""
        data = self.coordinator.data
        if not data:
            return None

        if self._is_top_level:
            # For top-level keys like "code" or "message"
            val = data.get(self._attribute)
        else:
            # For detail.* fields
            detail = data.get("detail", {})
            val = detail.get(self._attribute)

        if val is None:
            return None

        if self._is_percentage:
            # Convert 0..1 -> 0..100%
            return round(float(val) * 100, 1)

        return val

    async def async_update(self):
        """If forced by HA, we trigger a coordinator refresh."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Register for coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
