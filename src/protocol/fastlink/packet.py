"""
FastLink Protocol Packet Definitions
FastLink 协议数据包定义

This module defines the core packet structures for FastLink P2P and Server protocols.
"""

from __future__ import annotations
import struct
import json
import hashlib
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Union
from enum import IntEnum, auto
from datetime import datetime


class PacketType(IntEnum):
    """FastLink packet types"""
    # P2P packets
    P2P_HANDSHAKE = 0x01
    P2P_HEARTBEAT = 0x02
    P2P_DATA = 0x03
    P2P_DISCONNECT = 0x04
    P2P_NAT_PUNCH = 0x05
    
    # Server packets
    SERVER_AUTH = 0x10
    SERVER_JOIN_ROOM = 0x11
    SERVER_LEAVE_ROOM = 0x12
    SERVER_BROADCAST = 0x13
    SERVER_DIRECT = 0x14
    SERVER_STATE_SYNC = 0x15
    SERVER_ROOM_LIST = 0x16
    
    # MnMCP packets
    MNMCP_ENTITY = 0x20
    MNMCP_BLOCK = 0x21
    MNMCP_ITEM = 0x22
    MNMCP_EVENT = 0x23
    MNMCP_CHAT = 0x24
    MNMCP_COMMAND = 0x25


class ProtocolVersion(IntEnum):
    """Protocol versions"""
    V1_0 = 0x0100
    V1_1 = 0x0101
    V2_0 = 0x0200


@dataclass
class PacketHeader:
    """FastLink packet header"""
    magic: bytes = b'FLNK'  # Magic number
    version: int = ProtocolVersion.V2_0
    packet_type: PacketType = PacketType.P2P_DATA
    sequence: int = 0
    timestamp: int = 0
    payload_length: int = 0
    checksum: int = 0
    
    HEADER_SIZE = 24
    
    def encode(self) -> bytes:
        """Encode header to bytes"""
        return struct.pack(
            '>4sHHIIII',
            self.magic,
            self.version,
            self.packet_type,
            self.sequence,
            self.timestamp,
            self.payload_length,
            self.checksum
        )
    
    @classmethod
    def decode(cls, data: bytes) -> Optional[PacketHeader]:
        """Decode header from bytes"""
        if len(data) < cls.HEADER_SIZE:
            return None
        
        magic, version, pkt_type, seq, ts, length, checksum = struct.unpack(
            '>4sHHIIII', data[:cls.HEADER_SIZE]
        )
        
        if magic != b'FLNK':
            return None
        
        return cls(
            magic=magic,
            version=version,
            packet_type=PacketType(pkt_type),
            sequence=seq,
            timestamp=ts,
            payload_length=length,
            checksum=checksum
        )
    
    def calculate_checksum(self, payload: bytes) -> int:
        """Calculate CRC32 checksum"""
        import binascii
        return binascii.crc32(payload) & 0xFFFFFFFF


@dataclass
class FastLinkPacket:
    """Complete FastLink packet"""
    header: PacketHeader
    payload: bytes
    
    def encode(self) -> bytes:
        """Encode complete packet"""
        self.header.payload_length = len(self.payload)
        self.header.checksum = self.header.calculate_checksum(self.payload)
        self.header.timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        return self.header.encode() + self.payload
    
    @classmethod
    def decode(cls, data: bytes) -> Optional[FastLinkPacket]:
        """Decode complete packet"""
        header = PacketHeader.decode(data)
        if not header:
            return None
        
        payload_start = PacketHeader.HEADER_SIZE
        payload_end = payload_start + header.payload_length
        
        if len(data) < payload_end:
            return None
        
        payload = data[payload_start:payload_end]
        
        # Verify checksum
        if header.calculate_checksum(payload) != header.checksum:
            return None
        
        return cls(header=header, payload=payload)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            'header': {
                'version': self.header.version,
                'packet_type': self.header.packet_type.name,
                'sequence': self.header.sequence,
                'timestamp': self.header.timestamp,
                'payload_length': self.header.payload_length,
                'checksum': self.header.checksum
            },
            'payload': self.payload.hex() if isinstance(self.payload, bytes) else self.payload
        }


# ============================================================================
# P2P Protocol Packets
# ============================================================================

