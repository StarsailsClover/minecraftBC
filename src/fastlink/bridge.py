"""
FastLink Bridge

Python与FastLink Rust库之间的桥接层。
提供统一的接口，支持多种连接方式。
"""

from __future__ import annotations
import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, Tuple
import hashlib

logger = logging.getLogger(__name__)


class BridgeMode(Enum):
    """桥接模式"""
    
    # 通过subprocess调用CLI (当前可行)
    SUBPROCESS = "subprocess"
    
    # 通过TCP连接到FastLink守护进程 (未来)
    TCP = "tcp"
    
    # 通过HTTP API (未来)
    HTTP = "http"
    
    # 通过PyO3直接调用 (未来，需要FastLink添加绑定)
    PYO3 = "pyo3"


@dataclass
class BridgeConfig:
    """桥接配置"""
    
    mode: BridgeMode = BridgeMode.SUBPROCESS
    
    # FastLink仓库路径
    fastlink_path: Optional[Path] = None
    
    # CLI路径 (subprocess模式)
    cli_binary: Optional[Path] = None
    
    # TCP配置 (TCP模式)
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 8080
    
    # HTTP配置 (HTTP模式)
    http_url: str = "http://127.0.0.1:8080"
    http_api_key: Optional[str] = None
    
    # 连接设置
    connection_timeout: float = 10.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # 日志
    log_fastlink_output: bool = False
    
    def __post_init__(self):
        if self.fastlink_path is None:
            # 默认路径
            self.fastlink_path = Path(__file__).parent.parent.parent.parent / "FastLink"
        
        if self.cli_binary is None:
            # 默认CLI路径
            self.cli_binary = self.fastlink_path / "target" / "release" / "fastlink.exe"


@dataclass
class P2PConnectionInfo:
    """P2P连接信息"""
    node_id: str
    peer_id: str
    address: Tuple[str, int]
    state: str
    latency_ms: float
    established_at: datetime
    
    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id,
            'peer_id': self.peer_id,
            'address': f"{self.address[0]}:{self.address[1]}",
            'state': self.state,
            'latency_ms': self.latency_ms,
            'established_at': self.established_at.isoformat(),
        }


