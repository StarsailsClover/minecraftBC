"""
Tests for crypto module
"""

import pytest
from src.protocol.fastlink.crypto import (
    generate_node_keypair,
    sign_message,
    verify_signature,
    get_node_id_from_pubkey,
    NodeIdentity
)


class TestCrypto:
    """Test cryptographic functions"""
    
    def test_generate_keypair(self):
        """Test key pair generation"""
        public_key, private_key = generate_node_keypair()
        
        assert isinstance(public_key, str)
        assert isinstance(private_key, str)
        assert len(public_key) == 64  # 32 bytes hex
        assert len(private_key) == 64
    
    def test_sign_and_verify(self):
        """Test signing and verification"""
        public_key, private_key = generate_node_keypair()
        message = b"Hello, World!"
        
        # Sign
        signature = sign_message(private_key, message)
        assert isinstance(signature, bytes)
        assert len(signature) == 64  # Ed25519 signature is 64 bytes
        
        # Verify
        result = verify_signature(public_key, message, signature)
        assert result is True
    
    def test_verify_wrong_signature(self):
        """Test verification with wrong signature"""
        public_key, _ = generate_node_keypair()
        message = b"Hello, World!"
        wrong_signature = b"\x00" * 64
        
        result = verify_signature(public_key, message, wrong_signature)
        assert result is False
    
    def test_node_id_generation(self):
        """Test node ID generation from public key"""
        public_key, _ = generate_node_keypair()
        node_id = get_node_id_from_pubkey(public_key)
        
        assert isinstance(node_id, str)
        assert len(node_id) == 32  # 16 bytes hex
    
    def test_node_identity(self):
        """Test NodeIdentity class"""
        identity = NodeIdentity(key_file=None)
        identity.generate()
        
        assert identity.node_id is not None
        assert identity.public_key is not None
        assert identity.private_key is not None
        assert len(identity.public_key) == 64
    
    def test_sign_verify_flow(self):
        """Test complete sign/verify flow"""
        identity = NodeIdentity(key_file=None)
        identity.generate()
        
        message = b"Test message for signing"
        signature = identity.sign(message)
        
        assert isinstance(signature, bytes)
        assert len(signature) == 64
        
        # Verify with same identity
        result = identity.verify(message, signature)
        assert result is True
        
        # Verify with tampered message
        tampered = b"Tampered message"
        result = identity.verify(tampered, signature)
        assert result is False
