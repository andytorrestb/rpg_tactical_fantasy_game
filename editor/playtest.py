"""
Editor-contained playtest support.

The game runtime can only start levels named `level_<number>` from its own
`maps/` folder, and that behavior is a fixed contract. However, the runtime
resolves the level directory it is given both against the working directory
(for `map.tmx`) and against `data/<language>/` (for `map_properties.tmx` and
the dialog files) — and joining `data/<language>` with an *absolute* path
yields the absolute path itself. Staging the whole level flat into one
absolute folder therefore lets `LevelScene` load it without any runtime
change; `editor/playtest_run.py` does exactly that in a separate process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from editor.project import LevelProject

REPO_ROOT = Path(__file__).resolve().parent.parent


def stage(project: LevelProject, staging_root: Path | str) -> Path:
    """Stage the project into `<staging_root>/<project name>` and return it."""
    staging_dir = Path(staging_root) / project.name
    return project.stage_for_playtest(staging_dir)


def launch(staged_dir: Path) -> subprocess.Popen:
    """
    Launch the staged level in a separate game process, keeping the editor
    responsive. The child process must run from the repository root so the
    game finds its assets.
    """
    return subprocess.Popen(
        [sys.executable, "-m", "editor.playtest_run", str(Path(staged_dir).resolve())],
        cwd=str(REPO_ROOT),
    )


def stage_and_launch(
    project: LevelProject, staging_root: Path | str
) -> subprocess.Popen:
    return launch(stage(project, staging_root))
