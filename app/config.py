from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """应用配置，统一从环境变量 / .env 文件读取。"""

    # ── Embedding ──
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "text-embedding-3-small"
    )
    EMBEDDING_API_BASE: str = os.getenv(
        "EMBEDDING_API_BASE", "https://api.openai.com/v1"
    )

    # ── LLM ──
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    # ── Chroma 持久化路径 ──
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "chroma")

    # ── PDF 目录 ──
    PDF_DIR: str = str(BASE_DIR / "data" / "pdfs")

    # ── SQLite 数据库路径 ──
    DB_PATH: str = str(BASE_DIR / "data" / "rag.db")


settings = Settings()