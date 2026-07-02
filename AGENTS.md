# AGENTS.md

## 项目概述
MindMate 是一个主动式 AI 心理陪伴 Agent——模拟真人好友的对话质感、情绪记忆与有分寸的主动关心。基于 asyncio + FastAPI + WebSocket 全双工通信，搭载 DeepSeek LLM + SQLite 记忆持久化 + MCP 工具扩展，配套咨询师六维可视化后台。

## 开发命令
- 安装依赖：`pip install -e ".[dev]"`
- 本地启动：`python -m mindmate.main`
- 运行测试：`pytest tests/ -q`
- 代码检查：`ruff check mindmate/ tests/`
- 自动修复：`ruff check --fix mindmate/ tests/`

## 关键目录
- `mindmate/agent/` — 核心引擎：AgentLoop（被动响应）、IntentRouter（意图路由）、TraceBuilder（可观测性）、能量模型
- `mindmate/bus/` — MessageBus 异步消息总线（asyncio.Queue）
- `mindmate/memory/` — MemoryStore SQLite 持久化（8 张表：history、emotion_anchors、relationship、diary、dreams、crisis_alerts、agent_traces）
- `mindmate/personality/` — 人格系统：防御、关系、情绪锚点、记忆压缩、日记/梦境子 Agent、遗忘
- `mindmate/proactive/` — 主动行为：ProactiveLoop（能量模型驱动定时问候）
- `mindmate/tools/` — 工具调用：天气、危机检测、MCP 客户端
- `mindmate/web/` — FastAPI 应用 + WebSocket 端点 + Dashboard 静态页面
- `mindmate/llm/` — DeepSeekProvider (OpenAI SDK 兼容)
- `tests/` — 147 个测试（pytest + pytest-asyncio）

## 边界约束
- **Python >= 3.11**，使用 `from __future__ import annotations`
- **ruff 规范**：line-length=100，select E/F/I/N/W，提交前必须 `ruff check` 通过
- **测试策略**：TDD 优先，新功能至少 6 个测试；mock LLM provider 避免真实 API 调用
- **向后兼容**：新增 `AgentLoop` 方法参数必须默认为 `None`，内部用 `if param:` 守卫
- **禁止**：直接改 `memory/store.py` 的 `_init_db` 已有表结构（只追加新表）
- **禁止**：在测试中硬编码固定 ID 写入共享 SQLite（用 `_uniq()` 时间戳隔离）
- **SOUL.md 和 MEMORY.md** 仍用文件存储（便于人工编辑和版本控制），不进 SQLite

## AI 上下文
详细规则见 `.ai/rules/ai-readme/RULE.md`：
- 架构：`.ai/rules/ai-readme/generated/技术架构.md`
- 流程：`.ai/rules/ai-readme/generated/核心流程.md`
- 业务（人工维护）：`.ai/rules/ai-readme/manual/业务知识.md`
- 踩坑（人工维护）：`.ai/rules/ai-readme/manual/历史经验.md`
