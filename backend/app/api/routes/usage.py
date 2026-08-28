"""Token usage statistics endpoints."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services.token_usage import query_token_usage

router = APIRouter()


@router.get("/token-usage")
async def get_token_usage(period: Literal["today", "7d"] = Query("today", alias="range")):
    try:
        return await query_token_usage(period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
