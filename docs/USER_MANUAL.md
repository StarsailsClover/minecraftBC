# minecraftBC 用户操作手册

版本: minecraftBC HighIsland v26.15-20260606-RC

---

## 目录

1. [快速开始](#快速开始)
2. [安装指南](#安装指南)
3. [使用教程](#使用教程)
4. [常见问题](#常见问题)
5. [故障排除](#故障排除)

---

## 快速开始

### 5分钟上手

```bash
# 1. 克隆仓库
git clone https://github.com/StarsailsClover/minecraftBC.git
cd minecraftBC

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动外部服务器
python -m src.external.server --port 25566

# 4. 构建并安装Minecraft模组
cd mod && ./gradlew build
# 复制 mod/fabric/build/libs/*.jar 到 .minecraft/mods/

# 5. 启动Minecraft，开始P2P联机！
```

---

## 安装指南

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| Python | 3.11 | 3.12 |
| Java | 21 | 21 LTS |
| Minecraft | 1.16.5 | 1.20.6 |
| 内存 | 4GB | 8GB |
| 网络 | 宽带 | 光纤 |

### Python环境安装

**Windows:**
```powershell
# 下载Python 3.11
# https://www.python.org/downloads/release/python-3119/

# 验证安装
python --version
pip --version
```

**Linux/macOS:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3-pip

# macOS
brew install python@3.11
```

### 依赖安装

```bash
pip install -r requirements.txt
```

### Minecraft模组安装

**方法1: 使用模组加载器**

1. 安装 [Fabric](https://fabricmc.net/use/) 或 [NeoForge](https://neoforged.net/)
2. 下载模组JAR文件
3. 复制到 `.minecraft/mods/` 文件夹

**方法2: 手动构建**

```bash
cd mod
./gradlew build
cp fabric/build/libs/*-fabric.jar ~/.minecraft/mods/
```

---

## 使用教程

### 场景A: 托管世界 (主机)

**步骤:**

1. **启动外部服务器**
   ```bash
   python -m src.external.server --port 25566
   ```

2. **启动Minecraft**
   - 创建或打开一个世界
   - 按ESC -> "对局域网开放"
   - 记录端口号 (通常是25565)

3. **你的世界自动出现在P2P网络中**
   - 其他玩家可以在他们的多人游戏中看到

4. **分享节点ID**
   - 查看外部服务器输出的节点ID
   - 告诉朋友: "连接到我的节点 xxxxxx"

### 场景B: 加入世界 (客户端)

**步骤:**

1. **启动外部服务器**
   ```bash
   python -m src.external.server --port 25566
   ```

2. **启动Minecraft**
   - 打开"多人游戏"
   - 等待P2P服务器列表加载
   - 或点击"直接连接"输入 `p2p://节点ID`

3. **点击加入服务器**
   - 自动建立P2P连接
   - 开始游戏！

### 场景C: 命令行模式 (高级)

**托管世界:**
```bash
python -m src.main p2p \
    --port 0 \
    --name "MyWorld" \
    --mc-port 25565
```

**加入世界:**
```bash
python -m src.main client \
    --server "朋友节点ID"
```

---

## 配置指南

### 最小配置

创建 `config.yaml`:

```yaml
network:
  listen_port: 0
  preferred_protocol: "fastlink"

node:
  name: "MyNode"

minecraft:
  version: "1.20.6"
```

### 高级配置

查看 `examples/config/advanced.yaml` 获取完整配置选项。

### 配置文件位置

| 操作系统 | 路径 |
|----------|------|
| Windows | `%appdata%/minecraftbc/config.yaml` |
| Linux | `~/.config/minecraftbc/config.yaml` |
| macOS | `~/Library/Application Support/minecraftbc/config.yaml` |

---

## 常见问题

### Q: 为什么看不到P2P服务器?

**可能原因:**
1. 外部服务器未启动
2. 防火墙阻挡了UDP端口
3. NAT类型不兼容

**解决方案:**
```bash
# 检查外部服务器状态
python -m src.external.server --debug

# 检查防火墙
# Windows: 允许Python通过防火墙
# Linux: sudo ufw allow 25566/tcp
```

### Q: 连接超时怎么办?

**尝试:**
1. 启用WebRTC备用协议
   ```yaml
   network:
     enable_webrtc_fallback: true
   ```

2. 检查双方是否可以访问STUN服务器

3. 使用TURN服务器 (如果处于对称NAT后)

### Q: 模组安装后崩溃?

**检查:**
1. 使用正确版本的Fabric/NeoForge
2. 模组版本与Minecraft版本匹配
3. Java版本为21

### Q: 性能问题?

**优化建议:**
```yaml
performance:
  worker_threads: 4
  udp_buffer_size: 2048
```

---

## 故障排除

### 诊断工具

```bash
# 网络诊断
python -m src.main diagnose

# 测试TCP连接
python test_tcp_basic.py

# 检查FastLink状态
python -m src.main p2p --check-fastlink
```

### 日志分析

**日志位置:**
- 默认: `minecraftbc.log`
- 调试: 启动时添加 `--debug`

**关键日志:**
```
[INFO] TCP server started on 127.0.0.1:25566
[INFO] P2P node started, ID: xxxxxx
[INFO] Connected to external client
[INFO] Server list updated: 3 servers
```

### 错误代码

| 错误 | 原因 | 解决 |
|------|------|------|
| 0x01 | 连接超时 | 检查网络 |
| 0x02 | 版本不匹配 | 更新软件 |
| 0x03 | 认证失败 | 检查密钥 |
| 0x04 | NAT穿透失败 | 启用备用 |

---

## 最佳实践

### 安全建议

1. **仅与信任的玩家联机**
2. **定期备份世界存档**
3. **使用强身份密钥**
4. **不要分享节点ID给陌生人**

### 性能优化

1. **使用有线网络连接**
2. **关闭不必要的背景程序**
3. **分配足够的内存给Minecraft**
4. **选择地理位置近的玩家联机**

---

## 获取帮助

### 资源

- **GitHub Issues:** https://github.com/StarsailsClover/minecraftBC/issues
- **文档:** https://github.com/StarsailsClover/minecraftBC/wiki
- **讨论:** https://github.com/StarsailsClover/minecraftBC/discussions

### 报告问题

提供以下信息:
1. 操作系统版本
2. Python版本
3. Minecraft版本
4. 模组版本
5. 错误日志
6. 复现步骤

---

## 更新日志

### HighIsland v26.15-20260606-RC

- 新增: TCP服务器测试通过
- 新增: API参考文档
- 新增: 用户操作手册
- 优化: 构建指南

---

**文档版本:** minecraftBC HighIsland v26.15-20260606-RC
