# Level Editor Layer System with Sprite Support

## Overview
The level editor now supports a multi-layer system with 4 named layers, layer visibility controls, and **layer-specific sprite palettes** that automatically show appropriate tiles for each layer.

## Layers
- **Ground**: Base terrain tiles (stone, dirt, grass patterns)
- **Obstacles**: Blocking elements (walls, rocks, doors) 
- **Allies**: Allied character placement markers
- **Foes**: Enemy character placement markers

## New Sprite Features

### Layer-Specific Tile Palettes
- **Automatic Filtering**: Each layer shows only relevant tiles
- **Ground Layer**: Stone floors, dirt, grass, terrain varieties
- **Obstacles Layer**: Walls, rocks, doors, blocking elements  
- **Allies Layer**: Spawn markers, chests, special items
- **Foes Layer**: Enemy spawn indicators and dark-themed markers

### Smart Tile Selection
- **Auto-Selection**: Switching layers automatically selects appropriate default tile
- **Visual Feedback**: Current layer shown in palette header
- **Categorized Display**: Tiles organized by intended purpose

### Sprite Integration
- **Real Sprites**: All tiles show actual game sprites, not placeholders
- **Tileset Support**: Full integration with existing .tsx tilesets
- **Performance**: Efficient sprite caching and rendering

## Enhanced Features

### Layer Management Panel
- Located between the main grid and tile palette
- Shows all 4 layers with color coding
- Current active layer highlighted
- Eye icon indicates visibility state

### Layer Controls
- **Click layer name**: Switch to that layer for editing
- **Click eye icon**: Toggle layer visibility 
- **1-4 keys**: Quick switch between layers (1=Ground, 2=Obstacles, 3=Allies, 4=Foes)
- **Auto-tile selection**: Appropriate tile selected when switching

### Visual Feedback
- Active layer highlighted with colored border on grid
- Non-ground layers have subtle color tinting
- Hidden layers shown grayed out in panel
- **Layer indicator** in tile palette shows current active layer
- **Filtered tiles** only show relevant sprites per layer

### File Format Changes
- JSON templates now store layers separately with visibility state
- Backward compatible with old single-grid format
- New format:
```json
{
  "width": 22,
  "height": 14,
  "layers": {
    "ground": {"data": [[...]], "visible": true},
    "obstacles": {"data": [[...]], "visible": true},
    "allies": {"data": [[...]], "visible": true},
    "foes": {"data": [[...]], "visible": true}
  },
  "tilesets": [...]
}
```

## Usage
1. Start editor: `python tools/level_editor/editor_app.py`
2. Select a layer from the layer panel or use 1-4 keys
3. **Browse layer-specific tiles** in the filtered palette
4. Paint tiles normally - they go to the current layer with actual sprites
5. Toggle layer visibility to see different combinations
6. All tools (Paint, Rectangle, Flood Fill) work with current layer

## Tile Categories

### Ground Tiles (589, 591-593, 562-585, etc.)
- Stone floor variants
- Dirt and earth patterns  
- Grass and outdoor terrain
- Dungeon floor types

### Obstacle Tiles (847-858, 911-920, 783-792, etc.)
- Wall varieties and textures
- Rock formations and debris
- Doors and barriers
- Blocking decorations

### Ally Markers (1099, 1093, 8-12, 22-26, etc.)
- Spawn point indicators
- Chest and equipment locations
- Special item placement
- Altar and objective markers

### Foe Markers (800-805, 900-905, etc.)  
- Enemy spawn indicators
- Dark-themed markers
- Battle area designations

## Advanced Features

### Smart Categorization
- **Automatic Assignment**: Tiles automatically categorized by ID patterns
- **Extensible System**: Easy to add new tile categories
- **Fallback Support**: Unknown tiles default to all-tiles view

### Multi-Tileset Support
- **Tileset Filtering**: Each tileset filtered per layer
- **Consistent Categories**: Same categorization across all tilesets
- **Mixed Content**: Different tilesets can contribute to same layers

## Backward Compatibility
- Old JSON templates automatically converted to new format
- Legacy single-grid files loaded as "ground" layer with empty other layers
- Existing tilesets work without modification
- All previous editor features preserved

## Technical Details
- **Tile Categorizer**: `TileCategorizer` class manages tile-to-layer assignments  
- **Layer Palettes**: Dynamic filtering creates layer-specific tile lists
- **Sprite Caching**: Efficient loading and display of tile graphics
- **Event Handling**: Enhanced mouse/keyboard input for layer operations