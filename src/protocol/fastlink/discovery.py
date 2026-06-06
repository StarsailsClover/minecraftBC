"""
FastLink Discovery

Node discovery for FastLink P2P network.
"""

import asyncio
import socket
from typing import Optional, List, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredNode:
    """Discovered node information"""
    node_id: str
    name: str
    address: Optional[tuple]
    latency: int = -1


class FastLinkDiscovery:
    """
    FastLink node discovery
    
    Discovers peers in P2P network.
    """
    
    def __init__(self, p2p_connection):
        self.p2p = p2p_connection
        self.running = False
        self.discovered: List[DiscoveredNode] = []
        
    async def start(self):
        """Start discovery"""
        self.running = True
        logger.info("FastLink discovery started")
        
    async def stop(self):
        """Stop discovery"""
        self.running = False
        logger.info("FastLink discovery stopped")
        
    def get_discovered_nodes(self) -> List[DiscoveredNode]:
        """Get list of discovered nodes"""
        return self.discovered
        
    def is_running(self) -> bool:
        """Check if discovery is running"""
        return self.running
