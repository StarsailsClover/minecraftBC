"""
Basic TCP Server Test

Simplified test without complex dependencies.
"""

import asyncio
import struct
import socket
from enum import IntEnum
from dataclasses import dataclass
from typing import List


class PacketType(IntEnum):
    HEARTBEAT = 0x01
    HANDSHAKE = 0x02
    SERVER_LIST = 0x03
    CONNECT_REQUEST = 0x04
    CONNECT_RESPONSE = 0x05
    DISCONNECT = 0x06
    ERROR = 0x07
    AUTH = 0x08


@dataclass
class MockServerInfo:
    id: str
    name: str
    host: str
    port: int


class SimpleTCPServer:
    """Simplified TCP server for testing"""
    
    def __init__(self, host="127.0.0.1", port=25566):
        self.host = host
        self.port = port
        self.server = None
        self.connections = []
        self.servers = [
            MockServerInfo("test-1", "Test Server 1", "192.168.1.1", 25565),
            MockServerInfo("test-2", "Test Server 2", "192.168.1.2", 25565),
        ]
        
    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        print(f"[SERVER] Started on {self.host}:{self.port}")
        
    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
    async def _handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[SERVER] Client connected: {addr}")
        self.connections.append(writer)
        
        try:
            while True:
                # Read length
                length_data = await reader.read(4)
                if not length_data:
                    break
                    
                length = struct.unpack('>I', length_data)[0]
                
                # Read type
                type_byte = await reader.read(1)
                packet_type = struct.unpack('B', type_byte)[0]
                
                # Read payload
                payload_length = length - 1
                payload = await reader.read(payload_length) if payload_length > 0 else b''
                
                await self._process_packet(writer, packet_type, payload)
                
        except Exception as e:
            print(f"[SERVER] Client error: {e}")
        finally:
            print(f"[SERVER] Client disconnected: {addr}")
            self.connections.remove(writer)
            writer.close()
            
    async def _process_packet(self, writer, packet_type, payload):
        if packet_type == PacketType.HANDSHAKE:
            print(f"[SERVER] Received HANDSHAKE")
            # Send server list
            await self._send_server_list(writer)
        elif packet_type == PacketType.HEARTBEAT:
            print(f"[SERVER] Received HEARTBEAT")
            # Echo heartbeat
            await self._send_heartbeat(writer)
        elif packet_type == PacketType.CONNECT_REQUEST:
            print(f"[SERVER] Received CONNECT_REQUEST")
            # Send connect response
            await self._send_connect_response(writer, True)
            
    async def _send_server_list(self, writer):
        import io
        buf = io.BytesIO()
        
        # Write server count
        buf.write(struct.pack('>I', len(self.servers)))
        
        for srv in self.servers:
            # Write server info
            for s in [srv.id, srv.name, "", srv.host]:
                data = s.encode('utf-8')
                buf.write(struct.pack('>I', len(data)))
                buf.write(data)
            buf.write(struct.pack('>I', srv.port))
            buf.write(struct.pack('>I', 50))  # latency
            buf.write(struct.pack('>I', 0))  # player count
            buf.write(struct.pack('>I', 20))  # max players
            version = "1.20.6"
            data = version.encode('utf-8')
            buf.write(struct.pack('>I', len(data)))
            buf.write(data)
            
        payload = buf.getvalue()
        total_length = 1 + len(payload)
        
        writer.write(struct.pack('>I', total_length))
        writer.write(struct.pack('B', PacketType.SERVER_LIST))
        writer.write(payload)
        await writer.drain()
        print(f"[SERVER] Sent SERVER_LIST ({len(self.servers)} servers)")
        
    async def _send_heartbeat(self, writer):
        writer.write(struct.pack('>I', 1))
        writer.write(struct.pack('B', PacketType.HEARTBEAT))
        await writer.drain()
        
    async def _send_connect_response(self, writer, success):
        import io
        buf = io.BytesIO()
        buf.write(struct.pack('B', 1 if success else 0))
        
        for s in ["test-server", "127.0.0.1", "Connected"]:
            data = s.encode('utf-8')
            buf.write(struct.pack('>I', len(data)))
            buf.write(data)
        buf.write(struct.pack('>I', 30000))  # local port
        
        payload = buf.getvalue()
        total_length = 1 + len(payload)
        
        writer.write(struct.pack('>I', total_length))
        writer.write(struct.pack('B', PacketType.CONNECT_RESPONSE))
        writer.write(payload)
        await writer.drain()
        print(f"[SERVER] Sent CONNECT_RESPONSE")


