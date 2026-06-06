"""
BirthdayPunch NAT Traversal Implementation

Based on FastLink v26.4-20260515 specification:
- 99%+ NAT penetration success rate
- ISP-Specific Port Prediction
- Zero-Server Architecture

Core algorithm for UDP hole punching with high success rate.
"""

import asyncio
import socket
import struct
import random
import time
import hashlib
from typing import Optional, Tuple, List, Dict, Callable
from dataclasses import dataclass
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class ISPType(IntEnum):
    """ISP types for port prediction"""
    UNKNOWN = 0
    CHINA_TELECOM = 1
    CHINA_UNICOM = 2
    CHINA_MOBILE = 3
    OTHER = 4


class NATType(IntEnum):
    """NAT types"""
    UNKNOWN = 0
    OPEN = 1
    FULL_CONE = 2
    RESTRICTED_CONE = 3
    PORT_RESTRICTED = 4
    SYMMETRIC = 5


@dataclass
class ISPParams:
    """ISP-specific NAT parameters"""
    isp_type: ISPType
    port_increment: int
    time_window_ms: int
    pre_mapping_seconds: int
    
    # ISP-specific parameters
    PARAMS = {
        ISPType.CHINA_TELECOM: {
            'port_increment': 48,
            'time_window_ms': 200,
            'pre_mapping_seconds': 10
        },
        ISPType.CHINA_UNICOM: {
            'port_increment': 64,
            'time_window_ms': 200,
            'pre_mapping_seconds': 10
        },
        ISPType.CHINA_MOBILE: {
            'port_increment': 32,
            'time_window_ms': 200,
            'pre_mapping_seconds': 10
        },
        ISPType.OTHER: {
            'port_increment': 16,
            'time_window_ms': 200,
            'pre_mapping_seconds': 10
        }
    }
    
    @classmethod
    def for_isp(cls, isp_type: ISPType) -> 'ISPParams':
        params = cls.PARAMS.get(isp_type, cls.PARAMS[ISPType.OTHER])
        return cls(
            isp_type=isp_type,
            port_increment=params['port_increment'],
            time_window_ms=params['time_window_ms'],
            pre_mapping_seconds=params['pre_mapping_seconds']
        )


@dataclass
class PunchAttempt:
    """A single punch attempt"""
    target_addr: Tuple[str, int]
    local_port: int
    timestamp: float
    attempt_number: int
    success: bool = False


@dataclass
class PunchResult:
    """Result of BirthdayPunch"""
    success: bool
    local_addr: Optional[Tuple[str, int]]
    remote_addr: Optional[Tuple[str, int]]
    latency_ms: float
    attempts: int
    error: Optional[str] = None


