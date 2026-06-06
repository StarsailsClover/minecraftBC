# FastLink 集成指南

**版本**: v26.1-20260523
**适用于**: minecraftBC v26.1+

---

## 📋 架构总览

```
minecraftBC (Python)
├── src/fastlink/
│   ├── version_manager.py    # 版本管理与锁定
│   ├── compatibility.py      # 兼容性检查
│   ├── auto_updater.py       # 自动更新
│   └── bridge.py             # 桥接层 (subprocess/TCP/HTTP)
│
└── src/connector/
    └── hybrid_connector.py   # 使用bridge作为FastLink实现
```

---

## 🎯 设计目标

1. **接口稳定**: 最小化FastLink版本变更对minecraftBC的影响
2. **向后兼容**: 支持历史版本快速回退
3. **自动管理**: 检测重大更新并提示用户
4. **灵活集成**: 支持多种连接方式

---

## 🔧 版本管理策略

### 版本锁定机制

```
fastlink.lock 文件格式:
{
  "locked_version": "26.1-20260523",
  "updated_at": "2026-05-23T10:00:00",
  "reason": "stable_release"
}
```

**锁定原因**:
- 生产环境稳定版
- 测试阶段锁定
- 用户手动选择

### 更新策略

| 策略 | 行为 |
|------|------|
| `AUTO` | 自动安装所有稳定版更新 |
| `STABLE_ONLY` | 仅安装稳定版，需要手动触发 |
| `LOCKED` | 锁定版本，不自动更新 |

### 兼容性矩阵

| minecraftBC接口 | 最低FastLink版本 |
|-----------------|------------------|
| 1.0 | 26.1-20260523 |
| 1.1 | 26.2-20260525 |

---

## 📦 快速开始

### 1. 基本使用

```python
from src.fastlink.version_manager import FastLinkVersionManager
from src.fastlink.bridge import FastLinkBridge, BridgeConfig

# 初始化版本管理器
version_mgr = FastLinkVersionManager()
await version_mgr.initialize()

# 检查当前版本
current = version_mgr.get_current_version()
print(f"Current FastLink: {current}")

# 检查更新
update = await version_mgr.check_for_updates()
if update:
    print(f"Update available: {update.version}")
```

### 2. 桥接器使用

```python
from src.fastlink.bridge import FastLinkBridge, BridgeConfig

# 配置
config = BridgeConfig(
    mode=BridgeMode.SUBPROCESS,
    fastlink_path=Path("./FastLink"),
    log_fastlink_output=True
)

# 初始化
bridge = FastLinkBridge(config)
await bridge.initialize()

# 启动节点
success = await bridge.start_p2p_node("0.0.0.0:8080")

# 连接对等节点
conn = await bridge.connect_to_peer("peer_node_id", ("host", 8080))

# 停止
await bridge.stop()
```

### 3. 兼容性检查

```python
from src.fastlink.compatibility import CompatibilityChecker

checker = CompatibilityChecker()
report = await checker.check_compatibility()

if not report.is_compatible:
    print(f"Compatibility issues: {report.errors}")
    print(f"Missing features: {report.missing_features}")
else:
    print("All compatibility checks passed")
```

### 4. 自动更新

```python
from src.fastlink.auto_updater import FastLinkUpdater, UpdateConfig

config = UpdateConfig(
    strategy=UpdateStrategy.STABLE_ONLY,
    auto_install=False,  # 手动确认
    notify_on_update=True
)

updater = FastLinkUpdater(config=config)
await updater.initialize()

# 检查并安装
success, version = await updater.check_and_install()
if success:
    print(f"Updated to {version}")
```

---

## 🔄 集成到minecraftBC主程序

### 修改后的主程序入口

```python
# src/main.py 新增部分

async def init_fastlink(args, settings):
    """初始化FastLink集成"""
    from src.fastlink.version_manager import FastLinkVersionManager
    from src.fastlink.compatibility import CompatibilityChecker
    from src.fastlink.bridge import FastLinkBridge
    from src.fastlink.auto_updater import FastLinkUpdater
    
    # 1. 版本管理
    version_mgr = FastLinkVersionManager()
    await version_mgr.initialize()
    
    # 2. 兼容性检查
    checker = CompatibilityChecker()
    report = await checker.check_compatibility()
    if not report.is_compatible:
        logger.error(f"FastLink incompatible: {report}")
        sys.exit(1)
    
    # 3. 检查更新 (如果启用)
    if args.check_updates:
        update = await version_mgr.check_for_updates()
        if update:
            logger.info(f"FastLink update available: {update.version}")
    
    # 4. 初始化桥接器
    config = BridgeConfig(
        mode=BridgeMode.SUBPROCESS,
        fastlink_path=settings.p2p.fastlink_path,
    )
    
    bridge = FastLinkBridge(config)
    await bridge.initialize()
    
    return bridge
```

---

## 🛠️ 开发指南

### 添加新特性支持

1. **更新特性矩阵** (`compatibility.py`):
```python
REQUIRED_FEATURES = {
    "1.0": {FeatureFlag.BIRTHDAY_PUNCH, ...},
    "1.1": {FeatureFlag.BIRTHDAY_PUNCH, FeatureFlag.MULTI_PATH, ...},
}
```

2. **更新兼容性矩阵** (`version_manager.py`):
```python
COMPATIBILITY_MATRIX = {
    "1.0": "26.1-20260523",
    "1.1": "26.2-20260525",
}
```

### 添加新的桥接模式

在 `bridge.py` 中实现:
```python
async def _init_new_mode(self) -> bool:
    # 实现新模式的初始化
    pass
```

---

## ⚠️ 已知限制

| 限制 | 说明 | 解决方案 |
|------|------|----------|
| CLI是占位符 | FastLink v26.5的CLI仅打印日志 | 等v27+完善后使用 |
| 无PyO3绑定 | 无法直接调用Rust API | 当前使用subprocess |
| 构建依赖Rust | 需要cargo工具链 | 提供预编译二进制 |

---

## 🔮 未来计划

### v26.2 (当前)
- [x] 版本管理系统
- [x] 兼容性检查
- [x] 自动更新
- [x] Subprocess桥接

### v27 (FastLink完善后)
- [ ] TCP守护进程模式
- [ ] HTTP REST API
- [ ] PyO3绑定支持
- [ ] 预编译二进制下载

---

## 📞 与FastLink开发者协作

作为FastLink开发者，你可以:
1. 更新 `COMPATIBILITY_MATRIX` 中的版本要求
2. 通知minecraftBC团队API变更
3. 提供预编译二进制用于测试

---

## 📚 相关文档

- [FastLink仓库](https://github.com/StarsailsClover/FastLink)
- [FastLink技术文档](https://github.com/StarsailsClover/FastLink/tree/master/workplace)
- [minecraftBC开发文档](./docs/)
