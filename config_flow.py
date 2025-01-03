"""
Config flow for Flashforge Adventurer 5M PRO integration.
"""
import logging
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlashforgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Flashforge Adventurer 5M PRO integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """
        This is the first step of the config flow, shown when the user chooses
        to add your integration from the UI.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # 1) Validate the user input
            host = user_input["host"]
            serial_number = user_input["serial_number"]
            check_code = user_input["check_code"]

            # Optional: check if this printer is already configured
            await self.async_set_unique_id(f"flashforge_{serial_number}")
            self._abort_if_unique_id_configured()

            # 2) You can do a connection test here if you want
            try:
                await self._test_printer_connection(
                    self.hass,
                    host,
                    serial_number,
                    check_code,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            
            # 3) If no errors, create the config entry
            if not errors:
                return self.async_create_entry(
                    title=f"Flashforge {serial_number}",  # Shown in HA UI
                    data={
                        "host": host,
                        "serial_number": serial_number,
                        "check_code": check_code,
                    },
                )

        # Show the form if no user input yet or on errors
        data_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Required("serial_number"): str,
                vol.Required("check_code"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _test_printer_connection(
        self,
        hass: HomeAssistant,
        host: str,
        serial_number: str,
        check_code: str
    ) -> None:
        """
        Optional method to verify the printer is reachable and the
        check_code is valid. Raise exceptions on failure.
        """
        # For example, do a quick POST to http://<host>:8898/detail
        # If you can connect, do nothing. If not, raise CannotConnect or InvalidAuth.

        # Pseudocode:
        # try:
        #     async with aiohttp.ClientSession() as session:
        #         resp = await session.post(..., json=...)
        #         resp.raise_for_status()
        #         data = await resp.json()
        #         if data.get("code") != 0:
        #             raise InvalidAuth
        # except aiohttp.ClientError:
        #     raise CannotConnect

        pass


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
