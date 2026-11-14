"""Tests for the Minecraft Server config flow."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer, LegacyServer
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import (
    CONF_ENABLE_QUERY,
    CONF_QUERY_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_TYPE, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .const import (
    ENTITY_ID_MAP_NAME,
    ENTITY_ID_SOFTWARE,
    TEST_ADDRESS,
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_LEGACY_JAVA_STATUS_RESPONSE,
    TEST_PORT,
    TEST_QUERY_PORT,
    TEST_QUERY_RESPONSE,
)

SERVER_EDITION_CASE_PARAM_NAMES = (
    "server_type",
    "lookup_target",
    "lookup_result",
    "status_target",
    "status_response",
)

SERVER_EDITION_SUCCESS_CASES = [
    (
        MinecraftServerType.LEGACY_JAVA_EDITION,
        "homeassistant.components.minecraft_server.api.LegacyServer.async_lookup",
        lambda: LegacyServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.LegacyServer.async_status",
        TEST_LEGACY_JAVA_STATUS_RESPONSE,
    ),
    (
        MinecraftServerType.JAVA_EDITION,
        "homeassistant.components.minecraft_server.api.JavaServer.async_lookup",
        lambda: JavaServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.JavaServer.async_status",
        TEST_JAVA_STATUS_RESPONSE,
    ),
    (
        MinecraftServerType.BEDROCK_EDITION,
        "homeassistant.components.minecraft_server.api.BedrockServer.lookup",
        lambda: BedrockServer(host=TEST_HOST, port=TEST_PORT),
        "homeassistant.components.minecraft_server.api.BedrockServer.async_status",
        TEST_BEDROCK_STATUS_RESPONSE,
    ),
]

SERVER_EDITION_CASE_IDS = ["legacy_java", "java", "bedrock"]


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_full_config_flow(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test config entry creation for all supported server editions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_ADDRESS
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result["data"][CONF_TYPE] == server_type


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_config_flow_service_already_configured(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test config flow abort if a server is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TYPE: server_type},
    )
    entry.add_to_hass(hass)

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_config_flow_recovery(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: callable,
    status_target: str,
    status_response: dict,
) -> None:
    """Test recovery flow across all supported server editions."""
    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, side_effect=OSError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_ADDRESS
    assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result2["data"][CONF_TYPE] == server_type


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_config_flow_address_lookup_error(
    hass: HomeAssistant,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: Callable[[], Any],
    status_target: str,
    status_response: dict[str, Any],
) -> None:
    """Test config flow handles a server address lookup error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(lookup_target, side_effect=ValueError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfiguration_flow_edition_change(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguration changes the server edition but keeps the same address."""
    java_mock_config_entry.add_to_hass(hass)

    result = await java_mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert java_mock_config_entry.data == {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
    }


async def test_reconfiguration_flow_address_change(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguration changes the address but keeps the same edition."""
    java_mock_config_entry.add_to_hass(hass)
    new_address = "new.dummyserver.com:25566"

    result = await java_mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.JAVA_EDITION,
                CONF_ADDRESS: new_address,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert java_mock_config_entry.data == {
        CONF_ADDRESS: new_address,
        CONF_TYPE: MinecraftServerType.JAVA_EDITION,
    }
    assert java_mock_config_entry.title == new_address


async def test_reconfiguration_flow_service_already_configured(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguration aborts if another entry has the requested address."""
    java_mock_config_entry.add_to_hass(hass)
    other_address = "another.dummyserver.com:25566"
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: other_address,
            CONF_TYPE: MinecraftServerType.JAVA_EDITION,
        },
    ).add_to_hass(hass)

    result = await java_mock_config_entry.start_reconfigure_flow(hass)

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: MinecraftServerType.JAVA_EDITION,
                CONF_ADDRESS: other_address,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_reconfiguration_flow_recovery(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: Callable[[], Any],
    status_target: str,
    status_response: dict[str, Any],
) -> None:
    """Test recovery after a reconfiguration connection error for each edition."""
    java_mock_config_entry.add_to_hass(hass)
    result = await java_mock_config_entry.start_reconfigure_flow(hass)

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, side_effect=OSError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    SERVER_EDITION_CASE_PARAM_NAMES,
    SERVER_EDITION_SUCCESS_CASES,
    ids=SERVER_EDITION_CASE_IDS,
)
async def test_reconfiguration_flow_address_lookup_error(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    server_type: MinecraftServerType,
    lookup_target: str,
    lookup_result: Callable[[], Any],
    status_target: str,
    status_response: dict[str, Any],
) -> None:
    """Test recovery after an address lookup error for each server edition."""
    java_mock_config_entry.add_to_hass(hass)
    result = await java_mock_config_entry.start_reconfigure_flow(hass)

    with patch(lookup_target, side_effect=ValueError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(lookup_target, return_value=lookup_result()),
        patch(status_target, return_value=status_response),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: server_type,
                CONF_ADDRESS: TEST_ADDRESS,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert java_mock_config_entry.data[CONF_TYPE] == server_type


async def test_options_flow(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test the query protocol options flow."""
    java_mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        java_mock_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"].schema[CONF_ENABLE_QUERY].config["read_only"] is False
    assert result["data_schema"].schema[CONF_QUERY_PORT].config["read_only"] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_QUERY: False, CONF_QUERY_PORT: TEST_QUERY_PORT},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert java_mock_config_entry.options == {
        CONF_ENABLE_QUERY: False,
        CONF_QUERY_PORT: TEST_QUERY_PORT,
    }


@pytest.mark.parametrize(
    "server_type",
    [
        pytest.param(MinecraftServerType.BEDROCK_EDITION, id="bedrock"),
        pytest.param(MinecraftServerType.LEGACY_JAVA_EDITION, id="legacy_java"),
    ],
)
async def test_options_flow_unsupported_edition(
    hass: HomeAssistant, server_type: MinecraftServerType
) -> None:
    """Test query options are read-only for unsupported server editions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TYPE: server_type},
        options={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT},
        version=3,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_ENABLE_QUERY].config["read_only"] is True
    assert result["data_schema"].schema[CONF_QUERY_PORT].config["read_only"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT}


@pytest.mark.parametrize(
    "server_type",
    [
        pytest.param(MinecraftServerType.BEDROCK_EDITION, id="bedrock"),
        pytest.param(MinecraftServerType.LEGACY_JAVA_EDITION, id="legacy_java"),
    ],
)
async def test_options_flow_read_only_rejects_changes(
    hass: HomeAssistant, server_type: MinecraftServerType
) -> None:
    """Test submitted values cannot change read-only query options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TYPE: server_type},
        options={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT},
        version=3,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_QUERY: False, CONF_QUERY_PORT: TEST_PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "query_not_supported"}
    assert entry.options == {CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT}


