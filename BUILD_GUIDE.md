# MinecraftBC Mod 构建指南

## 前置要求

1. **Java Development Kit (JDK) 21**
   - 下载: https://adoptium.net/temurin/releases/?version=21
   - 验证: `java -version`

2. **Gradle 8.7+**
   - 下载: https://gradle.org/releases/
   - 或使用IDE内置Gradle

3. **IDE (推荐)**
   - IntelliJ IDEA (推荐)
   - Eclipse + BuildShip
   - VS Code + Gradle扩展

## 构建步骤

### 方法1: 使用IDE

1. 打开IntelliJ IDEA
2. File -> Open -> 选择 `mod/` 目录
3. 等待Gradle同步完成
4. 点击右侧Gradle面板 -> `mod` -> `Tasks` -> `build` -> `build`

### 方法2: 命令行

```bash
cd mod

# 下载Gradle Wrapper (首次)
gradle wrapper --gradle-version 8.7

# 构建所有模块
./gradlew build

# 或构建特定模块
./gradlew :fabric:build
./gradlew :neoforge:build
./gradlew :common:build
```

## 输出位置

构建成功后，JAR文件位于:

```
mod/
├── fabric/build/libs/*.jar       # Fabric模组
├── neoforge/build/libs/*.jar     # NeoForge模组
└── common/build/libs/*.jar       # Common库
```

## 安装模组

将 `-fabric.jar` 或 `-neoforge.jar` 复制到:

- Windows: `%appdata%/.minecraft/mods/`
- Linux: `~/.minecraft/mods/`
- macOS: `~/Library/Application Support/minecraft/mods/`

## 常见问题

### Q: Gradle sync失败?
**A:** 检查网络连接，确保可以访问Maven仓库

### Q: 缺少Minecraft依赖?
**A:** 确保使用了正确的Gradle插件 (`dev.architectury.loom`)

### Q: Mixin编译错误?
**A:** 检查 `minecraftbc.mixins.json` 配置

### Q: Access Widener警告?
**A:** 这是正常的，用于访问Minecraft私有成员

## 开发调试

### 运行测试客户端

```bash
./gradlew :fabric:runClient
./gradlew :neoforge:runClient
```

### 调试模式

在IDE中:
1. 创建Run Configuration
2. 选择 `Minecraft Client (fabric)` 或类似
3. 点击Debug按钮

## 版本兼容性

| Minecraft | Fabric | NeoForge |
|-----------|--------|----------|
| 1.21.1 | ✅ | ✅ |
| 1.20.6 | ✅ | ✅ |
| 1.20.4 | ✅ | ✅ |
| 1.20.1 | ✅ | ✅ |
| 1.19.2 | ✅ | ❌ |
| 1.18.2 | ✅ | ❌ |
| 1.16.5 | ✅ | ❌ |

## 构建配置

### 修改Minecraft版本

编辑 `mod/gradle.properties`:

```properties
minecraft_version=1.20.6
fabric_loader_version=0.15.11
neoforge_version=20.6.78-beta
```

### 修改模组版本

编辑 `mod/gradle.properties`:

```properties
mod_version=2.0.0
```

## 自动构建脚本

### Windows (PowerShell)

```powershell
# build.ps1
$gradle = Get-Command gradle -ErrorAction SilentlyContinue

if (-not $gradle) {
    Write-Host "Error: Gradle not found"
    Write-Host "Please install Gradle: https://gradle.org/install/"
    exit 1
}

Push-Location mod

try {
    if (-not (Test-Path "gradlew.bat")) {
        Write-Host "Creating Gradle Wrapper..."
        gradle wrapper --gradle-version 8.7
    }
    
    Write-Host "Building mod..."
    .\gradlew.bat clean build
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Build successful!"
        Write-Host "Output:"
        Get-ChildItem "fabric/build/libs/*.jar" | ForEach-Object { "  $_" }
        Get-ChildItem "neoforge/build/libs/*.jar" | ForEach-Object { "  $_" }
    }
}
finally {
    Pop-Location
}
```

## 下一步

构建成功后:
1. 安装模组到 `.minecraft/mods/`
2. 启动Python外部服务器
3. 启动Minecraft测试联机功能

---

**注意:** 当前需要通过IDE或手动安装Gradle来构建。
命令行构建需要完整配置Gradle环境。
