"""
Unit Tests for minecraftBC

Run tests:
    python -m pytest tests/ -v
    python tests/run_tests.py
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nat.birthday_punch import BirthdayPunch, ISPType, NATType, PunchResult
from nat.tcp_proxy_tunnel import TCPProxyTunnel, TunnelManager


class TestBirthdayPunch:
    """Test BirthdayPunch NAT traversal"""
    
    def test_isp_params(self):
        """Test ISP parameter generation"""
        from nat.birthday_punch import ISPParams, ISPType
        
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
        
    def test_predict_port_range(self):
        """Test port prediction"""
        punch = BirthdayPunch(isp_type=ISPType.CHINA_TELECOM)
        
        # Predict ports
        ports = punch.predict_port_range(30000, 0)
        
        # Should return list of ports
        assert isinstance(ports, list)
        assert len(ports) > 0
        
        # All ports should be in valid range
        for port in ports:
            assert 1024 <= port <= 65535
            
    @pytest.mark.asyncio
    async def test_punch_timeout(self):
        """Test punch timeout with no target"""
        punch = BirthdayPunch()
        
        # Try to punch to non-existent target (should timeout)
        result = await punch.punch(
            target_public_addr=("127.0.0.1", 1),  # Invalid port
            target_local_addr=("127.0.0.1", 1),
            timeout=1.0  # Short timeout for test
        )
        
        assert isinstance(result, PunchResult)
        assert result.success == False
        assert result.attempts > 0
        
        punch.close()
        

class TestTCPProxyTunnel:
    """Test TCP Proxy Tunnel"""
    
    @pytest.mark.asyncio
    async def test_tunnel_start_stop(self):
        """Test tunnel start and stop"""
        tunnel = TCPProxyTunnel(local_host="127.0.0.1", local_port=0)
        
        # Start tunnel
        port = await tunnel.start()
        assert port > 0
        assert tunnel.local_port == port
        
        # Stop tunnel
        await tunnel.stop()
        
    @pytest.mark.asyncio
    async def test_tunnel_manager(self):
        """Test TunnelManager"""
        manager = TunnelManager()
        
        # Mock P2P functions
        def mock_send(data):
            pass
        def mock_recv():
            return b""
            
        # Create tunnel
        port = await manager.create_tunnel(
            "test-tunnel",
            mock_send,
            mock_recv
        )
        
        assert port > 0
        assert "test-tunnel" in manager.tunnels
        
        # Get stats
        stats = manager.get_tunnel_stats("test-tunnel")
        assert stats is not None
        
        # List tunnels
        tunnels = manager.list_tunnels()
        assert "test-tunnel" in tunnels
        
        # Close tunnel
        await manager.close_tunnel("test-tunnel")
        assert "test-tunnel" not in manager.tunnels
        
        # Cleanup
        await manager.close_all()
        

class TestProtocol:
    """Test protocol encoding/decoding"""
    
    def test_packet_header(self):
        """Test packet header format"""
        import struct
        
        # Length: 4 bytes big-endian
        # Type: 1 byte
        # Payload: N bytes
        
        length = 100
        packet_type = 0x01
        
        header = struct.pack('>I', length) + struct.pack('B', packet_type)
        
        assert len(header) == 5
        assert struct.unpack('>I', header[:4])[0] == length
        assert struct.unpack('B', header[4:5])[0] == packet_type
        
    def test_string_encoding(self):
        """Test string length-prefixed encoding"""
        import struct
        import io
        
        buf = io.BytesIO()
        test_string = "Hello World"
        
        # Write string
        data = test_string.encode('utf-8')
        buf.write(struct.pack('>I', len(data)))
        buf.write(data)
        
        # Read back
        buf.seek(0)
        length = struct.unpack('>I', buf.read(4))[0]
        read_data = buf.read(length)
        read_string = read_data.decode('utf-8')
        
        assert read_string == test_string
        

class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_flow(self):
        """Test complete flow"""
        # This is a simplified integration test
        # Real test would require actual network setup
        
        punch = BirthdayPunch()
        tunnel = TCPProxyTunnel()
        
        # Start components
        tunnel_port = await tunnel.start()
        assert tunnel_port > 0
        
        # Cleanup
        await tunnel.stop()
        punch.close()
        

# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
