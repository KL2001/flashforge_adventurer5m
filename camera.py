import logging
from typing import Callable, Optional

from homeassistant import config_entries, core
from homeassistant.components.mjpeg.camera import MjpegCamera
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable
) -> bool:
    """
    Set up camera entities for the Flashforge Adventurer 5M PRO via a config entry.

    Option B: The camera only needs the coordinator to fetch the stream URL.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create camera entities
    cameras = [
        FlashforgeAdventurer5MCamera(coordinator),
    ]

    async_add_entities(cameras, update_before_add=True)
    return True

class FlashforgeAdventurer5MCamera(MjpegCamera):
    """
    A camera entity for the Flashforge Adventurer 5M PRO, using the MjpegCamera base class.
    This implementation assumes that the camera stream URL is available via the coordinator's data.
    """
    def __init__(self, coordinator):
        self._coordinator = coordinator
        detail = coordinator.data.get("detail", {})
        serial_number = coordinator.serial_number
        unique_id = f"flashforge_{serial_number}_camera"
        name = "Flashforge Adventurer 5M PRO Camera"
        stream_url = detail.get("cameraStreamUrl")
        if not stream_url:
            ip_addr = detail.get("ipAddr")
            if (ip_addr):
                stream_url = f"http://{ip_addr}:8080/?action=stream"
                _LOGGER.debug(f"'cameraStreamUrl' missing, using fallback URL: {stream_url}")
            else:
                _LOGGER.warning(
                    "Coordinator does not have 'ipAddr' and 'cameraStreamUrl' is missing. Using dummy URL."
                )
                stream_url = "http://0.0.0.0/"
        super().__init__(
            name=name,
            mjpeg_url=stream_url,
            still_image_url=None
        )
        self._attr_unique_id = unique_id

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        if not self._coordinator.data:
            return None
        fw = self._coordinator.data.get("detail", {}).get("firmwareVersion")
        return DeviceInfo(
            identifiers = {(DOMAIN, self._coordinator.serial_number)},
            name = "Flashforge Adventurer 5M PRO",
            manufacturer = "Flashforge",
            model = "Adventurer 5M PRO",
            sw_version = fw,
        )

    @property
    def is_streaming(self):
        """MjpegCamera sets up a continuous stream, so this is True."""
        return True

    async def stream_source(self) -> Optional[str]:
        """
        Return the camera stream URL.
        This async method is used by HA to access the live stream.
        """
        detail = self._coordinator.data.get("detail", {})
        camera_stream_url = detail.get("cameraStreamUrl")
        ip_addr = detail.get("ipAddr")
        if camera_stream_url:
            return camera_stream_url
        elif ip_addr:
            fallback_url = f"http://{ip_addr}:8080/?action=stream"
            _LOGGER.debug(f"No 'cameraStreamUrl', using fallback URL: {fallback_url}")
            return fallback_url
        else:
            _LOGGER.warning(
                "No 'cameraStreamUrl' and no 'ipAddr' available. Returning None."
            )
            return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_stream_url)
        )

    def _update_stream_url(self) -> None:
        import asyncio
        async def update_url():
            new_url = await self.stream_source()
            if new_url and new_url != self._mjpeg_url:
                _LOGGER.debug("Updating camera stream URL to: %s", new_url)
                self._mjpeg_url = new_url
                self.async_write_ha_state()
        asyncio.create_task(update_url())
