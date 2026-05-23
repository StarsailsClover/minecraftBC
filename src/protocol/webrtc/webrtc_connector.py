"""
WebRTC Connector Implementation

实现基于WebRTC的P2P连接，作为FastLink的备用方案。
支持ICE/STUN/TURN，兼容性更好但延迟略高。
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional, Dict, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
    from aiortc.rtcconfiguration import RTCIceServer
    from aiortc.rtcdatachannel import RTCDataChannel
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    logging.warning("aiortc not installed. WebRTC support disabled.")

from ...connector.connector_base import ConnectorBase, ConnectionState, ConnectionStats, PeerInfo
from ...connector.protocol_type import ProtocolType

logger = logging.getLogger(__name__)


@dataclass
class WebRTCConfig:
    """WebRTC配置"""
    ice_servers: list[RTCIceServer] = None
    stun_servers: list[str] = None
    turn_servers: list[dict] = None
    
    def __post_init__(self):
        if self.ice_servers is None:
            self.ice_servers = []
        if self.stun_servers is None:
            # 默认使用Google的公共STUN服务器
            self.stun_servers = [
                "stun:stun.l.google.com:19302",
                "stun:stun1.l.google.com:19302",
            ]
        if self.turn_servers is None:
            self.turn_servers = []
        
        # 构建ICE服务器列表
        for stun in self.stun_servers:
            self.ice_servers.append(RTCIceServer(urls=[stun]))
        
        for turn in self.turn_servers:
            self.ice_servers.append(RTCIceServer(
                urls=[turn['url']],
                username=turn.get('username'),
                credential=turn.get('credential')
            ))


class WebRTCConnector(ConnectorBase):
    """
    WebRTC连接器实现
    
    使用aiortc库实现ICE连接，作为FastLink的备用方案。
    
    特点:
    - 依赖STUN/TURN服务器（可配置）
    - 使用DataChannel传输数据
    - 支持自动ICE候选收集
    - 连接建立时间约3-8秒
    
    使用示例:
    ```python
    config = WebRTCConfig(stun_servers=["stun:..."])
    webrtc = WebRTCConnector(node_id, local_addr, config)
    await webrtc.start()
    success = await webrtc.connect_to_peer(peer_id, addr)
    ```
    """
    
    def __init__(self, node_id: str, local_addr: Tuple[str, int],
                 config: Optional[WebRTCConfig] = None):
        super().__init__(node_id, local_addr)
        self.config = config or WebRTCConfig()
        
        # WebRTC连接映射
        self._peer_connections: Dict[str, RTCPeerConnection] = {}
        self._data_channels: Dict[str, RTCDataChannel] = {}
        
        # 信令回调（用于交换SDP）
        self._on_signaling: Optional[Callable[[str, str], None]] = None
        
        # 连接配置
        self._rtc_config = RTCConfiguration(
            iceServers=self.config.ice_servers
        )
    
    def on_signaling(self, callback: Callable[[str, str], None]) -> 'WebRTCConnector':
        """
        注册信令回调
        
        Args:
            callback: (peer_id, sdp_message) -> None
        """
        self._on_signaling = callback
        return self
    
    async def start(self) -> bool:
        """
        启动WebRTC连接器
        
        Returns:
            启动成功返回True
        """
        if not AIORTC_AVAILABLE:
            logger.error("aiortc not available. Install with: pip install aiortc")
            await self._set_state(ConnectionState.ERROR)
            return False
        
        logger.info("WebRTC connector started")
        await self._set_state(ConnectionState.CONNECTED)
        return True
    
    async def stop(self) -> None:
        """停止所有WebRTC连接"""
        await self._set_state(ConnectionState.DISCONNECTED)
        
        # 关闭所有连接
        for peer_id, pc in list(self._peer_connections.items()):
            try:
                await pc.close()
            except Exception as e:
                logger.error(f"Error closing peer connection for {peer_id}: {e}")
        
        self._peer_connections.clear()
        self._data_channels.clear()
    
    async def connect_to_peer(self, peer_id: str, addr: Tuple[str, int],
                               timeout: float = 30.0) -> bool:
        """
        连接到对等节点
        
        WebRTC连接流程:
        1. 创建PeerConnection
        2. 创建DataChannel
        3. 生成Offer SDP
        4. 通过信令发送Offer
        5. 等待Answer SDP
        6. ICE候选收集
        7. 连接建立
        
        Args:
            peer_id: 目标节点ID
            addr: 目标地址（用于信令，实际数据走P2P）
            timeout: 连接超时
        
        Returns:
            连接成功返回True
        """
        if not AIORTC_AVAILABLE:
            return False
        
        try:
            logger.info(f"Starting WebRTC connection to {peer_id}")
            
            # 创建PeerConnection
            pc = RTCPeerConnection(configuration=self._rtc_config)
            self._peer_connections[peer_id] = pc
            
            # 创建DataChannel
            channel = pc.createDataChannel('data', ordered=True)
            self._setup_data_channel(peer_id, channel)
            
            # 生成Offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # 收集ICE候选
            await self._gather_ice_candidates(pc, timeout=5.0)
            
            # 发送信令（通过回调）
            if self._on_signaling:
                signal_msg = {
                    'type': 'offer',
                    'sdp': pc.localDescription.sdp,
                    'node_id': self.node_id,
                    'target': peer_id
                }
                self._on_signaling(peer_id, json.dumps(signal_msg))
            
            # 等待连接建立
            success = await self._wait_for_connection(pc, timeout)
            
            if success:
                logger.info(f"WebRTC connection to {peer_id} established")
                self._peer_protocols[peer_id] = ProtocolType.WEBRTC
                self._notify_connect(peer_id)
                return True
            else:
                logger.error(f"WebRTC connection to {peer_id} failed")
                await pc.close()
                self._peer_connections.pop(peer_id, None)
                return False
                
        except Exception as e:
            logger.error(f"WebRTC connection error: {e}")
            return False
    
    def _setup_data_channel(self, peer_id: str, channel: RTCDataChannel) -> None:
        """设置DataChannel事件处理"""
        
        @channel.on('open')
        def on_open():
            logger.debug(f"DataChannel opened for {peer_id}")
        
        @channel.on('message')
        def on_message(message):
            if isinstance(message, str):
                data = message.encode()
            else:
                data = message
            self._notify_message(peer_id, data, 'webrtc')
        
        @channel.on('close')
        def on_close():
            logger.debug(f"DataChannel closed for {peer_id}")
            self._notify_disconnect(peer_id)
        
        @channel.on('error')
        def on_error(error):
            logger.error(f"DataChannel error for {peer_id}: {error}")
        
        self._data_channels[peer_id] = channel
    
    async def _gather_ice_candidates(self, pc: RTCPeerConnection, timeout: float = 5.0) -> None:
        """等待ICE候选收集完成"""
        # 简化的ICE收集
        await asyncio.sleep(0.5)  # 给ICE收集一点时间
    
    async def _wait_for_connection(self, pc: RTCPeerConnection, timeout: float) -> bool:
        """等待连接建立"""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if pc.connectionState == 'connected':
                return True
            if pc.connectionState == 'failed':
                return False
            await asyncio.sleep(0.1)
        
        return False
    
    async def handle_signaling_message(self, peer_id: str, message: str) -> None:
        """
        处理接收到的信令消息
        
        Args:
            peer_id: 发送方节点ID
            message: SDP消息JSON
        """
        if not AIORTC_AVAILABLE:
            return
        
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'offer':
                # 收到Offer，生成Answer
                await self._handle_offer(peer_id, data)
            elif msg_type == 'answer':
                # 收到Answer
                await self._handle_answer(peer_id, data)
            elif msg_type == 'ice-candidate':
                # 收到ICE候选
                await self._handle_ice_candidate(peer_id, data)
                
        except Exception as e:
            logger.error(f"Error handling signaling message: {e}")
    
    async def _handle_offer(self, peer_id: str, data: dict) -> None:
        """处理收到的Offer"""
        try:
            # 创建PeerConnection
            pc = RTCPeerConnection(configuration=self._rtc_config)
            self._peer_connections[peer_id] = pc
            
            # 监听DataChannel
            @pc.on('datachannel')
            def on_datachannel(channel):
                self._setup_data_channel(peer_id, channel)
            
            # 设置RemoteDescription
            offer = RTCSessionDescription(sdp=data['sdp'], type='offer')
            await pc.setRemoteDescription(offer)
            
            # 创建Answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            # 发送Answer
            if self._on_signaling:
                response = {
                    'type': 'answer',
                    'sdp': pc.localDescription.sdp,
                    'node_id': self.node_id,
                    'target': peer_id
                }
                self._on_signaling(peer_id, json.dumps(response))
            
        except Exception as e:
            logger.error(f"Error handling offer: {e}")
    
    async def _handle_answer(self, peer_id: str, data: dict) -> None:
        """处理收到的Answer"""
        pc = self._peer_connections.get(peer_id)
        if pc:
            try:
                answer = RTCSessionDescription(sdp=data['sdp'], type='answer')
                await pc.setRemoteDescription(answer)
            except Exception as e:
                logger.error(f"Error handling answer: {e}")
    
    async def _handle_ice_candidate(self, peer_id: str, data: dict) -> None:
        """处理ICE候选（简化处理）"""
        # aiortc自动处理ICE，这里可以扩展为手动添加候选
        pass
    
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """断开与指定节点的连接"""
        pc = self._peer_connections.pop(peer_id, None)
        channel = self._data_channels.pop(peer_id, None)
        
        if pc:
            try:
                await pc.close()
                return True
            except Exception as e:
                logger.error(f"Error disconnecting from {peer_id}: {e}")
        
        return False
    
    async def send_to_peer(self, peer_id: str, data: bytes) -> bool:
        """向指定节点发送数据"""
        channel = self._data_channels.get(peer_id)
        
        if channel and channel.readyState == 'open':
            try:
                # WebRTC DataChannel支持str或bytes
                if isinstance(data, bytes):
                    channel.send(data)
                else:
                    channel.send(data.decode())
                return True
            except Exception as e:
                logger.error(f"Error sending to {peer_id}: {e}")
        
        return False
    
    async def broadcast(self, data: bytes) -> int:
        """向所有连接的节点广播"""
        sent_count = 0
        
        for peer_id in list(self._data_channels.keys()):
            if await self.send_to_peer(peer_id, data):
                sent_count += 1
        
        return sent_count
    
    def get_peer_list(self) -> list[PeerInfo]:
        """获取已连接节点列表"""
        peers = []
        
        for peer_id, pc in self._peer_connections.items():
            if pc.connectionState == 'connected':
                peers.append(PeerInfo(
                    peer_id=peer_id,
                    address=('', 0),  # WebRTC隐藏真实地址
                    public_key=None,
                    metadata={'protocol': 'webrtc', 'ice_state': pc.iceConnectionState}
                ))
        
        return peers
    
    def is_connected_to(self, peer_id: str) -> bool:
        """检查是否与指定节点连接"""
        pc = self._peer_connections.get(peer_id)
        return pc is not None and pc.connectionState == 'connected'


# 辅助函数
def create_default_webrtc_connector(node_id: str, local_addr: Tuple[str, int]) -> Optional[WebRTCConnector]:
    """创建默认配置的WebRTC连接器"""
    if not AIORTC_AVAILABLE:
        logger.warning("aiortc not available")
        return None
    
    config = WebRTCConfig()
    return WebRTCConnector(node_id, local_addr, config)