async def test_options_flow_edition_changed(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test options cannot be changed after switching to an unsupported edition."""
    java_mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(
        java_mock_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM

    hass.config_entries.async_update_entry(
        java_mock_config_entry,
        data={
            **java_mock_config_entry.data,
            CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ENABLE_QUERY: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "query_not_supported"}
    assert result["data_schema"].schema[CONF_ENABLE_QUERY].config["read_only"] is True
    assert java_mock_config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert java_mock_config_entry.options == {}


async def test_options_flow_fractional_query_port(
    hass: HomeAssistant, java_mock_config_entry: MockConfigEntry
) -> None:
    """Test that the query port must be an integer."""
    java_mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(
        java_mock_config_entry.entry_id
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: 25565.5},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_QUERY_PORT: "invalid_query_port"}
    assert java_mock_config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENABLE_QUERY: True, CONF_QUERY_PORT: TEST_QUERY_PORT},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert java_mock_config_entry.options == {
        CONF_ENABLE_QUERY: True,
        CONF_QUERY_PORT: TEST_QUERY_PORT,
    }
    assert type(java_mock_config_entry.options[CONF_QUERY_PORT]) is int


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_query_options_reload(
    hass: HomeAssistant,
    java_mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enabling and disabling query sensors through the options flow."""
    java_mock_config_entry.add_to_hass(hass)
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
