"""
minecraftBC - Minecraft Bridge Connector
Minecraft 桥接连接器

A P2P networking solution for Minecraft multiplayer with cross-game support.
Minecraft 多人联机的 P2P 网络解决方案，支持跨游戏联机。
"""

__version__ = "0.1.0"
__author__ = "minecraftBC Team"

from .protocol.fastlink.packet import generate_node_id
from .protocol.fastlink.p2p import P2PConnection
from .protocol.fastlink.server import FastLinkServer
from .protocol.mnmcp.proxy import MnMCPProxy, GameType
from .network.connector import UnifiedConnector, ConnectionConfig, ConnectionMode

__all__ = [
    'generate_node_id',
    'P2PConnection',
    'FastLinkServer',
    'MnMCPProxy',
    'GameType',
    'UnifiedConnector',
    'ConnectionConfig',
    'ConnectionMode',
]
