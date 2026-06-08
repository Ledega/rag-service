from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(slots=True)
class RetrievedChunk:
    document_name: str
    chunk_index: int
    content: str
    score: float


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def retrieve_chunks(question: str, chunks: Iterable[dict[str, object]], top_k: int = 4) -> list[RetrievedChunk]:
    chunk_rows = list(chunks)
    if not chunk_rows:
        return []

    corpus = [str(row["content"]) for row in chunk_rows]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(corpus + [question])
    similarity_scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()

    ranked_indices = similarity_scores.argsort()[::-1][:top_k]
    results: list[RetrievedChunk] = []
    for index in ranked_indices:
        row = chunk_rows[index]
        results.append(
            RetrievedChunk(
                document_name=str(row["document_name"]),
                chunk_index=int(row["chunk_index"]),
                content=str(row["content"]),
                score=float(similarity_scores[index]),
            )
        )
    return results


def build_answer(question: str, retrieved_chunks: list[RetrievedChunk]) -> dict[str, object]:
    if not retrieved_chunks:
        return {
            "answer": "当前知识库里还没有足够内容。先上传一份文本或使用示例文档，再来提问。",
            "citations": [],
        }

    top_chunks = retrieved_chunks[:3]
    citations = [
        {
            "source": f"{chunk.document_name} / chunk {chunk.chunk_index + 1}",
            "score": round(chunk.score, 3),
            "content": chunk.content,
        }
        for chunk in top_chunks
    ]

    answer_lines = [
        f"根据检索到的文档，和问题“{question}”最相关的是下面这些片段。",
        "",
        "可以先把它理解成一个最小版 RAG：先检索，再把检索结果组织成答案。",
        "",
        "重点参考：",
    ]
    for citation in citations:
        answer_lines.append(f"- {citation['source']}: {citation['content'][:180]}")

    answer_lines.extend(
        [
            "",
            "下一步你可以把这里替换成真实大模型回答，保持引用来源不变。",
        ]
    )

    return {"answer": "\n".join(answer_lines), "citations": citations}
