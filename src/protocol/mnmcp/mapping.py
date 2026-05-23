"""
Mapping Manager for MnMCP
MnMCP 映射管理器

Manages bidirectional translations between game-specific IDs and generic IDs.
管理游戏特定ID和通用ID之间的双向转换。
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import logging

from .proxy import GameType, EntityType, BlockType

logger = logging.getLogger(__name__)


class MappingEntry:
    """Single mapping entry"""
    
    def __init__(self, generic_id: str, game_mappings: Dict[str, Any], 
                 properties: Dict[str, Any] = None):
        self.generic_id = generic_id
        self.game_mappings = game_mappings
        self.properties = properties or {}
    
    def get_game_id(self, game_type: GameType, version: str = "default") -> Optional[Any]:
        """Get game-specific ID"""
        game_key = game_type.name.lower()
        
        if game_key not in self.game_mappings:
            return None
        
        mapping = self.game_mappings[game_key]
        
        # Check for version-specific mapping
        if version in mapping:
            return mapping[version]
        
        # Check for version range (e.g., "1.13+")
        for key in mapping:
            if key.endswith('+') and version >= key[:-1]:
                return mapping[key]
        
        # Return default mapping
        return mapping.get('default') or mapping.get('id')
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """Get property value"""
        return self.properties.get(key, default)


class MappingManager:
    """
    Manages all game-to-generic mappings
    
    Supports:
    - Block mappings
    - Entity mappings
    - Item mappings
    - Protocol mappings
    """
    
    def __init__(self, mapping_dir: str = "data/mappings"):
        self.mapping_dir = Path(mapping_dir)
        
        # Mapping tables
        self.block_mappings: Dict[str, MappingEntry] = {}
        self.entity_mappings: Dict[str, MappingEntry] = {}
        self.item_mappings: Dict[str, MappingEntry] = {}
        
        # Reverse lookups: game_type -> game_id -> generic_id
        self.block_reverse: Dict[GameType, Dict[str, str]] = {}
        self.entity_reverse: Dict[GameType, Dict[str, str]] = {}
        self.item_reverse: Dict[GameType, Dict[str, str]] = {}
        
        # Fallbacks
        self.fallbacks: Dict[str, Any] = {}
        
        # Load all mappings
        self._load_all_mappings()
    
    def _load_all_mappings(self):
        """Load all mapping files"""
        # Load block mappings
        block_file = self.mapping_dir / "block_mapping.json"
        if block_file.exists():
            self._load_mapping_file(block_file, 'block')
        else:
            logger.warning(f"Block mapping file not found: {block_file}")
        
        # Load entity mappings
        entity_file = self.mapping_dir / "entity_mapping.json"
        if entity_file.exists():
            self._load_mapping_file(entity_file, 'entity')
        else:
            logger.warning(f"Entity mapping file not found: {entity_file}")
        
        # Load item mappings
        item_file = self.mapping_dir / "item_mapping.json"
        if item_file.exists():
            self._load_mapping_file(item_file, 'item')
        else:
            logger.warning(f"Item mapping file not found: {item_file}")
    
    def _load_mapping_file(self, file_path: Path, mapping_type: str):
        """Load a mapping file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load fallbacks
            if 'fallbacks' in data:
                self.fallbacks.update(data['fallbacks'])
            
            # Load mappings
            for entry in data.get('mappings', []):
                generic_id = entry.get('generic_id')
                if not generic_id:
                    continue
                
                mapping_entry = MappingEntry(
                    generic_id=generic_id,
                    game_mappings=entry.get('games', {}),
                    properties=entry.get('properties', {})
                )
                
                # Add to appropriate table
                if mapping_type == 'block':
                    self.block_mappings[generic_id] = mapping_entry
                    self._build_reverse_lookup(
                        mapping_entry, self.block_reverse, 'block_id'
                    )
                elif mapping_type == 'entity':
                    self.entity_mappings[generic_id] = mapping_entry
                    self._build_reverse_lookup(
                        mapping_entry, self.entity_reverse, 'entity_id'
                    )
                elif mapping_type == 'item':
                    self.item_mappings[generic_id] = mapping_entry
                    self._build_reverse_lookup(
                        mapping_entry, self.item_reverse, 'item_id'
                    )
            
            logger.info(f"Loaded {len(data.get('mappings', []))} {mapping_type} mappings from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load mapping file {file_path}: {e}")
    
    def _build_reverse_lookup(self, entry: MappingEntry, 
                             reverse_table: Dict[GameType, Dict[str, str]],
                             id_key: str):
        """Build reverse lookup table"""
        for game_key, mapping in entry.game_mappings.items():
            try:
                game_type = GameType[game_key.upper()]
            except KeyError:
                continue
            
            if game_type not in reverse_table:
                reverse_table[game_type] = {}
            
            # Extract game ID
            if isinstance(mapping, dict):
                game_id = mapping.get(id_key) or mapping.get('id')
            else:
                game_id = mapping
            
            if game_id is not None:
                reverse_table[game_type][str(game_id)] = entry.generic_id
    
    # Block mappings
    def to_generic_block(self, game_type: GameType, game_block_id: str, 
                        version: str = "default") -> Optional[str]:
        """Convert game block ID to generic ID"""
        # Check reverse lookup first
        reverse = self.block_reverse.get(game_type, {})
        if game_block_id in reverse:
            return reverse[game_block_id]
        
        # Search in mappings
        for entry in self.block_mappings.values():
            game_id = entry.get_game_id(game_type, version)
            if game_id == game_block_id:
                return entry.generic_id
        
        return None
    
    def from_generic_block(self, game_type: GameType, generic_id: str,
                          version: str = "default") -> Optional[str]:
        """Convert generic block ID to game block ID"""
        entry = self.block_mappings.get(generic_id)
        if entry:
            return entry.get_game_id(game_type, version)
        return None
    
    def get_block_properties(self, generic_id: str) -> Dict[str, Any]:
        """Get block properties by generic ID"""
        entry = self.block_mappings.get(generic_id)
        if entry:
            return entry.properties
        return {}
    
    def get_block_fallback(self, game_type: GameType) -> str:
        """Get fallback block for game"""
        return self.fallbacks.get(game_type.name.lower(), 'generic:stone')
    
    # Entity mappings
    def to_generic_entity(self, game_type: GameType, game_entity_id: str,
                         version: str = "default") -> Optional[str]:
        """Convert game entity ID to generic ID"""
        reverse = self.entity_reverse.get(game_type, {})
        if game_entity_id in reverse:
            return reverse[game_entity_id]
        
        for entry in self.entity_mappings.values():
            game_id = entry.get_game_id(game_type, version)
            if game_id == game_entity_id:
                return entry.generic_id
        
        return None
    
    def from_generic_entity(self, game_type: GameType, generic_id: str,
                           version: str = "default") -> Optional[str]:
        """Convert generic entity ID to game entity ID"""
        entry = self.entity_mappings.get(generic_id)
        if entry:
            return entry.get_game_id(game_type, version)
        return None
    
    def get_entity_properties(self, generic_id: str) -> Dict[str, Any]:
        """Get entity properties by generic ID"""
        entry = self.entity_mappings.get(generic_id)
        if entry:
            return entry.properties
        return {}
    
    def get_entity_type(self, generic_id: str) -> Optional[EntityType]:
        """Get entity type from generic ID"""
        entry = self.entity_mappings.get(generic_id)
        if entry:
            type_str = entry.properties.get('entity_type', '')
            try:
                return EntityType[type_str]
            except KeyError:
                pass
        return None
    
    def get_entity_fallback(self, game_type: GameType) -> str:
        """Get fallback entity for game"""
        return self.fallbacks.get(f"{game_type.name.lower()}_entity", 'generic:pig')
    
    # Item mappings
    def to_generic_item(self, game_type: GameType, game_item_id: str,
                       version: str = "default") -> Optional[str]:
        """Convert game item ID to generic ID"""
        reverse = self.item_reverse.get(game_type, {})
        if game_item_id in reverse:
            return reverse[game_item_id]
        
        for entry in self.item_mappings.values():
            game_id = entry.get_game_id(game_type, version)
            if game_id == game_item_id:
                return entry.generic_id
        
        return None
    
    def from_generic_item(self, game_type: GameType, generic_id: str,
                         version: str = "default") -> Optional[str]:
        """Convert generic item ID to game item ID"""
        entry = self.item_mappings.get(generic_id)
        if entry:
            return entry.get_game_id(game_type, version)
        return None
    
    def get_item_properties(self, generic_id: str) -> Dict[str, Any]:
        """Get item properties by generic ID"""
        entry = self.item_mappings.get(generic_id)
        if entry:
            return entry.properties
        return {}
    
    def get_item_fallback(self, game_type: GameType) -> str:
        """Get fallback item for game"""
        return self.fallbacks.get(f"{game_type.name.lower()}_item", 'generic:stick')
    
    # Utility methods
    def list_generic_blocks(self) -> List[str]:
        """List all generic block IDs"""
        return list(self.block_mappings.keys())
    
    def list_generic_entities(self) -> List[str]:
        """List all generic entity IDs"""
        return list(self.entity_mappings.keys())
    
    def list_generic_items(self) -> List[str]:
        """List all generic item IDs"""
        return list(self.item_mappings.keys())
    
    def search_mappings(self, query: str, mapping_type: str = 'all') -> List[Dict[str, Any]]:
        """Search mappings by query string"""
        results = []
        
        mappings_to_search = []
        if mapping_type in ('all', 'block'):
            mappings_to_search.append(('block', self.block_mappings))
        if mapping_type in ('all', 'entity'):
            mappings_to_search.append(('entity', self.entity_mappings))
        if mapping_type in ('all', 'item'):
            mappings_to_search.append(('item', self.item_mappings))
        
        for mtype, mappings in mappings_to_search:
            for generic_id, entry in mappings.items():
                if query.lower() in generic_id.lower():
                    results.append({
                        'type': mtype,
                        'generic_id': generic_id,
                        'properties': entry.properties
                    })
        
        return results
    
    def reload_mappings(self):
        """Reload all mapping files"""
        self.block_mappings.clear()
        self.entity_mappings.clear()
        self.item_mappings.clear()
        self.block_reverse.clear()
        self.entity_reverse.clear()
        self.item_reverse.clear()
        self.fallbacks.clear()
        
        self._load_all_mappings()
        logger.info("Mappings reloaded")
    
    def get_stats(self) -> Dict[str, int]:
        """Get mapping statistics"""
        return {
            'block_mappings': len(self.block_mappings),
            'entity_mappings': len(self.entity_mappings),
            'item_mappings': len(self.item_mappings),
            'total': len(self.block_mappings) + len(self.entity_mappings) + len(self.item_mappings)
        }


# Example usage
if __name__ == '__main__':
    # Create mapping manager
    manager = MappingManager("../../data/mappings")
    
    # Print stats
    print(f"Mapping stats: {manager.get_stats()}")
    
    # Test block mapping
    mc_stone = manager.to_generic_block(GameType.MINECRAFT_JAVA, "minecraft:stone")
    print(f"Minecraft stone -> {mc_stone}")
    
    miniworld_stone = manager.from_generic_block(GameType.MINIWORLD, "generic:stone")
    print(f"Generic stone -> MiniWorld: {miniworld_stone}")
    
    # Test entity mapping
    mc_zombie = manager.to_generic_entity(GameType.MINECRAFT_JAVA, "minecraft:zombie")
    print(f"Minecraft zombie -> {mc_zombie}")
    
    # Get properties
    stone_props = manager.get_block_properties("generic:stone")
    print(f"Stone properties: {stone_props}")
    
    # Search
    results = manager.search_mappings("diamond")
    print(f"Search 'diamond': {len(results)} results")
    for r in results:
        print(f"  {r['type']}: {r['generic_id']}")
