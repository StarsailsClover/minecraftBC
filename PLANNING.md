# minecraftBC 改进开发计划

## 目标调整

基于市场调研，minecraftBC的核心差异化价值：**开源的Minecraft P2P联机方案，支持NAT穿透+局域网开放组合**。

## 双协议接口预留设计

```
minecraftBC 架构调整
├── protocol/
│   ├── fastlink/           # FastLink协议实现（保留）
│   │   ├── p2p.py         # BirthdayPunch NAT穿透
│   │   └── server.py      # 轻服务器组网
│   ├── webrtc/            # 🆕 WebRTC备用协议
│   │   ├── ice_client.py  # ICE连接客户端
│   │   └── turn_relay.py  # TURN中继支持
│   └── mnmcp/             # MnMCP跨游戏（保留）
├── connector/
│   ├── fastlink_connector.py   # FastLink连接管理
│   ├── webrtc_connector.py   # 🆕 WebRTC连接管理
│   └── hybrid_connector.py     # 🆕 双协议自动选择
└── minecraft/
    ├── lan_injector.py    # 🆕 局域网开放注入
    └── proxy_handler.py   # 代理处理器
```

## Phase 1: 双协议接口预留 (本周)

### 1.1 创建WebRTC协议层桩代码

文件：`src/protocol/webrtc/__init__.py`

```python
"""
WebRTC备用协议实现
用于FastLink穿透失败时回退到WebRTC ICE
"""

class WebRTCConnector:
    """
    WebRTC连接器 - 双协议备用方案
    
    设计目标:
    1. 与FastLinkConnector接口兼容
    2. 支持ICE + TURN中继
    3. 自动协议降级
    """
    pass
```

### 1.2 创建混合连接器

文件：`src/connector/hybrid_connector.py`

```python
class HybridConnector:
    """
    双协议混合连接器
    
    策略:
    1. 优先尝试FastLink (低延迟)
    2. 失败时降级到WebRTC (高兼容)
    3. 运行时动态切换
    """
    pass
```

### 1.3 Minecraft局域网注入器

文件：`src/minecraft/lan_injector.py`

```python
class LANInjector:
    """
    Minecraft局域网开放注入器
    
    功能:
    1. 拦截原版"对局域网开放"
    2. 将本地端口映射到P2P连接
    3. 自动广播到P2P网络
    """
    pass
```

## Phase 2: FastLink修复接口 (并行)

为FastLink预留修复后的对接接口：

```python
# src/protocol/fastlink/rust_bridge.py
"""
FastLink Rust库的Python绑定接口预留

当FastLink修复完成后，使用PyO3替换Python重实现
"""

class FastLinkRustBridge:
    """
    Rust库调用接口
    
    当前: Python重实现
    目标: PyO3绑定Rust库
    """
    pass
```

## 关键TODO修复清单

| 文件 | 问题 | 优先级 | 修复方案 |
|------|------|--------|----------|
| `src/network/connector.py:76` | `# TODO: Implement client connection` | 🔴 P0 | 实现客户端连接逻辑 |
| `src/protocol/fastlink/p2p.py:142` | `public_key="" # TODO: Add actual key` | 🔴 P0 | 集成Ed25519密钥生成 |
| `src/protocol/fastlink/packet.py` | 缺少Minecraft协议包封装 | 🟡 P1 | 添加MC协议适配层 |
| `src/minecraft/` | 缺少实际MC协议处理 | 🟡 P1 | 实现握手/登录/游戏状态机 |

## 本周开发任务分解

### 任务1: 双协议接口设计 (2天)
- [ ] 定义Connector统一接口
- [ ] 设计协议降级策略
- [ ] 创建协议抽象基类

### 任务2: WebRTC桩实现 (1天)
- [ ] 创建webrtc包结构
- [ ] 实现接口兼容层
- [ ] 添加配置开关

### 任务3: 修复现有TODO (2天)
- [ ] 实现client connection
- [ ] 集成密钥生成
- [ ] 添加基础加密

### 任务4: LAN注入器设计 (1天)
- [ ] 研究Minecraft局域网广播机制
- [ ] 设计注入点
- [ ] 实现广播拦截

## 需要新引入的依赖

```txt
# requirements.txt新增
cryptography>=3.4.8  # Ed25519密钥
typing-extensions>=4.0.0

# WebRTC相关（Phase 2使用）
# aiortc>=0.9.0      # Python WebRTC实现
```

## 代码审查检查点

根据code-review技能，每个Phase需要审查：

- [ ] **Security**: 密钥生成是否安全
- [ ] **Correctness**: 协议降级逻辑是否正确
- [ ] **Maintainability**: 接口是否清晰可扩展
- [ ] **Testing**: 需要模拟NAT环境测试
