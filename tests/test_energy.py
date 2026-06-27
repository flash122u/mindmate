"""测试能量模型（主动开口调度）."""

import sys

sys.path.insert(0, '.')

import time

from mindmate.agent.energy import EnergyModel


def _noon(day_offset_days: float = 0) -> float:
    """返回一个确定落在非安静时段（中午12点）的时间戳."""
    base = time.mktime((2026, 6, 27, 12, 0, 0, 0, 0, -1))
    return base + day_offset_days * 86400


def test_fresh_model_not_idle():
    e = EnergyModel(idle_threshold_s=1800)
    e.on_user_message(now=_noon())
    ok, reason = e.should_reach_out(now=_noon() + 60)  # 才过 1 分钟
    assert ok is False
    assert reason == "not_idle_enough"


def test_idle_long_enough_reaches_out():
    e = EnergyModel(idle_threshold_s=1800)
    e.on_user_message(now=_noon())
    ok, reason = e.should_reach_out(now=_noon() + 2000)  # 超过 30 分钟
    assert ok is True
    assert reason == "ok"


def test_quiet_hour_blocks():
    e = EnergyModel(idle_threshold_s=1800, quiet_start=23, quiet_end=8)
    midnight = time.mktime((2026, 6, 27, 2, 0, 0, 0, 0, -1))  # 凌晨2点
    e.on_user_message(now=midnight - 10000)
    ok, reason = e.should_reach_out(now=midnight)
    assert ok is False
    assert reason == "quiet_hour"


def test_cooldown_blocks():
    e = EnergyModel(idle_threshold_s=1800, cooldown_s=7200)
    e.on_user_message(now=_noon())
    e.mark_proactive(now=_noon() + 2000)
    # 主动后过一会又沉默够久，但还在冷却中
    ok, reason = e.should_reach_out(now=_noon() + 2000 + 1800 + 60)
    assert ok is False
    assert reason == "cooldown"


def test_daily_limit():
    e = EnergyModel(idle_threshold_s=1800, cooldown_s=0, max_per_day=2)
    t = _noon()
    for _ in range(2):
        e.on_user_message(now=t)
        e.mark_proactive(now=t + 2000)
        t += 2000 + 60
    e.on_user_message(now=t)
    ok, reason = e.should_reach_out(now=t + 2000)
    assert ok is False
    assert reason == "daily_limit"


def test_quiet_hour_detection_cross_midnight():
    e = EnergyModel(quiet_start=23, quiet_end=8)
    assert e.is_quiet_hour(23) is True
    assert e.is_quiet_hour(2) is True
    assert e.is_quiet_hour(7) is True
    assert e.is_quiet_hour(8) is False
    assert e.is_quiet_hour(12) is False
    assert e.is_quiet_hour(22) is False


def test_mark_proactive_resets_idle():
    e = EnergyModel(idle_threshold_s=1800)
    e.on_user_message(now=_noon())
    e.mark_proactive(now=_noon() + 2000)
    # 主动后立刻检查，沉默计时已重置 → 不够 idle
    ok, reason = e.should_reach_out(now=_noon() + 2000 + 60)
    assert ok is False
    assert reason in ("not_idle_enough", "cooldown")


def test_daily_count_resets_next_day():
    e = EnergyModel(idle_threshold_s=1800, cooldown_s=0, max_per_day=1)
    e.mark_proactive(now=_noon())
    assert e._proactive_count == 1
    e.mark_proactive(now=_noon(day_offset_days=1))  # 第二天
    assert e._proactive_count == 1  # 计数重置后又 +1
