"""Base entity for the Minecraft Server integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, TYPE_JAVA
from .coordinator import MinecraftServerData, MinecraftServerDataUpdateCoordinator


@dataclass
class MinecraftServerEntityDescriptionMixin:
    """Mixin values for Minecraft Server entities."""

    value_fn: Callable[[MinecraftServerData], StateType]


class MinecraftServerEntity(CoordinatorEntity[MinecraftServerDataUpdateCoordinator]):
    """Representation of a Minecraft Server base entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: MinecraftServerDataUpdateCoordinator,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator=coordinator)
        if self.coordinator.server_type == TYPE_JAVA:
            model = "Minecraft Server (Java Edition)"
        else:
            model = "Minecraft Server (Bedrock Edition)"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer=MANUFACTURER,
            model=model,
            name=self.coordinator.name,
            sw_version=f"{self.coordinator.data.version} ({self.coordinator.data.protocol_version})",
        )
