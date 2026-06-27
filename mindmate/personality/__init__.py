"""Personality 模块 — 人格系统 + 防御机制 + 关系演进."""

from .defense import DefenseMechanism
from .relationship import RelationshipManager
from .soul import SoulManager

__all__ = ["SoulManager", "DefenseMechanism", "RelationshipManager"]
