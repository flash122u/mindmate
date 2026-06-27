"""天气工具 —— 让小暖能感知真实天气.

用 wttr.in（免费、无需 API key）查询实时天气，返回简短可读的中文描述。
配合情绪锚点（如"下雨天=安心"），让小暖的世界更真实。
"""

from __future__ import annotations

import httpx
from loguru import logger

from mindmate.tools.base import Tool


class WeatherTool(Tool):
    """查询某地实时天气."""

    name = "get_weather"
    description = (
        "查询某个城市的实时天气（温度、天气状况、体感、湿度）。"
        "当对话提到天气、某地冷不冷热不热、要不要带伞、出门穿什么时可以用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "城市名，如 '北京'、'Shanghai'、'东京'",
            }
        },
        "required": ["location"],
    }

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    async def execute(self, location: str = "", **_: object) -> str:
        location = (location or "").strip()
        if not location:
            return "[未提供城市名]"

        # wttr.in 的紧凑格式：天气状况 + 温度 + 体感 + 湿度（中文、公制）
        url = f"https://wttr.in/{location}"
        params = {"format": "%C %t 体感%f 湿度%h", "lang": "zh", "m": ""}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                text = resp.text.strip()
        except Exception as e:
            logger.warning("Weather lookup failed for {}: {}", location, e)
            return f"[查不到 {location} 的天气，可能是网络问题]"

        if not text or "Unknown location" in text or "Sorry" in text:
            return f"[找不到 {location} 这个地方]"
        return f"{location}：{text}"
