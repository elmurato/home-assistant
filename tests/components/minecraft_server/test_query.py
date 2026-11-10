"""Tests for the query protocol support of the Minecraft Server integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import JavaServer
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.minecraft_server.api import QUERY_RETRY_INTERVAL
from homeassistant.components.minecraft_server.const import CONF_QUERY_PORT
from homeassistant.core import HomeAssistant

from .const import (
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
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
    """Test that no query sensors are created if the query protocol is not available."""
    java_mock_config_entry.add_to_hass(hass)
    lookup, status = _patch_server()

    with lookup, status:
        assert await hass.config_entries.async_setup(java_mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID_SOFTWARE) is None
    assert hass.states.get(ENTITY_ID_MAP_NAME) is None
    assert hass.states.get(ENTITY_ID_PLAYERS_ONLINE).attributes["players_list"] == [
        "Player 1",
        "Player 2",
        "Player 3",
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_becomes_available(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that query sensors are added once the query protocol becomes available."""
    java_mock_config_entry.add_to_hass(hass)
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
        assert hass.states.get(ENTITY_ID_SOFTWARE) is None
        assert query.call_count == 1

        query.side_effect = None
        query.return_value = TEST_QUERY_RESPONSE

        # The query protocol is not probed on every update.
        for _ in range(QUERY_RETRY_INTERVAL - 1):
            freezer.tick(timedelta(minutes=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        assert query.call_count == 1
        assert hass.states.get(ENTITY_ID_SOFTWARE) is None

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
        data={**java_mock_config_entry.data, CONF_QUERY_PORT: TEST_QUERY_PORT},
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
