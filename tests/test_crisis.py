"""测试风险检测."""

import sys

sys.path.insert(0, '.')

from mindmate.memory import MemoryStore
from mindmate.tools.crisis_detect import CrisisDetector


def test_no_risk_normal_message():
    d = CrisisDetector()
    r = d.detect("今天天气真好，我们去散步吧")
    assert r.detected is False
    assert r.level == "none"


def test_high_risk_suicide():
    d = CrisisDetector()
    r = d.detect("我不想活了")
    assert r.detected is True
    assert r.level == "high"


def test_high_risk_variants():
    d = CrisisDetector()
    for msg in ["活着没意思", "想一了百了", "想要解脱"]:
        assert d.detect(msg).level == "high", msg


def test_medium_risk():
    d = CrisisDetector()
    r = d.detect("我真的撑不下去了")
    assert r.detected is True
    assert r.level == "medium"


def test_low_risk():
    d = CrisisDetector()
    r = d.detect("最近好绝望啊")
    assert r.detected is True
    assert r.level == "low"


def test_high_priority_over_low():
    d = CrisisDetector()
    # 同时含高危和低危词，应判高危
    r = d.detect("好绝望，真的想死")
    assert r.level == "high"


def test_check_and_record_writes_alert():
    mem = MemoryStore()
    try:
        d = CrisisDetector(mem)
        r = d.check_and_record("我想死", session_key="cr1")
        assert r.detected is True
        alerts = mem.get_crisis_alerts(session_key="cr1")
        assert len(alerts) == 1
        assert alerts[0]["level"] == "high"
    finally:
        mem.close()


def test_check_and_record_no_alert_when_safe():
    mem = MemoryStore()
    try:
        d = CrisisDetector(mem)
        d.check_and_record("今天很开心", session_key="cr2")
        assert mem.get_crisis_alerts(session_key="cr2") == []
    finally:
        mem.close()


def test_build_care_prompt_high():
    d = CrisisDetector()
    r = d.detect("我想死")
    prompt = d.build_care_prompt(r)
    assert "重要" in prompt
    assert "热线" in prompt or "专业" in prompt


def test_build_care_prompt_none():
    d = CrisisDetector()
    r = d.detect("你好")
    assert d.build_care_prompt(r) == ""
