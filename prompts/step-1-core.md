# Step 1：核心骨架搭建

## 目标

打通"发送消息 → Agent 处理 → 返回回复"的最小闭环。

## 已完成的基础文件

以下文件已创建，需要验证和补充：

| 文件 | 状态 | 说明 |
|------|------|------|
| `pyproject.toml` | ✅ | 项目配置 + 依赖 |
| `.env.example` | ✅ | 环境变量模板 |
| `CLAUDE.md` | ✅ | 项目记忆 |
| `prompts/README.md` | ✅ | 步骤索引 |
| `prompts/step-0-setup.md` | ✅ | 环境准备指引 |
| `mindmate/__init__.py` | ✅ | 包入口 |
| `mindmate/config/settings.py` | ✅ | 配置加载 |
| `mindmate/bus/events.py` | ✅ | 消息总线 |
| `mindmate/llm/deepseek.py` | ✅ | DeepSeek Provider |
| `mindmate/memory/store.py` | ✅ | 记忆持久化 |
| `mindmate/agent/loop.py` | ✅ | Agent 主循环 |
| `mindmate/personality/soul.py` | ✅ | 人格核心 |
| `mindmate/proactive/energy.py` | ✅ | 能量模型 |
| `mindmate/proactive/passive.py` | ✅ | 被动循环 |
| `mindmate/proactive/loop.py` | ✅ | 主动循环 |
| `mindmate/channels/web.py` | ✅ | WebSocket 通道 |
| `mindmate/web/app.py` | ✅ | FastAPI 应用 |
| `mindmate/main.py` | ✅ | 入口 |
| `mindmate/web/static/index.html` | ✅ | 聊天页面 |
| `mindmate/web/static/dashboard.html` | ✅ | 管理后台 |
| `tests/test_basic.py` | ✅ | 基础测试 |
| `tests/test_agent.py` | ✅ | Agent 测试 |
| `tests/test_energy.py` | ✅ | 能量模型测试 |

## 下一步需要做的事

### 1. 安装依赖并验证导入

```bash
cd D:\Files\BaiduNetdiskDownload\agent\主动agent\mindmate
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -c "from mindmate import __version__; print(__version__)"
```

### 2. 补充缺失的空 `__init__.py`

确认所有 `mindmate/` 子目录下都有 `__init__.py`：
- `mindmate/config/__init__.py`
- `mindmate/agent/__init__.py`
- `mindmate/proactive/__init__.py`
- `mindmate/personality/__init__.py`
- `mindmate/memory/__init__.py`
- `mindmate/channels/__init__.py`
- `mindmate/bus/__init__.py`
- `mindmate/llm/__init__.py`
- `mindmate/tools/__init__.py`（空文件即可）
- `mindmate/web/__init__.py`

### 3. 修复 main.py 中的循环导入问题

当前 `main.py` 使用了 `from mindmate.bus.events import MessageBus` 但 `settings` 对象引用了 `settings.bus` 而 `bus` 并未挂载到 `settings`。需要重构：

**方案 A**：在 `settings.py` 中添加 `bus` 属性
**方案 B**：在 `main.py` 中直接创建 `bus = MessageBus()` 并传递给各组件

推荐 **方案 B**，更清晰。

### 4. 运行测试

```bash
cd D:\Files\BaiduNetdiskDownload\agent\主动agent\mindmate
python -m pytest tests/ -v
```

预期：4 个测试全部通过。

### 5. 启动验证

```bash
python -m mindmate.main
```

预期：
- 日志输出 `=== MindMate starting ===`
- FastAPI 在 `:19876` 启动
- 浏览器访问 `http://localhost:19876/chat` 看到聊天界面
- 发送消息后能看到"等待小暖回复..."（因为还没有后端对接）
