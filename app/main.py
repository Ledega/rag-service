# 开启未来版本的注解行为，让类型注解以字符串形式延迟解析
from __future__ import annotations

from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 导入 Pydantic 的 BaseModel 和 Field：
# BaseModel 用来定义请求/响应的数据结构
# Field 用来给字段增加约束
from pydantic import BaseModel, Field

# 导入 Request 类型，模板渲染时常常需要传入 request 对象
from starlette.requests import Request

# 从你自己的 db模块 | RAG模块中导入若干函数：
from app.db import add_document, ensure_storage, list_chunks, list_documents, seed_demo_documents
from app.rag import build_answer, chunk_text, retrieve_chunks

# 当前文件路径，例如 /project/app/main.py
# resolve() 会得到绝对路径
# parent.parent 表示上上级目录，通常用于回到项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 项目中的模板目录，通常放 index.html 等模板文件
TEMPLATES_DIR = BASE_DIR / "templates"

# 项目中的静态资源目录，通常放 CSS、JS、图片等文件
STATIC_DIR = BASE_DIR / "static"

# 创建 FastAPI 应用实例
# title 是接口文档标题
# version 是当前应用版本
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
    # question 字段必须是字符串，最小长度为 1，防止空问题
    question: str = Field(min_length=1)


# 注册应用启动事件
# 当服务启动时，这个函数会自动执行一次
@app.on_event("startup")
def startup_event() -> None:
    # 确保存储系统已经准备好，例如创建数据目录、数据库文件、数据表等
    ensure_storage()

    # 写入演示文档，方便系统刚启动时就有基础数据可用
    seed_demo_documents()


# 定义首页接口
# 当用户访问 GET / 时，返回 HTML 页面
@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    # 渲染 templates 目录下的 index.html
    # 并传入模板变量
    return templates.TemplateResponse(
        # 当前请求对象，Jinja 模板里通常需要它
        request,

        # 要渲染的模板文件名
        "index.html",

        # 传递给模板的上下文变量字典
        {
            # request 必须传给模板，很多模板函数依赖它
            "request": request,

            # index.html line:6     <title>{{ app_name }}</title>
            # 这里传入 app_name 变量，模板里就可以使用 {{ app_name }} 来显示应用名称
            "app_name": "RAG Service",
        },
    )


# 定义健康检查接口
# 通常用于运维系统判断服务是否存活
@app.get("/health")
def health() -> dict[str, str]:
    # 返回一个简单的 JSON，表示服务正常
    return {"status": "ok"}


# 定义获取文档列表接口
# 用于查看系统当前存储了哪些文档
@app.get("/api/documents")
def get_documents() -> dict[str, object]:
    # 调用 list_documents() 取出所有文档
    # 再包装成统一的 JSON 结构返回
    return {"documents": list_documents()}


# 定义上传文档接口
# 支持文本内容上传，也支持文件上传 异步函数
@app.post("/api/documents")
async def upload_document(
    # name 是表单字段，表示文档名称，默认值为 uploaded-document.txt
    name: str = Form(default="uploaded-document.txt"),

    # content 是表单字段，表示直接输入的文档文本内容，默认空字符串
    content: str = Form(default=""),

    # file 是上传文件字段，可选；如果没传文件则为 None
    file: UploadFile | None = File(default=None),
) -> dict[str, object]:

    # 如果既没有上传文件，也没有填写文本内容，则返回 400 错误
    if file is None and not content.strip():
        raise HTTPException(status_code=400, detail="请上传文件或填写文档内容。")

    # 优先使用 name 去掉首尾空格后的结果作为文档名
    # 如果 name 为空，则尝试使用上传文件的文件名
    # 如果还没有，就使用默认值 uploaded-document.txt
    document_name = name.strip() or (file.filename if file and file.filename else "uploaded-document.txt")

    # 先把表单文本内容去掉首尾空格，作为初始文档正文
    document_text = content.strip()

    # 如果用户上传了文件，则优先读取文件内容
    if file is not None:
        # 异步读取文件全部字节内容
        raw_bytes = await file.read()

        try:
            # 尝试按 UTF-8 解码为字符串
            document_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            # 如果解码失败，说明文件不是 UTF-8 文本，返回 400 错误
            raise HTTPException(status_code=400, detail="当前版本只支持 UTF-8 文本文件。") from exc

        # 如果前面没有得到有效文档名，而上传文件本身有文件名，则使用它
        if not document_name and file.filename:
            document_name = file.filename

    # 把完整文档文本切成多个块，供后续检索使用
    chunks = chunk_text(document_text)

    # 如果切分后没有任何块，说明内容为空或无有效文本，返回 400 错误
    if not chunks:
        raise HTTPException(status_code=400, detail="文档内容为空，无法建立索引。")

    # 调用数据库层保存文档名、原文内容和切块结果
    # 返回值通常是新文档的唯一 ID
    document_id = add_document(document_name, document_text, chunks)

    # 返回上传成功结果
    return {
        # 给前端展示的提示消息
        "message": "文档已导入。",

        # 新文档的唯一标识
        "document_id": document_id,

        # 这篇文档被切成了多少个块
        "chunk_count": len(chunks),
    }


# 定义问答接口
# 前端向该接口提交问题，系统返回基于文档的回答
@app.post("/api/ask")
def ask(request: AskRequest) -> dict[str, object]:
    # 取出当前所有已存储的文档块
    chunks = list_chunks()

    # 根据用户问题，从全部文档块中检索最相关的块
    retrieved = retrieve_chunks(request.question, chunks)

    # 基于“问题 + 检索结果”构造最终回答
    response = build_answer(request.question, retrieved)

    # 把原始问题附加进响应中，方便前端展示或调试
    response["question"] = request.question

    # 返回最终结果
    return response