from fastapi import APIRouter, Depends, status
from app.core.security import get_security_context, SecurityContext
from app.core.config import settings
from app.schemas.chat import (
    ChatTurnRequest,
    ChatTurnResponse,
    VoiceConfigResponse,
)
from app.chat.engine import run_conversational_turn
from app.agent.client import PRIMARY_MODEL, FALLBACK_MODEL, get_groq_client
from app.chat.tools import CHAT_TOOL_DEFINITIONS

router = APIRouter(prefix="/chat", tags=["conversational-ai"])


@router.post("/message", response_model=ChatTurnResponse, status_code=status.HTTP_200_OK)
async def send_chat_message(
    payload: ChatTurnRequest,
    context: SecurityContext = Depends(get_security_context),
):
    """Authenticated conversational AI assistant endpoint.
    Supports hospital workflow navigation, doctor discovery, appointment booking/cancellation with confirmation,
    document status tracking, verified prescription review, and care plan checklists.
    Enforces deterministic emergency triage (112/108/102) and medication dosage calculation barriers.
    """
    response = await run_conversational_turn(context=context, request=payload)
    return response


@router.get("/voice-config", response_model=VoiceConfigResponse, status_code=status.HTTP_200_OK)
def get_voice_configuration(
    context: SecurityContext = Depends(get_security_context),
):
    """Returns configuration and capabilities for browser-native Web Speech API voice interaction."""
    return VoiceConfigResponse(
        status="available",
        engine="browser-native-web-speech",
        supported_locales=["en-IN", "ta-IN", "en-US"],
        features=["speech-recognition", "speech-synthesis"],
        instructions="Use window.SpeechRecognition/webkitSpeechRecognition and window.speechSynthesis. Client fallback to keyboard input when unavailable.",
    )


@router.get("/health", status_code=status.HTTP_200_OK)
def get_conversational_health(
    context: SecurityContext = Depends(get_security_context),
):
    """Health probe reporting conversational engine readiness, tools registered, and model configuration."""
    groq_client = get_groq_client()
    return {
        "status": "operational",
        "engine": "CareBridge Conversational AI Engine",
        "groq_configured": groq_client is not None,
        "primary_model": PRIMARY_MODEL,
        "fallback_model": FALLBACK_MODEL,
        "registered_tools_count": len(CHAT_TOOL_DEFINITIONS),
        "emergency_triage_interceptor": "active",
        "dosage_guardrail_interceptor": "active",
        "action_confirmation_barrier": "active",
    }
