"""
Hybrid Connector - Dual Protocol P2P Connector

混合连接器 - 结合FastLink和WebRTC的优势
- 优先使用FastLink（如果可用）
- 回退到WebRTC
- 支持TCP代理隧道
"""

import asyncio
import socket
import logging
from typing import Optional, Dict, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

from protocol.fastlink.p2p import FastLinkP2P
from protocol.fastlink.server import FastLinkServer
from protocol.fastlink.config import FastLinkConfig
from protocol.fastlink.discovery import FastLinkDiscovery
from protocol.webbrtc.connection import WebRTCConnection

logger = logging.getLogger(__name__)


class ProtocolType(Enum):
    """协议类型"""
    NONE = "none"
    FASTLINK = "fastlink"
    WEBRTC = "webrtc"


@dataclass
class ConnectionInfo:
    """连接信息"""
    protocol: ProtocolType
    local_port: int
    remote_host: str
    remote_port: int
    established_at: float
    bytes_sent: int = 0
    bytes_received: int = 0


class HybridConnector:
    """
    混合P2P连接器
    
    管理多种P2P协议，提供统一的连接接口。
    同时支持TCP代理隧道（供模组使用）。
    """
    
    def __init__(
        self,
        config: Optional[FastLinkConfig] = None,
        prefer_protocol: ProtocolType = ProtocolType.FASTLINK,
        enable_webrtc_fallback: bool = True
    ):
        self.config = config or FastLinkConfig()
        self.prefer_protocol = prefer_protocol
        self.enable_webrtc_fallback = enable_webrtc_fallback
        
        # 协议实例
        self._fastlink: Optional[FastLinkP2P] = None
        self._webrtc: Optional[WebRTCConnection] = None
        self._discovery: Optional[FastLinkDiscovery] = None
        
        # 代理隧道管理
        self._proxy_tunnels: Dict[str, Tuple[int, asyncio.Task]] = {}  # server_id -> (local_port, task)
        self._next_proxy_port: int = 30000  # 代理端口起始
        
        # 回调
        self.on_connection_established: Optional[Callable[[str, ConnectionInfo], None]] = None
        self.on_connection_closed: Optional[Callable[[str], None]] = None
        self.on_data_received: Optional[Callable[[str, bytes], None]] = None
        
        self._running = False
        
    async def start(self):
        """启动连接器"""
        logger.info("Starting Hybrid Connector...")
        
        # 启动FastLink（优先）
        if self.prefer_protocol == ProtocolType.FASTLINK or self.enable_webrtc_fallback:
            try:
                self._fastlink = FastLinkP2P(self.config)
                await self._fastlink.start()
                logger.info("FastLink P2P started")
            except Exception as e:
                logger.warning(f"Failed to start FastLink: {e}")
                if not self.enable_webrtc_fallback:
                    raise
                    
        # 启动WebRTC（回退）
        if self.enable_webrtc_fallback and self._fastlink is None:
            try:
                self._webrtc = WebRTCConnection()
                await self._webrtc.start()
                logger.info("WebRTC started (fallback)")
            except Exception as e:
                logger.error(f"Failed to start WebRTC: {e}")
                
        # 启动节点发现
        if self._fastlink:
            self._discovery = FastLinkDiscovery(self._fastlink)
            await self._discovery.start()
            
        self._running = True
        logger.info("Hybrid Connector started")
        
    async def stop(self):
        """停止连接器"""
        logger.info("Stopping Hybrid Connector...")
        self._running = False
        
        # 关闭所有代理隧道
        for server_id, (port, task) in list(self._proxy_tunnels.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._proxy_tunnels.clear()
        
        # 停止协议
        if self._discovery:
            await self._discovery.stop()
            
        if self._fastlink:
            await self._fastlink.stop()
            
        if self._webrtc:
            await self._webrtc.stop()
            
        logger.info("Hybrid Connector stopped")
        
    async def connect(
        self,
        target_id: str,
        target_host: Optional[str] = None,
        target_port: int = 25565
    ) -> bool:
        """
        建立P2P连接
        
        Args:
            target_id: 目标节点ID
            target_host: 目标主机（可选，用于WebRTC）
            target_port: 目标端口
            
        Returns:
            是否连接成功
        """
        logger.info(f"Connecting to {target_id}...")
        
        # 优先使用FastLink
        if self._fastlink and await self._fastlink.can_connect(target_id):
            try:
                success = await self._fastlink.connect(target_id, target_port)
                if success:
                    logger.info(f"Connected to {target_id} via FastLink")
                    if self.on_connection_established:
                        info = ConnectionInfo(
                            protocol=ProtocolType.FASTLINK,
                            local_port=target_port,
                            remote_host=target_id,
                            remote_port=target_port,
                            established_at=asyncio.get_event_loop().time()
                        )
                        self.on_connection_established(target_id, info)
                    return True
            except Exception as e:
                logger.warning(f"FastLink connection failed: {e}")
                
        # 回退到WebRTC
        if self.enable_webrtc_fallback and self._webrtc:
            try:
                success = await self._webrtc.connect(target_id, target_host, target_port)
                if success:
                    logger.info(f"Connected to {target_id} via WebRTC")
                    if self.on_connection_established:
                        info = ConnectionInfo(
                            protocol=ProtocolType.WEBRTC,
                            local_port=target_port,
                            remote_host=target_host or target_id,
                            remote_port=target_port,
                            established_at=asyncio.get_event_loop().time()
                        )
                        self.on_connection_established(target_id, info)
                    return True
            except Exception as e:
                logger.error(f"WebRTC connection failed: {e}")
                
        logger.error(f"Failed to connect to {target_id}")
        return False
        
    async def create_proxy_tunnel(
        self,
        server_id: str,
        target_host: str,
        target_port: int
    ) -> int:
        """
        创建TCP代理隧道（供模组使用）
        
        返回本地代理端口，模组连接此端口即可访问远程服务器
        
        Args:
            server_id: P2P服务器ID
            target_host: 目标主机
            target_port: 目标端口
            
        Returns:
            本地代理端口号（失败返回0）
        """
        logger.info(f"Creating proxy tunnel to {server_id} ({target_host}:{target_port})")
        
        # 分配本地端口
        local_port = self._next_proxy_port
        self._next_proxy_port += 1
        
        # 先建立P2P连接
        if not await self.connect(server_id, target_host, target_port):
            return 0
            
        # 启动TCP代理服务器
        try:
            server = await asyncio.start_server(
                lambda r, w: self._handle_proxy_client(server_id, r, w),
                "127.0.0.1",
                local_port
            )
            
            # 保存隧道信息
            task = asyncio.create_task(self._run_proxy_server(server))
            self._proxy_tunnels[server_id] = (local_port, task)
            
            logger.info(f"Proxy tunnel created: 127.0.0.1:{local_port} -> {server_id}")
            return local_port
            
        except Exception as e:
            logger.error(f"Failed to create proxy tunnel: {e}")
            return 0
            
    async def _run_proxy_server(self, server: asyncio.Server):
        """运行代理服务器"""
        try:
            async with server:
                await server.serve_forever()
        except asyncio.CancelledError:
            logger.debug("Proxy server cancelled")
        finally:
            server.close()
            
    async def _handle_proxy_client(
        self,
        server_id: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """处理代理客户端连接"""
        logger.debug(f"Proxy client connected for {server_id}")
        
        # 获取P2P连接
        p2p_reader, p2p_writer = await self._get_p2p_connection(server_id)
        
        if not p2p_reader or not p2p_writer:
            logger.error(f"No P2P connection for {server_id}")
            writer.close()
            return
            
        # 双向转发
        async def forward_to_p2p():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    p2p_writer.write(data)
                    await p2p_writer.drain()
                    
                    # 更新统计
                    if server_id in self._proxy_tunnels:
                        # 可以在这里更新统计信息
                        pass
            except Exception as e:
                logger.debug(f"Forward to P2P error: {e}")
            finally:
                p2p_writer.close()
                
        async def forward_from_p2p():
            try:
                while True:
                    data = await p2p_reader.read(4096)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except Exception as e:
                logger.debug(f"Forward from P2P error: {e}")
            finally:
                writer.close()
                
        # 同时运行两个转发任务
        await asyncio.gather(
            forward_to_p2p(),
            forward_from_p2p(),
            return_exceptions=True
        )
        
        logger.debug(f"Proxy client disconnected for {server_id}")
        
    async def _get_p2p_connection(
        self,
        server_id: str
    ) -> Tuple[Optional[asyncio.StreamReader], Optional[asyncio.StreamWriter]]:
        """获取P2P连接"""
        # 从FastLink获取连接
        if self._fastlink:
            return await self._fastlink.get_connection(server_id)
            
        # 从WebRTC获取连接
        if self._webrtc:
            return await self._webrtc.get_connection(server_id)
            
        return None, None
        
    async def disconnect(self, target_id: str) -> bool:
        """断开连接"""
        logger.info(f"Disconnecting from {target_id}")
        
        # 关闭代理隧道
        if target_id in self._proxy_tunnels:
            _, task = self._proxy_tunnels[target_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._proxy_tunnels[target_id]
            
        # 断开协议连接
        success = False
        if self._fastlink:
            success = await self._fastlink.disconnect(target_id)
        if self._webrtc and not success:
            success = await self._webrtc.disconnect(target_id)
            
        if success and self.on_connection_closed:
            self.on_connection_closed(target_id)
            
        return success
        
    async def disconnect_all(self):
        """断开所有连接"""
        logger.info("Disconnecting all connections")
        
        # 关闭所有隧道
        for server_id in list(self._proxy_tunnels.keys()):
            await self.disconnect(server_id)
            
    async def send(self, target_id: str, data: bytes) -> bool:
        """发送数据"""
        if self._fastlink:
            return await self._fastlink.send(target_id, data)
        if self._webrtc:
            return await self._webrtc.send(target_id, data)
        return False
        
    def get_active_protocol(self, target_id: str) -> ProtocolType:
        """获取指定目标的活跃协议"""
        if self._fastlink and self._fastlink.is_connected(target_id):
            return ProtocolType.FASTLINK
        if self._webrtc and self._webrtc.is_connected(target_id):
            return ProtocolType.WEBRTC
        return ProtocolType.NONE
        
    def get_connection_stats(self, target_id: str) -> Optional[ConnectionInfo]:
        """获取连接统计"""
        # 从协议获取统计信息
        # 这里需要各协议提供统计接口
        return None
        
    def get_available_servers(self) -> list:
        """获取可用的P2P服务器列表"""
        servers = []
        
        # 从FastLink发现
        if self._discovery:
            for node in self._discovery.get_discovered_nodes():
                servers.append({
                    "id": node.node_id,
                    "name": node.display_name or node.node_id[:8],
                    "host": node.address[0] if node.address else "",
                    "port": node.address[1] if node.address else 0,
                    "latency": node.latency,
                    "protocol": "fastlink"
                })
                
        return servers
        
    def get_status(self) -> Dict:
        """获取连接器状态"""
        return {
            "running": self._running,
            "fastlink_available": self._fastlink is not None,
            "webrtc_available": self._webrtc is not None,
            "discovery_running": self._discovery is not None and self._discovery.is_running(),
            "active_tunnels": len(self._proxy_tunnels),
            "preferred_protocol": self.prefer_protocol.value
        }
