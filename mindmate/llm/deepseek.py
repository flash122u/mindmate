"""LLM Provider — DeepSeek (兼容 OpenAI SDK)，支持工具调用."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from mindmate.config import settings


class DeepSeekProvider:
    """DeepSeek LLM Provider，兼容 OpenAI API 格式."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model: str = settings.deepseek_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """发送聊天请求，返回结构化响应.

        返回字段：
        - content: 文本回复（可能为 None，当模型选择调用工具时）
        - tool_calls: 解析后的工具调用 [{id, name, arguments(dict)}]，无则 None
        - raw_message: 助手消息的原始 dict（用于把这一回合追加进 messages）
        - finish_reason / usage
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls = None
        if getattr(message, "tool_calls", None):
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    {"id": tc.id, "name": tc.function.name, "arguments": args}
                )

        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "raw_message": message.model_dump(exclude_none=True),
            "finish_reason": response.choices[0].finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }
