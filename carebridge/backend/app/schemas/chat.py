from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatCitation(BaseModel):
    source_type: str = Field(..., description="Type of source: 'document', 'prescription', 'appointment', 'care_task', 'hospital_directory'")
    title: str = Field(..., description="Title or human-readable identifier of the source")
    reference_id: Optional[str] = Field(None, description="Identifier of the referenced resource")
    snippet: Optional[str] = Field(None, description="Relevant excerpt or metadata")


class ActionConfirmation(BaseModel):
    action_type: str = Field(..., description="Action name, e.g. 'book_appointment' or 'cancel_appointment'")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    description: str = Field(..., description="Human-readable summary of the action requiring confirmation")


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', 'system'")
    content: str = Field(..., description="Message text content")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of message")
    citations: Optional[List[ChatCitation]] = Field(default_factory=list)


class ChatTurnRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User prompt or natural language query")
    conversation_id: Optional[str] = Field(None, description="Optional conversation tracking UUID")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation turns")
    confirmed_action: Optional[ActionConfirmation] = Field(None, description="Explicit client confirmation for sensitive write actions")


class ChatTurnResponse(BaseModel):
    conversation_id: str
    role: str = "assistant"
    content: str
    is_emergency: bool = False
    requires_confirmation: bool = False
    pending_action: Optional[ActionConfirmation] = None
    citations: List[ChatCitation] = Field(default_factory=list)
    tool_calls_executed: List[Dict[str, Any]] = Field(default_factory=list)
    model_used: str


class VoiceConfigResponse(BaseModel):
    status: str = "available"
    engine: str = "browser-native-web-speech"
    supported_locales: List[str] = ["en-IN", "ta-IN", "en-US"]
    features: List[str] = ["speech-recognition", "speech-synthesis"]
    instructions: str = "Use browser SpeechRecognition and window.speechSynthesis. Fallback to text entry on unsupported browsers."
