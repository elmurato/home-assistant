"""Constants for Minecraft Server integration tests."""

from mcstatus.responses import (
    BedrockStatusResponse,
    JavaStatusResponse,
    LegacyStatusResponse,
    QueryResponse,
)

from homeassistant.components.minecraft_server.api import MinecraftServerData

TEST_CONFIG_ENTRY_ID: str = "01234567890123456789012345678901"
TEST_HOST = "mc.dummyserver.com"
TEST_PORT = 25566
TEST_ADDRESS = f"{TEST_HOST}:{TEST_PORT}"

ENTITY_ID_MAP_NAME = "sensor.mc_dummyserver_com_25566_map_name"
ENTITY_ID_SOFTWARE = "sensor.mc_dummyserver_com_25566_software"

TEST_JAVA_STATUS_RESPONSE = JavaStatusResponse.build(
    {
        "players": {
            "online": 3,
            "max": 10,
            "sample": [
                {"id": "1", "name": "Player 1"},
                {"id": "2", "name": "Player 2"},
                {"id": "3", "name": "Player 3"},
            ],
        },
        "version": {
            "name": "Dummy Version",
            "protocol": 123,
        },
        "description": "Dummy MOTD",
    },
    latency=5,
)

TEST_QUERY_PORT = 25570

TEST_QUERY_RESPONSE = QueryResponse.build(
    {
        "hostname": "Dummy MOTD",
        "gametype": "SMP",
        "game_id": "MINECRAFT",
        "version": "1.21.4",
        "plugins": "Paper on 1.21.4: PluginA 1.0; PluginB 2.0",
        "map": "Dummy Query Map",
        "numplayers": "2",
        "maxplayers": "10",
        "hostport": str(TEST_PORT),
        "hostip": "127.0.0.1",
    },
    players_list=["Query Player B", "Query Player A"],
)

TEST_JAVA_DATA = MinecraftServerData(
    latency=5,
    motd="Dummy MOTD",
    players_max=10,
    players_online=3,
    protocol_version=123,
    version="Dummy Version",
    players_list=["Player 1", "Player 2", "Player 3"],
    edition=None,
    game_mode=None,
    map_name=None,
)

TEST_BEDROCK_STATUS_RESPONSE = BedrockStatusResponse.build(
    [
        "MCPE",  # version.brand
        "Dummy MOTD",  # motd
        "123",  # version.protocol
        "Dummy Version",  # version.name
        "3",  # players.online
        "10",  # players.max
        "Dummy Server ID",  # server unique ID
        "Dummy Map Name",  # map_name
        "Dummy Game Mode",  # gamemode
    ],
    latency=5,
)

TEST_BEDROCK_DATA = MinecraftServerData(
    latency=5,
    motd="Dummy MOTD",
    players_max=10,
    players_online=3,
    protocol_version=123,
    version="Dummy Version",
    players_list=None,
    edition="Dummy Edition",
    game_mode="Dummy Game Mode",
    map_name="Dummy Map Name",
)

TEST_LEGACY_JAVA_STATUS_RESPONSE = LegacyStatusResponse.build(
    [
        "78",  # version.protocol
        "1.6.4",  # version.name
        "Dummy MOTD",  # motd
        "3",  # players online
        "10",  # players max
    ],
    latency=5,
)
