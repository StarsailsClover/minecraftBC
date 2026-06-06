"""
TCP Proxy Tunnel

Bidirectional TCP proxy for P2P connections.
Routes Minecraft protocol over P2P tunnel.

Architecture:
[Minecraft Client] <--TCP--> [Local Proxy] <--P2P--> [Remote Proxy] <--TCP--> [Minecraft Server]
"""

import asyncio
import socket
import logging
from typing import Optional, Dict, Tuple, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TunnelStats:
    """Tunnel statistics"""
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    connection_time: float = 0.0
    errors: int = 0


class TCPProxyTunnel:
    """
    TCP Proxy Tunnel for P2P connections
    
    Creates a local TCP server that forwards to P2P tunnel.
    """
    
    def __init__(self,
                 local_host: str = "127.0.0.1",
                 local_port: int = 0,
                 p2p_send: Optional[Callable[[bytes], None]] = None,
                 p2p_recv: Optional[Callable[[], bytes]] = None):
        self.local_host = local_host
        self.local_port = local_port
        self.p2p_send = p2p_send
        self.p2p_recv = p2p_recv
        
        self.server: Optional[asyncio.Server] = None
        self.clients: Dict[str, asyncio.Transport] = {}
        self.stats = TunnelStats()
        
        self._running = False
        self._recv_buffer: asyncio.Queue[bytes] = asyncio.Queue()
        
    async def start(self) -> int:
        """
        Start TCP proxy server
        
        Returns:
            Assigned local port number
        """
        self.server = await asyncio.start_server(
            self._handle_client,
            self.local_host,
            self.local_port
        )
        
        # Get assigned port
        if self.local_port == 0:
            self.local_port = self.server.sockets[0].getsockname()[1]
            
        self._running = True
        
        logger.info(f"TCP proxy started on {self.local_host}:{self.local_port}")
        
        # Start P2P receive loop
        if self.p2p_recv:
            asyncio.create_task(self._p2p_receive_loop())
            
        return self.local_port
        
    async def stop(self):
        """Stop TCP proxy server"""
        self._running = False
        
        # Close all client connections
        for client_id, transport in list(self.clients.items()):
            try:
                transport.close()
            except:
                pass
        self.clients.clear()
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        logger.info("TCP proxy stopped")
        
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming Minecraft client connection"""
        addr = writer.get_extra_info('peername')
        client_id = f"{addr[0]}:{addr[1]}"
        
        logger.info(f"Minecraft client connected: {client_id}")
        self.clients[client_id] = writer.transport
        
        try:
            # Start bidirectional forwarding
            await asyncio.gather(
                self._forward_to_p2p(reader, client_id),
                self._forward_from_p2p(writer, client_id),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Client {client_id} error: {e}")
            self.stats.errors += 1
        finally:
            logger.info(f"Minecraft client disconnected: {client_id}")
            if client_id in self.clients:
                del self.clients[client_id]
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
                
    async def _forward_to_p2p(self, reader: asyncio.StreamReader, client_id: str):
        """Forward data from Minecraft client to P2P tunnel"""
        while self._running:
            try:
                # Read from Minecraft client
                data = await reader.read(4096)
                
                if not data:
                    break
                    
                # Update stats
                self.stats.bytes_received += len(data)
                self.stats.packets_received += 1
                
                # Add client ID header
                header = f"[{client_id}]".encode()
                packet = header + b":" + data
                
                # Send through P2P
                if self.p2p_send:
                    self.p2p_send(packet)
                else:
                    # Queue for internal testing
                    await self._recv_buffer.put(packet)
                    
                self.stats.bytes_sent += len(data)
                self.stats.packets_sent += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Forward to P2P error: {e}")
                self.stats.errors += 1
                break
                
    async def _forward_from_p2p(self, writer: asyncio.StreamWriter, client_id: str):
        """Forward data from P2P tunnel to Minecraft client"""
        while self._running:
            try:
                # Wait for data from P2P
                if self.p2p_recv:
                    data = self.p2p_recv()
                else:
                    data = await asyncio.wait_for(
                        self._recv_buffer.get(),
                        timeout=1.0
                    )
                    
                if not data:
                    continue
                    
                # Parse client ID from header
                if b":" in data:
                    header, payload = data.split(b":", 1)
                    target_client = header.decode().strip("[]")
                    
                    # Only forward to matching client
                    if target_client != client_id:
                        continue
                        
                    data = payload
                    
                # Write to Minecraft client
                writer.write(data)
                await writer.drain()
                
                self.stats.bytes_sent += len(data)
                self.stats.packets_sent += 1
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Forward from P2P error: {e}")
                self.stats.errors += 1
                break
                
    async def _p2p_receive_loop(self):
        """Background loop to receive from P2P"""
        while self._running:
            try:
                if self.p2p_recv:
                    data = self.p2p_recv()
                    if data:
                        await self._recv_buffer.put(data)
            except Exception as e:
                logger.debug(f"P2P recv error: {e}")
            await asyncio.sleep(0.001)
            
    def set_p2p_callbacks(self, 
                         send: Callable[[bytes], None],
                         recv: Callable[[], bytes]):
        """Set P2P send/receive callbacks"""
        self.p2p_send = send
        self.p2p_recv = recv
        
    def get_stats(self) -> TunnelStats:
        """Get tunnel statistics"""
        return TunnelStats(
            bytes_sent=self.stats.bytes_sent,
            bytes_received=self.stats.bytes_received,
            packets_sent=self.stats.packets_sent,
            packets_received=self.stats.packets_received,
            connection_time=self.stats.connection_time,
            errors=self.stats.errors
        )


class TunnelManager:
    """
    Manager for multiple proxy tunnels
    
    Handles creation and lifecycle of tunnels.
    """
    
    def __init__(self):
        self.tunnels: Dict[str, TCPProxyTunnel] = {}
        self.next_port = 30000
        
    async def create_tunnel(self, 
                            tunnel_id: str,
                            p2p_send: Callable[[bytes], None],
                            p2p_recv: Callable[[], bytes]) -> int:
        """
        Create new proxy tunnel
        
        Args:
            tunnel_id: Unique tunnel identifier
            p2p_send: Function to send data through P2P
            p2p_recv: Function to receive data from P2P
            
        Returns:
            Local port number for Minecraft to connect to
        """
        if tunnel_id in self.tunnels:
            logger.warning(f"Tunnel {tunnel_id} already exists")
            return self.tunnels[tunnel_id].local_port
            
        tunnel = TCPProxyTunnel(
            local_host="127.0.0.1",
            local_port=self.next_port,
            p2p_send=p2p_send,
            p2p_recv=p2p_recv
        )
        
        port = await tunnel.start()
        self.tunnels[tunnel_id] = tunnel
        
        self.next_port += 1
        
        logger.info(f"Created tunnel {tunnel_id} on port {port}")
        return port
        
    async def close_tunnel(self, tunnel_id: str):
        """Close specific tunnel"""
        if tunnel_id in self.tunnels:
            await self.tunnels[tunnel_id].stop()
            del self.tunnels[tunnel_id]
            logger.info(f"Closed tunnel {tunnel_id}")
            
    async def close_all(self):
        """Close all tunnels"""
        for tunnel_id in list(self.tunnels.keys()):
            await self.close_tunnel(tunnel_id)
            
    def get_tunnel_stats(self, tunnel_id: str) -> Optional[TunnelStats]:
        """Get statistics for specific tunnel"""
        if tunnel_id in self.tunnels:
            return self.tunnels[tunnel_id].get_stats()
        return None
        
    def list_tunnels(self) -> Dict[str, int]:
        """List active tunnels and their ports"""
        return {
            tid: t.local_port 
            for tid, t in self.tunnels.items()
        }


# Example usage
if __name__ == "__main__":
    async def test():
        # Create manager
        manager = TunnelManager()
        
        # Mock P2P functions
        def mock_send(data: bytes):
            print(f"P2P Send: {len(data)} bytes")
            
        def mock_recv() -> bytes:
            return b""
            
        # Create tunnel
        port = await manager.create_tunnel(
            "test-tunnel",
            mock_send,
            mock_recv
        )
        
        print(f"Tunnel created on port {port}")
        print("Connect Minecraft to 127.0.0.1:{}".format(port))
        
        # Run for 30 seconds
        await asyncio.sleep(30)
        
        # Cleanup
        await manager.close_all()
        
    asyncio.run(test())
