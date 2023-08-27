"""Config flow for Minecraft Server integration."""
from typing import Any

from mcstatus import BedrockServer, JavaServer
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_QUERY_ENABLED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TYPE_BEDROCK,
    TYPE_JAVA,
)

DEFAULT_ADDRESS = "localhost:25565"
DEFAULT_NAME = "Minecraft Server"


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 4

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            title = address
            server: BedrockServer | JavaServer
            server_type: str | None = None
            # Some bedrock servers mimic a Java server,
            # therefore check if it is a bedrock server first.
            bedrock_server = await self._async_is_bedrock_server(address)
            if bedrock_server is not None:
                server = bedrock_server
                server_type = TYPE_BEDROCK
            else:
                java_server = await self._async_is_java_server(address)
                if java_server is not None:
                    server = java_server
                    server_type = TYPE_JAVA
                else:
                    errors["base"] = "cannot_connect"

            if server_type is not None:
                port = server.address.port

                # Validate port configuration (limit to user and dynamic port range).
                if (port < 1024) or (port > 65535):
                    errors["base"] = "invalid_port"
                # Validate host and port by checking the server connection.
                else:
                    # Configuration data are available and no error was detected,
                    # create configuration entry.
                    config_data = {
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_ADDRESS: address,
                        CONF_TYPE: server_type,
                    }
                    options = {
                        CONF_QUERY_ENABLED: False,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    }
                    return self.async_create_entry(
                        title=title, data=config_data, options=options
                    )

        # Show configuration form (default form in case of no user_input,
        # form filled with user_input and eventually with errors otherwise).
        return self._show_config_form(user_input, errors)

    def _show_config_form(self, user_input=None, errors=None) -> FlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_ADDRESS,
                        default=user_input.get(CONF_ADDRESS, DEFAULT_ADDRESS),
                    ): vol.All(str, vol.Lower),
                }
            ),
            errors=errors,
        )

    async def _async_is_java_server(self, address) -> JavaServer | None:
        """Check if the server is of type 'Java Edition'."""
        server: JavaServer

        try:
            server = JavaServer.lookup(address)
        except ValueError:
            return None

        try:
            await server.async_status()
        except OSError:
            return None

        return server

    async def _async_is_bedrock_server(self, address) -> BedrockServer | None:
        """Check if the server is of type 'Bedrock Edition'."""
        server: BedrockServer

        try:
            server = BedrockServer.lookup(address)
        except ValueError:
            return None

        try:
            await server.async_status()
        except OSError:
            return None

        return server

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""

        return MinecraftServerOptionsFlowHandler(config_entry)


class MinecraftServerOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Minecraft Server."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options[CONF_SCAN_INTERVAL],
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        step=1,
                        unit_of_measurement=UnitOfTime.SECONDS,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        if self.config_entry.data[CONF_TYPE] == TYPE_JAVA:
            data_schema = data_schema.extend(
                {
                    vol.Required(
                        CONF_QUERY_ENABLED,
                        default=self.config_entry.options[CONF_QUERY_ENABLED],
                    ): selector.BooleanSelector(),
                }
            )

        return self.async_show_form(step_id="init", data_schema=data_schema)
