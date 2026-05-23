"""
Minecraft Proxy Handler

处理Minecraft客户端与服务器之间的TCP连接转发。
支持数据包拦截、修改和注入。

功能:
- TCP连接代理
- Minecraft协议数据包解析
- 数据包修改（用于跨游戏映射）
- 压缩/加密处理
"""

from __future__ import annotations
import asyncio
import struct
import logging
from typing import Optional, Dict, Callable, Any, Tuple, BinaryIO
from dataclasses import dataclass
from enum import IntEnum
from io import BytesIO

logger = logging.getLogger(__name__)


class PacketState(IntEnum):
    """Minecraft连接状态"""
    HANDSHAKE = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3


class PacketDirection(IntEnum):
    """数据包方向"""
    CLIENT_TO_SERVER = 0
    SERVER_TO_CLIENT = 1


@dataclass
class MinecraftPacket:
    """
    Minecraft数据包
    
    格式:
    [Length: varint] [Packet ID: varint] [Data: bytes]
    """
    packet_id: int
    data: bytes
    compressed: bool = False
    
    def encode(self) -> bytes:
        """编码为字节"""
        # 包ID + 数据
        packet_data = encode_varint(self.packet_id) + self.data
        
        if self.compressed:
            # TODO: 压缩处理
            pass
        
        # 长度 + 包数据
        length = encode_varint(len(packet_data))
        return length + packet_data


def encode_varint(value: int) -> bytes:
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


def decode_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """解码varint，返回(值, 新偏移)"""
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


