"""The Minecraft Server sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_TYPE, EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import MinecraftServerData, MinecraftServerType
from .const import DOMAIN, KEY_LATENCY, KEY_MOTD
from .coordinator import MinecraftServerConfigEntry, MinecraftServerCoordinator
from .entity import MinecraftServerEntity

ATTR_PLAYERS_LIST = "players_list"
ATTR_PLUGINS = "plugins"
ATTR_SOFTWARE_VERSION = "software_version"

KEY_EDITION = "edition"
KEY_GAME_MODE = "game_mode"
KEY_MAP_NAME = "map_name"
KEY_PLAYERS_MAX = "players_max"
KEY_PLAYERS_ONLINE = "players_online"
KEY_PROTOCOL_VERSION = "protocol_version"
KEY_SOFTWARE = "software"
KEY_VERSION = "version"

UNIT_PLAYERS_MAX = "players"
UNIT_PLAYERS_ONLINE = "players"

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MinecraftServerSensorEntityDescription(SensorEntityDescription):
    """Class describing Minecraft Server sensor entities."""

    value_fn: Callable[[MinecraftServerData], StateType]
    attributes_fn: Callable[[MinecraftServerData], dict[str, Any]] | None
    supported_server_types: set[MinecraftServerType]
    requires_query: bool = False


def get_extra_state_attributes_players_list(
    data: MinecraftServerData,
) -> dict[str, list[str]]:
    """Return players list as extra state attributes, if available."""
    extra_state_attributes: dict[str, Any] = {}
    players_list = data.players_list

    if players_list is not None and len(players_list) != 0:
        extra_state_attributes[ATTR_PLAYERS_LIST] = players_list

    return extra_state_attributes


def get_extra_state_attributes_software(
    data: MinecraftServerData,
) -> dict[str, Any]:
    """Return software version and plugins as extra state attributes."""
    extra_state_attributes: dict[str, Any] = {}

    if data.software_version:
        extra_state_attributes[ATTR_SOFTWARE_VERSION] = data.software_version
    if data.plugins:
        extra_state_attributes[ATTR_PLUGINS] = data.plugins

    return extra_state_attributes


SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_VERSION,
        translation_key=KEY_VERSION,
        value_fn=lambda data: data.version,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PROTOCOL_VERSION,
        translation_key=KEY_PROTOCOL_VERSION,
        value_fn=lambda data: data.protocol_version,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_MAX,
        translation_key=KEY_PLAYERS_MAX,
        native_unit_of_measurement=UNIT_PLAYERS_MAX,
        value_fn=lambda data: data.players_max,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_LATENCY,
        translation_key=KEY_LATENCY,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: data.latency,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MOTD,
        translation_key=KEY_MOTD,
        value_fn=lambda data: data.motd,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_ONLINE,
        translation_key=KEY_PLAYERS_ONLINE,
        native_unit_of_measurement=UNIT_PLAYERS_ONLINE,
        value_fn=lambda data: data.players_online,
        attributes_fn=get_extra_state_attributes_players_list,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
            MinecraftServerType.BEDROCK_EDITION,
            MinecraftServerType.LEGACY_JAVA_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_EDITION,
        translation_key=KEY_EDITION,
        value_fn=lambda data: data.edition,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_GAME_MODE,
        translation_key=KEY_GAME_MODE,
        value_fn=lambda data: data.game_mode,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MAP_NAME,
        translation_key=KEY_MAP_NAME,
        value_fn=lambda data: data.map_name,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.BEDROCK_EDITION,
        },
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MAP_NAME,
        translation_key=KEY_MAP_NAME,
        value_fn=lambda data: data.map_name,
        attributes_fn=None,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
        },
        requires_query=True,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_SOFTWARE,
        translation_key=KEY_SOFTWARE,
        value_fn=lambda data: data.software_brand,
        attributes_fn=get_extra_state_attributes_software,
        supported_server_types={
            MinecraftServerType.JAVA_EDITION,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_query=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MinecraftServerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    coordinator = config_entry.runtime_data
    server_type = config_entry.data.get(CONF_TYPE, MinecraftServerType.JAVA_EDITION)
    entity_registry = er.async_get(hass)
    entities = []
    pending_query_descriptions = []

    for description in SENSOR_DESCRIPTIONS:
        if server_type not in description.supported_server_types:
            # Remove existing stale entity (e.g. after server type change)
            if entity_id := entity_registry.async_get_entity_id(
                Platform.SENSOR, DOMAIN, f"{config_entry.entry_id}-{description.key}"
            ):
                entity_registry.async_remove(entity_id)
        elif description.requires_query:
            pending_query_descriptions.append(description)
        else:
            entities.append(
                MinecraftServerSensorEntity(coordinator, description, config_entry)
            )

    async_add_entities(entities)

    if not pending_query_descriptions:
        return

    @callback
    def _async_add_query_entities() -> None:
        """Add sensors based on the query protocol as soon as it is available."""
        if not coordinator.data.query_available:
            return

        async_add_entities(
            MinecraftServerSensorEntity(coordinator, description, config_entry)
            for description in pending_query_descriptions
        )
        pending_query_descriptions.clear()
        remove_listener()

    remove_listener = coordinator.async_add_listener(_async_add_query_entities)
    config_entry.async_on_unload(remove_listener)
    _async_add_query_entities()


class MinecraftServerSensorEntity(MinecraftServerEntity, SensorEntity):
    """Representation of a Minecraft Server sensor base entity."""

    entity_description: MinecraftServerSensorEntityDescription
    _unrecorded_attributes = frozenset({ATTR_PLUGINS})

    def __init__(
        self,
        coordinator: MinecraftServerCoordinator,
        description: MinecraftServerSensorEntityDescription,
        config_entry: MinecraftServerConfigEntry,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._update_properties()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_properties()
        self.async_write_ha_state()

    @callback
    def _update_properties(self) -> None:
        """Update sensor properties."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )

        if func := self.entity_description.attributes_fn:
            self._attr_extra_state_attributes = func(self.coordinator.data)
