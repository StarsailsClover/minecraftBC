"""
Tests for Minecraft protocol adapter
"""

import pytest
from src.minecraft.protocol_adapter import (
    MinecraftProtocolAdapter,
    ProtocolVersion,
    create_adapter
)


class TestProtocolAdapter:
    """Test protocol adapter"""
    
    def test_create_adapter(self):
        """Test adapter creation"""
        adapter = create_adapter("1.20.1")
        assert adapter.version == ProtocolVersion.V1_20_1
    
    def test_varint_encoding(self):
        """Test varint encoding/decoding"""
        adapter = create_adapter("1.20.1")
        
        # Test encoding
        encoded = adapter.encode_varint(127)
        assert encoded == b'\x7f'
        
        encoded = adapter.encode_varint(255)
        assert encoded == b'\xff\x01'
        
        # Test decoding
        value, offset = adapter.decode_varint(b'\x7f')
        assert value == 127
        assert offset == 1
    
    def test_string_encoding(self):
        """Test string encoding/decoding"""
        adapter = create_adapter("1.20.1")
        
        test_str = "Hello"
        encoded = adapter.encode_string(test_str)
        
        # Format: [length varint] [utf-8 bytes]
        assert encoded[0] == 5  # length
        assert encoded[1:] == b"Hello"
    
    def test_get_packet_id(self):
        """Test packet ID retrieval"""
        adapter = create_adapter("1.20.1")
        
        # Check handshake packet exists
        packet_id = adapter.get_packet_id('handshake')
        assert packet_id is not None
        assert packet_id == 0x00
    
    def test_create_handshake_packet(self):
        """Test handshake packet creation"""
        adapter = create_adapter("1.20.1")
        
        packet = adapter.create_handshake_packet(
            protocol_version=763,  # 1.20.1
            server_address="localhost",
            server_port=25565,
            next_state=2  # login
        )
        
        assert isinstance(packet, bytes)
        assert len(packet) > 0
        
        # First byte should be length
        assert packet[0] == len(packet) - 1
    
    def test_supported_versions(self):
        """Test supported versions list"""
        adapter = create_adapter("1.20.1")
        versions = adapter.get_supported_versions()
        
        assert "1.12.2" in versions
        assert "1.20.1" in versions
        assert len(versions) >= 5
