"""测试能量模型."""

import sys
sys.path.insert(0, '..')

from mindmate.agent.energy import EnergyModel


def test_energy_initial():
    model = EnergyModel()
    level, interval = model.tick()
    assert level in ("LOW", "DEEP")


def test_energy_after_message():
    model = EnergyModel()
    model.on_user_message()
    level, interval = model.tick()
    assert level == "HIGH"
    assert interval == 10  # HIGH 时每10秒检查一次


def test_energy_reset():
    model = EnergyModel()
    model.reset()
    level, interval = model.tick()
    assert level == "HIGH"  # reset 设 last_interaction=now → 刚互动过
    assert interval == 10


def test_energy_state_tracking():
    model = EnergyModel()
    # 首次 tick
    model.tick()
    initial_ticks = model.state.consecutive_ticks
    # 同一 level 再 tick
    model.tick()
    assert model.state.consecutive_ticks > initial_ticks
