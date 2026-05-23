"""
MnMCP (Multi-Network Multi-Game Connection Protocol)
多网络多游戏连接协议 - 中间人代理实现

通用跨游戏联机代理，支持任意游戏接入 Minecraft 世界。
基于 FastLink 协议传输，提供双向协议转换。

Features:
- 通用游戏适配器接口
- 双向协议转换
- 实体/方块/物品映射
- 事件转发
- 延迟优化
"""

from __future__ import annotations
import asyncio
import json
import time
import hashlib
from typing import Optional, Dict, List, Callable, Any, Set, Tuple, Type
from dataclasses import dataclass, field
from enum import IntEnum, auto
from abc import ABC, abstractmethod
import logging

from ..fastlink.packet import (
    PacketType, FastLinkPacket, PacketFactory,
    MnMCPEntityPacket, MnMCPBlockPacket, MnMCPChatPacket
)
from ..fastlink.p2p import P2PConnection, NodeInfo
from ..fastlink.server import FastLinkServer, RoomInfo

logger = logging.getLogger(__name__)


class GameType(IntEnum):
    """Supported game types"""
    UNKNOWN = 0
    MINECRAFT_JAVA = 1
    MINECRAFT_BEDROCK = 2
    MINIWORLD = 3
    ROBLOX = 4
    TERRARIA = 5
    # 可扩展更多游戏


class EntityType(IntEnum):
    """Generic entity types"""
    PLAYER = auto()
    MOB_HOSTILE = auto()
    MOB_PASSIVE = auto()
    MOB_NEUTRAL = auto()
    NPC = auto()
    ITEM = auto()
    PROJECTILE = auto()
    VEHICLE = auto()
    BLOCK_ENTITY = auto()
    UNKNOWN = auto()


class BlockType(IntEnum):
    """Generic block types"""
    SOLID = auto()
    TRANSPARENT = auto()
    LIQUID = auto()
    PLANT = auto()
    REDSTONE = auto()
    LIGHT = auto()
    DOOR = auto()
    CHEST = auto()
    UNKNOWN = auto()


