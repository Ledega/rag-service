from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.embedding import get_embedding_model

# 检索时默认返回的 top-k 结果数
DEFAULT_TOP_K = 4

# 向量存储文件路径
_VECTOR_STORE_PATH = Path(settings.CHROMA_PERSIST_DIR) / "vectors.pkl"


def _load_store() -> dict:
    """从磁盘加载向量存储。"""
    if _VECTOR_STORE_PATH.exists():
        with open(_VECTOR_STORE_PATH, "rb") as f:
            return pickle.load(f)
    return {"ids": [], "embeddings": [], "metadatas": [], "documents": []}


def _save_store(store: dict) -> None:
    """将向量存储保存到磁盘。"""
    _VECTOR_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_VECTOR_STORE_PATH, "wb") as f:
        pickle.dump(store, f)


def add_chunks(
    document_id: int,
    document_name: str,
    chunks: list[str],
    chunk_start_index: int = 0,
) -> int:
    """
    将文档的文本块向量化后存入本地向量存储。

    :param document_id: 数据库中的文档 ID
    :param document_name: 文档名称
    :param chunks: 文本块列表
    :param chunk_start_index: 起始 chunk 序号
    :return: 写入的 chunk 数量
    """
    if not chunks:
        return 0

    store = _load_store()
    model = get_embedding_model()

    for i, chunk in enumerate(chunks):
        chunk_index = chunk_start_index + i
        chunk_id = f"doc_{document_id}_chunk_{chunk_index}"

        # 生成向量
        vector = model.embed_documents([chunk])[0]

        store["ids"].append(chunk_id)
        store["embeddings"].append(vector)
        store["metadatas"].append(
            {
                "document_id": document_id,
                "document_name": document_name,
                "chunk_index": chunk_index,
            }
        )
        store["documents"].append(chunk)

    _save_store(store)
    return len(chunks)


def delete_document_chunks(document_id: int) -> None:
    """删除指定文档的所有向量块。"""
    store = _load_store()
    indices_to_keep = [
        i
        for i, meta in enumerate(store["metadatas"])
        if meta["document_id"] != document_id
    ]

    if len(indices_to_keep) == len(store["ids"]):
        return  # 无变化

    store["ids"] = [store["ids"][i] for i in indices_to_keep]
    store["embeddings"] = [store["embeddings"][i] for i in indices_to_keep]
    store["metadatas"] = [store["metadatas"][i] for i in indices_to_keep]
    store["documents"] = [store["documents"][i] for i in indices_to_keep]
    _save_store(store)


def retrieve_chunks(
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    语义检索：将问题转为向量，从本地向量存储中检索最相关的文本块。

    :param question: 用户问题
    :param top_k: 返回结果数量
    :return: 检索结果列表，每项包含 source / score / content
    """
    store = _load_store()
    if not store["embeddings"]:
        return []

    model = get_embedding_model()
    question_vector = model.embed_documents([question])[0]

    # 计算余弦相似度
    vectors = np.array(store["embeddings"])
    q_vec = np.array(question_vector).reshape(1, -1)
    scores = cosine_similarity(q_vec, vectors).flatten()

    # 取 top-k
    top_indices = scores.argsort()[::-1][:top_k]

    citations: list[dict] = []
    for idx in top_indices:
        meta = store["metadatas"][idx]
        citations.append(
            {
                "source": f"{meta['document_name']} / chunk {meta['chunk_index'] + 1}",
                "score": round(float(scores[idx]), 3),
                "content": store["documents"][idx],
            }
        )

    return citations