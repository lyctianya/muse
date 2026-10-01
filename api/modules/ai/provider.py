"""LLM 厂商抽象：OpenAI 兼容接口（/chat/completions，stream:true）。

覆盖：OpenAI / DeepSeek / Moonshot(Kimi) / Qwen / GLM / 硅基流动 /
OpenRouter / Ollama / vLLM 等。Anthropic/Gemini 原生协议后续可扩展。
"""
import json
from typing import AsyncIterator

import httpx


class ProviderError(Exception):
    pass


async def stream_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncIterator[dict]:
    """流式对话，yield OpenAI chunk dict。网络/协议错误抛 ProviderError。"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": messages, "stream": True}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    try:
                        detail = json.loads(body).get("error", {}).get("message") or body.decode()[:300]
                    except Exception:
                        detail = body.decode(errors="ignore")[:300]
                    raise ProviderError(f"厂商返回 {resp.status_code}：{detail}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue
    except httpx.HTTPError as e:
        raise ProviderError(f"请求厂商失败：{e}")


def extract_delta_text(chunk: dict) -> str:
    """从 chunk 取增量文本，兼容 choices[0].delta.content / message.content。"""
    try:
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        text = delta.get("content")
        if text is None:
            text = (choices[0].get("message") or {}).get("content") or ""
        return text or ""
    except Exception:
        return ""
