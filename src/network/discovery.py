"""
Node Discovery Module
节点发现模块

Supports multiple discovery methods:
- mDNS (Multicast DNS) for LAN discovery
- Signaling server for WAN discovery
- Direct IP exchange
"""

from __future__ import annotations
import asyncio
import socket
import struct
import json
import time
import hashlib
from typing import Optional, Dict, List, Callable, Any, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredNode:
    """Discovered node information"""
    node_id: str
    name: str
    addresses: List[tuple]  # List of (ip, port) tuples
    capabilities: List[str]
    last_seen: float = field(default_factory=time.time)
    ttl: int = 300  # Time to live in seconds
    
    def is_valid(self) -> bool:
        """Check if discovery entry is still valid"""
        return time.time() - self.last_seen < self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'name': self.name,
            'addresses': self.addresses,
            'capabilities': self.capabilities,
            'last_seen': self.last_seen
        }


class MDNSDiscovery:
    """
    mDNS (Multicast DNS) discovery for LAN
    
    Uses multicast to discover peers on the same network.
    """
    
    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353
    
    SERVICE_TYPE = "_minecraftBC._tcp.local"
    
    def __init__(self, node_id: str, node_name: str, 
                 service_port: int, capabilities: List[str] = None):
        self.node_id = node_id
        self.node_name = node_name
        self.service_port = service_port
        self.capabilities = capabilities or ["p2p"]
        
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.discovered: Dict[str, DiscoveredNode] = {}
        self.callbacks: List[Callable[[DiscoveredNode], None]] = []
        
        self.announce_interval = 30.0
        self.cleanup_interval = 60.0
    
    async def start(self) -> bool:
        """Start mDNS discovery"""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Join multicast group
            mreq = struct.pack("4sl", 
                socket.inet_aton(self.MDNS_ADDR), 
                socket.INADDR_ANY)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            self.socket.bind(("", self.MDNS_PORT))
            self.socket.setblocking(False)
            
            self.running = True
            
            # Start tasks
            asyncio.create_task(self._announce_loop())
            asyncio.create_task(self._receive_loop())
            asyncio.create_task(self._cleanup_loop())
            
            logger.info(f"mDNS discovery started on {self.MDNS_ADDR}:{self.MDNS_PORT}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start mDNS: {e}")
            return False
    
    async def stop(self):
        """Stop mDNS discovery"""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
    
    async def _announce_loop(self):
        """Periodically announce our presence"""
        while self.running:
            try:
                self._send_announcement()
                await asyncio.sleep(self.announce_interval)
            except Exception as e:
                logger.debug(f"Announce error: {e}")
    
    def _send_announcement(self):
        """Send mDNS announcement"""
        if not self.socket:
            return
        
        # Create announcement packet
        announcement = {
            'type': 'minecraftBC_announce',
            'node_id': self.node_id,
            'name': self.node_name,
            'port': self.service_port,
            'capabilities': self.capabilities,
            'timestamp': time.time()
        }
        
        data = json.dumps(announcement).encode()
        
        try:
            self.socket.sendto(data, (self.MDNS_ADDR, self.MDNS_PORT))
        except Exception as e:
            logger.debug(f"Failed to send announcement: {e}")
    
    async def _receive_loop(self):
        """Receive and process mDNS announcements"""
        while self.running:
            try:
                if not self.socket:
                    await asyncio.sleep(0.1)
                    continue
                
                # Receive data
                data, addr = await asyncio.get_event_loop().sock_recvfrom(
                    self.socket, 1024
                )
                
                # Process announcement
                self._process_announcement(data, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Receive error: {e}")
                await asyncio.sleep(0.1)
    
    def _process_announcement(self, data: bytes, addr: tuple):
        """Process received announcement"""
        try:
            message = json.loads(data.decode())
            
            # Validate
            if message.get('type') != 'minecraftBC_announce':
                return
            
            node_id = message.get('node_id')
            if not node_id or node_id == self.node_id:
                return  # Ignore self or invalid
            
            # Create/update discovered node
            node = DiscoveredNode(
                node_id=node_id,
                name=message.get('name', 'Unknown'),
                addresses=[(addr[0], message.get('port', 0))],
                capabilities=message.get('capabilities', []),
                last_seen=time.time()
            )
            
            # Update discovered nodes
            is_new = node_id not in self.discovered
            self.discovered[node_id] = node
            
            # Notify callbacks
            if is_new:
                logger.info(f"Discovered new node: {node.name} ({node_id})")
                for callback in self.callbacks:
                    try:
                        callback(node)
                    except Exception as e:
                        logger.error(f"Discovery callback error: {e}")
            
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # Ignore invalid packets
    
    async def _cleanup_loop(self):
        """Remove stale discovery entries"""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Remove expired nodes
                expired = [
                    node_id for node_id, node in self.discovered.items()
                    if not node.is_valid()
                ]
                
                for node_id in expired:
                    del self.discovered[node_id]
                    logger.debug(f"Removed expired node: {node_id}")
                    
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")
    
    def on_discover(self, callback: Callable[[DiscoveredNode], None]):
        """Register discovery callback"""
        self.callbacks.append(callback)
    
    def get_discovered(self) -> List[DiscoveredNode]:
        """Get list of valid discovered nodes"""
        return [node for node in self.discovered.values() if node.is_valid()]
    
    def get_node(self, node_id: str) -> Optional[DiscoveredNode]:
        """Get specific discovered node"""
        node = self.discovered.get(node_id)
        if node and node.is_valid():
            return node
        return None


class SignalingDiscovery:
    """
    Signaling server discovery for WAN
    
    Connects to a signaling server to discover peers across the internet.
    """
    
    def __init__(self, node_id: str, node_name: str, 
                 signal_server: str, capabilities: List[str] = None):
        self.node_id = node_id
        self.node_name = node_name
        self.signal_server = signal_server
        self.capabilities = capabilities or ["p2p"]
        
        self.ws: Optional[Any] = None  # WebSocket connection
        self.running = False
        self.discovered: Dict[str, DiscoveredNode] = {}
        self.callbacks: List[Callable[[DiscoveredNode], None]] = []
    
    async def start(self) -> bool:
        """Start signaling discovery"""
        try:
            import websockets
            
            self.running = True
            
            # Connect to signaling server
            uri = f"ws://{self.signal_server}/signal"
            self.ws = await websockets.connect(uri)
            
            # Register with server
            await self._register()
            
            # Start receive loop
            asyncio.create_task(self._receive_loop())
            
            logger.info(f"Signaling discovery connected to {self.signal_server}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start signaling: {e}")
            return False
    
    async def stop(self):
        """Stop signaling discovery"""
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
    
    async def _register(self):
        """Register with signaling server"""
        if not self.ws:
            return
        
        message = {
            'type': 'register',
            'node_id': self.node_id,
            'name': self.node_name,
            'capabilities': self.capabilities
        }
        
        await self.ws.send(json.dumps(message))
    
    async def _receive_loop(self):
        """Receive messages from signaling server"""
        while self.running:
            try:
                if not self.ws:
                    break
                
                message = await self.ws.recv()
                data = json.loads(message)
                
                await self._handle_message(data)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Signaling receive error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle signaling message"""
        msg_type = data.get('type')
        
        if msg_type == 'peer_list':
            # Received list of available peers
            for peer in data.get('peers', []):
                self._add_discovered_peer(peer)
        
        elif msg_type == 'peer_joined':
            # New peer joined
            self._add_discovered_peer(data.get('peer', {}))
        
        elif msg_type == 'peer_left':
            # Peer disconnected
            node_id = data.get('node_id')
            if node_id in self.discovered:
                del self.discovered[node_id]
    
    def _add_discovered_peer(self, peer: Dict[str, Any]):
        """Add discovered peer"""
        node_id = peer.get('node_id')
        if not node_id or node_id == self.node_id:
            return
        
        node = DiscoveredNode(
            node_id=node_id,
            name=peer.get('name', 'Unknown'),
            addresses=[],  # Will be resolved when connecting
            capabilities=peer.get('capabilities', []),
            last_seen=time.time()
        )
        
        is_new = node_id not in self.discovered
        self.discovered[node_id] = node
        
        if is_new:
            logger.info(f"Discovered peer via signaling: {node.name}")
            for callback in self.callbacks:
                try:
                    callback(node)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    async def query_peers(self):
        """Query for available peers"""
        if not self.ws:
            return
        
        await self.ws.send(json.dumps({'type': 'query_peers'}))
    
    def on_discover(self, callback: Callable[[DiscoveredNode], None]):
        """Register discovery callback"""
        self.callbacks.append(callback)
    
    def get_discovered(self) -> List[DiscoveredNode]:
        """Get list of discovered nodes"""
        return list(self.discovered.values())


class DiscoveryManager:
    """
    Manages multiple discovery methods
    
    Combines mDNS (LAN) and signaling (WAN) discovery.
    """
    
    def __init__(self, node_id: str, node_name: str, 
                 service_port: int, signal_server: Optional[str] = None):
        self.node_id = node_id
        self.node_name = node_name
        self.service_port = service_port
        self.signal_server = signal_server
        
        self.mdns: Optional[MDNSDiscovery] = None
        self.signaling: Optional[SignalingDiscovery] = None
        
        self.all_discovered: Dict[str, DiscoveredNode] = {}
        self.callbacks: List[Callable[[DiscoveredNode], None]] = []
    
    async def start(self) -> bool:
        """Start all discovery methods"""
        # Start mDNS
        self.mdns = MDNSDiscovery(
            self.node_id, 
            self.node_name, 
            self.service_port
        )
        self.mdns.on_discover(self._on_node_discovered)
        
        if not await self.mdns.start():
            logger.warning("Failed to start mDNS discovery")
        
        # Start signaling if server configured
        if self.signal_server:
            self.signaling = SignalingDiscovery(
                self.node_id,
                self.node_name,
                self.signal_server
            )
            self.signaling.on_discover(self._on_node_discovered)
            
            if not await self.signaling.start():
                logger.warning("Failed to start signaling discovery")
        
        return True
    
    async def stop(self):
        """Stop all discovery methods"""
        if self.mdns:
            await self.mdns.stop()
        if self.signaling:
            await self.signaling.stop()
    
    def _on_node_discovered(self, node: DiscoveredNode):
        """Handle discovered node"""
        self.all_discovered[node.node_id] = node
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(node)
            except Exception as e:
                logger.error(f"Discovery callback error: {e}")
    
    def on_discover(self, callback: Callable[[DiscoveredNode], None]):
        """Register discovery callback"""
        self.callbacks.append(callback)
    
    def get_all_discovered(self) -> List[DiscoveredNode]:
        """Get all discovered nodes"""
        # Update from both sources
        if self.mdns:
            for node in self.mdns.get_discovered():
                self.all_discovered[node.node_id] = node
        
        if self.signaling:
            for node in self.signaling.get_discovered():
                self.all_discovered[node.node_id] = node
        
        return list(self.all_discovered.values())
    
    def get_node(self, node_id: str) -> Optional[DiscoveredNode]:
        """Get specific node"""
        return self.all_discovered.get(node_id)
    
    async def query_signaling(self):
        """Query signaling server for peers"""
        if self.signaling:
            await self.signaling.query_peers()


# Example usage
if __name__ == '__main__':
    async def main():
        from ..protocol.fastlink.packet import generate_node_id
        
        node_id = generate_node_id()
        print(f"Starting discovery for node: {node_id}")
        
        # Create discovery manager
        discovery = DiscoveryManager(
            node_id=node_id,
            node_name="TestNode",
            service_port=25565
        )
        
        # Register callback
        def on_discover(node: DiscoveredNode):
            print(f"Discovered: {node.name} ({node.node_id})")
            print(f"  Addresses: {node.addresses}")
            print(f"  Capabilities: {node.capabilities}")
        
        discovery.on_discover(on_discover)
        
        # Start
        await discovery.start()
        
        print("Discovery started. Press Ctrl+C to stop.")
        
        try:
            while True:
                await asyncio.sleep(5)
                nodes = discovery.get_all_discovered()
                print(f"Total discovered: {len(nodes)}")
        except KeyboardInterrupt:
            pass
        
        # Stop
        await discovery.stop()
    
    asyncio.run(main())