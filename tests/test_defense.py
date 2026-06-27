"""测试防御机制."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality import DefenseSystem


def test_no_taboo_triggered():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        result = defense.check("今天天气真不错")
        assert result is None
    finally:
        store.close()


def test_taboo_robot_triggered():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        result = defense.check("你是不是机器人？")
        assert result is not None
        assert result["strategy"] in ("gentle", "refuse", "deflect", "vague")
    finally:
        store.close()


def test_taboo_diary_triggered():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        result = defense.check("你昨天日记里写了什么？")
        assert result is not None
    finally:
        store.close()


def test_defense_system_prompt():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        prompt = defense.get_defense_system_prompt()
        assert "雷区" in prompt
    finally:
        store.close()


def test_defense_instruction_gentle():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        instruction = defense._build_instruction("gentle", "你是不是机器人？")
        assert "不想讨论" in instruction or "温柔" in instruction
    finally:
        store.close()


def test_defense_instruction_deflect():
    store = MemoryStore()
    try:
        defense = DefenseSystem(store)
        instruction = defense._build_instruction("deflect", "测试雷区")
        assert "转移话题" in instruction
    finally:
        store.close()
