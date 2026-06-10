from __future__ import annotations

from app.config import settings

# 默认系统提示词，可被外部覆盖
DEFAULT_SYSTEM_PROMPT = (
    "你是一个基于文档内容回答问题的助手。"
    "请根据提供的文档片段回答问题，如果找不到相关信息就如实说不知道。"
    "请注明信息来源。"
)


def get_llm_model():
    """获取 LLM 模型实例（单例懒加载）。"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
    )


def build_context_from_citations(citations: list[dict]) -> str:
    """将引用片段拼装为 LLM 上下文。"""
    parts = []
    for i, citation in enumerate(citations, 1):
        parts.append(f"[{i}] 来源：{citation['source']}\n{citation['content']}")
    return "\n\n".join(parts)


def generate_answer(
    question: str,
    context_chunks: list[dict],
    system_prompt: str | None = None,
) -> str:
    """
    基于问题和检索到的上下文，生成回答。

    :param question: 用户问题
    :param context_chunks: 检索到的相关片段列表（含 source 和 content）
    :param system_prompt: 可选的系统提示词，不传则使用默认
    :return: LLM 生成的回答文本
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm_model()
    context = build_context_from_citations(context_chunks)

    messages = [
        SystemMessage(content=system_prompt or DEFAULT_SYSTEM_PROMPT),
        HumanMessage(content=f"文档内容：\n{context}\n\n问题：{question}"),
    ]

    response = llm.invoke(messages)
    return response.content