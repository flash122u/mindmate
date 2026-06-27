"""测试关系阶段管理."""

import sys

sys.path.insert(0, '.')

from mindmate.memory import MemoryStore
from mindmate.personality.relationship import RelationshipManager


def test_initial_stage():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        state = rm.get_state("rel_t1")
        assert state.stage == "初识"
    finally:
        mem.close()


def test_score_positive_message():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        score = rm.score_message("谢谢你，你真的很懂我")
        assert score > 0
    finally:
        mem.close()


def test_score_negative_message():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        score = rm.score_message("你好烦，闭嘴")
        assert score < 0
    finally:
        mem.close()


def test_relationship_evolves_to_friend():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        for _ in range(15):
            rm.update("谢谢你，好喜欢和你聊天，好开心", "rel_t2")
        state = rm.get_state("rel_t2")
        assert state.stage in ("朋友", "信赖")
    finally:
        mem.close()


def test_relationship_score_floor():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        for _ in range(10):
            rm.update("讨厌，滚开", "rel_t3")
        state = rm.get_state("rel_t3")
        assert state.score >= 0
    finally:
        mem.close()


def test_build_relationship_prompt():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        prompt = rm.build_relationship_prompt("rel_t4")
        assert "关系" in prompt
        assert "初识" in prompt
    finally:
        mem.close()


def test_stage_for_score():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        assert rm._stage_for_score(0) == "初识"
        assert rm._stage_for_score(25) == "朋友"
        assert rm._stage_for_score(70) == "信赖"
    finally:
        mem.close()


def test_normal_message_grows_familiarity():
    mem = MemoryStore()
    try:
        rm = RelationshipManager(mem)
        score = rm.score_message("今天去上班了")
        assert score >= 1
    finally:
        mem.close()
