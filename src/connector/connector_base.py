"""
连接器抽象基类

定义统一接口，用于FastLink和WebRTC双协议
"""

from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any, Tuple
from datetime import datetime


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()


@dataclass
class ConnectionStats:
    """连接统计信息"""
    latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0
    connect_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None


@dataclass
class PeerInfo:
    """对等节点信息"""
    peer_id: str
    address: Tuple[str, int]
    public_key: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConnectorBase(ABC):
    """
    连接器抽象基类
    
    所有协议连接器(FastLink/WebRTC)必须实现此接口
    """
    
    def __init__(self, node_id: str, local_addr: Tuple[str, int]):
        self.node_id = node_id
        self.local_addr = local_addr
        self.state = ConnectionState.DISCONNECTED
        self.stats = ConnectionStats()
        self.peers: Dict[str, PeerInfo] = {}
        
        # 回调函数
        self._on_message: Optional[Callable[[str, bytes, str], None]] = None
        self._on_connect: Optional[Callable[[str], None]] = None
        self._on_disconnect: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str, Exception], None]] = None
        
        self._state_lock = asyncio.Lock()
    
    # ========== 回调注册 ==========
    
    def on_message(self, callback: Callable[[str, bytes, str], None]) -> 'ConnectorBase':
        """
        注册消息接收回调
        
        Args:
            callback: (peer_id, data, addr) -> None
        """
        self._on_message = callback
        return self
    
    def on_connect(self, callback: Callable[[str], None]) -> 'ConnectorBase':
        """
        注册连接建立回调
        
        Args:
            callback: (peer_id) -> None
        """
        self._on_connect = callback
        return self
    
    def on_disconnect(self, callback: Callable[[str], None]) -> 'ConnectorBase':
        """
        注册连接断开回调
        
        Args:
            callback: (peer_id) -> None
        """
        self._on_disconnect = callback
        return self
    
    def on_error(self, callback: Callable[[str, Exception], None]) -> 'ConnectorBase':
        """
        注册错误回调
        
        Args:
            callback: (peer_id, error) -> None
        """
        self._on_error = callback
        return self
    
    # ========== 抽象方法 ==========
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动连接器
        
        Returns:
            启动成功返回True
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止连接器"""
        pass
    
    @abstractmethod
    async def connect_to_peer(self, peer_id: str, addr: Tuple[str, int], 
                               timeout: float = 30.0) -> bool:
        """
        连接到指定对等节点
        
        Args:
            peer_id: 节点ID
            addr: 目标地址 (host, port)
            timeout: 连接超时(秒)
        
        Returns:
            连接成功返回True
        """
        pass
    
    @abstractmethod
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """
        断开与指定节点的连接
        
        Args:
            peer_id: 节点ID
        
        Returns:
            断开成功返回True
        """
        pass
    
    @abstractmethod
    async def send_to_peer(self, peer_id: str, data: bytes) -> bool:
        """
        向指定节点发送数据
        
        Args:
            peer_id: 目标节点ID
            data: 要发送的数据
        
        Returns:
            发送成功返回True
        """
        pass
    
    @abstractmethod
    async def broadcast(self, data: bytes) -> int:
        """
        向所有连接的节点广播数据
        
        Args:
            data: 要广播的数据
        
        Returns:
            成功发送的节点数量
        """
        pass
    
    @abstractmethod
    def get_peer_list(self) -> list[PeerInfo]:
        """获取所有已连接节点列表"""
        pass
    
    @abstractmethod
    def is_connected_to(self, peer_id: str) -> bool:
        """检查是否与指定节点已连接"""
        pass
    
    # ========== 状态管理 ==========
    
    async def _set_state(self, new_state: ConnectionState) -> None:
        """线程安全的状态更新"""
        async with self._state_lock:
            self.state = new_state
    
    def get_state(self) -> ConnectionState:
        """获取当前状态"""
        return self.state
    
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.state == ConnectionState.CONNECTED
    
    def get_stats(self) -> ConnectionStats:
        """获取连接统计"""
        return self.stats
    
    # ========== 受保护方法 ==========
    
    def _notify_message(self, peer_id: str, data: bytes, addr: str) -> None:
        """通知消息接收"""
        self.stats.bytes_received += len(data)
        self.stats.last_activity = datetime.now()
        if self._on_message:
            try:
                self._on_message(peer_id, data, addr)
            except Exception as e:
                if self._on_error:
                    self._on_error(peer_id, e)
    
    def _notify_connect(self, peer_id: str) -> None:
        """通知连接建立"""
        if self._on_connect:
            try:
                self._on_connect(peer_id)
            except Exception as e:
                if self._on_error:
                    self._on_error(peer_id, e)
    
    def _notify_disconnect(self, peer_id: str) -> None:
        """通知连接断开"""
        if self._on_disconnect:
            try:
                self._on_disconnect(peer_id)
            except Exception as e:
                if self._on_error:
                    self._on_error(peer_id, e)
    
    def _notify_error(self, peer_id: str, error: Exception) -> None:
        """通知错误发生"""
        if self._on_error:
            self._on_error(peer_id, error)
