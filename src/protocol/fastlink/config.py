"""
FastLink Configuration

Configuration for FastLink P2P protocol.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class FastLinkConfig:
    """FastLink configuration"""
    
    # Network settings
    listen_port: int = 0
    preferred_protocol: str = "fastlink"
    enable_webrtc_fallback: bool = True
    
    # Node settings
    node_name: str = "FastLinkNode"
    node_id: Optional[str] = None
    
    # Security
    enable_encryption: bool = True
    identity_key_path: Optional[str] = None
    
    # STUN servers
    stun_servers: List[str] = None
    
    def __post_init__(self):
        if self.stun_servers is None:
            self.stun_servers = [
                "stun.l.google.com:19302",
                "stun1.l.google.com:19302"
            ]
