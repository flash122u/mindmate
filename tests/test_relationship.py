"""测试关系管理系统."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality import RelationshipManager


def test_relationship_initial():
    store = MemoryStore()
    try:
        rel = RelationshipManager(store)
        state = rel.get_current("rel_test")
        assert state["stage"] == "初识"
        assert state["style"]["tone"] == "礼貌、稍显拘谨"
    finally:
        store.close()


def test_relationship_style_instructions():
    store = MemoryStore()
    try:
        rel = RelationshipManager(store)
        instructions = rel.get_style_instructions("rel_style")
        assert "初识" in instructions
        assert "礼貌" in instructions
    finally:
        store.close()


def test_relationship_advance():
    """推进需要至少 3 条历史 + 正向互动."""
    store = MemoryStore()
    try:
        rel = RelationshipManager(store)
        # 先写 3 条历史（模拟互动）
        store.append_history("[user] 今天心情不错", "rel_adv")
        store.append_history("[Assistant] 太好了，什么事让你开心？", "rel_adv")
        store.append_history("[user] 和朋友吃了顿好吃的", "rel_adv")

        # 记录正向互动
        rel.record_interaction(0.7, "rel_adv")
        rel.record_interaction(0.6, "rel_adv")

        state = rel.get_current("rel_adv")
        assert state["stage"] == "朋友"
    finally:
        store.close()


def test_relationship_not_advance_without_history():
    """没有历史的情况下不应该推进."""
    store = MemoryStore()
    try:
        rel = RelationshipManager(store)
        rel.record_interaction(0.8, "rel_no_hist")
        rel.record_interaction(0.7, "rel_no_hist")
        state = rel.get_current("rel_no_hist")
        assert state["stage"] == "初识"
    finally:
        store.close()


def test_relationship_retreat():
    """强负向互动可以退步."""
    store = MemoryStore()
    try:
        rel = RelationshipManager(store)
        # 先推进
        store.append_history("[user] 你好", "rel_ret")
        store.append_history("[Assistant] 嗨", "rel_ret")
        store.append_history("[user] 今天很好", "rel_ret")
        rel.record_interaction(0.8, "rel_ret")
        rel.record_interaction(0.7, "rel_ret")
        assert rel.get_current("rel_ret")["stage"] == "朋友"

        # 强负向 → 退回
        rel.record_interaction(-0.6, "rel_ret")
        state = rel.get_current("rel_ret")
        assert state["stage"] == "初识"
    finally:
        store.close()
