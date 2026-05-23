"""
WebRTC Signaling Server

提供信令服务用于交换SDP消息。
支持WebSocket和HTTP两种模式。
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional, Dict, Callable, Any, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SignalMessage:
    """信令消息"""
    msg_type: str  # offer, answer, ice-candidate
    sdp: Optional[str]
    node_id: str
    target_id: str
    timestamp: datetime
    ice_candidate: Optional[Dict] = None


class SignalingTransport(Enum):
    """信令传输方式"""
    WEBSOCKET = "websocket"
    HTTP = "http"


class WebRTCSignaling:
    """
    WebRTC信令服务器
    
    处理SDP offer/answer/ice-candidate的交换。
    支持点对点信令（通过现有连接）或中央信令服务器。
    
    使用示例:
    ```python
    signaling = WebRTCSignaling(node_id)
    signaling.on_message(lambda peer, msg: handle_msg(peer, msg))
    await signaling.start(host, port)
    await signaling.send_offer(target_id, sdp)
    ```
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        
        # 待发送的消息队列
        self._pending_messages: Dict[str, list] = {}
        
        # 消息处理器
        self._message_handlers: list[Callable[[str, dict], None]] = []
        self._connection_handlers: list[Callable[[str], None]] = []
        
        # 连接的节点
        self._connected_nodes: Set[str] = set()
        
        # 服务器实例
        self._server = None
        self._running = False
    
    def on_message(self, handler: Callable[[str, dict], None]) -> 'WebRTCSignaling':
        """
        注册消息处理器
        
        Args:
            handler: (peer_id, message_dict) -> None
        """
        self._message_handlers.append(handler)
        return self
    
    def on_connection(self, handler: Callable[[str], None]) -> 'WebRTCSignaling':
        """
        注册连接处理器
        
        Args:
            handler: (peer_id) -> None
        """
        self._connection_handlers.append(handler)
        return self
    
    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> bool:
        """
        启动信令服务器
        
        Args:
            host: 监听地址
            port: 监听端口
        
        Returns:
            启动成功返回True
        """
        try:
            logger.info(f"Starting signaling server on {host}:{port}")
            
            # 简化的TCP信令服务器
            self._server = await asyncio.start_server(
                self._handle_connection,
                host, port
            )
            
            self._running = True
            logger.info("Signaling server started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start signaling server: {e}")
            return False
    
    async def stop(self) -> None:
        """停止信令服务器"""
        self._running = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        logger.info("Signaling server stopped")
    
    async def _handle_connection(self, reader: asyncio.StreamReader,
                                  writer: asyncio.StreamWriter) -> None:
        """处理新连接"""
        addr = writer.get_extra_info('peername')
        logger.debug(f"New signaling connection from {addr}")
        
        try:
            while self._running:
                # 读取消息长度
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                length = int.from_bytes(length_data, 'big')
                
                # 读取消息
                data = await reader.read(length)
                if not data:
                    break
                
                message = json.loads(data.decode())
                await self._process_message(message, writer)
                
        except asyncio.CancelledError:
            raise  # Re-raise cancellation
        except Exception as e:
            logger.error(f"Signaling connection error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    
    async def _process_message(self, message: dict,
                                writer: asyncio.StreamWriter) -> None:
        """处理信令消息"""
        msg_type = message.get('type')
        node_id = message.get('node_id')
        target_id = message.get('target')
        
        if not node_id:
            return
        
        # 记录连接的节点
        self._connected_nodes.add(node_id)
        
        # 转发消息
        if target_id:
            await self._forward_message(target_id, message)
        
        # 通知处理器
        for handler in self._message_handlers:
            try:
                handler(node_id, message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    async def _forward_message(self, target_id: str, message: dict) -> bool:
        """
        转发消息到目标节点
        
        Args:
            target_id: 目标节点ID
            message: 消息内容
        
        Returns:
            转发成功返回True
        """
        # 简化实现：存储到待处理队列
        if target_id not in self._pending_messages:
            self._pending_messages[target_id] = []
        
        self._pending_messages[target_id].append({
            'message': message,
            'timestamp': datetime.now()
        })
        
        return True
    
    async def send_message(self, target_id: str, message: dict) -> bool:
        """
        发送信令消息
        
        Args:
            target_id: 目标节点ID
            message: 消息内容
        
        Returns:
            发送成功返回True
        """
        message['node_id'] = self.node_id
        message['target'] = target_id
        message['timestamp'] = datetime.now().isoformat()
        
        return await self._forward_message(target_id, message)
    
    async def send_offer(self, target_id: str, sdp: str) -> bool:
        """发送Offer SDP"""
        return await self.send_message(target_id, {
            'type': 'offer',
            'sdp': sdp
        })
    
    async def send_answer(self, target_id: str, sdp: str) -> bool:
        """发送Answer SDP"""
        return await self.send_message(target_id, {
            'type': 'answer',
            'sdp': sdp
        })
    
    async def send_ice_candidate(self, target_id: str,
                                  candidate: dict) -> bool:
        """发送ICE候选"""
        return await self.send_message(target_id, {
            'type': 'ice-candidate',
            'candidate': candidate
        })
    
    def get_pending_messages(self, target_id: str) -> list:
        """获取待发送给目标节点的消息"""
        return self._pending_messages.pop(target_id, [])


class P2PSignaling:
    """
    点对点信令（通过已有连接）
    
    使用已有的网络连接（如FastLink）作为信令通道
    """
    
    def __init__(self, connector):
        """
        初始化
        
        Args:
            connector: 现有的网络连接器
        """
        self.connector = connector
        self._handlers: list[Callable[[str, dict], None]] = []
        
        # 设置消息处理
        self.connector.on_message(self._on_message)
    
    def _on_message(self, peer_id: str, data: bytes, addr: str) -> None:
        """处理接收到的消息"""
        try:
            message = json.loads(data.decode())
            if message.get('protocol') == 'webrtc-signaling':
                for handler in self._handlers:
                    handler(peer_id, message)
        except Exception:
            pass
    
    def on_message(self, handler: Callable[[str, dict], None]):
        """注册消息处理器"""
        self._handlers.append(handler)
    
    async def send_message(self, target_id: str, message: dict) -> bool:
        """发送信令消息"""
        message['protocol'] = 'webrtc-signaling'
        data = json.dumps(message).encode()
        return await self.connector.send_to_peer(target_id, data)
