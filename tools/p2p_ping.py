"""
P2P Ping Tool

Test P2P connectivity between nodes.

Usage:
    python tools/p2p_ping.py --target <NODE_ID>
    python tools/p2p_ping.py --discover
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from protocol.fastlink.packet import generate_node_id
from network.discovery import DiscoveryManager, DiscoveredNode
from connector.hybrid_connector import HybridConnector


async def discover_nodes(timeout: int = 10):
    """Discover available P2P nodes"""
    print(f"[DISCOVER] Starting discovery for {timeout} seconds...")
    
    node_id = generate_node_id()
    discovery = DiscoveryManager(
        node_id=node_id,
        node_name="PingTool",
        service_port=0
    )
    
    discovered = []
    
    def on_discover(node: DiscoveredNode):
        print(f"[DISCOVER] Found: {node.name} ({node.node_id[:8]}...)")
        print(f"  Addresses: {node.addresses}")
        discovered.append(node)
    
    discovery.on_discover(on_discover)
    
    await discovery.start()
    
    try:
        await asyncio.sleep(timeout)
    except asyncio.TimeoutError:
        pass
    
    await discovery.stop()
    
    print(f"\n[DISCOVER] Total nodes found: {len(discovered)}")
    return discovered


async def ping_node(target_id: str, count: int = 4):
    """Ping a P2P node"""
    print(f"[PING] Pinging node: {target_id[:16]}...")
    
    node_id = generate_node_id()
    connector = HybridConnector()
    
    await connector.start()
    
    # Try to connect
    print(f"[PING] Connecting...")
    connected = await connector.connect(target_id)
    
    if not connected:
        print(f"[PING] Failed to connect")
        await connector.stop()
        return False
    
    print(f"[PING] Connected! Sending {count} pings...")
    
    # Send pings
    latencies = []
    for i in range(count):
        start = time.time()
        
        # Send ping data
        success = await connector.send(target_id, b"PING")
        
        if success:
            # Wait for response (simplified)
            await asyncio.sleep(0.1)
            
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            print(f"  Ping {i+1}: {latency:.1f}ms")
        else:
            print(f"  Ping {i+1}: Timeout")
        
        await asyncio.sleep(1)
    
    # Disconnect
    await connector.disconnect(target_id)
    await connector.stop()
    
    # Statistics
    if latencies:
        avg = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        
        print(f"\n[PING] Statistics:")
        print(f"  Sent: {count}")
        print(f"  Received: {len(latencies)}")
        print(f"  Loss: {((count - len(latencies)) / count) * 100:.1f}%")
        print(f"  Min: {min_lat:.1f}ms")
        print(f"  Max: {max_lat:.1f}ms")
        print(f"  Avg: {avg:.1f}ms")
    
    return len(latencies) > 0


def main():
    parser = argparse.ArgumentParser(description="P2P Ping Tool")
    parser.add_argument("--discover", action="store_true", help="Discover nodes")
    parser.add_argument("--target", type=str, help="Target node ID to ping")
    parser.add_argument("--count", type=int, default=4, help="Number of pings")
    parser.add_argument("--timeout", type=int, default=10, help="Discovery timeout")
    
    args = parser.parse_args()
    
    if args.discover:
        asyncio.run(discover_nodes(args.timeout))
    elif args.target:
        asyncio.run(ping_node(args.target, args.count))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
