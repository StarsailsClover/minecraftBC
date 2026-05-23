# MnMCP Protocol Specification
# MnMCP (Multi-Network Multi-Game Connection Protocol)

## Overview 概述

MnMCP is a universal protocol translation layer that enables cross-game multiplayer connections. It acts as a middleman proxy between different games, translating entities, blocks, items, and events between game-specific formats.

MnMCP (多网络多游戏连接协议) 是一个通用协议转换层，实现跨游戏多人联机。它作为不同游戏之间的中间人代理，转换实体、方块、物品和事件。

## Design Goals 设计目标

1. **Game Agnostic**: Support any game that can be adapted
2. **Bidirectional**: Full two-way translation
3. **Extensible**: Easy to add new game adapters
4. **Low Latency**: Minimal overhead for real-time gameplay
5. **State Synchronization**: Keep game states in sync across platforms

## Architecture 架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Game A    │     │    MnMCP    │     │   Game B    │
│  (Minecraft)│◄───►│    Proxy    │◄───►│ (MiniWorld) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  MC Adapter │     │   Generic   │     │  MW Adapter │
│             │◄───►│   Format    │◄───►│             │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Generic Data Types 通用数据类型

### Vec3 - 3D Vector

```json
{
  "x": 100.5,
  "y": 64.0,
  "z": -200.25
}
```

### Vec2 - 2D Rotation

```json
{
  "yaw": 45.0,    // Horizontal rotation (0-360)
  "pitch": -10.5  // Vertical rotation (-90 to 90)
}
```

## Entity Translation 实体转换

### Generic Entity Format 通用实体格式

```json
{
  "entity_id": "uuid_or_unique_id",
  "game_type": "MINECRAFT_JAVA",
  "entity_type": "MOB_HOSTILE",
  "position": {"x": 100, "y": 64, "z": -200},
  "rotation": {"yaw": 45, "pitch": 0},
  "velocity": {"x": 0.1, "y": -0.05, "z": 0.2},
  "name": "Zombie",
  "health": 20.0,
  "max_health": 20.0,
  "level": 1,
  "game_data": {
    // Game-specific properties
    "is_baby": false,
    "is_villager": false
  }
}
```

### Entity Type Mapping 实体类型映射

| Generic Type | Minecraft | MiniWorld | Roblox |
|--------------|-----------|-----------|--------|
| PLAYER | minecraft:player | 玩家 | Player |
| MOB_HOSTILE | Zombie, Skeleton, Creeper | 僵尸, 骷髅 | Zombie |
| MOB_PASSIVE | Pig, Cow, Sheep | 猪, 牛, 羊 | Pig |
| MOB_NEUTRAL | Enderman | 末影人 | - |
| NPC | Villager | 村民 | NPC |
| ITEM | Item entity | 掉落物 | DroppedItem |
| PROJECTILE | Arrow, Snowball | 箭, 雪球 | Projectile |
| VEHICLE | Boat, Minecart | 船, 矿车 | Vehicle |

## Block Translation 方块转换

### Generic Block Format 通用方块格式

```json
{
  "block_id": "uuid_or_position_hash",
  "game_type": "MINECRAFT_JAVA",
  "block_type": "SOLID",
  "position": {"x": 100, "y": 64, "z": -200},
  "block_state": {
    "variant": "stone",
    "facing": "north"
  },
  "hardness": 1.5,
  "light_level": 0,
  "is_solid": true
}
```

### Block Type Mapping 方块类型映射

| Generic Type | Description | Example |
|--------------|-------------|---------|
| SOLID | Full block, opaque | Stone, Dirt |
| TRANSPARENT | See-through | Glass, Ice |
| LIQUID | Flowing fluid | Water, Lava |
| PLANT | Non-solid vegetation | Leaves, Flowers |
| REDSTONE | Logic component | Redstone wire, Torch |
| LIGHT | Emits light | Torch, Glowstone |
| DOOR | Interactive door | Oak Door |
| CHEST | Storage container | Chest, Trapped Chest |

## Item Translation 物品转换

### Generic Item Format 通用物品格式

```json
{
  "item_id": "generic_item_identifier",
  "game_type": "MINECRAFT_JAVA",
  "name": "Diamond Sword",
  "count": 1,
  "max_stack": 64,
  "durability": 100,
  "max_durability": 1561,
  "is_stackable": false,
  "is_damageable": true,
  "is_food": false
}
```

## Event Translation 事件转换

### Supported Events 支持的事件

| Event | Direction | Description |
|-------|-----------|-------------|
| entity_spawn | Bidirectional | Entity appeared in world |
| entity_update | Bidirectional | Entity moved/changed |
| entity_despawn | Bidirectional | Entity disappeared |
| entity_interact | Bidirectional | Player interacted with entity |
| block_place | Bidirectional | Block was placed |
| block_break | Bidirectional | Block was destroyed |
| block_update | Bidirectional | Block state changed |
| chat_message | Bidirectional | Player sent message |
| player_join | Bidirectional | Player joined world |
| player_leave | Bidirectional | Player left world |
| damage | Bidirectional | Entity took damage |
| death | Bidirectional | Entity died |

### Event Format 事件格式

```json
{
  "event_type": "entity_spawn",
  "timestamp": 1704067200000,
  "source_game": "MINECRAFT_JAVA",
  "target_game": "ALL",
  "data": {
    // Event-specific data
  }
}
```

## MnMCP Packet Types MnMCP 数据包类型

