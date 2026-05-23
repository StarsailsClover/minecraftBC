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
    [Minecraft主机] --本地连接--> [LANInjector] --P2P--> [P2P节点]
                                            |
    [Minecraft客户端] <--拦截广播-- [世界列表] <--P2P发现--
    ```
    
    使用示例:
    ```python
    config = LANConfig(enable_offline=True)
    injector = LANInjector(config, hybrid_connector)
    
    # 主机端：开启世界
    await injector.host_world(local_port=25565, world_name="My World")
    
    # 客户端：发现世界
    worlds = injector.discover_worlds()
    for world in worlds:
        print(f"Found: {world.motd} at {world.p2p_address}")
    ```
    """
    
    def __init__(self, config: LANConfig, connector):
        """
        初始化LAN注入器
        
        Args:
            config: 局域网配置
            connector: P2P连接器（HybridConnector）
        """
        self.config = config
        self.connector = connector
        
        # 状态
        self._hosting_world: bool = False
        self._local_mc_port: Optional[int] = None
        self._world_name: Optional[str] = None
        
        # 发现的世界
        self._discovered_worlds: Dict[str, LANWorldInfo] = {}
        
        # 连接映射 (peer_id -> local_port)
        self._peer_connections: Dict[str, int] = {}
        
        # UDP socket（用于拦截广播）
        self._udp_socket: Optional[socket.socket] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        
        # 回调
        self._on_world_discovered: Optional[Callable[[LANWorldInfo], None]] = None
        self._on_player_joined: Optional[Callable[[str], None]] = None
        self._on_player_left: Optional[Callable[[str], None]] = None
    
    def on_world_discovered(self, callback: Callable[[LANWorldInfo], None]) -> 'LANInjector':
        """注册世界发现回调"""
        self._on_world_discovered = callback
        return self
    
    def on_player_joined(self, callback: Callable[[str], None]) -> 'LANInjector':
        """注册玩家加入回调"""
        self._on_player_joined = callback
        return self
    
    def on_player_left(self, callback: Callable[[str], None]) -> 'LANInjector':
        """注册玩家离开回调"""
        self._on_player_left = callback
        return self
    
    async def start(self) -> bool:
        """
        启动LAN注入器
        
        开始监听P2P世界广播
        
        Returns:
            启动成功返回True
        """
        try:
            logger.info("Starting LAN injector...")
            
            # 创建UDP socket监听广播
            self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._udp_socket.bind(('0.0.0.0', self.config.listen_port))
            self._udp_socket.setblocking(False)
            
            # 启动监听任务
            self._listen_task = asyncio.create_task(self._listen_for_broadcasts())
            
            # 设置P2P消息处理器
            self.connector.on_message(self._on_p2p_message)
            self.connector.on_connect(self._on_p2p_connect)
            self.connector.on_disconnect(self._on_p2p_disconnect)
            
            logger.info("LAN injector started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start LAN injector: {e}")
            return False
    
    async def stop(self) -> None:
        """停止LAN注入器"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self._udp_socket:
            self._udp_socket.close()
        
        self._hosting_world = False
        logger.info("LAN injector stopped")
    
    async def host_world(self, local_port: int, world_name: str,
                         game_mode: str = "survival") -> bool:
        """
        开始托管世界
        
        将本地Minecraft世界广播到P2P网络
        
        Args:
            local_port: 本地Minecraft服务器端口
            world_name: 世界名称（显示给客户端）
            game_mode: 游戏模式
        
        Returns:
            成功返回True
        """
        if self._hosting_world:
            logger.warning("Already hosting a world")
            return False
        
        self._local_mc_port = local_port
        self._world_name = world_name
        self._hosting_world = True
        
        logger.info(f"Hosting world '{world_name}' on port {local_port}")
        
        # 启动广播任务
        self._broadcast_task = asyncio.create_task(
            self._broadcast_world_info()
        )
        
        return True
    
    async def stop_hosting(self) -> None:
        """停止托管世界"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
        
        self._hosting_world = False
        self._local_mc_port = None
        self._world_name = None
        
        logger.info("Stopped hosting world")
    
    async def _broadcast_world_info(self) -> None:
        """
        定期广播世界信息到P2P网络
        """
        while self._hosting_world:
            try:
                # 构建世界信息
                world_info = {
                    'protocol': 'minecraft-lan',
                    'type': 'world_broadcast',
                    'motd': f"{self.config.motd_prefix}{self._world_name}",
                    'host': self.connector.node_id,
                    'port': self._local_mc_port,
                    'version': self.config.mc_version,
                    'players': 0,  # TODO: 获取真实玩家数
                    'max_players': self.config.max_players,
                    'timestamp': datetime.now().isoformat()
                }
                
                # 广播到P2P网络
                data = json.dumps(world_info).encode()
                await self.connector.broadcast(data)
                
                logger.debug(f"Broadcasted world info: {world_info['motd']}")
                
            except Exception as e:
                logger.error(f"Error broadcasting world info: {e}")
            
            await asyncio.sleep(self.config.broadcast_interval)
    
    async def _listen_for_broadcasts(self) -> None:
        """
        监听Minecraft原版局域网广播
        
        监听UDP 4445端口，拦截原版广播并转发到P2P
        """
        logger.info(f"Listening for Minecraft LAN broadcasts on port {self.config.listen_port}")
        
        while True:
            try:
                data, addr = await asyncio.get_event_loop().sock_recvfrom(
                    self._udp_socket, 1500
                )
                
                # 解析Minecraft广播
                await self._handle_mc_broadcast(data, addr)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast listener: {e}")
                await asyncio.sleep(1)
    
    async def _handle_mc_broadcast(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        处理Minecraft广播消息
        
        格式:
        [1 byte: 0xFE] [1 byte: 0xFD] [MOTD] [0x00] [Address] [0x00]
        """
        try:
            # 解析Minecraft LAN广播
            if len(data) < 3:
                return
            
            # 检查Minecraft广播签名
            if data[0] == 0xFE and data[1] == 0xFD:
                # 这是Minecraft广播
                motd_start = 2
                
                # 找到MOTD结束（0x00）
                motd_end = data.find(0x00, motd_start)
                if motd_end == -1:
                    return
                
                motd = data[motd_start:motd_end].decode('utf-8', errors='ignore')
                
                # 找到地址
                addr_start = motd_end + 1
                addr_end = data.find(0x00, addr_start)
                if addr_end == -1:
                    return
                
                address = data[addr_start:addr_end].decode('utf-8', errors='ignore')
                
                logger.debug(f"Detected Minecraft LAN broadcast: {motd} at {address}")
                
                # 如果我们在托管世界，忽略自己的广播
                if self._hosting_world and motd == self._world_name:
                    return
                
                # 转发到P2P（如果是本地世界）
                await self._relay_to_p2p(motd, address)
                
        except Exception as e:
            logger.debug(f"Failed to parse broadcast: {e}")
    
    async def _relay_to_p2p(self, motd: str, address: str) -> None:
        """将本地世界信息中继到P2P网络"""
        # 只有当我们是主机时才需要这个
        if not self._hosting_world:
            return
        
        # 构建P2P广播
        world_info = {
            'protocol': 'minecraft-lan',
            'type': 'local_relay',
            'motd': motd,
            'local_address': address,
            'version': self.config.mc_version,
            'timestamp': datetime.now().isoformat()
        }
        
        data = json.dumps(world_info).encode()
        await self.connector.broadcast(data)
    
    def _on_p2p_message(self, peer_id: str, data: bytes, addr: str) -> None:
        """处理P2P消息"""
        try:
            message = json.loads(data.decode())
            
            if message.get('protocol') != 'minecraft-lan':
                return
            
            msg_type = message.get('type')
            
            if msg_type == 'world_broadcast':
                # 收到世界广播
                self._handle_world_broadcast(peer_id, message)
            elif msg_type == 'join_request':
                # 收到加入请求
                asyncio.create_task(self._handle_join_request(peer_id, message))
            elif msg_type == 'player_list':
                # 收到玩家列表更新
                self._handle_player_list(peer_id, message)
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling P2P message: {e}")
    
    def _handle_world_broadcast(self, peer_id: str, message: dict) -> None:
        """处理世界广播"""
        world_info = LANWorldInfo(
            motd=message.get('motd', 'Unknown'),
            address=f"{peer_id}:{message.get('port')}",
            player_count=message.get('players', 0),
            max_players=message.get('max_players', 8),
            game_version=message.get('version', 'unknown'),
            host_node_id=peer_id,
            p2p_address=f"p2p://{peer_id}/{message.get('port')}",
            latency_ms=0  # TODO: 测量延迟
        )
        
        self._discovered_worlds[peer_id] = world_info
        
        if self._on_world_discovered:
            try:
                self._on_world_discovered(world_info)
            except Exception as e:
                logger.error(f"World discovered callback error: {e}")
        
        logger.info(f"Discovered P2P world: {world_info.motd} from {peer_id}")
    
    async def _handle_join_request(self, peer_id: str, message: dict) -> None:
        """处理玩家加入请求"""
        if not self._hosting_world:
            # 转发给主机
            return
        
        # 主机处理加入请求
        logger.info(f"Player {peer_id} requesting to join")
        
        # 建立TCP代理连接
        # TODO: 实现TCP端口转发
        
        # 通知
        if self._on_player_joined:
            self._on_player_joined(peer_id)
    
    def _handle_player_list(self, peer_id: str, message: dict) -> None:
        """处理玩家列表更新"""
        if peer_id in self._discovered_worlds:
            self._discovered_worlds[peer_id].player_count = message.get('count', 0)
    
    def _on_p2p_connect(self, peer_id: str) -> None:
        """P2P连接建立"""
        logger.debug(f"P2P connected: {peer_id}")
    
    def _on_p2p_disconnect(self, peer_id: str) -> None:
        """P2P连接断开"""
        # 移除相关世界
        if peer_id in self._discovered_worlds:
            del self._discovered_worlds[peer_id]
        
        if self._on_player_left:
            self._on_player_left(peer_id)
    
    def discover_worlds(self) -> List[LANWorldInfo]:
        """
        获取发现的所有P2P世界
        
        Returns:
            世界信息列表
        """
        # 清理过期世界
        current_time = datetime.now()
        expired = []
        for peer_id, world in self._discovered_worlds.items():
            # TODO: 实现过期检查
            pass
        
        return list(self._discovered_worlds.values())
    
    async def connect_to_world(self, peer_id: str) -> bool:
        """
        连接到P2P世界
        
        Args:
            peer_id: 主机节点ID
        
        Returns:
            连接成功返回True
        """
        if peer_id not in self._discovered_worlds:
            logger.error(f"Unknown world: {peer_id}")
            return False
        
        world = self._discovered_worlds[peer_id]
        
        # 发送加入请求
        join_request = {
            'protocol': 'minecraft-lan',
            'type': 'join_request',
            'player_name': 'Player',  # TODO: 获取真实玩家名
            'timestamp': datetime.now().isoformat()
        }
        
        data = json.dumps(join_request).encode()
        success = await self.connector.send_to_peer(peer_id, data)
        
        if success:
            logger.info(f"Sent join request to {world.motd}")
        
        return success
    
    def is_hosting(self) -> bool:
        """是否正在托管世界"""
        return self._hosting_world
    
    def get_hosted_world_info(self) -> Optional[LANWorldInfo]:
        """获取当前托管的世界信息"""
        if not self._hosting_world:
            return None
        
        return LANWorldInfo(
            motd=f"{self.config.motd_prefix}{self._world_name}",
            address=f"0.0.0.0:{self._local_mc_port}",
            host_node_id=self.connector.node_id,
            p2p_address=f"p2p://{self.connector.node_id}/{self._local_mc_port}",
            game_version=self.config.mc_version
        )
