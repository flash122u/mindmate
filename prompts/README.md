# MindMate 开发步骤

主动式心理医生伙伴。核心目标是**真实感**——做一个"伙伴"而非"工具"。

## 开发顺序（已按"对话质感优先"重排）

| 文件 | 用途 | 状态 |
|---|---|---|
| `step-0-setup.md` | 环境准备：创建项目、安装依赖 | ✅ |
| `step-1-core.md` | 核心骨架：消息总线 + Agent 循环 + DeepSeek + SQLite + Web | ✅ 含地基修正 |
| `step-2-personality.md` | 人格系统：防御机制 + 关系演进 | ✅ |
| `step-3-dialogue.md` | **对话质感**：短消息分段 + 不秒回 + 人格锚定 | ✅ 实测通过 |
| `step-4-proactive.md` | 主动行为：能量模型 + LLM 生成主动消息 | ✅ |
| `step-5-memory.md` | 记忆深化：情绪锚点 + 记忆整合 + 遗忘 | ✅ |
| `step-6-subagents.md` | 子 Agent（日记/造梦）+ 医生管理后台 | ✅ |
| `step-7-scheduler.md` | 定时任务：每日日记/梦自动生成 | ⬜ |
| `step-8-multiuser.md` | 多用户支持：per-user 记忆/关系/能量隔离 | ⬜ |

## 关键设计原则（来自最初想法）

1. **不是工具，是伙伴** — 不追求完美，追求真实感
2. **对话质感优先** — 先让单纯聊天就像真人，再加功能
3. **情绪锚点 > 事实标签** — 记住"感觉"而非流水账
4. **记忆双层** — 客观日志（不可改）+ 主观体验（可整合/遗忘）
5. **内部私密性** — 日记/梦默认不可见，只在强情绪共鸣时吐露
6. **有分寸的主动** — 半夜不发、刚聊完不发、有冷却和每日上限

## 当前架构

```
mindmate/
├── agent/          loop.py（主循环+分段投递+记忆维护）, energy.py（能量模型）
├── personality/
│   ├── soul.py              人格核心（SOUL.md）
│   ├── defense.py           防御机制（雷区检测）
│   ├── relationship.py      关系演进（初识→朋友→信赖）
│   ├── emotion_anchor.py    情绪锚点（提取+召回）
│   ├── memory_consolidator.py  长期记忆整合
│   └── forget.py            遗忘机制
├── proactive/      loop.py（主动循环）, passive.py（被动循环）
├── memory/         store.py（SQLite：history/emotion_anchors/relationship）
├── llm/            deepseek.py
├── bus/            events.py（消息总线）
├── channels/       （预留）
├── utils/          splitter.py（短消息分段+延迟）
└── web/            app.py + static/（聊天界面 + 后台）
```

## 测试

```bash
python -m pytest tests/ -q     # 74 测试全过
python -m ruff check mindmate/ tests/
```
