
## Python 包与模块解析

### 项目的目录结构

```
d:\project\rag-service/     ← 项目根目录（运行时的工作目录）
├── app/                    ← Python 包（因为有 __init__.py）
│   ├── __init__.py         ← 告诉 Python 这是一个「包」
│   ├── db.py               ← app.db 模块
│   ├── main.py             ← app.main 模块
│   └── rag.py              ← app.rag 模块
```

### 为什么 `from app.db import add_document` 能找到 `app/db.py`？

回答分三步：

1. **`app/` 是一个包** — 因为 `app/` 目录下有一个 `__init__.py` 文件（即使是空的），Python 就把 `app/` 识别为一个**包（package）**。

2. **Python 的模块搜索路径** — 当你从项目根目录 `d:/project/rag-service` 启动应用时（比如 `python -m app.main` 或 `uv run uvicorn app.main:app`），Python **会自动把当前工作目录（项目根目录）加入到 `sys.path`（模块搜索路径）** 中。

3. **`app.db` 的解析过程**：
   - Python 在 `sys.path` 中找到项目根目录
   - 在根目录下找到 `app/`（包）
   - 在 `app/` 下找到 `db.py`（模块）
   - 因此 `app.db` 就指向了 `app/db.py` 这个文件

```
from app.db import add_document, ensure_storage
         ↑    ↑
        包   模块
```

所以 `app.db` 就是 `app/db.py`，`app.main` 就是 `app/main.py`，`app.rag` 就是 `app/rag.py`。

### 4 种常见的运行方式对比

| 运行方式 | 能否正常 import | 原因 |
|----------|:---:|------|
| `python app/main.py` | ❌ 会报错 `ModuleNotFoundError` | Python 把 `app/main.py` 当作独立脚本运行，`app/` 不被视为包 |
| `python -m app.main` | ✅ | `-m` 告诉 Python 以包的方式运行，包结构生效 |
| `uvicorn app.main:app` | ✅ | Uvicorn 内部使用 `-m` 方式导入 |
| `uv run uvicorn app.main:app` | ✅ | uv 也会正确处理包导入 |

### 一句话总结

`app.db` ＝ **`app/` 包下的 `db.py` 模块**，能这样写的前提是：
1. `app/` 目录有 `__init__.py` 文件
2. 从项目根目录**以包的形式**启动应用（`python -m` 或 `uvicorn`）