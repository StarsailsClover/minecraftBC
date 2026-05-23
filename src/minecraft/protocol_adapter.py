"""
Minecraft Protocol Adapter

适配不同Minecraft版本的协议差异。
支持1.12.2到1.20.x的多版本。
"""

from __future__ import annotations
import struct
import json
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)


class ProtocolVersion(IntEnum):
    """Minecraft协议版本号"""
    V1_12_2 = 340
    V1_16_5 = 754
    V1_18_2 = 758
    V1_19_2 = 760
    V1_20_1 = 763
    V1_20_4 = 765


@dataclass
class ServerInfo:
    """服务器状态信息"""
    version: str
    protocol: int
    max_players: int
    online_players: int
    motd: str
    favicon: Optional[str] = None


class MinecraftProtocolAdapter:
    """
    Minecraft协议适配器
    
    处理不同版本的协议差异，包括:
    - 包ID映射
    - 数据格式转换
    - 状态查询
    
    支持的版本:
    - 1.12.2
    - 1.16.5
    - 1.18.2
    - 1.19.2
    - 1.20.1
    - 1.20.4
    """
    
    # 包ID映射 (packet_name -> {version -> packet_id})
    PACKET_IDS = {
        # Handshake
        'handshake': {
            ProtocolVersion.V1_12_2: 0x00,
            ProtocolVersion.V1_16_5: 0x00,
            ProtocolVersion.V1_18_2: 0x00,
            ProtocolVersion.V1_20_1: 0x00,
        },
        # Status
        'status_request': {
            ProtocolVersion.V1_12_2: 0x00,
            ProtocolVersion.V1_16_5: 0x00,
            ProtocolVersion.V1_18_2: 0x00,
            ProtocolVersion.V1_20_1: 0x00,
        },
        'status_response': {
            ProtocolVersion.V1_12_2: 0x00,
            ProtocolVersion.V1_16_5: 0x00,
            ProtocolVersion.V1_18_2: 0x00,
            ProtocolVersion.V1_20_1: 0x00,
        },
        # Login
        'login_start': {
            ProtocolVersion.V1_12_2: 0x00,
            ProtocolVersion.V1_16_5: 0x00,
            ProtocolVersion.V1_18_2: 0x00,
            ProtocolVersion.V1_20_1: 0x00,
        },
        'login_success': {
            ProtocolVersion.V1_12_2: 0x02,
            ProtocolVersion.V1_16_5: 0x02,
            ProtocolVersion.V1_18_2: 0x02,
            ProtocolVersion.V1_20_1: 0x02,
        },
        # Play
        'join_game': {
            ProtocolVersion.V1_12_2: 0x23,
            ProtocolVersion.V1_16_5: 0x24,
            ProtocolVersion.V1_18_2: 0x25,
            ProtocolVersion.V1_20_1: 0x28,
        },
        'player_position': {
            ProtocolVersion.V1_12_2: 0x0C,
            ProtocolVersion.V1_16_5: 0x11,
            ProtocolVersion.V1_18_2: 0x11,
            ProtocolVersion.V1_20_1: 0x14,
        },
        'chat_message': {
            ProtocolVersion.V1_12_2: 0x02,
            ProtocolVersion.V1_16_5: 0x0E,
            ProtocolVersion.V1_18_2: 0x0F,
            ProtocolVersion.V1_20_1: 0x31,
        },
    }
    
    def __init__(self, version: ProtocolVersion = ProtocolVersion.V1_20_1):
        """
        初始化协议适配器
        
        Args:
            version: 目标协议版本
        """
        self.version = version
        self._packet_id_cache: Dict[str, int] = {}
        self._build_cache()
    
    def _build_cache(self) -> None:
        """构建包ID缓存"""
        for packet_name, versions in self.PACKET_IDS.items():
            if self.version in versions:
                self._packet_id_cache[packet_name] = versions[self.version]
            else:
                # 使用最近的版本
                sorted_versions = sorted(versions.keys())
                # 找到小于等于当前版本的最新版本
                closest = None
                for v in sorted_versions:
                    if v <= self.version:
                        closest = v
                if closest:
                    self._packet_id_cache[packet_name] = versions[closest]
    
    def get_packet_id(self, packet_name: str) -> Optional[int]:
        """
        获取包ID
        
        Args:
            packet_name: 包名称
        
        Returns:
            包ID或None
        """
        return self._packet_id_cache.get(packet_name)
    
    def encode_string(self, s: str) -> bytes:
        """编码字符串（UTF-8 + varint长度）"""
        data = s.encode('utf-8')
        length = len(data)
        return self.encode_varint(length) + data
    
    def encode_varint(self, value: int) -> bytes:
        """编码varint"""
        result = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                byte |= 0x80
            result.append(byte)
            if not value:
                break
        return bytes(result)
    
    def encode_short(self, value: int) -> bytes:
        """编码short (2 bytes)"""
        return struct.pack('>H', value)
    
    def encode_int(self, value: int) -> bytes:
        """编码int (4 bytes)"""
        return struct.pack('>i', value)
    
    def encode_long(self, value: int) -> bytes:
        """编码long (8 bytes)"""
        return struct.pack('>q', value)
    
    def encode_float(self, value: float) -> bytes:
        """编码float (4 bytes)"""
        return struct.pack('>f', value)
    
    def encode_double(self, value: float) -> bytes:
        """编码double (8 bytes)"""
        return struct.pack('>d', value)
    
    def encode_bool(self, value: bool) -> bytes:
        """编码bool (1 byte)"""
        return b'\x01' if value else b'\x00'
    
    def decode_string(self, data: bytes, offset: int = 0) -> Tuple[str, int]:
        """解码字符串"""
        length, offset = self.decode_varint(data, offset)
        string_data = data[offset:offset + length]
        return string_data.decode('utf-8'), offset + length
    
    def decode_varint(self, data: bytes, offset: int = 0) -> Tuple[int, int]:
        """解码varint"""
        result = 0
        shift = 0
        pos = offset
        
        while True:
            if pos >= len(data):
                raise ValueError("Incomplete varint")
            
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            
            if not (byte & 0x80):
                break
            
            shift += 7
            if shift >= 35:
                raise ValueError("Varint too large")
        
        return result, pos
    
    def decode_short(self, data: bytes, offset: int = 0) -> Tuple[int, int]:
        """解码short"""
        value = struct.unpack_from('>H', data, offset)[0]
        return value, offset + 2
    
    def decode_int(self, data: bytes, offset: int = 0) -> Tuple[int, int]:
        """解码int"""
        value = struct.unpack_from('>i', data, offset)[0]
        return value, offset + 4
    
    def create_handshake_packet(self, protocol_version: int,
                                server_address: str,
                                server_port: int,
                                next_state: int) -> bytes:
        """
        创建握手包
        
        Args:
            protocol_version: 协议版本号
            server_address: 服务器地址
            server_port: 服务器端口
            next_state: 下一个状态 (1=status, 2=login)
        
        Returns:
            编码后的数据包
        """
        # 构建包内容
        data = self.encode_varint(protocol_version)
        data += self.encode_string(server_address)
        data += self.encode_short(server_port)
        data += self.encode_varint(next_state)
        
        # 获取包ID
        packet_id = self.get_packet_id('handshake') or 0x00
        
        # 包格式: [length] [packet_id] [data]
        packet_data = self.encode_varint(packet_id) + data
        length = self.encode_varint(len(packet_data))
        
        return length + packet_data
    
    def create_status_request(self) -> bytes:
        """创建状态请求包"""
        packet_id = self.get_packet_id('status_request') or 0x00
        packet_data = self.encode_varint(packet_id)
        length = self.encode_varint(len(packet_data))
        return length + packet_data
    
    def parse_status_response(self, data: bytes) -> Optional[ServerInfo]:
        """解析状态响应"""
        try:
            # 解码字符串
            json_str, _ = self.decode_string(data)
            response = json.loads(json_str)
            
            version_info = response.get('version', {})
            players_info = response.get('players', {})
            
            return ServerInfo(
                version=version_info.get('name', 'Unknown'),
                protocol=version_info.get('protocol', 0),
                max_players=players_info.get('max', 0),
                online_players=players_info.get('online', 0),
                motd=response.get('description', {}).get('text', '') if isinstance(response.get('description'), dict) else str(response.get('description', '')),
                favicon=response.get('favicon')
            )
        except Exception as e:
            logger.error(f"Failed to parse status response: {e}")
            return None
    
    def create_login_start(self, username: str) -> bytes:
        """创建登录开始包"""
        data = self.encode_string(username)
        
        packet_id = self.get_packet_id('login_start') or 0x00
        packet_data = self.encode_varint(packet_id) + data
        length = self.encode_varint(len(packet_data))
        
        return length + packet_data
    
    def parse_login_success(self, data: bytes) -> Optional[Tuple[str, str]]:
        """
        解析登录成功包
        
        Returns:
            (uuid, username) 或 None
        """
        try:
            offset = 0
            uuid_str, offset = self.decode_string(data, offset)
            username, offset = self.decode_string(data, offset)
            return uuid_str, username
        except Exception as e:
            logger.error(f"Failed to parse login success: {e}")
            return None
    
    @classmethod
    def for_version(cls, version_str: str) -> 'MinecraftProtocolAdapter':
        """
        为指定版本创建适配器
        
        Args:
            version_str: 版本号字符串 (如 "1.20.1")
        
        Returns:
            协议适配器实例
        """
        version_map = {
            '1.12.2': ProtocolVersion.V1_12_2,
            '1.16.5': ProtocolVersion.V1_16_5,
            '1.18.2': ProtocolVersion.V1_18_2,
            '1.19.2': ProtocolVersion.V1_19_2,
            '1.20.1': ProtocolVersion.V1_20_1,
            '1.20.4': ProtocolVersion.V1_20_4,
        }
        
        protocol_version = version_map.get(version_str, ProtocolVersion.V1_20_1)
        return cls(protocol_version)
    
    def get_supported_versions(self) -> list[str]:
        """获取支持的版本列表"""
        return ['1.12.2', '1.16.5', '1.18.2', '1.19.2', '1.20.1', '1.20.4']


# 快捷函数
def create_adapter(version: str = "1.20.1") -> MinecraftProtocolAdapter:
    """创建协议适配器"""
    return MinecraftProtocolAdapter.for_version(version)