@dataclass
class Vec3:
    """3D vector"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}
    
    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'Vec3':
        return cls(x=d.get('x', 0), y=d.get('y', 0), z=d.get('z', 0))


@dataclass
class Vec2:
    """2D vector (rotation)"""
    yaw: float = 0.0
    pitch: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {'yaw': self.yaw, 'pitch': self.pitch}
    
    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'Vec2':
        return cls(yaw=d.get('yaw', 0), pitch=d.get('pitch', 0))


@dataclass
class GenericEntity:
    """Generic entity representation (game-agnostic)"""
    entity_id: str                          # 全局唯一ID
    game_type: GameType                     # 来源游戏
    entity_type: EntityType                 # 实体类型
    
    # Transform
    position: Vec3 = field(default_factory=Vec3)
    rotation: Vec2 = field(default_factory=Vec2)
    velocity: Vec3 = field(default_factory=Vec3)
    
    # Properties
    name: str = ""
    health: float = 100.0
    max_health: float = 100.0
    level: int = 1
    
    # Game-specific data
    game_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    
    def update_position(self, pos: Vec3):
        """Update position"""
        self.position = pos
        self.last_update = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_id': self.entity_id,
            'game_type': self.game_type.name,
            'entity_type': self.entity_type.name,
            'position': self.position.to_dict(),
            'rotation': self.rotation.to_dict(),
            'velocity': self.velocity.to_dict(),
            'name': self.name,
            'health': self.health,
            'max_health': self.max_health,
            'level': self.level,
            'game_data': self.game_data,
            'created_at': self.created_at,
            'last_update': self.last_update
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericEntity':
        return cls(
            entity_id=data['entity_id'],
            game_type=GameType[data.get('game_type', 'UNKNOWN')],
            entity_type=EntityType[data.get('entity_type', 'UNKNOWN')],
            position=Vec3.from_dict(data.get('position', {})),
            rotation=Vec2.from_dict(data.get('rotation', {})),
            velocity=Vec3.from_dict(data.get('velocity', {})),
            name=data.get('name', ''),
            health=data.get('health', 100.0),
            max_health=data.get('max_health', 100.0),
            level=data.get('level', 1),
            game_data=data.get('game_data', {})
        )


@dataclass
class GenericBlock:
    """Generic block representation"""
    block_id: str
    game_type: GameType
    block_type: BlockType
    
    position: Vec3 = field(default_factory=Vec3)
    
    # Block state
    block_state: Dict[str, Any] = field(default_factory=dict)
    
    # Properties
    hardness: float = 1.0
    light_level: int = 0
    is_solid: bool = True
    
    # Game-specific
    game_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'block_id': self.block_id,
            'game_type': self.game_type.name,
            'block_type': self.block_type.name,
            'position': self.position.to_dict(),
            'block_state': self.block_state,
            'hardness': self.hardness,
            'light_level': self.light_level,
            'is_solid': self.is_solid,
            'game_data': self.game_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericBlock':
        return cls(
            block_id=data['block_id'],
            game_type=GameType[data.get('game_type', 'UNKNOWN')],
            block_type=BlockType[data.get('block_type', 'UNKNOWN')],
            position=Vec3.from_dict(data.get('position', {})),
            block_state=data.get('block_state', {}),
            hardness=data.get('hardness', 1.0),
            light_level=data.get('light_level', 0),
            is_solid=data.get('is_solid', True),
            game_data=data.get('game_data', {})
        )


@dataclass
class GenericItem:
    """Generic item representation"""
    item_id: str
    game_type: GameType
    
    name: str = ""
    count: int = 1
    max_stack: int = 64
    durability: int = 0
    max_durability: int = 0
    
    # Properties
    is_stackable: bool = True
    is_damageable: bool = False
    is_food: bool = False
    
    # Game-specific
    game_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'game_type': self.game_type.name,
            'name': self.name,
            'count': self.count,
            'max_stack': self.max_stack,
            'durability': self.durability,
            'max_durability': self.max_durability,
            'is_stackable': self.is_stackable,
            'is_damageable': self.is_damageable,
            'is_food': self.is_food,
            'game_data': self.game_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericItem':
        return cls(
            item_id=data['item_id'],
            game_type=GameType[data.get('game_type', 'UNKNOWN')],
            name=data.get('name', ''),
            count=data.get('count', 1),
            max_stack=data.get('max_stack', 64),
            durability=data.get('durability', 0),
            max_durability=data.get('max_durability', 0),
            is_stackable=data.get('is_stackable', True),
            is_damageable=data.get('is_damageable', False),
            is_food=data.get('is_food', False),
            game_data=data.get('game_data', {})
        )


class GameAdapter(ABC):
    """
    Abstract base class for game adapters
    
    Each game needs to implement this interface to connect to MnMCP.
    """
    
    def __init__(self, game_type: GameType):
        self.game_type = game_type
        self.connected = False
        self.players: Dict[str, GenericEntity] = {}
        self.entities: Dict[str, GenericEntity] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
    
    @abstractmethod
    async def connect(self, host: str, port: int, **kwargs) -> bool:
        """Connect to the game server/instance"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the game"""
        pass
    
    @abstractmethod
    async def send_entity(self, entity: GenericEntity) -> bool:
        """Send entity to the game"""
        pass
    
    @abstractmethod
    async def send_block(self, block: GenericBlock) -> bool:
        """Send block update to the game"""
        pass
    
    @abstractmethod
    async def send_chat(self, sender: str, message: str, message_type: str = "global") -> bool:
        """Send chat message to the game"""
        pass
    
    @abstractmethod
    def to_generic_entity(self, game_entity: Any) -> Optional[GenericEntity]:
        """Convert game-specific entity to generic entity"""
        pass
    
    @abstractmethod
    def from_generic_entity(self, generic: GenericEntity) -> Any:
        """Convert generic entity to game-specific entity"""
        pass
    
    @abstractmethod
    def to_generic_block(self, game_block: Any) -> Optional[GenericBlock]:
        """Convert game-specific block to generic block"""
        pass
    
    @abstractmethod
    def from_generic_block(self, generic: GenericBlock) -> Any:
        """Convert generic block to game-specific block"""
        pass
    
    def on_event(self, event_type: str, callback: Callable):
        """Register event callback"""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
    
    def emit_event(self, event_type: str, data: Any):
        """Emit event to registered callbacks"""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if adapter is connected"""
        pass


class MappingManager:
    """
    Manages mappings between different games
    
    Provides bidirectional translation between game-specific IDs and generic IDs.
    """
    
    def __init__(self, mapping_dir: str = "data/mappings"):
        self.mapping_dir = mapping_dir
        
        # Entity mappings: game_type -> entity_id -> generic_id
        self.entity_mappings: Dict[GameType, Dict[str, str]] = {}
        self.entity_reverse: Dict[GameType, Dict[str, str]] = {}
        
        # Block mappings
        self.block_mappings: Dict[GameType, Dict[str, str]] = {}
        self.block_reverse: Dict[GameType, Dict[str, str]] = {}
        
        # Item mappings
        self.item_mappings: Dict[GameType, Dict[str, str]] = {}
        self.item_reverse: Dict[GameType, Dict[str, str]] = {}
        
        # Fallback mappings for unknown entities
        self.fallback_mappings: Dict[GameType, Dict[str, str]] = {}
    
    def load_mappings(self, game_type: GameType):
        """Load mappings for a specific game"""
        import os
        import json
        
        # Entity mappings
        entity_file = os.path.join(self.mapping_dir, f"{game_type.name.lower()}_entity.json")
        if os.path.exists(entity_file):
            with open(entity_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.entity_mappings[game_type] = {}
                self.entity_reverse[game_type] = {}
                for entry in data.get('mappings', []):
                    game_id = entry.get('game_id')
                    generic_id = entry.get('generic_id')
                    if game_id and generic_id:
                        self.entity_mappings[game_type][game_id] = generic_id
                        self.entity_reverse[game_type][generic_id] = game_id
        
        # Block mappings
        block_file = os.path.join(self.mapping_dir, f"{game_type.name.lower()}_block.json")
        if os.path.exists(block_file):
            with open(block_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.block_mappings[game_type] = {}
                self.block_reverse[game_type] = {}
                for entry in data.get('mappings', []):
                    game_id = entry.get('game_id')
                    generic_id = entry.get('generic_id')
                    if game_id and generic_id:
                        self.block_mappings[game_type][game_id] = generic_id
                        self.block_reverse[game_type][generic_id] = game_id
        
        # Item mappings
        item_file = os.path.join(self.mapping_dir, f"{game_type.name.lower()}_item.json")
        if os.path.exists(item_file):
            with open(item_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.item_mappings[game_type] = {}
                self.item_reverse[game_type] = {}
                for entry in data.get('mappings', []):
                    game_id = entry.get('game_id')
                    generic_id = entry.get('generic_id')
                    if game_id and generic_id:
                        self.item_mappings[game_type][game_id] = generic_id
                        self.item_reverse[gameType][generic_id] = game_id
    
    def to_generic_entity(self, game_type: GameType, game_entity_id: str) -> Optional[str]:
        """Convert game entity ID to generic ID"""
        mappings = self.entity_mappings.get(game_type, {})
        return mappings.get(game_entity_id)
    
    def from_generic_entity(self, game_type: GameType, generic_id: str) -> Optional[str]:
        """Convert generic entity ID to game entity ID"""
        reverse = self.entity_reverse.get(game_type, {})
        return reverse.get(generic_id)
    
    def to_generic_block(self, game_type: GameType, game_block_id: str) -> Optional[str]:
        """Convert game block ID to generic ID"""
        mappings = self.block_mappings.get(game_type, {})
        return mappings.get(game_block_id)
    
    def from_generic_block(self, game_type: GameType, generic_id: str) -> Optional[str]:
        """Convert generic block ID to game block ID"""
        reverse = self.block_reverse.get(game_type, {})
        return reverse.get(generic_id)
    
    def to_generic_item(self, game_type: GameType, game_item_id: str) -> Optional[str]:
        """Convert game item ID to generic ID"""
        mappings = self.item_mappings.get(game_type, {})
        return mappings.get(game_item_id)
    
    def from_generic_item(self, game_type: GameType, generic_id: str) -> Optional[str]:
        """Convert generic item ID to game item ID"""
        reverse = self.item_reverse.get(game_type, {})
        return reverse.get(generic_id)
    
    def get_fallback_entity(self, game_type: GameType, entity_type: EntityType) -> str:
        """Get fallback entity for unknown entities"""
        fallbacks = self.fallback_mappings.get(game_type, {})
        return fallbacks.get(entity_type.name, "unknown")


class MnMCPProxy:
    """
    MnMCP Multi-Game Proxy
    
    Acts as a middleman between different games, translating protocols
    and forwarding events between connected game adapters.
    """
    
    def __init__(self, node_id: str, bind_addr: Tuple[str, int]):
        self.node_id = node_id
        self.bind_addr = bind_addr
        
        # Connected adapters
        self.adapters: Dict[GameType, GameAdapter] = {}
        
        # Entity tracking
        self.entities: Dict[str, GenericEntity] = {}
        self.entity_owners: Dict[str, GameType] = {}  # entity_id -> source game
        
        # Block tracking
        self.blocks: Dict[str, GenericBlock] = {}
        
        # Mapping manager
        self.mapping = MappingManager()
        
        # FastLink connection
        self.p2p: Optional[P2PConnection] = None
        self.server: Optional[FastLinkServer] = None
        
        # Running state
        self.running = False
        
        # Statistics
        self.stats = {
            'entities_synced': 0,
            'blocks_synced': 0,
            'messages_forwarded': 0,
            'bytes_transferred': 0
        }
    
    async def start(self, mode: str = "p2p") -> bool:
        """Start MnMCP proxy"""
        try:
            if mode == "p2p":
                self.p2p = P2PConnection(self.node_id, self.bind_addr)
                self.p2p.on_message(self._on_p2p_message)
                self.p2p.on_connect(self._on_peer_connect)
                self.p2p.on_disconnect(self._on_peer_disconnect)
                
                if not await self.p2p.start():
                    return False
                    
            elif mode == "server":
                self.server = FastLinkServer(self.node_id, self.bind_addr)
                
                if not await self.server.start():
                    return False
            
            self.running = True
            logger.info(f"MnMCP proxy started in {mode} mode on {self.bind_addr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MnMCP proxy: {e}")
            return False
    
    async def stop(self):
        """Stop MnMCP proxy"""
        self.running = False
        
        # Disconnect all adapters
        for adapter in self.adapters.values():
            await adapter.disconnect()
        self.adapters.clear()
        
        # Stop FastLink
        if self.p2p:
            await self.p2p.stop()
        if self.server:
            await self.server.stop()
        
        logger.info("MnMCP proxy stopped")
    
    def register_adapter(self, adapter: GameAdapter):
        """Register a game adapter"""
        self.adapters[adapter.game_type] = adapter
        
        # Setup event forwarding
        adapter.on_event('entity_spawn', lambda data: self._forward_entity(adapter.game_type, data, 'spawn'))
        adapter.on_event('entity_update', lambda data: self._forward_entity(adapter.game_type, data, 'update'))
        adapter.on_event('entity_despawn', lambda data: self._forward_entity(adapter.game_type, data, 'despawn'))
        adapter.on_event('block_update', lambda data: self._forward_block(adapter.game_type, data))
        adapter.on_event('chat_message', lambda data: self._forward_chat(adapter.game_type, data))
        
        logger.info(f"Registered adapter for {adapter.game_type.name}")
    
    async def _forward_entity(self, source_game: GameType, entity: GenericEntity, action: str):
        """Forward entity update to all other games"""
        # Track entity
        self.entities[entity.entity_id] = entity
        self.entity_owners[entity.entity_id] = source_game
        
        # Create MnMCP packet
        packet = MnMCPEntityPacket(
            entity_id=entity.entity_id,
            source_game=source_game.name,
            target_game="ALL",  # Broadcast
            entity_type=entity.entity_type.name,
            position=entity.position.to_dict(),
            rotation=entity.rotation.to_dict(),
            velocity=entity.velocity.to_dict(),
            metadata=entity.game_data,
            action=action
        )
        
        # Send to all other adapters
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    # Convert to target game format
                    target_entity = adapter.from_generic_entity(entity)
                    if target_entity:
                        await adapter.send_entity(entity)
                        self.stats['entities_synced'] += 1
                except Exception as e:
                    logger.error(f"Failed to forward entity to {game_type.name}: {e}")
        
        # Also send via FastLink if in P2P mode
        if self.p2p:
            for peer_id in self.p2p.get_connected_peers():
                await self.p2p.send(peer_id, packet.encode())
    
    async def _forward_block(self, source_game: GameType, block: GenericBlock):
        """Forward block update to all other games"""
        self.blocks[block.block_id] = block
        
        packet = MnMCPBlockPacket(
            block_id=block.block_id,
            source_game=source_game.name,
            target_game="ALL",
            position=block.position.to_dict(),
            block_type=block.block_type.name,
            block_state=block.block_state,
            action='update'
        )
        
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    target_block = adapter.from_generic_block(block)
                    if target_block:
                        await adapter.send_block(block)
                        self.stats['blocks_synced'] += 1
                except Exception as e:
                    logger.error(f"Failed to forward block to {game_type.name}: {e}")
    
    async def _forward_chat(self, source_game: GameType, data: Dict[str, Any]):
        """Forward chat message to all other games"""
        sender = data.get('sender', 'Unknown')
        message = data.get('message', '')
        
        packet = MnMCPChatPacket(
            message_id=hashlib.md5(f"{time.time()}{message}".encode()).hexdigest()[:16],
            sender_id=data.get('sender_id', ''),
            sender_name=sender,
            source_game=source_game.name,
            target_game="ALL",
            message=message,
            message_type=data.get('type', 'global'),
            timestamp=int(time.time() * 1000)
        )
        
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    await adapter.send_chat(sender, message)
                    self.stats['messages_forwarded'] += 1
                except Exception as e:
                    logger.error(f"Failed to forward chat to {game_type.name}: {e}")
    
    def _on_p2p_message(self, peer_id: str, data: bytes, addr: str):
        """Handle incoming P2P message"""
        try:
            packet = FastLinkPacket.decode(data)
            if not packet:
                return
            
            if packet.header.packet_type == PacketType.MNMCP_ENTITY:
                payload = MnMCPEntityPacket.decode(packet.payload)
                if payload:
                    self._handle_remote_entity(payload)
                    
            elif packet.header.packet_type == PacketType.MNMCP_BLOCK:
                payload = MnMCPBlockPacket.decode(packet.payload)
                if payload:
                    self._handle_remote_block(payload)
                    
            elif packet.header.packet_type == PacketType.MNMCP_CHAT:
                payload = MnMCPChatPacket.decode(packet.payload)
                if payload:
                    self._handle_remote_chat(payload)
                    
        except Exception as e:
            logger.error(f"Error handling P2P message: {e}")
    
    def _handle_remote_entity(self, packet: MnMCPEntityPacket):
        """Handle entity packet from remote peer"""
        source_game = GameType[packet.source_game]
        
        # Convert to generic entity
        entity = GenericEntity(
            entity_id=packet.entity_id,
            game_type=source_game,
            entity_type=EntityType[packet.entity_type],
            position=Vec3.from_dict(packet.position),
            rotation=Vec2.from_dict(packet.rotation),
            velocity=Vec3.from_dict(packet.velocity),
            game_data=packet.metadata
        )
        
        # Forward to local adapters
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    adapter.send_entity(entity)
                except Exception as e:
                    logger.error(f"Failed to send entity to {game_type.name}: {e}")
    
    def _handle_remote_block(self, packet: MnMCPBlockPacket):
        """Handle block packet from remote peer"""
        source_game = GameType[packet.source_game]
        
        block = GenericBlock(
            block_id=packet.block_id,
            game_type=source_game,
            block_type=BlockType[packet.block_type],
            position=Vec3.from_dict(packet.position),
            block_state=packet.block_state
        )
        
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    adapter.send_block(block)
                except Exception as e:
                    logger.error(f"Failed to send block to {game_type.name}: {e}")
    
    def _handle_remote_chat(self, packet: MnMCPChatPacket):
        """Handle chat packet from remote peer"""
        source_game = GameType[packet.source_game]
        
        for game_type, adapter in self.adapters.items():
            if game_type != source_game and adapter.is_connected:
                try:
                    adapter.send_chat(packet.sender_name, packet.message, packet.message_type)
                except Exception as e:
                    logger.error(f"Failed to send chat to {game_type.name}: {e}")
    
    def _on_peer_connect(self, peer_id: str):
        """Handle peer connection"""
        logger.info(f"Peer {peer_id} connected via MnMCP")
    
    def _on_peer_disconnect(self, peer_id: str):
        """Handle peer disconnection"""
        logger.info(f"Peer {peer_id} disconnected from MnMCP")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proxy statistics"""
        return {
            **self.stats,
            'connected_games': len([a for a in self.adapters.values() if a.is_connected]),
            'tracked_entities': len(self.entities),
            'tracked_blocks': len(self.blocks)
        }


# Example usage
if __name__ == '__main__':
    async def main():
        from ..fastlink.packet import generate_node_id
        
        # Create proxy
        node_id = generate_node_id()
        proxy = MnMCPProxy(node_id, ('0.0.0.0', 25566))
        
        # Start
        if await proxy.start("p2p"):
            print(f"MnMCP proxy {node_id} started")
            
            try:
                while True:
                    await asyncio.sleep(10)
                    stats = proxy.get_stats()
                    print(f"Stats: {stats}")
            except KeyboardInterrupt:
                pass
        
        await proxy.stop()
    
    asyncio.run(main())
