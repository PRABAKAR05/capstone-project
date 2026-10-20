from fastapi import APIRouter, Depends, status
from app.core.security import get_security_context, SecurityContext
from app.core.config import settings
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentHealthResponse
from app.agent.engine import run_agent_turn
from app.agent.client import PRIMARY_MODEL, FALLBACK_MODEL, get_groq_client

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse, status_code=status.HTTP_200_OK)
async def chat_with_agent(
    payload: AgentChatRequest,
    context: SecurityContext = Depends(get_security_context),
):
    """Authenticated clinical and hospital operations AI agent conversation endpoint.
    Enforces tenant scoping, role permissions, emergency triage detection, and tool calling.
    """
    history_dicts = [m.model_dump() for m in (payload.history or [])]
    result = await run_agent_turn(
        context=context,
        message_history=history_dicts,
        user_message=payload.message,
    )
    return AgentChatResponse(**result)


@router.get("/health", response_model=AgentHealthResponse)
def get_agent_health(
    context: SecurityContext = Depends(get_security_context),
):
    """Health probe reporting AI agent framework readiness and Groq configuration status."""
    has_key = bool(settings.GROQ_API_KEY)
    return AgentHealthResponse(
        status="operational",
        groq_configured=has_key,
        primary_model=PRIMARY_MODEL,
        fallback_model=FALLBACK_MODEL,
    )
