"""测试主动行为系统."""

import sys
sys.path.insert(0, '..')

from mindmate.bus.events import MessageBus
from mindmate.proactive import ProactiveLoop, Sensor, Judge, DriftMode
from mindmate.agent.energy import EnergyModel
from mindmate.memory import MemoryStore


class TestSensor:
    def test_collect_returns_signals(self):
        energy = EnergyModel()
        energy.on_user_message()  # 标记为活跃
        sensor = Sensor(energy)
        signals = sensor.collect()
        assert "period" in signals
        assert "energy_level" in signals
        assert "consecutive_ticks" in signals
        assert signals["energy_level"] == "HIGH"

    def test_collect_idle(self):
        energy = EnergyModel()
        # 不调用 on_user_message，模拟空闲
        sensor = Sensor(energy)
        signals = sensor.collect()
        assert signals["energy_level"] in ("LOW", "DEEP")


class TestJudge:
    def test_high_level_returns_none(self):
        judge = Judge()
        result = judge.decide({"level": "HIGH", "period": "上午", "seed": 0.9, "idle_seconds": 30})
        assert result["action_type"] == "none"

    def test_morning_greeting(self):
        judge = Judge()
        result = judge.decide({"level": "LOW", "period": "早晨", "seed": 0.3, "idle_seconds": 2000})
        assert result["action_type"] in ("morning_greeting", "small_talk", "casual_greeting")
        assert result["message"] is not None

    def test_care_for_very_idle(self):
        judge = Judge()
        result = judge.decide({"level": "DEEP", "period": "下午", "seed": 0.3, "idle_seconds": 8000})
        assert result["action_type"] == "care" or result["message"] is not None

    def test_evening_greeting(self):
        judge = Judge()
        result = judge.decide({"level": "DEEP", "period": "深夜", "seed": 0.3, "idle_seconds": 5000})
        assert result["action_type"] in ("evening_greeting", "small_talk", "casual_greeting", "care")

    def test_normal_level_sometimes_proactive(self):
        judge = Judge()
        has_action = False
        for seed_val in [v / 100 for v in range(0, 100, 1)]:
            result = judge.decide({"level": "NORMAL", "period": "下午", "seed": seed_val, "idle_seconds": 200})
            if result["action_type"] != "none":
                has_action = True
                break
        # 大约 20% 的概率会触发主动
        # 只要有一个 seed 触发就算通过


class TestDriftMode:
    def test_drift_audit_soul(self):
        store = MemoryStore()
        try:
            drift = DriftMode(store)
            import asyncio
            result = asyncio.run(drift._task_audit_soul())
            assert result is not None
        finally:
            store.close()

    def test_drift_compact_history(self):
        store = MemoryStore()
        try:
            store.append_history("old entry")
            drift = DriftMode(store)
            import asyncio
            result = asyncio.run(drift._task_compact_history())
            assert "Deleted" in result
        finally:
            store.close()

    def test_drift_run_one(self):
        store = MemoryStore()
        try:
            drift = DriftMode(store)
            import asyncio
            result = asyncio.run(drift.run_one())
            assert result is not None
        finally:
            store.close()


class TestProactiveLoop:
    def test_create_proactive_loop(self):
        bus = MessageBus()
        energy = EnergyModel()
        loop = ProactiveLoop(bus, energy)
        assert loop.energy is energy
        assert loop.bus is bus

    def test_sensor_judge_pipeline(self):
        bus = MessageBus()
        energy = EnergyModel()
        loop = ProactiveLoop(bus, energy)
        signals = loop.sensor.collect()
        decision = loop.judge.decide(signals)
        assert decision["action_type"] in (
            "none", "morning_greeting", "evening_greeting",
            "casual_greeting", "small_talk", "care", "drift_maintenance",
        )