class BirthdayPunch:
    """
    BirthdayPunch NAT Traversal
    
    Core algorithm for high-success-rate NAT penetration.
    
    Algorithm:
    1. Detect ISP type
    2. Calculate predicted port range
    3. Perform coordinated punching
    4. Verify connection
    """
    
    def __init__(self, 
                 isp_type: ISPType = ISPType.UNKNOWN,
                 nat_type: NATType = NATType.UNKNOWN):
        self.isp_params = ISPParams.for_isp(isp_type)
        self.nat_type = nat_type
        
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.attempts: List[PunchAttempt] = []
        
        # Success callback
        self.on_success: Optional[Callable[[Tuple[str, int]], None]] = None
        
    async def detect_isp(self) -> ISPType:
        """
        Detect ISP type based on network characteristics
        
        Returns detected ISP type
        """
        # TODO: Implement ISP detection
        # Methods:
        # 1. IP range matching
        # 2. Port increment analysis
        # 3. RTT characteristics
        
        logger.info("ISP detection not implemented, using auto-detect")
        return ISPType.UNKNOWN
        
    def predict_port_range(self, 
                          base_port: int, 
                          time_delta_ms: int) -> List[int]:
        """
        Predict remote port range based on ISP parameters
        
        Args:
            base_port: Known base port
            time_delta_ms: Time difference in milliseconds
            
        Returns:
            List of predicted ports to try
        """
        increment = self.isp_params.port_increment
        window = self.isp_params.time_window_ms
        
        # Calculate expected port progression
        port_changes = time_delta_ms // window
        expected_port = base_port + (port_changes * increment)
        
        # Generate range around expected port
        # Try +/- 3 increments for safety margin
        ports = []
        for i in range(-3, 4):
            ports.append(expected_port + (i * increment))
            
        # Also include common ports
        ports.extend([base_port, base_port + increment, base_port + 2*increment])
        
        # Remove duplicates and invalid ports
        ports = list(set(ports))
        ports = [p for p in ports if 1024 <= p <= 65535]
        
        return sorted(ports)
        
    async def punch(self,
                   target_public_addr: Tuple[str, int],
                   target_local_addr: Tuple[str, int],
                   timeout: float = 30.0) -> PunchResult:
        """
        Perform BirthdayPunch NAT traversal
        
        Args:
            target_public_addr: Target's public address (from signaling)
            target_local_addr: Target's local address (for LAN shortcut)
            timeout: Maximum time to attempt punching
            
        Returns:
            PunchResult with success status and connection info
        """
        start_time = time.time()
        logger.info(f"Starting BirthdayPunch to {target_public_addr}")
        
        # Check if on same LAN
        if self._is_same_lan(target_local_addr):
            logger.info("Target appears to be on same LAN, using direct connection")
            return await self._try_lan_direct(target_local_addr)
            
        # Create UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        
        # Bind to random port
        self.socket.bind(('0.0.0.0', 0))
        local_addr = self.socket.getsockname()
        logger.info(f"Bound to local address: {local_addr}")
        
        # Get predicted port range
        predicted_ports = self.predict_port_range(
            target_public_addr[1], 
            0  # Assume simultaneous start
        )
        logger.info(f"Predicted ports: {predicted_ports}")
        
        # Perform punching
        success = False
        remote_addr = None
        
        try:
            success, remote_addr = await self._coordinated_punch(
                target_public_addr,
                predicted_ports,
                timeout
            )
        except Exception as e:
            logger.error(f"Punching failed: {e}")
            
        elapsed = (time.time() - start_time) * 1000
        
        if success and remote_addr:
            logger.info(f"Punch succeeded in {elapsed:.1f}ms!")
            return PunchResult(
                success=True,
                local_addr=local_addr,
                remote_addr=remote_addr,
                latency_ms=elapsed,
                attempts=len(self.attempts)
            )
        else:
            logger.warning(f"Punch failed after {elapsed:.1f}ms")
            return PunchResult(
                success=False,
                local_addr=None,
                remote_addr=None,
                latency_ms=elapsed,
                attempts=len(self.attempts),
                error="Punch timeout"
            )
            
    async def _coordinated_punch(self,
                                  target_addr: Tuple[str, int],
                                  predicted_ports: List[int],
                                  timeout: float) -> Tuple[bool, Optional[Tuple[str, int]]]:
        """
        Perform coordinated punching with peer
        
        This is the core BirthdayPunch algorithm
        """
        end_time = time.time() + timeout
        attempt = 0
        
        # Create punching pattern
        # Send to multiple predicted ports in rapid succession
        punch_data = b"BIRTHDAY_PUNCH" + struct.pack('>I', random.randint(0, 0xFFFFFFFF))
        
        while time.time() < end_time:
            attempt += 1
            
            # Try each predicted port
            for port in predicted_ports[:5]:  # Limit to top 5
                addr = (target_addr[0], port)
                
                try:
                    self.socket.sendto(punch_data, addr)
                    
                    # Record attempt
                    self.attempts.append(PunchAttempt(
                        target_addr=addr,
                        local_port=self.socket.getsockname()[1],
                        timestamp=time.time(),
                        attempt_number=attempt
                    ))
                    
                    # Small delay between attempts
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.debug(f"Send failed to {addr}: {e}")
                    
            # Check for response
            try:
                self.socket.setblocking(False)
                data, addr = self.socket.recvfrom(1024)
                
                if data.startswith(b"BIRTHDAY_ACK"):
                    logger.info(f"Received ACK from {addr}")
                    return True, addr
                    
            except BlockingIOError:
                pass
            except Exception as e:
                logger.debug(f"Recv error: {e}")
                
            # Wait before next round
            await asyncio.sleep(0.1)
            
        return False, None
        
    def _is_same_lan(self, addr: Tuple[str, int]) -> bool:
        """Check if address is on same LAN"""
        # Simple check: if local IP matches first 3 octets
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            remote_ip = addr[0]
            
            local_parts = local_ip.split('.')
            remote_parts = remote_ip.split('.')
            
            return (local_parts[0] == remote_parts[0] and 
                    local_parts[1] == remote_parts[1] and
                    local_parts[2] == remote_parts[2])
        except:
            return False
            
    async def _try_lan_direct(self, 
                             addr: Tuple[str, int]) -> PunchResult:
        """Try direct LAN connection"""
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            
            # Send probe
            sock.sendto(b"LAN_PROBE", addr)
            
            # Wait for response
            data, _ = sock.recvfrom(1024)
            
            elapsed = (time.time() - start_time) * 1000
            
            if data == b"LAN_ACK":
                return PunchResult(
                    success=True,
                    local_addr=sock.getsockname(),
                    remote_addr=addr,
                    latency_ms=elapsed,
                    attempts=1
                )
        except:
            pass
            
        return PunchResult(
            success=False,
            local_addr=None,
            remote_addr=None,
            latency_ms=(time.time() - start_time) * 1000,
            attempts=1,
            error="LAN direct failed"
        )
        
    def close(self):
        """Close socket and cleanup"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            

# Example usage
if __name__ == "__main__":
    async def test():
        punch = BirthdayPunch(isp_type=ISPType.CHINA_TELECOM)
        
        # Mock target (would come from signaling)
        result = await punch.punch(
            target_public_addr=("203.0.113.1", 30000),
            target_local_addr=("192.168.1.100", 25565),
            timeout=10.0
        )
        
        print(f"Success: {result.success}")
        print(f"Local: {result.local_addr}")
        print(f"Remote: {result.remote_addr}")
        print(f"Latency: {result.latency_ms:.1f}ms")
        print(f"Attempts: {result.attempts}")
        
        punch.close()
        
    asyncio.run(test())
