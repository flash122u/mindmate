"""测试消息分段 + 打字延迟."""

import sys

sys.path.insert(0, '.')

from mindmate.utils.splitter import split_message, think_delay, typing_delay


def test_empty_message():
    assert split_message("") == []
    assert split_message("   ") == []


def test_single_short_sentence():
    result = split_message("你好呀")
    assert result == ["你好呀"]


def test_split_multiple_sentences():
    text = "今天过得怎么样？我有点担心你。要不要聊聊？"
    result = split_message(text)
    assert len(result) >= 2
    # 拼回去应该覆盖原内容（去标点干扰）
    joined = "".join(result)
    assert "今天过得怎么样" in joined
    assert "聊聊" in joined


def test_max_segments_respected():
    text = "一句话。两句话。三句话。四句话。五句话。六句话。"
    result = split_message(text, max_segments=3)
    assert len(result) <= 3


def test_single_long_no_punctuation():
    text = "这是一段没有任何标点符号的很长的话用来测试边界情况看看会不会出错"
    result = split_message(text)
    assert len(result) >= 1
    assert "".join(result).replace(" ", "") == text.replace(" ", "")


def test_newline_splits():
    text = "第一行\n第二行\n第三行"
    result = split_message(text)
    assert len(result) >= 1


def test_typing_delay_scales_with_length():
    short = typing_delay("嗯")
    long = typing_delay("这是一段比较长的消息内容用来测试打字延迟")
    assert long > short


def test_typing_delay_capped():
    huge = typing_delay("字" * 1000)
    assert huge <= 4.0


def test_think_delay_scales():
    short = think_delay("嗯")
    long = think_delay("我今天遇到了很多很多的事情想跟你慢慢说一下")
    assert long >= short


def test_think_delay_capped():
    huge = think_delay("字" * 1000)
    assert huge <= 3.0


def test_segments_are_nonempty():
    text = "好的。。。！！！"
    result = split_message(text)
    assert all(s.strip() for s in result)
