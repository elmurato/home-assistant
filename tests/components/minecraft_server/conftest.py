"""Fixtures for Minecraft Server integration tests."""

from collections.abc import Generator
from unittest.mock import patch

from mcstatus import JavaServer
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.minecraft_server.api import MinecraftServerType
from homeassistant.components.minecraft_server.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_TYPE

from .const import TEST_ADDRESS, TEST_CONFIG_ENTRY_ID


@pytest.fixture(autouse=True)
def mock_query() -> Generator[None]:
    """Make the query protocol unavailable by default."""
    with patch.object(JavaServer, "async_query", side_effect=OSError):
        yield


@pytest.fixture
def java_mock_config_entry() -> MockConfigEntry:
    """Create Java Edition mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id=TEST_CONFIG_ENTRY_ID,
        title=TEST_ADDRESS,
        data={
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.JAVA_EDITION,
        },
        version=3,
    )


@pytest.fixture
def bedrock_mock_config_entry() -> MockConfigEntry:
    """Create Bedrock Edition mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id=TEST_CONFIG_ENTRY_ID,
        title=TEST_ADDRESS,
        data={
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.BEDROCK_EDITION,
        },
        version=3,
    )


@pytest.fixture
def legacy_java_mock_config_entry() -> MockConfigEntry:
    """Create legacy Java Edition mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id=TEST_CONFIG_ENTRY_ID,
        title=TEST_ADDRESS,
        data={
            CONF_ADDRESS: TEST_ADDRESS,
            CONF_TYPE: MinecraftServerType.LEGACY_JAVA_EDITION,
        },
        version=3,
    )
