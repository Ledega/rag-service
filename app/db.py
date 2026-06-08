from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# ==========================================
# 路径配置与全局变量设置
# ==========================================
# 获取当前文件所在目录的上一级目录（通常是项目的根目录）
BASE_DIR = Path(__file__).resolve().parent.parent
# 定义数据存放文件夹路径（根目录下的 data 文件夹）
DATA_DIR = BASE_DIR / "data"
# 定义 SQLite 数据库文件的绝对路径
DB_PATH = DATA_DIR / "rag.db"

# 预设的演示用文档数据，包含两个元组：(文档名称, 文档内容)
DEMO_DOCUMENTS = [
    (
        "rag-intro.md",
        "RAG combines retrieval and generation. The retrieval step finds the most relevant chunks from a knowledge base before the model writes the final answer.\n\nA good RAG system needs chunking, embeddings, a vector or lexical index, and citations so users can inspect the sources.",
    ),
    (
        "fastapi-notes.md",
        "FastAPI is a lightweight Python web framework for building APIs. It is a good choice for a small RAG service because it can serve JSON endpoints and a simple frontend from the same application.",
    ),
]


def ensure_storage() -> None:
    """
    确保存储环境正常初始化。
    如果数据文件夹不存在则创建，并初始化 SQLite 数据库的表结构。
    """
    # 创建 data 文件夹。parents=True 表示如果父目录不存在连同父目录一起创建；exist_ok=True 表示如果已存在则不报错
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 获取数据库连接
    with get_connection() as connection:
        # 开启 SQLite 的外键约束支持（SQLite 默认是关闭的）
        connection.execute("PRAGMA foreign_keys = ON")
        
        # 创建 documents (文档) 表
        # 字段包括：主键 id、文档名 name、文本内容 content、创建时间 created_at
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # 创建 chunks (文档切片) 表
        # 在 RAG 系统中，长文档通常会被切分成多个短的 chunk 方便向量化检索
        # 字段包括：主键 id、所属文档的 document_id、切片序号 chunk_index、切片内容 content、创建时间
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
            """
        )
        # 提交事务，保存表结构更改
        connection.commit()


def seed_demo_documents() -> None:
    """
    向数据库中植入初始的演示文档数据（如果数据库为空的话）。
    """
    with get_connection() as connection:
        # 查询 documents 表中的记录总数
        existing_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        # 如果数据库中已经存在文档数据，则直接返回，不再重复插入
        if existing_count:
            return

    # 从当前项目的 app.rag 模块中导入分块函数 (延迟导入，防止循环依赖或加载过早)
    from app.rag import chunk_text

    # 遍历前面定义的演示文档列表，将其逐个添加到数据库中
    for name, content in DEMO_DOCUMENTS:
        # chunk_text(content) 会将完整文本切割成片段（chunks）
        add_document(name, content, chunk_text(content))


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    获取 SQLite 数据库连接的上下文管理器。
    使用 @contextmanager 装饰器，可以使用 with 语句安全地管理数据库连接，确保用完后自动关闭。
    """
    # 连接到指定路径的 SQLite 数据库
    connection = sqlite3.connect(DB_PATH)
    # 设置 row_factory 为 sqlite3.Row，这样查询结果可以用字典方式（键值对）访问列字段，比单纯的元组更好用
    connection.row_factory = sqlite3.Row
    try:
        # 将连接对象交还给 with 语句块
        yield connection
    finally:
        # 无论有没有发生异常，最后都会执行 close，释放数据库资源
        connection.close()


def add_document(name: str, content: str, chunks: list[str] | None = None) -> int:
    """
    向数据库添加一篇新文档，并将其对应的文本切片 (chunks) 一并入库。
    
    :param name: 文档名称
    :param content: 文档完整内容
    :param chunks: 预先分好的文本切片列表，如果没有提供，则自动调用 chunk_text 进行分块
    :return: 新插入文档的 ID
    """
    from app.rag import chunk_text

    # 如果没提供 chunks 参数，则调用系统内置的文本切片逻辑
    chunk_list = chunks if chunks is not None else chunk_text(content)
    
    with get_connection() as connection:
        # 1. 插入主文档信息
        cursor = connection.execute(
            "INSERT INTO documents (name, content) VALUES (?, ?)",
            (name, content),
        )
        # 获取刚插入的这篇文档的自增 ID
        document_id = int(cursor.lastrowid)
        
        # 2. 批量插入该文档对应的所有切片 (chunks)
        # enumerate 会生成切片的索引 (index) 和内容 (chunk)
        connection.executemany(
            "INSERT INTO chunks (document_id, chunk_index, content) VALUES (?, ?, ?)",
            [(document_id, index, chunk) for index, chunk in enumerate(chunk_list)],
        )
        # 提交事务，确保主文档和切片数据作为一个整体被安全写入
        connection.commit()
        
        return document_id


def list_documents() -> list[dict[str, object]]:
    """
    获取数据库中所有的文档列表及其对应的切片数量。
    
    :return: 包含文档信息的字典列表
    """
    with get_connection() as connection:
        # 使用 LEFT JOIN 关联 documents 表和 chunks 表，统计每个文档有多少个 chunk
        rows = connection.execute(
            """
            SELECT
                d.id,
                d.name,
                d.created_at,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC, d.id DESC
            """
        ).fetchall()
    # 将 sqlite3.Row 对象转换为标准的 Python 字典并返回
    return [dict(row) for row in rows]


def list_chunks() -> list[dict[str, object]]:
    """
    获取数据库中所有的文本切片数据，同时包含它所属的文档名称。
    
    :return: 包含切片信息的字典列表
    """
    with get_connection() as connection:
        # 使用 JOIN 联合查询，调取出每个 chunk 对应的具体信息和父文档名
        rows = connection.execute(
            """
            SELECT
                c.id,
                c.document_id,
                d.name AS document_name,
                c.chunk_index,
                c.content
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            ORDER BY d.id DESC, c.chunk_index ASC
            """
        ).fetchall()
    # 将 sqlite3.Row 对象转换为标准的 Python 字典并返回
    return [dict(row) for row in rows]