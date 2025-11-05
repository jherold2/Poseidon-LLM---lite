"""Central registry for runtime agent factories with feature flag awareness."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Callable, Dict, Set

from poseidon.utils.config_loader import get_enabled_modules


@dataclass(frozen=True)
class _AgentPath:
    module: str
    factory: str


_AGENT_PATHS: Dict[str, _AgentPath] = {
    "sales": _AgentPath("poseidon.agents.sales_agent", "create_sales_agent"),
    "purchasing": _AgentPath("poseidon.agents.purchasing_agent", "create_purchasing_agent"),
    "logistics": _AgentPath("poseidon.agents.logistics_agent", "create_logistics_agent"),
    "manufacturing": _AgentPath("poseidon.agents.manufacturing_agent", "create_manufacturing_agent"),
    "accounting": _AgentPath("poseidon.agents.accounting_agent", "create_accounting_agent"),
    "inference": _AgentPath("poseidon.agents.inference_agent", "create_inference_agent"),
    "communications": _AgentPath("poseidon.agents.comms_agent", "create_comms_agent"),
}


class AgentRegistry:
    """Singleton registry for all autonomous agents."""

    _factories: Dict[str, Callable[[], object]] = {}
    _agents: Dict[str, Callable[[], object]] = {}
    _enabled: Set[str] = set()

    @classmethod
    def _load_factories(cls) -> Dict[str, Callable[[], object]]:
        factories: Dict[str, Callable[[], object]] = {}
        for name, path in _AGENT_PATHS.items():
            module = importlib.import_module(path.module)
            factory = getattr(module, path.factory)
            factories[name] = factory
        return factories

    @classmethod
    def register_agents(cls) -> None:
        if os.getenv("POSEIDON_DISABLE_AGENTS") == "1":
            cls._factories = {}
            cls._agents = {}
            cls._enabled = set()
            return

        module_map = cls._load_factories()
        cls._factories = module_map

        enabled_from_flags = set(get_enabled_modules())
        if enabled_from_flags:
            cls._enabled = enabled_from_flags & set(module_map.keys())
        else:
            cls._enabled = set(module_map.keys())

        cls._agents = {
            name: factory for name, factory in module_map.items() if name in cls._enabled
        }

    @classmethod
    def get_agent(cls, name: str):
        if not cls._factories:
            cls.register_agents()

        if name not in cls._factories:
            raise ValueError(f"Agent '{name}' not registered")

        if name not in cls._agents:
            raise ValueError(f"Agent '{name}' is disabled in feature flags")

        return cls._agents[name]()

    @classmethod
    def get_available_modules(cls) -> Set[str]:
        if not cls._factories:
            cls.register_agents()
        return set(cls._factories.keys())

    @classmethod
    def get_enabled_modules(cls) -> Set[str]:
        if not cls._factories:
            cls.register_agents()
        return set(cls._enabled)


# Initialize all agents unless explicitly disabled for tests
if os.getenv("POSEIDON_DISABLE_AGENTS") != "1":
    AgentRegistry.register_agents()
