# minecraftBC [HighIsland v26.10-20260606-RC]

**Release Date:** 2026-06-06  
**Version:** minecraftBC [HighIsland v26.10-20260606-RC]  
**Status:** Release Candidate (Pre-Release)

---

## Release Contents

This release includes both the **Python External Server** and the **Minecraft Mod source code**.

```
minecraftBC/
├── src/              # Python External Server
├── mod/              # Minecraft Mod Source (Java)
├── requirements.txt  # Python dependencies
└── RELEASE_*.md      # Release notes
```

---

## Version Naming

```
minecraftBC [大版本号 v{YY}.{COMMITS}-{YYYYMMDD}-{TYPE}]

Current: minecraftBC [HighIsland v26.10-20260606-RC]

Format:
- minecraftBC: Project name
- HighIsland: Major version name (new name every 50 commits)
- 26: Year 2026 (last two digits)
- 10: Total commit count
- 20260606: Release date (YYYYMMDD)
- RC: Release Candidate (Stable for production release)
```

---

## Build Instructions

### Python External Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m src.external.server --port 25566
```

### Minecraft Mod

**Requirements:**
- Java 21 JDK
- Gradle (wrapper included)

```bash
# Enter mod directory
cd mod

# Build all loaders
./gradlew build

# Or build specific loader
./gradlew :fabric:build
./gradlew :neoforge:build
```

**Output:**
- Fabric: mod/fabric/build/libs/*.jar
- NeoForge: mod/neoforge/build/libs/*.jar

---

## Quick Start

### Step 1: Start External Server

```bash
python -m src.external.server --port 25566 --debug
```

### Step 2: Build and Install Mod

```bash
cd mod
./gradlew build
# Copy JAR to .minecraft/mods/
cp fabric/build/libs/*-fabric.jar ~/.minecraft/mods/
```

### Step 3: Launch Minecraft

1. Launch with Fabric/NeoForge
2. Mod auto-connects to 127.0.0.1:25566
3. Open Multiplayer menu
4. See P2P servers in list

---

## What's Included

### Python Components (src/)
- TCP server for mod communication
- Hybrid P2P connector (FastLink + WebRTC)
- LAN world injection
- Protocol abstraction layer

### Java Components (mod/)
- Cross-loader support (Fabric/NeoForge)
- TCP communication with Python server
- Mixin-based connection interception
- Server list injection
- Configuration system

---

## Known Issues

- Build configuration needs verification
- P2P node discovery incomplete
- End-to-end testing pending
- Error handling needs improvement

---

## Links

- **Repository:** https://github.com/StarsailsClover/minecraftBC
- **Issues:** https://github.com/StarsailsClover/minecraftBC/issues
- **Wiki:** (Coming soon)

---

## License

MIT License - See LICENSE file

---

**WARNING: This is a Release Candidate. Do not use in production.**

**minecraftBC [HighIsland v26.10-20260606-RC]**
