"""
minecraftBC - Minecraft Bridge Connector
Minecraft 桥接连接器主程序 v2.0

双协议P2P联机 + 局域网注入 + MnMCP跨游戏支持

Usage:
    # P2P模式（推荐）
    python -m src.main p2p [--port PORT] [--name NAME] [--config PATH]
    
    # 轻服务器模式
    python -m src.main server [--port PORT] [--room ROOM]
    
    # 客户端模式
    python -m src.main client --server NODE_ID [--connect]
    
    # LAN注入模式（核心功能）
    python -m src.main lan [--mc-port PORT] [--world-name NAME]
    
    # MnMCP代理模式
    python -m src.main mnmcp --mc-port PORT [--adapter ADAPTER]

Examples:
    # 启动P2P节点并托管世界
    python -m src.main p2p --port 0 --name "MyNode"
    
    # 启动LAN注入器托管本地世界
    python -m src.main lan --mc-port 25565 --world-name "Survival World"
    
    # 连接到P2P世界（客户端）
    python -m src.main client --server <NODE_ID> --connect
"""

from __future__ import annotations
import asyncio
import argparse
import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# 导入组件
from config.manager import ConfigManager
from config.settings import MinecraftBCSettings, P2PSettings, MinecraftSettings
from connector.hybrid_connector import HybridConnector
from connector.protocol_type import ProtocolSelector
from protocol.fastlink.packet import generate_node_id
from protocol.fastlink.crypto import NodeIdentity
from protocol.fastlink.p2p import P2PConnection, NodeInfo
from protocol.fastlink.server import FastLinkServer, RoomVisibility
from protocol.mnmcp.proxy import MnMCPProxy, GameType
from minecraft.lan_injector import LANInjector, LANConfig, LANWorldInfo
from minecraft.protocol_adapter import MinecraftProtocolAdapter


def setup_logging(settings: MinecraftBCSettings):
    """配置日志"""
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    
    handlers = []
    
    # 控制台处理器
    if settings.logging.console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # 文件处理器
    if settings.logging.file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            settings.logging.file,
            maxBytes=settings.logging.max_size_mb * 1024 * 1024,
            backupCount=settings.logging.backup_count
        )
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # 配置根日志
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )


def print_banner():
    """打印启动横幅"""
    print(r""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   minecraftBC - Minecraft Bridge Connector                    ║
    ║   双协议P2P联机 + 局域网注入 + MnMCP跨游戏                   ║
    ║                                                               ║
    ║   Protocol: FastLink (primary) + WebRTC (fallback)          ║
    ║   Version: 2.0.0                                              ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)


async def load_identity(config: MinecraftBCSettings) -> NodeIdentity:
    """加载或生成节点身份"""
    key_path = config.get_node_identity_path()
    
    identity = NodeIdentity(key_file=key_path)
    
    # 检查是否已有密钥
    if os.path.exists(key_path):
        identity.load()
        logging.info(f"Loaded existing identity: {identity.node_id}")
    else:
        identity.generate()
        identity.save()
        logging.info(f"Generated new identity: {identity.node_id}")
    
    return identity


async def run_p2p_mode(args, config: MinecraftBCSettings, identity: NodeIdentity):
    """
    运行P2P模式
    
    启动双协议P2P节点，支持LAN世界托管。
    """
    logger = logging.getLogger('p2p')
    logger.info("Starting P2P mode...")
    
    # 创建混合连接器
    local_addr = (config.p2p.bind_host, args.port or config.p2p.bind_port)
    
    connector = HybridConnector(
        node_id=identity.node_id,
        local_addr=local_addr,
        prefer_fastlink=config.p2p.prefer_fastlink,
        fallback_timeout=config.p2p.fallback_timeout
    )
    
    # 设置回调
    def on_message(peer_id: str, data: bytes, addr: str):
        logger.debug(f"Message from {peer_id}: {len(data)} bytes")
    
    def on_connect(peer_id: str):
        logger.info(f"Connected: {peer_id}")
    
    def on_disconnect(peer_id: str):
        logger.info(f"Disconnected: {peer_id}")
    
    connector.on_message(on_message)
    connector.on_connect(on_connect)
    connector.on_disconnect(on_disconnect)
    
    # 启动连接器
    if not await connector.start():
        logger.error("Failed to start P2P connector!")
        return 1
    
    logger.info(f"P2P node started: {identity.node_id}")
    logger.info(f"Local address: {local_addr}")
    
    # 启动LAN注入器
    lan_config = LANConfig(
        listen_port=config.minecraft.lan_listen_port,
        mc_version=config.minecraft.mc_version,
        motd_prefix=config.minecraft.motd_prefix,
        enable_offline=config.minecraft.enable_offline,
        broadcast_interval=config.minecraft.broadcast_interval,
        max_players=8
    )
    
    lan_injector = LANInjector(lan_config, connector)
    
    def on_world_discovered(world: LANWorldInfo):
        print(f"\n[World Discovered] {world.motd}")
        print(f"  Host: {world.host_node_id}")
        print(f"  Address: {world.p2p_address}")
        print(f"  Players: {world.player_count}/{world.max_players}")
        print()
    
    lan_injector.on_world_discovered(on_world_discovered)
    
    if not await lan_injector.start():
        logger.error("Failed to start LAN injector!")
        await connector.stop()
        return 1
    
    logger.info("LAN injector started")
    
    # 如果指定了MC端口，自动托管世界
    if args.mc_port:
        world_name = args.world_name or f"{args.name}'s World"
        if await lan_injector.host_world(args.mc_port, world_name):
            logger.info(f"Hosting world: {world_name}")
            logger.info(f"Other players can discover this world in their LAN list")
        else:
            logger.error("Failed to host world")
    
    # 主循环
    print("\n" + "="*60)
    print("P2P mode running. Commands:")
    print("  worlds  - List discovered worlds")
    print("  connect <node_id> - Connect to world")
    print("  quit    - Exit")
    print("="*60 + "\n")
    
    try:
        while True:
            # 简单的命令处理
            # 实际应用中可以使用更复杂的交互方式
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await lan_injector.stop()
        await connector.stop()
    
    return 0


