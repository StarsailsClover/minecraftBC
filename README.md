# minecraftBC HighIsland v26.13-20260606-RC

Minecraft 桥接连接器 - 双协议P2P联机与跨游戏互联解决方案

**English** | [中文](#中文说明)

---

## 仓库结构

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
| 双协议P2P | 完成 | FastLink (主) + WebRTC (备用) |
| LAN注入 | 完成 | 拦截"对局域网开放"，共享到P2P网络 |
| 零配置NAT穿透 | 完成 | 自动ICE/STUN，无需端口映射 |
| 多版本支持 | 完成 | 1.12.2 - 1.20.x |
| 离线模式 | 完成 | 无需正版验证 |
| Minecraft Mod | 完成 | Fabric/NeoForge双加载器支持 |

### 使用方式

方式A: Python外部服务器 (无需安装模组)
```bash
pip install -r requirements.txt
python -m src.main p2p --port 0 --name MyNode
```

方式B: 模组 + 外部服务器 (推荐)
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

## 技术架构 HighIsland

```
HighIsland (minecraftBC v2.0)
|
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

## 版本命名

本项目采用大版本命名制：

```
minecraftBC 大版本号 v{YY}.{COMMITS}-{YYYYMMDD}-{TYPE}

当前: minecraftBC HighIsland v26.13-20260606-RC

说明:
- minecraftBC: 项目名称
- HighIsland: 大版本号命名 (每50个提交一个新版本名)
- 26: 年份2026后两位
- 13: 当前提交计数
- 20260606: 日期 (YYYYMMDD)
- RC: 版本类型 (RC=Release Candidate, Stable=稳定版)
```

---

## FastLink集成

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
| 版本自动检查 | 完成 | 自动检测FastLink更新 |
| 版本锁定 | 完成 | 锁定到稳定版本 |
| 兼容性检查 | 完成 | 启动前验证接口兼容 |
| 自动回滚 | 完成 | 更新失败自动回退 |
| 多桥接模式 | 完成 | Subprocess/TCP/HTTP |

---

## 快速开始

### 环境准备

```bash
# 克隆仓库
git clone https://github.com/StarsailsClover/minecraftBC.git
cd minecraftBC

# 安装Python依赖
pip install -r requirements.txt
```

### 启动P2P节点

```bash
# 方式1: 简单模式
python -m src.main p2p

# 方式2: 完整配置
python -m src.main p2p \
    --port 0 \
    --name MyNode \
    --mc-port 25565 \
    --disable-webrtc
```

### 连接世界

```bash
# 发现世界
python -m src.main client

# 连接到指定节点
python -m src.main client --server <NODE_ID>
```

---

## 项目结构

```
minecraftBC/
├── src/
│   ├── main.py                 # CLI入口
│   ├── cli/                    # 命令行接口
│   │   ├── commands.py
│   │   └── parser.py
│   ├── config/                 # 配置管理
│   │   ├── settings.py
│   │   └── __init__.py
│   ├── connector/              # 连接器
│   │   ├── hybrid_connector.py
│   │   └── __init__.py
│   ├── external/               # 外部服务器
│   │   ├── tcp_server.py
│   │   └── server.py
│   ├── minecraft/              # Minecraft集成
│   │   ├── lan_injector.py
│   │   └── proxy_handler.py
│   ├── protocol/               # 协议实现
│   │   ├── fastlink/
│   │   ├── webrtc/
│   │   └── mnmcp/
│   └── network/                # 网络层
│       ├── discovery.py
│       └── connector.py
├── mod/                        # Minecraft模组源代码
│   ├── common/
│   ├── fabric/
│   └── neoforge/
├── data/                       # 数据文件
│   ├── mappings/
│   └── icons/
├── tests/                      # 测试
├── docs/                       # 文档
├── requirements.txt
├── setup.py
└── README.md
```

---

## 开发

### 本地开发

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest

# 代码格式化
black src/
isort src/

# 类型检查
mypy src/
```

### 构建发布

```bash
# 构建Python包
python setup.py sdist bdist_wheel

# 构建Minecraft模组
cd mod && ./gradlew build
```

---

## 参与贡献

欢迎提交Issue和PR！

### 贡献流程

1. Fork仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 免责声明

本项目仅供学习和技术研究使用。使用本项目进行联机游戏时，请遵守相关游戏的服务条款。

作者不对因使用本项目造成的任何损失承担责任。

---

## 致谢

- FastLink协议贡献者
- Architectury团队 (多加载器框架)
- Fabric和NeoForge社区
- Mixin项目

---

**minecraftBC HighIsland v26.13-20260606-RC**

**状态: Release Candidate (候选发布版)**
