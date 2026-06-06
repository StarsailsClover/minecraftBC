# minecraftBC 工具集

版本: minecraftBC HighIsland v26.15-20260606-RC

---

## 工具列表

### 1. P2P Ping Tool (`p2p_ping.py`)

测试P2P节点连通性和延迟。

**用法:**
```bash
# 发现网络中的节点
python tools/p2p_ping.py --discover --timeout 10

# Ping特定节点
python tools/p2p_ping.py --target <NODE_ID> --count 4
```

**输出示例:**
```
[DISCOVER] Starting discovery for 10 seconds...
[DISCOVER] Found: MyNode (abc123...)
  Addresses: [('192.168.1.100', 25565)]

[PING] Pinging node: abc123...
[PING] Connected! Sending 4 pings...
  Ping 1: 15.2ms
  Ping 2: 12.8ms
  Ping 3: 14.1ms
  Ping 4: 13.5ms

[PING] Statistics:
  Sent: 4
  Received: 4
  Loss: 0.0%
  Min: 12.8ms
  Max: 15.2ms
  Avg: 13.9ms
```

---

### 2. World Host Helper (`host_world.py`)

辅助托管Minecraft世界。

**用法:**
```bash
# 默认配置托管
python tools/host_world.py

# 自定义配置
python tools/host_world.py --world-name "MySurvivalWorld" --port 25565 --protocol fastlink
```

**功能:**
- 自动启动外部服务器
- 启动P2P连接器
- 显示连接信息
- 等待Ctrl+C停止

---

### 3. TCP测试 (`test_tcp_basic.py`)

测试TCP协议通信。

**用法:**
```bash
python test_tcp_basic.py
```

---

## 开发工具

### 代码格式化

```bash
# 格式化Python代码
black src/ tools/

# 排序导入
isort src/ tools/

# 类型检查
mypy src/ tools/
```

### 性能分析

```bash
# 运行性能分析
python -m cProfile -o profile.stats tools/p2p_ping.py --discover

# 查看结果
python -m pstats profile.stats
```

---

## 调试工具

### 网络诊断

```bash
# 检查端口占用
python -c "import socket; sock = socket.socket(); sock.bind(('127.0.0.1', 25566)); print('Port available')"

# 测试UDP连接
python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'test', ('127.0.0.1', 25566))"
```

### 日志分析

```bash
# 实时监控日志
tail -f minecraftbc.log

# 搜索错误
grep "ERROR" minecraftbc.log

# 统计连接数
grep "Connected" minecraftbc.log | wc -l
```

---

## 自动化脚本

### Windows (PowerShell)

```powershell
# start-hosting.ps1
python tools/host_world.ps1 --world-name "MyWorld"
```

### Linux/macOS (Bash)

```bash
# start-hosting.sh
#!/bin/bash
python3 tools/host_world.py --world-name "MyWorld" &
echo $! > hosting.pid
```

---

## 扩展工具

欢迎贡献更多工具！

### 建议的工具

- `bandwidth_test.py` - 带宽测试
- `network_scanner.py` - 网络扫描
- `config_generator.py` - 配置生成器
- `update_checker.py` - 更新检查

### 工具开发指南

1. 在 `tools/` 目录创建脚本
2. 使用标准argparse处理参数
3. 添加文档字符串
4. 测试通过后提交PR

---

**文档版本:** minecraftBC HighIsland v26.15-20260606-RC