class MinecraftProxy:
    """
    Minecraft连接代理
    
    在客户端和服务器之间建立透明代理，
    可以拦截和修改数据包。
    
    使用示例:
    ```python
    proxy = MinecraftProxy()
    proxy.on_packet(packet_handler)
    await proxy.start(local_port=25565, target_host='mc.example.com', target_port=25565)
    ```
    """
    
    def __init__(self, compression_threshold: int = 256):
        """
        初始化代理
        
        Args:
            compression_threshold: 压缩阈值（字节）
        """
        self.compression_threshold = compression_threshold
        
        # 连接映射
        self._client_to_server: Dict[str, asyncio.Transport] = {}
        self._server_to_client: Dict[str, asyncio.Transport] = {}
        
        # 状态
        self._connection_states: Dict[str, PacketState] = {}
        
        # 回调
        self._packet_handlers: list[Callable[[PacketDirection, MinecraftPacket], Optional[MinecraftPacket]]] = []
        self._connect_handlers: list[Callable[[str], None]] = []
        self._disconnect_handlers: list[Callable[[str], None]] = []
        
        # 服务器
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False
    
    def on_packet(self, handler: Callable[[PacketDirection, MinecraftPacket], Optional[MinecraftPacket]]):
        """
        注册数据包处理器
        
        Args:
            handler: (direction, packet) -> modified_packet or None
        """
        self._packet_handlers.append(handler)
        return self
    
    def on_connect(self, handler: Callable[[str], None]):
        """注册连接处理器"""
        self._connect_handlers.append(handler)
        return self
    
    def on_disconnect(self, handler: Callable[[str], None]):
        """注册断开处理器"""
        self._disconnect_handlers.append(handler)
        return self
    
    async def start(self, local_port: int, target_host: str, target_port: int) -> bool:
        """
        启动代理服务器
        
        Args:
            local_port: 本地监听端口
            target_host: 目标服务器主机
            target_port: 目标服务器端口
        
        Returns:
            启动成功返回True
        """
        try:
            logger.info(f"Starting Minecraft proxy on port {local_port} -> {target_host}:{target_port}")
            
            self._server = await asyncio.start_server(
                lambda r, w: self._handle_client(r, w, target_host, target_port),
                '0.0.0.0', local_port
            )
            
            self._running = True
            logger.info("Minecraft proxy started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start proxy: {e}")
            return False
    
    async def stop(self) -> None:
        """停止代理服务器"""
        self._running = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # 关闭所有连接
        for conn_id in list(self._client_to_server.keys()):
            await self._disconnect(conn_id)
        
        logger.info("Minecraft proxy stopped")
    
    async def _handle_client(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter,
                             target_host: str, target_port: int) -> None:
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        conn_id = f"{addr[0]}:{addr[1]}"
        
        logger.info(f"Client connected: {conn_id}")
        
        try:
            # 连接到目标服务器
            server_reader, server_writer = await asyncio.open_connection(
                target_host, target_port
            )
            
            self._client_to_server[conn_id] = writer
            self._server_to_client[conn_id] = server_writer
            self._connection_states[conn_id] = PacketState.HANDSHAKE
            
            # 通知
            for handler in self._connect_handlers:
                try:
                    handler(conn_id)
                except Exception as e:
                    logger.error(f"Connect handler error: {e}")
            
            # 双向转发
            await asyncio.gather(
                self._forward_client_to_server(conn_id, reader, server_writer),
                self._forward_server_to_client(conn_id, server_reader, writer)
            )
            
        except Exception as e:
            logger.error(f"Proxy error for {conn_id}: {e}")
        finally:
            await self._disconnect(conn_id)
    
    async def _forward_client_to_server(self, conn_id: str,
                                         client_reader: asyncio.StreamReader,
                                         server_writer: asyncio.StreamWriter) -> None:
        """转发客户端到服务器"""
        try:
            while self._running:
                # 读取包长度
                length_data = await client_reader.readexactly(1)
                length, _ = decode_varint(length_data)
                
                # 读取完整包
                packet_data = await client_reader.readexactly(length)
                
                # 解析包
                packet = self._parse_packet(packet_data)
                
                # 处理包
                modified = self._handle_packet(PacketDirection.CLIENT_TO_SERVER, packet)
                
                if modified:
                    # 转发修改后的包
                    encoded = modified.encode()
                    server_writer.write(encoded)
                    await server_writer.drain()
                
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logger.error(f"Forward C2S error: {e}")
    
    async def _forward_server_to_client(self, conn_id: str,
                                         server_reader: asyncio.StreamReader,
                                         client_writer: asyncio.StreamWriter) -> None:
        """转发服务器到客户端"""
        try:
            while self._running:
                # 读取包长度
                length_data = await server_reader.readexactly(1)
                length, _ = decode_varint(length_data)
                
                # 读取完整包
                packet_data = await server_reader.readexactly(length)
                
                # 解析包
                packet = self._parse_packet(packet_data)
                
                # 处理包
                modified = self._handle_packet(PacketDirection.SERVER_TO_CLIENT, packet)
                
                if modified:
                    # 转发修改后的包
                    encoded = modified.encode()
                    client_writer.write(encoded)
                    await client_writer.drain()
                
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logger.error(f"Forward S2C error: {e}")
    
    def _parse_packet(self, data: bytes) -> MinecraftPacket:
        """解析Minecraft数据包"""
        packet_id, offset = decode_varint(data)
        packet_data = data[offset:]
        return MinecraftPacket(packet_id=packet_id, data=packet_data)
    
    def _handle_packet(self, direction: PacketDirection,
                       packet: MinecraftPacket) -> Optional[MinecraftPacket]:
        """处理数据包"""
        current = packet
        
        for handler in self._packet_handlers:
            try:
                result = handler(direction, current)
                if result is None:
                    # 丢弃包
                    return None
                current = result
            except Exception as e:
                logger.error(f"Packet handler error: {e}")
        
        return current
    
    async def _disconnect(self, conn_id: str) -> None:
        """断开连接"""
        # 关闭连接
        writer = self._client_to_server.pop(conn_id, None)
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        
        writer = self._server_to_client.pop(conn_id, None)
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        
        self._connection_states.pop(conn_id, None)
        
        # 通知
        for handler in self._disconnect_handlers:
            try:
                handler(conn_id)
            except Exception as e:
                logger.error(f"Disconnect handler error: {e}")
        
        logger.info(f"Client disconnected: {conn_id}")
