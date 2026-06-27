"""人格系统 — 人格核心 + 防御机制 + 关系演进."""

from .defense import DefenseSystem
from .relationship import RelationshipManager
from .soul import SoulManager

__all__ = ["SoulManager", "DefenseSystem", "RelationshipManager"]
