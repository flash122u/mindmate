"""测试每日调度器 + list_sessions."""

import sys

sys.path.insert(0, '.')

import asyncio
from datetime import datetime

from mindmate.agent.scheduler import DailyScheduler
from mindmate.memory import MemoryStore


def test_list_sessions_distinct():
    mem = MemoryStore()
    try:
        mem.append_history("user", "hi", session_key="u1")
        mem.append_history("assistant", "yo", session_key="u1")
        mem.append_history("user", "hello", session_key="u2")
        sessions = mem.list_sessions()
        assert "u1" in sessions
        assert "u2" in sessions
        assert sessions.count("u1") == 1  # 去重
    finally:
        mem.close()


def test_list_sessions_empty(tmp_path):
    # 隔离的全新库（无对话）应返回空
    mem = MemoryStore(workspace=tmp_path)
    try:
        assert mem.list_sessions() == []
    finally:
        mem.close()


def _clock(hour):
    return lambda: datetime(2026, 6, 27, hour, 0, 0)


def test_scheduler_skips_off_hour():
    fired = []

    async def run_cb(sk):
        fired.append(sk)

    sched = DailyScheduler(
        run_cb=run_cb,
        list_sessions=lambda: ["u1", "u2"],
        hour=3,
        clock=_clock(14),  # 下午2点，非目标时段
    )

    async def run():
        return await sched.tick()

    n = asyncio.run(run())
    assert n == 0
    assert fired == []


def test_scheduler_fires_at_target_hour():
    fired = []

    async def run_cb(sk):
        fired.append(sk)

    sched = DailyScheduler(
        run_cb=run_cb,
        list_sessions=lambda: ["u1", "u2"],
        hour=3,
        clock=_clock(3),
    )

    async def run():
        return await sched.tick()

    n = asyncio.run(run())
    assert n == 2
    assert set(fired) == {"u1", "u2"}


def test_scheduler_no_duplicate_same_day():
    fired = []

    async def run_cb(sk):
        fired.append(sk)

    sched = DailyScheduler(
        run_cb=run_cb,
        list_sessions=lambda: ["u1"],
        hour=3,
        clock=_clock(3),
    )

    async def run():
        await sched.tick()
        await sched.tick()  # 同一天再触发一次
        return len(fired)

    total = asyncio.run(run())
    assert total == 1  # 同一天只触发一次


def test_scheduler_fires_again_next_day():
    fired = []

    async def run_cb(sk):
        fired.append(sk)

    current = {"day": 27}

    def clock():
        return datetime(2026, 6, current["day"], 3, 0, 0)

    sched = DailyScheduler(
        run_cb=run_cb,
        list_sessions=lambda: ["u1"],
        hour=3,
        clock=clock,
    )

    async def run():
        await sched.tick()
        current["day"] = 28  # 第二天
        await sched.tick()
        return len(fired)

    total = asyncio.run(run())
    assert total == 2


def test_scheduler_one_user_failure_does_not_block_others():
    fired = []

    async def run_cb(sk):
        if sk == "bad":
            raise RuntimeError("boom")
        fired.append(sk)

    sched = DailyScheduler(
        run_cb=run_cb,
        list_sessions=lambda: ["bad", "good"],
        hour=3,
        clock=_clock(3),
    )

    async def run():
        return await sched.tick()

    n = asyncio.run(run())
    assert "good" in fired
    assert n == 1  # 只有 good 成功
