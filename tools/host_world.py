"""
World Host Helper

Helper script to host a Minecraft world via P2P.

Usage:
    python tools/host_world.py --world-name "MyWorld" --port 25565
"""

import asyncio
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from external.server import ExternalServer
from connector.hybrid_connector import HybridConnector


class WorldHost:
    """Helper to host a Minecraft world via P2P"""
    
    def __init__(self, world_name: str, mc_port: int = 25565):
        self.world_name = world_name
        self.mc_port = mc_port
        self.external_server = None
        self.connector = None
        
    async def start(self):
        """Start hosting"""
        print(f"[HOST] Starting world host for: {self.world_name}")
        
        # 1. Start external server
        print("[HOST] Starting external server...")
        self.external_server = ExternalServer(
            host="127.0.0.1",
            port=25566,
            hybrid_connector=None
        )
        await self.external_server.start()
        
        # 2. Start hybrid connector
        print("[HOST] Starting P2P connector...")
        self.connector = HybridConnector(
            prefer_protocol="fastlink",
            enable_webrtc_fallback=True
        )
        await self.connector.start()
        
        # Get node info
        node_info = self.connector.get_status()
        
        print("\n" + "=" * 60)
        print("World Hosting Started!")
        print("=" * 60)
        print(f"World: {self.world_name}")
        print(f"External Server: 127.0.0.1:25566")
        if 'preferred_protocol' in node_info:
            print(f"P2P Protocol: {node_info['preferred_protocol']}")
        print("\nInstructions:")
        print("1. Open Minecraft")
        print("2. Load your world")
        print("3. Press ESC -> 'Open to LAN'")
        print(f"4. Set port to: {self.mc_port}")
        print("5. Your friends will see it in P2P server list!")
        print("=" * 60)
        
    async def stop(self):
        """Stop hosting"""
        print("[HOST] Stopping...")
        
        if self.external_server:
            await self.external_server.stop()
            
        if self.connector:
            await self.connector.stop()
            
        print("[HOST] Stopped")
        
    async def run(self):
        """Run hosting loop"""
        await self.start()
        
        try:
            print("\nPress Ctrl+C to stop hosting")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()


def main():
    parser = argparse.ArgumentParser(description="Minecraft World Host Helper")
    parser.add_argument("--world-name", type=str, default="MyWorld", help="World name")
    parser.add_argument("--port", type=int, default=25565, help="Minecraft server port")
    parser.add_argument("--protocol", type=str, default="fastlink", 
                       choices=["fastlink", "webrtc", "auto"],
                       help="Preferred P2P protocol")
    
    args = parser.parse_args()
    
    host = WorldHost(
        world_name=args.world_name,
        mc_port=args.port
    )
    
    try:
        asyncio.run(host.run())
    except Exception as e:
        print(f"[HOST] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
