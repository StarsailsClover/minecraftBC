"""
External Server Mode for MinecraftBC

作为独立进程运行，提供TCP服务供Minecraft模组连接。

Usage:
    python -m src.external.server [--port 25566] [--p2p-port 0]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from external.tcp_server import ExternalTCPServer, P2PServerInfo
from connector.hybrid_connector import HybridConnector, ProtocolType
from config.settings import MinecraftBCSettings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExternalServer:
    """
    外部服务器主类
    
    整合TCP服务器和P2P连接器，为Minecraft模组提供完整的P2P联机服务。
    """
    
    def __init__(
        self,
        tcp_port: int = 25566,
        p2p_port: int = 0,
        prefer_protocol: str = "fastlink"
    ):
        self.tcp_port = tcp_port
        self.p2p_port = p2p_port
        self.prefer_protocol = ProtocolType(prefer_protocol) if prefer_protocol else ProtocolType.FASTLINK
        
        # 组件
        self.tcp_server: ExternalTCPServer = None
        self.hybrid_connector: HybridConnector = None
        
        # 运行状态
        self._running = False
        
    async def start(self):
        """启动服务器"""
        logger.info("Starting MinecraftBC External Server...")
        
        # 1. 启动Hybrid Connector (P2P网络)
        logger.info("Initializing P2P connector...")
        self.hybrid_connector = HybridConnector(
            prefer_protocol=self.prefer_protocol,
            enable_webrtc_fallback=True
        )
        await self.hybrid_connector.start()
        
        # 2. 启动TCP服务器 (模组通信)
        logger.info(f"Starting TCP server on port {self.tcp_port}...")
        self.tcp_server = ExternalTCPServer(
            host="127.0.0.1",
            port=self.tcp_port,
            hybrid_connector=self.hybrid_connector
        )
        
        # 设置回调
        self.tcp_server.on_server_list_request = self._on_server_list_request
        self.tcp_server.on_connect_request = self._on_connect_request
        self.tcp_server.on_disconnect = self._on_disconnect
        
        await self.tcp_server.start()
        
        self._running = True
        
        # 3. 显示状态
        self._print_status()
        
        # 4. 保持运行
        logger.info("Server is running. Press Ctrl+C to stop.")
        try:
            while self._running:
                await asyncio.sleep(1)
                await self._update_server_list()
        except asyncio.CancelledError:
            pass
            
    async def stop(self):
        """停止服务器"""
        logger.info("Stopping server...")
        self._running = False
        
        if self.tcp_server:
            await self.tcp_server.stop()
            
        if self.hybrid_connector:
            await self.hybrid_connector.stop()
            
        logger.info("Server stopped")
        
    def _on_server_list_request(self, conn) -> list:
        """处理服务器列表请求"""
        # 从Hybrid Connector获取可用服务器
        servers = self.hybrid_connector.get_available_servers()
        
        # 转换为P2PServerInfo
        result = []
        for srv in servers:
            result.append(P2PServerInfo(
                id=srv["id"],
                name=srv["name"],
                description=f"P2P Server ({srv['protocol']})",
                host=srv["host"],
                port=srv["port"],
                latency=srv.get("latency", -1),
                player_count=0,  # 需要从实际服务器获取
                max_players=20,
                version="1.20.6"
            ))
            
        # 添加测试服务器（开发用）
        if not result:
            result.append(P2PServerInfo(
                id="test-server",
                name="Test P2P Server",
                description="Test server for development",
                host="127.0.0.1",
                port=25565,
                latency=10,
                player_count=0,
                max_players=10,
                version="1.20.6"
            ))
            
        logger.debug(f"Returning {len(result)} servers to {conn.player_name}")
        return result
        
    async def _on_connect_request(
        self,
        conn,
        server_id: str,
        host: str,
        port: int
    ):
        """处理连接请求"""
        logger.info(
            f"Connection request from {conn.player_name} to {server_id} ({host}:{port})"
        )
        
        try:
            # 创建代理隧道
            local_port = await self.hybrid_connector.create_proxy_tunnel(
                server_id, host, port
            )
            
            if local_port > 0:
                logger.info(
                    f"Proxy tunnel created: 127.0.0.1:{local_port} -> {server_id}"
                )
                return True, "127.0.0.1", local_port, "P2P connection established"
            else:
                return False, "", 0, "Failed to create proxy tunnel"
                
        except Exception as e:
            logger.error(f"Connection request failed: {e}")
            return False, "", 0, f"Error: {str(e)}"
            
    def _on_disconnect(self, conn):
        """处理断开连接"""
        logger.info(f"Player disconnected: {conn.player_name}")
        
    async def _update_server_list(self):
        """定期更新服务器列表"""
        # 每30秒广播一次服务器列表更新
        # 实际实现需要更智能的触发机制
        pass
        
    def _print_status(self):
        """打印服务器状态"""
        print("\n" + "=" * 60)
        print("MinecraftBC External Server")
        print("=" * 60)
        print(f"TCP Server:     127.0.0.1:{self.tcp_port}")
        print(f"P2P Protocol:   {self.prefer_protocol.value}")
        
        if self.hybrid_connector:
            status = self.hybrid_connector.get_status()
            print(f"FastLink:       {'✓' if status['fastlink_available'] else '✗'}")
            print(f"WebRTC:         {'✓' if status['webrtc_available'] else '✗'}")
            print(f"Discovery:      {'Running' if status['discovery_running'] else 'Stopped'}")
            
        print(f"Connected Mods: {self.tcp_server.get_connection_count()}")
        print("=" * 60)
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MinecraftBC External Server - TCP service for Minecraft mod"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=25566,
        help="TCP port for mod communication (default: 25566)"
    )
    parser.add_argument(
        "--p2p-port",
        type=int,
        default=0,
        help="P2P listening port (0=auto, default: 0)"
    )
    parser.add_argument(
        "--protocol",
        choices=["fastlink", "webrtc", "auto"],
        default="fastlink",
        help="Preferred P2P protocol (default: fastlink)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    server = ExternalServer(
        tcp_port=args.port,
        p2p_port=args.p2p_port,
        prefer_protocol=args.protocol
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        asyncio.run(server.stop())


if __name__ == "__main__":
    main()
