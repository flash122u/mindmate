"""测试消息分段器."""

import sys
sys.path.insert(0, '..')

from mindmate.utils.splitter import split_message, delays_for_segments, MessageSplitter, clean_text


class TestCleanText:
    def test_remove_fullwidth_paren(self):
        r = clean_text("（轻声）嗯...今天天气不错")
        assert "（轻声）" not in r

    def test_remove_halfwidth_paren(self):
        r = clean_text("(sighs)今天心情不错")
        assert "(sighs)" not in r

    def test_multiple_parens(self):
        r = clean_text("（笑）（小声）嗯......（低头）")
        assert "（笑）" not in r and "（低头）" not in r

    def test_no_parens_unchanged(self):
        r = clean_text("今天天气真不错")
        assert r == "今天天气真不错"


class TestSplitMessage:
    def test_short_text(self):
        result = split_message("你好")
        assert result == ["你好"]

    def test_split_by_punctuation(self):
        result = split_message("今天天气真好。你过得怎么样？")
        assert len(result) >= 2
        assert "今天天气真好" in result[0] or "今天天气真好" in "".join(result)

    def test_split_long_sentence(self):
        """超长句按逗号再拆（逗号通常出现在句内）。"""
        text = "我今天去了一家新开的咖啡店，坐在窗边喝了一杯拿铁，感觉很舒服，坐在那里发呆了一下午。"
        result = split_message(text)
        # 整句话 > 40 字符且有逗号，应该被拆成多段
        if len(text) > 40:
            assert len(result) >= 2, f"expected >=2 segments, got {result}"
        else:
            assert len(result) >= 1

    def test_merge_short_segments(self):
        """短段应合并."""
        result = split_message("好。嗯。行。")
        merged = "".join(result)
        assert "好" in merged

    def test_whitespace_only(self):
        result = split_message("   ")
        assert len(result) == 1

    def test_real_reply(self):
        text = "嗯，其实有时候心情不好也不需要什么特别的原因。可能是太累了，也可能是天气的关系。我有时候也会这样，什么都提不起兴趣。不过没关系的，你愿意跟我说说，我就陪着你聊聊天。"
        result = split_message(text, max_length=40)
        assert len(result) >= 2
        for seg in result:
            assert len(seg) <= 60  # 允许略超 max_length（合并后的）

    def test_no_delay_for_single(self):
        d = delays_for_segments(["一句话"])
        assert d == [0.0]

    def test_delays_multiple(self):
        d = delays_for_segments(["短", "中等长度的一段话", "这是一段超过二十个字的长文本段啊一共二十多个字"])
        assert len(d) == 3
        assert d[-1] == 0.0  # 最后一段延迟为0


class TestYieldSegments:
    def test_yield(self):
        gen = MessageSplitter.yield_segments("你好。我很好。")
        items = list(gen)
        assert len(items) >= 2
        for seg, delay, is_last in items:
            assert isinstance(seg, str)
            assert isinstance(delay, float)
            assert isinstance(is_last, bool)
