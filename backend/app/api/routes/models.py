"""
多平台模型聚合接口
支持 OpenAI、智谱等多个平台，通过白名单过滤模型
"""

import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Literal

from fastapi import APIRouter
import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator

from app.core.config import get_user_settings_file
from app.core.logging import get_logger
from app.models.chat import ModelInfo, ModelsResponse

logger = get_logger(__name__)
router = APIRouter()

# 设置文件路径
SETTINGS_FILE = get_user_settings_file()


# ============== 模型名称格式化 ==============

# 需要全大写的前缀/品牌词
UPPERCASE_WORDS = {"gpt", "glm", "dall", "llama", "yi", "ernie", "ppt", "cogview", "embedding"}


def format_model_name(model_id: str) -> str:
    """
    格式化模型 ID 为显示名称

    规则：
    1. 特定品牌词全大写：gpt -> GPT, glm -> GLM
    2. 其他词首字母大写：claude -> Claude, sonnet -> Sonnet
    3. 版本号连字符转点号：4-5 -> 4.5
    4. 保留数字和字母的连接：4o -> 4o

    示例：
    - gpt-4o -> GPT-4o
    - gpt-4o-mini -> GPT-4o Mini
    - glm-4-flash -> GLM-4 Flash
    - claude-sonnet-4-5 -> Claude Sonnet 4.5
    - deepseek-v3 -> Deepseek V3
    - qwen-turbo -> QWEN Turbo
    """
    import re

    # 按 - 分割
    parts = model_id.split("-")
    result_parts = []
    i = 0

    while i < len(parts):
        part = parts[i]

        # 检查是否是需要全大写的词
        if part.lower() in UPPERCASE_WORDS:
            result_parts.append(part.upper())
        # 检查是否是纯数字，可能是版本号的一部分
        elif part.isdigit() and i + 1 < len(parts) and parts[i + 1].isdigit():
            # 将 "4-5" 这样的版本号合并为 "4.5"
            result_parts.append(f"{part}.{parts[i + 1]}")
            i += 1  # 跳过下一个部分
        # 检查是否是数字开头（如 4o, 3.5）
        elif re.match(r"^\d", part):
            # 如果前一个是大写词，用连字符连接（如 GPT-4o）
            if result_parts and result_parts[-1].isupper():
                result_parts[-1] = result_parts[-1] + "-" + part
            else:
                result_parts.append(part)
        else:
            # 普通词首字母大写
            result_parts.append(part.capitalize())

        i += 1

    return " ".join(result_parts)


