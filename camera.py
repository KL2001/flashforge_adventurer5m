"""
Camera support for the Flashforge Adventurer 5M PRO printer.
"""

import logging
from typing import Callable

from homeassistant import config_entries, core
from homeassistant.components.mjpeg.camera import MjpegCamera

from .const import DOMAIN
from .sensor import (
    FlashforgeAdventurerCommonPropertiesMixin,
    PrinterDefinition,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable
) -> bool:
    """
    Set up camera entities for the Flashforge Adventurer 5M PRO from a config entry.

    :param hass: Home Assistant instance
    :param config_entry: The config entry holding integration data
    :param async_add_entities: Callback to add entities to HA
    :return: True if setup succeeded
    """
    # Retrieve the integration config that was saved in __init__.py (or wherever).
    config = hass.data[DOMAIN][config_entry.entry_id]

    # Merge in any user-defined options from the UI, if your integration uses them.
    if config_entry.options:
        config.update(config_entry.options)

    # Create a single camera or multiple cameras if needed.
    cameras = [
        FlashforgeAdventurer5MCamera(config),
    ]

    async_add_entities(cameras, update_before_add=True)
    return True


class FlashforgeAdventurer5MCamera(
    FlashforgeAdventurerCommonPropertiesMixin,
    MjpegCamera
):
    """
    A camera entity for the Flashforge Adventurer 5M PRO,
    exposing the MJPEG stream from the printer.
    """

    def __init__(self, printer_definition: PrinterDefinition) -> None:
        """
        :param printer_definition: A dict or object containing printer IP, port, etc.
        """
        self._ip = printer_definition["ip_address"]
        self._port = printer_definition["port"]

        # Initialize the parent MjpegCamera with the name, MJPEG URL, etc.
        # We'll set 'still_image_url=None' because the printer typically
        # doesn't provide a snapshot endpoint, only a stream.
        super().__init__(
            name=self.name,
            mjpeg_url=self.stream_url,
            still_image_url=None
        )

    @property
    def name(self) -> str:
        """
        The friendly name of this camera entity.
        """
        # If your mixin provides a base name (like 'Flashforge Adventurer 5M PRO'),
        # we append 'camera' for clarity. Adjust as you like.
        return f"{super().name} camera"

    @property
    def unique_id(self) -> str:
        """
        A unique ID, allowing users to manage this entity from the UI.
        """
        # The mixin might provide a base unique_id as well.
        return f"{super().unique_id}_camera"

    @property
    def stream_url(self) -> str:
        """
        The MJPEG URL for the printer's built-in camera.
        Typically http://<ip>:8080/?action=stream
        """
        # If your mixin or config provides a camera path, adapt here.
        return f"http://{self._ip}:8080/?action=stream"
