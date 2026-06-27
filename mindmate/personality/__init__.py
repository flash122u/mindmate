"""Personality 模块 — 人格系统 + 防御 + 关系 + 情绪锚点 + 记忆."""

from .defense import DefenseMechanism
from .emotion_anchor import EmotionAnchorManager
from .forget import ForgetAgent
from .memory_consolidator import MemoryConsolidator
from .relationship import RelationshipManager
from .soul import SoulManager

__all__ = [
    "SoulManager",
    "DefenseMechanism",
    "RelationshipManager",
    "EmotionAnchorManager",
    "MemoryConsolidator",
    "ForgetAgent",
]
