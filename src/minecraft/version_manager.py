"""
Minecraft Version Manager
Minecraft 版本管理器

Parses version.json files and manages multi-version protocol support.
解析 version.json 文件并管理多版本协议支持。
"""

from __future__ import annotations
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class MCVersionInfo:
    """Minecraft version information"""
    id: str
    type: str  # release, snapshot, etc.
    release_time: str
    protocol_version: Optional[int] = None
    
    # Java version
    java_version: int = 8
    java_component: str = "jre-legacy"
    
    # Downloads
    client_url: str = ""
    client_sha1: str = ""
    client_size: int = 0
    server_url: str = ""
    server_sha1: str = ""
    server_size: int = 0
    
    # Mappings (for newer versions)
    client_mappings_url: str = ""
    server_mappings_url: str = ""
    
    # Assets
    asset_index: str = ""
    asset_index_url: str = ""
    
    # Main class
    main_class: str = "net.minecraft.client.main.Main"
    minecraft_arguments: str = ""
    
    # Libraries
    libraries: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'MCVersionInfo':
        """Parse from version.json"""
        downloads = data.get('downloads', {})
        client = downloads.get('client', {})
        server = downloads.get('server', {})
        
        # Get protocol version from asset index or infer from version
        protocol = None
        
        # Java version
        java_ver = data.get('javaVersion', {})
        
        # Mappings (1.14.4+)
        client_mappings = downloads.get('client_mappings', {})
        server_mappings = downloads.get('server_mappings', {})
        
        # Assets
        asset_index = data.get('assetIndex', {})
        
        # Arguments (1.13+)
        arguments = data.get('arguments', {})
        mc_args = data.get('minecraftArguments', '')
        
        return cls(
            id=data.get('id', 'unknown'),
            type=data.get('type', 'unknown'),
            release_time=data.get('releaseTime', ''),
            protocol_version=protocol,
            java_version=java_ver.get('majorVersion', 8),
            java_component=java_ver.get('component', 'jre-legacy'),
            client_url=client.get('url', ''),
            client_sha1=client.get('sha1', ''),
            client_size=client.get('size', 0),
            server_url=server.get('url', ''),
            server_sha1=server.get('sha1', ''),
            server_size=server.get('size', 0),
            client_mappings_url=client_mappings.get('url', ''),
            server_mappings_url=server_mappings.get('url', ''),
            asset_index=asset_index.get('id', ''),
            asset_index_url=asset_index.get('url', ''),
            main_class=data.get('mainClass', 'net.minecraft.client.main.Main'),
            minecraft_arguments=mc_args,
            libraries=data.get('libraries', [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'release_time': self.release_time,
            'protocol_version': self.protocol_version,
            'java_version': self.java_version,
            'client_url': self.client_url,
            'server_url': self.server_url,
            'asset_index': self.asset_index,
            'main_class': self.main_class
        }
    
    def is_modern(self) -> bool:
        """Check if version uses modern (1.13+) argument format"""
        return 'arguments' in self.to_dict() or self.id.startswith('1.1') or \
               self.id.startswith('1.2') and not self.id.startswith('1.2.')
    
    def has_mappings(self) -> bool:
        """Check if version has official mappings"""
        return bool(self.client_mappings_url)


class VersionManager:
    """
    Manages multiple Minecraft versions
    
    Loads and parses version.json files from the versions directory.
    """
    
    # Known protocol versions for common releases
    PROTOCOL_VERSIONS = {
        '1.12.2': 340,
        '1.16.5': 754,
        '1.17.1': 756,
        '1.18.2': 758,
        '1.19.2': 760,
        '1.19.4': 762,
        '1.20.1': 763,
        '1.20.2': 764,
        '1.20.4': 766,
    }
    
    def __init__(self, versions_dir: str):
        self.versions_dir = Path(versions_dir)
        self.versions: Dict[str, MCVersionInfo] = {}
        self._load_versions()
    
    def _load_versions(self):
        """Load all versions from directory"""
        if not self.versions_dir.exists():
            logger.warning(f"Versions directory not found: {self.versions_dir}")
            return
        
        for version_dir in self.versions_dir.iterdir():
            if version_dir.is_dir():
                json_file = version_dir / f"{version_dir.name}.json"
                if json_file.exists():
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        version_info = MCVersionInfo.from_json(data)
                        
                        # Infer protocol version if not set
                        if version_info.protocol_version is None:
                            version_info.protocol_version = self._infer_protocol(version_info.id)
                        
                        self.versions[version_info.id] = version_info
                        logger.debug(f"Loaded version: {version_info.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to load version {version_dir.name}: {e}")
    
    def _infer_protocol(self, version_id: str) -> Optional[int]:
        """Infer protocol version from version ID"""
        # Check exact match
        if version_id in self.PROTOCOL_VERSIONS:
            return self.PROTOCOL_VERSIONS[version_id]
        
        # Check base version (e.g., "1.16.5-Fabric" -> "1.16.5")
        for base_version, protocol in self.PROTOCOL_VERSIONS.items():
            if version_id.startswith(base_version):
                return protocol
        
        return None
    
    def get_version(self, version_id: str) -> Optional[MCVersionInfo]:
        """Get version info by ID"""
        return self.versions.get(version_id)
    
    def list_versions(self) -> List[str]:
        """List all available version IDs"""
        return list(self.versions.keys())
    
    def get_releases(self) -> List[MCVersionInfo]:
        """Get all release versions"""
        return [v for v in self.versions.values() if v.type == 'release']
    
    def get_protocol_version(self, version_id: str) -> Optional[int]:
        """Get protocol version for a version"""
        version = self.get_version(version_id)
        if version:
            return version.protocol_version
        return self._infer_protocol(version_id)
    
    def is_compatible(self, version1: str, version2: str) -> bool:
        """Check if two versions are protocol-compatible"""
        proto1 = self.get_protocol_version(version1)
        proto2 = self.get_protocol_version(version2)
        
        if proto1 is None or proto2 is None:
            return False
        
        return proto1 == proto2
    
    def get_compatible_versions(self, version_id: str) -> List[str]:
        """Get all versions compatible with given version"""
        target_proto = self.get_protocol_version(version_id)
        if target_proto is None:
            return []
        
        compatible = []
        for vid, version in self.versions.items():
            if version.protocol_version == target_proto:
                compatible.append(vid)
        
        return compatible
    
    def get_version_features(self, version_id: str) -> Dict[str, bool]:
        """Get feature flags for a version"""
        version = self.get_version(version_id)
        if not version:
            return {}
        
        # Parse version number
        try:
            parts = version.id.split('-')[0].split('.')
            major = int(parts[0]) if len(parts) > 0 else 1
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            major, minor, patch = 1, 0, 0
        
        return {
            'has_modern_args': version.is_modern(),
            'has_mappings': version.has_mappings(),
            'has_datafixer': minor >= 13,
            'has_brigadier': minor >= 13,
            'uses_jar_in_jar': minor >= 18,
            'is_flattened': minor >= 13,  # Flattened block IDs
            'has_data_components': minor >= 20 and patch >= 5,
        }
    
    def get_best_version_for_protocol(self, protocol: int) -> Optional[str]:
        """Get the best version string for a protocol number"""
        for version_id, proto in self.PROTOCOL_VERSIONS.items():
            if proto == protocol:
                return version_id
        return None


# Protocol packet definitions by version
class ProtocolDefinitions:
    """
    Minecraft protocol packet definitions
    
    Packet IDs vary by protocol version.
    """
    
    # Handshake packets (consistent across versions)
    HANDSHAKE = 0x00
    
    # Protocol 340 (1.12.2)
    PROTOCOL_340 = {
        'LOGIN_START': 0x00,
        'LOGIN_SUCCESS': 0x02,
        'JOIN_GAME': 0x23,
        'SPAWN_PLAYER': 0x05,
        'ENTITY_RELATIVE_MOVE': 0x25,
        'ENTITY_LOOK_AND_RELATIVE_MOVE': 0x26,
        'ENTITY_TELEPORT': 0x4C,
        'CHAT_MESSAGE_CB': 0x0F,
        'CHAT_MESSAGE_SB': 0x02,
        'PLAYER_POSITION': 0x0D,
        'PLAYER_POSITION_LOOK': 0x0E,
        'KEEP_ALIVE_CB': 0x1F,
        'KEEP_ALIVE_SB': 0x0B,
        'CHUNK_DATA': 0x20,
        'BLOCK_CHANGE': 0x0B,
    }
    
    # Protocol 754 (1.16.5)
    PROTOCOL_754 = {
        'LOGIN_START': 0x00,
        'LOGIN_SUCCESS': 0x02,
        'JOIN_GAME': 0x24,
        'SPAWN_PLAYER': 0x04,
        'ENTITY_RELATIVE_MOVE': 0x27,
        'ENTITY_LOOK_AND_RELATIVE_MOVE': 0x28,
        'ENTITY_TELEPORT': 0x56,
        'CHAT_MESSAGE_CB': 0x0E,
        'CHAT_MESSAGE_SB': 0x03,
        'PLAYER_POSITION': 0x11,
        'PLAYER_POSITION_ROTATION': 0x12,
        'KEEP_ALIVE_CB': 0x21,
        'KEEP_ALIVE_SB': 0x10,
        'CHUNK_DATA': 0x20,
        'BLOCK_CHANGE': 0x0B,
    }
    
    # Protocol 756+ (1.17+)
    PROTOCOL_756 = {
        'LOGIN_START': 0x00,
        'LOGIN_SUCCESS': 0x02,
        'JOIN_GAME': 0x24,
        'SPAWN_PLAYER': 0x04,
        'ENTITY_RELATIVE_MOVE': 0x27,
        'ENTITY_LOOK_AND_RELATIVE_MOVE': 0x28,
        'ENTITY_TELEPORT': 0x62,
        'CHAT_MESSAGE_CB': 0x0E,
        'CHAT_MESSAGE_SB': 0x03,
        'PLAYER_POSITION': 0x11,
        'PLAYER_POSITION_ROTATION': 0x12,
        'KEEP_ALIVE_CB': 0x21,
        'KEEP_ALIVE_SB': 0x0F,
        'CHUNK_DATA': 0x20,
        'BLOCK_CHANGE': 0x0B,
    }
    
    @classmethod
    def get_packets(cls, protocol: int) -> Dict[str, int]:
        """Get packet definitions for protocol version"""
        if protocol >= 756:
            return cls.PROTOCOL_756
        elif protocol >= 754:
            return cls.PROTOCOL_754
        elif protocol >= 340:
            return cls.PROTOCOL_340
        else:
            return cls.PROTOCOL_340  # Fallback


# Example usage
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        versions_dir = sys.argv[1]
    else:
        versions_dir = r"C:\Users\Sails\Documents\Workspace\NormalWorkplace\Coding\MCJEBooster\workspace(plzz-add-this-floder-to-gitignore)\.minecraft\versions"
    
    manager = VersionManager(versions_dir)
    
    print(f"Loaded {len(manager.versions)} versions:")
    for version_id in sorted(manager.list_versions())[:10]:
        version = manager.get_version(version_id)
        if version:
            proto = version.protocol_version or "unknown"
            print(f"  {version_id}: protocol={proto}, java={version.java_version}")
    
    # Test compatibility
    print("\nCompatible versions for 1.16.5:")
    compatible = manager.get_compatible_versions("1.16.5")
    for v in compatible[:5]:
        print(f"  {v}")
