"""Tracked background tasks owned by the FastAPI application."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class BackgroundTaskRegistry:
    """Keep fire-and-forget tasks observable and drain them on shutdown."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    def create(self, coroutine: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        try:
            error = task.exception()
        except asyncio.CancelledError:
            return
        if error is not None:
            logger.error(
                "后台任务 %s 执行失败: %s",
                task.get_name(),
                error,
                exc_info=(type(error), error, error.__traceback__),
            )

    async def shutdown(self, timeout: float = 10.0) -> None:
        """Wait briefly for registered tasks, then cancel unfinished wrappers."""
        if not self._tasks:
            return

        tasks = set(self._tasks)
        logger.info("正在等待 %s 个后台任务结束", len(tasks))
        done, pending = await asyncio.wait(tasks, timeout=max(0.0, timeout))
        if pending:
            logger.warning("%s 个后台任务未及时结束，正在取消", len(pending))
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        # Retrieve exceptions even if callbacks have not run yet.
        for task in done:
            if task.cancelled():
                continue
            try:
                task.exception()
            except asyncio.CancelledError:
                pass


background_tasks = BackgroundTaskRegistry()
