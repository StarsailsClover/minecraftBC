"""
协议类型定义
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class ProtocolType(Enum):
    """
    支持的协议类型
    
    FASTLINK: 主要协议，低延迟P2P直连
    WEBRTC: 备用协议，高兼容性
    """
    FASTLINK = "fastlink"
    WEBRTC = "webrtc"


@dataclass
class ProtocolCapabilities:
    """协议能力描述"""
    protocol: ProtocolType
    
    # NAT穿透能力
    supports_nat_traversal: bool = False
    supports_birthday_punch: bool = False  # FastLink特有
    supports_ice: bool = False  # WebRTC特有
    
    # 传输能力
    supports_udp: bool = False
    supports_tcp: bool = False
    supports_reliable_udp: bool = False
    supports_datagram: bool = False
    
    # 安全能力
    supports_dtls: bool = False
    supports_srtp: bool = False  # WebRTC特有
    supports_forward_secrecy: bool = False
    
    # 性能指标
    typical_latency_ms: float = 0.0
    typical_throughput_mbps: float = 0.0
    
    # 可靠性
    fallback_compatible: bool = True  # 可作为其他协议的fallback


# 预定义协议能力
FASTLINK_CAPABILITIES = ProtocolCapabilities(
    protocol=ProtocolType.FASTLINK,
    supports_nat_traversal=True,
    supports_birthday_punch=True,  # 核心优势
    supports_ice=False,
    supports_udp=True,
    supports_tcp=True,
    supports_reliable_udp=True,
    supports_datagram=True,
    supports_dtls=True,
    supports_srtp=False,
    supports_forward_secrecy=True,
    typical_latency_ms=20.0,  # 低延迟
    typical_throughput_mbps=100.0,
    fallback_compatible=True
)

WEBRTC_CAPABILITIES = ProtocolCapabilities(
    protocol=ProtocolType.WEBRTC,
    supports_nat_traversal=True,
    supports_birthday_punch=False,
    supports_ice=True,  # WebRTC核心
    supports_udp=True,
    supports_tcp=False,
    supports_reliable_udp=False,  # 使用SCTP
    supports_datagram=True,
    supports_dtls=True,
    supports_srtp=True,
    supports_forward_secrecy=True,
    typical_latency_ms=50.0,  # 略高
    typical_throughput_mbps=50.0,
    fallback_compatible=True  # 可作为FastLink的fallback
)


def get_protocol_capabilities(protocol: ProtocolType) -> ProtocolCapabilities:
    """获取指定协议的能力描述"""
    if protocol == ProtocolType.FASTLINK:
        return FASTLINK_CAPABILITIES
    elif protocol == ProtocolType.WEBRTC:
        return WEBRTC_CAPABILITIES
    else:
        raise ValueError(f"Unknown protocol type: {protocol}")


class ProtocolSelector:
    """
    协议选择器
    
    根据网络环境和策略自动选择最优协议
    """
    
    def __init__(self, prefer_fastlink: bool = True):
        self.prefer_fastlink = prefer_fastlink
        self._fastlink_available = True
        self._webrtc_available = True
    
    def select_protocol(self, peer_info: Optional[dict] = None) -> ProtocolType:
        """
        选择最优协议
        
        策略:
        1. 如果FastLink可用且优先，选择FastLink
        2. FastLink不可用时，降级到WebRTC
        3. 如果peer明确要求特定协议，优先使用
        """
        # 检查peer偏好
        if peer_info and 'preferred_protocol' in peer_info:
            preferred = peer_info['preferred_protocol']
            if preferred == 'webrtc' and self._webrtc_available:
                return ProtocolType.WEBRTC
            elif preferred == 'fastlink' and self._fastlink_available:
                return ProtocolType.FASTLINK
        
        # 默认策略
        if self.prefer_fastlink and self._fastlink_available:
            return ProtocolType.FASTLINK
        elif self._webrtc_available:
            return ProtocolType.WEBRTC
        
        # 都无可用，抛出异常
        raise RuntimeError("No protocol available")
    
    def mark_protocol_failed(self, protocol: ProtocolType) -> None:
        """标记协议暂时不可用"""
        if protocol == ProtocolType.FASTLINK:
            self._fastlink_available = False
        elif protocol == ProtocolType.WEBRTC:
            self._webrtc_available = False
    
    def reset_protocol_status(self, protocol: ProtocolType) -> None:
        """重置协议状态为可用"""
        if protocol == ProtocolType.FASTLINK:
            self._fastlink_available = True
        elif protocol == ProtocolType.WEBRTC:
            self._webrtc_available = True
