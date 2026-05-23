"""
FastLink加密模块

提供Ed25519密钥生成和X25519密钥交换
"""

from __future__ import annotations
import base64
import os
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_node_keypair() -> Tuple[str, str]:
    """
    生成节点密钥对 (Ed25519)
    
    Returns:
        (public_key_hex, private_key_hex) 十六进制字符串
    """
    # 生成Ed25519签名密钥对
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # 序列化
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    # 返回十六进制字符串
    return public_bytes.hex(), private_bytes.hex()


def generate_x25519_keypair() -> Tuple[bytes, bytes]:
    """
    生成X25519密钥对 (用于密钥交换)
    
    Returns:
        (public_key_bytes, private_key_bytes)
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return public_bytes, private_bytes


def sign_message(private_key_hex: str, message: bytes) -> bytes:
    """
    使用Ed25519签名消息
    
    Args:
        private_key_hex: 私钥十六进制字符串
        message: 要签名的消息
    
    Returns:
        签名(64字节)
    """
    private_bytes = bytes.fromhex(private_key_hex)
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    return private_key.sign(message)


def verify_signature(public_key_hex: str, message: bytes, signature: bytes) -> bool:
    """
    验证Ed25519签名
    
    Args:
        public_key_hex: 公钥十六进制字符串
        message: 原始消息
        signature: 签名
    
    Returns:
        验证成功返回True
    """
    try:
        public_bytes = bytes.fromhex(public_key_hex)
        public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
        public_key.verify(signature, message)
        return True
    except Exception:
        return False


def perform_key_exchange(private_key_bytes: bytes, peer_public_key_bytes: bytes) -> bytes:
    """
    执行X25519密钥交换
    
    Args:
        private_key_bytes: 本地私钥
        peer_public_key_bytes: 对端公钥
    
    Returns:
        共享密钥(32字节)
    """
    private_key = X25519PrivateKey.from_private_bytes(private_key_bytes)
    peer_public_key = X25519PublicKey.from_public_bytes(peer_public_key_bytes)
    
    shared_key = private_key.exchange(peer_public_key)
    return shared_key


def get_node_id_from_pubkey(public_key_hex: str) -> str:
    """
    从公钥派生节点ID
    
    使用公钥的前16字节作为节点ID
    
    Args:
        public_key_hex: 公钥十六进制字符串
    
    Returns:
        节点ID (32字符十六进制)
    """
    import hashlib
    
    public_bytes = bytes.fromhex(public_key_hex)
    # 使用BLAKE2b或SHA3-256生成节点ID
    node_id = hashlib.sha3_256(public_bytes).hexdigest()[:32]
    return node_id


class NodeIdentity:
    """
    节点身份管理器
    
    管理节点的公私钥，支持持久化存储
    """
    
    def __init__(self, key_file: Optional[str] = None):
        self.key_file = key_file
        self._private_key: Optional[str] = None
        self._public_key: Optional[str] = None
        self._node_id: Optional[str] = None
    
    def generate(self) -> 'NodeIdentity':
        """生成新密钥对"""
        self._public_key, self._private_key = generate_node_keypair()
        self._node_id = get_node_id_from_pubkey(self._public_key)
        return self
    
    def load(self) -> 'NodeIdentity':
        """从文件加载密钥"""
        if self.key_file and os.path.exists(self.key_file):
            with open(self.key_file, 'r') as f:
                data = json.load(f)
                self._private_key = data['private_key']
                self._public_key = data['public_key']
                self._node_id = data.get('node_id') or get_node_id_from_pubkey(self._public_key)
        else:
            # 生成新密钥
            self.generate()
            self.save()
        return self
    
    def save(self) -> None:
        """保存密钥到文件"""
        if self.key_file:
            os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
            with open(self.key_file, 'w') as f:
                json.dump({
                    'private_key': self._private_key,
                    'public_key': self._public_key,
                    'node_id': self._node_id
                }, f)
    
    @property
    def public_key(self) -> str:
        """获取公钥"""
        return self._public_key or ""
    
    @property
    def private_key(self) -> str:
        """获取私钥"""
        return self._private_key or ""
    
    @property
    def node_id(self) -> str:
        """获取节点ID"""
        return self._node_id or ""
    
    def sign(self, message: bytes) -> bytes:
        """签名消息"""
        return sign_message(self._private_key, message)
    
    def verify(self, message: bytes, signature: bytes) -> bool:
        """验证签名"""
        return verify_signature(self._public_key, message, signature)


# JSON支持
import json


def generate_node_id_with_key() -> Tuple[str, str, str]:
    """
    生成节点ID和密钥对
    
    Returns:
        (node_id, public_key, private_key)
    """
    public_key, private_key = generate_node_keypair()
    node_id = get_node_id_from_pubkey(public_key)
    return node_id, public_key, private_key
