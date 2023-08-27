"""The Minecraft Server sensor platform."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_QUERY_ENABLED,
    DOMAIN,
    KEY_LATENCY,
    KEY_MOTD,
    TYPE_BEDROCK,
    TYPE_JAVA,
)
from .coordinator import MinecraftServerDataUpdateCoordinator
from .entity import MinecraftServerEntity, MinecraftServerEntityDescriptionMixin

KEY_PLAYERS_MAX = "players_max"
KEY_PLAYERS_ONLINE = "players_online"
KEY_PROTOCOL_VERSION = "protocol_version"
KEY_VERSION = "version"
KEY_EDITION = "edition"
KEY_MAP_NAME = "map_name"
KEY_GAME_MODE = "game_mode"


@dataclass
class MinecraftServerSensorEntityDescription(
    SensorEntityDescription, MinecraftServerEntityDescriptionMixin
):
    """Class describing Minecraft Server sensor entities."""


COMMON_SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_VERSION,
        translation_key=KEY_VERSION,
        icon="mdi:numeric",
        value_fn=lambda x: x.version if x else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PROTOCOL_VERSION,
        translation_key=KEY_PROTOCOL_VERSION,
        icon="mdi:numeric",
        value_fn=lambda x: x.protocol_version if x else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_PLAYERS_MAX,
        translation_key=KEY_PLAYERS_MAX,
        native_unit_of_measurement="players",
        icon="mdi:account-multiple",
        value_fn=lambda x: x.players_max if x else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_LATENCY,
        translation_key=KEY_LATENCY,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        icon="mdi:signal",
        value_fn=lambda x: x.latency if x else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MOTD,
        translation_key=KEY_MOTD,
        icon="mdi:minecraft",
        value_fn=lambda x: x.motd if x else None,
    ),
]

PLAYERS_ONLINE_SENSOR_DESCRIPTION = MinecraftServerSensorEntityDescription(
    key=KEY_PLAYERS_ONLINE,
    translation_key=KEY_PLAYERS_ONLINE,
    native_unit_of_measurement="players",
    icon="mdi:account-multiple",
    value_fn=lambda x: None,
)

JAVA_QUERY_OR_BEDROCK_SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_EDITION,
        translation_key=KEY_EDITION,
        icon="mdi:minecraft",
        value_fn=lambda x: x.edition if x else None,
    ),
    MinecraftServerSensorEntityDescription(
        key=KEY_MAP_NAME,
        translation_key=KEY_MAP_NAME,
        icon="mdi:map",
        value_fn=lambda x: x.map_name if x else None,
    ),
]

BEDROCK_SENSOR_DESCRIPTIONS = [
    MinecraftServerSensorEntityDescription(
        key=KEY_GAME_MODE,
        translation_key=KEY_GAME_MODE,
        icon="mdi:cog",
        value_fn=lambda x: x.game_mode if x else None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities list.
    entities = []

    for description in COMMON_SENSOR_DESCRIPTIONS:
        entities.append(
            MinecraftServerSensorEntity(
                coordinator=coordinator, description=description
            )
        )

    entities.append(
        MinecraftServerPlayersOnlineSensor(
            coordinator=coordinator, description=PLAYERS_ONLINE_SENSOR_DESCRIPTION
        )
    )

    if (
        config_entry.data[CONF_TYPE] == TYPE_JAVA
        and config_entry.options[CONF_QUERY_ENABLED]
    ):
        for description in JAVA_QUERY_OR_BEDROCK_SENSOR_DESCRIPTIONS:
            entities.append(
                MinecraftServerSensorEntity(
                    coordinator=coordinator, description=description
                )
            )
    elif config_entry.data[CONF_TYPE] == TYPE_BEDROCK:
        for description in JAVA_QUERY_OR_BEDROCK_SENSOR_DESCRIPTIONS:
            entities.append(
                MinecraftServerSensorEntity(
                    coordinator=coordinator, description=description
                )
            )
        for description in BEDROCK_SENSOR_DESCRIPTIONS:
            entities.append(
                MinecraftServerSensorEntity(
                    coordinator=coordinator, description=description
                )
            )

    # Add sensor entities.
    async_add_entities(entities, True)


class MinecraftServerSensorEntity(MinecraftServerEntity, SensorEntity):
    """Representation of a Minecraft Server sensor base entity."""

    entity_description: MinecraftServerSensorEntityDescription

    def __init__(
        self,
        coordinator: MinecraftServerDataUpdateCoordinator,
        description: MinecraftServerSensorEntityDescription,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return self.coordinator.online

    @property
    def native_value(
        self,
        # ) -> StateType | date | datetime | Decimal:
    ) -> StateType:
        """Update sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)


class MinecraftServerPlayersOnlineSensor(MinecraftServerSensorEntity):
    """Representation of a Minecraft Server online players sensor."""

    def __init__(
        self,
        coordinator: MinecraftServerDataUpdateCoordinator,
        description: MinecraftServerSensorEntityDescription,
    ) -> None:
        """Initialize online players sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_unique_id = f"{coordinator.unique_id}-{self.entity_description.key}"

    @property
    def native_value(
        self,
        # ) -> StateType | date | datetime | Decimal:
    ) -> StateType:
        """Update online players state and device state attributes."""
        extra_state_attributes = {}
        players_list = self.coordinator.data.players_list

        if players_list is not None and len(players_list) != 0:
            extra_state_attributes["players_list"] = players_list

        self._attr_extra_state_attributes = extra_state_attributes

        return self.coordinator.data.players_online
