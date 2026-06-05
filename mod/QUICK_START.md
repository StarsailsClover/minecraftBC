# MinecraftBC Mod - Quick Start

## 项目状态

✅ **架构完成** - 多加载器模组 + Python外部客户端
✅ **协议定义** - TCP通信协议已对齐
✅ **核心代码** - Java模组和Python服务器框架
🔄 **待完成** - 构建测试和端到端联调

## 文件结构

```
minecraftBC-MCMod/           # Java模组
├── build.gradle
├── settings.gradle
├── gradle.properties
├── common/                    # 跨平台代码
│   ├── src/main/java/
│   │   └── com/minecraftbc/
│   │       ├── core/         # MinecraftBC.java, Platform.java
│   │       ├── external/     # ExternalClientManager.java
│   │       ├── network/      # P2PNetworkManager.java
│   │       ├── config/       # MinecraftBCConfig.java
│   │       └── mixin/        # Mixins for connection hijacking
│   └── src/main/resources/
│       ├── minecraftbc.mixins.json
│       └── minecraftbc.accesswidener
├── fabric/                    # Fabric实现
├── neoforge/                  # NeoForge实现
└── forge/                     # (预留)

minecraftBC/                   # Python外部客户端
├── src/
│   ├── external/
│   │   ├── tcp_server.py     # TCP服务器（与模组通信）
│   │   └── server.py         # 外部服务入口
│   └── connector/
│       └── hybrid_connector.py # 更新版（支持代理隧道）
└── requirements.txt
```

## 核心协议

### TCP通信 (模组 ↔ Python)

```
[Length: 4字节大端] [Type: 1字节] [Payload: N字节]

包类型:
0x01 HEARTBEAT      - 心跳
0x02 HANDSHAKE      - 握手
0x03 SERVER_LIST    - 服务器列表
0x04 CONNECT_REQUEST - 连接请求
0x05 CONNECT_RESPONSE - 连接响应
0x07 ERROR          - 错误
```

### 工作流程

```
1. 启动外部服务器
   $ python -m src.external.server --port 25566

2. 启动Minecraft (带模组)
   - 模组自动连接 127.0.0.1:25566
   - 发送握手包 (MC版本, 玩家UUID)

3. 在多人游戏菜单
   - 看到P2P服务器列表
   - 点击"加入服务器"

4. 连接流程
   Mod ──TCP──► External Server
                   │
                   ▼
            Hybrid Connector
                   │
                   ▼
            创建本地代理端口
                   │
                   ▼
   Mod ◄──TCP── 127.0.0.1:30000+
      游戏连接到本地代理
                   │
                   ▼
            P2P隧道 ──► 远程主机
```

## 待办清单

### Java模组
- [ ] 验证Mixin配置 (minecraftbc.mixins.json)
- [ ] 创建完整Access Widener
- [ ] 添加Architectury依赖配置
- [ ] 测试编译: `./gradlew :common:build`
- [ ] 测试运行: `./gradlew :fabric:runClient`

### Python外部客户端
- [ ] 验证协议实现与Java端对齐
- [ ] 测试TCP服务器启动
- [ ] 实现完整的P2P节点发现
- [ ] 创建代理隧道双向转发

### 端到端
- [ ] 模组连接外部服务器测试
- [ ] 服务器列表同步测试
- [ ] P2P连接建立测试
- [ ] 游戏数据包转发测试

## 关键类说明

### Java (模组侧)

| 类 | 功能 |
|----|------|
| `MinecraftBC` | 核心入口，初始化所有组件 |
| `ExternalClientManager` | TCP连接管理，协议编解码 |
| `P2PNetworkManager` | 服务器列表管理，连接状态 |
| `MixinConnectScreen` | 拦截连接，重定向到代理 |
| `MixinServerSelectionList` | 注入P2P服务器到列表 |

### Python (外部客户端)

| 类 | 功能 |
|----|------|
| `ExternalTCPServer` | TCP服务器，处理模组连接 |
| `HybridConnector` | P2P连接管理，创建代理隧道 |
| `ExternalServer` | 整合TCP和P2P的主服务 |

## 构建命令

```bash
# 1. 下载Gradle Wrapper (首次)
gradle wrapper --gradle-version 8.7

# 2. 构建Common模块
./gradlew :common:build

# 3. 构建Fabric
./gradlew :fabric:build

# 4. 构建NeoForge
./gradlew :neoforge:build

# 5. 全部构建
./gradlew build
```

## 测试步骤

```bash
# Terminal 1: 启动Python外部服务器
cd minecraftBC
python -m src.external.server --port 25566 --debug

# Terminal 2: 启动Minecraft (开发环境)
cd minecraftBC-MCMod
./gradlew :fabric:runClient
```

## 常见问题

### Q: Mixin不生效？
A: 检查 minecraftbc.mixins.json 配置，确保映射关系正确

### Q: 连接失败？
A: 检查防火墙设置，确保127.0.0.1:25566可访问

### Q: 协议不匹配？
A: 检查Java和Python端的PacketType定义是否一致

## 下一步建议

1. **优先**: 完成Mixin的Access Widener配置
2. **优先**: 测试TCP通信协议
3. **次要**: 实现完整P2P节点发现
4. **后续**: 添加GUI配置界面
