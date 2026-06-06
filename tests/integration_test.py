"""
Integration Test for minecraftBC

Tests the complete flow:
1. Python external server starts
2. TCP server accepts connections
3. Mock client connects and handshakes
4. Server list is sent
5. P2P tunnel is created

Usage:
    python tests/integration_test.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from external.tcp_server import ExternalTCPServer, P2PServerInfo
from nat.tcp_proxy_tunnel import TunnelManager


class IntegrationTest:
    """Complete integration test"""
    
    def __init__(self):
        self.server = None
        self.tunnel_manager = None
        self.results = {}
        
    async def run(self):
        """Run all integration tests"""
        print("=" * 70)
        print("minecraftBC Integration Test")
        print("=" * 70)
        print()
        
        try:
            # Test 1: Server startup
            await self.test_server_startup()
            
            # Test 2: TCP connection
            await self.test_tcp_connection()
            
            # Test 3: Handshake
            await self.test_handshake()
            
            # Test 4: Server list
            await self.test_server_list()
            
            # Test 5: Tunnel creation
            await self.test_tunnel_creation()
            
            # Summary
            self.print_summary()
            
        except Exception as e:
            print(f"\n[ERROR] Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        return all(self.results.values())
        
    async def test_server_startup(self):
        """Test 1: External server startup"""
        print("[TEST 1/5] Server startup...")
        
        try:
            # Create mock servers
            servers = [
                P2PServerInfo(
                    id="test-server-1",
                    name="Test Server 1",
                    host="192.168.1.100",
                    port=25565,
                    latency=50
                )
            ]
            
            # Start server
            self.server = ExternalTCPServer(
                host="127.0.0.1",
                port=25566,
                hybrid_connector=None
            )
            self.server.servers = servers
            
            await self.server.start()
            
            self.results['server_startup'] = True
            print("  ✓ Server started on 127.0.0.1:25566")
            
        except Exception as e:
            self.results['server_startup'] = False
            print(f"  ✗ Failed: {e}")
            raise
            
    async def test_tcp_connection(self):
        """Test 2: TCP connection"""
        print("[TEST 2/5] TCP connection...")
        
        try:
            # Connect mock client
            import struct
            reader, writer = await asyncio.open_connection("127.0.0.1", 25566)
            
            self.results['tcp_connection'] = True
            print("  ✓ TCP connection established")
            
            # Store for later tests
            self.test_reader = reader
            self.test_writer = writer
            
        except Exception as e:
            self.results['tcp_connection'] = False
            print(f"  ✗ Failed: {e}")
            raise
            
    async def test_handshake(self):
        """Test 3: Handshake protocol"""
        print("[TEST 3/5] Handshake...")
        
        try:
            import struct
            import io
            
            # Build handshake packet
            buf = io.BytesIO()
            buf.write(struct.pack('>I', 1))  # protocol version
            buf.write(struct.pack('>I', 2))  # mod version
            
            for s in ["1.20.6", "test-uuid", "TestPlayer"]:
                data = s.encode('utf-8')
                buf.write(struct.pack('>I', len(data)))
                buf.write(data)
                
            payload = buf.getvalue()
            total_length = 1 + len(payload)
            
            # Send packet
            self.test_writer.write(struct.pack('>I', total_length))
            self.test_writer.write(struct.pack('B', 0x02))  # HANDSHAKE
            self.test_writer.write(payload)
            await self.test_writer.drain()
            
            self.results['handshake'] = True
            print("  ✓ Handshake sent")
            
        except Exception as e:
            self.results['handshake'] = False
            print(f"  ✗ Failed: {e}")
            raise
            
    async def test_server_list(self):
        """Test 4: Server list reception"""
        print("[TEST 4/5] Server list...")
        
        try:
            import struct
            
            # Wait for server list
            data = await asyncio.wait_for(
                self.test_reader.read(4),
                timeout=5.0
            )
            
            if not data:
                raise Exception("No data received")
                
            length = struct.unpack('>I', data)[0]
            packet_type = await self.test_reader.read(1)
            ptype = struct.unpack('B', packet_type)[0]
            
            if ptype != 0x03:  # SERVER_LIST
                raise Exception(f"Expected SERVER_LIST, got {ptype}")
                
            # Read payload
            payload = await self.test_reader.read(length - 1)
            
            self.results['server_list'] = True
            print("  ✓ Server list received")
            
        except Exception as e:
            self.results['server_list'] = False
            print(f"  ✗ Failed: {e}")
            raise
            
    async def test_tunnel_creation(self):
        """Test 5: Tunnel creation"""
        print("[TEST 5/5] Tunnel creation...")
        
        try:
            # Create tunnel manager
            self.tunnel_manager = TunnelManager()
            
            # Mock P2P functions
            def mock_send(data):
                pass
            def mock_recv():
                return b""
                
            # Create tunnel
            port = await self.tunnel_manager.create_tunnel(
                "test-tunnel",
                mock_send,
                mock_recv
            )
            
            if port <= 0:
                raise Exception("Invalid port")
                
            # Verify tunnel exists
            tunnels = self.tunnel_manager.list_tunnels()
            if "test-tunnel" not in tunnels:
                raise Exception("Tunnel not created")
                
            self.results['tunnel_creation'] = True
            print(f"  ✓ Tunnel created on port {port}")
            
        except Exception as e:
            self.results['tunnel_creation'] = False
            print(f"  ✗ Failed: {e}")
            raise
            
    def print_summary(self):
        """Print test summary"""
        print()
        print("=" * 70)
        print("Integration Test Summary")
        print("=" * 70)
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        for test, result in self.results.items():
            status = "PASS" if result else "FAIL"
            symbol = "✓" if result else "✗"
            print(f"  {symbol} {test}: {status}")
            
        print()
        print(f"Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("Status: ALL TESTS PASSED ✓")
        else:
            print("Status: SOME TESTS FAILED ✗")
            
        print("=" * 70)
        
    async def cleanup(self):
        """Cleanup resources"""
        print()
        print("[CLEANUP] Closing resources...")
        
        try:
            if hasattr(self, 'test_writer'):
                self.test_writer.close()
                await self.test_writer.wait_closed()
        except:
            pass
            
        try:
            if self.server:
                await self.server.stop()
        except:
            pass
            
        try:
            if self.tunnel_manager:
                await self.tunnel_manager.close_all()
        except:
            pass
            
        print("[CLEANUP] Done")


async def main():
    """Main entry"""
    test = IntegrationTest()
    
    try:
        success = await test.run()
        await test.cleanup()
        return 0 if success else 1
    except Exception:
        await test.cleanup()
        return 1


if __name__ == "__main__":
    import sys
    result = asyncio.run(main())
    sys.exit(result)
