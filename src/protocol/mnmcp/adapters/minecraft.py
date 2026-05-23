"""
Minecraft Java Edition Adapter for MnMCP
Minecraft JE 适配器

Implements the GameAdapter interface for Minecraft Java Edition.
Supports multiple versions (1.12.2 - 1.20.x)
"""

from __future__ import annotations
import asyncio
import struct
import json
import zlib
import time
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass
from enum import IntEnum
import logging

from ..proxy import GameAdapter, GameType, GenericEntity, GenericBlock, GenericItem
from ..proxy import Vec3, Vec2, EntityType, BlockType
from ..packet import MnMCPEntityPacket, MnMCPBlockPacket, MnMCPChatPacket

logger = logging.getLogger(__name__)


class MCProtocolState(IntEnum):
    """Minecraft protocol states"""
    HANDSHAKE = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3


class MCPacketType(IntEnum):
    """Minecraft packet types (simplified)"""
    # Handshake
    HANDSHAKE = 0x00
    
    # Login
    LOGIN_START = 0x00
    LOGIN_SUCCESS = 0x02
    
    # Play - Clientbound
    SPAWN_ENTITY = 0x00
    SPAWN_LIVING_ENTITY = 0x02
    ENTITY_POSITION = 0x28
    ENTITY_ROTATION = 0x29
    ENTITY_POSITION_AND_ROTATION = 0x2A
    CHAT_MESSAGE_CB = 0x0E
    CHUNK_DATA = 0x20
    BLOCK_CHANGE = 0x0B
    
    # Play - Serverbound
    CHAT_MESSAGE_SB = 0x03
    PLAYER_POSITION = 0x11
    PLAYER_POSITION_AND_ROTATION = 0x12


@dataclass
class MCVersion:
    """Minecraft version info"""
    name: str
    protocol: int
    
    # Known versions
    VERSIONS = {
        '1.12.2': 340,
        '1.16.5': 754,
        '1.17.1': 756,
        '1.18.2': 758,
        '1.19.2': 760,
        '1.19.4': 762,
        '1.20.1': 763,
        '1.20.4': 766,
    }
    
    @classmethod
    def from_name(cls, name: str) -> 'MCVersion':
        protocol = cls.VERSIONS.get(name, 763)  # Default to 1.20.1
        return cls(name=name, protocol=protocol)
    
    @classmethod
    def from_protocol(cls, protocol: int) -> 'MCVersion':
        for name, proto in cls.VERSIONS.items():
            if proto == protocol:
                return cls(name=name, protocol=protocol)
        return cls(name=f"unknown_{protocol}", protocol=protocol)


class MinecraftAdapter(GameAdapter):
    """
    Minecraft Java Edition adapter for MnMCP
    
    Connects to Minecraft servers and translates between
    Minecraft protocol and MnMCP generic format.
    """
    
    # Entity type mappings: Minecraft -> Generic
    ENTITY_MAPPINGS = {
        'minecraft:player': EntityType.PLAYER,
        'minecraft:zombie': EntityType.MOB_HOSTILE,
        'minecraft:skeleton': EntityType.MOB_HOSTILE,
        'minecraft:creeper': EntityType.MOB_HOSTILE,
        'minecraft:spider': EntityType.MOB_HOSTILE,
        'minecraft:enderman': EntityType.MOB_NEUTRAL,
        'minecraft:pig': EntityType.MOB_PASSIVE,
        'minecraft:cow': EntityType.MOB_PASSIVE,
        'minecraft:chicken': EntityType.MOB_PASSIVE,
        'minecraft:sheep': EntityType.MOB_PASSIVE,
        'minecraft:villager': EntityType.NPC,
        'minecraft:item': EntityType.ITEM,
        'minecraft:arrow': EntityType.PROJECTILE,
        'minecraft:snowball': EntityType.PROJECTILE,
        'minecraft:boat': EntityType.VEHICLE,
        'minecraft:minecart': EntityType.VEHICLE,
        'minecraft:chest_minecart': EntityType.VEHICLE,
    }
    
    # Block type mappings
    BLOCK_MAPPINGS = {
        'minecraft:stone': BlockType.SOLID,
        'minecraft:dirt': BlockType.SOLID,
        'minecraft:grass_block': BlockType.SOLID,
        'minecraft:glass': BlockType.TRANSPARENT,
        'minecraft:water': BlockType.LIQUID,
        'minecraft:lava': BlockType.LIQUID,
        'minecraft:oak_leaves': BlockType.PLANT,
        'minecraft:grass': BlockType.PLANT,
        'minecraft:redstone_wire': BlockType.REDSTONE,
        'minecraft:redstone_torch': BlockType.REDSTONE,
        'minecraft:torch': BlockType.LIGHT,
        'minecraft:glowstone': BlockType.LIGHT,
        'minecraft:oak_door': BlockType.DOOR,
        'minecraft:chest': BlockType.CHEST,
        'minecraft:trapped_chest': BlockType.CHEST,
    }
    
    def __init__(self, version: str = "1.20.1"):
        super().__init__(GameType.MINECRAFT_JAVA)
        
        self.version = MCVersion.from_name(version)
        self.protocol_state = MCProtocolState.HANDSHAKE
        
        # Connection
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
        # Compression
        self.compression_threshold = -1
        
        # Entity tracking
        self.mc_entities: Dict[int, Dict[str, Any]] = {}  # MC entity ID -> data
        self.entity_id_map: Dict[int, str] = {}  # MC ID -> Generic ID
        
        # Player info
        self.player_uuid: Optional[str] = None
        self.player_name: str = ""
        self.player_entity_id: Optional[int] = None
        
        # Callbacks
        self.packet_handlers: Dict[int, Callable] = {}
        self._setup_packet_handlers()
        
        # Tasks
        self.read_task: Optional[asyncio.Task] = None
        self.keepalive_task: Optional[asyncio.Task] = None
    
    def _setup_packet_handlers(self):
        """Setup packet handlers"""
        self.packet_handlers[MCPacketType.LOGIN_SUCCESS] = self._handle_login_success
        self.packet_handlers[MCPacketType.SPAWN_ENTITY] = self._handle_spawn_entity
        self.packet_handlers[MCPacketType.SPAWN_LIVING_ENTITY] = self._handle_spawn_living
        self.packet_handlers[MCPacketType.ENTITY_POSITION] = self._handle_entity_position
        self.packet_handlers[MCPacketType.ENTITY_ROTATION] = self._handle_entity_rotation
        self.packet_handlers[MCPacketType.ENTITY_POSITION_AND_ROTATION] = self._handle_entity_pos_rot
        self.packet_handlers[MCPacketType.CHAT_MESSAGE_CB] = self._handle_chat_message
        self.packet_handlers[MCPacketType.BLOCK_CHANGE] = self._handle_block_change
    
    @property
    def is_connected(self) -> bool:
        return self.connected and self.writer is not None
    
    async def connect(self, host: str, port: int, **kwargs) -> bool:
        """Connect to Minecraft server"""
        try:
            self.player_name = kwargs.get('username', 'MnMCPPlayer')
            
            # Connect
            self.reader, self.writer = await asyncio.open_connection(host, port)
            
            # Send handshake
            await self._send_handshake(host, port)
            
            # Start reading
            self.read_task = asyncio.create_task(self._read_loop())
            
            self.connected = True
            logger.info(f"Connected to Minecraft server {host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Minecraft: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Minecraft server"""
        self.connected = False
        
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
        
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass
        
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        
        logger.info("Disconnected from Minecraft server")
    
    async def _send_handshake(self, host: str, port: int):
        """Send handshake packet""