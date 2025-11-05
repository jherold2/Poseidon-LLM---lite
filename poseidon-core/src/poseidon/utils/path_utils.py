"""Helpers for resolving project-relative paths after repo restructuring."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List


@lru_cache(maxsize=1)
def core_root() -> Path:
    """Return the absolute path to the poseidon-core project root."""
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Return the repository root (one level above poseidon-core)."""
    return core_root().parent


def _dedupe(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    deduped: List[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


@lru_cache(maxsize=1)
def config_roots() -> List[Path]:
    """Candidate directories that may contain configuration files."""
    env_root = os.getenv("POSEIDON_CONFIG_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend(
        [
            Path.cwd() / "config",
            core_root() / "config",
            repo_root() / "config",
            repo_root() / "poseidon-cda" / "config",
        ]
    )
    return _dedupe([path for path in candidates if path])


def resolve_config_path(relative_path: str) -> Path:
    """
    Resolve a configuration file by searching known config roots.

    Parameters
    ----------
    relative_path:
        Path to the file under a config directory. The prefix ``config/`` is optional.
    """
    relative = relative_path.strip("/")
    if relative.startswith("config/"):
        relative = relative[len("config/") :]

    for root in config_roots():
        candidate = root / relative
        if candidate.exists():
            return candidate

    # Fall back to the core configuration directory.
    return (core_root() / "config" / relative).resolve()
