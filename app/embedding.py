from __future__ import annotations

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_openai_client():
    """
    获取 OpenAI 兼容客户端实例（单例懒加载）。
    DashScope 通义千问兼容 OpenAI 接口，直接使用 openai 客户端。
    """
    from openai import OpenAI

    return OpenAI(
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_API_BASE,
    )


def get_embedding_model():
    """
    获取 Embedding 模型实例。
    直接使用 openai 客户端调用 DashScope 的 Embedding API。
    """
    return _OpenAIEmbeddingWrapper()


def get_llm_model():
    """
    获取 LLM 模型实例（单例懒加载）。
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
    )


class _OpenAIEmbeddingWrapper:
    """
    OpenAI Embedding 封装，直接调用 openai 客户端。
    保持与 LangChain Embeddings 相同的接口（embed_documents / embed_query）。
    避免 langchain_openai 的 request 格式与 DashScope 不兼容的问题。
    """

    def __init__(self) -> None:
        self.client = get_openai_client()
        self.model = settings.EMBEDDING_MODEL_NAME

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """将文档列表转为向量。"""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        # openai 返回结果按输入顺序排列
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        """将单个查询文本转为向量。"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding