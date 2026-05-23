"""
FastLink Server Protocol Implementation
FastLink Server 协议实现

Based on FastLink v26.4-20260515 specification:
- Decentralized relay and intelligent routing
- Room/channel system
- Permission management
- Message broadcast/multicast
- State synchronization

Features:
- TCP/WebSocket dual mode
- 5D routing algorithm
- Reputation-based node selection
- Cluster management
"""

from __future__ import annotations
import asyncio
import json
import time
import hashlib
from typing import Optional, Dict, List, Callable, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import IntEnum, auto
from datetime import datetime, timedelta
import logging

from .packet import (
    PacketType, ProtocolVersion, PacketHeader, FastLinkPacket,
    ServerAuthPacket, ServerJoinRoomPacket, ServerStateSyncPacket,
    PacketFactory, generate_node_id
)

logger = logging.getLogger(__name__)


class RoomVisibility(IntEnum):
    """Room visibility types"""
    PUBLIC = 0      # Visible to all
    PRIVATE = 1     # Invite only
    HIDDEN = 2      # Not listed


class MemberRole(IntEnum):
    """Room member roles"""
    VISITOR = 0     # Read-only
    MEMBER = 1      # Can send messages
    MODERATOR = 2   # Can kick, mute
    ADMIN = 3       # Can manage room
    OWNER = 4       # Full control


class Permission(IntEnum):
    """Room permissions"""
    SEND_MESSAGE = auto()
    SEND_MEDIA = auto()
    EDIT_ROOM = auto()
    KICK_MEMBER = auto()
    BAN_MEMBER = auto()
    ASSIGN_ROLE = auto()
    DELETE_MESSAGE = auto()
    PIN_MESSAGE = auto()


