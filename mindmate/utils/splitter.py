"""消息分段工具 — 将长文本拆成短段，模拟人聊天分开发送."""

from __future__ import annotations

import random
import re
from typing import Any


def split_message(text: str, max_length: int = 40) -> list[str]:
    """
    将一段话按句子拆成短段，模拟人聊天分开发送。

    策略：
    1. 先按句号/问号/感叹号拆分出完整句子
    2. 每个句子如果超过 max_length，再按逗号/分号拆分
    3. 拆分后合并相邻的过短段（< 8 字），避免碎片化
    4. 太短 (< 2) 的文本直接返回
    """
    if not text or len(text.strip()) <= 2:
        return [text.strip()]

    # 第一步：按句末标点拆分为完整句子
    raw_sentences = re.split(r'(?<=[。！？!?…\n])', text)
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]

    # 第二步：每个句子如果超长，按逗号拆
    segments: list[str] = []
    for s in raw_sentences:
        if len(s) <= max_length:
            segments.append(s)
        else:
            # 按逗号拆
            parts = re.split(r'(?<=[，；、,;])', s)
            parts = [p.strip() for p in parts if p.strip()]
            for p in parts:
                if len(p) <= max_length:
                    segments.append(p)
                else:
                    # 还是超长，暴力截断
                    while len(p) > max_length:
                        segments.append(p[:max_length])
                        p = p[max_length:]
                    if p:
                        segments.append(p)

    # 如果只有一段，直接返回
    if len(segments) <= 1:
        return [text.strip()]

    # 第三步：合并过短段（< 8 字），避免碎片化
    # 但不要合并以句末标点结尾和开头的段
    merged: list[str] = []
    for seg in segments:
        seg_ends = seg[-1] if seg else ""
        prev_ends = merged[-1][-1] if merged else ""

        should_merge = (
            merged
            and len(seg) < 8
            and seg_ends not in "。！？.!?"  # seg不以句号结尾
            and prev_ends not in "。！？.!?"  # 前一段没结束句子
        )
        if should_merge:
            merged[-1] += seg
        else:
            merged.append(seg)

    return merged


def delays_for_segments(segments: list[str]) -> list[float]:
    """
    为每段生成发送延迟（秒）。

    规则：
    - 短段（< 10 字）：0.8 ~ 1.5s
    - 中段（10-20 字）：1.5 ~ 2.5s
    - 长段（> 20 字）：2.0 ~ 3.5s
    - 最后一段：0（立即完成）
    """
    n = len(segments)
    if n <= 1:
        return [0.0]

    delays = []
    for i, seg in enumerate(segments):
        if i == n - 1:
            delays.append(0.0)
        else:
            length = len(seg)
            if length < 10:
                delays.append(round(random.uniform(0.8, 1.5), 1))
            elif length < 20:
                delays.append(round(random.uniform(1.5, 2.5), 1))
            else:
                delays.append(round(random.uniform(2.0, 3.5), 1))

    return delays


class MessageSplitter:
    """
    消息分段器 — 将 LLM 回复分段推送，模拟打字效果。

    使用方式：
        splitter = MessageSplitter()
        for segment in splitter.yield_segments(reply_text):
            yield segment
    """

    @staticmethod
    def yield_segments(text: str):
        """生成器，依次产出 (segment_text, delay_seconds, is_last)。"""
        segments = split_message(text)
        delays = delays_for_segments(segments)

        for i, (seg, delay) in enumerate(zip(segments, delays)):
            is_last = i == len(segments) - 1
            yield seg, delay, is_last
