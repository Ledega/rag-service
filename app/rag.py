from __future__ import annotations

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter


def normalize_text(text: str) -> str:
    """统一换行符、压缩连续空白。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """将长文本切分为多个块，使用 RecursiveCharacterTextSplitter。"""
    normalized = normalize_text(text)
    if not normalized:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    chunks = text_splitter.split_text(normalized)
    return chunks


def retrieve_chunks(
    question: str,
    top_k: int = 4,
) -> list[dict]:
    """
    语义检索：将问题转为向量，从 Chroma 中检索最相关的文本块。

    :param question: 用户问题
    :param top_k: 返回结果数量
    :return: 检索结果列表，每项含 source / score / content
    """
    from app.vector_store import retrieve_chunks as _retrieve

    return _retrieve(question, top_k=top_k)


def build_answer(
    question: str,
    retrieved_chunks: list[dict],
) -> dict[str, object]:
    """
    基于问题和检索结果生成最终回答。
    如果检索结果为空则返回兜底信息，否则调用 LLM 生成真实回答。

    :param question: 用户问题
    :param retrieved_chunks: 检索结果列表
    :return: 包含 answer 和 citations 的字典
    """
    if not retrieved_chunks:
        return {
            "answer": "当前知识库里还没有足够内容。先上传一份文档，再来提问。",
            "citations": [],
        }

    # 取 top-3 作为 LLM 上下文（与前端展示一致）
    top_chunks = retrieved_chunks[:3]

    from app.llm import generate_answer

    answer_text = generate_answer(question, top_chunks)

    return {
        "answer": answer_text,
        "citations": top_chunks,
    }