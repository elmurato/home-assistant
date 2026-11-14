"""Tests for Minecraft Server sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import BedrockServer, JavaServer, LegacyServer
from mcstatus.responses import (
    BedrockStatusResponse,
    JavaStatusResponse,
    LegacyStatusResponse,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import CONF_ENABLE_QUERY
from homeassistant.const import CONF_TYPE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import (
    ENTITY_ID_MAP_NAME,
    ENTITY_ID_SOFTWARE,
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_LEGACY_JAVA_STATUS_RESPONSE,
    TEST_PORT,
    TEST_QUERY_RESPONSE,
)

ENTITY_ID_PLAYERS_ONLINE = "sensor.mc_dummyserver_com_25566_players_online"

JAVA_SENSOR_ENTITIES: list[str] = [
    "sensor.mc_dummyserver_com_25566_latency",
    "sensor.mc_dummyserver_com_25566_players_online",
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_world_message",
    "sensor.mc_dummyserver_com_25566_version",
    "sensor.mc_dummyserver_com_25566_protocol_version",
]

JAVA_SENSOR_ENTITIES_DISABLED_BY_DEFAULT: list[str] = [
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_protocol_version",
]

BEDROCK_SENSOR_ENTITIES: list[str] = [
    "sensor.mc_dummyserver_com_25566_latency",
    "sensor.mc_dummyserver_com_25566_players_online",
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_world_message",
    "sensor.mc_dummyserver_com_25566_version",
    "sensor.mc_dummyserver_com_25566_protocol_version",
    "sensor.mc_dummyserver_com_25566_map_name",
    "sensor.mc_dummyserver_com_25566_game_mode",
    "sensor.mc_dummyserver_com_25566_edition",
]

BEDROCK_SENSOR_ENTITIES_DISABLED_BY_DEFAULT: list[str] = [
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_protocol_version",
    "sensor.mc_dummyserver_com_25566_edition",
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
        (
            "legacy_java_mock_config_entry",
            LegacyServer,
            "async_lookup",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer | LegacyServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse | LegacyStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES_DISABLED_BY_DEFAULT,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES_DISABLED_BY_DEFAULT,
        ),
        (
            "legacy_java_mock_config_entry",
            LegacyServer,
            "async_lookup",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES_DISABLED_BY_DEFAULT,
        ),
    ],
)
async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer | LegacyServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse | LegacyStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
) -> None:
    """Test sensor, which is disabled by default."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert not hass.states.get(entity_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
        (
            "legacy_java_mock_config_entry",
            LegacyServer,
            "async_lookup",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer | LegacyServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse | LegacyStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id) == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
        (
            "legacy_java_mock_config_entry",
            LegacyServer,
            "async_lookup",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer | LegacyServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse | LegacyStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failed sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        side_effect=OSError,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("server_type", "server", "lookup_function_name", "status_response"),
    [
        (
            MinecraftServerType.JAVA_EDITION,
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
        ),
        (
            MinecraftServerType.LEGACY_JAVA_EDITION,
            LegacyServer,
            "async_lookup",
            TEST_LEGACY_JAVA_STATUS_RESPONSE,
        ),
    ],
    ids=["java", "legacy_java"],
)
async def test_sensor_entities_removed_when_edition_changes(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    bedrock_mock_config_entry: MockConfigEntry,
    server_type: MinecraftServerType,
    server: JavaServer | LegacyServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | LegacyStatusResponse,
) -> None:
    """Test Bedrock-only sensors are removed after switching to another edition."""
    bedrock_mock_config_entry.add_to_hass(hass)
    bedrock_only_entity_ids = set(BEDROCK_SENSOR_ENTITIES) - set(JAVA_SENSOR_ENTITIES)

    with (
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
            return_value=BedrockServer(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
            return_value=TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ):
        assert await hass.config_entries.async_setup(bedrock_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    registered_entity_ids = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, bedrock_mock_config_entry.entry_id
        )
    }

    for entity_id in bedrock_only_entity_ids:
        assert entity_id in registered_entity_ids

    hass.config_entries.async_update_entry(
        bedrock_mock_config_entry,
        data={
            **bedrock_mock_config_entry.data,
            CONF_TYPE: server_type,
        },
    )

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_reload(
            bedrock_mock_config_entry.entry_id
        )
        await hass.async_block_till_done()

    remaining_entity_ids = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, bedrock_mock_config_entry.entry_id
        )
    }
    for entity_id in bedrock_only_entity_ids:
        assert entity_id not in remaining_entity_ids
        assert hass.states.get(entity_id) is None

    for entity_id in JAVA_SENSOR_ENTITIES:
        assert entity_id in remaining_entity_ids


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
