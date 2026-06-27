"""Personality 模块 — 人格 + 防御 + 关系 + 情绪锚点 + 记忆 + 内在生活."""

from .defense import DefenseMechanism
from .diary import DiaryAgent
from .dream import DreamAgent
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
    "DiaryAgent",
    "DreamAgent",
]
