"""
Simple Integration Test

Tests core components without complex imports.
"""

import asyncio
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "protocol"))

from nat.birthday_punch import BirthdayPunch, ISPType
from nat.tcp_proxy_tunnel import TCPProxyTunnel, TunnelManager


async def test_components():
    """Test individual components"""
    print("=" * 60)
    print("Simple Integration Test")
    print("=" * 60)
    print()
    
    results = {}
    
    # Test 1: NAT Punch
    print("[TEST 1/3] BirthdayPunch...")
    try:
        punch = BirthdayPunch(isp_type=ISPType.CHINA_TELECOM)
        ports = punch.predict_port_range(30000, 0)
        assert len(ports) > 0
        results['punch'] = True
        print("  ✓ Port prediction works")
    except Exception as e:
        results['punch'] = False
        print(f"  ✗ Failed: {e}")
        
    # Test 2: Proxy Tunnel
    print("[TEST 2/3] TCP Proxy Tunnel...")
    try:
        tunnel = TCPProxyTunnel()
        port = await tunnel.start()
        assert port > 0
        await tunnel.stop()
        results['tunnel'] = True
        print(f"  ✓ Tunnel started on port {port}")
    except Exception as e:
        results['tunnel'] = False
        print(f"  ✗ Failed: {e}")
        
    # Test 3: Tunnel Manager
    print("[TEST 3/3] Tunnel Manager...")
    try:
        manager = TunnelManager()
        
        def mock_send(d): pass
        def mock_recv(): return b""
        
        port = await manager.create_tunnel("test", mock_send, mock_recv)
        assert port > 0
        
        tunnels = manager.list_tunnels()
        assert "test" in tunnels
        
        await manager.close_all()
        results['manager'] = True
        print(f"  ✓ Manager created tunnel on port {port}")
    except Exception as e:
        results['manager'] = False
        print(f"  ✗ Failed: {e}")
        
    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        
    print(f"\nResult: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = asyncio.run(test_components())
    sys.exit(0 if success else 1)
