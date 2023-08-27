"""The Minecraft Server integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from .const import (
    CONF_QUERY_ENABLED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_LATENCY,
    KEY_MOTD,
    TYPE_JAVA,
)
from .coordinator import MinecraftServerDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Server from a config entry."""
    coordinator = MinecraftServerDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Minecraft Server config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to a new format."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # 1 --> 2: Use config entry ID as base for unique IDs.
    if config_entry.version == 1:
        assert config_entry.unique_id
        old_unique_id = config_entry.unique_id
        config_entry_id = config_entry.entry_id

        # Migrate config entry.
        _LOGGER.debug("Migrating config entry, resetting unique ID: %s", old_unique_id)
        config_entry.unique_id = None
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry)

        # Migrate device.
        await _async_migrate_device_identifiers(hass, config_entry, old_unique_id)

        # Migrate entities.
        await er.async_migrate_entries(hass, config_entry_id, _migrate_entity_unique_id)

    # 2 --> 3: Use address in config entry instead of host and port.
    if config_entry.version == 2:
        assert config_entry.data

        address: str

        # Migrate config entry.
        if config_entry.data[CONF_PORT] is None:
            address = config_entry.data[CONF_HOST]
        else:
            address = f"{config_entry.data[CONF_HOST]}:{config_entry.data[CONF_PORT]}"

        _LOGGER.debug(
            "Migrating config entry, replacing host '%s' and port '%s' with address '%s'",
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            address,
        )

        data = {**config_entry.data, CONF_ADDRESS: address}
        data.pop(CONF_HOST)
        data.pop(CONF_PORT)
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=data)

    # 3 --> 4: Add server type and options (query and scan interval).
    if config_entry.version == 3:
        assert config_entry.data
        # Migrate config entry.
        # Already existing servers can only be of type Java Edition,
        # as Bedrock Edition server support was added in version 4.
        # Query option is disabled by default, as this option
        # must be manually activated within the server.
        _LOGGER.debug(
            "Migrating config entry, adding server type '%s' and 'query' option",
            TYPE_JAVA,
        )
        config_entry.version = 4
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_TYPE: TYPE_JAVA},
            options={
                CONF_QUERY_ENABLED: False,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            },
        )

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def _async_migrate_device_identifiers(
    hass: HomeAssistant, config_entry: ConfigEntry, old_unique_id: str | None
) -> None:
    """Migrate the device identifiers to the new format."""
    device_registry = dr.async_get(hass)
    device_entry_found = False
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        assert device_entry
        for identifier in device_entry.identifiers:
            if identifier[1] == old_unique_id:
                # Device found in registry. Update identifiers.
                new_identifiers = {
                    (
                        DOMAIN,
                        config_entry.entry_id,
                    )
                }
                _LOGGER.debug(
                    "Migrating device identifiers from %s to %s",
                    device_entry.identifiers,
                    new_identifiers,
                )
                device_registry.async_update_device(
                    device_id=device_entry.id, new_identifiers=new_identifiers
                )
                # Device entry found. Leave inner for loop.
                device_entry_found = True
                break

        # Leave outer for loop if device entry is already found.
        if device_entry_found:
            break


@callback
def _migrate_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
    """Migrate the unique ID of an entity to the new format."""
    assert entity_entry

    # Different variants of unique IDs are available in version 1:
    # 1) SRV record: '<host>-srv-<entity_type>'
    # 2) Host & port: '<host>-<port>-<entity_type>'
    # 3) IP address & port: '<mac_address>-<port>-<entity_type>'
    unique_id_pieces = entity_entry.unique_id.split("-")
    entity_type = unique_id_pieces[2]

    # Handle bug in version 1: Entity type names were used instead of
    # keys (e.g. "Protocol Version" instead of "protocol_version").
    new_entity_type = entity_type.lower()
    new_entity_type = new_entity_type.replace(" ", "_")

    # Special case 'MOTD': Name and key differs.
    if new_entity_type == "world_message":
        new_entity_type = KEY_MOTD

    # Special case 'latency_time': Renamed to 'latency'.
    if new_entity_type == "latency_time":
        new_entity_type = KEY_LATENCY

    new_unique_id = f"{entity_entry.config_entry_id}-{new_entity_type}"
    _LOGGER.debug(
        "Migrating entity unique ID from %s to %s",
        entity_entry.unique_id,
        new_unique_id,
    )

    return {"new_unique_id": new_unique_id}


async def async_options_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    _LOGGER.debug("Options changed, reloading config entry")
    await hass.config_entries.async_reload(entry.entry_id)
