"""
Settings Definition

定义minecraftBC的所有配置项。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class P2PSettings:
    """P2P连接设置"""
    
    # 本地监听
    bind_host: str = "0.0.0.0"
    bind_port: int = 0  # 0 = 随机端口
    
    # 协议偏好
    prefer_fastlink: bool = True
    fallback_timeout: float = 10.0
    
    # NAT穿透
    enable_nat_traversal: bool = True
    nat_discovery_timeout: float = 5.0
    
    # STUN服务器（WebRTC使用）
    stun_servers: List[str] = field(default_factory=lambda: [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302"
    ])
    
    # TURN服务器（可选）
    turn_servers: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ServerSettings:
    """轻服务器设置"""
    
    enable_server: bool = False
    server_port: int = 25565
    max_rooms: int = 10
    max_players_per_room: int = 8
    default_room_visibility: str = "public"  # public, private, friends


@dataclass
class MinecraftSettings:
    """Minecraft集成设置"""
    
    # 版本
    mc_version: str = "1.20.1"
    
    # LAN注入
    enable_lan_injector: bool = True
    lan_listen_port: int = 4445
    motd_prefix: str = "[P2P] "
    
    # 离线模式
    enable_offline: bool = True
    require_p2p_auth: bool = True
    
    # 广播
    broadcast_interval: float = 3.0
    world_timeout: float = 30.0


@dataclass
class MnMCPSettings:
    """MnMCP跨游戏设置"""
    
    enable_mnmcp: bool = False
    adapter_configs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecuritySettings:
    """安全设置"""
    
    # 密钥存储
    key_file: str = "~/.minecraftBC/node.key"
    encrypt_key_file: bool = False
    
    # DTLS设置
    enable_encryption: bool = True
    dtls_handshake_timeout: float = 5.0
    
    # 认证
    require_mutual_auth: bool = True


@dataclass
class LoggingSettings:
    """日志设置"""
    
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    file: Optional[str] = None
    max_size_mb: int = 100
    backup_count: int = 5
    
    # 控制台输出
    console_output: bool = True
    colorize: bool = True


@dataclass
class MinecraftBCSettings:
    """
    minecraftBC完整设置
    
    所有配置项的聚合。
    """
    
    # 节点信息
    node_name: str = "minecraftBC Node"
    node_id: Optional[str] = None  # 自动从密钥派生
    
    # 各模块设置
    p2p: P2PSettings = field(default_factory=P2PSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    minecraft: MinecraftSettings = field(default_factory=MinecraftSettings)
    mnmcp: MnMCPSettings = field(default_factory=MnMCPSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    
    # 调试
    debug_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MinecraftBCSettings':
        """从字典创建"""
        # 简化实现
        settings = cls()
        
        if 'node_name' in data:
            settings.node_name = data['node_name']
        if 'node_id' in data:
            settings.node_id = data['node_id']
        if 'debug_mode' in data:
            settings.debug_mode = data['debug_mode']
        
        # P2P设置
        if 'p2p' in data:
            p2p_data = data['p2p']
            settings.p2p = P2PSettings(
                bind_host=p2p_data.get('bind_host', '0.0.0.0'),
                bind_port=p2p_data.get('bind_port', 0),
                prefer_fastlink=p2p_data.get('prefer_fastlink', True),
                fallback_timeout=p2p_data.get('fallback_timeout', 10.0),
                enable_nat_traversal=p2p_data.get('enable_nat_traversal', True),
                stun_servers=p2p_data.get('stun_servers', [
                    "stun:stun.l.google.com:19302"
                ]),
                turn_servers=p2p_data.get('turn_servers', [])
            )
        
        # Minecraft设置
        if 'minecraft' in data:
            mc_data = data['minecraft']
            settings.minecraft = MinecraftSettings(
                mc_version=mc_data.get('mc_version', '1.20.1'),
                enable_lan_injector=mc_data.get('enable_lan_injector', True),
                motd_prefix=mc_data.get('motd_prefix', '[P2P] '),
                enable_offline=mc_data.get('enable_offline', True),
                broadcast_interval=mc_data.get('broadcast_interval', 3.0)
            )
        
        # 安全设置
        if 'security' in data:
            sec_data = data['security']
            settings.security = SecuritySettings(
                key_file=sec_data.get('key_file', '~/.minecraftBC/node.key'),
                enable_encryption=sec_data.get('enable_encryption', True)
            )
        
        return settings
    
    def get_node_identity_path(self) -> str:
        """获取节点身份文件路径"""
        import os
        return os.path.expanduser(self.security.key_file)
