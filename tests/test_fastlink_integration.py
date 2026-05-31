"""
Integration tests for FastLink integration
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.fastlink.version_manager import FastLinkVersionManager, VersionInfo, VersionConstraint, VersionType
from src.fastlink.compatibility import CompatibilityChecker, InterfaceVersion
from src.fastlink.bridge import FastLinkBridge, BridgeConfig, BridgeMode


class TestVersionManager:
    """Test FastLink version manager"""
    
    def test_version_info_creation(self):
        """Test version info creation"""
        vinfo = VersionInfo("26.1-20260523", VersionType.STABLE)
        assert vinfo.version == "26.1-20260523"
        assert vinfo.version_type == VersionType.STABLE
    
    def test_version_comparison(self):
        """Test version comparison"""
        v1 = VersionInfo("26.1-20260523")
        v2 = VersionInfo("26.2-20260525")
        
        assert v1._compare_version("26.2-20260525") == -1
        assert v2._compare_version("26.1-20260523") == 1
        assert v1._compare_version("26.1-20260523") == 0
    
    def test_version_constraint_parse(self):
        """Test version constraint parsing"""
        c = VersionConstraint.parse(">=26.1")
        assert c.min_version == "26.1"
        
        c = VersionConstraint.parse("~26.1")
        assert c.min_version == "26.1"
        assert c.max_version == "27.0"
        
        c = VersionConstraint.parse("26.1")
        assert c.exact == "26.1"


class TestCompatibility:
    """Test compatibility checker"""
    
    @pytest.mark.asyncio
    async def test_compatibility_check(self):
        """Test basic compatibility check"""
        checker = CompatibilityChecker()
        # Should work with mock or when FastLink not found
        report = await checker.check_compatibility()
        
        assert hasattr(report, 'is_compatible')
        assert hasattr(report, 'errors')
        assert hasattr(report, 'fastlink_version')
    
    def test_interface_version(self):
        """Test interface version"""
        assert InterfaceVersion.CURRENT == "1.0"
        assert "1.0" in InterfaceVersion.HISTORY
        
        features = InterfaceVersion.get_features("1.0")
        assert "p2p_connect" in features


class TestBridge:
    """Test FastLink bridge"""
    
    def test_bridge_config_creation(self):
        """Test bridge config creation"""
        config = BridgeConfig(
            mode=BridgeMode.SUBPROCESS,
            tcp_port=9090
        )
        assert config.mode == BridgeMode.SUBPROCESS
        assert config.tcp_port == 9090
    
    def test_bridge_initialization(self):
        """Test bridge initialization"""
        config = BridgeConfig(mode=BridgeMode.SUBPROCESS)
        bridge = FastLinkBridge(config)
        
        # Should initialize without errors (even without FastLink)
        assert bridge.config == config


class TestTCPBridge:
    """Test TCP bridge"""
    
    def test_tcp_packet_encode_decode(self):
        """Test TCP packet encoding and decoding"""
        from src.minecraft.tcp_bridge import TCPPacket
        
        packet = TCPPacket(
            connection_id="test_conn",
            sequence=123,
            data=b"Hello, World!",
            flags=TCPPacket.FLAG_DATA
        )
        
        encoded = packet.encode()
        decoded = TCPPacket.decode(encoded)
        
        assert decoded.connection_id == "test_conn"
        assert decoded.sequence == 123
        assert decoded.data == b"Hello, World!"
        assert decoded.flags == TCPPacket.FLAG_DATA
