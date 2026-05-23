"""
Network Connector Module
网络连接器模块

Provides unified connection management for P2P and Server modes.
为 P2P 和 Server 模式提供统一的连接管理。
"""

from __future__ import annotations
import asyncio
from typing import Optional, Dict, List, Callable, Any, Union
from dataclasses import dataclass
from enum import IntEnum
import logging

from ..protocol.fastlink.p2p import P2PConnection, NodeInfo
from ..protocol.fastlink.server import FastLinkServer
from .discovery import DiscoveryManager, DiscoveredNode

logger = logging.getLogger(__name__)


class ConnectionMode(IntEnum):
    """Connection mode"""
    P2P = 1
    SERVER = 2
    CLIENT = 3


@dataclass
class ConnectionConfig:
    """Connection configuration"""
    mode: ConnectionMode
    bind_host: str = "0.0.0.0"
    bind_port: int = 0
    server_host: Optional[str] = None
    server_port: Optional[int] = None
    room_name: Optional[str] = None
    room_password: Optional[str] = None
    use_discovery: bool = True
    signal_server: Optional[str] = None


class UnifiedConnector:
    """
    Unified connector for minecraftBC
    
    Manages both P2P and Server connections with automatic discovery.
    """
    
    def __init__(self, node_id: str, node_name: str, config: ConnectionConfig):
        self.node_id = node_id
        self.node_name = node_name
        self.config = config
        
        # Connection instances
        self.p2p: Optional[P2PConnection] = None
        self.server: Optional[FastLinkServer] = None
        self.discovery: Optional[DiscoveryManager] = None
        
        # State
        self.connected = False
        self.current_room: Optional[str] = None
        
        # Callbacks
        self.message_handlers: List[Callable[[str, bytes, str], None]] = []
        self.connect_handlers: List[Callable[[str], None]] = []
        self.disconnect_handlers: List[Callable[[str], None]] = []
    
    async def start(self) -> bool:
        """Start connector"""
        try:
            if self.config.mode == ConnectionMode.P2P:
                return await self._start_p2p()
            elif self.config.mode == ConnectionMode.SERVER:
                return await self._start_server()
            elif self.config.mode == ConnectionMode.CLIENT:
                return await self._start_client()
            else:
                logger.error(f"Unknown connection mode: {self.config.mode}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start connector: {e}")
            return False
    
    async def _start_p2p(self) -> bool:
        """Start P2P mode"""
        logger.info("Starting P2P mode...")
        
        # Create P2P connection
        self.p2p = P2PConnection(
            self.node_id,
            (self.config.bind_host, self.config.bind_port)
        )
        
        # Setup handlers
        self.p2p.on_message(self._on_p2p_message)
        self.p2p.on_connect(self._on_p2p_connect)
        self.p2p.on_disconnect(self._on_p2p_disconnect)
        
        # Start
        if not await self.p2p.start():
            return False
        
        self.connected = True
        
        # Start discovery if enabled
        if self.config.use_discovery:
            self.discovery = DiscoveryManager(
                self.node_id,
                self.node_name,
                self.p2p.bind_addr[1],
                self.config.signal_server
            )
            self.discovery.on_discover(self._on_discovered_node)
            await self.discovery.start()
        
        logger.info(f"P2P started on {self.p2p.bind_addr}")
        return True
    
    async def _start_server(self) -> bool:
        """Start Server mode"""
        logger.info("Starting Server mode...")
        
        # Create server
        self.server = FastLinkServer(
            self.node_id,
            (self.config.bind_host, self.config.bind_port)
        )
        
        # Start
        if not await self.server.start():
            return False
        
        self.connected = True
        
        # Create default room if specified
        if self.config.room_name:
            room_id = self.server.create_room(
                name=self.config.room_name,
                password=self.config.room_password
            )
            self.current_room = room_id
            logger.info(f"Created room: {room_id}")
        
        logger.info(f"Server started on port {self.config.bind_port}")
        return True
    
    async def _start_client(self) -> bool:
        """Start Client mode"""
        logger.info("Starting Client mode...")
        
        # Client mode connects to a server
        # This would implement the client-side connection logic
        logger.info(f"Connecting to {self.config.server_host}:{self.config.server_port}")
        
        # 实现客户端连接逻辑
        try:
            if self.config.mode == ConnectionMode.CLIENT:
                if not self.config.server_host or not self.config.server_port:
                    logger.error("Server address not configured")
                    return False
                
                # 启动发现服务
                if self.config.use_discovery:
                    self.discovery = DiscoveryManager(self.node_id)
                    self.discovery.on_discovered(self._on_discovered)
                    await self.discovery.start()
                
                # 创建P2P连接
                self.p2p = P2PConnection(
                    node_id=self.node_id,
                    bind_addr=(self.config.bind_host, self.config.bind_port)
                )
                
                # 设置P2P回调
                self.p2p.on_message(self._on_p2p_message)
                self.p2p.on_connect(self._on_p2p_connect)
                self.p2p.on_disconnect(self._on_p2p_disconnect)
                
                # 启动P2P
                if not await self.p2p.start():
                    logger.error("Failed to start P2P connection")
                    return False
                
                # 尝试连接到指定的服务器节点
                server_addr = (self.config.server_host, self.config.server_port)
                logger.info(f"Connecting to server at {server_addr}")
                
                # 发起连接（通过P2P hole punching）
                success = await self.p2p.connect_to_peer(
                    self.config.server_host,  # 使用server_host作为peer_id
                    server_addr,
                    timeout=30.0
                )
                
                if not success:
                    logger.error(f"Failed to connect to server {server_addr}")
                    return False
                
                logger.info(f"Successfully connected to server {server_addr}")
                
            elif self.config.mode == ConnectionMode.P2P:
                # P2P模式：仅启动P2P监听
                self.p2p = P2PConnection(
                    node_id=self.node_id,
                    bind_addr=(self.config.bind_host, self.config.bind_port)
                )
                
                self.p2p.on_message(self._on_p2p_message)
                self.p2p.on_connect(self._on_p2p_connect)
                self.p2p.on_disconnect(self._on_p2p_disconnect)
                
                if not await self.p2p.start():
                    logger.error("Failed to start P2P connection")
                    return False
                
                # 启动发现
                if self.config.use_discovery:
                    self.discovery = DiscoveryManager(self.node_id)
                    self.discovery.on_discovered(self._on_discovered)
                    await self.discovery.start()
                    
            elif self.config.mode == ConnectionMode.SERVER:
                # 服务器模式
                self.server = FastLinkServer(
                    bind_addr=(self.config.bind_host, self.config.bind_port)
                )
                
                # 设置服务器回调
                self.server.on_room_created(self._on_room_created)
                self.server.on_player_joined(self._on_player_joined)
                self.server.on_player_left(self._on_player_left)
                
                if not await self.server.start():
                    logger.error("Failed to start server")
                    return False
                
                # 如果指定了房间，自动创建
                if self.config.room_name:
                    room = await self.server.create_room(
                        self.config.room_name,
                        password=self.config.room_password
                    )
                    if room:
                        logger.info(f"Created room: {room.room_id}")
                        self.current_room = room.room_id
                
                # 启动发现
                if self.config.use_discovery:
                    self.discovery = DiscoveryManager(self.node_id)
                    await self.discovery.start()
                    # 广播服务器存在
                    await self.discovery.announce_service(
                        "fastlink_server",
                        self.config.bind_port,
                        {"node_name": self.node_name}
                    )
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """Stop connector"""
        self.connected = False
        
        if self.p2p:
            await self.p2p.stop()
            self.p2p = None
        
        if self.server:
            await self.server.stop()
            self.server = None
        
        if self.discovery:
            await self.discovery.stop()
            self.discovery = None
        
        logger.info("Connector stopped")
    
    async def connect_to_peer(self, node_info: NodeInfo) -> bool:
        """Connect to a peer (P2P mode)"""
        if not self.p2p:
            logger.error("Not in P2P mode")
            return False
        
        return await self.p2p.connect(node_info)
    
    async def connect_to_discovered(self, node_id: str) -> bool:
        """Connect to a discovered node"""
        if not self.discovery:
            logger.error("Discovery not enabled")
            return False
        
        node = self.discovery.get_node(node_id)
        if not node:
            logger.error(f"Node {node_id} not found in discovery")
            return False
        
        # Convert to NodeInfo
        node_info = NodeInfo(
            node_id=node.node_id,
            public_key="",  # Would be obtained from discovery
            external_ip=node.addresses[0][0] if node.addresses else "",
            external_port=node.addresses[0][1] if node.addresses else 0,
            internal_ip="",
            internal_port=0,
            capabilities=node.capabilities
        )
        
        return await self.connect_to_peer(node_info)
    
    async def send(self, target: str, data: bytes) -> bool:
        """Send data to target"""
        if self.p2p:
            return await self.p2p.send(target, data)
        return False
    
    async def broadcast(self, data: bytes) -> int:
        """Broadcast data to all peers"""
        if self.p2p:
            return await self.p2p.broadcast(data)
        return 0
    
    def _on_p2p_message(self, peer_id: str, data: bytes, addr: str):
        """Handle P2P message"""
        for handler in self.message_handlers:
            try:
                handler(peer_id, data, addr)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    def _on_p2p_connect(self, peer_id: str):
        """Handle P2P connect"""
        logger.info(f"Connected to peer: {peer_id}")
        for handler in self.connect_handlers:
            try:
                handler(peer_id)
            except Exception as e:
                logger.error(f"Connect handler error: {e}")
    
    def _on_p2p_disconnect(self, peer_id: str):
        """Handle P2P disconnect"""
        logger.info(f"Disconnected from peer: {peer_id}")
        for handler in self.disconnect_handlers:
            try:
                handler(peer_id)
            except Exception as e:
                logger.error(f"Disconnect handler error: {e}")
    
    def _on_discovered_node(self, node: DiscoveredNode):
        """Handle discovered node"""
        logger.info(f"Discovered node: {node.name} ({node.node_id})")
        # Auto-connect if configured
        # asyncio.create_task(self.connect_to_discovered(node.node_id))
    
    def on_message(self, handler: Callable[[str, bytes, str], None]):
        """Register message handler"""
        self.message_handlers.append(handler)
    
    def on_connect(self, handler: Callable[[str], None]):
        """Register connect handler"""
        self.connect_handlers.append(handler)
    
    def on_disconnect(self, handler: Callable[[str], None]):
        """Register disconnect handler"""
        self.disconnect_handlers.append(handler)
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status"""
        status = {
            'mode': self.config.mode.name,
            'connected': self.connected,
            'node_id': self.node_id,
            'node_name': self.node_name
        }
        
        if self.p2p:
            status['p2p'] = {
                'bind_addr': self.p2p.bind_addr,
                'connected_peers': len(self.p2p.get_connected_peers()),
                'peers': self.p2p.get_connected_peers()
            }
        
        if self.server:
            status['server'] = self.server.get_stats()
        
        if self.discovery:
            status['discovery'] = {
                'discovered_nodes': len(self.discovery.get_all_discovered())
            }
        
        return status


# Example usage
if __name__ == '__main__':
    async def main():
        from ..protocol.fastlink.packet import generate_node_id
        
        node_id = generate_node_id()
        print(f"Starting connector for node: {node_id}")
        
        # Create config for P2P mode
        config = ConnectionConfig(
            mode=ConnectionMode.P2P,
            bind_port=25565,
            use_discovery=True
        )
        
        # Create connector
        connector = UnifiedConnector(
            node_id=node_id,
            node_name="TestConnector",
            config=config
        )
        
        # Register handlers
        def on_message(peer_id: str, data: bytes, addr: str):
            print(f"[Message from {peer_id}]: {data[:50]}...")
        
        def on_connect(peer_id: str):
            print(f"[Connected] {peer_id}")
        
        def on_disconnect(peer_id: str):
            print(f"[Disconnected] {peer_id}")
        
        connector.on_message(on_message)
        connector.on_connect(on_connect)
        connector.on_disconnect(on_disconnect)
        
        # Start
        if await connector.start():
            print("Connector started!")
            print(f"Status: {connector.get_status()}")
            
            try:
                while True:
                    await asyncio.sleep(10)
                    print(f"Status: {connector.get_status()}")
            except KeyboardInterrupt:
                pass
        else:
            print("Failed to start connector")
        
        # Stop
        await connector.stop()
    
    asyncio.run(main())