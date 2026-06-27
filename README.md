# MindMate · 小暖 🌿

一个**主动式心理医生伙伴** AI Agent。目标是做一个"伙伴"而非"工具"——
追求真实感，而不是完美。她会像微信里的朋友一样和你聊天：短消息、不秒回、
有自己的情绪和私密生活，会记住你们之间的"感觉"，也会在你沉默时有分寸地主动关心你。

> 灵感来自 nanobot 与 akashic-agent 的设计，用 Python 从零实现。

---

## ✨ 核心特性

| 能力 | 说明 |
|---|---|
| 🗣️ **真实对话质感** | 回复分多条短消息连发、模拟打字延迟（不秒回）、口语化、有语气词 |
| 🧠 **情绪锚点记忆** | 记住"感觉"而非流水账。聊过"下雨天的安心"，下次下雨她就会想起 |
| 💞 **关系演进** | 初识 → 朋友 → 信赖，随互动自然推进，影响亲密度和自我暴露 |
| 🛡️ **防御机制** | 有自己的"雷区"，被追问隐私/身份会回避、转移话题（像真人） |
| 📅 **主动陪伴** | 你沉默一阵后会主动找你，但有分寸：半夜不发、有冷却、每日上限 |
| 📔 **私密内在生活** | 每天自动写日记、做梦（默认不可见），只在交心时刻不经意吐露 |
| ⚠️ **风险检测** | 识别自伤/自杀意念等危机信号，认真陪伴并预警给医生 |
| 👥 **多用户支持** | 每个患者有独立的记忆/关系/情绪，互不干扰 |
| 🩺 **医生后台** | 情绪趋势图、风险预警、对话回放，可切换查看不同患者 |
| 🔧 **工具调用 + MCP** | 内置天气工具（感知真实天气，呼应情绪锚点），可接入任意 MCP server |

---

## 🚀 快速开始

### 1. 环境要求

- **Python 3.11 或更高**（推荐 3.12）
- 一个 **DeepSeek API Key**（[在这里申请](https://platform.deepseek.com/)，兼容 OpenAI 格式）

### 2. 进入项目目录

```bash
cd mindmate
```

### 3. 创建虚拟环境并安装依赖

**方式 A：用 venv + pip（通用）**

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows）
.venv\Scripts\activate
# 激活（macOS / Linux）
source .venv/bin/activate

# 安装项目（含开发依赖）
pip install -e ".[dev]"
```

**方式 B：用 uv（更快，可选）**

```bash
uv venv
uv pip install -e ".[dev]"
```

> 国内网络慢可加清华镜像：`pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 4. 配置 API Key

复制环境变量模板，填入你的 DeepSeek Key：

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

然后编辑 `.env`，把 `your-api-key-here` 换成你的真实 Key：

```ini
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

HOST=0.0.0.0
PORT=19876

# 每日内在生活（日记/梦自动生成）
INNER_LIFE_ENABLED=true
INNER_LIFE_HOUR=3
```

### 5. 启动

```bash
python -m mindmate.main
```

看到日志 `=== MindMate starting ===` 和 uvicorn 启动信息即成功。

### 6. 打开浏览器

| 页面 | 地址 | 用途 |
|---|---|---|
| 💬 聊天 | http://localhost:19876/ | 和小暖聊天（患者端） |
| 🩺 后台 | http://localhost:19876/dashboard | 医生管理后台 |

直接在聊天页输入消息即可开始。第一次访问会自动分配一个匿名用户 id；
也可以用 `?uid=xxx` 指定身份，比如 `http://localhost:19876/?uid=alice`。

---

## 🧪 运行测试

```bash
# 全部测试（107 个）
python -m pytest tests/ -q

# 代码风格检查
python -m ruff check mindmate/ tests/
```

---

## 📁 项目结构

```
mindmate/
├── mindmate/
│   ├── main.py              # 入口：启动 Web + 被动/主动循环 + 调度器
│   ├── agent/
│   │   ├── loop.py          # 核心 Agent 循环（对话/分段投递/记忆维护）
│   │   ├── energy.py        # 能量模型（主动开口的时机判断，per-user）
│   │   └── scheduler.py     # 每日调度器（日记/梦自动生成）
│   ├── personality/
│   │   ├── soul.py          # 人格核心（SOUL.md）
│   │   ├── defense.py       # 防御机制（雷区检测）
│   │   ├── relationship.py  # 关系演进
│   │   ├── emotion_anchor.py# 情绪锚点（提取 + 召回）
│   │   ├── memory_consolidator.py # 长期记忆整合
│   │   ├── forget.py        # 遗忘机制
│   │   ├── diary.py         # 日记子 Agent
│   │   └── dream.py         # 造梦子 Agent
│   ├── proactive/           # 被动循环 + 主动循环
│   ├── memory/store.py      # SQLite 持久化
│   ├── llm/deepseek.py      # LLM Provider
│   ├── bus/                 # 异步消息总线
│   ├── tools/crisis_detect.py # 风险检测
│   ├── web/                 # FastAPI + 前端（微信风）
│   └── config/settings.py   # 配置加载
├── memory/                  # 运行时数据（SQLite + SOUL.md + MEMORY.md）
├── tests/                   # 107 个测试
├── prompts/                 # 分阶段开发文档（step-0 ~ step-8）
├── pyproject.toml
└── .env.example
```

---

## ⚙️ 配置项说明

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | **必填**，DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `19876` | 端口 |
| `INNER_LIFE_ENABLED` | `true` | 是否启用每日日记/梦自动生成 |
| `INNER_LIFE_HOUR` | `3` | 每天几点生成（0-23，默认凌晨3点） |

---

## ❓ 常见问题

**Q：启动报 `DEEPSEEK_API_KEY` 为空 / 回复报错？**
A：检查 `.env` 是否在 `mindmate/` 目录下，且 Key 填写正确。

**Q：端口被占用？**
A：改 `.env` 里的 `PORT`，或关掉占用 19876 的进程。

**Q：聊天没反应 / 一直转圈？**
A：看启动终端的日志。多半是 API Key 无效、余额不足或网络不通；
先确认能访问 `https://api.deepseek.com`。

**Q：想换成别的模型（如 OpenAI）？**
A：`.env` 里把 `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` 改成兼容 OpenAI 格式的
任意服务即可（Provider 用的是 OpenAI SDK）。

**Q：数据存在哪？怎么清空？**
A：全部在 `memory/memory.db`（SQLite）。删掉该文件即重置所有对话/记忆。

---

## 🛠️ 技术栈

Python 3.11+ · asyncio · FastAPI · WebSocket · OpenAI SDK（DeepSeek 兼容）·
SQLite · 原生 HTML/CSS/JS 前端（微信风，零前端依赖）

---

## 📌 设计理念

> 工具需要完美，但"人"不需要。目标是做一个"伙伴"，追求真实感。

- **对话质感优先**——先让单纯聊天就像真人，再加功能
- **情绪锚点 > 事实标签**——记住感觉，而非流水账
- **记忆双层**——客观日志（不可改）+ 主观体验（可整合、可遗忘）
- **内部私密性**——日记/梦不被用户掌控，才是独立人格的基石
- **有分寸的主动**——像朋友偶尔冒泡，不像推销骚扰

详细的分阶段实现见 [`prompts/`](prompts/) 目录。
