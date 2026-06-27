# Step 5：记忆深化 ✅

## 目标

让小暖记住"感觉"而非流水账，记忆像人一样会沉淀、会褪色。

实现最初想法里的核心：
> 情绪锚点 = {event: 那次晚餐, emotion: 安全感, trigger: 下雨天}
> 未来遇到下雨天，ta 就会产生想依赖用户的冲动。

## 已实现

### 情绪锚点（personality/emotion_anchor.py）
- `extract()`：对话后用 LLM 提取 `{event, emotion, trigger, valence}`
  - 只在有明显情绪波动时提取，平淡闲聊返回空
- `recall()`：当前消息命中某个 trigger → 召回相关锚点
- `build_anchor_prompt()`：把召回的锚点注入 system prompt，影响语气

### 记忆整合（personality/memory_consolidator.py）
- 历史超阈值（默认 40 轮）时，把窗口外旧对话总结进 MEMORY.md
- MEMORY.md 作为"长期主观记忆"注入 system prompt
- 让小暖记得住超出上下文窗口的"很久以前的事"

### 遗忘（personality/forget.py）
- 陈旧 + 微弱的情绪锚点会被遗忘
- 强烈情绪（|valence| 大）保留更久——刻骨铭心忘得慢
- **只作用于主观层（情绪锚点），绝不碰客观日志（history）**

## 记忆双层架构

| 层 | 存储 | 可变性 |
|---|---|---|
| 客观日志层 | SQLite `history` 表 | 不可篡改 |
| 主观体验层 | 情绪锚点 + MEMORY.md | 可整合、可遗忘、可褪色 |

## 实测闭环

```
"上次下雨天你陪我聊到很晚，特别安心"
  → 锚点：{下雨天深夜陪伴 | 安心 | trigger=下雨天 | 0.9}
"今天又下雨了"
  → 召回 → 小暖主动关心"你还好吗？要不要聊聊？"
```

## 集成点

- `_build_context` 注入长期记忆 + 召回的情绪锚点
- 对话后 `_post_turn_memory` 后台执行提取/整合/遗忘（不阻塞回复）
- `memory_maintenance` 开关便于测试
