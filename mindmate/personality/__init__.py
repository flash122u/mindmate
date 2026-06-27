"""Personality 模块 — 人格系统 + 防御机制 + 关系演进."""

from .soul import SoulManager
from .defense import DefenseMechanism
from .relationship import RelationshipManager

__all__ = ["SoulManager", "DefenseMechanism", "RelationshipManager"]
