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
        """
        Initialize the MJPEG camera entity.

        :param coordinator: The DataUpdateCoordinator that holds printer data (including cameraStreamUrl).
        """
        self._coordinator = coordinator

        # Extract necessary details from coordinator data
        detail = coordinator.data.get("detail", {})
        printer_name = detail.get("name", "unknown")
        unique_id = f"flashforge_{printer_name}_camera"
        name = f"Flashforge Adventurer 5M PRO Camera"

        # Fetch the stream URL from the coordinator data
        stream_url = detail.get("cameraStreamUrl")

        if not stream_url:
            # Use fallback if 'cameraStreamUrl' is missing
            ip_addr = detail.get("ipAddr")
            if ip_addr:
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
    def device_info(self):
        """
        Group the camera entity under the same device as sensors,
        using the coordinator's printer name.
        """
        data = self._coordinator.data or {}
        detail = data.get("detail", {})
        fw = detail.get("firmwareVersion")

        return {
            "identifiers": { (DOMAIN, detail.get("name", "unknown")) },
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": "Adventurer 5M PRO",
            "sw_version": fw,
        }

    @property
    def is_streaming(self):
        """MjpegCamera sets up a continuous stream, so this is True."""
        return True

    @property
    def stream_source(self) -> str | None:
        """
        Return the camera stream URL.
        This property is used by HA to access the live stream.
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
                "No 'cameraStreamUrl' and no 'ipAddr' available. Using dummy URL."
            )
            return "http://0.0.0.0/"

    async def async_added_to_hass(self) -> None:
        """
        Register for coordinator updates to handle dynamic changes in the stream URL.
        """
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_stream_url)
        )

    def _update_stream_url(self) -> None:
        """
        If the coordinator fetches a new 'cameraStreamUrl', update our mjpeg_url.
        Then call self.async_write_ha_state() to refresh the camera entity.
        """
        new_url = self.stream_source

        if new_url and new_url != self._mjpeg_url:
            _LOGGER.debug("Updating camera stream URL to: %s", new_url)
            self._mjpeg_url = new_url
            self.async_write_ha_state()
