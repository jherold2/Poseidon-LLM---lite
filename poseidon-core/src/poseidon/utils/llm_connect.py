"""Backward-compatible helper for obtaining the configured LLM instance."""

from __future__ import annotations

import logging
from typing import Any, Tuple

import yaml

from poseidon.utils.local_llm import get_llm as _get_llm
from poseidon.utils.path_utils import resolve_config_path


def setup_logging(config: dict) -> logging.Logger:
    """Configure logging based on connect_llm.yaml contents."""
    logging.basicConfig(
        filename=config.get("logging", {}).get("log_file", "logs/llm.log"),
        level=getattr(logging, config.get("logging", {}).get("log_level", "INFO")),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger("llm_connect")


def get_llm() -> Tuple[Any, Any]:
    """
    Return the configured LLM instance along with an optional tokenizer.

    For remote providers (e.g. remote Ollama), the tokenizer may be ``None`` because
    inference is proxied over SSH. Existing callers expecting a tuple can continue to
    unpack without changes.
    """
    config_path = resolve_config_path("connect_llm.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    logger = setup_logging(config)
    logger.info("Loading LLM using provider configuration in %s", config_path)

    llm = _get_llm()
    tokenizer = None

    try:
        provider = (config.get("model", {}).get("provider") or "local").lower()
        if provider not in {"remote", "remote_ollama", "ollama_remote"}:
            # Local HuggingFace/llama.cpp paths often require paired tokenizers.
            from transformers import AutoTokenizer  # type: ignore

            model_path = config.get("model", {}).get("path")
            if model_path:
                tokenizer = AutoTokenizer.from_pretrained(model_path)
    except Exception as exc:  # pragma: no cover - optional convenience path
        logger.warning("Tokenizer load skipped: %s", exc)

    return llm, tokenizer


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    llm, _ = get_llm()
    response = llm.invoke("Test prompt: Generate a simple response.")
    print(f"Response: {response}")
