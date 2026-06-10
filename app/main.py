from __future__ import annotations

from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field
from starlette.requests import Request

from app.config import settings
from app.db import add_document, ensure_storage, list_documents
from app.loader import load_pdfs_from_directory
from app.rag import build_answer, chunk_text, retrieve_chunks
from app.vector_store import add_chunks

# 当前文件路径，例如 /project/app/main.py
BASE_DIR = Path(__file__).resolve().parent.parent

# 项目中的模板目录，通常放 index.html 等模板文件
TEMPLATES_DIR = BASE_DIR / "templates"

# 项目中的静态资源目录，通常放 CSS、JS、图片等文件
STATIC_DIR = BASE_DIR / "static"

# 创建 FastAPI 应用实例
app = FastAPI(title="RAG Service", version="0.1.0")

# 把 /static 路由映射到本地 STATIC_DIR 目录
# 这样浏览器访问 /static/xxx.css 时，就能取到对应静态文件
# index.html line:309
# <script src="/static/app.js" defer></script>
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 初始化 Jinja2 模板引擎，并指定模板目录
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# 定义问答接口的请求体结构
class AskRequest(BaseModel):
    question: str = Field(min_length=1)


# 注册应用启动事件
@app.on_event("startup")
def startup_event() -> None:
    # 确保存储系统已经准备好
    ensure_storage()

    # 扫描 data/pdfs/ 目录下的所有 PDF 文件
    # 自动提取文本 → 切块 → 存入 SQLite → 写入 Chroma 向量库
    imported = load_pdfs_from_directory(
        pdf_dir=settings.PDF_DIR,
        chunk_text_fn=chunk_text,
        add_document_fn=add_document,
        add_chunks_fn=add_chunks,
    )
    if imported:
        print(f"启动时已自动导入 {len(imported)} 份 PDF 文档: {', '.join(imported)}")
    else:
        print("未发现新的 PDF 文档，请将 PDF 文件放入 data/pdfs/ 目录后重启服务。")


# 定义首页接口
@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "app_name": "RAG Service",
        },
    )


# 定义健康检查接口
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 定义获取文档列表接口
@app.get("/api/documents")
def get_documents() -> dict[str, object]:
    return {"documents": list_documents()}


# 定义上传文档接口
@app.post("/api/documents")
async def upload_document(
    name: str = Form(default="uploaded-document.txt"),
    content: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> dict[str, object]:

    if file is None and not content.strip():
        raise HTTPException(status_code=400, detail="请上传文件或填写文档内容。")

    document_name = name.strip() or (
        file.filename if file and file.filename else "uploaded-document.txt"
    )
    document_text = content.strip()

    if file is not None:
        raw_bytes = await file.read()
        try:
            document_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="当前版本只支持 UTF-8 文本文件。"
            ) from exc

        if not document_name and file.filename:
            document_name = file.filename

    chunks = chunk_text(document_text)

    if not chunks:
        raise HTTPException(status_code=400, detail="文档内容为空，无法建立索引。")

    # 存入 SQLite
    document_id = add_document(document_name, document_text, chunks)

    # 同时写入 Chroma 向量库
    add_chunks(document_id, document_name, chunks)

    return {
        "message": "文档已导入。",
        "document_id": document_id,
        "chunk_count": len(chunks),
    }


# 定义问答接口
@app.post("/api/ask")
def ask(request: AskRequest) -> dict[str, object]:
    # 从 Chroma 语义检索最相关的 chunk
    retrieved = retrieve_chunks(request.question)

    # 基于"问题 + 检索结果"构造最终回答
    response = build_answer(request.question, retrieved)

    # 把原始问题附加进响应中
    response["question"] = request.question

    return response