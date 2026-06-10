from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str | Path) -> list[dict[str, object]]:
    """
    从 PDF 文件中提取文本，按页返回。

    :param pdf_path: PDF 文件路径
    :return: 按页提取的文本列表，每页格式为 {"page": int, "text": str}
    """
    from pypdf import PdfReader

    pages: list[dict[str, object]] = []
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.warning("PDF 文件不存在: %s", pdf_path)
        return pages

    reader = PdfReader(str(pdf_path))
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text().strip()
        if text:
            pages.append({"page": page_num + 1, "text": text})

    logger.info("已从 %s 提取 %d 页文本", pdf_path.name, len(pages))
    return pages


def load_pdfs_from_directory(
    pdf_dir: str | Path,
    chunk_text_fn,
    add_document_fn,
    add_chunks_fn=None,
) -> list[str]:
    """
    扫描指定目录下所有 PDF 文件，逐个提取文本、切块、存入数据库和向量库。

    :param pdf_dir: PDF 文件所在目录
    :param chunk_text_fn: chunk_text 函数引用，用于将文本切块
    :param add_document_fn: add_document 函数引用，用于将文档和切块存入 SQLite
    :param add_chunks_fn: add_chunks 函数引用（可选），用于将切块写入 Chroma 向量库
    :return: 成功导入的 PDF 文件名列表
    """
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True, exist_ok=True)
        logger.info("已创建 PDF 目录: %s", pdf_dir)
        return []

    imported: list[str] = []
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        logger.info("PDF 目录中没有 PDF 文件: %s", pdf_dir)
        return []

    for pdf_path in pdf_files:
        filename = pdf_path.name
        pages = extract_text_from_pdf(pdf_path)
        if not pages:
            logger.warning("跳过空 PDF: %s", filename)
            continue

        # 将所有页文本合并为完整文档内容
        full_text = "\n\n".join(page["text"] for page in pages)

        # 切块
        chunks = chunk_text_fn(full_text)

        if not chunks:
            logger.warning("PDF 提取文本为空，跳过: %s", filename)
            continue

        # 1) 存入 SQLite 数据库
        document_id = add_document_fn(filename, full_text, chunks)

        # 2) 如果提供了 add_chunks_fn，同时写入 Chroma 向量库
        if add_chunks_fn is not None:
            add_chunks_fn(document_id, filename, chunks)

        imported.append(filename)
        logger.info(
            "已导入 PDF: %s (document_id=%d, pages=%d, chunks=%d)",
            filename,
            document_id,
            len(pages),
            len(chunks),
        )

    return imported
