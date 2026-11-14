"""The Minecraft Server integration."""

from datetime import timedelta
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MinecraftServer,
    MinecraftServerAddressError,
    MinecraftServerConnectionError,
    MinecraftServerData,
    MinecraftServerNotInitializedError,
    MinecraftServerType,
)
from .const import CONF_ENABLE_QUERY, CONF_QUERY_PORT, DOMAIN, ISSUE_QUERY_FAILED

type MinecraftServerConfigEntry = ConfigEntry[MinecraftServerCoordinator]

SCAN_INTERVAL = timedelta(seconds=60)
QUERY_FAILURE_THRESHOLD = 3

_LOGGER = logging.getLogger(__name__)


class MinecraftServerCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    config_entry: MinecraftServerConfigEntry
    _api: MinecraftServer

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MinecraftServerConfigEntry,
    ) -> None:
        """Initialize coordinator instance."""

        super().__init__(
            hass=hass,
            name=config_entry.title,
            config_entry=config_entry,
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )
        self._query_failures = 0

    @override
    async def _async_setup(self) -> None:
        """Set up the Minecraft Server data coordinator."""

        server_type = self.config_entry.data.get(
            CONF_TYPE, MinecraftServerType.JAVA_EDITION
        )
        self._api = MinecraftServer(
            self.hass,
            server_type,
            self.config_entry.data[CONF_ADDRESS],
            query_enabled=(
                server_type == MinecraftServerType.JAVA_EDITION
                and self.config_entry.options.get(CONF_ENABLE_QUERY, False)
            ),
            query_port=self.config_entry.options.get(
                CONF_QUERY_PORT, self.config_entry.data.get(CONF_QUERY_PORT)
            ),
        )
        if not (
            server_type == MinecraftServerType.JAVA_EDITION
            and self.config_entry.options.get(CONF_ENABLE_QUERY, False)
        ):
            ir.async_delete_issue(
                self.hass, DOMAIN, f"{ISSUE_QUERY_FAILED}_{self.config_entry.entry_id}"
            )

        try:
            await self._api.async_initialize()
        except MinecraftServerAddressError as error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="address_lookup_failed",
                translation_placeholders={
                    "address": self.config_entry.data[CONF_ADDRESS]
                },
            ) from error

    @override
    async def _async_update_data(self) -> MinecraftServerData:
        """Get updated data from the server."""
        try:
            data = await self._api.async_get_data()
        except (
            MinecraftServerConnectionError,
            MinecraftServerNotInitializedError,
        ) as error:
            self._query_failures = 0
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="data_update_failed",
                translation_placeholders={
                    "address": self.config_entry.data[CONF_ADDRESS]
                },
            ) from error

        issue_id = f"{ISSUE_QUERY_FAILED}_{self.config_entry.entry_id}"
        if self._api.query_failed:
            self._query_failures += 1
            if self._query_failures >= QUERY_FAILURE_THRESHOLD:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    config_entry_id=self.config_entry.entry_id,
                    is_fixable=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_QUERY_FAILED,
                    translation_placeholders={"name": self.config_entry.title},
                    data={"entry_id": self.config_entry.entry_id},
                )
        else:
            self._query_failures = 0
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return data
