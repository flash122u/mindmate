"""Personality 模块 — 人格系统."""

from .soul import SoulManager
from .defense import DefenseMechanism, DefenseResult, DefenseStrategy, TabooRule
from .relationship import RelationshipManager, RelationshipState

__all__ = [
    "SoulManager",
    "DefenseMechanism",
    "DefenseResult",
    "DefenseStrategy",
    "TabooRule",
    "RelationshipManager",
    "RelationshipState",
]
