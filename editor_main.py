#!/usr/bin/env python3

"""
Entry point of the level editor.

Run from the repository root:

    python editor_main.py

This is entirely separate from the game (`main.py`): starting the game never
touches the editor and vice versa.
"""

from editor.ui.app import main

if __name__ == "__main__":
    main()
