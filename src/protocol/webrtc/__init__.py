"""
WebRTC Protocol Implementation

作为FastLink的备用协议，提供高兼容性的P2P连接。
使用aiortc库实现ICE/STUN/TURN。
"""

from .webrtc_connector import WebRTCConnector
from .ice_client import ICEClient
from .signaling import WebRTCSignaling

__all__ = ['WebRTCConnector', 'ICEClient', 'WebRTCSignaling']
