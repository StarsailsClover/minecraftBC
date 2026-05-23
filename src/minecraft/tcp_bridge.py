"""
TCP Bridge for Minecraft Connection

实现Minecraft客户端到P2P主机的TCP连接转发。
这是LAN注入器的核心功能，允许玩家通过P2P网络连接到远程世界。

工作原理:
1. 在本地监听Minecraft连接端口
2. 将TCP数据封装到P2P消息
3. 通过HybridConnector发送到远程主机
4. 远程主机解封装并转发到本地Minecraft服务器
5. 双向数据流

架构:
```
[MC Client] <--TCP--> [TCP Bridge] <--P2P--> [P2P Network] <--P2P--> [TCP Bridge] <--TCP--> [MC Server]
```
"""

from __future__ import annotations
import asyncio
import struct
import logging
from typing import Optional, Dict, Callable, Tuple, BinaryIO
from dataclasses import dataclass
from enum import IntEnum
from io import BytesIO

logger = logging.getLogger(__name__)


class BridgeState(IntEnum):
    """TCP桥接状态"""
    CLOSED = 0
    LISTENING = 1
    CONNECTING = 2
    CONNECTED = 3
    CLOSING = 4


@dataclass
class TCPPacket:
    """
    TCP数据包封装
    
    用于在P2P网络上传输TCP数据。
    """
    connection_id: str
    sequence: int
    data: bytes
    flags: int = 0  # SYN, ACK, FIN等
    
    # 包标志
    FLAG_DATA = 0x01
    FLAG_SYN = 0x02
    FLAG_ACK = 0x04
    FLAG_FIN = 0x08
    FLAG_RST = 0x10
    
    def encode(self) -> bytes:
        """编码为字节"""
        # 格式: [conn_id_len:1][conn_id][seq:4][flags:1][data_len:4][data]
        conn_bytes = self.connection_id.encode()
        header = struct.pack('>B', len(conn_bytes))
        header += conn_bytes
        header += struct.pack('>IBI', self.sequence, self.flags, len(self.data))
        return header + self.data
    
    @classmethod
    def decode(cls, data: bytes) -> 'TCPPacket':
        """从字节解码"""
        offset = 0
        conn_len = data[offset]
        offset += 1
        
        conn_id = data[offset:offset + conn_len].decode()
        offset += conn_len
        
        seq, flags, data_len = struct.unpack('>IBI', data[offset:offset + 9])
        offset += 9
        
        payload = data[offset:offset + data_len]
        
        return cls(
            connection_id=conn_id,
            sequence=seq,
            data=payload,
            flags=flags
        )


class TCPConnection:
    """
    TCP连接管理
    
    管理单个TCP连接的状态和序列号。
    """
    
    def __init__(self, connection_id: str, local_addr: Tuple[str, int],
                 remote_peer: str, remote_mc_port: int):
        self.connection_id = connection_id
        self.local_addr = local_addr
        self.remote_peer = remote_peer
        self.remote_mc_port = remote_mc_port
        
        self.state = BridgeState.CLOSED
        self.send_sequence = 0
        self.recv_sequence = 0
        
        # 数据缓冲区
        self._send_buffer = bytearray()
        self._recv_buffer = bytearray()
        
        # 统计
        self.bytes_sent = 0
        self.bytes_received = 0
        self.connect_time = None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.state == BridgeState.CONNECTED