@dataclass
class RoomMember:
    """Room member information"""
    node_id: str
    username: str
    role: MemberRole = MemberRole.MEMBER
    joined_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    latency_ms: int = 0
    platform: str = "java"  # java, bedrock, miniworld
    
    # Permissions cache
    permissions: Set[Permission] = field(default_factory=set)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if member has permission"""
        if self.role == MemberRole.OWNER:
            return True
        if self.role == MemberRole.ADMIN:
            return permission in [
                Permission.SEND_MESSAGE, Permission.SEND_MEDIA,
                Permission.EDIT_ROOM, Permission.KICK_MEMBER,
                Permission.BAN_MEMBER, Permission.ASSIGN_ROLE,
                Permission.DELETE_MESSAGE, Permission.PIN_MESSAGE
            ]
        if self.role == MemberRole.MODERATOR:
            return permission in [
                Permission.SEND_MESSAGE, Permission.SEND_MEDIA,
                Permission.KICK_MEMBER, Permission.DELETE_MESSAGE
            ]
        if self.role == MemberRole.MEMBER:
            return permission in [Permission.SEND_MESSAGE, Permission.SEND_MEDIA]
        return False
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active = time.time()


@dataclass
class RoomInfo:
    """Room information"""
    room_id: str
    name: str
    description: str = ""
    visibility: RoomVisibility = RoomVisibility.PUBLIC
    password: Optional[str] = None
    max_members: int = 100
    created_at: float = field(default_factory=time.time)
    owner_id: str = ""
    
    # State
    members: Dict[str, RoomMember] = field(default_factory=dict)
    banned: Set[str] = field(default_factory=set)
    pinned_messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Game-specific
    game_mode: str = "survival"  # survival, creative, adventure
    difficulty: str = "normal"   # peaceful, easy, normal, hard
    world_seed: Optional[int] = None
    
    def to_dict(self, include_members: bool = True) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            'room_id': self.room_id,
            'name': self.name,
            'description': self.description,
            'visibility': self.visibility.name,
            'max_members': self.max_members,
            'created_at': self.created_at,
            'owner_id': self.owner_id,
            'member_count': len(self.members),
            'game_mode': self.game_mode,
            'difficulty': self.difficulty,
            'world_seed': self.world_seed
        }
        
        if include_members:
            data['members'] = [
                {
                    'node_id': m.node_id,
                    'username': m.username,
                    'role': m.role.name,
                    'platform': m.platform,
                    'latency_ms': m.latency_ms
                }
                for m in self.members.values()
            ]
        
        return data
    
    def add_member(self, member: RoomMember) -> bool:
        """Add member to room"""
        if member.node_id in self.banned:
            return False
        if len(self.members) >= self.max_members:
            return False
        
        self.members[member.node_id] = member
        return True
    
    def remove_member(self, node_id: str) -> bool:
        """Remove member from room"""
        if node_id in self.members:
            del self.members[node_id]
            return True
        return False
    
    def ban_member(self, node_id: str) -> bool:
        """Ban member from room"""
        self.banned.add(node_id)
        return self.remove_member(node_id)
    
    def get_member(self, node_id: str) -> Optional[RoomMember]:
        """Get room member"""
        return self.members.get(node_id)
    
    def is_full(self) -> bool:
        """Check if room is full"""
        return len(self.members) >= self.max_members


@dataclass
class RouteMetrics:
    """5D routing metrics"""
    latency_ms: float = 0.0
    loss_rate: float = 0.0
    hop_count: int = 0
    isp_match: bool = False
    distance_km: float = 0.0
    
    def calculate_weight(self) -> float:
        """Calculate 5D routing weight"""
        # Weight = 0.4×Latency + 0.3×LossRate + 0.1×HopCount + 0.15×ISPMatch + 0.05×Distance
        isp_score = 1.0 if self.isp_match else 0.0
        normalized_distance = min(self.distance_km / 1000.0, 1.0)
        
        return (
            0.4 * (self.latency_ms / 1000.0) +
            0.3 * self.loss_rate +
            0.1 * (self.hop_count / 10.0) +
            0.15 * (1.0 - isp_score) +  # Lower is better
            0.05 * normalized_distance
        )


@dataclass
class NodeReputation:
    """Node reputation score"""
    node_id: str
    score: float = 100.0  # 0-100
    total_packets: int = 0
    failed_packets: int = 0
    avg_latency_ms: float = 0.0
    last_penalty: float = 0.0
    penalties: List[Dict[str, Any]] = field(default_factory=list)
    
    # Penalty values
    PENALTIES = {
        'handshake_failure': 20,
        'high_latency': 15,
        'packet_loss_per_percent': 10,
        'relay_timeout': 25,
        'protocol_violation': 30,
        'replay_attack': 100
    }
    
    def apply_penalty(self, penalty_type: str, details: str = ""):
        """Apply penalty to reputation"""
        penalty = self.PENALTIES.get(penalty_type, 5)
        self.score = max(0.0, self.score - penalty)
        self.last_penalty = time.time()
        
        self.penalties.append({
            'type': penalty_type,
            'penalty': penalty,
            'timestamp': time.time(),
            'details': details
        })
        
        logger.warning(f"Applied penalty {penalty_type} (-{penalty}) to {self.node_id}")
    
    def record_success(self, latency_ms: float):
        """Record successful packet"""
        self.total_packets += 1
        
        # Update average latency
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = 0.9 * self.avg_latency_ms + 0.1 * latency_ms
        
        # Gradually restore score
        self.score = min(100.0, self.score + 0.1)
    
    def record_failure(self):
        """Record failed packet"""
        self.total_packets += 1
        self.failed_packets += 1
    
    def get_loss_rate(self) -> float:
        """Get packet loss rate"""
        if self.total_packets == 0:
            return 0.0
        return self.failed_packets / self.total_packets
    
    def is_trusted(self, threshold: float = 50.0) -> bool:
        """Check if node is trusted"""
        return self.score >= threshold


class FastLinkServer:
    """
    FastLink Server protocol implementation
    
    Features:
    - Room management
    - Member management with roles
    - Message routing
    - State synchronization
    - Reputation-based node selection
    """
    
    # Timeouts
    HEARTBEAT_INTERVAL = 10.0
    HEARTBEAT_TIMEOUT = 30.0
    SYNC_INTERVAL = 1.0  # State sync interval
    
    def __init__(self, node_id: str, bind_addr: Tuple[str, int]):
        self.node_id = node_id
        self.bind_addr = bind_addr
        
        # Rooms
        self.rooms: Dict[str, RoomInfo] = {}
        self.public_rooms: Set[str] = set()
        
        # Connected clients
        self.clients: Dict[str, Dict[str, Any]] = {}  # node_id -> client info
        
        # Reputation
        self.reputations: Dict[str, NodeReputation] = {}
        
        # Routing
        self.routes: Dict[str, RouteMetrics] = {}
        
        # Server socket
        self.server: Optional[asyncio.Server] = None
        self.websocket_server: Optional[Any] = None
        
        # Tasks
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.sync_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.message_handlers: List[Callable[[str, str, Dict[str, Any]], None]] = []
        self.room_handlers: List[Callable[[str, str, str], None]] = []
        
        # Running state
        self.running = False
        self.sequence = 0
    
    async def start(self) -> bool:
        """Start FastLink server"""
        try:
            # Start TCP server
            self.server = await asyncio.start_server(
                self._handle_client,
                self.bind_addr[0],
                self.bind_addr[1]
            )
            
            self.running = True
            
            # Start background tasks
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.sync_task = asyncio.create_task(self._sync_loop())
            
            logger.info(f"FastLink server started on {self.bind_addr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    async def stop(self):
        """Stop FastLink server"""
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        for node_id in list(self.clients.keys()):
            await self._disconnect_client(node_id)
        
        logger.info("FastLink server stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader, 
                            writer: asyncio.StreamWriter):
        """Handle new client connection"""
        addr = writer.get_extra_info('peername')
        logger.info(f"New client connection from {addr}")
        
        client_info = {
            'reader': reader,
            'writer': writer,
            'addr': addr,
            'node_id': None,
            'authenticated': False,
            'rooms': set(),
            'connected_at': time.time()
        }
        
        try:
            while self.running:
                # Read packet header
                header_data = await reader.read(24)
                if len(header_data) < 24:
                    break
                
                header = PacketHeader.decode(header_data)
                if not header:
                    logger.warning(f"Invalid header from {addr}")
                    break
                
                # Read payload
                payload_data = await reader.read(header.payload_length)
                if len(payload_data) < header.payload_length:
                    logger.warning(f"Incomplete payload from {addr}")
                    break
                
                # Create packet
                packet = FastLinkPacket(header=header, payload=payload_data)
                
                # Handle packet
                await self._handle_server_packet(packet, client_info)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Client error: {e}")
        finally:
            # Cleanup
            if client_info['node_id']:
                await self._disconnect_client(client_info['node_id'])
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    
    async def _handle_server_packet(self, packet: FastLinkPacket, 
                                   client_info: Dict[str, Any]):
        """Handle server protocol packet"""
        handler_map = {
            PacketType.SERVER_AUTH: self._handle_auth,
            PacketType.SERVER_JOIN_ROOM: self._handle_join_room,
            PacketType.SERVER_LEAVE_ROOM: self._handle_leave_room,
            PacketType.SERVER_BROADCAST: self._handle_broadcast,
            PacketType.SERVER_DIRECT: self._handle_direct,
            PacketType.SERVER_STATE_SYNC: self._handle_state_sync,
            PacketType.SERVER_ROOM_LIST: self._handle_room_list,
        }
        
        handler = handler_map.get(packet.header.packet_type)
        if handler:
            await handler(packet, client_info)
        else:
            logger.debug(f"Unhandled packet type: {packet.header.packet_type}")
    
    async def _handle_auth(self, packet: FastLinkPacket, 
                          client_info: Dict[str, Any]):
        """Handle authentication"""
        payload = ServerAuthPacket.decode(packet.payload)
        if not payload:
            return
        
        # Validate token (simplified - real impl would verify JWT or similar)
        node_id = generate_node_id()
        
        # Check reputation
        if node_id in self.reputations:
            rep = self.reputations[node_id]
            if not rep.is_trusted():
                logger.warning(f"Untrusted node {node_id} attempted connection")
                return
        
        # Authenticate
        client_info['node_id'] = node_id
        client_info['authenticated'] = True
        client_info['username'] = payload.username
        client_info['platform'] = payload.platform
        
        self.clients[node_id] = client_info
        
        # Initialize reputation if new
        if node_id not in self.reputations:
            self.reputations[node_id] = NodeReputation(node_id=node_id)
        
        logger.info(f"Client {node_id} ({payload.username}) authenticated")
        
        # Send auth response
        await self._send_response(client_info, PacketType.SERVER_AUTH, {
            'success': True,
            'node_id': node_id,
            'server_version': '2.0.0'
        })
    
    async def _handle_join_room(self, packet: FastLinkPacket, 
                               client_info: Dict[str, Any]):
        """Handle join room request"""
        if not client_info.get('authenticated'):
            return
        
        payload = ServerJoinRoomPacket.decode(packet.payload)
        if not payload:
            return
        
        node_id = client_info['node_id']
        room_id = payload.room_id
        
        # Get or create room
        room = self.rooms.get(room_id)
        if not room:
            # Create new room
            room = RoomInfo(
                room_id=room_id,
                name=f"Room {room_id}",
                owner_id=node_id,
                password=payload.password
            )
            self.rooms[room_id] = room
            if room.visibility == RoomVisibility.PUBLIC:
                self.public_rooms.add(room_id)
        
        # Check password
        if room.password and room.password != payload.password:
            await self._send_response(client_info, PacketType.SERVER_JOIN_ROOM, {
                'success': False,
                'error': 'Invalid password'
            })
            return
        
        # Check if banned
        if node_id in room.banned:
            await self._send_response(client_info, PacketType.SERVER_JOIN_ROOM, {
                'success': False,
                'error': 'You are banned from this room'
            })
            return
        
        # Check if full
        if room.is_full():
            await self._send_response(client_info, PacketType.SERVER_JOIN_ROOM, {
                'success': False,
                'error': 'Room is full'
            })
            return
        
        # Create member
        member = RoomMember(
            node_id=node_id,
            username=client_info.get('username', 'Unknown'),
            platform=client_info.get('platform', 'java'),
            role=MemberRole.OWNER if room.owner_id == node_id else MemberRole.MEMBER
        )
        
        # Add to room
        if room.add_member(member):
            client_info['rooms'].add(room_id)
            
            # Notify room members
            await self._broadcast_to_room(room_id, {
                'type': 'member_joined',
                'node_id': node_id,
                'username': member.username
            }, exclude=[node_id])
            
            # Send success response with room info
            await self._send_response(client_info, PacketType.SERVER_JOIN_ROOM, {
                'success': True,
                'room': room.to_dict()
            })
            
            logger.info(f"{node_id} joined room {room_id}")
        else:
            await self._send_response(client_info, PacketType.SERVER_JOIN_ROOM, {
                'success': False,
                'error': 'Failed to join room'
            })
    
    async def _handle_leave_room(self, packet: FastLinkPacket, 
                                client_info: Dict[str, Any]):
        """Handle leave room request"""
        if not client_info.get('authenticated'):
            return
        
        # Parse room_id from payload
        try:
            data = json.loads(packet.payload.decode())
            room_id = data.get('room_id')
        except Exception:
            return
        
        node_id = client_info['node_id']
        
        if room_id in client_info.get('rooms', set()):
            await self._remove_from_room(node_id, room_id)
    
    async def _handle_broadcast(self, packet: FastLinkPacket, 
                               client_info: Dict[str, Any]):
        """Handle broadcast message"""
        if not client_info.get('authenticated'):
            return
        
        try:
            data = json.loads(packet.payload.decode())
            room_id = data.get('room_id')
            message = data.get('message')
        except Exception:
            return
        
        node_id = client_info['node_id']
        
        # Check if in room
        if room_id not in client_info.get('rooms', set()):
            return
        
        room = self.rooms.get(room_id)
        if not room:
            return
        
        member = room.get_member(node_id)
        if not member or not member.has_permission(Permission.SEND_MESSAGE):
            return
        
        # Update activity
        member.update_activity()
        
        # Broadcast to room
        await self._broadcast_to_room(room_id, {
            'type': 'message',
            'sender_id': node_id,
            'sender_name': member.username,
            'message': message,
            'timestamp': time.time()
        })
    
    async def _handle_direct(self, packet: FastLinkPacket, 
                            client_info: Dict[str, Any]):
        """Handle direct message"""
        if not client_info.get('authenticated'):
            return
        
        try:
            data = json.loads(packet.payload.decode())
            target_id = data.get('target_id')
            message = data.get('message')
        except Exception:
            return
        
        node_id = client_info['node_id']
        
        # Send to target
        target_client = self.clients.get(target_id)
        if target_client:
            await self._send_response(target_client, PacketType.SERVER_DIRECT, {
                'type': 'direct_message',
                'sender_id': node_id,
                'sender_name': client_info.get('username'),
                'message': message,
                'timestamp': time.time()
            })
    
    async def _handle_state_sync(self, packet: FastLinkPacket, 
                                client_info: Dict[str, Any]):
        """Handle state synchronization"""
        if not client_info.get('authenticated'):
            return
        
        payload = ServerStateSyncPacket.decode(packet.payload)
        if not payload:
            return
        
        node_id = client_info['node_id']
        
        # Forward to room members
        for room_id in client_info.get('rooms', set()):
            room = self.rooms.get(room_id)
            if room:
                member = room.get_member(node_id)
                if member:
                    await self._broadcast_to_room(room_id, {
                        'type': 'state_sync',
                        'sync_type': payload.sync_type,
                        'sender_id': node_id,
                        'data': payload.data,
                        'sequence': payload.sequence
                    }, exclude=[node_id])
    
    async def _handle_room_list(self, packet: FastLinkPacket, 
                               client_info: Dict[str, Any]):
        """Handle room list request"""
        if not client_info.get('authenticated'):
            return
        
        # Return public rooms
        rooms = []
        for room_id in self.public_rooms:
            room = self.rooms.get(room_id)
            if room:
                rooms.append(room.to_dict(include_members=False))
        
        await self._send_response(client_info, PacketType.SERVER_ROOM_LIST, {
            'rooms': rooms
        })
    
    async def _broadcast_to_room(self, room_id: str, message: Dict[str, Any], 
                                exclude: List[str] = None):
        """Broadcast message to room members"""
        exclude = exclude or []
        room = self.rooms.get(room_id)
        if not room:
            return
        
        for member in room.members.values():
            if member.node_id not in exclude:
                client = self.clients.get(member.node_id)
                if client:
                    await self._send_response(client, PacketType.SERVER_BROADCAST, message)
    
    async def _send_response(self, client_info: Dict[str, Any], 
                            packet_type: PacketType, data: Dict[str, Any]):
        """Send response to client"""
        try:
            payload = json.dumps(data).encode()
            
            header = PacketHeader(
                packet_type=packet_type,
                sequence=self._next_sequence(),
                payload_length=len(payload)
            )
            
            packet = FastLinkPacket(header=header, payload=payload)
            
            writer = client_info['writer']
            writer.write(packet.encode())
            await writer.drain()
            
        except Exception as e:
            logger.debug(f"Failed to send response: {e}")
    
    async def _remove_from_room(self, node_id: str, room_id: str):
        """Remove member from room"""
        room = self.rooms.get(room_id)
        if room:
            member = room.get_member(node_id)
            if member:
                room.remove_member(node_id)
                
                # Notify others
                await self._broadcast_to_room(room_id, {
                    'type': 'member_left',
                    'node_id': node_id,
                    'username': member.username
                })
        
        # Update client info
        client = self.clients.get(node_id)
        if client:
            client['rooms'].discard(room_id)
    
    async def _disconnect_client(self, node_id: str):
        """Disconnect client"""
        client = self.clients.get(node_id)
        if not client:
            return
        
        # Leave all rooms
        for room_id in list(client.get('rooms', set())):
            await self._remove_from_room(node_id, room_id)
        
        # Remove from clients
        del self.clients[node_id]
        
        logger.info(f"Client {node_id} disconnected")
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                # Check for stale clients
                now = time.time()
                for node_id, client in list(self.clients.items()):
                    if now - client.get('last_heartbeat', client['connected_at']) > self.HEARTBEAT_TIMEOUT:
                        logger.warning(f"Client {node_id} heartbeat timeout")
                        await self._disconnect_client(node_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
    
    async def _sync_loop(self):
        """Periodic state synchronization"""
        while self.running:
            try:
                await asyncio.sleep(self.SYNC_INTERVAL)
                
                # Sync room states
                for room_id, room in self.rooms.items():
                    if room.members:
                        await self._broadcast_to_room(room_id, {
                            'type': 'room_sync',
                            'room_id': room_id,
                            'member_count': len(room.members),
                            'timestamp': time.time()
                        })
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Sync error: {e}")
    
    def _next_sequence(self) -> int:
        """Get next packet sequence number"""
        self.sequence += 1
        return self.sequence
    
    def create_room(self, name: str, visibility: RoomVisibility = RoomVisibility.PUBLIC,
                   password: Optional[str] = None, max_members: int = 100) -> str:
        """Create a new room"""
        room_id = generate_node_id()[:8]
        
        room = RoomInfo(
            room_id=room_id,
            name=name,
            visibility=visibility,
            password=password,
            max_members=max_members,
            owner_id=self.node_id
        )
        
        self.rooms[room_id] = room
        if visibility == RoomVisibility.PUBLIC:
            self.public_rooms.add(room_id)
        
        logger.info(f"Created room {room_id}: {name}")
        return room_id
    
    def get_room(self, room_id: str) -> Optional[RoomInfo]:
        """Get room information"""
        return self.rooms.get(room_id)
    
    def list_public_rooms(self) -> List[RoomInfo]:
        """List all public rooms"""
        return [self.rooms[rid] for rid in self.public_rooms if rid in self.rooms]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return {
            'clients': len(self.clients),
            'rooms': len(self.rooms),
            'public_rooms': len(self.public_rooms),
            'reputation_scores': {nid: rep.score for nid, rep in self.reputations.items()}
        }


# Example usage
if __name__ == '__main__':
    async def main():
        # Create server
        node_id = generate_node_id()
        server = FastLinkServer(node_id, ('0.0.0.0', 8765))
        
        # Start
        if await server.start():
            print(f"Server {node_id} started on port 8765")
            
            # Create a sample room
            room_id = server.create_room("Test Room", RoomVisibility.PUBLIC)
            print(f"Created room: {room_id}")
            
            try:
                while True:
                    await asyncio.sleep(10)
                    stats = server.get_stats()
                    print(f"Stats: {stats}")
            except KeyboardInterrupt:
                pass
        
        # Stop
        await server.stop()
    
    asyncio.run(main())
