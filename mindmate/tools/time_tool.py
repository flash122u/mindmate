"""时间工具 —— 让小暖能感知真实时间.

当对话提到时间、几点、星期几、日期时，小暖能给出准确回答。
还能在深夜时主动关心用户作息。
"""

from __future__ import annotations

from datetime import datetime, timezone

from mindmate.tools.base import Tool


class TimeTool(Tool):
    """查询当前时间和日期."""

    name = "get_time"
    description = (
        "查询当前日期、时间、星期、是否为深夜。"
        "当用户问'现在几点''今天是几号''星期几''是不是很晚了'时用这个。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "timezone_offset": {
                "type": "string",
                "description": "时区偏移，如 '+8' (东八区/中国)，默认 '+8'",
            }
        },
    }

    def __init__(self, default_tz: str = "+8") -> None:
        self.default_tz = default_tz

    async def execute(self, timezone_offset: str = "", **_: object) -> str:
        offset_str = (timezone_offset or self.default_tz).strip()
        # 解析时区偏移
        try:
            offset_hours = int(offset_str.replace("+", ""))
        except ValueError:
            offset_hours = 8
        tz = timezone(__import__("datetime").timedelta(hours=offset_hours))
        now = datetime.now(tz)

        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        hour = now.hour
        # 时段判断
        if 5 <= hour < 8:
            period = "清晨"
        elif 8 <= hour < 12:
            period = "上午"
        elif 12 <= hour < 14:
            period = "中午"
        elif 14 <= hour < 18:
            period = "下午"
        elif 18 <= hour < 22:
            period = "晚上"
        elif 22 <= hour < 24:
            period = "深夜"
        else:
            period = "凌晨"

        is_late = hour >= 23 or hour < 5

        lines = [
            f"现在是 {now.strftime('%Y年%m月%d日')}",
            f"星期{weekday_names[now.weekday()]}",
            f"时间 {now.strftime('%H:%M')}",
            f"时段：{period}",
        ]
        if is_late:
            lines.append("⚠️ 已经是深夜了，用户可能需要休息了。")

        return "，".join(lines)
