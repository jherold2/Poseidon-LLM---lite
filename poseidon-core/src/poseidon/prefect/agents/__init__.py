"""Prefect agent entrypoints for Poseidon."""

import logging

LOGGER = logging.getLogger(__name__)


def start_local_agent() -> None:
    """Placeholder helper for provisioning a local Prefect agent."""
    LOGGER.info("Local Prefect agent configuration lives in infrastructure-as-code assets.")
