"""
External TCP Server for MinecraftBC Mod

与Minecraft模组建立TCP连接，提供P2P网络管理能力。

协议:
[Length: 4字节大端] [Type: 1字节] [Payload: N字节]

This is the Python-side TCP server that the Minecraft mod connects to.
"""

import asyncio
import struct
import logging
from enum import IntEnum
from typing import Dict, List, Callable, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

from connector.hybrid_connector import HybridConnector

logger = logging.getLogger(__name__)


class PacketType(IntEnum):
    """包类型 - 必须与Java端完全一致"""
    HEARTBEAT = 0x01
    HANDSHAKE = 0x02
    SERVER_LIST = 0x03
    CONNECT_REQUEST = 0x04
    CONNECT_RESPONSE = 0x05
    DISCONNECT = 0x06
    ERROR = 0x07
    AUTH = 0x08


@dataclass
class P2PServerInfo:
    """P2P服务器信息"""
    id: str
    name: str
    description: str = ""
    host: str = ""
    port: int = 25565
    latency: int = -1
    player_count: int = 0
    max_players: int = 20
    version: str = "1.20.6"
    icon: str = ""  # Base64 encoded


@dataclass
class ModConnection:
    """模组连接状态"""
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    protocol_version: int = 1
    mod_version: int = 0
    mc_version: str = ""
    player_uuid: str = ""
    player_name: str = ""
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    
    async def send_packet(self, packet_type: PacketType, payload: bytes):
        """发送包到模组"""
        try:
            total_length = 1 + len(payload)
            header = struct.pack('>I', total_length)
            packet = header + struct.pack('B', packet_type) + payload
            self.writer.write(packet)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
    
    async def close(self):
        """关闭连接"""
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class ExternalTCPServer:
    """
    外部TCP服务器
    
    监听端口，接收Minecraft模组连接，管理P2P网络。
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 25566,
        hybrid_connector: Optional[HybridConnector] = None
    ):
        self.host = host
        self.port = port
        self.hybrid_connector = hybrid_connector
        
        self.server: Optional[asyncio.Server] = None
        self.connections: Dict[str, ModConnection] = {}  # player_uuid -> connection
        self.running = False
        
        # 回调函数
        self.on_server_list_request: Optional[Callable[[ModConnection], List[P2PServerInfo]]] = None
        self.on_connect_request: Optional[Callable[[ModConnection, str, str, int], Tuple[bool, str, int, str]]] = None
        self.on_disconnect: Optional[Callable[[ModConnection], None]] = None
        
    async def start(self):
        """启动服务器"""
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        self.running = True
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"External TCP Server started on {addr}")
        
        # 启动心跳检查
        asyncio.create_task(self._heartbeat_check())
        
    async def stop(self):
        """停止服务器"""
        self.running = False
        
        # 关闭所有连接
        for conn in list(self.connections.values()):
            await conn.close()
        self.connections.clear()
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        logger.info("External TCP Server stopped")
        
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        logger.info(f"Mod connected from {addr}")
        
        conn = ModConnection(reader=reader, writer=writer)
        
        try:
            while self.running:
                # 读取包长度
                length_data = await reader.readexactly(4)
                if not length_data:
                    break
                    
                total_length = struct.unpack('>I', length_data)[0]
                if total_length > 65536:
                    logger.error(f"Packet too large: {total_length}")
                    break
                
                # 读取包类型
                type_data = await reader.readexactly(1)
                packet_type = PacketType(type_data[0])
                
                # 读取payload
                payload_length = total_length - 1
                payload = await reader.readexactly(payload_length) if payload_length > 0 else b''
                
                # 处理包
                await self._handle_packet(conn, packet_type, payload)
                
        except asyncio.IncompleteReadError:
            logger.info(f"Mod disconnected: {addr}")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            # 清理
            if conn.player_uuid in self.connections:
                del self.connections[conn.player_uuid]
            await conn.close()
            
            if self.on_disconnect:
                try:
                    self.on_disconnect(conn)
                except Exception as e:
                    logger.error(f"Disconnect callback error: {e}")
                    
    async def _handle_packet(self, conn: ModConnection, packet_type: PacketType, payload: bytes):
        """处理收到的包"""
        handlers = {
            PacketType.HEARTBEAT: self._handle_heartbeat,
            PacketType.HANDSHAKE: self._handle_handshake,
            PacketType.CONNECT_REQUEST: self._handle_connect_request,
            PacketType.DISCONNECT: self._handle_disconnect_request,
        }
        
        handler = handlers.get(packet_type)
        if handler:
            await handler(conn, payload)
        else:
            logger.warning(f"Unknown packet type: {packet_type}")
            
    async def _handle_heartbeat(self, conn: ModConnection, payload: bytes):
        """处理心跳"""
        conn.last_heartbeat = datetime.now()
        # 回复心跳
        await conn.send_packet(PacketType.HEARTBEAT, b'')
        
    async def _handle_handshake(self, conn: ModConnection, payload: bytes):
        """处理握手"""
        try:
            idx = 0
            
            # 协议版本
            conn.protocol_version = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            
            # 模组版本
            conn.mod_version = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            
            # MC版本
            mc_version_len = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            conn.mc_version = payload[idx:idx+mc_version_len].decode('utf-8')
            idx += mc_version_len
            
            # 玩家UUID
            uuid_len = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            conn.player_uuid = payload[idx:idx+uuid_len].decode('utf-8')
            idx += uuid_len
            
            # 玩家名称
            name_len = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            conn.player_name = payload[idx:idx+name_len].decode('utf-8')
            
            # 保存连接
            self.connections[conn.player_uuid] = conn
            
            logger.info(
                f"Handshake from {conn.player_name} (UUID: {conn.player_uuid}), "
                f"MC: {conn.mc_version}, Protocol: {conn.protocol_version}"
            )
            
            # 发送服务器列表
            await self._send_server_list(conn)
            
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            
    async def _handle_connect_request(self, conn: ModConnection, payload: bytes):
        """处理连接请求"""
        try:
            idx = 0
            
            # Server ID
            server_id_len = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            server_id = payload[idx:idx+server_id_len].decode('utf-8')
            idx += server_id_len
            
            # Host
            host_len = struct.unpack('>I', payload[idx:idx+4])[0]
            idx += 4
            host = payload[idx:idx+host_len].decode('utf-8')
            idx += host_len
            
            # Port
            port = struct.unpack('>I', payload[idx:idx+4])[0]
            
            logger.info(f"Connect request from {conn.player_name} to {server_id} ({host}:{port})")
            
            # 调用回调
            if self.on_connect_request:
                success, local_host, local_port, message = self.on_connect_request(conn, server_id, host, port)
            else:
                # 默认使用P2P连接器
                if self.hybrid_connector:
                    success, local_host, local_port, message = await self._establish_p2p_connection(
                        conn, server_id, host, port
                    )
                else:
                    success = False
                    local_host = ""
                    local_port = 0
                    message = "P2P connector not available"
            
            # 发送响应
            await self._send_connect_response(conn, success, server_id, local_host, local_port, message)
            
        except Exception as e:
            logger.error(f"Connect request error: {e}")
            await self._send_connect_response(conn, False, "", "", 0, str(e))
            
    async def _handle_disconnect_request(self, conn: ModConnection, payload: bytes):
        """处理断开请求"""
        logger.info(f"Disconnect request from {conn.player_name}")
        # 清理P2P连接
        if self.hybrid_connector:
            await self.hybrid_connector.disconnect_all()
            
    async def _send_connect_response(
        self,
        conn: ModConnection,
        success: bool,
        server_id: str,
        local_host: str,
        local_port: int,
        message: str
    ):
        """发送连接响应"""
        try:
            payload = struct.pack('>?', success)
            
            # Server ID
            server_id_bytes = server_id.encode('utf-8')
            payload += struct.pack('>I', len(server_id_bytes)) + server_id_bytes
            
            # Local host
            host_bytes = local_host.encode('utf-8')
            payload += struct.pack('>I', len(host_bytes)) + host_bytes
            
            # Local port
            payload += struct.pack('>I', local_port)
            
            # Message
            msg_bytes = message.encode('utf-8')
            payload += struct.pack('>I', len(msg_bytes)) + msg_bytes
            
            await conn.send_packet(PacketType.CONNECT_RESPONSE, payload)
            
        except Exception as e:
            logger.error(f"Failed to send connect response: {e}")
            
    async def _send_server_list(self, conn: ModConnection):
        """发送服务器列表到模组"""
        try:
            if self.on_server_list_request:
                servers = self.on_server_list_request(conn)
            else:
                servers = self._get_default_servers()
                
            # 构建payload
            payload = struct.pack('>I', len(servers))
            
            for server in servers:
                # ID
                id_bytes = server.id.encode('utf-8')
                payload += struct.pack('>I', len(id_bytes)) + id_bytes
                
                # Name
                name_bytes = server.name.encode('utf-8')
                payload += struct.pack('>I', len(name_bytes)) + name_bytes
                
                # Description
                desc_bytes = server.description.encode('utf-8')
                payload += struct.pack('>I', len(desc_bytes)) + desc_bytes
                
                # Host
                host_bytes = server.host.encode('utf-8')
                payload += struct.pack('>I', len(host_bytes)) + host_bytes
                
                # Port, Latency, PlayerCount, MaxPlayers
                payload += struct.pack('>I', server.port)
                payload += struct.pack('>I', server.latency)
                payload += struct.pack('>I', server.player_count)
                payload += struct.pack('>I', server.max_players)
                
                # Version
                ver_bytes = server.version.encode('utf-8')
                payload += struct.pack('>I', len(ver_bytes)) + ver_bytes
            
            await conn.send_packet(PacketType.SERVER_LIST, payload)
            logger.debug(f"Sent {len(servers)} servers to {conn.player_name}")
            
        except Exception as e:
            logger.error(f"Failed to send server list: {e}")
            
    def _get_default_servers(self) -> List[P2PServerInfo]:
        """获取默认服务器列表"""
        # 如果有P2P连接器，从那里获取
        if self.hybrid_connector:
            # 转换P2P节点信息
            return self._convert_p2p_nodes()
        
        # 返回空列表或测试服务器
        return []
        
    def _convert_p2p_nodes(self) -> List[P2PServerInfo]:
        """转换P2P节点到服务器信息"""
        servers = []
        # 从hybrid_connector获取可用节点
        # 这里需要实现节点发现逻辑
        return servers
        
    async def _establish_p2p_connection(
        self,
        conn: ModConnection,
        server_id: str,
        host: str,
        port: int
    ) -> Tuple[bool, str, int, str]:
        """
        建立P2P连接
        
        返回: (success, local_host, local_port, message)
        """
        if not self.hybrid_connector:
            return False, "", 0, "P2P connector not initialized"
            
        try:
            # 使用hybrid_connector建立P2P连接
            # 创建本地代理端口
            local_port = await self.hybrid_connector.create_proxy_tunnel(server_id, host, port)
            
            if local_port > 0:
                return True, "127.0.0.1", local_port, "P2P connection established"
            else:
                return False, "", 0, "Failed to create proxy tunnel"
                
        except Exception as e:
            logger.error(f"P2P connection error: {e}")
            return False, "", 0, f"P2P error: {str(e)}"
            
    async def _heartbeat_check(self):
        """定期检查心跳"""
        while self.running:
            await asyncio.sleep(10)
            
            now = datetime.now()
            dead_connections = []
            
            for uuid, conn in self.connections.items():
                # 30秒无心跳视为断开
                if (now - conn.last_heartbeat).total_seconds() > 30:
                    logger.warning(f"Connection timeout: {conn.player_name}")
                    dead_connections.append(uuid)
                    
            # 清理死连接
            for uuid in dead_connections:
                if uuid in self.connections:
                    await self.connections[uuid].close()
                    del self.connections[uuid]
                    
    async def broadcast_server_list_update(self):
        """广播服务器列表更新到所有连接"""
        for conn in self.connections.values():
            await self._send_server_list(conn)
            
    def get_connection_count(self) -> int:
        """获取连接数"""
        return len(self.connections)
        
    def get_connection_info(self) -> List[Dict]:
        """获取连接信息"""
        return [
            {
                "player_name": conn.player_name,
                "player_uuid": conn.player_uuid,
                "mc_version": conn.mc_version,
                "connected_at": conn.connected_at.isoformat(),
                "last_heartbeat": conn.last_heartbeat.isoformat()
            }
            for conn in self.connections.values()
        ]