class MockClient:
    """Mock client for testing"""
    
    def __init__(self):
        self.reader = None
        self.writer = None
        self.packets = []
        
    async def connect(self, host="127.0.0.1", port=25566):
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            print(f"[CLIENT] Connected to {host}:{port}")
            return True
        except Exception as e:
            print(f"[CLIENT] Connection failed: {e}")
            return False
            
    async def send_handshake(self):
        import io
        buf = io.BytesIO()
        
        buf.write(struct.pack('>I', 1))  # protocol version
        buf.write(struct.pack('>I', 2))  # mod version
        
        for s in ["1.20.6", "test-uuid", "TestPlayer"]:
            data = s.encode('utf-8')
            buf.write(struct.pack('>I', len(data)))
            buf.write(data)
            
        payload = buf.getvalue()
        total_length = 1 + len(payload)
        
        self.writer.write(struct.pack('>I', total_length))
        self.writer.write(struct.pack('B', PacketType.HANDSHAKE))
        self.writer.write(payload)
        await self.writer.drain()
        print("[CLIENT] Sent HANDSHAKE")
        
    async def read_packets(self, timeout=5):
        """Read packets for a given time"""
        end_time = asyncio.get_event_loop().time() + timeout
        
        while asyncio.get_event_loop().time() < end_time:
            try:
                # Wait for data with timeout
                await asyncio.wait_for(
                    self._read_one_packet(),
                    timeout=end_time - asyncio.get_event_loop().time()
                )
            except asyncio.TimeoutError:
                break
                
    async def _read_one_packet(self):
        length_data = await self.reader.read(4)
        if not length_data:
            return
            
        length = struct.unpack('>I', length_data)[0]
        type_byte = await self.reader.read(1)
        packet_type = struct.unpack('B', type_byte)[0]
        
        payload_length = length - 1
        payload = await self.reader.read(payload_length) if payload_length > 0 else b''
        
        self.packets.append((packet_type, payload))
        print(f"[CLIENT] Received: {PacketType(packet_type).name}")
        
    def close(self):
        if self.writer:
            self.writer.close()


async def run_test():
    """Run basic TCP test"""
    print("=" * 60)
    print("Basic TCP Server Test")
    print("=" * 60)
    
    # Start server
    server = SimpleTCPServer()
    await server.start()
    
    # Give server time to start
    await asyncio.sleep(0.5)
    
    # Connect client
    client = MockClient()
    connected = await client.connect()
    
    if not connected:
        print("[TEST] FAILED: Connection failed")
        await server.stop()
        return False
        
    # Send handshake
    await client.send_handshake()
    
    # Read responses
    await client.read_packets(timeout=3)
    
    # Cleanup
    client.close()
    await server.stop()
    
    # Results
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Connection: {'PASS' if connected else 'FAIL'}")
    print(f"Packets received: {len(client.packets)}")
    
    if client.packets:
        print("\nReceived packets:")
        for pkt_type, _ in client.packets:
            print(f"  - {PacketType(pkt_type).name}")
            
    success = connected and len(client.packets) > 0
    print(f"\nOverall: {'PASS' if success else 'FAIL'}")
    return success


if __name__ == "__main__":
    import sys
    try:
        result = asyncio.run(run_test())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