class FastLinkBridge:
    """
    FastLink桥接器
    
    提供Python与FastLink之间的统一接口。
    当前使用subprocess调用CLI，未来支持TCP/HTTP/PyO3。
    
    使用示例:
    ```python
    config = BridgeConfig()
    bridge = FastLinkBridge(config)
    await bridge.initialize()
    
    # 启动P2P节点
    await bridge.start_p2p_node("0.0.0.0:8080")
    
    # 连接到对等节点
    conn = await bridge.connect_to_peer("node_id_here", ("host", port))
    ```
    """
    
    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig()
        self._process: Optional[subprocess.Popen] = None
        self._node_id: Optional[str] = None
        self._connections: Dict[str, P2PConnectionInfo] = {}
        self._running = False
        
        # 回调
        self._message_callbacks: List[Callable] = []
        self._connect_callbacks: List[Callable] = []
        self._disconnect_callbacks: List[Callable] = []
    
    async def initialize(self) -> bool:
        """
        初始化桥接器
        
        Returns:
            初始化成功返回True
        """
        logger.info(f"Initializing FastLink bridge in {self.config.mode.value} mode...")
        
        if self.config.mode == BridgeMode.SUBPROCESS:
            return await self._init_subprocess()
        
        elif self.config.mode == BridgeMode.TCP:
            return await self._init_tcp()
        
        elif self.config.mode == BridgeMode.HTTP:
            return await self._init_http()
        
        else:
            logger.error(f"Unsupported bridge mode: {self.config.mode}")
            return False
    
    async def _init_subprocess(self) -> bool:
        """初始化subprocess模式"""
        # 检查FastLink二进制是否存在
        if not self.config.cli_binary or not self.config.cli_binary.exists():
            logger.warning(f"FastLink CLI not found at {self.config.cli_binary}")
            logger.info("Will use Python fallback implementation")
            return True  # 允许回退
        
        logger.info(f"FastLink CLI found at {self.config.cli_binary}")
        return True
    
    async def _init_tcp(self) -> bool:
        """初始化TCP模式"""
        try:
            # 尝试连接到FastLink守护进程
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.tcp_host, self.config.tcp_port),
                timeout=self.config.connection_timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            logger.warning(f"TCP connection failed: {e}")
            return False
    
    async def _init_http(self) -> bool:
        """初始化HTTP模式"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.config.http_url}/health",
                    timeout=aiohttp.ClientTimeout(total=self.config.connection_timeout)
                ) as resp:
                    return resp.status == 200
        except ImportError:
            logger.warning("aiohttp not installed, HTTP mode unavailable")
            return False
        except Exception as e:
            logger.warning(f"HTTP connection failed: {e}")
            return False
    
    async def start_p2p_node(self, bind_addr: str) -> bool:
        """
        启动P2P节点
        
        Args:
            bind_addr: 绑定地址 (如 "0.0.0.0:8080")
        
        Returns:
            启动成功返回True
        """
        if self.config.mode == BridgeMode.SUBPROCESS:
            return await self._start_p2p_subprocess(bind_addr)
        else:
            logger.error(f"start_p2p_node not implemented for mode {self.config.mode}")
            return False
    
    async def _start_p2p_subprocess(self, bind_addr: str) -> bool:
        """通过subprocess启动P2P节点"""
        try:
            cmd = [
                str(self.config.cli_binary),
                "start",
                "--bind", bind_addr
            ]
            
            logger.info(f"Starting FastLink node: {' '.join(cmd)}")
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if not self.config.log_fastlink_output else None,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=str(self.config.fastlink_path)
            )
            
            # 等待启动
            await asyncio.sleep(2)
            
            # 检查进程状态
            if self._process.poll() is not None:
                stdout, stderr = self._process.communicate()
                logger.error(f"FastLink process exited: {stderr.decode()}")
                return False
            
            self._running = True
            logger.info("FastLink node started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start FastLink node: {e}")
            return False
    
    async def connect_to_peer(self, 
                               peer_id: str, 
                               address: Tuple[str, int],
                               timeout: Optional[float] = None) -> Optional[P2PConnectionInfo]:
        """
        连接到对等节点
        
        Args:
            peer_id: 目标节点ID
            address: 目标地址
            timeout: 连接超时
        
        Returns:
            连接信息或None
        """
        timeout = timeout or self.config.connection_timeout
        
        if self.config.mode == BridgeMode.SUBPROCESS:
            return await self._connect_subprocess(peer_id, address, timeout)
        
        logger.error(f"connect_to_peer not implemented for mode {self.config.mode}")
        return None
    
    async def _connect_subprocess(self, 
                                   peer_id: str, 
                                   address: Tuple[str, int],
                                   timeout: float) -> Optional[P2PConnectionInfo]:
        """通过subprocess连接"""
        try:
            # 这里应该调用FastLink的连接命令
            # 由于当前CLI是占位符，我们返回模拟连接
            logger.info(f"Connecting to peer {peer_id} at {address}")
            
            # TODO: 实际调用FastLink CLI的连接命令
            # cmd = [str(self.config.cli_binary), "connect", peer_id, str(address)]
            # result = await asyncio.create_subprocess_exec(...)
            
            # 临时返回模拟连接
            conn = P2PConnectionInfo(
                node_id="local_node",
                peer_id=peer_id,
                address=address,
                state="connecting",
                latency_ms=0.0,
                established_at=datetime.now()
            )
            
            return conn
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return None
    
    async def send_message(self, peer_id: str, data: bytes) -> bool:
        """发送消息到对等节点"""
        if self.config.mode == BridgeMode.SUBPROCESS:
            # TODO: 通过subprocess发送
            return False
        
        return False
    
    async def broadcast(self, data: bytes) -> int:
        """广播消息"""
        count = 0
        for conn in self._connections.values():
            if await self.send_message(conn.peer_id, data):
                count += 1
        return count
    
    def on_message(self, callback: Callable) -> None:
        """注册消息接收回调"""
        self._message_callbacks.append(callback)
    
    def on_connect(self, callback: Callable) -> None:
        """注册连接建立回调"""
        self._connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable) -> None:
        """注册连接断开回调"""
        self._disconnect_callbacks.append(callback)
    
    async def stop(self) -> None:
        """停止桥接器"""
        self._running = False
        
        if self._process:
            try:
                self._process.terminate()
                await asyncio.sleep(0.5)
                if self._process.poll() is None:
                    self._process.kill()
            except Exception as e:
                logger.error(f"Error stopping FastLink process: {e}")
        
        self._connections.clear()
        logger.info("FastLink bridge stopped")
    
    async def get_node_info(self) -> Optional[Dict]:
        """获取当前节点信息"""
        if self.config.mode == BridgeMode.SUBPROCESS:
            # TODO: 调用CLI的info命令
            return {
                'node_id': self._node_id or "unknown",
                'status': 'running' if self._running else 'stopped',
                'connections': len(self._connections),
            }
        return None
    
    def get_connected_peers(self) -> List[P2PConnectionInfo]:
        """获取已连接的节点列表"""
        return list(self._connections.values())
    
    async def health_check(self) -> bool:
        """健康检查"""
        if self.config.mode == BridgeMode.SUBPROCESS:
            if self._process:
                return self._process.poll() is None
            return True
        
        return False


# 兼容旧接口的别名
FastLinkConnector = FastLinkBridge
ConnectorConfig = BridgeConfig
P2PConfig = BridgeConfig
