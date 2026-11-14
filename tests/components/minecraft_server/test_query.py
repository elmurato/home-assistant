"""Tests for the query protocol support of the Minecraft Server integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import BedrockServer, JavaServer, LegacyServer
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.minecraft_server.const import (
    CONF_ENABLE_QUERY,
    CONF_QUERY_PORT,
    DOMAIN,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_LEGACY_JAVA_STATUS_RESPONSE,
    TEST_PORT,
    TEST_QUERY_PORT,
    TEST_QUERY_RESPONSE,
)

ENTITY_ID_SOFTWARE = "sensor.mc_dummyserver_com_25566_software"
ENTITY_ID_MAP_NAME = "sensor.mc_dummyserver_com_25566_map_name"
ENTITY_ID_PLAYERS_ONLINE = "sensor.mc_dummyserver_com_25566_players_online"


def _patch_server():
    """Patch the Java server lookup and status."""
    return (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_sensors(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test sensors provided by the query protocol."""
    java_mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        java_mock_config_entry, options={CONF_ENABLE_QUERY: True}
    )
    lookup, status = _patch_server()

    with (
        lookup,
        status,
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            return_value=TEST_QUERY_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    software = hass.states.get(ENTITY_ID_SOFTWARE)
    assert software.state == "Paper on 1.21.4"
    assert software.attributes["software_version"] == "1.21.4"
    assert software.attributes["plugins"] == ["PluginA 1.0", "PluginB 2.0"]
    assert hass.states.get(ENTITY_ID_MAP_NAME).state == "Dummy Query Map"
    assert hass.states.get(ENTITY_ID_PLAYERS_ONLINE).attributes["players_list"] == [
        "Query Player A",
        "Query Player B",
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_unavailable(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test query sensors are unknown when query protocol is not available."""
    java_mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        java_mock_config_entry, options={CONF_ENABLE_QUERY: True}
    )
    lookup, status = _patch_server()

    with lookup, status:
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_SOFTWARE).state == STATE_UNKNOWN
    assert hass.states.get(ENTITY_ID_MAP_NAME).state == STATE_UNKNOWN
    assert hass.states.get(ENTITY_ID_PLAYERS_ONLINE).attributes["players_list"] == [
        "Player 1",
        "Player 2",
        "Player 3",
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_retried_after_failure(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that query protocol is retried on the next update after a failure."""
    java_mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        java_mock_config_entry, options={CONF_ENABLE_QUERY: True}
    )
    lookup, status = _patch_server()
    query = AsyncMock(side_effect=OSError)

    with (
        lookup,
        status,
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            query,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID_SOFTWARE).state == STATE_UNKNOWN
        assert query.call_count == 1

        query.side_effect = None
        query.return_value = TEST_QUERY_RESPONSE

        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert query.call_count == 2
    assert hass.states.get(ENTITY_ID_SOFTWARE).state == "Paper on 1.21.4"
    assert hass.states.get(ENTITY_ID_MAP_NAME).state == "Dummy Query Map"


async def test_custom_query_port(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test that the configured query port is used."""
    java_mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        java_mock_config_entry,
        options={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT},
    )
    server = JavaServer(host=TEST_HOST, port=TEST_PORT)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
            return_value=server,
        ),
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_status",
            return_value=TEST_JAVA_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert server.query_port == TEST_QUERY_PORT


async def test_query_disabled_by_default(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test that query protocol requests are disabled by default."""
    java_mock_config_entry.add_to_hass(hass)
    lookup, status = _patch_server()
    query = AsyncMock(return_value=TEST_QUERY_RESPONSE)

    with (
        lookup,
        status,
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            query,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    query.assert_not_awaited()
    assert hass.states.get(ENTITY_ID_SOFTWARE) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_options_reload(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enabling and disabling query sensors through the options flow."""
    java_mock_config_entry.add_to_hass(hass)
    lookup, status = _patch_server()

    with (
        lookup,
        status,
        patch(
            "homeassistant.components.minecraft_server.api.JavaServer.async_query",
            return_value=TEST_QUERY_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID_SOFTWARE) is None
        assert hass.states.get(ENTITY_ID_MAP_NAME) is None

        result = await hass.config_entries.options.async_init(
            java_mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ENABLE_QUERY: True}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID_SOFTWARE).state == "Paper on 1.21.4"
        assert hass.states.get(ENTITY_ID_MAP_NAME).state == "Dummy Query Map"

        result = await hass.config_entries.options.async_init(
            java_mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ENABLE_QUERY: False}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_SOFTWARE).state == STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID_MAP_NAME) is None
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{java_mock_config_entry.entry_id}-software"
    )


@pytest.mark.parametrize(
    ("entry_fixture", "lookup_target", "server", "status_target", "status_response"),
    [
        pytest.param(
            "bedrock_mock_config_entry",
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
            BedrockServer(host=TEST_HOST, port=TEST_PORT),
            "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
            TEST_BEDROCK_STATUS_RESPONSE,
            id="bedrock",
        ),
        pytest.param(
            "legacy_java_mock_config_entry",
            "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
            LegacyServer(host=TEST_HOST, port=TEST_PORT),
            "homeassistant.components.minecraft_server.api.LegacyServer.async_status",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
            id="legacy_java",
        ),
    ],
)
async def test_saved_query_options_after_edition_change(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    lookup_target: str,
    server: BedrockServer | LegacyServer,
    status_target: str,
    status_response: object,
) -> None:
    """Test saved query options do not break other server editions."""
    entry: MockConfigEntry = request.getfixturevalue(entry_fixture)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_ENABLE_QUERY: True})

    with (
        patch(lookup_target, return_value=server),
        patch(status_target, return_value=status_response),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_SOFTWARE) is None
