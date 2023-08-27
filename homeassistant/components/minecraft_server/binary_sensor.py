"""The Minecraft Server binary sensor platform."""
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MinecraftServerDataUpdateCoordinator
from .entity import MinecraftServerEntity, MinecraftServerEntityDescriptionMixin

ICON_STATUS = "mdi:lan"
KEY_STATUS = "status"


@dataclass
class MinecraftServerBinarySensorEntityDescription(
    BinarySensorEntityDescription, MinecraftServerEntityDescriptionMixin
):
    """Class describing Minecraft Server binary sensor entities."""


STATUS_BINARY_SENSOR_DESCRIPTION = MinecraftServerBinarySensorEntityDescription(
    key=KEY_STATUS,
    translation_key=KEY_STATUS,
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    icon=ICON_STATUS,
    value_fn=lambda x: None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Minecraft Server binary sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create entities list.
    entities = [
        MinecraftServerStatusBinarySensor(coordinator, STATUS_BINARY_SENSOR_DESCRIPTION)
    ]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class MinecraftServerStatusBinarySensor(MinecraftServerEntity, BinarySensorEntity):
    """Representation of a Minecraft Server status binary sensor."""

    entity_description: MinecraftServerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MinecraftServerDataUpdateCoordinator,
        description: MinecraftServerBinarySensorEntityDescription,
    ) -> None:
        """Initialize status binary sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_is_on = False
        self._attr_unique_id = f"{coordinator.unique_id}-{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Update status."""
        return self.coordinator.last_update_success
