# minecraftBC 版本说明

## 当前版本: v26.1-20260523

### 版本号格式

```
v[YY].[COMMITS]-[YYYYMMDD]
```

- **YY**: 年份后二位 (2026 → 26)
- **COMMITS**: 仓库提交计数 (首个版本为1)
- **YYYYMMDD**: 发布日期 (2026-05-23 → 20260523)

---

## v26.1-20260523 (Initial Release)

**发布日期**: 2026-05-23
**版本类型**: 初始发布

### 包含功能

#### 核心功能
- ✅ 双协议P2P连接器 (FastLink + WebRTC)
- ✅ LAN注入器 - 拦截原版"对局域网开放"
- ✅ TCP桥接器 - 端到端连接转发
- ✅ 加密模块 - Ed25519/X25519
- ✅ 配置管理 - YAML/JSON支持

#### Minecraft支持
- ✅ 多版本协议适配 (1.12.2 - 1.20.x)
- ✅ 离线模式支持
- ✅ 世界自动广播与发现
- ✅ 玩家连接管理

#### 开发质量
- ✅ 完整代码审计 (25个问题已识别，10处已修复)
- ✅ 基础单元测试 (12个测试用例)
- ✅ 5份技术文档 (~2,000行)
- ✅ 模块化架构设计

### 文件统计

```
源代码:        ~5,800 行
测试代码:        ~250 行
文档:          ~2,000 行
配置文件:        ~100 行
---------------------------------
总计:          ~8,150 行
```

### 模块清单

| 模块 | 文件数 | 主要功能 |
|------|--------|----------|
| connector | 4 | 双协议连接器 |
| protocol/fastlink | 6 | FastLink协议 |
| protocol/webrtc | 4 | WebRTC备用协议 |
| protocol/mnmcp | 4 | 跨游戏协议 |
| minecraft | 4 | Minecraft集成 |
| config | 3 | 配置管理 |
| tests | 3 | 单元测试 |
| docs | 5 | 技术文档 |

### 依赖

```
必需:
- Python 3.9+
- cryptography>=41.0.0
- pyyaml>=6.0.1

可选:
- aiortc>=0.9.0 (WebRTC支持)
- pytest>=7.4.0 (测试)
```

### 已知问题

| 问题 | 状态 | 计划 |
|------|------|------|
| FastLink Python重实现 | ✅ 可用 | Rust修复后自动切换 |
| WebRTC可选依赖 | ✅ 可用 | 需手动安装aiortc |
| TCP端口转发 | 🚧 待测试 | 本版本新增，待验证 |
| bare except | ✅ 已修复 | 全部10处已修复 |

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/minecraftBC.git
cd minecraftBC

# 安装依赖
pip install -r requirements.txt

# 可选: WebRTC支持
pip install aiortc

# 运行
python -m src.main p2p --help
```

### 快速开始

```bash
# 主机端 - 托管世界
python -m src.main lan --mc-port 25565 --world-name "My World"

# 客户端 - 发现世界
python -m src.main client

# 或直接连接
python -m src.main client --server <NODE_ID>
```

---

## 版本历史

### v26.1-20260523
- 初始发布
- 双协议P2P支持
- LAN注入器实现
- TCP桥接器实现
- 完整文档

---

## 未来版本规划

### v26.2-2026XXXX (Phase 2)
- 集成测试
- TCP端口转发验证
- 性能优化
- 错误处理改进

### v27.X-2026XXXX (Phase 3 - FastLink集成)
- PyO3 Rust绑定
- BirthdayPunch NAT穿透
- 多路径聚合
- 性能基准测试

---

**维护者**: minecraftBC Team
**许可证**: MIT
**仓库**: https://github.com/yourusername/minecraftBC
