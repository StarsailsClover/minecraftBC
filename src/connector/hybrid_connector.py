"""
混合连接器 - 双协议自动选择

实现FastLink + WebRTC双协议支持
自动协议降级和恢复
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from .connector_base import ConnectorBase, ConnectionState, ConnectionStats, PeerInfo
from .protocol_type import ProtocolType, ProtocolSelector, get_protocol_capabilities
from ..protocol.fastlink.p2p import P2PConnection

logger = logging.getLogger(__name__)


class HybridConnector(ConnectorBase):
    """
    双协议混合连接器
    
    特性:
    - 优先使用FastLink（低延迟）
    - FastLink失败时自动降级到WebRTC
    - 协议切换对上层透明
    - 运行时性能监控
    
    使用示例:
    ```python
    connector = HybridConnector(node_id, local_addr)
    connector.on_message(on_msg).on_connect(on_conn)
    await connector.start()
    
    # 自动选择协议
    success = await connector.connect_to_peer(peer_id, addr)
    ```
    """
    
    def __init__(self, node_id: str, local_addr: Tuple[str, int],
                 prefer_fastlink: bool = True,
                 fallback_timeout: float = 10.0):
        """
        初始化混合连接器
        
        Args:
            node_id: 本节点唯一标识
            local_addr: 本地监听地址
            prefer_fastlink: 是否优先使用FastLink
            fallback_timeout: 协议降级超时时间(秒)
        """
        super().__init__(node_id, local_addr)
        self.protocol_selector = ProtocolSelector(prefer_fastlink)
        self.fallback_timeout = fallback_timeout
        
        # 子连接器
        self._fastlink_connector: Optional[P2PConnection] = None
        self._webrtc_connector: Optional[Any] = None  # WebRTC预留
        
        # 每个peer使用的协议
        self._peer_protocols: Dict[str, ProtocolType] = {}
        
        # 协议特定统计
        self._protocol_stats: Dict[ProtocolType, ConnectionStats] = {
            ProtocolType.FASTLINK: ConnectionStats(),
            ProtocolType.WEBRTC: ConnectionStats()
        }
    
    async def start(self) -> bool:
        """
        启动混合连接器
        
        初始化所有子协议
        """
        logger.info("Starting HybridConnector...")
        
        # 启动FastLink
        try:
            from ..protocol.fastlink.p2p import P2PConnection, NodeInfo
            from ..protocol.fastlink.packet import generate_node_id
            
            node_info = NodeInfo(
                node_id=self.node_id,
                addresses=[f"{self.local_addr[0]}:{self.local_addr[1]}"],
                public_key="",  # 待实现: 生成Ed25519密钥
                capabilities=["p2p", "fastlink"]
            )
            
            self._fastlink_connector = P2PConnection(
                self.node_id, 
                self.local_addr,
                node_info
            )
            
            # 转发回调
            self._setup_fastlink_callbacks()
            
            fastlink_ok = await self._fastlink_connector.start()
            if not fastlink_ok:
                logger.warning("FastLink failed to start, will rely on WebRTC fallback")
                self.protocol_selector.mark_protocol_failed(ProtocolType.FASTLINK)
            else:
                logger.info("FastLink started successfully")
                
        except Exception as e:
            logger.error(f"Failed to start FastLink: {e}")
            self.protocol_selector.mark_protocol_failed(ProtocolType.FASTLINK)
        
        # WebRTC预留初始化
        # TODO: 实现WebRTC连接器
        self.protocol_selector.mark_protocol_failed(ProtocolType.WEBRTC)
        
        await self._set_state(ConnectionState.CONNECTED if self._is_any_protocol_available() else ConnectionState.ERROR)
        return self.state != ConnectionState.ERROR
    
    def _setup_fastlink_callbacks(self) -> None:
        """设置FastLink回调转发"""
        if not self._fastlink_connector:
            return
        
        def on_fastlink_msg(peer_id: str, data: bytes, addr: str):
            self._peer_protocols[peer_id] = ProtocolType.FASTLINK
            self._notify_message(peer_id, data, addr)
        
        def on_fastlink_connect(peer_id: str):
            if peer_id not in self._peer_protocols:
                self._peer_protocols[peer_id] = ProtocolType.FASTLINK
            self._notify_connect(peer_id)
        
        def on_fastlink_disconnect(peer_id: str):
            self._peer_protocols.pop(peer_id, None)
            self._notify_disconnect(peer_id)
        
        self._fastlink_connector.on_message(on_fastlink_msg)
        self._fastlink_connector.on_connect(on_fastlink_connect)
        self._fastlink_connector.on_disconnect(on_fastlink_disconnect)
    
    def _is_any_protocol_available(self) -> bool:
        """检查是否有可用协议"""
        return (self.protocol_selector._fastlink_available or 
                self.protocol_selector._webrtc_available)
    
    async def stop(self) -> None:
        """停止所有协议"""
        await self._set_state(ConnectionState.DISCONNECTED)
        
        if self._fastlink_connector:
            try:
                await self._fastlink_connector.stop()
            except Exception as e:
                logger.error(f"Error stopping FastLink: {e}")
        
        # TODO: 停止WebRTC
        
        self._peer_protocols.clear()
    
    async def connect_to_peer(self, peer_id: str, addr: Tuple[str, int],
                               timeout: float = 30.0) -> bool:
        """
        连接到对等节点
        
        自动选择协议，优先FastLink，失败降级到WebRTC
        """
        protocol = self.protocol_selector.select_protocol()
        
        # 先尝试主协议
        if protocol == ProtocolType.FASTLINK and self._fastlink_connector:
            try:
                logger.info(f"Trying FastLink connection to {peer_id}")
                
                # 使用超时包装
                success = await asyncio.wait_for(
                    self._try_fastlink_connect(peer_id, addr),
                    timeout=self.fallback_timeout
                )
                
                if success:
                    self._peer_protocols[peer_id] = ProtocolType.FASTLINK
                    logger.info(f"FastLink connection to {peer_id} succeeded")
                    return True
                    
            except asyncio.TimeoutError:
                logger.warning(f"FastLink connection to {peer_id} timed out")
            except Exception as e:
                logger.error(f"FastLink connection to {peer_id} failed: {e}")
        
        # FastLink失败，降级到WebRTC
        logger.info(f"Falling back to WebRTC for {peer_id}")
        return await self._connect_webrtc(peer_id, addr, timeout)
    
    async def _try_fastlink_connect(self, peer_id: str, addr: Tuple[str, int]) -> bool:
        """尝试FastLink连接"""
        # 创建hole punching任务
        # 这里需要实现实际的NAT穿透逻辑
        # 当前使用简化实现
        return await self._fastlink_connector.connect_to_peer(peer_id, addr)
    
    async def _connect_webrtc(self, peer_id: str, addr: Tuple[str, int],
                               timeout: float) -> bool:
        """
        WebRTC连接实现
        
        TODO: 实现WebRTC连接逻辑
        """
        logger.warning("WebRTC not yet implemented, connection will fail")
        return False
    
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """断开指定节点的连接"""
        protocol = self._peer_protocols.get(peer_id)
        
        if protocol == ProtocolType.FASTLINK and self._fastlink_connector:
            return await self._fastlink_connector.disconnect_from_peer(peer_id)
        elif protocol == ProtocolType.WEBRTC:
            # TODO: WebRTC断开
            pass
        
        self._peer_protocols.pop(peer_id, None)
        return True
    
    async def send_to_peer(self, peer_id: str, data: bytes) -> bool:
        """向指定节点发送数据"""
        protocol = self._peer_protocols.get(peer_id)
        
        if protocol == ProtocolType.FASTLINK and self._fastlink_connector:
            return await self._fastlink_connector.send_to_peer(peer_id, data)
        elif protocol == ProtocolType.WEBRTC:
            # TODO: WebRTC发送
            pass
        
        return False
    
    async def broadcast(self, data: bytes) -> int:
        """向所有节点广播"""
        sent_count = 0
        
        # FastLink广播
        if self._fastlink_connector:
            try:
                # 获取FastLink连接的peers
                fastlink_peers = [
                    pid for pid, proto in self._peer_protocols.items()
                    if proto == ProtocolType.FASTLINK
                ]
                for peer_id in fastlink_peers:
                    if await self.send_to_peer(peer_id, data):
                        sent_count += 1
            except Exception as e:
                logger.error(f"FastLink broadcast error: {e}")
        
        # TODO: WebRTC广播
        
        return sent_count
    
    def get_peer_list(self) -> list[PeerInfo]:
        """获取已连接节点列表"""
        peers = []
        
        if self._fastlink_connector:
            # 从FastLink获取
            fastlink_peers = self._fastlink_connector.get_peer_list()
            for peer_id in fastlink_peers:
                if peer_id in self._peer_protocols:
                    peers.append(PeerInfo(
                        peer_id=peer_id,
                        address=("", 0),  # 待填充
                        public_key=None,
                        metadata={'protocol': 'fastlink'}
                    ))
        
        return peers
    
    def is_connected_to(self, peer_id: str) -> bool:
        """检查是否与指定节点连接"""
        if peer_id not in self._peer_protocols:
            return False
        
        protocol = self._peer_protocols[peer_id]
        
        if protocol == ProtocolType.FASTLINK and self._fastlink_connector:
            return self._fastlink_connector.is_connected_to(peer_id)
        elif protocol == ProtocolType.WEBRTC:
            # TODO: WebRTC检查
            return False
        
        return False
    
    def get_peer_protocol(self, peer_id: str) -> Optional[ProtocolType]:
        """获取指定节点使用的协议"""
        return self._peer_protocols.get(peer_id)
    
    def get_protocol_stats(self, protocol: ProtocolType) -> ConnectionStats:
        """获取指定协议的统计信息"""
        return self._protocol_stats.get(protocol, ConnectionStats())
