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

    In this version of "Option B," we ensure that MjpegCamera
    receives a valid mjpeg_url string in its constructor so we don't
    hit "TypeError: Invalid type for url. Expected str or httpx.URL, got: None."
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # We build the actual camera entity, passing a fallback MJPEG URL
    # if coordinator.data doesn't contain 'cameraStreamUrl' yet.
    cameras = [
        FlashforgeAdventurer5MCamera(coordinator),
    ]

    async_add_entities(cameras, update_before_add=True)
    return True


class FlashforgeAdventurer5MCamera(MjpegCamera):
    """
    A camera entity for the Flashforge Adventurer 5M PRO, using the MjpegCamera base class.
    We pass a valid 'mjpeg_url' to the parent constructor to avoid None errors.
    """

    def __init__(self, coordinator):
        """
        :param coordinator: The DataUpdateCoordinator that holds printer data (including cameraStreamUrl).
        """
        self._coordinator = coordinator
        self._attr_unique_id = f"flashforge_{coordinator.serial_number}_camera"

        # If the printer hasn't yet provided "cameraStreamUrl," fall back to a known port:
        # e.g., http://<coordinator.host>:8080/?action=stream
        # Assuming 'host' is stored on the coordinator. Adjust as needed if it's stored differently.
        fallback_url = None
        if hasattr(coordinator, "host"):
            fallback_url = f"http://{coordinator.host}:8080/?action=stream"

        data = coordinator.data or {}
        detail = data.get("detail", {})
        # If 'cameraStreamUrl' is missing or empty, use the fallback:
        stream_url = detail.get("cameraStreamUrl") or fallback_url

        # Avoid a None-type url:
        if not stream_url:
            _LOGGER.warning(
                "No 'cameraStreamUrl' and no known fallback. Using a dummy URL to prevent errors."
            )
            stream_url = "http://0.0.0.0/"

        super().__init__(
            name="Flashforge Adventurer 5M PRO camera",
            mjpeg_url=stream_url,
            still_image_url=None
        )

    @property
    def device_info(self):
        """
        Group the camera entity under the same device as sensors,
        using the coordinator's serial number.
        """
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

    async def async_added_to_hass(self) -> None:
        """
        Register an update listener so we refresh if the coordinator data changes.
        """
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_mjpeg_url)
        )

    def _update_mjpeg_url(self) -> None:
        """
        If the coordinator fetches a new 'cameraStreamUrl', update our mjpeg_url.
        Then call self.async_write_ha_state() to refresh the camera entity.
        """
        data = self._coordinator.data or {}
        detail = data.get("detail", {})

        # If the detail includes a fresh 'cameraStreamUrl', use it.
        # Otherwise keep our existing fallback.
        new_url = detail.get("cameraStreamUrl")
        if not new_url and hasattr(self._coordinator, "host"):
            new_url = f"http://{self._coordinator.host}:8080/?action=stream"

        if new_url and new_url != self._mjpeg_url:
            _LOGGER.debug("Updating camera stream URL to: %s", new_url)
            self._mjpeg_url = new_url
            self.async_write_ha_state()

    @property
    def is_streaming(self):
        """MjpegCamera sets up a continuous stream, so this is True."""
        return True
