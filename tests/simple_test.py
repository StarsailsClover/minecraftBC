"""
Simple Unit Tests for minecraftBC (No pytest required)

Usage:
    python tests/simple_test.py
"""

import asyncio
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nat.birthday_punch import BirthdayPunch, ISPType, NATType, PunchResult, ISPParams
from nat.tcp_proxy_tunnel import TCPProxyTunnel, TunnelManager


class TestRunner:
    """Simple test runner"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
        
    def test(self, name):
        """Decorator to register test"""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator
        
    def run(self):
        """Run all tests"""
        print("=" * 60)
        print("Running minecraftBC Unit Tests")
        print("=" * 60)
        print()
        
        for name, func in self.tests:
            try:
                print(f"Testing: {name}...", end=" ")
                
                # Run test
                if asyncio.iscoroutinefunction(func):
                    asyncio.run(func())
                else:
                    func()
                    
                print("PASS")
                self.passed += 1
                
            except Exception as e:
                print(f"FAIL: {e}")
                self.failed += 1
                traceback.print_exc()
                print()
                
        # Summary
        print()
        print("=" * 60)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("=" * 60)
        
        return self.failed == 0


# Create test runner
runner = TestRunner()


@runner.test("ISPParams.for_isp")
def test_isp_params():
    """Test ISP parameter generation"""
    # Test China Telecom
    params = ISPParams.for_isp(ISPType.CHINA_TELECOM)
    assert params.isp_type == ISPType.CHINA_TELECOM
    assert params.port_increment == 48
    
    # Test China Unicom
    params = ISPParams.for_isp(ISPType.CHINA_UNICOM)
    assert params.port_increment == 64
    
    # Test China Mobile
    params = ISPParams.for_isp(ISPType.CHINA_MOBILE)
    assert params.port_increment == 32
    

@runner.test("BirthdayPunch.predict_port_range")
def test_predict_port_range():
    """Test port prediction"""
    punch = BirthdayPunch(isp_type=ISPType.CHINA_TELECOM)
    
    ports = punch.predict_port_range(30000, 0)
    assert isinstance(ports, list)
    assert len(ports) > 0
    
    # All ports should be valid
    for port in ports:
        assert 1024 <= port <= 65535
        

@runner.test("BirthdayPunch.punch timeout")
async def test_punch_timeout():
    """Test punch with invalid target"""
    punch = BirthdayPunch()
    
    result = await punch.punch(
        target_public_addr=("127.0.0.1", 1),
        target_local_addr=("127.0.0.1", 1),
        timeout=1.0
    )
    
    assert isinstance(result, PunchResult)
    assert result.success == False
    assert result.attempts >= 0
    
    punch.close()


@runner.test("TCPProxyTunnel start/stop")
async def test_tunnel_start_stop():
    """Test tunnel lifecycle"""
    tunnel = TCPProxyTunnel(local_host="127.0.0.1", local_port=0)
    
    # Start
    port = await tunnel.start()
    assert port > 0
    assert tunnel.local_port == port
    
    # Stop
    await tunnel.stop()


@runner.test("TunnelManager create/close")
async def test_tunnel_manager():
    """Test tunnel manager"""
    manager = TunnelManager()
    
    # Mock P2P functions
    def mock_send(data):
        pass
    def mock_recv():
        return b""
        
    # Create tunnel
    port = await manager.create_tunnel("test", mock_send, mock_recv)
    assert port > 0
    
    # List tunnels
    tunnels = manager.list_tunnels()
    assert "test" in tunnels
    
    # Get stats
    stats = manager.get_tunnel_stats("test")
    assert stats is not None
    
    # Close
    await manager.close_tunnel("test")
    assert "test" not in manager.tunnels
    
    # Cleanup
    await manager.close_all()


@runner.test("Protocol packet header")
def test_packet_header():
    """Test packet header encoding"""
    import struct
    
    length = 100
    packet_type = 0x01
    
    header = struct.pack('>I', length) + struct.pack('B', packet_type)
    
    assert len(header) == 5
    assert struct.unpack('>I', header[:4])[0] == length
    assert struct.unpack('B', header[4:5])[0] == packet_type


@runner.test("String encoding")
def test_string_encoding():
    """Test string length-prefixed encoding"""
    import struct
    import io
    
    buf = io.BytesIO()
    test_string = "Hello World"
    
    # Write
    data = test_string.encode('utf-8')
    buf.write(struct.pack('>I', len(data)))
    buf.write(data)
    
    # Read
    buf.seek(0)
    length = struct.unpack('>I', buf.read(4))[0]
    read_data = buf.read(length)
    read_string = read_data.decode('utf-8')
    
    assert read_string == test_string


if __name__ == "__main__":
    success = runner.run()
    sys.exit(0 if success else 1)
