"""
Test script for TCP Server

Tests the TCP communication protocol between Python server and mock client.
"""

import asyncio
import struct
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from external.tcp_server import ExternalTCPServer, PacketType, P2PServerInfo


class MockModClient:
    """Mock Minecraft Mod client for testing"""
    
    def __init__(self):
        self.reader = None
        self.writer = None
        self.received_packets = []
        
    async def connect(self, host="127.0.0.1", port=25566):
        """Connect to TCP server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            print(f"[TEST] Connected to {host}:{port}")
            return True
        except Exception as e:
            print(f"[TEST] Connection failed: {e}")
            return False
            
    async def send_handshake(self, protocol_version=1, mc_version="1.20.6", 
                             player_uuid="test-uuid", player_name="TestPlayer"):
        """Send handshake packet"""
        import io
        
        buf = io.BytesIO()
        
        # Write handshake data
        buf.write(struct.pack('>I', protocol_version))
        buf.write(struct.pack('>I', 2))  # mod version
        
        # Write strings
        for s in [mc_version, player_uuid, player_name]:
            data = s.encode('utf-8')
            buf.write(struct.pack('>I', len(data)))
            buf.write(data)
            
        payload = buf.getvalue()
        
        # Send packet
        total_length = 1 + len(payload)
        header = struct.pack('>I', total_length)
        packet = header + struct.pack('B', PacketType.HANDSHAKE) + payload
        
        self.writer.write(packet)
        await self.writer.drain()
        print(f"[TEST] Sent HANDSHAKE")
        
    async def read_packet(self):
        """Read packet from server"""
        try:
            # Read length
            length_data = await self.reader.read(4)
            if not length_data:
                return None
                
            length = struct.unpack('>I', length_data)[0]
            
            # Read type
            type_byte = await self.reader.read(1)
            packet_type = struct.unpack('B', type_byte)[0]
            
            # Read payload
            payload_length = length - 1
            payload = await self.reader.read(payload_length) if payload_length > 0 else b''
            
            return packet_type, payload
            
        except Exception as e:
            print(f"[TEST] Read error: {e}")
            return None
            
    async def listen(self):
        """Listen for packets"""
        while True:
            result = await self.read_packet()
            if result:
                packet_type, payload = result
                self.received_packets.append((packet_type, payload))
                print(f"[TEST] Received packet type: {packet_type}")
                
                if packet_type == PacketType.SERVER_LIST:
                    print(f"[TEST] Server list received!")
                elif packet_type == PacketType.HEARTBEAT:
                    print(f"[TEST] Heartbeat received")
            else:
                await asyncio.sleep(0.1)
                
    async def close(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


async def test_tcp_server():
    """Test TCP server functionality"""
    print("=" * 60)
    print("TCP Server Test")
    print("=" * 60)
    
    # 1. Start TCP Server
    print("\n[1/4] Starting TCP Server...")
    server = ExternalTCPServer(host="127.0.0.1", port=25566)
    
    # Add mock server for testing
    mock_server = P2PServerInfo(
        id="test-server-1",
        name="Test Server",
        description="A test server",
        host="192.168.1.100",
        port=25565,
        latency=50,
        player_count=3,
        max_players=20,
        version="1.20.6"
    )
    
    server.servers = [mock_server]
    
    await server.start()
    print("[TEST] Server started on 127.0.0.1:25566")
    
    # 2. Connect mock client
    print("\n[2/4] Connecting mock client...")
    client = MockModClient()
    connected = await client.connect()
    
    if not connected:
        print("[TEST] FAILED: Could not connect to server")
        await server.stop()
        return False
        
    # 3. Send handshake
    print("\n[3/4] Testing handshake...")
    await client.send_handshake()
    
    # Wait for response
    await asyncio.sleep(1)
    
    # 4. Listen for packets
    print("\n[4/4] Listening for packets...")
    
    # Start listening task
    listen_task = asyncio.create_task(client.listen())
    
    # Wait a few seconds
    await asyncio.sleep(3)
    
    # Check received packets
    print(f"\n[TEST] Total packets received: {len(client.received_packets)}")
    
    # Cleanup
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass
        
    await client.close()
    await server.stop()
    
    # Results
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Connection: {'PASS' if connected else 'FAIL'}")
    print(f"Packets received: {len(client.received_packets)}")
    
    if client.received_packets:
        print("\nPacket types received:")
        for pkt_type, _ in client.received_packets:
            print(f"  - {PacketType(pkt_type).name}")
            
    return connected and len(client.received_packets) > 0


if __name__ == "__main__":
    try:
        success = asyncio.run(test_tcp_server())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[TEST] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
