"""Data update coordinator for the Minecraft Server integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from mcstatus import BedrockServer
from mcstatus.querier import QueryResponse
from mcstatus.server import JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_QUERY_ENABLED, TYPE_JAVA

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
SCAN_INTERVAL = 60

_LOGGER = logging.getLogger(__name__)


@dataclass
class MinecraftServerData:
    """Representation of Minecraft server data."""

    # Common data
    latency: float
    motd: str
    players_max: int
    players_online: int
    version: str
    protocol_version: int

    # Data available only in 'Java Edition'
    players_list: list[str] | None

    # Data available only in 'Java Edition' with query protocol
    plugins_list: list[str] | None

    # Data available only in 'Bedrock Edition' or in 'Java Edition' with query protocol
    edition: str | None
    map_name: str | None

    # Data available only in 'Bedrock Edition'
    game_mode: str | None


class MinecraftServerDataUpdateCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    server: JavaServer | BedrockServer

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize server instance."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=config_entry.data[CONF_NAME],
            update_interval=timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL]),
        )

        # Config entry data
        self.unique_id = config_entry.entry_id
        self.address = config_entry.data[CONF_ADDRESS]
        self.server_type = config_entry.data[CONF_TYPE]

        # Server data
        if self.server_type == TYPE_JAVA:
            self.server = JavaServer.lookup(address=self.address)
        else:
            self.server = BedrockServer.lookup(address=self.address)
        self.host = self.server.address.host
        self.port = self.server.address.port
        self.online = False
        if self.server_type == TYPE_JAVA:
            self.query_enabled = config_entry.options[CONF_QUERY_ENABLED]
        else:
            self.query_enabled = False
        self.last_query_success = True

    async def _async_update_data(self) -> MinecraftServerData:
        """Get and update data from the server."""
        status_response: BedrockStatusResponse | JavaStatusResponse

        try:
            status_response = await self.server.async_status()
        except OSError as error:
            self.online = False
            # Inform data update coordinator about failed update.
            raise UpdateFailed(error) from error

        self.online = True
        query_response = await self.async_get_query_response()
        data: MinecraftServerData

        # Get 'Java Edition' data.
        if isinstance(status_response, JavaStatusResponse):
            data = await self.async_get_java_data_from_response(
                status_response, query_response
            )
        # Get 'Bedrock Edition' data.
        else:
            data = await self.async_get_bedrock_data_from_response(status_response)

        # Return updated data.
        return data

    async def async_get_query_response(self) -> QueryResponse | None:
        """Get query response from the server."""
        query_response: QueryResponse | None = None
        if self.query_enabled:
            try:
                query_response = await self.server.async_query()  # type: ignore[union-attr]
            except OSError as error:
                query_response = None
                if self.last_query_success:
                    _LOGGER.warning(
                        "Error fetching %s query data, falling back to status protocol only: %s",
                        self.name,
                        error,
                    )
                self.last_query_success = False
            else:
                if not self.last_query_success:
                    _LOGGER.debug("Fetching %s query data recovered", self.name)
                self.last_query_success = True

        return query_response

    async def async_get_java_data_from_response(
        self, status_response: JavaStatusResponse, query_response: QueryResponse | None
    ) -> MinecraftServerData:
        """Get 'Java Edition' data from status/query response."""
        if query_response is not None:
            if query_response.players.names is not None:
                players_list = query_response.players.names

            map_name = query_response.map
            edition = query_response.software.brand
            plugins_list = query_response.software.plugins
        else:
            players_list = []
            if status_response.players.sample is not None:
                for player in status_response.players.sample:
                    players_list.append(player.name)

            map_name = None
            edition = None
            plugins_list = None

        players_list.sort()

        return MinecraftServerData(
            version=status_response.version.name,
            protocol_version=status_response.version.protocol,
            players_online=status_response.players.online,
            players_max=status_response.players.max,
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_list=players_list,
            edition=edition,
            map_name=map_name,
            game_mode=None,
            plugins_list=plugins_list,
        )

    async def async_get_bedrock_data_from_response(
        self, response: BedrockStatusResponse
    ) -> MinecraftServerData:
        """Get 'Bedrock Edition' data from status response."""
        return MinecraftServerData(
            version=response.version.name,
            protocol_version=response.version.protocol,
            players_online=response.players.online,
            players_max=response.players.max,
            latency=response.latency,
            motd=response.motd.to_plain(),
            players_list=None,
            edition=response.version.brand,
            map_name=response.map_name,
            game_mode=response.gamemode,
            plugins_list=None,
        )
