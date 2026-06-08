# rag-service

最小可运行的 RAG 学习骨架：FastAPI + SQLite + 轻量检索 + 单页前端。

## 环境管理（uv）

本项目使用 uv 管理 Python 版本、虚拟环境和依赖。

```powershell
uv python pin 3.13
uv sync
```

- Python 版本固定在 `.python-version`
- 依赖锁定在 `uv.lock`

## 启动

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

常用命令：

```powershell
uv run python
uv add <package>
uv remove <package>
uv lock
```

打开 `http://127.0.0.1:8000` 后，你可以直接使用示例文档提问，也可以上传 `.txt` / `.md` 文本文件或者直接粘贴文本导入。

## 现在包含什么

- 一个 FastAPI 服务，提供 `/health`、`/api/documents` 和 `/api/ask`
- 一个 SQLite 知识库，启动时会自动写入两份示例文档
- 一个前后端一体的页面，用于导入文档和提问
- 一个可替换的检索层，当前用 `TfidfVectorizer` 做最小版检索

## 下一步可以怎么扩展

- 把当前检索层替换成 embedding + 向量库
- 加入 PDF / DOCX 解析
- 把回答生成接到你想用的大模型 API 或本地模型
- 增加对话历史、重排和引用高亮