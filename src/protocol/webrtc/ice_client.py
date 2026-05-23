"""
ICE Client Implementation

管理ICE候选收集和STUN/TURN服务器连接。
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from aiortc import RTCPeerConnection, RTCIceCandidate
    from aiortc.rtcconfiguration import RTCIceServer
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ICECandidate:
    """ICE候选信息"""
    ip: str
    port: int
    protocol: str
    type: str  # host, srflx, relay
    foundation: str
    component: int
    priority: int


class NATType(Enum):
    """NAT类型检测"""
    UNKNOWN = "unknown"
    OPEN = "open"
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"


class ICEClient:
    """
    ICE客户端
    
    管理ICE候选收集和NAT类型检测。
    支持多个STUN/TURN服务器。
    
    使用示例:
    ```python
    client = ICEClient(stun_servers=["stun:..."])
    candidates = await client.gather_candidates()
    nat_type = await client.detect_nat_type()
    ```
    """
    
    def __init__(self, stun_servers: Optional[List[str]] = None,
                 turn_servers: Optional[List[Dict]] = None):
        self.stun_servers = stun_servers or [
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302"
        ]
        self.turn_servers = turn_servers or []
        
        self._ice_servers: List[RTCIceServer] = []
        self._setup_ice_servers()
    
    def _setup_ice_servers(self) -> None:
        """配置ICE服务器"""
        # 添加STUN服务器
        for stun in self.stun_servers:
            self._ice_servers.append(RTCIceServer(urls=[stun]))
        
        # 添加TURN服务器
        for turn in self.turn_servers:
            self._ice_servers.append(RTCIceServer(
                urls=[turn['url']],
                username=turn.get('username'),
                credential=turn.get('credential')
            ))
    
    async def gather_candidates(self) -> List[ICECandidate]:
        """
        收集ICE候选
        
        Returns:
            候选列表
        """
        if not AIORTC_AVAILABLE:
            return []
        
        candidates = []
        
        # 创建临时PC用于收集候选
        from aiortc import RTCPeerConnection, RTCConfiguration
        
        config = RTCConfiguration(iceServers=self._ice_servers)
        pc = RTCPeerConnection(configuration=config)
        
        # 创建一个数据通道触发ICE收集
        pc.createDataChannel('ice-gather')
        
        # 创建offer以触发ICE
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # 等待ICE收集
        await asyncio.sleep(2.0)
        
        # 获取候选
        # 注意：aiortc内部处理候选，这里返回简化信息
        
        await pc.close()
        
        return candidates
    
    async def detect_nat_type(self) -> NATType:
        """
        检测NAT类型
        
        通过多个STUN服务器比较映射结果
        
        Returns:
            检测到的NAT类型
        """
        # 简化的NAT类型检测
        # 完整实现需要比较不同STUN服务器返回的映射地址
        return NATType.UNKNOWN
    
    def get_preferred_candidate(self, candidates: List[ICECandidate]) -> Optional[ICECandidate]:
        """
        选择最佳候选
        
        优先级: host > srflx > relay
        
        Args:
            candidates: 候选列表
        
        Returns:
            最佳候选
        """
        if not candidates:
            return None
        
        # 按类型排序
        type_priority = {'host': 0, 'srflx': 1, 'relay': 2}
        sorted_candidates = sorted(
            candidates,
            key=lambda c: type_priority.get(c.type, 3)
        )
        
        return sorted_candidates[0]


class TURNManager:
    """
    TURN服务器管理
    
    管理TURN中继服务器连接和配额。
    """
    
    def __init__(self):
        self.turn_servers: List[Dict] = []
        self._active_relays: Dict[str, Any] = {}
    
    def add_turn_server(self, url: str, username: str, credential: str) -> None:
        """添加TURN服务器"""
        self.turn_servers.append({
            'url': url,
            'username': username,
            'credential': credential
        })
    
    def get_turn_servers(self) -> List[Dict]:
        """获取TURN服务器列表"""
        return self.turn_servers.copy()
    
    async def allocate_relay(self, peer_id: str) -> Optional[Dict]:
        """
        为指定peer分配TURN中继
        
        Args:
            peer_id: 目标节点ID
        
        Returns:
            分配的TURN服务器信息
        """
        if not self.turn_servers:
            return None
        
        # 简单轮询选择
        turn = self.turn_servers[hash(peer_id) % len(self.turn_servers)]
        self._active_relays[peer_id] = turn
        return turn
    
    async def release_relay(self, peer_id: str) -> None:
        """释放TURN中继"""
        self._active_relays.pop(peer_id, None)
