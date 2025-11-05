"""Logging helpers respecting the refactored repo layout."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import logging.config
import logging.handlers
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

import yaml

from poseidon.utils.path_utils import core_root, resolve_config_path

LOG_DIR = core_root() / "logs"

_SESSION_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "poseidon_session_id", default="N/A"
)
_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "poseidon_trace_id", default="N/A"
)
_AGENT_NAME: contextvars.ContextVar[str] = contextvars.ContextVar(
    "poseidon_agent_name", default="N/A"
)
_CONFIGURED = False

_RESERVED_ATTRS: set[str] = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}

_SENSITIVE_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|credential|authorization)\b"
    r"([=:]\s*['\"]?)([^,'\";\s]+)",
)


class ContextFilter(logging.Filter):
    """Inject request context metadata into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if getattr(record, "session_id", None) in (None, ""):
            record.session_id = _SESSION_ID.get()
        if getattr(record, "trace_id", None) in (None, ""):
            record.trace_id = _TRACE_ID.get()
        if getattr(record, "agent_name", None) in (None, ""):
            record.agent_name = _AGENT_NAME.get()
        record.module = getattr(record, "module", None) or record.name
        return True


class SensitiveDataFilter(logging.Filter):
    """Redact sensitive values such as passwords or API keys before emission."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if getattr(record, "__poseidon_sanitized__", False):
            return True

        for attr in ("msg",):
            value = getattr(record, attr, None)
            if isinstance(value, str):
                setattr(record, attr, _sanitize_text(value))

        if isinstance(record.args, tuple):
            record.args = tuple(_sanitize_value(arg) for arg in record.args)
        elif isinstance(record.args, Mapping):
            record.args = {k: _sanitize_value(v) for k, v in record.args.items()}

        for key, value in list(record.__dict__.items()):
            if key.startswith("_"):
                continue
            record.__dict__[key] = _sanitize_value(value)

        record.__poseidon_sanitized__ = True
        return True


class StructuredFormatter(logging.Formatter):
    """Key-value formatter that enforces consistent ordering."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        original_msg = record.msg
        if isinstance(record.msg, Mapping):
            record.msg = json.dumps(record.msg, ensure_ascii=False)
        try:
            return super().format(record)
        finally:
            record.msg = original_msg


class StructuredJSONFormatter(logging.Formatter):
    """Emit structured JSON log entries."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": getattr(record, "module", record.name),
            "session_id": getattr(record, "session_id", "N/A"),
            "trace_id": getattr(record, "trace_id", "N/A"),
            "agent_name": getattr(record, "agent_name", "N/A"),
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info

        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = _normalize_extra_value(value)

        return json.dumps(payload, ensure_ascii=False)


class ColorFormatter(StructuredFormatter):
    """Colorize console output for development friendliness."""

    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        super().__init__(fmt, datefmt)
        self._stream_is_tty = sys.stdout.isatty()
        self._color_disabled = os.getenv("POSEIDON_NO_COLOR") == "1"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        if self._stream_is_tty and not self._color_disabled:
            original = record.levelname
            colour = self.COLORS.get(record.levelno)
            if colour:
                record.levelname = f"{colour}{record.levelname}{self.RESET}"
            try:
                return super().format(record)
            finally:
                record.levelname = original
        return super().format(record)


class AgentRoutingHandler(logging.Handler):
    """Route agent logs to per-agent rotating files."""

    def __init__(
        self,
        directory: str,
        maxBytes: int = 10485760,
        backupCount: int = 5,
    ):
        super().__init__()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(maxBytes)
        self.backup_count = int(backupCount)
        self._handlers: dict[str, logging.Handler] = {}

    def setFormatter(self, fmt: logging.Formatter) -> None:  # noqa: N802
        super().setFormatter(fmt)
        for handler in self._handlers.values():
            handler.setFormatter(fmt)

    def setLevel(self, level: int | str) -> None:  # noqa: N802
        super().setLevel(level)
        for handler in self._handlers.values():
            handler.setLevel(level)

    def addFilter(self, filt: logging.Filter) -> None:  # noqa: N802
        super().addFilter(filt)
        for handler in self._handlers.values():
            handler.addFilter(filt)

    def removeFilter(self, filt: logging.Filter) -> None:  # noqa: N802
        super().removeFilter(filt)
        for handler in self._handlers.values():
            handler.removeFilter(filt)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        agent = getattr(record, "agent_name", "") or record.name.rsplit(".", 1)[-1]
        agent_slug = _slugify(agent) or "general"
        handler = self._handlers.get(agent_slug)
        if handler is None:
            log_path = self.directory / f"{agent_slug}.log"
            handler = logging.handlers.RotatingFileHandler(
                filename=log_path,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8",
            )
            handler.setLevel(self.level)
            if self.formatter:
                handler.setFormatter(self.formatter)
            for filt in self.filters:
                handler.addFilter(filt)
            self._handlers[agent_slug] = handler

        handler.emit(record)

    def close(self) -> None:  # noqa: D401
        for handler in self._handlers.values():
            with contextlib.suppress(Exception):
                handler.close()
        self._handlers.clear()
        super().close()


@dataclass
class ContextTokens:
    """Container to reset context vars."""

    session_token: contextvars.Token[str] | None = None
    trace_token: contextvars.Token[str] | None = None
    agent_token: contextvars.Token[str] | None = None

    def reset(self) -> None:
        """Reset stored context tokens."""
        if self.session_token is not None:
            _SESSION_ID.reset(self.session_token)
        if self.trace_token is not None:
            _TRACE_ID.reset(self.trace_token)
        if self.agent_token is not None:
            _AGENT_NAME.reset(self.agent_token)


class LoggingContext:
    """Context manager for binding logging metadata."""

    def __init__(
        self,
        session_id: str | None = None,
        trace_id: str | None = None,
        agent_name: str | None = None,
    ):
        self.session_id = session_id
        self.trace_id = trace_id
        self.agent_name = agent_name
        self._tokens = ContextTokens()

    def __enter__(self) -> "LoggingContext":
        self._tokens = bind_context(
            session_id=self.session_id,
            trace_id=self.trace_id,
            agent_name=self.agent_name,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self._tokens.reset()


def bind_context(
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    agent_name: str | None = None,
) -> ContextTokens:
    """Set logging context values and return tokens for later reset."""
    tokens = ContextTokens()
    if session_id is not None:
        tokens.session_token = _SESSION_ID.set(session_id or "N/A")
    if trace_id is not None:
        tokens.trace_token = _TRACE_ID.set(trace_id or "N/A")
    if agent_name is not None:
        tokens.agent_token = _AGENT_NAME.set(agent_name or "N/A")
    return tokens


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger, ensuring the logging subsystem is configured."""
    setup_logging()
    return logging.getLogger(name or "poseidon")