class TCPBridge:
    """
    TCP桥接器
    
    在P2P网络上桥接TCP连接。
    用于Minecraft客户端连接到远程P2P主机。
    
    使用示例:
    ```python
    bridge = TCPBridge(connector)
    await bridge.start(local_port=25566)
    
    # 连接到远程世界
    await bridge.connect_to_world(peer_id, remote_mc_port=25565)
    ```
    """
    
    def __init__(self, connector):
        """
        初始化TCP桥接器
        
        Args:
            connector: HybridConnector实例
        """
        self.connector = connector
        self.local_port: Optional[int] = None
        
        # 连接管理
        self._connections: Dict[str, TCPConnection] = {}
        self._client_transports: Dict[str, asyncio.Transport] = {}
        
        # 服务器
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False
        
        # 回调
        self._on_connection: Optional[Callable[[str], None]] = None
        self._on_disconnection: Optional[Callable[[str], None]] = None
        self._on_data: Optional[Callable[[str, bytes], None]] = None
        
        # 设置P2P消息处理
        self.connector.on_message(self._on_p2p_message)
    
    def on_connection(self, callback: Callable[[str], None]) -> 'TCPBridge':
        """注册连接回调"""
        self._on_connection = callback
        return self
    
    def on_disconnection(self, callback: Callable[[str], None]) -> 'TCPBridge':
        """注册断开回调"""
        self._on_disconnection = callback
        return self
    
    def on_data(self, callback: Callable[[str, bytes], None]) -> 'TCPBridge':
        """注册数据回调"""
        self._on_data = callback
        return self
    
    async def start(self, local_port: int = 25566) -> bool:
        """
        启动TCP桥接器
        
        Args:
            local_port: 本地监听端口（Minecraft客户端连接到此端口）
        
        Returns:
            启动成功返回True
        """
        try:
            self.local_port = local_port
            
            logger.info(f"Starting TCP bridge on port {local_port}")
            
            # 创建TCP服务器
            self._server = await asyncio.start_server(
                self._handle_client_connection,
                '127.0.0.1',  # 仅本地监听
                local_port
            )
            
            self._running = True
            
            logger.info(f"TCP bridge listening on 127.0.0.1:{local_port}")
            logger.info(f"Players should connect to localhost:{local_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start TCP bridge: {e}")
            return False
    
    async def stop(self) -> None:
        """停止TCP桥接器"""
        self._running = False
        
        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # 关闭所有连接
        for conn_id in list(self._connections.keys()):
            await self._close_connection(conn_id)
        
        logger.info("TCP bridge stopped")
    
    async def _handle_client_connection(self,
                                         reader: asyncio.StreamReader,
                                         writer: asyncio.StreamWriter) -> None:
        """
        处理Minecraft客户端连接
        
        当Minecraft客户端连接到本地端口时调用。
        """
        addr = writer.get_extra_info('peername')
        conn_id = f"{addr[0]}:{addr[1]}"
        
        logger.info(f"Minecraft client connected: {conn_id}")
        
        try:
            # 等待P2P连接建立
            # 实际应用中，应该在此之前已经建立了P2P连接
            # 这里简化处理
            
            # 读取Minecraft握手包
            handshake_data = await self._read_minecraft_handshake(reader)
            if handshake_data:
                logger.debug(f"Received Minecraft handshake: {len(handshake_data)} bytes")
            
            # 转发数据
            while self._running:
                data = await reader.read(4096)
                if not data:
                    break
                
                # 转发到P2P
                await self._forward_to_p2p(conn_id, data)
                
                # 统计数据
                if conn_id in self._connections:
                    self._connections[conn_id].bytes_received += len(data)
            
        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            logger.info(f"Client {conn_id} connection reset")
        except Exception as e:
            logger.error(f"Client handler error for {conn_id}: {e}")
        finally:
            await self._close_connection(conn_id)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    
    async def _read_minecraft_handshake(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        """
        读取Minecraft握手包
        
        格式: [Length: varint] [Packet ID: varint] [Data]
        """
        try:
            # 读取长度（第一个字节）
            length_data = await reader.read(1)
            if not length_data:
                return None
            
            length = length_data[0]
            
            # 读取剩余数据
            remaining = await reader.read(length)
            return length_data + remaining
            
        except Exception as e:
            logger.debug(f"Failed to read handshake: {e}")
            return None
    
    async def _forward_to_p2p(self, conn_id: str, data: bytes) -> bool:
        """
        转发数据到P2P网络
        
        Args:
            conn_id: 连接ID
            data: 要转发的数据
        
        Returns:
            转发成功返回True
        """
        # 查找连接
        conn = self._connections.get(conn_id)
        if not conn:
            logger.warning(f"No P2P connection for {conn_id}")
            return False
        
        try:
            # 创建TCP数据包
            packet = TCPPacket(
                connection_id=conn_id,
                sequence=conn.send_sequence,
                data=data,
                flags=TCPPacket.FLAG_DATA
            )
            
            # 发送到P2P
            message = {
                'protocol': 'minecraft-tcp',
                'type': 'tcp_data',
                'packet': packet.encode().hex()
            }
            
            import json
            success = await self.connector.send_to_peer(
                conn.remote_peer,
                json.dumps(message).encode()
            )
            
            if success:
                conn.send_sequence += 1
                conn.bytes_sent += len(data)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to forward to P2P: {e}")
            return False
    
    def _on_p2p_message(self, peer_id: str, data: bytes, addr: str) -> None:
        """
        处理P2P消息
        
        接收来自远程主机的TCP数据。
        """
        try:
            import json
            message = json.loads(data.decode())
            
            if message.get('protocol') != 'minecraft-tcp':
                return
            
            msg_type = message.get('type')
            
            if msg_type == 'tcp_data':
                # 收到TCP数据
                packet_data = bytes.fromhex(message['packet'])
                packet = TCPPacket.decode(packet_data)
                
                # 转发到本地客户端
                asyncio.create_task(
                    self._forward_to_client(packet.connection_id, packet.data)
                )
                
            elif msg_type == 'tcp_syn':
                # 连接建立确认
                conn_id = message.get('connection_id')
                logger.info(f"P2P connection established: {conn_id}")
                
            elif msg_type == 'tcp_fin':
                # 连接关闭
                conn_id = message.get('connection_id')
                asyncio.create_task(self._close_connection(conn_id))
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling P2P message: {e}")
    
    async def _forward_to_client(self, conn_id: str, data: bytes) -> bool:
        """
        转发数据到本地Minecraft客户端
        
        Args:
            conn_id: 连接ID
            data: 要转发的数据
        
        Returns:
            转发成功返回True
        """
        transport = self._client_transports.get(conn_id)
        if not transport:
            logger.warning(f"No client transport for {conn_id}")
            return False
        
        try:
            transport.write(data)
            
            # 更新统计
            if conn_id in self._connections:
                self._connections[conn_id].bytes_received += len(data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to forward to client: {e}")
            return False
    
    async def connect_to_world(self, peer_id: str, remote_mc_port: int) -> bool:
        """
        连接到远程Minecraft世界
        
        Args:
            peer_id: 主机节点ID
            remote_mc_port: 远程Minecraft端口
        
        Returns:
            连接成功返回True
        """
        logger.info(f"Connecting to world at {peer_id}:{remote_mc_port}")
        
        # 确保P2P连接已建立
        if not self.connector.is_connected_to(peer_id):
            success = await self.connector.connect_to_peer(
                peer_id,
                ('0.0.0.0', 0),  # 地址信息不重要，P2P会处理
                timeout=30.0
            )
            if not success:
                logger.error(f"Failed to establish P2P connection to {peer_id}")
                return False
        
        # 创建连接记录
        conn_id = f"{peer_id}_{remote_mc_port}"
        conn = TCPConnection(
            connection_id=conn_id,
            local_addr=('127.0.0.1', self.local_port),
            remote_peer=peer_id,
            remote_mc_port=remote_mc_port
        )
        conn.state = BridgeState.CONNECTED
        self._connections[conn_id] = conn
        
        # 发送SYN包
        syn_message = {
            'protocol': 'minecraft-tcp',
            'type': 'tcp_syn',
            'connection_id': conn_id,
            'target_port': remote_mc_port
        }
        
        import json
        success = await self.connector.send_to_peer(
            peer_id,
            json.dumps(syn_message).encode()
        )
        
        if success:
            logger.info(f"TCP bridge connected to {peer_id}:{remote_mc_port}")
            logger.info(f"Players can now connect to localhost:{self.local_port}")
        
        return success
    
    async def _close_connection(self, conn_id: str) -> None:
        """关闭连接"""
        conn = self._connections.pop(conn_id, None)
        if conn:
            conn.state = BridgeState.CLOSED
            logger.info(f"Connection {conn_id} closed")
        
        transport = self._client_transports.pop(conn_id, None)
        if transport:
            transport.close()
    
    def get_connection_stats(self, conn_id: str) -> Optional[Dict]:
        """获取连接统计"""
        conn = self._connections.get(conn_id)
        if not conn:
            return None
        
        return {
            'connection_id': conn_id,
            'state': conn.state.name,
            'bytes_sent': conn.bytes_sent,
            'bytes_received': conn.bytes_received,
            'remote_peer': conn.remote_peer,
            'remote_port': conn.remote_mc_port
        }


class TCPBridgeServer:
    """
    TCP桥接服务器
    
    在P2P主机端运行，接收来自P2P的TCP数据并转发到本地Minecraft服务器。
    """
    
    def __init__(self, connector, local_mc_port: int = 25565):
        self.connector = connector
        self.local_mc_port = local_mc_port
        
        # 连接到本地Minecraft服务器的连接
        self._mc_connections: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        
        # 设置P2P消息处理
        self.connector.on_message(self._on_p2p_message)
    
    async def _on_p2p_message(self, peer_id: str, data: bytes, addr: str) -> None:
        """处理P2P消息"""
        try:
            import json
            message = json.loads(data.decode())
            
            if message.get('protocol') != 'minecraft-tcp':
                return
            
            msg_type = message.get('type')
            
            if msg_type == 'tcp_syn':
                # 客户端请求建立连接
                conn_id = message.get('connection_id')
                await self._handle_new_connection(peer_id, conn_id)
                
            elif msg_type == 'tcp_data':
                # 收到数据
                conn_id = message.get('connection_id')
                packet_data = bytes.fromhex(message['packet'])
                packet = TCPPacket.decode(packet_data)
                await self._forward_to_mc(conn_id, packet.data)
                
        except Exception as e:
            logger.error(f"Error in bridge server: {e}")
    
    async def _handle_new_connection(self, peer_id: str, conn_id: str) -> None:
        """处理新连接请求"""
        try:
            # 连接到本地Minecraft服务器
            reader, writer = await asyncio.open_connection(
                '127.0.0.1',
                self.local_mc_port
            )
            
            self._mc_connections[conn_id] = (reader, writer)
            
            logger.info(f"Bridge server: Connected to local MC server for {conn_id}")
            
            # 发送ACK
            ack_message = {
                'protocol': 'minecraft-tcp',
                'type': 'tcp_syn_ack',
                'connection_id': conn_id
            }
            
            import json
            await self.connector.send_to_peer(
                peer_id,
                json.dumps(ack_message).encode()
            )
            
            # 启动数据转发
            asyncio.create_task(self._forward_from_mc(peer_id, conn_id, reader))
            
        except Exception as e:
            logger.error(f"Failed to connect to MC server: {e}")
    
    async def _forward_from_mc(self, peer_id: str, conn_id: str,
                                reader: asyncio.StreamReader) -> None:
        """从Minecraft服务器转发数据到P2P"""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                
                # 封装并发送
                packet = TCPPacket(
                    connection_id=conn_id,
                    sequence=0,
                    data=data,
                    flags=TCPPacket.FLAG_DATA
                )
                
                message = {
                    'protocol': 'minecraft-tcp',
                    'type': 'tcp_data',
                    'packet': packet.encode().hex()
                }
                
                import json
                await self.connector.send_to_peer(
                    peer_id,
                    json.dumps(message).encode()
                )
                
        except Exception as e:
            logger.error(f"Error forwarding from MC: {e}")
    
    async def _forward_to_mc(self, conn_id: str, data: bytes) -> None:
        """转发数据到Minecraft服务器"""
        connection = self._mc_connections.get(conn_id)
        if not connection:
            logger.warning(f"No MC connection for {conn_id}")
            return
        
        _, writer = connection
        try:
            writer.write(data)
            await writer.drain()
        except Exception as e:
            logger.error(f"Error forwarding to MC: {e}")
