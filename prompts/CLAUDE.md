# MindMate — 主动式心理医生伙伴

## 项目概览

一个基于 Python 的主动式 AI 心理医生伙伴，融合 nanobot 和 akashic-agent 的设计精华。

## 技术栈

- Python 3.11+ (asyncio)
- FastAPI + WebSocket (后端)
- DeepSeek API (兼容 OpenAI SDK)
- ChromaDB (向量存储)
- MCP 协议 (工具扩展)
- 原生 HTML/CSS/JS 前端 (Vanilla)

## 目录结构

```
mindmate/
├── mindmate/
│   ├── agent/         # 核心 Agent 循环
│   ├── proactive/     # 主动行为系统
│   ├── personality/   # 人格系统
│   ├── memory/        # 记忆系统
│   ├── bus/           # 消息总线
│   ├── channels/      # 通信通道
│   ├── llm/           # LLM 集成
│   ├── tools/         # 工具注册
│   ├── web/           # Web 界面
│   └── config/        # 配置
├── tests/
├── memory/           # 运行时记忆文件
└── prompts/          # 开发指引
```

## 开发命令

```bash
# 运行
python -m mindmate.main

# 测试
python -m pytest tests/ -v

# 格式检查
ruff check mindmate/
```

## 关键设计原则

1. **双循环架构** — 被动响应 + 主动触发
2. **子 Agent 人格系统** — 日记、造梦、遗忘、防御机制
3. **情绪锚点 > 事实标签** — 记忆以情绪效价为主导
4. **三层记忆** — 客观日志 / 主观体验 / 情绪锚点
