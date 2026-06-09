from __future__ import annotations

from pydantic import BaseModel, Field


class ChatInvokeRequest(BaseModel):
    scenario: str = Field(..., description="场景标识: spark, xiaoke, shuxi, general")
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-=:.]+$",
        description="会话 ID",
    )
    user_text: str = Field(
        ..., min_length=1, max_length=10000, description="用户输入文本"
    )
    context: dict | None = Field(None, description="前端附加上下文（企业名、老板名等）")
    conversation_history: list[dict] | None = Field(
        None, max_length=200, description="对话历史（hermes 会话内可省略）"
    )


class ChatStreamRequest(ChatInvokeRequest):
    pass


class ChatInvokeResponse(BaseModel):
    final_response: str | None = None
    completed: bool = True
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    session_id: str = ""
    error: str | None = None


class ToolInfo(BaseModel):
    name: str
    description: str
    category: str | None = None
    icon: str | None = None
    input_schema: dict | None = None
    output_schema: list[dict] | None = None
    card_template: str | None = None


class ToolsListResponse(BaseModel):
    tools: list[ToolInfo]


class HealthResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# 兼容路由：/invoke 和 /invoke/stream (适配 core-sdk HermesAdapter 格式)
# ---------------------------------------------------------------------------

class CompatInvokeRequest(BaseModel):
    """HermesAdapter 调用契约: prompt + 可选 system_prompt / model / provider。"""

    prompt: str = Field(..., min_length=1, description="用户 prompt（必填）")
    session_id: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-=:.@]+$",
        description="稳定会话 ID；未提供时由 bridge 使用默认兼容会话",
    )
    agent_profile: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_\-=:.]+$",
        description="Hermes agent profile；规则、工具、专家由服务端 profile 管理",
    )
    model: str | None = Field(None, description="模型名（当前由 settings 统一管理，忽略）")
    provider: str | None = Field(None, description="提供商（当前由 settings 统一管理，忽略）")
    max_tokens: int | None = Field(None, description="最大 token 数（透传给 hermes-agent）")
    temperature: float | None = Field(None, description="温度（透传给 hermes-agent）")
    system_prompt: str | None = Field(None, description="覆盖 scenario 的自定义 system prompt")
    skill_command: str | None = Field(None, description="Hermes slash skill command，不含或可含 / 前缀")
    task_id: str | None = Field(None, description="Hermes skill invocation task id")
    runtime_note: str | None = Field(None, description="Hermes skill invocation runtime note")


class CompatUsage(BaseModel):
    prompt_tokens: int | None = 0
    completion_tokens: int | None = 0
    total_tokens: int | None = 0


class CompatInvokeResponse(BaseModel):
    """HermesAdapter 期望的非流式响应格式。"""

    text: str
    model: str | None = None
    provider: str | None = None
    usage: CompatUsage | None = None


class CompatStreamRequest(CompatInvokeRequest):
    """流式兼容路由复用非流式请求体。"""

    pass
