"""Test configuration for deepagents-cli.

Adds local library paths to sys.path so imports work without installation.
"""

import sys
from pathlib import Path


def _ensure_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _find_repo_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / ".git").exists():
            return parent
    return start


REPO_ROOT = _find_repo_root(Path(__file__).resolve())

# Make both the CLI and core library importable for tests
_ensure_path(REPO_ROOT / "libs" / "deepagents-cli")
_ensure_path(REPO_ROOT / "libs" / "deepagents")
