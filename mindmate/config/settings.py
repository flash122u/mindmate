"""配置加载 — 参考 nanobot config/loader.py + schema.py."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（CLAUDE.md 所在目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"


def ensure_dirs() -> None:
    """确保必要的目录存在."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    (MEMORY_DIR / "sessions").mkdir(parents=True, exist_ok=True)


class Settings:
    """全局配置对象."""

    def __init__(self) -> None:
        load_dotenv(PROJECT_ROOT / ".env")
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "19876"))
        # 每日内在生活（日记/梦）调度
        self.inner_life_enabled: bool = (
            os.getenv("INNER_LIFE_ENABLED", "true").lower() == "true"
        )
        self.inner_life_hour: int = int(os.getenv("INNER_LIFE_HOUR", "3"))
        # 小暖自己所在的城市（用于主动感知天气，方向 A）
        self.home_city: str = os.getenv("HOME_CITY", "杭州")
        # 工具开关 + MCP server 配置（JSON 字符串）
        self.tools_enabled: bool = (
            os.getenv("TOOLS_ENABLED", "true").lower() == "true"
        )
        _default_mcp = json.dumps({
            "music": {
                "command": "python",
                "args": ["-m", "mindmate.tools.mcp_servers.music_server"],
            }
        }, ensure_ascii=False)
        self.mcp_servers: dict = self._parse_mcp_servers(
            os.getenv("MCP_SERVERS", _default_mcp)
        )
        ensure_dirs()

    @staticmethod
    def _parse_mcp_servers(raw: str) -> dict:
        """解析 MCP_SERVERS 环境变量（JSON），失败则返回空."""
        import json

        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


# 全局配置实例
settings = Settings()
