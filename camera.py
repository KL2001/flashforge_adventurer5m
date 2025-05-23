import logging
from typing import Callable

from homeassistant import config_entries, core  # type: ignore
from homeassistant.components.mjpeg.camera import MjpegCamera  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore

from .const import DOMAIN
from .coordinator import FlashforgeDataUpdateCoordinator  # type: ignore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable
) -> bool:
    """
    Set up camera entities for the Flashforge Adventurer 5M PRO via a config entry.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    cameras = [
        FlashforgeAdventurer5MCamera(coordinator),
    ]

    async_add_entities(cameras, update_before_add=True)
    return True


class FlashforgeAdventurer5MCamera(CoordinatorEntity, MjpegCamera):
    """
    A camera entity for the Flashforge Adventurer 5M PRO, using the MjpegCamera base class.
    This implementation assumes that the camera stream URL is available via the coordinator's data.
    """

    def __init__(self, coordinator: FlashforgeDataUpdateCoordinator):
        CoordinatorEntity.__init__(self, coordinator)
        self.coordinator = coordinator

        detail = self.coordinator.data.get("detail", {}) if self.coordinator.data else {}
        serial_number = getattr(self.coordinator, "serial_number", "unknown")
        name = "Flashforge Adventurer 5M PRO Camera"

        # Determine initial stream URL
        stream_url = detail.get("cameraStreamUrl")
        if not stream_url:
            ip_addr = detail.get("ipAddr")
            if ip_addr:
                stream_url = f"http://{ip_addr}:8080/?action=stream"
                _LOGGER.debug("'cameraStreamUrl' missing, using fallback URL: %s", stream_url)
            else:
                _LOGGER.warning(
                    "Coordinator does not have 'ipAddr' and 'cameraStreamUrl' is missing. Using dummy URL."
                )
                stream_url = "http://0.0.0.0/"

        MjpegCamera.__init__(
            self,
            name=name,
            mjpeg_url=stream_url,
            still_image_url=None
        )
        self._attr_unique_id = f"flashforge_{serial_number}_camera"
        self._attr_is_streaming = True

        # CRITICAL: Assign device_info, do NOT return it
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial_number)},
            "name": "Flashforge Adventurer 5M PRO",
            "manufacturer": "Flashforge",
            "model": detail.get("model", "Adventurer 5M PRO"),
            "sw_version": detail.get("firmwareVersion"),
        }

    @property
    def stream_source(self) -> str | None:
        """Return the camera stream URL for Home Assistant."""
        detail = self.coordinator.data.get("detail", {}) if self.coordinator.data else {}
        camera_stream_url = detail.get("cameraStreamUrl")
        ip_addr = detail.get("ipAddr")
        if camera_stream_url:
            return camera_stream_url
        elif ip_addr:
            fallback_url = f"http://{ip_addr}:8080/?action=stream"
            _LOGGER.debug("No 'cameraStreamUrl', using fallback URL: %s", fallback_url)
            return fallback_url
        else:
            _LOGGER.warning(
                "No 'cameraStreamUrl' and no 'ipAddr' available. Using dummy URL."
            )
            return "http://0.0.0.0/"

    @property
    def available(self) -> bool:
        """Return True if the camera is available."""
        return (
            self.coordinator.last_update_success
            and self._mjpeg_url is not None
            and self._mjpeg_url != "http://0.0.0.0/"
        )

    def _handle_coordinator_update(self) -> None:
        """Update stream URL and device info if coordinator data changes."""
        new_url = self.stream_source
        if new_url and new_url != self._mjpeg_url:
            _LOGGER.debug("Updating camera stream URL to: %s", new_url)
            self._mjpeg_url = new_url
        # Optionally update sw_version if it has changed
        fw_version = self.coordinator.data.get("detail", {}).get("firmwareVersion")
        if fw_version and self._attr_device_info.get("sw_version") != fw_version:
            self._attr_device_info["sw_version"] = fw_version
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register for coordinator updates and update state on add."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
