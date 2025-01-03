import logging
from typing import Callable

from homeassistant import config_entries, core
from homeassistant.components.mjpeg.camera import MjpegCamera

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable
) -> bool:
    """
    Set up camera entities for the Flashforge Adventurer 5M PRO via a config entry.

    In Option B, we assume the camera only needs the coordinator object
    (so it can pull the stream URL from coordinator.data) rather than
    a raw config dict with "ip_address" or "port". That means we pass
    the coordinator directly into our camera entity constructor, not a
    dictionary.

    This camera expects to fetch its URL from coordinator.data["detail"]["cameraStreamUrl"].
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create one or more camera entities, each receiving the coordinator.
    cameras = [
        FlashforgeAdventurer5MCamera(coordinator),
    ]

    async_add_entities(cameras, update_before_add=True)
    return True


class FlashforgeAdventurer5MCamera(MjpegCamera):
    """
    A camera entity for the Flashforge Adventurer 5M PRO, exposing the MJPEG stream
    from the printer. In this 'Option B' approach, we only need the coordinator.
    """

    def __init__(self, coordinator):
        """
        :param coordinator: The DataUpdateCoordinator that holds printer data.
        """
        super().__init__(
            name="Flashforge Adventurer 5M PRO camera",
            mjpeg_url=None,         # We'll fetch via stream_source property
            still_image_url=None
        )
        self._coordinator = coordinator
        self._attr_unique_id = f"flashforge_{self._coordinator.serial_number}_camera"

    @property
    def device_info(self):
        """
        Group the camera entity under the same device as sensors, using
        the coordinator's serial number.
        """
        data = self._coordinator.data or {}
        detail = data.get("detail", {})
        fw = detail.get("firmwareVersion")

        return {
            "identifiers": { (DOMAIN, self._coordinator.serial_number) },
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": fw,
        }

    @property
    def is_streaming(self):
        return True

    @property
    def stream_source(self) -> str | None:
        """
        Return the MJPEG URL from the coordinator data:
          coordinator.data["detail"]["cameraStreamUrl"]
        Fallback if missing.
        """
        data = self._coordinator.data or {}
        detail = data.get("detail", {})
        stream_url = detail.get("cameraStreamUrl")

        if not stream_url:
            # fallback if the detail doesn't provide a URL
            stream_url = f"http://{self._coordinator.host}:8080/?action=stream"

        return stream_url

    async def async_added_to_hass(self) -> None:
        """
        Register an update listener so we refresh if the coordinator data changes.
        """
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
