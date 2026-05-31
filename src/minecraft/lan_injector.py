"""
Minecraft LAN Injector

拦截Minecraft原版"对局域网开放"功能，将其映射到P2P网络。
支持多人加入P2P主机的世界。

工作原理:
1. 拦截原版局域网广播（mDNS/UDP 4445）
2. 将本地世界信息广播到P2P网络
3. P2P节点"伪装"成LAN客户端连接
4. 双向数据转发

支持版本: 1.12.2 - 1.20.x
"""

from __future__ import annotations
import asyncio
import socket
import struct
import json
import logging
from typing import Optional, Dict, List, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .tcp_bridge import TCPBridge, TCPBridgeServer

logger = logging.getLogger(__name__)


class MinecraftVersion(Enum):
    """支持的Minecraft版本"""
    V1_12_2 = "1.12.2"
    V1_16_5 = "1.16.5"
    V1_18_2 = "1.18.2"
    V1_20_1 = "1.20.1"
    V1_20_4 = "1.20.4"


@dataclass
class LANWorldInfo:
    """
    局域网世界信息
    
    对应Minecraft的LanServerInfo
    """
    motd: str  # 世界名称
    address: str  # 主机:端口
    player_count: int = 0
    max_players: int = 8
    game_version: str = "1.20.1"
    
    # P2P特有字段
    host_node_id: Optional[str] = None
    p2p_address: Optional[str] = None
    latency_ms: int = 0


@dataclass
class LANConfig:
    """
    局域网注入配置
    
    Attributes:
        listen_port: 监听端口（拦截原版广播）
        mc_version: 目标Minecraft版本
        motd_prefix: MOTD前缀（识别为P2P世界）
        enable_offline: 是否支持离线模式
        require_auth: 是否需要P2P密钥认证
    """
    listen_port: int = 4445  # Minecraft默认LAN端口
    mc_version: str = "1.20.1"
    motd_prefix: str = "[P2P] "
    enable_offline: bool = True
    require_auth: bool = True
    max_players: int = 8
    
    # P2P网络配置
    broadcast_interval: float = 3.0  # 广播间隔（秒）
    world_timeout: float = 30.0  # 世界过期时间


class LANInjector:
    """
    Minecraft局域网注入器
    
    核心功能：将Minecraft本地世界通过P2P网络共享
    
    工作流程:
    ```
    [Minecraft主机] --本地连接--> [LANInjector] --P2P广播--> [P2P网络]
                                            |
    [Minecraft客户端] <--拦截广播-- [世界列表] <--P2P发现--
    ```
    
    使用示例:
    ```python
    config = LANConfig(enable_offline=True)
    injector = LANInjector(config, hybrid_connector)
    
    # 主机端：开启世界
    await injector.host_world(local_port=25565, world_name="My
...[omitted 15024 bytes sha1=b8e3c9a273dc field=tool_result_content]