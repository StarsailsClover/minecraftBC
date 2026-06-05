# minecraftBC v2.0 - Minecraft Bridge Connector

Minecraft 桥接连接器 - 双协议P2P联机与跨游戏互联解决方案

**English** | [中文](#中文说明)

## 📁 Repository Structure

```
minecraftBC/
├── src/              # Python External Server
│   ├── external/     # TCP server for mod communication
│   ├── connector/    # Hybrid P2P connector
│   ├── fastlink/     # FastLink protocol
│   └── main.py       # CLI entry point
├── mod/              # Minecraft Mod Source (Java)
│   ├── common/       # Cross-loader shared code
│   ├── fabric/       # Fabric implementation
│   └── neoforge/     # NeoForge implementation
├── requirements.txt  # Python dependencies
└── RELEASE_*.md      # Release notes
```

---

## 中文说明

### 核心特性

| 特性 | 状态 | 说明 |
|------|------|------|
| **双协议P2P** | ✅ | FastLink (主) + WebRTC (备用) |
| **LAN注入** | ✅ | 拦截"对局域网开放"，共享到P2P网络 |
| **零配置NAT穿透** | ✅ | 自动ICE/STUN，无需端口映射 |
| **多版本支持** | ✅ | 1.12.2 - 1.20.x |
| **离线模式** | ✅ | 无需正版验证 |
| **Minecraft Mod** | ✅ | Fabric/NeoForge双加载器支持 |

### 使用方式

方式A: **Python外部服务器** (无需安装模组)
```bash
pip install -r requirements.txt
python -m src.main p2p --port 0 --name MyNode
```

方式B: **模组 + 外部服务器** (推荐)
```bash
# 1. 启动外部服务器
python -m src.external.server --port 25566

# 2. 构建并安装模组
cd mod && ./gradlew build
# 复制 mod/fabric/build/libs/*.jar 到 .minecraft/mods/

# 3. 启动Minecraft，模组自动连接
```

---

### 工作原理

```
[Minecraft主机] --本地连接--> [LANInjector] --P2P广播--> [P2P网络]
                                            |
[Minecraft客户端] <--UDP广播-- [世界发现] <--P2P发现--
```

其他玩家可以在他们的Minecraft"多人游戏"中看到你的世界，就像局域网世界一样！

---

## 技术架构 v2.0

```
minecraftBC v2.0
│
├── 双协议连接器 (HybridConnector)
│   ├── FastLink (主协议) - 低延迟，预留Rust接口
│   └── WebRTC (备用协议) - 高兼容，自动降级
│
├── Minecraft集成
│   ├── LANInjector - 拦截局域网广播
│   ├── ProxyHandler - TCP连接代理
│   └── ProtocolAdapter - 多版本协议适配
│
├── 跨游戏 (MnMCP)
│   ├── MappingManager - 游戏协议映射
│   ├── Entity/Block/Item映射
│   └── ProxyCore - 中间人代理
│
├── 安全
│   ├── Ed25519 - 节点身份签名
│   ├── X25519 - 密钥交换
│   └── DTLS加密 - 数据传输加密
│
└── 配置管理
    ├── YAML/JSON配置
    ├── 多平台支持 (Windows/Linux/macOS)
    └── 自动身份生成
```

---

## FastLink集成 (v26.1+)

### 版本管理

```bash
# 检查FastLink更新
python -m src.main p2p --check-fastlink

# 锁定FastLink版本
python -m src.main p2p --lock-fastlink 26.1-20260523
```

### 特性

| 特性 | 状态 | 说明 |
|------|------|------|
| 版本自动检查 | ✅ | 自动检测FastLink更新 |
| 版本锁定 | ✅ | 锁定到稳定版本 |
| 兼容性检查 | ✅ | 启动前验证接口兼容 |
| 自动回滚 | ✅ | 更新失败自动回退 |
| 多桥接模式 | ✅ | Subprocess/TCP/HTTP |

### 架构

```
minecraftBC
├── src/fastlink/
│   ├── version_manager.py    # 版本管理与锁定
│   ├── compatibility.py      # 接口兼容性检查
│   ├── auto_updater.py       # 自动更新
│   └── bridge.py             # 桥接层 (subprocess/TCP/HTTP)
│
└── src/connector/
    └── hybrid_connector.py   # 使用bridge作为FastLink实现
```

### 使用方式

```python
from src.fastlink.bridge import FastLinkBridge, BridgeConfig

# 配置
config = BridgeConfig(
    mode=BridgeMode.SUBPROCESS,
    fastlink_path=Path("./FastLink")
)

# 初始化
bridge = FastLinkBridge(config)
await bridge.initialize()

# 启动节点
await bridge.start_p2p_node("0.0.0.0:8080")

# 连接对等节点
conn = await bridge.connect_to_peer("node_id", ("host", 8080))
```

### FastLink双协议预留

当前实现使用Python重实现，FastLink Rust库修复后自动切换：

```python
# 预留接口 (src/connector/hybrid_connector.py)
class HybridConnector:
    def __init__(self):
        # 当前: Python重实现
        self._fastlink_connector: Optional[P2PConnection] = None
        
        # FastLink修复后: PyO3绑定
        # self._fastlink_connector: Optional[FastLinkRustBridge] = None
```

预留能力字段:
- `supports_birthday_punch`: BirthdayPunch NAT穿透
- `supports_multipath`: 多路径聚合
- `supports_qos_evasion`: QoS规避

---

## 文件清单

```
minecraftBC/
├── src/
│   ├── main.py                          # 主程序入口
│   ├── connector/                       # 双协议连接器
│   │   ├── connector_base.py            # 抽象基类
│   │   ├── hybrid_connector.py          # 混合连接器
│   │   └── protocol_type.py             # 协议类型
│   ├── protocol/
│   │   ├── fastlink/                    # FastLink协议
│   │   │   ├── crypto.py                # Ed25519/X25519加密
│   │   │   ├── p2p.py                   # P2P实现
│   │   │   ├── server.py                # 轻服务器
│   │   │   └── packet.py                # 数据包定义
│   │   ├── webrtc/                      # WebRTC备用协议
│   │   │   ├── webrtc_connector.py      # WebRTC连接器
│   │   │   ├── ice_client.py            # ICE客户端
│   │   │   └── signaling.py             # 信令服务器
│   │   └── mnmcp/                       # MnMCP跨游戏
│   │       ├── proxy.py
│   │       ├── mapping.py
│   │       └── adapters/
│   ├── minecraft/                       # Minecraft集成
│   │   ├── lan_injector.py              # LAN注入器 ⭐
│   │   ├── proxy_handler.py             # TCP代理
│   │   └── protocol_adapter.py          # 协议适配
│   ├── network/                         # 网络层
│   └── config/                          # 配置管理
│       ├── manager.py
│       └── settings.py
├── data/mappings/                       # 游戏映射表
│   ├── block_mapping.json
│   ├── entity_mapping.json
│   └── item_mapping.json
├── docs/                                # 文档
│   ├── DEVELOPMENT_SUMMARY.md           # 开发总结
│   ├── CODE_REVIEW.md                   # 代码审查
│   ├── MARKET_RESEARCH.md               # 市场调研
│   └── PLANNING.md                      # 开发计划
├── config/
│   └── default.yaml
├── requirements.txt
├── setup.py
└── README.md
```

---

## 市场定位

### 竞品对比

| 方案 | P2P | 开源 | 离线 | NAT穿透 | 特点 |
|------|-----|------|------|---------|------|
| **minecraftBC** | ✅ | ✅ | ✅ | ✅ | **双协议，自动降级** |
| Essential Mod | ✅ | ❌ | ❌ | ✅ | 闭源，需正版 |
| mcwifipnp | ❌ | ✅ | ✅ | ❌ | 仅局域网扩展 |
| Hamachi | ❌ | ❌ | ✅ | ✅ | VPN，延迟高 |

**核心差异化**: 开源 + P2P直连 + 双协议自动降级

---

## 开发状态

### 已完成 (Phase 1)

- ✅ 双协议接口预留
- ✅ WebRTC备用实现
- ✅ LAN注入器
- ✅ 配置管理
- ✅ 多版本协议适配
- ✅ 加密模块

### 待完成 (Phase 2)

- 🚧 TCP端口转发（玩家实际连接）
- 🚧 玩家列表同步
- 🚧 延迟测量
- 🚧 单元测试
- 🚧 WebRTC可选依赖安装指南

### 等待FastLink (Phase 3)

- ⏸️ PyO3绑定
- ⏸️ BirthdayPunch实现
- ⏸️ 多路径聚合

---

## 快速命令参考

```bash
# P2P模式（托管世界）
python -m src.main p2p --port 0 --name MyNode --mc-port 25565 --world-name "Survival"

# LAN注入器模式
python -m src.main lan --mc-port 25565 --world-name "My World"

# 客户端模式
python -m src.main client

# 带配置文件
python -m src.main p2p --config /path/to/config.yaml

# 详细日志
python -m src.main p2p -v
```

---

## 配置示例

```yaml
# config.yaml
node_name: "My minecraftBC Node"

p2p:
  bind_host: "0.0.0.0"
  bind_port: 0  # 随机端口
  prefer_fastlink: true
  fallback_timeout: 10.0
  stun_servers:
    - "stun:stun.l.google.com:19302"

minecraft:
  mc_version: "1.20.1"
  enable_offline: true
  motd_prefix: "[P2P] "

security:
  key_file: "~/.minecraftBC/node.key"
  enable_encryption: true

logging:
  level: "INFO"
  console_output: true
```

---

## 许可证

MIT License - 详见 [LICENSE](./LICENSE)

---

## 贡献

欢迎贡献！请查看 [PLANNING.md](./PLANNING.md) 了解开发计划。

**特别说明**: FastLink Rust库修复后，将提供PyO3绑定贡献指南。
