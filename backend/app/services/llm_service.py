"""
LiteLLM 统一模型调用服务封装。
支持 OpenAI / DeepSeek / Qwen / Claude 等兼容 OpenAI 格式的模型。
"""
import time
import asyncio
from typing import Optional, AsyncGenerator

import httpx
from app.core.config import settings


class LLMService:
    """统一 LLM 调用服务，支持多种模型接入"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def chat(
        self,
        api_base: str,
        api_key: str,
        model_identifier: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: int = 3,
    ) -> dict:
        """调用 LLM 完成对话，带重试机制"""
        client = await self._get_client()
        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_identifier,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                start = time.perf_counter()
                response = await client.post(url, json=payload, headers=headers)
                elapsed_ms = int((time.perf_counter() - start) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    return {
                        "success": True,
                        "content": content,
                        "usage": usage,
                        "latency_ms": elapsed_ms,
                        "model": model_identifier,
                    }
                else:
                    error_detail = response.text[:500]
                    last_error = f"HTTP {response.status_code}: {error_detail}"
                    if response.status_code == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
            except httpx.TimeoutException:
                last_error = "请求超时"
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = str(e)
                await asyncio.sleep(1)

        return {
            "success": False,
            "content": "",
            "error": last_error,
            "latency_ms": 0,
            "model": model_identifier,
        }

    async def chat_stream(
        self,
        api_base: str,
        api_key: str,
        model_identifier: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM"""
        client = await self._get_client()
        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_identifier,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except Exception:
                        continue

    async def ping(self, api_base: str, api_key: str, model_identifier: str) -> dict:
        """测试模型连通性"""
        result = await self.chat(
            api_base=api_base,
            api_key=api_key,
            model_identifier=model_identifier,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
            max_retries=1,
        )
        return {
            "success": result["success"],
            "latency_ms": result.get("latency_ms", 0),
            "message": "连接成功" if result["success"] else result.get("error", "连接失败"),
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# 全局单例
llm_service = LLMService()