| Type | Value | Description |
|------|-------|-------------|
| MNMCP_ENTITY | 0x20 | Entity synchronization |
| MNMCP_BLOCK | 0x21 | Block update |
| MNMCP_ITEM | 0x22 | Item data |
| MNMCP_EVENT | 0x23 | Game event |
| MNMCP_CHAT | 0x24 | Chat message |
| MNMCP_COMMAND | 0x25 | Game command |

## Entity Packet 实体数据包

```json
{
  "entity_id": "mc_zombie_12345",
  "source_game": "MINECRAFT_JAVA",
  "target_game": "MINIWORLD",
  "entity_type": "MOB_HOSTILE",
  "position": {"x": 100, "y": 64, "z": -200},
  "rotation": {"yaw": 45, "pitch": 0},
  "velocity": {"x": 0.1, "y": 0, "z": 0.1},
  "metadata": {
    "name": "Zombie",
    "health": 20,
    "is_baby": false
  },
  "action": "spawn"  // spawn, update, despawn, interact
}
```

## Block Packet 方块数据包

```json
{
  "block_id": "pos_100_64_-200",
  "source_game": "MINECRAFT_JAVA",
  "target_game": "MINIWORLD",
  "position": {"x": 100, "y": 64, "z": -200},
  "block_type": "SOLID",
  "block_state": {
    "material": "stone",
    "variant": "smooth"
  },
  "action": "place"  // place, break, update
}
```

## Chat Packet 聊天数据包

```json
{
  "message_id": "msg_1234567890",
  "sender_id": "player_uuid",
  "sender_name": "Steve",
  "source_game": "MINECRAFT_JAVA",
  "target_game": "MINIWORLD",
  "message": "Hello from Minecraft!",
  "message_type": "global",  // global, room, whisper, system
  "timestamp": 1704067200000
}
```

## Adapter Interface 适配器接口

### Required Methods 必需方法

```python
class GameAdapter:
    async def connect(self, host: str, port: int, **kwargs) -> bool
    async def disconnect(self)
    async def send_entity(self, entity: GenericEntity) -> bool
    async def send_block(self, block: GenericBlock) -> bool
    async def send_chat(self, sender: str, message: str) -> bool
    
    def to_generic_entity(self, game_entity: Any) -> Optional[GenericEntity]
    def from_generic_entity(self, generic: GenericEntity) -> Any
    def to_generic_block(self, game_block: Any) -> Optional[GenericBlock]
    def from_generic_block(self, generic: GenericBlock) -> Any
```

### Event Registration 事件注册

```python
adapter.on_event('entity_spawn', handle_spawn)
adapter.on_event('block_break', handle_break)
adapter.on_event('chat_message', handle_chat)
```

## Mapping Tables 映射表

### Location 位置

- `data/mappings/block_mapping.json` - Block ID mappings
- `data/mappings/entity_mapping.json` - Entity ID mappings
- `data/mappings/item_mapping.json` - Item ID mappings

### Format 格式

```json
{
  "schema_version": "1.0",
  "mappings": [
    {
      "generic_id": "generic:stone",
      "games": {
        "minecraft": {
          "1.12.2": "minecraft:stone",
          "1.13+": "minecraft:stone"
        },
        "miniworld": {
          "block_id": 1,
          "name": "石头"
        }
      },
      "properties": {
        "hardness": 1.5,
        "resistance": 6.0
      }
    }
  ]
}
```

## Synchronization 同步机制

### Entity Sync 实体同步

1. **Full Sync**: Sent on join, contains all visible entities
2. **Delta Sync**: Regular updates, only changed properties
3. **Range-based**: Only sync entities within player view distance

### Block Sync 方块同步

1. **Chunk-based**: Sync blocks in chunk units
2. **Priority Queue**: Prioritize blocks near players
3. **Batch Updates**: Combine multiple block changes

### Rate Limiting 速率限制

- Entity updates: 60 per second
- Block updates: 100 per second
- Chat messages: 10 per second per player

## Security 安全性

### Validation 验证

- Entity ID uniqueness check
- Position bounds validation
- Rate limiting per source
- Permission checks for actions

### Sanitization 清理

- Chat message filtering
- Command injection prevention
- Data size limits

## Performance 性能

### Optimization 优化

- Entity culling (out of view)
- Block update batching
- Compression for large data
- Delta compression for updates

### Caching 缓存

- Mapping table cache
- Entity state cache
- Block state cache

## Error Handling 错误处理

### Fallback Strategy 回退策略

1. Try exact mapping
2. Try similar type mapping
3. Use generic placeholder
4. Log and skip

### Error Types 错误类型

| Error | Action |
|-------|--------|
| Unknown entity type | Use generic placeholder |
| Missing mapping | Log warning, use fallback |
| Invalid position | Clamp to valid range |
| Rate limit exceeded | Drop excess packets |

## Future Extensions 未来扩展

### Planned Features 计划功能

- [ ] Inventory synchronization
- [ ] Redstone logic translation
- [ ] Biome/climate mapping
- [ ] Weather synchronization
- [ ] Time of day sync
- [ ] Quest/objective translation

### Potential Adapters 潜在适配器

- Minecraft Bedrock (via Geyser)
- Terraria
- Roblox
- Garry's Mod
- VRChat

## References 参考

- Minecraft Protocol: https://wiki.vg/Protocol
- MiniWorld Protocol: (reverse engineered)
- FastLink Protocol: See fastlink-p2p.md
