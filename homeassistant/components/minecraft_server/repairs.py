"""Repair flows for Minecraft Server."""

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_ENABLE_QUERY


class DisableQueryRepairFlow(RepairsFlow):
    """Disable the query protocol after user confirmation."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Start the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm disabling the query protocol."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_known_entry(self._entry_id)
            self.hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_ENABLE_QUERY: False}
            )
            if not await self.hass.config_entries.async_reload(entry.entry_id):
                return self.async_show_form(
                    step_id="confirm", errors={"base": "reload_failed"}
                )
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the query repair flow."""
    if data is None or not isinstance(entry_id := data.get("entry_id"), str):
        raise ValueError(f"Missing config entry ID for repair {issue_id}")
    return DisableQueryRepairFlow(entry_id)