def setup_logging(name: str | None = None, *, reload_config: bool = False) -> logging.Logger:
    """Configure logging based on ``logging_config.yaml``."""
    global _CONFIGURED
    if _CONFIGURED and not reload_config:
        return logging.getLogger(name or "poseidon")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    config_path = resolve_config_path("logging_config.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        config: MutableMapping[str, Any] = yaml.safe_load(handle) or {}

    _apply_environment_overrides(config)
    _ensure_handler_paths(config)

    logging.config.dictConfig(config)
    _CONFIGURED = True
    return logging.getLogger(name or "poseidon")


def _ensure_handler_paths(config: MutableMapping[str, Any]) -> None:
    handlers: Mapping[str, MutableMapping[str, Any]] = config.get("handlers", {})  # type: ignore[assignment]
    for handler_config in handlers.values():
        filename = handler_config.get("filename")
        if filename:
            handler_path = Path(filename)
            if not handler_path.is_absolute():
                handler_path = core_root() / handler_path
            handler_path.parent.mkdir(parents=True, exist_ok=True)
            handler_config["filename"] = str(handler_path)

        directory = handler_config.get("directory")
        if directory:
            directory_path = Path(directory)
            if not directory_path.is_absolute():
                directory_path = core_root() / directory_path
            directory_path.mkdir(parents=True, exist_ok=True)
            handler_config["directory"] = str(directory_path)


def _apply_environment_overrides(config: MutableMapping[str, Any]) -> None:
    env_level = os.getenv("POSEIDON_LOG_LEVEL")
    if env_level:
        level = env_level.upper()
        for logger_cfg in config.get("loggers", {}).values():
            logger_cfg["level"] = level
        if "root" in config:
            config["root"]["level"] = level

    env_format = os.getenv("POSEIDON_LOG_FORMAT", "").lower()
    if env_format == "json":
        for handler_cfg in config.get("handlers", {}).values():
            formatter = handler_cfg.get("formatter")
            if formatter in {"structured", "console"}:
                handler_cfg["formatter"] = "structured_json"


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return type(value)(_sanitize_value(v) for v in value)
    return value


def _sanitize_text(text: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        prefix, sep, _ = match.groups()
        return f"{prefix}{sep}<REDACTED>"

    return _SENSITIVE_PATTERN.sub(_replacement, text)


def _slugify(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return sanitized.strip("-")


def _normalize_extra_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {k: _normalize_extra_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_extra_value(item) for item in value]
    try:
        return repr(value)
    except Exception:  # pragma: no cover - defensive
        return str(type(value))


__all__ = [
    "AgentRoutingHandler",
    "ColorFormatter",
    "ContextFilter",
    "LoggingContext",
    "SensitiveDataFilter",
    "StructuredFormatter",
    "StructuredJSONFormatter",
    "bind_context",
    "get_logger",
    "setup_logging",
]


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    log = setup_logging(reload_config=True)
    log.debug("Debug message")
    log.info("Info message")
    log.warning("Warning message")
    log.error("Error message")
