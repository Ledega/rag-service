from __future__ import annotations

from app.config import settings


def get_embedding_model():
    """获取 Embedding 模型实例（单例懒加载）。"""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL_NAME,
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_API_BASE,
    )