def load_user_settings() -> dict:
    """加载用户设置"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"providers": []}
    except Exception as e:
        logger.error(f"加载用户设置失败: {e}")
        return {"providers": []}


def get_enabled_models_from_settings() -> list[ModelInfo]:
    """
    从用户设置中获取已启用的模型
    """
    settings_data = load_user_settings()
    enabled_models = []
    providers = settings_data.get("providers", [])
    provider_order = {(provider.get("name", "Unknown") or "Unknown"): index for index, provider in enumerate(providers)}

    for provider in providers:
        if not provider.get("enabled", True):
            continue

        provider_name = provider.get("name", "Unknown")

        for model in provider.get("models", []):
            if model.get("enabled", False):
                model_id = model.get("id", "")
                model_name = model.get("name") or format_model_name(model_id)

                enabled_models.append(ModelInfo(id=model_id, name=model_name, provider=provider_name))

    # 按“提供商添加顺序 -> 模型名称”排序
    enabled_models.sort(
        key=lambda m: (
            provider_order.get(m.provider or "Unknown", len(provider_order)),
            (m.name or "").lower(),
        )
    )
    return enabled_models


# ============== API 路由 ==============


@router.get("/models", response_model=ModelsResponse)
async def get_models():
    """
    获取用户启用的模型列表
    从用户设置中读取已添加且启用的模型
    """
    try:
        models = get_enabled_models_from_settings()
        return ModelsResponse(success=True, models=models)
    except Exception as e:
        logger.error(f"❌ 获取模型列表失败: {e}")
        return ModelsResponse(success=True, models=[])


@router.post("/models/refresh")
async def refresh_models():
    """
    刷新模型列表（重新从设置文件读取）
    """
    models = get_enabled_models_from_settings()
    return {"success": True, "message": f"已刷新，共 {len(models)} 个可用模型"}


class ProviderModelsRequest(BaseModel):
    """获取 Provider 模型列表的请求体"""

    base_url: str
    api_key: str
    api_type: Literal["openai", "anthropic"] = "openai"


class ProviderConnectionRequest(ProviderModelsRequest):
    """Test a selected model with the current, possibly unsaved credentials."""

    model: str

    @field_validator("base_url", "api_key", "model")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("base_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("Base URL 必须是有效的 HTTP 或 HTTPS 地址")
        return value


def normalize_base_url(base_url: str) -> str:
    """
    标准化 base_url
    - 移除末尾的 /
    - 如果没有版本后缀（如 /v1），自动添加 /v1
    """
    url = base_url.rstrip("/")

    # 检查是否已有版本后缀（如 /v1, /v2 等）
    import re

    if not re.search(r"/v\d+$", url):
        url = url + "/v1"

    return url


@router.post("/providers/test-connection")
async def test_provider_connection(request: ProviderConnectionRequest):
    """Measure a short model request, without saving settings or creating a chat."""
    from app.services.llm_client import get_proxy_url

    try:
        base_url = normalize_base_url(request.base_url)
        body = {
            "model": request.model,
            "messages": [{"role": "user", "content": "Reply with only OK."}],
            "stream": False,
        }
        if request.api_type == "anthropic":
            url = f"{base_url}/messages"
            headers = {"x-api-key": request.api_key, "anthropic-version": "2023-06-01"}
            body["max_tokens"] = 16
        else:
            url = f"{base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {request.api_key}"}

        # Bound the entire request, including a slow/trickling response body.
        async with asyncio.timeout(20):
            async with httpx.AsyncClient(timeout=20, proxy=get_proxy_url()) as client:
                started = perf_counter()
                response = await client.post(url, headers=headers, json=body)
                latency_ms = max(0, round((perf_counter() - started) * 1000))
                response.raise_for_status()
                data = response.json()

        if not isinstance(data, dict):
            raise ValueError("服务商返回了无效的模型响应，请检查 Base URL 和 API 类型")
        if data.get("error"):
            error = data["error"]
            raise ValueError(str(error.get("message", error) if isinstance(error, dict) else error))
        if request.api_type == "anthropic":
            valid = data.get("type") == "message" and isinstance(data.get("content"), list)
        else:
            choices = data.get("choices")
            valid = (
                isinstance(choices, list)
                and bool(choices)
                and isinstance(choices[0], dict)
                and isinstance(choices[0].get("message"), dict)
            )
        if not valid:
            raise ValueError("服务商返回了无效的模型响应，请检查 Base URL 和 API 类型")
        return {"success": True, "latency_ms": latency_ms}
    except (TimeoutError, httpx.TimeoutException):
        return {"success": False, "error": "连接超时（20 秒），请检查网络或稍后重试"}
    except httpx.HTTPStatusError as exc:
        detail = exc.response.reason_phrase
        try:
            data = exc.response.json()
            error = data.get("error", {}) if isinstance(data, dict) else {}
            detail = str(error.get("message") or detail) if isinstance(error, dict) else str(error or detail)
        except ValueError:
            pass
        detail = detail.replace(request.api_key, "***")[:500]
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {detail}"}
    except httpx.RequestError:
        return {"success": False, "error": "无法连接模型服务，请检查 Base URL、网络和代理设置"}
    except Exception as exc:
        return {"success": False, "error": str(exc).replace(request.api_key, "***")[:500] or "连接测试失败"}


@router.post("/providers/models")
async def get_provider_models(request: ProviderModelsRequest):
    """
    获取指定 Provider 的可用模型列表
    - openai: 通过 OpenAI 兼容的 /models 接口获取
    - anthropic: 通过 Anthropic 风格的 /v1/models 接口获取
    """
    try:
        if request.api_type == "anthropic":
            base = request.base_url.rstrip("/")
            if base.endswith("/v1"):
                url = f"{base}/models"
            else:
                url = f"{base}/v1/models"

            logger.info(f"📡 获取 Anthropic 模型列表: {url}")
            headers = {
                "x-api-key": request.api_key,
                "anthropic-version": "2023-06-01",
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if not model_id:
                    continue
                models.append(
                    {
                        "id": model_id,
                        "name": format_model_name(model_id),
                        "owned_by": model.get("owned_by", "anthropic"),
                    }
                )
        else:
            # 标准化 base_url（自动补全 /v1）
            base_url = normalize_base_url(request.base_url)
            logger.info(f"📡 获取 OpenAI 兼容模型列表: {base_url}")

            # 创建 OpenAI 客户端
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=request.api_key,
            )

            # 获取模型列表
            models_response = await client.models.list()

            # 转换为统一格式
            models = []
            for model in models_response.data:
                models.append(
                    {
                        "id": model.id,
                        "name": format_model_name(model.id),
                        "owned_by": getattr(model, "owned_by", "unknown"),
                    }
                )

        # 按模型 ID 字母顺序排序
        models.sort(key=lambda m: m["id"].lower())
        return {"success": True, "models": models}

    except Exception as e:
        logger.error(f"❌ 获取 Provider 模型列表失败: {e}")
        return {"success": False, "error": str(e), "models": []}
