from __future__ import annotations

from pathlib import Path

from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.embedding import get_embedding_model

# 检索时默认返回的 top-k 结果数
DEFAULT_TOP_K = 4

# 自定义 embedding 函数，将 LangChain Embedding 包装为 Chroma 兼容格式
class _LangChainEmbeddingFunction:
    """将 LangChain 的 Embedding 模型包装为 Chroma 可用的 EmbeddingFunction。"""

    def __init__(self) -> None:
        self._model = get_embedding_model()

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._model.embed_documents(input)


def _get_collection():
    """
    获取 Chroma 集合实例（单例懒加载）。
    集合保存在 data/chroma/ 目录中，服务重启后自动恢复。
    """
    import chromadb

    persist_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    collection = client.get_or_create_collection(
        name="rag_chunks",
        embedding_function=_LangChainEmbeddingFunction(),
    )
    return collection


def add_chunks(
    document_id: int,
    document_name: str,
    chunks: list[str],
    chunk_start_index: int = 0,
) -> int:
    """
    将文档的文本块写入 Chroma 向量库。

    :param document_id: 数据库中的文档 ID
    :param document_name: 文档名称
    :param chunks: 文本块列表
    :param chunk_start_index: 起始 chunk 序号（用于增量追加）
    :return: 写入的 chunk 数量
    """
    if not chunks:
        return 0

    collection = _get_collection()

    ids: list[str] = []
    metadatas: list[dict] = []
    documents: list[str] = []

    for i, chunk in enumerate(chunks):
        chunk_index = chunk_start_index + i
        chunk_id = f"doc_{document_id}_chunk_{chunk_index}"
        ids.append(chunk_id)
        metadatas.append(
            {
                "document_id": document_id,
                "document_name": document_name,
                "chunk_index": chunk_index,
            }
        )
        documents.append(chunk)

    collection.add(
        ids=ids,
        metadatas=metadatas,
        documents=documents,
    )
    return len(chunks)


def delete_document_chunks(document_id: int) -> None:
    """删除指定文档的所有向量块。"""
    collection = _get_collection()
    collection.delete(where={"document_id": document_id})


def retrieve_chunks(
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    语义检索：根据问题从 Chroma 中检索最相关的文本块。

    :param question: 用户问题
    :param top_k: 返回结果数量
    :return: 检索结果列表，每项包含 source / score / content
    """
    collection = _get_collection()

    # 检查集合是否为空
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=min(top_k, collection.count()),
    )

    citations: list[dict] = []
    if not results["ids"] or not results["ids"][0]:
        return citations

    metadatas = results["metadatas"][0]
    documents = results["documents"][0]
    distances = results["distances"][0]

    for meta, doc, dist in zip(metadatas, documents, distances):
        # Chroma 返回的是 L2 距离，越小越相似 → 转换为 0~1 相似度分数
        score = round(1.0 / (1.0 + dist), 3)
        citations.append(
            {
                "source": f"{meta['document_name']} / chunk {meta['chunk_index'] + 1}",
                "score": score,
                "content": doc,
            }
        )

    return citations