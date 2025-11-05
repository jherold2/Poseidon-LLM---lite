"""Lightweight in-process async dispatcher for background workflow execution."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


TaskCallable = Callable[..., Any]


@dataclass
class TaskState:
    """Track task lifecycle for polling endpoints."""

    status: str = "queued"
    result: Any | None = None
    error: str | None = None
    attempts: int = 0
    max_retries: int = 0
    queued_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    metadata: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "metadata": self.metadata,
        }


@dataclass
class _TaskEnvelope:
    """Internal representation for queued jobs."""

    task_id: str
    func: TaskCallable
    args: tuple[Any, ...]
    kwargs: Dict[str, Any]
    retries: int
    metadata: Dict[str, Any] | None = None


class AsyncTaskDispatcher:
    """Minimal async dispatch queue living inside the FastAPI process."""

    def __init__(self, *, concurrency: int = 2, max_queue_size: int = 100):
        self._queue: asyncio.Queue[_TaskEnvelope | None] = asyncio.Queue(maxsize=max_queue_size)
        self._concurrency = max(1, concurrency)
        self._workers: list[asyncio.Task[None]] = []
        self._states: Dict[str, TaskState] = {}
        self._state_lock = asyncio.Lock()
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        logger.info("Starting AsyncTaskDispatcher with %s workers", self._concurrency)
        self._running = True
        for index in range(self._concurrency):
            worker = asyncio.create_task(self._worker(index), name=f"poseidon-dispatcher-{index}")
            self._workers.append(worker)

    async def stop(self) -> None:
        if not self._running:
            return
        logger.info("Stopping AsyncTaskDispatcher")
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._running = False

    async def submit(
        self,
        func: TaskCallable,
        *args: Any,
        retries: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Queue a callable for background execution."""
        task_id = str(uuid4())
        envelope = _TaskEnvelope(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            retries=max(0, retries),
            metadata=metadata,
        )
        async with self._state_lock:
            self._states[task_id] = TaskState(max_retries=envelope.retries, metadata=metadata)
        await self._queue.put(envelope)
        return task_id

    async def result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return task state if known."""
        async with self._state_lock:
            state = self._states.get(task_id)
            return state.to_dict() if state else None

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            envelope = await self._queue.get()
            if envelope is None:
                break

            async with self._state_lock:
                state = self._states.get(envelope.task_id)
                if state:
                    state.status = "running"
                    state.started_at = time.time()
                    state.attempts += 1
                    if state.metadata is None and envelope.metadata is not None:
                        state.metadata = envelope.metadata

            try:
                result = await self._execute(envelope)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Worker %s failed task %s", worker_id, envelope.task_id)
                result = exc

            async with self._state_lock:
                state = self._states.get(envelope.task_id)
                if not state:
                    continue
                state.finished_at = time.time()
                if isinstance(result, Exception):
                    state.error = str(result)
                    if state.attempts <= envelope.retries:
                        state.status = "retrying"
                        logger.warning(
                            "Re-queuing task %s (attempt %s/%s)",
                            envelope.task_id,
                            state.attempts,
                            envelope.retries + 1,
                        )
                        await self._queue.put(envelope)
                    else:
                        state.status = "failed"
                else:
                    state.status = "completed"
                    state.result = result

            self._queue.task_done()

    async def _execute(self, envelope: _TaskEnvelope) -> Any:
        maybe_coro = envelope.func(*envelope.args, **envelope.kwargs)
        if asyncio.iscoroutine(maybe_coro) or isinstance(maybe_coro, Awaitable):
            return await maybe_coro  # type: ignore[no-any-return]
        return await asyncio.to_thread(lambda: maybe_coro)


# Singleton dispatcher for application use
dispatcher = AsyncTaskDispatcher()


async def startup_dispatcher() -> None:
    await dispatcher.start()


async def shutdown_dispatcher() -> None:
    await dispatcher.stop()


__all__ = ["dispatcher", "AsyncTaskDispatcher", "startup_dispatcher", "shutdown_dispatcher"]
