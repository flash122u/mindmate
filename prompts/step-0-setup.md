# Step 0：环境准备

## 0.1 创建项目根目录

```bash
cd "D:\Files\BaiduNetdiskDownload\agent\主动agent\mindmate"
```

## 0.2 初始化 Python 虚拟环境

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# 或使用 uv
uv venv
```

## 0.3 安装依赖

```bash
pip install fastapi uvicorn websockets openai pydantic httpx loguru python-dotenv pyyaml
# 或
uv add fastapi uvicorn websockets openai pydantic httpx loguru python-dotenv pyyaml
```

## 0.4 创建 .env 文件

```bash
# 复制 .env.example 到 .env 并填入 DeepSeek API Key
cp .env.example .env
```

## 0.5 验证

```bash
python -c "import fastapi, uvicorn, openai, pydantic, chromadb; print('OK')"
```
