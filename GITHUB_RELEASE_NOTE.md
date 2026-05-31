# minecraftBC v26.2-20260523 - Initial Release

**Dual-Protocol P2P Minecraft Multiplayer Solution**

---

## 🎉 What's New

### Core Features

✅ **Dual-Protocol P2P Connector**
- FastLink (primary) - Low latency direct connection
- WebRTC (fallback) - High compatibility with automatic downgrade
- Automatic protocol selection based on network conditions

✅ **Minecraft LAN Injector**
- Intercepts vanilla "Open to LAN" feature
- Broadcasts worlds to P2P network automatically
- Zero configuration required

✅ **TCP Bridge** (NEW in this release)
- End-to-end TCP connection forwarding
- Packet encapsulation/decapsulation
- Connection state management

✅ **Security**
- Ed25519 node identity signing
- X25519 key exchange
- DTLS data transmission encryption

✅ **Multi-Version Support**
- Minecraft 1.12.2 - 1.20.x
- Protocol adaptation for different versions
- Offline mode support (no authentication required)

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: WebRTC support
pip install aiortc

# Host a world (server side)
python -m src.main lan --mc-port 25565 --world-name "My World"

# Discover worlds (client side)
python -m src.main client
```

---

## 📊 Release Statistics

- **Source Code**: ~5,800 lines
- **Documentation**: ~2,200 lines
- **Tests**: 12 test cases
- **Total Files**: 41 files
- **Commits**: 2 commits

---

## 🔧 Bug Fixes

### HIGH Severity Fixes
- Fixed 10 bare `except:` clauses across 5 files
  - `webrtc/signaling.py` (2)
  - `fastlink/server.py` (4)
  - `mnmcp/adapters/minecraft.py` (1)
  - `minecraft/proxy_handler.py` (2)
  - `minecraft/version_manager.py` (1)

---

## 📦 What's Included

```
minecraftBC/
├── src/                     # Source code
│   ├── main.py             # Main entry
│   ├── connector/          # Dual-protocol connector
│   ├── protocol/           # Protocol implementations
│   │   ├── fastlink/      # FastLink protocol
│   │   ├── webrtc/        # WebRTC fallback
│   │   └── mnmcp/         # Cross-game protocol
│   ├── minecraft/          # Minecraft integration
│   │   ├── lan_injector.py
│   │   ├── proxy_handler.py
│   │   ├── protocol_adapter.py
│   │   └── tcp_bridge.py  # NEW
│   ├── network/            # Network layer
│   └── config/             # Configuration
├── tests/                   # Unit tests
│   ├── test_crypto.py
│   └── test_protocol_adapter.py
├── data/                    # Data files
└── docs/                    # Documentation
```

---

## 📝 Documentation

- [README.md](README.md) - Project overview
- [VERSION.md](VERSION.md) - Version information
- [FINAL_RELEASE_REPORT.md](FINAL_RELEASE_REPORT.md) - Complete release report
- [DEVELOPMENT_SUMMARY.md](DEVELOPMENT_SUMMARY.md) - Development summary
- [AUDIT_AND_DEVELOPMENT_REPORT.md](AUDIT_AND_DEVELOPMENT_REPORT.md) - Code audit

---

## ⚠️ Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| FastLink Python implementation | Slightly lower performance | Will auto-switch to Rust when fixed |
| WebRTC optional dependency | Needs manual install | `pip install aiortc` |
| TCP forwarding | Untested in production | Testing in progress |

---

## 🔮 Future Plans

### v26.3 (Next)
- TCP bridge integration testing
- Performance benchmarking
- Extended unit tests

### v27.X (FastLink Integration)
- PyO3 Rust bindings
- BirthdayPunch NAT traversal
- Multipath aggregation

---

## 🙏 Acknowledgments

- FastLink protocol design
- aiortc project (WebRTC)
- cryptography project

---

**Full Changelog**: Compare with previous commits (initial release)

**License**: MIT
**Repository**: https://github.com/StarsailsClover/minecraftBC
