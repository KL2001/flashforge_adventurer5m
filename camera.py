import logging
from homeassistant.components.camera import Camera
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    coordinator = hass.data[DOMAIN]["coordinator"]
    camera = FlashforgeMjpegCamera(coordinator)
    add_entities([camera])


class FlashforgeMjpegCamera(Camera):
    """Camera for the Flashforge printer using its MJPEG stream."""

    def __init__(self, coordinator):
        super().__init__()
        self._coordinator = coordinator
        self._name = "Flashforge Adventurer 5M Camera"

    @property
    def name(self):
        return self._name

    @property
    def is_streaming(self):
        return True

    @property
    def device_info(self):
        """Group camera under same device."""
        data = self._coordinator.data or {}
        detail = data.get("detail", {})
        fw = detail.get("firmwareVersion")

        return {
            "identifiers": {(DOMAIN, self._coordinator.serial_number)},
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": fw,
        }

    @property
    def stream_source(self):
        """Return the MJPEG URL from the printer JSON, or hardcode if you prefer."""
        data = self._coordinator.data or {}
        detail = data.get("detail", {})
        stream_url = detail.get("cameraStreamUrl")

        # Fallback if missing in JSON:
        if not stream_url:
            stream_url = f"http://{self._coordinator.host}:8080/?action=stream"

        return stream_url