async def run_lan_mode(args, config: MinecraftBCSettings, identity: NodeIdentity):
    """
    运行LAN注入器模式
    
    专门用于托管Minecraft本地世界。
    """
    logger = logging.getLogger('lan')
    logger.info("Starting LAN injector mode...")
    
    if not args.mc_port:
        logger.error("--mc-port required for LAN mode")
        return 1
    
    # 创建连接器
    local_addr = (config.p2p.bind_host, 0)  # 随机端口
    
    connector = HybridConnector(
        node_id=identity.node_id,
        local_addr=local_addr,
        prefer_fastlink=config.p2p.prefer_fastlink
    )
    
    if not await connector.start():
        logger.error("Failed to start connector!")
        return 1
    
    # 创建LAN注入器
    lan_config = LANConfig(
        listen_port=config.minecraft.lan_listen_port,
        mc_version=config.minecraft.mc_version,
        motd_prefix=config.minecraft.motd_prefix,
        enable_offline=config.minecraft.enable_offline,
        max_players=8
    )
    
    injector = LANInjector(lan_config, connector)
    
    if not await injector.start():
        logger.error("Failed to start LAN injector!")
        await connector.stop()
        return 1
    
    # 托管世界
    world_name = args.world_name or "P2P World"
    if not await injector.host_world(args.mc_port, world_name):
        logger.error("Failed to host world!")
        await connector.stop()
        return 1
    
    logger.info(f"LAN injector running!")
    logger.info(f"World: {world_name}")
    logger.info(f"Minecraft Port: {args.mc_port}")
    logger.info(f"Node ID: {identity.node_id}")
    logger.info(f"")
    logger.info(f"Players can find your world in their Minecraft LAN list!")
    logger.info(f"Or connect directly: python -m src.main client --server {identity.node_id}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await injector.stop_hosting()
        await injector.stop()
        await connector.stop()
    
    return 0


async def run_client_mode(args, config: MinecraftBCSettings, identity: NodeIdentity):
    """
    运行客户端模式
    
    连接到P2P网络并发现世界。
    """
    logger = logging.getLogger('client')
    logger.info("Starting client mode...")
    
    # 创建连接器
    local_addr = (config.p2p.bind_host, 0)
    
    connector = HybridConnector(
        node_id=identity.node_id,
        local_addr=local_addr,
        prefer_fastlink=config.p2p.prefer_fastlink
    )
    
    if not await connector.start():
        logger.error("Failed to start connector!")
        return 1
    
    logger.info(f"Client started: {identity.node_id}")
    
    # 如果指定了服务器，尝试连接
    if args.server:
        logger.info(f"Connecting to {args.server}...")
        # 解析地址
        if ':' in args.server:
            host, port_str = args.server.rsplit(':', 1)
            port = int(port_str)
        else:
            host, port = args.server, 25565
        
        success = await connector.connect_to_peer(
            args.server, (host, port), timeout=30.0
        )
        
        if success:
            logger.info(f"Connected to {args.server}")
        else:
            logger.error(f"Failed to connect to {args.server}")
            await connector.stop()
            return 1
    
    # 启动LAN注入器以发现世界
    lan_config = LANConfig(
        listen_port=config.minecraft.lan_listen_port,
        mc_version=config.minecraft.mc_version
    )
    
    injector = LANInjector(lan_config, connector)
    
    discovered_worlds = []
    
    def on_world_discovered(world: LANWorldInfo):
        discovered_worlds.append(world)
        print(f"\n[Discovered] {world.motd}")
    
    injector.on_world_discovered(on_world_discovered)
    
    if not await injector.start():
        logger.warning("LAN injector failed to start, discovery limited")
    
    print("\n" + "="*60)
    print("Client mode running. Discovering worlds...")
    print("Press Ctrl+C to exit")
    print("="*60 + "\n")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n")
        logger.info("Discovered worlds:")
        for i, world in enumerate(discovered_worlds, 1):
            logger.info(f"  {i}. {world.motd} ({world.host_node_id})")
    finally:
        await injector.stop()
        await connector.stop()
    
    return 0


async def run_mnmcp_mode(args, config: MinecraftBCSettings, identity: NodeIdentity):
    """运行MnMCP代理模式"""
    logger = logging.getLogger('mnmcp')
    logger.info("Starting MnMCP mode...")
    
    if not args.mc_port:
        logger.error("--mc-port required for MnMCP mode")
        return 1
    
    # 创建代理
    from minecraft.proxy_handler import MinecraftProxy
    
    proxy = MinecraftProxy()
    
    # 设置包处理器
    def packet_handler(direction, packet):
        logger.debug(f"Packet: {direction} {packet.packet_id}")
        return packet
    
    proxy.on_packet(packet_handler)
    
    # 启动代理
    if not await proxy.start(
        local_port=args.mc_port,
        target_host=args.target_host or 'localhost',
        target_port=args.target_port or 25565
    ):
        logger.error("Failed to start proxy!")
        return 1
    
    logger.info(f"MnMCP proxy running on port {args.mc_port}")
    logger.info(f"Forward to: {args.target_host}:{args.target_port}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await proxy.stop()
    
    return 0


def main():
    """主入口"""
    print_banner()
    
    # 参数解析
    parser = argparse.ArgumentParser(
        description='minecraftBC - Minecraft P2P Bridge',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s p2p --port 0 --name MyNode
    %(prog)s lan --mc-port 25565 --world-name "My World"
    %(prog)s client --server <NODE_ID>
        """
    )
    
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    subparsers = parser.add_subparsers(dest='mode', help='运行模式')
    
    # P2P模式
    p2p_parser = subparsers.add_parser('p2p', help='P2P节点模式')
    p2p_parser.add_argument('--port', '-p', type=int, default=0, help='监听端口')
    p2p_parser.add_argument('--name', '-n', default='Node', help='节点名称')
    p2p_parser.add_argument('--mc-port', type=int, help='Minecraft服务器端口（自动托管）')
    p2p_parser.add_argument('--world-name', help='世界名称')
    
    # LAN模式
    lan_parser = subparsers.add_parser('lan', help='LAN注入器模式')
    lan_parser.add_argument('--mc-port', '-p', type=int, required=True, help='Minecraft端口')
    lan_parser.add_argument('--world-name', '-n', default='P2P World', help='世界名称')
    
    # 客户端模式
    client_parser = subparsers.add_parser('client', help='客户端模式')
    client_parser.add_argument('--server', '-s', help='目标服务器节点ID')
    client_parser.add_argument('--connect', '-c', action='store_true', help='立即连接')
    
    # MnMCP模式
    mnmcp_parser = subparsers.add_parser('mnmcp', help='MnMCP代理模式')
    mnmcp_parser.add_argument('--mc-port', '-p', type=int, required=True, help='代理端口')
    mnmcp_parser.add_argument('--target-host', default='localhost', help='目标主机')
    mnmcp_parser.add_argument('--target-port', type=int, default=25565, help='目标端口')
    mnmcp_parser.add_argument('--adapter', default='generic', help='适配器类型')
    
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return 1
    
    # 加载配置
    config_manager = ConfigManager(args.config)
    config = config_manager.load()
    
    if args.verbose:
        config.logging.level = 'DEBUG'
    
    # 配置日志
    setup_logging(config)
    logger = logging.getLogger('main')
    
    logger.info(f"Starting minecraftBC in {args.mode} mode")
    logger.info(f"Config loaded from: {config_manager.config_path}")
    
    # 加载节点身份
    identity = asyncio.run(load_identity(config))
    
    if not identity.node_id:
        logger.error("Failed to load/generate node identity!")
        return 1
    
    logger.info(f"Node ID: {identity.node_id}")
    
    # 运行对应模式
    try:
        if args.mode == 'p2p':
            return asyncio.run(run_p2p_mode(args, config, identity))
        elif args.mode == 'lan':
            return asyncio.run(run_lan_mode(args, config, identity))
        elif args.mode == 'client':
            return asyncio.run(run_client_mode(args, config, identity))
        elif args.mode == 'mnmcp':
            return asyncio.run(run_mnmcp_mode(args, config, identity))
        else:
            parser.print_help()
            return 1
    except Exception as e:
        logger.exception("Fatal error:")
        return 1


if __name__ == '__main__':
    sys.exit(main())
