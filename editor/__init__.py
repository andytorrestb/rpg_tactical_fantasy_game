"""
In-game level editor for the rpg-tactical-fantasy-game.

This package is entirely editor-only: nothing in the game runtime imports it,
and it never writes into the working `maps/` or `data/` folders of the game.
Levels are exported to a separate output directory chosen by the user.

Entry point: run `python editor_main.py` from the repository root.
"""
