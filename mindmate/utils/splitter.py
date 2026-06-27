"""消息分段 + 打字延迟 — 让回复像微信连发，而非一整段.

核心理念：真人聊天是短句连发的，不是一次发一大段。
把 LLM 的回复智能拆成 2-3 条短消息，每条之间有自然的打字停顿。
"""

from __future__ import annotations

import re

# 句子结束标点（中英文）
_SENTENCE_END = "。！？!?…\n"
# 用于切分的标点（保留语气，不切逗号以免太碎）
_SPLIT_PATTERN = re.compile(r"([。！？!?…\n]+)")

# 极短碎片合并阈值：仅"嗯""好"这种单字碎片才并入下一句
_TINY_FRAGMENT_CHARS = 2
# 最多分成几条
_MAX_SEGMENTS = 3


def split_message(text: str, max_segments: int = _MAX_SEGMENTS) -> list[str]:
    """把一段回复拆成多条短消息.

    策略：
    1. 按句末标点切成句子
    2. 把相邻短句合并，使每条接近但不超过目标长度
    3. 最多 max_segments 条，超出的并入最后一条

    Args:
        text: LLM 原始回复
        max_segments: 最多拆成几条

    Returns:
        消息段列表（至少 1 条）
    """
    text = text.strip()
    if not text:
        return []

    # 1. 按句末标点切分，保留标点
    parts = _SPLIT_PATTERN.split(text)
    sentences: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if _SPLIT_PATTERN.fullmatch(part):
            # 这是标点，拼回上一句
            buf += part
            sentences.append(buf.strip())
            buf = ""
        else:
            buf += part
    if buf.strip():
        sentences.append(buf.strip())

    sentences = [s for s in sentences if s]
    if not sentences:
        return [text]

    # 2. 一句一气泡（像微信连发）；只把"极短碎片"并入下一句，避免出现单字气泡
    segments: list[str] = []
    pending = ""
    last_idx = len(sentences) - 1
    for i, sentence in enumerate(sentences):
        merged = pending + sentence
        pending = ""
        bare = merged.strip("。！？!?…\n ")
        if len(bare) <= _TINY_FRAGMENT_CHARS and i != last_idx:
            # 极短碎片，暂存并入下一句
            pending = merged
            continue
        segments.append(merged)
    if pending:
        if segments:
            segments[-1] += pending
        else:
            segments.append(pending)

    if not segments:
        segments = sentences

    # 3. 限制最多 max_segments 条，多余的并入最后一条
    if len(segments) > max_segments:
        head = segments[: max_segments - 1]
        tail = "".join(segments[max_segments - 1:])
        segments = head + [tail]

    return segments


def typing_delay(text: str, base: float = 0.4, per_char: float = 0.06,
                 max_delay: float = 4.0) -> float:
    """根据消息长度估算"打字耗时"（秒）.

    模拟真人打字速度：基础延迟 + 每字耗时，封顶 max_delay。

    Args:
        text: 消息内容
        base: 基础延迟（拿起手机、思考）
        per_char: 每个字的打字耗时
        max_delay: 单条最大延迟，避免长消息等太久

    Returns:
        延迟秒数
    """
    delay = base + len(text) * per_char
    return min(delay, max_delay)


def think_delay(text: str, base: float = 1.0, per_char: float = 0.03,
                max_delay: float = 3.0) -> float:
    """收到消息后、开始回复前的"思考延迟"（秒）.

    用户消息越长，思考越久（但有上限）。

    Args:
        text: 用户消息内容
        base: 基础思考时间
        per_char: 每字增加的思考时间
        max_delay: 思考延迟上限

    Returns:
        延迟秒数
    """
    delay = base + len(text) * per_char
    return min(delay, max_delay)
