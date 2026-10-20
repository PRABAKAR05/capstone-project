from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User prompt or clinical query")
    history: Optional[List[ChatMessageItem]] = Field(default=[], description="Recent conversation history")


class AgentChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    is_emergency: bool = False
    tool_calls_executed: List[Dict[str, Any]] = []
    model_used: str


class AgentHealthResponse(BaseModel):
    status: str
    groq_configured: bool
    primary_model: str
    fallback_model: str
