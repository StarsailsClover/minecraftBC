# GitHub Release Checklist

**版本号**: v26.1-20260523
**发布日期**: 2026-05-23
**标签**: Initial Release

---

## 版本号说明

格式: `v[YY].[COMMITS]-[YYYYMMDD]`

- `26` - 年份后二位 (2026)
- `1` - 初始提交 (首个版本)
- `20260523` - 发布日期

---

## 发布前检查清单

### 代码质量

- [x] 所有 HIGH 级别问题已修复
- [x] 所有 bare except 子句已修复 (10处)
- [x] 代码通过基础审计
- [x] 核心功能实现完成

### 功能完成度

- [x] 双协议连接器 (FastLink + WebRTC)
- [x] LAN注入器
- [x] TCP桥接器
- [x] 加密模块 (Ed25519/X25519)
- [x] 配置管理
- [x] 协议适配 (1.12.2-1.20.x)
- [ ] 集成测试 (待后续补充)

### 文档

- [x] README.md 已更新
- [x] 开发文档已整理
- [x] 代码注释完整
- [x] 使用示例已提供

### 测试

- [x] 单元测试基础 (crypto, protocol_adapter)
- [ ] 集成测试 (待后续)
- [ ] 性能测试 (待后续)

### 仓库准备

- [x] .gitignore 已创建
- [x] LICENSE 已包含 (MIT)
- [x] 目录结构清晰
- [x] 依赖文件完整 (requirements.txt)

---

## 发布步骤

### 1. 本地准备

```bash
# 确保代码是最新状态
git status

# 检查未提交更改
git diff

# 添加所有文件
git add .

# 提交
git commit -m "Initial release v26.1-20260523

- Dual-protocol P2P connector (FastLink + WebRTC)
- Minecraft LAN injector with P2P bridge
- TCP bridge for player connections
- Ed25519/X25519 encryption
- Multi-version support (1.12.2-1.20.x)
- Configuration management
- Unit tests for core modules
- Complete documentation"

# 创建标签
git tag -a v26.1-20260523 -m "Initial release - minecraftBC v2.0"

# 推送
git push origin main
git push origin v26.1-20260523
```

### 2. GitHub Release

1. 访问仓库页面
2. 点击 "Releases"
3. 点击 "Draft a new release"
4. 选择标签 `v26.1-20260523`
5. 标题: `minecraftBC v26.1-20260523 - Initial Release`
6. 内容 (见下方发布说明)
7. 发布

---

## 发布说明

### minecraftBC v26.1-20260523 - Initial Release

**双协议P2P联机解决方案**

#### 核心特性

🌐 **双协议P2P**
- FastLink (主协议) - 低延迟直连
- WebRTC (备用协议) - 高兼容性自动降级

🎮 **LAN注入器**
- 拦截原版"对局域网开放"
- 自动广播到P2P网络
- 无需配置，即开即玩

🔐 **安全加密**
- Ed25519 节点身份签名
- X25519 密钥交换
- DTLS 数据传输加密

📦 **多版本支持**
- Minecraft 1.12.2 - 1.20.x
- 离线模式支持
- 无需正版验证

#### 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动P2P节点并托管世界
python -m src.main p2p --port 0 --name MyNode --mc-port 25565

# 客户端发现世界
python -m src.main client
```

#### 技术亮点

- **混合连接器**: 自动协议选择和降级
- **TCP桥接**: 完整的端到端连接转发
- **模块化架构**: 清晰的接口预留，FastLink修复后无缝接入
- **全面文档**: 5份技术文档，完整开发记录

#### 已知限制

- FastLink使用Python重实现 (Rust库修复后自动切换)
- WebRTC为可选依赖 (`pip install aiortc` 启用)
- TCP端口转发待实际测试验证

#### 文件统计

- 源代码: ~5,800 行
- 测试代码: ~250 行
- 文档: ~2,000 行
- 总计: 25+ 个源文件

#### 文档

- [README.md](README.md) - 项目说明
- [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md) - 开发总结
- [PLANNING.md](PLANNING.md) - 开发计划
- [CODE_REVIEW.md](CODE_REVIEW.md) - 代码审查
- [MARKET_RESEARCH.md](MARKET_RESEARCH.md) - 市场调研

---

## 发布后任务

- [ ] 创建讨论区帖子
- [ ] 更新项目描述
- [ ] 添加标签和主题
- [ ] 设置议题模板
- [ ] 启用GitHub Actions (CI/CD)

---

## 版本历史

### v26.1-20260523 (Initial Release)
- 双协议P2P连接器
- LAN注入器
- TCP桥接器
- 加密模块
- 多版本协议适配
- 配置管理
- 基础单元测试

---

**Full Changelog**: 首次发布，无历史变更
