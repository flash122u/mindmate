"""测试能量模型."""

import sys
sys.path.insert(0, '..')

from mindmate.agent.energy import EnergyModel


def test_energy_initial():
    model = EnergyModel()
    level, interval = model.tick()
    assert level == "LOW"


def test_energy_after_message():
    model = EnergyModel()
    model.on_user_message()
    level, interval = model.tick()
    assert level == "HIGH"
    assert interval == 0


def test_energy_reset():
    model = EnergyModel()
    model.reset()
    level, interval = model.tick()
    # reset() 设置了 last_interaction = now，所以 tick() 检测到刚互动过 → HIGH
    assert level == "HIGH"
    assert interval == 0  # 暂停主动行为
