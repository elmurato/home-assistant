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


@dataclass
class MinecraftServerData:
    """Representation of Minecraft Server data."""

    # Common data available for all server types
    latency: float
    motd: str
    players_max: int
    players_online: int
    protocol_version: int
    version: str

    # Server type specific data
    edition: str | None = None
    game_mode: str | None = None
    map_name: str | None = None
    players_list: list[str] | None = None
    plugins: list[str] | None = None
    software_brand: str | None = None
    software_version: str | None = None


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
        query_enabled: bool = False,
        query_port: int | None = None,
    ) -> None:
        """Initialize server instance."""
        self._server = None
        self._hass = hass
        self._server_type = server_type
        self._address = address
        self._query_enabled = query_enabled
        self._query_port = query_port
        self.query_failed: bool | None = None

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
        query_response: QueryResponse | None = None

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

        if self._query_enabled and isinstance(self._server, JavaServer):
            try:
                async with asyncio.timeout(QUERY_TIMEOUT):
                    query_response = await self._server.async_query(
                        tries=DATA_UPDATE_RETRIES
                    )
            except (OSError, ValueError, KeyError) as error:
                self.query_failed = True
                _LOGGER.debug(
                    "Query request to '%s' failed: %s",
                    self._address,
                    self._get_error_message(error),
                )
            else:
                self.query_failed = False

        if isinstance(status_response, JavaStatusResponse):
            data = self._extract_java_data(status_response, query_response)
        elif isinstance(status_response, BedrockStatusResponse):
            data = self._extract_bedrock_data(status_response)
        else:
            data = self._extract_legacy_data(status_response)

        return data

    def _extract_java_data(
        self,
        status_response: JavaStatusResponse,
        query_response: QueryResponse | None,
    ) -> MinecraftServerData:
        """Extract Java Edition server data from status and query responses."""
        players_list: list[str] = []

        if players := status_response.players.sample:
            players_list.extend(player.name for player in players)
            players_list.sort()

        data = MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            players_list=players_list,
        )

        if query_response is not None:
            data.map_name = query_response.map_name
            data.players_list = sorted(query_response.players.list)
            data.software_brand = query_response.software.brand
            data.software_version = query_response.software.version
            data.plugins = query_response.software.plugins

        return data

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
