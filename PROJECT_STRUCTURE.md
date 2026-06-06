# minecraftBC Project Structure
# minecraftBC 项目结构

```
minecraftBC/
├── README.md                          # 项目说明文档
├── PROJECT_STRUCTURE.md               # 本文件 - 项目结构说明
├── LICENSE                            # MIT 许可证
├── requirements.txt                   # Python 依赖
├── setup.py                           # 安装脚本
│
├── config/
│   └── default.yaml                   # 默认配置文件
│
├── data/
│   └── mappings/                      # 游戏数据映射表
│       ├── block_mapping.json         # 方块映射 (26个通用方块)
│       ├── entity_mapping.json        # 实体映射 (30个通用实体)
│       └── item_mapping.json          # 物品映射 (40个通用物品)
│
├── docs/
│   └── protocol/                      # 协议文档
│       ├── fastlink-p2p.md            # FastLink P2P 协议规范
│       ├── fastlink-server.md         # FastLink Server 协议规范
│       └── mnmcp.md                   # MnMCP 跨游戏协议规范
│
└── src/                               # 源代码
    ├── __init__.py                    # 包初始化
    ├── main.py                        # 主程序入口 (CLI)
    │
    ├── minecraft/                     # Minecraft 专用模块
    │   └── version_manager.py         # 版本管理器 (支持 1.12.2-1.20.x)
    │
    ├── network/                       # 网络连接层
    │   ├── connector.py               # 统一连接器 (P2P/Server/Client)
    │   └── discovery.py               # 节点发现 (mDNS + Signaling)
    │
    └── protocol/                      # 协议实现
        ├── fastlink/                  # FastLink 协议
        │   ├── packet.py              # 数据包定义 (24字节头部 + JSON负载)
        │   ├── p2p.py                 # P2P 协议 (BirthdayPunch NAT穿透)
        │   └── server.py              # Server 协议 (房间系统)
        │
        └── mnmcp/                     # MnMCP 中间人代理
            ├── proxy.py               # 代理核心 (通用游戏适配)
            ├── mapping.py             # 映射管理器
            └── adapters/
                └── minecraft.py       # Minecraft 适配器
```

## 核心功能模块

### 1. FastLink P2P (`src/protocol/fastlink/p2p.py`)
- **BirthdayPunch NAT 穿透**: 99%+ 成功率
- **ISP 特定端口预测**: 电信/联通/移动
- **DTLS 加密**: 安全通信
- **自动重连**: 心跳保活机制

### 2. FastLink Server (`src/protocol/fastlink/server.py`)
- **房间系统**: 创建/加入/离开房间
- **权限管理**: Owner/Admin/Mod/Member/Visitor
- **5D 路由**: 延迟/丢包/跳数/ISP/距离
- **状态同步**: 玩家位置、世界数据

### 3. MnMCP 代理 (`src/protocol/mnmcp/`)
- **通用游戏适配器接口**: 支持任意游戏
- **双向协议转换**: 实体/方块/物品/事件
- **完整映射表**: 26个方块 + 30个实体 + 40个物品
- **延迟优化**: 速率限制和批量更新

### 4. 网络发现 (`src/network/discovery.py`)
- **mDNS**: 局域网自动发现
- **Signaling**: 广域网信令服务器
- **统一接口**: 自动合并发现结果

### 5. Minecraft 版本管理 (`src/minecraft/version_manager.py`)
- **多版本支持**: 1.12.2, 1.16.5, 1.17.1, 1.18.2, 1.19.2, 1.19.4, 1.20.1, 1.20.4
- **协议版本检测**: 自动推断协议号
- **版本兼容性检查**: 判断版本间兼容性

## 映射预设表

### 方块映射 (26个)
- 基础方块: stone, dirt, grass_block, cobblestone
- 资源: coal_ore, iron_ore, gold_ore, diamond_ore
- 植物: log_oak, leaves_oak, sapling_oak
- 功能: chest, furnace, crafting_table, torch
- 红石: redstone_wire
- 特殊: bedrock, glass, water, lava

### 实体映射 (30个)
- 玩家: player
- 敌对生物: zombie, skeleton, creeper, spider, enderman
- 被动生物: pig, cow, sheep, chicken
- NPC: villager
- 物品: item, arrow, snowball
- 载具: boat, minecart, chest_minecart
- Boss: ender_dragon, wither
- 特殊: blaze, ghast, witch

### 物品映射 (40个)
- 方块物品: stone, dirt, planks_oak
- 原材料: coal, iron_ingot, gold_ingot, diamond, emerald
- 工具材料: stick, flint, string, feather
- 食物: bread, raw/cooked porkchop, raw/cooked beef, raw/cooked chicken
- 种子: wheat_seeds, wheat

## 使用方法

### P2P 模式
```bash
python -m minecraftBC p2p --port 25565 --name MyNode
```

### 服务器模式
```bash
python -m minecraftBC server --port 8765 --room MyRoom
```

### 客户端模式
```bash
python -m minecraftBC client --server localhost:8765 --room MyRoom
```

### MnMCP 跨游戏模式
```bash
python -m minecraftBC mnmcp --mc-port 25565 --adapter miniworld
```

## 技术特性

| 特性 | 实现 |
|------|------|
| NAT 穿透 | BirthdayPunch 算法 (99%+ 成功率) |
| 加密 | DTLS (可选) |
| 传输 | UDP (P2P) / TCP (Server) |
| 发现 | mDNS (LAN) + Signaling (WAN) |
| 协议版本 | FastLink v2.0 |
| 支持游戏 | Minecraft JE, MiniWorld (可扩展) |

## 文件大小统计

| 文件 | 大小 |
|------|------|
| src/protocol/fastlink/server.py | 28.44 KB |
| src/protocol/fastlink/p2p.py | 25.12 KB |
| src/protocol/mnmcp/proxy.py | 26.29 KB |
| src/protocol/fastlink/packet.py | 18.38 KB |
| src/network/discovery.py | 16.27 KB |
| src/protocol/mnmcp/mapping.py | 13.52 KB |
| src/minecraft/version_manager.py | 12.06 KB |
| data/mappings/entity_mapping.json | 14.07 KB |
| data/mappings/block_mapping.json | 13.48 KB |
| data/mappings/item_mapping.json | 12.61 KB |

**总计**: ~180 KB 核心代码 + 40 KB 映射数据

## 许可证

MIT License - 详见 LICENSE 文件
