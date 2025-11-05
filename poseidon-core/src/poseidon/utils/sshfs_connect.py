"""Helpers for mounting the remote LLM directory via SSHFS."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Tuple

import yaml

# Default location for the SSH connection configuration.
from poseidon.utils.path_utils import resolve_config_path

_CONFIG_PATH = resolve_config_path("ssh_config.yaml")
LOGGER = logging.getLogger(__name__)


def _load_config(path: Path = _CONFIG_PATH) -> Dict[str, Dict[str, object]]:
    """Return the SSHFS configuration block keyed by connection name."""
    if not path.exists():
        raise FileNotFoundError(
            f"SSHFS configuration not found at {path}. "
            "Set POSEIDON_CONFIG_ROOT or create the file with a 'connections' section."
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    connections = raw.get("connections")
    if not isinstance(connections, dict) or not connections:
        raise ValueError(
            f"{path} must define a non-empty 'connections' mapping."
        )
    return connections


def _resolve_connection(
    name: str, config: Dict[str, Dict[str, object]]
) -> Tuple[str, Path, str, Dict[str, object]]:
    """Validate and return the individual connection parameters."""
    if name not in config:
        raise KeyError(f"Unknown SSHFS connection '{name}' in ssh_config.yaml")

    entry = config[name]
    for key in ("host", "remote_path", "local_mount"):
        if key not in entry or not entry[key]:
            raise ValueError(f"SSHFS connection '{name}' missing required field '{key}'")

    user = entry.get("user")
    if not user:
        raise ValueError(
            f"SSHFS connection '{name}' must include a 'user' field for authentication"
        )

    remote = f"{user}@{entry['host']}:{entry['remote_path']}"
    mount_point = Path(entry["local_mount"]).expanduser()
    options = entry.get("options") or {}
    if not isinstance(options, dict):
        raise ValueError(f"'options' for connection '{name}' must be a mapping")

    return remote, mount_point, str(entry.get("name") or name), options


def _build_option_args(options: Dict[str, object]) -> Iterable[str]:
    """Translate dict-based options into sshfs CLI arguments."""
    for key, value in options.items():
        if isinstance(value, bool):
            if value:
                yield f"-o{key}"
            continue
        yield f"-o{key}={value}"


def is_mounted(mount_point: Path | str) -> bool:
    """Return True if the mount point is active."""
    path = Path(mount_point).expanduser()
    return path.exists() and os.path.ismount(path)


def mount_remote_server(name: str = "default") -> Path:
    """
    Mount the configured remote directory using sshfs.

    The configuration is sourced from config/ssh_config.yaml with the schema::

        connections:
          default:
            host: foo.internal
            user: jane
            remote_path: /opt/models/Meta-Llama-3-8B-Instruct
            local_mount: ~/remote_llama
            options:
              reconnect: true
              ServerAliveInterval: 15
              ServerAliveCountMax: 3
              IdentityFile: ~/.ssh/id_ed25519

    Returns the resolved Path of the mount point.
    """
    connections = _load_config()
    remote, mount_point, label, options = _resolve_connection(name, connections)

    mount_point.mkdir(parents=True, exist_ok=True)
    if is_mounted(mount_point):
        LOGGER.info("SSHFS mount '%s' already active at %s", label, mount_point)
        return mount_point

    command = ["sshfs", remote, str(mount_point)]
    option_args = list(_build_option_args(options))
    if option_args:
        command[1:1] = option_args  # insert after sshfs

    LOGGER.info("Mounting SSHFS connection '%s' via: %s", label, " ".join(command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on env
        raise RuntimeError(f"Failed to mount SSHFS connection '{label}': {exc}") from exc

    if not is_mounted(mount_point):
        raise RuntimeError(
            f"SSHFS mount command for '{label}' completed but mount point not detected."
        )

    return mount_point


def unmount_remote_server(mount_point: Path | str) -> None:
    """Unmount the SSHFS mount point."""
    path = Path(mount_point).expanduser()
    if not is_mounted(path):
        LOGGER.info("Mount point %s already unmounted", path)
        return

    system = platform.system().lower()
    if system == "darwin":  # macOS
        command = ["diskutil", "unmount", str(path)]
    elif system.startswith("win"):
        raise RuntimeError("SSHFS unmount not supported on Windows via this helper")
    else:
        command = ["fusermount", "-u", str(path)]

    LOGGER.info("Unmounting SSHFS mount at %s", path)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - env dependent
        raise RuntimeError(f"Failed to unmount SSHFS at {path}: {exc}") from exc