@dataclass
class P2PHandshakePacket:
    """P2P handshake packet"""
    node_id: str
    protocol_version: int
    capabilities: List[str]
    public_key: str
    nonce: bytes
    
    def encode(self) -> bytes:
        """Encode to JSON bytes"""
        data = {
            'node_id': self.node_id,
            'protocol_version': self.protocol_version,
            'capabilities': self.capabilities,
            'public_key': self.public_key,
            'nonce': self.nonce.hex() if isinstance(self.nonce, bytes) else self.nonce
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[P2PHandshakePacket]:
        """Decode from JSON bytes"""
        try:
            data = json.loads(payload.decode('utf-8'))
            nonce = data.get('nonce', '')
            if isinstance(nonce, str):
                nonce = bytes.fromhex(nonce)
            return cls(
                node_id=data['node_id'],
                protocol_version=data['protocol_version'],
                capabilities=data.get('capabilities', []),
                public_key=data.get('public_key', ''),
                nonce=nonce
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None


@dataclass
class P2PHeartbeatPacket:
    """P2P heartbeat packet"""
    node_id: str
    latency_ms: int
    connected_peers: int
    room_id: Optional[str] = None
    
    def encode(self) -> bytes:
        data = {
            'node_id': self.node_id,
            'latency_ms': self.latency_ms,
            'connected_peers': self.connected_peers,
            'room_id': self.room_id
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[P2PHeartbeatPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                node_id=data['node_id'],
                latency_ms=data.get('latency_ms', 0),
                connected_peers=data.get('connected_peers', 0),
                room_id=data.get('room_id')
            )
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class P2PNATPunchPacket:
    """NAT hole punching packet"""
    punch_id: str
    external_ip: str
    external_port: int
    internal_ip: str
    internal_port: int
    
    def encode(self) -> bytes:
        data = {
            'punch_id': self.punch_id,
            'external_ip': self.external_ip,
            'external_port': self.external_port,
            'internal_ip': self.internal_ip,
            'internal_port': self.internal_port
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[P2PNATPunchPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                punch_id=data['punch_id'],
                external_ip=data['external_ip'],
                external_port=data['external_port'],
                internal_ip=data['internal_ip'],
                internal_port=data['internal_port']
            )
        except (json.JSONDecodeError, KeyError):
            return None


# ============================================================================
# Server Protocol Packets
# ============================================================================

@dataclass
class ServerAuthPacket:
    """Server authentication packet"""
    username: str
    token: str
    client_version: str
    platform: str  # java, bedrock, etc.
    
    def encode(self) -> bytes:
        data = {
            'username': self.username,
            'token': self.token,
            'client_version': self.client_version,
            'platform': self.platform
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[ServerAuthPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                username=data['username'],
                token=data['token'],
                client_version=data.get('client_version', 'unknown'),
                platform=data.get('platform', 'java')
            )
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class ServerJoinRoomPacket:
    """Join room packet"""
    room_id: str
    password: Optional[str] = None
    player_data: Dict[str, Any] = None
    
    def encode(self) -> bytes:
        data = {
            'room_id': self.room_id,
            'password': self.password,
            'player_data': self.player_data or {}
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[ServerJoinRoomPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                room_id=data['room_id'],
                password=data.get('password'),
                player_data=data.get('player_data', {})
            )
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class ServerStateSyncPacket:
    """State synchronization packet"""
    sync_type: str  # 'full', 'delta', 'entity', 'block', 'player'
    timestamp: int
    data: Dict[str, Any]
    sequence: int
    
    def encode(self) -> bytes:
        data = {
            'sync_type': self.sync_type,
            'timestamp': self.timestamp,
            'data': self.data,
            'sequence': self.sequence
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[ServerStateSyncPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                sync_type=data['sync_type'],
                timestamp=data['timestamp'],
                data=data.get('data', {}),
                sequence=data.get('sequence', 0)
            )
        except (json.JSONDecodeError, KeyError):
            return None


# ============================================================================
# MnMCP Protocol Packets
# ============================================================================

@dataclass
class MnMCPEntityPacket:
    """MnMCP entity packet for cross-game entity sync"""
    entity_id: str
    source_game: str  # 'minecraft', 'miniworld', etc.
    target_game: str
    entity_type: str
    position: Dict[str, float]  # x, y, z
    rotation: Dict[str, float]   # yaw, pitch
    velocity: Dict[str, float]   # vx, vy, vz
    metadata: Dict[str, Any]
    action: str  # 'spawn', 'update', 'despawn', 'interact'
    
    def encode(self) -> bytes:
        data = {
            'entity_id': self.entity_id,
            'source_game': self.source_game,
            'target_game': self.target_game,
            'entity_type': self.entity_type,
            'position': self.position,
            'rotation': self.rotation,
            'velocity': self.velocity,
            'metadata': self.metadata,
            'action': self.action
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[MnMCPEntityPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                entity_id=data['entity_id'],
                source_game=data['source_game'],
                target_game=data['target_game'],
                entity_type=data['entity_type'],
                position=data.get('position', {'x': 0, 'y': 0, 'z': 0}),
                rotation=data.get('rotation', {'yaw': 0, 'pitch': 0}),
                velocity=data.get('velocity', {'vx': 0, 'vy': 0, 'vz': 0}),
                metadata=data.get('metadata', {}),
                action=data.get('action', 'update')
            )
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class MnMCPBlockPacket:
    """MnMCP block packet for cross-game block sync"""
    block_id: str
    source_game: str
    target_game: str
    position: Dict[str, int]  # x, y, z
    block_type: str
    block_state: Dict[str, Any]
    action: str  # 'place', 'break', 'update'
    
    def encode(self) -> bytes:
        data = {
            'block_id': self.block_id,
            'source_game': self.source_game,
            'target_game': self.target_game,
            'position': self.position,
            'block_type': self.block_type,
            'block_state': self.block_state,
            'action': self.action
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[MnMCPBlockPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                block_id=data['block_id'],
                source_game=data['source_game'],
                target_game=data['target_game'],
                position=data['position'],
                block_type=data['block_type'],
                block_state=data.get('block_state', {}),
                action=data.get('action', 'update')
            )
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class MnMCPChatPacket:
    """MnMCP chat packet for cross-game communication"""
    message_id: str
    sender_id: str
    sender_name: str
    source_game: str
    target_game: str
    message: str
    message_type: str  # 'global', 'room', 'whisper', 'system'
    timestamp: int
    
    def encode(self) -> bytes:
        data = {
            'message_id': self.message_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'source_game': self.source_game,
            'target_game': self.target_game,
            'message': self.message,
            'message_type': self.message_type,
            'timestamp': self.timestamp
        }
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def decode(cls, payload: bytes) -> Optional[MnMCPChatPacket]:
        try:
            data = json.loads(payload.decode('utf-8'))
            return cls(
                message_id=data['message_id'],
                sender_id=data['sender_id'],
                sender_name=data['sender_name'],
                source_game=data['source_game'],
                target_game=data['target_game'],
                message=data['message'],
                message_type=data.get('message_type', 'global'),
                timestamp=data.get('timestamp', 0)
            )
        except (json.JSONDecodeError, KeyError):
            return None


# ============================================================================
# Packet Factory
# ============================================================================

class PacketFactory:
    """Factory for creating and decoding packets"""
    
    _decoders = {
        PacketType.P2P_HANDSHAKE: P2PHandshakePacket,
        PacketType.P2P_HEARTBEAT: P2PHeartbeatPacket,
        PacketType.P2P_NAT_PUNCH: P2PNATPunchPacket,
        PacketType.SERVER_AUTH: ServerAuthPacket,
        PacketType.SERVER_JOIN_ROOM: ServerJoinRoomPacket,
        PacketType.SERVER_STATE_SYNC: ServerStateSyncPacket,
        PacketType.MNMCP_ENTITY: MnMCPEntityPacket,
        PacketType.MNMCP_BLOCK: MnMCPBlockPacket,
        PacketType.MNMCP_CHAT: MnMCPChatPacket,
    }
    
    @classmethod
    def create_packet(cls, packet_type: PacketType, data: Any, sequence: int = 0) -> FastLinkPacket:
        """Create a complete FastLink packet"""
        payload = data.encode() if hasattr(data, 'encode') else json.dumps(data).encode()
        
        header = PacketHeader(
            packet_type=packet_type,
            sequence=sequence,
            payload_length=len(payload)
        )
        
        return FastLinkPacket(header=header, payload=payload)
    
    @classmethod
    def decode_payload(cls, packet: FastLinkPacket) -> Optional[Any]:
        """Decode packet payload based on type"""
        decoder = cls._decoders.get(packet.header.packet_type)
        if decoder:
            return decoder.decode(packet.payload)
        return None


# ============================================================================
# Utility Functions
# ============================================================================

def generate_node_id() -> str:
    """Generate a unique node ID"""
    import uuid
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]


def generate_punch_id() -> str:
    """Generate a unique punch ID for NAT traversal"""
    import uuid
    return f"punch_{uuid.uuid4().hex[:12]}"


def create_heartbeat(node_id: str, latency_ms: int = 0, peers: int = 0) -> FastLinkPacket:
    """Create a heartbeat packet"""
    data = P2PHeartbeatPacket(
        node_id=node_id,
        latency_ms=latency_ms,
        connected_peers=peers
    )
    return PacketFactory.create_packet(PacketType.P2P_HEARTBEAT, data)


def create_handshake(node_id: str, public_key: str, capabilities: List[str]) -> FastLinkPacket:
    """Create a handshake packet"""
    import os
    data = P2PHandshakePacket(
        node_id=node_id,
        protocol_version=ProtocolVersion.V2_0,
        capabilities=capabilities,
        public_key=public_key,
        nonce=os.urandom(32)
    )
    return PacketFactory.create_packet(PacketType.P2P_HANDSHAKE, data)


# Example usage
if __name__ == '__main__':
    # Create a sample packet
    node_id = generate_node_id()
    print(f"Generated node ID: {node_id}")
    
    # Create handshake packet
    handshake = create_handshake(
        node_id=node_id,
        public_key="sample_public_key",
        capabilities=["p2p", "server", "mnmcp"]
    )
    
    # Encode
    encoded = handshake.encode()
    print(f"Encoded packet length: {len(encoded)} bytes")
    
    # Decode
    decoded = FastLinkPacket.decode(encoded)
    if decoded:
        print(f"Decoded packet type: {decoded.header.packet_type.name}")
        payload = PacketFactory.decode_payload(decoded)
        if payload:
            print(f"Payload node_id: {payload.node_id}")
    
    print("Packet definitions loaded successfully!")
