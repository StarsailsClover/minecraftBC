# minecraftBC API 参考文档

版本: minecraftBC HighIsland v26.15-20260606-RC

---

## 目录

1. [TCP 协议](#tcp-协议)
2. [Python API](#python-api)
3. [Java API](#java-api)
4. [配置选项](#配置选项)

---

## TCP 协议

### 协议格式

```
[Length: 4字节大端] [Type: 1字节] [Payload: N字节]
```

### 包类型

| 值 | 名称 | 描述 |
|----|------|------|
| 0x01 | HEARTBEAT | 心跳包 |
| 0x02 | HANDSHAKE | 握手 |
| 0x03 | SERVER_LIST | 服务器列表 |
| 0x04 | CONNECT_REQUEST | 连接请求 |
| 0x05 | CONNECT_RESPONSE | 连接响应 |
| 0x06 | DISCONNECT | 断开连接 |
| 0x07 | ERROR | 错误 |
| 0x08 | AUTH | 认证 |

### 握手包 (HANDSHAKE)

**Payload 格式:**

```
[Protocol Version: 4字节]
[Mod Version: 4字节]
[MC Version Len: 4字节] [MC Version: N字节]
[Player UUID Len: 4字节] [Player UUID: N字节]
[Player Name Len: 4字节] [Player Name: N字节]
```

### 服务器列表包 (SERVER_LIST)

**Payload 格式:**

```
[Server Count: 4字节]
[
  [Server ID Len: 4字节] [Server ID: N字节]
  [Name Len: 4字节] [Name: N字节]
  [Description Len: 4字节] [Description: N字节]
  [Host Len: 4字节] [Host: N字节]
  [Port: 4字节]
  [Latency: 4字节]
  [Player Count: 4字节]
  [Max Players: 4字节]
  [Version Len: 4字节] [Version: N字节]
] * Count
```

### 连接响应包 (CONNECT_RESPONSE)

**Payload 格式:**

```
[Success: 1字节 (0/1)]
[Server ID Len: 4字节] [Server ID: N字节]
[Local Host Len: 4字节] [Local Host: N字节]
[Local Port: 4字节]
[Message Len: 4字节] [Message: N字节]
```

---

## Python API

### ExternalTCPServer

TCP服务器，用于与Minecraft模组通信。

```python
from external.tcp_server import ExternalTCPServer

server = ExternalTCPServer(
    host="127.0.0.1",
    port=25566,
    hybrid_connector=None
)

# 启动服务器
await server.start()

# 停止服务器
await server.stop()
```

### HybridConnector

混合P2P连接器，支持FastLink和WebRTC双协议。

```python
from connector.hybrid_connector import HybridConnector

connector = HybridConnector(
    prefer_protocol=ProtocolType.FASTLINK,
    enable_webrtc_fallback=True
)

# 启动连接器
await connector.start()

# 建立P2P连接
success = await connector.connect(
    target_id="node-id",
    target_host="192.168.1.100",
    target_port=25565
)

# 创建代理隧道
local_port = await connector.create_proxy_tunnel(
    server_id="server-id",
    target_host="192.168.1.100",
    target_port=25565
)

# 断开连接
await connector.disconnect("node-id")

# 停止连接器
await connector.stop()
```

### P2PServerInfo

P2P服务器信息数据类。

```python
from external.tcp_server import P2PServerInfo

server_info = P2PServerInfo(
    id="server-id",
    name="My Server",
    description="A P2P server",
    host="192.168.1.100",
    port=25565,
    latency=50,
    player_count=3,
    max_players=20,
    version="1.20.6"
)
```

---

## Java API

### MinecraftBC

模组核心入口类。

```java
// 获取实例
MinecraftBC mod = MinecraftBC.getInstance();

// 检查初始化状态
boolean initialized = mod.isInitialized();

// 获取配置
MinecraftBCConfig config = mod.getConfig();

// 获取外部客户端管理器
ExternalClientManager client = mod.getExternalClient();

// 获取网络管理器
P2PNetworkManager network = mod.getNetworkManager();
```

### ExternalClientManager

管理与Python外部客户端的TCP连接。

```java
ExternalClientManager client = MinecraftBC.getInstance().getExternalClient();

// 检查连接状态
boolean connected = client.isConnected();

// 请求连接P2P服务器
client.requestConnect("server-id", "host", port);

// 设置回调
client.setServerListCallback(servers -> {
    // 处理服务器列表更新
});

client.setStatusCallback(status -> {
    // 处理连接状态变化
});
```

### P2PNetworkManager

管理P2P服务器列表和连接。

```java
P2PNetworkManager network = MinecraftBC.getInstance().getNetworkManager();

// 获取服务器列表
List<P2PServerInfo> servers = network.getServerList();

// 连接到服务器
network.connectToServer(serverInfo);

// 添加服务器列表监听器
network.addServerListListener(servers -> {
    // 处理服务器列表更新
});
```

### Platform

跨加载器平台抽象接口。

```java
Platform platform = MinecraftBC.getInstance().getPlatform();

// 获取平台名称
String name = platform.getPlatformName();  // "Fabric" 或 "NeoForge"

// 检查环境
boolean isClient = platform.isClient();
boolean isServer = platform.isServer();

// 在客户端线程执行
platform.executeOnClient(() -> {
    // 客户端代码
});

// 获取玩家信息
String uuid = platform.getClientPlayerUUID();
String name = platform.getClientPlayerName();
```

---

## 配置选项

### Python 配置 (config/default.yaml)

```yaml
# 网络配置
network:
  # 监听端口 (0=自动分配)
  listen_port: 0
  
  # P2P协议偏好
  preferred_protocol: "fastlink"  # fastlink / webrtc / auto
  
  # 启用WebRTC备用
  enable_webrtc_fallback: true
  
  # 外部服务器端口 (模组连接用)
  external_server_port: 25566

# 节点配置
node:
  # 节点名称
  name: "MyNode"
  
  # 节点ID (自动生成)
  # id: "..."

# Minecraft配置
minecraft:
  # Minecraft服务器端口
  server_port: 25565
  
  # 版本
  version: "1.20.6"

# 安全设置
security:
  # 启用DTLS加密
  enable_encryption: true
  
  # 身份密钥路径
  identity_key_path: "identity.pem"

# 日志配置
logging:
  level: "INFO"  # DEBUG / INFO / WARNING / ERROR
  file: "minecraftbc.log"
```

### Java 配置 (minecraftbc.json)

```json
{
  "externalClientEnabled": true,
  "externalClientHost": "127.0.0.1",
  "externalClientPort": 25566,
  "modVersion": 2,
  "autoReconnect": true,
  "debugMode": false,
  "preferredProtocol": "fastlink"
}
```

---

## 事件回调

### Python

```python
# 连接建立回调
connector.on_connection_established = lambda target_id, info: print(f"Connected to {target_id}")

# 连接断开回调
connector.on_connection_closed = lambda target_id: print(f"Disconnected from {target_id}")

# 数据接收回调
connector.on_data_received = lambda target_id, data: print(f"Received {len(data)} bytes from {target_id}")
```

### Java

```java
// 服务器列表更新回调
ExternalClientManager client = MinecraftBC.getInstance().getExternalClient();
client.setServerListCallback(servers -> {
    for (P2PServerInfo server : servers) {
        System.out.println("Server: " + server.name);
    }
});

// 状态变化回调
client.setStatusCallback(status -> {
    System.out.println("Connection status: " + status);
});
```

---

## 错误码

| 代码 | 描述 | 解决方案 |
|------|------|----------|
| 0x01 | 连接超时 | 检查网络连接 |
| 0x02 | 协议版本不匹配 | 更新模组或外部服务器 |
| 0x03 | 认证失败 | 检查身份密钥 |
| 0x04 | NAT穿透失败 | 启用WebRTC备用 |
| 0x05 | 代理隧道创建失败 | 检查端口占用 |

---

## 示例代码

### 完整Python服务器

```python
import asyncio
from src.external.server import ExternalServer

async def main():
    server = ExternalServer(
        tcp_port=25566,
        prefer_protocol="fastlink"
    )
    
    await server.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 连接到P2P服务器

```python
from src.connector.hybrid_connector import HybridConnector

async def connect():
    connector = HybridConnector()
    await connector.start()
    
    # 创建代理隧道
    local_port = await connector.create_proxy_tunnel(
        server_id="friend-server",
        target_host="192.168.1.100",
        target_port=25565
    )
    
    print(f"Connect to 127.0.0.1:{local_port}")
    
    await connector.stop()
```

---

**文档版本:** minecraftBC HighIsland v26.15-20260606-RC
