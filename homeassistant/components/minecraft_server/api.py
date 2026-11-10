"""API for the Minecraft Server integration."""

import asyncio
from dataclasses import dataclass
from enum import StrEnum
import logging

from dns.resolver import LifetimeTimeout
from mcstatus import BedrockServer, JavaServer, LegacyServer
from mcstatus.responses import (
    BedrockStatusResponse,
    JavaStatusResponse,
    LegacyStatusResponse,
    QueryResponse,
)

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

LOOKUP_TIMEOUT: float = 10
DATA_UPDATE_TIMEOUT: float = 10
DATA_UPDATE_RETRIES: int = 3
QUERY_TIMEOUT: float = 3
QUERY_RETRY_INTERVAL: int = 10


@dataclass
class MinecraftServerData:
    """Representation of Minecraft Server data."""

    # Common data
    latency: float
    motd: str
    players_max: int
    players_online: int
    protocol_version: int
    version: str

    # Data available only in 'Java Edition'
    players_list: list[str] | None = None

    # Data available only in 'Java Edition' with enabled query protocol
    query_available: bool = False
    software_brand: str | None = None
    software_version: str | None = None
    plugins: list[str] | None = None

    # Data available only in 'Bedrock Edition'
    edition: str | None = None
    game_mode: str | None = None
    map_name: str | None = None


class MinecraftServerType(StrEnum):
    """Enumeration of Minecraft Server types."""

    LEGACY_JAVA_EDITION = "Legacy Java Edition"
    JAVA_EDITION = "Java Edition"
    BEDROCK_EDITION = "Bedrock Edition"


class MinecraftServerAddressError(Exception):
    """Raised when the input address is invalid."""


class MinecraftServerConnectionError(Exception):
    """Raised when no data can be fechted from the server."""


class MinecraftServerNotInitializedError(Exception):
    """Raised when APIs are used although server instance is not initialized yet."""


class MinecraftServer:
    """Minecraft Server wrapper class for 3rd party library mcstatus."""

    _server: BedrockServer | JavaServer | LegacyServer | None

    def __init__(
        self,
        hass: HomeAssistant,
        server_type: MinecraftServerType,
        address: str,
        query_port: int | None = None,
    ) -> None:
        """Initialize server instance."""
        self._server = None
        self._query_port = query_port
        self._query_ever_succeeded = False
        self._query_skip_count = 0
        self._hass = hass
        self._server_type = server_type
        self._address = address

    async def async_initialize(self) -> None:
        """Perform async initialization of server instance."""
        try:
            if self._server_type == MinecraftServerType.JAVA_EDITION:
                self._server = await JavaServer.async_lookup(self._address)
            elif self._server_type == MinecraftServerType.BEDROCK_EDITION:
                self._server = await self._hass.async_add_executor_job(
                    BedrockServer.lookup, self._address
                )
            else:
                self._server = await LegacyServer.async_lookup(self._address)
        except (ValueError, LifetimeTimeout) as error:
            raise MinecraftServerAddressError(
                f"Lookup of '{self._address}' failed: {self._get_error_message(error)}"
            ) from error

        self._server.timeout = DATA_UPDATE_TIMEOUT

        if self._query_port is not None and isinstance(self._server, JavaServer):
            self._server.query_port = self._query_port

        _LOGGER.debug(
            "Initialized %s server instance with address '%s'",
            self._server_type,
            self._address,
        )

    async def async_is_online(self) -> bool:
        """Check if the server is online."""
        try:
            await self.async_get_data()
        except (
            MinecraftServerConnectionError,
            MinecraftServerNotInitializedError,
        ) as error:
            _LOGGER.debug(
                "Connection check of %s server failed: %s",
                self._server_type,
                self._get_error_message(error),
            )
            return False

        return True

    async def async_get_data(self) -> MinecraftServerData:
        """Get updated data from the server."""
        status_response: (
            BedrockStatusResponse | JavaStatusResponse | LegacyStatusResponse
        )

        if self._server is None:
            raise MinecraftServerNotInitializedError(
                f"Server instance with address '{self._address}' is not initialized"
            )

        try:
            status_response = await self._server.async_status(tries=DATA_UPDATE_RETRIES)
        except OSError as error:
            raise MinecraftServerConnectionError(
                f"Status request to '{self._address}' failed: "
                f"{self._get_error_message(error)}"
            ) from error

        if isinstance(status_response, JavaStatusResponse):
            data = self._extract_java_data(status_response)
            if isinstance(self._server, JavaServer):
                await self._async_add_query_data(self._server, data)
        elif isinstance(status_response, BedrockStatusResponse):
            data = self._extract_bedrock_data(status_response)
        else:
            data = self._extract_legacy_data(status_response)

        return data

    def _extract_java_data(
        self, status_response: JavaStatusResponse
    ) -> MinecraftServerData:
        """Extract Java Edition server data out of status response."""
        players_list: list[str] = []

        if players := status_response.players.sample:
            players_list.extend(player.name for player in players)
            players_list.sort()

        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            players_list=players_list,
        )

    async def _async_add_query_data(
        self, server: JavaServer, data: MinecraftServerData
    ) -> None:
        """Add data of the query protocol to the data, if the server supports it."""
        # Servers without query support are probed only occasionally.
        if not self._query_ever_succeeded:
            if self._query_skip_count > 0:
                self._query_skip_count -= 1
                return
            self._query_skip_count = QUERY_RETRY_INTERVAL - 1

        try:
            async with asyncio.timeout(QUERY_TIMEOUT):
                query_response = await server.async_query(tries=1)
        except (OSError, ValueError, KeyError) as error:
            _LOGGER.debug(
                "Query request to '%s' failed: %s",
                self._address,
                self._get_error_message(error),
            )
            return

        self._query_ever_succeeded = True
        self._apply_query_response(data, query_response)

    def _apply_query_response(
        self, data: MinecraftServerData, query_response: QueryResponse
    ) -> None:
        """Apply query response to the server data."""
        data.query_available = True
        data.map_name = query_response.map_name
        data.players_list = sorted(query_response.players.list)
        data.software_brand = query_response.software.brand
        data.software_version = query_response.software.version
        data.plugins = query_response.software.plugins

    def _extract_bedrock_data(
        self, status_response: BedrockStatusResponse
    ) -> MinecraftServerData:
        """Extract Bedrock Edition server data out of status response."""
        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            edition=status_response.version.brand,
            game_mode=status_response.gamemode,
            map_name=status_response.map_name,
        )

    def _extract_legacy_data(
        self, status_response: LegacyStatusResponse
    ) -> MinecraftServerData:
        """Extract legacy Java Edition server data out of status response."""
        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
        )

    def _get_error_message(self, error: BaseException) -> str:
        """Get error message of an exception."""
        if not str(error):
            # Fallback to error type in case of an empty error message.
            return repr(error)

        return str(error)
