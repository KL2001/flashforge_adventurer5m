import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up sensors for Flashforge Adventurer 5M Pro."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    # EXAMPLE: We create several sensors. Adjust these as you wish.
    # Each sensor references a different key from the JSON response.

    sensors = [
        FlashforgeSensor(
            coordinator, 
            name="Flashforge Status", 
            attribute="status"
        ),
        FlashforgeSensor(
            coordinator,
            name="Flashforge Right Nozzle Temp",
            attribute="rightTemp",
            unit=UnitOfTemperature.CELSIUS
        ),
        FlashforgeSensor(
            coordinator,
            name="Flashforge Bed Temp",
            attribute="platTemp",
            unit=UnitOfTemperature.CELSIUS
        ),
        FlashforgeSensor(
            coordinator,
            name="Flashforge Print Progress",
            attribute="printProgress",
            is_percentage=True
        ),
    ]

    add_entities(sensors, True)


class FlashforgeSensor(SensorEntity):
    """A sensor for a single JSON field from the printer."""

    def __init__(self, coordinator, name, attribute, unit=None, is_percentage=False):
        """Initialize."""
        self.coordinator = coordinator
        self._attr_name = name
        self._attribute = attribute
        self._unit = unit
        self._is_percentage = is_percentage
        # Build a unique ID from the attribute
        self._attr_unique_id = f"flashforge_{coordinator.serial_number}_{attribute}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit, e.g. °C, %."""
        if self._is_percentage:
            return "%"
        return self._unit

    @property
    def device_info(self):
        """Group all sensors under one device in the device registry."""
        # We can pull version from coordinator.data if we want
        firmware_version = None
        if self.coordinator.data and "detail" in self.coordinator.data:
            firmware_version = self.coordinator.data["detail"].get("firmwareVersion")

        return {
            "identifiers": {(DOMAIN, self.coordinator.serial_number)},
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": firmware_version,
        }

    @property
    def should_poll(self):
        """Entities do not poll; we let the coordinator handle updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Extract the relevant data from coordinator's last fetch."""
        data = self.coordinator.data
        if not data or "detail" not in data:
            return None

        val = data["detail"].get(self._attribute)
        if val is None:
            return None

        # If it's progress, multiply by 100
        if self._is_percentage:
            return round(float(val) * 100, 1)

        return val

    async def async_update(self):
        """Manual update triggered by HA (rarely used)."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added, register callbacks to update automatically."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

