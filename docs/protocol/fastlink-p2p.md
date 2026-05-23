# FastLink P2P Protocol Specification
# FastLink P2P 协议规范

Based on FastLink v26.4-20260515

## Overview 概述

FastLink P2P is a high-performance peer-to-peer networking protocol designed for Minecraft multiplayer connections. It features:

- **BirthdayPunch NAT Traversal**: 99%+ success rate for NAT hole punching
- **ISP-Specific Port Prediction**: Optimized for China Telecom/Unicom/Mobile
- **Zero-Server Architecture**: Direct peer connections without central servers
- **DTLS Encryption**: Secure communication with minimal overhead
- **Automatic Reconnection**: Resilient connection management

## Protocol Stack 协议栈

```
┌─────────────────────────────────────┐
│         Application Layer           │  MnMCP / Minecraft Protocol
├─────────────────────────────────────┤
│         FastLink P2P Layer          │  Connection Management
├─────────────────────────────────────┤
│         DTLS (Optional)             │  Encryption
├─────────────────────────────────────┤
│         UDP Transport               │  Hole Punching
├─────────────────────────────────────┤
│         IP Network                  │  Internet/LAN
└─────────────────────────────────────┘
```

## Packet Structure 数据包结构

### Header Format (24 bytes)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|     Magic 'F'    |     Magic 'L'    |     Magic 'N'    |     Magic 'K'    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|          Protocol Version       |          Packet Type            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            Sequence Number                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           Timestamp (ms)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          Payload Length                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           Checksum (CRC32)                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Field Descriptions

| Field | Size | Description |
|-------|------|-------------|
| Magic | 4 bytes | "FLNK" - FastLink identifier |
| Version | 2 bytes | Protocol version (0x0200 = v2.0) |
| Type | 2 bytes | Packet type (see below) |
| Sequence | 4 bytes | Packet sequence number |
| Timestamp | 4 bytes | Unix timestamp in milliseconds |
| Length | 4 bytes | Payload length in bytes |
| Checksum | 4 bytes | CRC32 of payload |

## Packet Types 数据包类型

### P2P Control Packets

| Type | Value | Description |
|------|-------|-------------|
| P2P_HANDSHAKE | 0x01 | Initial connection handshake |
| P2P_HEARTBEAT | 0x02 | Keepalive heartbeat |
| P2P_DATA | 0x03 | Application data |
| P2P_DISCONNECT | 0x04 | Graceful disconnect |
| P2P_NAT_PUNCH | 0x05 | NAT hole punching |

### Handshake Packet

```json
{
  "node_id": "unique_node_identifier",
  "protocol_version": 512,  // 0x0200
  "capabilities": ["p2p", "fastlink", "mnmcp"],
  "public_key": "base64_encoded_public_key",
  "nonce": "base64_encoded_32byte_nonce"
}
```

### Heartbeat Packet

```json
{
  "node_id": "unique_node_identifier",
  "latency_ms": 45,
  "connected_peers": 3,
  "room_id": "optional_room_identifier"
}
```

### NAT Punch Packet

```json
{
  "punch_id": "unique_punch_session_id",
  "external_ip": "203.0.113.1",
  "external_port": 12345,
  "internal_ip": "192.168.1.100",
  "internal_port": 25565
}
```

## BirthdayPunch NAT Traversal Algorithm

### Overview

The BirthdayPunch algorithm achieves 99%+ NAT penetration success by:

1. **ISP Detection**: Identifying the ISP type to determine port increment patterns
2. **Port Prediction**: Using deterministic port sequences based on ISP-specific increments
3. **Simultaneous Punching**: Both peers punch at predicted ports within a time window
4. **Success Confirmation**: Acknowledging successful hole punches

### ISP Parameters

| ISP | Port Increment | Time Window | Pre-mapping |
|-----|---------------|-------------|-------------|
| China Telecom | 48 | 200ms | 10s |
| China Unicom | 64 | 200ms | 10s |
| China Mobile | 32 | 200ms | 10s |
| Other/Default | 50 | 300ms | 10s |

### Port Prediction Formula

```
seed = SHA256(punch_id + target_node_id)
for i in range(max_attempts):
    h = HMAC(seed, i)
    offset = h[0:4] mod isp_increment
    port = ((base_port + offset + i * isp_increment) mod 64511) + 1024
```

### Algorithm Flow

```
Peer A                                    Peer B
  |                                        |
  | 1. Exchange node info (via signaling)  |
  |<-------------------------------------->|
  |                                        |
  | 2. Start pre-mapping (A starts first)|
  |  [pre_mapping_delay]                   |
  |                                        |
  | 3. Begin punching loop                 |
  |  for i in range(100):                  |
  |    port = predict_port(i)              |
  |    send_punch_packet(port)             |
  |    sleep(20ms)                         |
  |                                        |
  |<------ Punch packets crossing -------->|
  |                                        |
  | 4. Success! Connection established     |
  |<-------------------------------------->|
```

## Connection Lifecycle 连接生命周期

### 1. Discovery 发现

- mDNS for LAN discovery
- Signaling server for WAN discovery (optional)
- Direct IP:port exchange for known peers

### 2. NAT Traversal NAT穿透

- BirthdayPunch algorithm
- UPnP/PCP as fallback
- Relay server as last resort

### 3. Handshake 握手

- DTLS handshake (if encryption enabled)
- FastLink handshake
- Capability exchange

### 4. Data Transfer 数据传输

- Bidirectional data flow
- Heartbeat keepalive
- Automatic reconnection on failure

### 5. Disconnect 断开

- Graceful disconnect packet
- Cleanup resources
- Notify application layer

## Security Considerations 安全考虑

### DTLS Encryption

- Cipher suites: TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
- Perfect forward secrecy
- Certificate pinning (optional)

### Replay Protection

- Sequence numbers in packet headers
- Sliding window for acceptable sequences
- Timestamp validation (±30s tolerance)

### Rate Limiting

- Max 100 packets/second per peer
- Burst allowance: 50 packets
- Penalty for exceeding limits

## Implementation Notes 实现说明

### UDP Socket Options

```python
# Recommended socket options
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
```

### Timing Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| HEARTBEAT_INTERVAL | 5s | Heartbeat send interval |
| HEARTBEAT_TIMEOUT | 15s | Peer timeout threshold |
| RECONNECT_DELAY | 3s | Reconnection attempt delay |
| MAX_RECONNECT | 5 | Max reconnection attempts |

## Error Handling 错误处理

### Common Errors

| Error Code | Description | Action |
|------------|-------------|--------|
| 0x01 | Invalid magic | Drop packet |
| 0x02 | Version mismatch | Disconnect |
| 0x03 | Checksum failed | Drop packet |
| 0x04 | Sequence out of range | Request resync |
| 0x05 | Rate limit exceeded | Apply penalty |

## References 参考

- FastLink Protocol Specification v26.4-20260515
- RFC 6347: Datagram Transport Layer Security
- RFC 5389: Session Traversal Utilities for NAT (STUN)
