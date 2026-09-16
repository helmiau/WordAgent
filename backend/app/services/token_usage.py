"""Token accounting for today's hours and the latest seven calendar days."""

from __future__ import annotations

import sqlite3
import threading
import weakref
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert

from app.core.config import get_data_dir
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.db_models import TokenDaily, TokenWeekly

logger = get_logger(__name__)

_usage_listener_lock = threading.Lock()
_usage_listener_refs: set[weakref.ReferenceType] = set()


def subscribe_token_usage_updates(callback: Callable[[], None]) -> Callable[[], None]:
    """Subscribe to successful usage writes without retaining GUI objects."""
    try:
        callback_ref = weakref.WeakMethod(callback)
    except TypeError:
        callback_ref = weakref.ref(callback)

    with _usage_listener_lock:
        _usage_listener_refs.add(callback_ref)

    def unsubscribe() -> None:
        with _usage_listener_lock:
            _usage_listener_refs.discard(callback_ref)

    return unsubscribe


def _notify_token_usage_updated() -> None:
    callbacks: list[Callable[[], None]] = []
    stale_refs: list[weakref.ReferenceType] = []
    with _usage_listener_lock:
        for callback_ref in _usage_listener_refs:
            callback = callback_ref()
            if callback is None:
                stale_refs.append(callback_ref)
            else:
                callbacks.append(callback)
        for callback_ref in stale_refs:
            _usage_listener_refs.discard(callback_ref)

    for callback in callbacks:
        try:
            callback()
        except Exception:
            logger.exception("通知 Token 仪表盘刷新失败")


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_usage_metadata(usage: dict | None) -> dict[str, int]:
    """Normalize LangChain, OpenAI-compatible and Anthropic token metadata."""
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("input_token_details")
    details = details if isinstance(details, dict) else {}
    prompt_details = usage.get("prompt_tokens_details")
    prompt_details = prompt_details if isinstance(prompt_details, dict) else {}
    detail_cache_values = [
        value for key, value in details.items() if key == "cache_read" or key.endswith("_cache_read")
    ]
    cached_candidates = (
        *detail_cache_values,
        details.get("cache_read_input_tokens"),
        details.get("cached_tokens"),
        prompt_details.get("cached_tokens"),
        usage.get("cache_read_input_tokens"),
        usage.get("prompt_cache_hit_tokens"),
        usage.get("prompt_cache_hit_token_count"),
        usage.get("cache_read_tokens"),
        usage.get("cached_input_tokens"),
        usage.get("cached_content_token_count"),
        usage.get("cached_tokens"),
    )
    return {
        "input_tokens": _safe_int(usage.get("input_tokens", usage.get("prompt_tokens", 0))),
        "output_tokens": _safe_int(usage.get("output_tokens", usage.get("completion_tokens", 0))),
        "cached_tokens": next((_safe_int(v) for v in cached_candidates if v is not None), 0),
    }


async def record_token_usage(*, input_tokens: int, output_tokens: int, cached_tokens: int, **_ignored) -> None:
    """Atomically add one model invocation to the current hour and day."""
    values = {
        "input_tokens": _safe_int(input_tokens),
        "output_tokens": _safe_int(output_tokens),
        "cached_tokens": _safe_int(cached_tokens),
    }
    if not any(values.values()):
        return

    now = datetime.now()
    hour = now.replace(minute=0, second=0, microsecond=0)
    today = now.date()
    try:
        async with AsyncSessionLocal() as db:
            daily = insert(TokenDaily).values(bucket_time=hour, updated_at=now, **values)
            await db.execute(
                daily.on_conflict_do_update(
                    index_elements=[TokenDaily.bucket_time],
                    set_={
                        "input_tokens": TokenDaily.input_tokens + values["input_tokens"],
                        "output_tokens": TokenDaily.output_tokens + values["output_tokens"],
                        "cached_tokens": TokenDaily.cached_tokens + values["cached_tokens"],
                        "updated_at": now,
                    },
                )
            )
            weekly = insert(TokenWeekly).values(usage_date=today, updated_at=now, **values)
            await db.execute(
                weekly.on_conflict_do_update(
                    index_elements=[TokenWeekly.usage_date],
                    set_={
                        "input_tokens": TokenWeekly.input_tokens + values["input_tokens"],
                        "output_tokens": TokenWeekly.output_tokens + values["output_tokens"],
                        "cached_tokens": TokenWeekly.cached_tokens + values["cached_tokens"],
                        "updated_at": now,
                    },
                )
            )
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            await db.execute(delete(TokenDaily).where(TokenDaily.bucket_time < midnight))
            await db.execute(delete(TokenWeekly).where(TokenWeekly.usage_date < today - timedelta(days=6)))
            await db.commit()
        _notify_token_usage_updated()
    except Exception:
        logger.exception("保存 token 使用统计失败")


def query_token_usage_sync(period: str) -> dict:
    """Read dashboard data without modifying the business SQLite database."""
    if period not in {"today", "7d"}:
        raise ValueError("period must be today or 7d")
    now = datetime.now()
    points: list[dict] = []
    if period == "today":
        for hour in range(now.hour + 1):
            bucket = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            points.append({"timestamp": bucket.isoformat(), "inputTokens": 0, "outputTokens": 0, "cachedTokens": 0})
        key_column, table = "bucket_time", "token_daily"
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")
        key_length = 13
    else:
        first_day = now.date() - timedelta(days=6)
        for offset in range(7):
            bucket = first_day + timedelta(days=offset)
            points.append({"timestamp": bucket.isoformat(), "inputTokens": 0, "outputTokens": 0, "cachedTokens": 0})
        key_column, table = "usage_date", "token_weekly"
        cutoff = first_day.isoformat()
        key_length = 10

    point_map = {point["timestamp"][:key_length]: point for point in points}
    db_path = get_data_dir() / "wence_ai.db"
    if db_path.exists():
        try:
            database_uri = f"{db_path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(database_uri, uri=True, timeout=1) as connection:
                table_names = {
                    row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                if table in table_names:
                    rows = connection.execute(
                        f"SELECT {key_column}, input_tokens, output_tokens, cached_tokens "
                        f"FROM {table} WHERE {key_column} >= ? ORDER BY {key_column}",
                        (cutoff,),
                    ).fetchall()
                    for raw_key, input_tokens, output_tokens, cached_tokens in rows:
                        normalized_key = str(raw_key).replace(" ", "T")
                        point = point_map.get(normalized_key[:key_length])
                        if point is not None:
                            # The dashboard's input metric represents tokens
                            # that were not served from the prompt cache.
                            total_input = _safe_int(input_tokens)
                            cached_input = _safe_int(cached_tokens)
                            point.update(
                                inputTokens=max(0, total_input - cached_input),
                                outputTokens=_safe_int(output_tokens),
                                cachedTokens=cached_input,
                            )
        except sqlite3.Error as exc:
            raise RuntimeError("Token 使用数据库读取失败") from exc

    totals = {key: sum(point[key] for point in points) for key in ("inputTokens", "outputTokens", "cachedTokens")}
    return {"range": period, "points": points, "totals": totals}


async def query_token_usage(period: str) -> dict:
    """Read usage without blocking the FastAPI event loop."""
    import asyncio

    return await asyncio.to_thread(query_token_usage_sync, period)
