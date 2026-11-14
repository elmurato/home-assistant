"""Tests for Minecraft Server repair issues."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import BedrockServer, JavaServer
from mcstatus.responses import JavaStatusResponse, QueryResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import (
    CONF_ENABLE_QUERY,
    CONF_QUERY_PORT,
    DOMAIN,
    ISSUE_QUERY_FAILED,
)
from homeassistant.components.repairs import (
    DOMAIN as REPAIRS_DOMAIN,
    repairs_flow_manager,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
    TEST_QUERY_PORT,
    TEST_QUERY_RESPONSE,
)


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the next scheduled update."""
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "issue_data",
    [
        pytest.param(None, id="no-data"),
        pytest.param({}, id="missing-entry-id"),
        pytest.param({"entry_id": 123}, id="invalid-entry-id"),
    ],
)
async def test_repair_with_invalid_issue_data(
    hass: HomeAssistant,
    issue_data: dict[str, str | int | float | None] | None,
) -> None:
    """Reject repair issues without a valid config entry ID."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
    assert await async_setup_component(hass, DOMAIN, {})
    issue_id = f"{ISSUE_QUERY_FAILED}_invalid"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data=issue_data,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_QUERY_FAILED,
        translation_placeholders={"name": "Minecraft server"},
    )

    with pytest.raises(
        ValueError, match=f"Missing config entry ID for repair {issue_id}"
    ):
        await repairs_flow_manager(hass).async_init(
            DOMAIN, context={"issue_id": issue_id}
        )


@pytest.mark.parametrize(
    ("status_results", "query_results", "issue_after_update"),
    [
        pytest.param(
            [TEST_JAVA_STATUS_RESPONSE] * 4,
            [OSError(), OSError(), OSError(), TEST_QUERY_RESPONSE],
            [False, False, True, False],
            id="threshold-and-recovery",
        ),
        pytest.param(
            [TEST_JAVA_STATUS_RESPONSE] * 5,
            [OSError(), TEST_QUERY_RESPONSE, OSError(), OSError(), OSError()],
            [False, False, False, False, True],
            id="query-success-resets-streak",
        ),
        pytest.param(
            [
                TEST_JAVA_STATUS_RESPONSE,
                TEST_JAVA_STATUS_RESPONSE,
                OSError(),
                TEST_JAVA_STATUS_RESPONSE,
                TEST_JAVA_STATUS_RESPONSE,
                TEST_JAVA_STATUS_RESPONSE,
            ],
            [OSError()] * 5,
            [False, False, False, False, False, True],
            id="status-failure-resets-streak",
        ),
    ],
)
async def test_query_issue_threshold(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    status_results: list[JavaStatusResponse | OSError],
    query_results: list[QueryResponse | OSError],
    issue_after_update: list[bool],
) -> None:
    """Create an issue after three consecutive failed query updates and clear it."""
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            side_effect=status_results,
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            side_effect=query_results,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert (issue_registry.async_get_issue(DOMAIN, issue_id) is not None) == (
            issue_after_update[0]
        )

        for expected in issue_after_update[1:]:
            await _refresh(hass, freezer)
            assert (issue_registry.async_get_issue(DOMAIN, issue_id) is not None) == (
                expected
            )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_disable_query_repair(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    hass_client: ClientSessionGenerator,
) -> None:
    """Confirming the repair disables query and preserves the query port."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT}
    )
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"
    query = AsyncMock(side_effect=OSError)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            query,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _refresh(hass, freezer)
        await _refresh(hass, freezer)
        issue = issue_registry.async_get_issue(DOMAIN, issue_id)
        assert issue is not None
        assert issue.is_fixable
        assert issue.config_entry_id == entry.entry_id
        assert issue.translation_key == ISSUE_QUERY_FAILED

        client = await hass_client()
        result = await start_repair_fix_flow(client, DOMAIN, issue_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert entry.options[CONF_ENABLE_QUERY] is True
        result = await process_repair_fix_flow(client, result["flow_id"], json={})
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options == {
            CONF_ENABLE_QUERY: False,
            CONF_QUERY_PORT: TEST_QUERY_PORT,
        }
        assert query.call_count == 3
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_issue_removed_when_query_disabled_in_options(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Disabling query in the options flow clears the issue."""
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _refresh(hass, freezer)
        await _refresh(hass, freezer)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ENABLE_QUERY: False}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_disable_query_repair_reload_fails(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Report a reload failure without marking the repair as fixed."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"
    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            config_entry_id=entry.entry_id,
            data={"entry_id": entry.entry_id},
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_QUERY_FAILED,
            translation_placeholders={"name": entry.title},
        )
        client = await hass_client()
        result = await start_repair_fix_flow(client, DOMAIN, issue_id)
        with patch.object(hass.config_entries, "async_reload", return_value=False):
            result = await process_repair_fix_flow(client, result["flow_id"], json={})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "reload_failed"}
    assert entry.options[CONF_ENABLE_QUERY] is False
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_query_issues_are_independent(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Recovery of one server does not clear another server's issue."""
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    other = MockConfigEntry(
        domain=DOMAIN,
        title="other server",
        data={
            CONF_ADDRESS: "other.example:25565",
            CONF_TYPE: MinecraftServerType.JAVA_EDITION,
        },
        options={CONF_ENABLE_QUERY: True},
        version=3,
    )
    other.add_to_hass(hass)
    first_server = JavaServer(host=TEST_HOST, port=TEST_PORT)
    second_server = JavaServer(host="other.example", port=TEST_PORT)
    first_query = AsyncMock(side_effect=OSError)
    second_query = AsyncMock(side_effect=OSError)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            side_effect=[first_server, second_server],
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
        patch.object(first_server, "async_query", first_query),
        patch.object(second_server, "async_query", second_query),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert other.state is ConfigEntryState.LOADED
        await _refresh(hass, freezer)
        await _refresh(hass, freezer)
        first_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"
        second_id = f"{ISSUE_QUERY_FAILED}_{other.entry_id}"
        assert issue_registry.async_get_issue(DOMAIN, first_id) is not None
        assert issue_registry.async_get_issue(DOMAIN, second_id) is not None
        first_query.side_effect = None
        first_query.return_value = TEST_QUERY_RESPONSE
        await _refresh(hass, freezer)
        assert issue_registry.async_get_issue(DOMAIN, first_id) is None
        assert issue_registry.async_get_issue(DOMAIN, second_id) is not None


async def test_issue_removed_after_edition_change(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Changing to Bedrock clears the query issue despite saved options."""
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
            return_value=BedrockServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
            return_value=TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _refresh(hass, freezer)
        await _refresh(hass, freezer)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TYPE: MinecraftServerType.BEDROCK_EDITION}
        )
        assert await hass.config_entries.async_reload(entry.entry_id)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
        assert entry.options[CONF_ENABLE_QUERY] is True


async def test_query_issue_removed_with_entry(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Remove the issue when the entry is removed."""
    entry = java_mock_config_entry
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})
    issue_id = f"{ISSUE_QUERY_FAILED}_{entry.entry_id}"

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _refresh(hass, freezer)
        await _refresh(hass, freezer)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
        await hass.config_entries.async_remove(entry.entry_id)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
