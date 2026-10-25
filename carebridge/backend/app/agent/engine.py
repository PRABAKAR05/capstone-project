import json
import logging
from typing import List, Dict, Any, Optional
from uuid import uuid4

from app.core.security import SecurityContext
from app.core.audit import audit_event
from app.agent.prompts import (
    CLINICAL_SYSTEM_PROMPT,
    DISCLAIMER_TEXT,
    EMERGENCY_DISPATCH_MESSAGE,
    detect_red_flag_symptoms,
)
from app.agent.tools import TOOL_DEFINITIONS, execute_agent_tool
from app.agent.client import chat_completion_with_fallback, get_groq_client

logger = logging.getLogger("carebridge.agent.engine")

MAX_REACT_TURNS = 5


def clean_mojibake(text: str) -> str:
    """Normalize corrupted special characters, currency symbols, and broken encoding."""
    if not text:
        return text

    # Attempt re-encoding for UTF-8 misdecoded as Latin-1 (e.g. â€‘, â€“)
    try:
        if any(c in text for c in ("â", "Ã", "Â", "€")):
            repaired = text.encode("latin-1").decode("utf-8")
            text = repaired
    except Exception:
        pass

    replacements = {
        "â€‘": "-",
        "â€“": "-",
        "â€”": "-",
        "â€˜": "'",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "₹": "INR ",
        "?_": " ",
        "??": "-",
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def generate_rule_based_fallback(context: SecurityContext, user_message: str) -> str:
    """Deterministic fallback response when Groq API is unreachable or rate-limited."""
    lower_msg = user_message.lower()
    
    if any(w in lower_msg for w in ("book", "appointment", "schedule", "slot")):
        return (
            "I am currently operating in guided offline mode. "
            "To book an appointment right now, please use the 3-step appointment booking wizard:\n\n"
            "👉 **Navigate to: Patient Portal -> Book Appointment** (`/portal/book`)\n\n"
            "There you can select a department, choose an available doctor, and pick your preferred 30-minute slot.\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )
    elif any(w in lower_msg for w in ("cancel", "reschedule")):
        return (
            "I am currently operating in guided offline mode. "
            "To cancel or reschedule an upcoming visit, please open your appointment list:\n\n"
            "👉 **Navigate to: Patient Portal -> Upcoming Visits** (`/portal`)\n\n"
            "Select the visit and choose 'Cancel Visit' (cancellations must be at least 2 hours in advance).\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )
    elif any(w in lower_msg for w in ("task", "care plan", "checklist", "instruction", "follow up")):
        return (
            "Here is how to check your care coordination tasks:\n\n"
            "👉 **Navigate to: Patient Portal -> Care Tasks** (`/portal`)\n\n"
            "There you can track your medication reminders, lab preparation steps, and clinical care plan instructions (care tasks are separate from doctor appointments).\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )
    elif any(w in lower_msg for w in ("doctor", "specialist", "cardiologist", "physician")):
        return (
            "I am currently operating in guided offline mode. "
            "You can browse all active hospital physicians, departments, and OPD consultation hours under:\n\n"
            "👉 **Hospital Directory / Booking Wizard** (`/portal/book`)\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )
    else:
        return (
            "Hello! I am CareBridge AI, your hospital operations and appointment assistant. "
            "I can help you check doctor availability, review clinic schedules, and coordinate appointments.\n\n"
            "How may I assist your hospital visit today?\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )


async def run_agent_turn(
    context: SecurityContext,
    message_history: List[Dict[str, str]],
    user_message: str,
) -> Dict[str, Any]:
    """Executes a full turn of the clinical AI agent with emergency pre-check, ReAct tool loop, and audit logging."""
    session_turn_id = str(uuid4())

    # 1. Critical Clinical Safety: Emergency Symptom Detection
    if detect_red_flag_symptoms(user_message):
        audit_event(
            event_type="AI_EMERGENCY_TRIGGERED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource="agent_emergency_triage",
            target_id=session_turn_id,
            action="TRIAGE_ESCALATE",
            status="CRITICAL",
        )
        return {
            "role": "assistant",
            "content": EMERGENCY_DISPATCH_MESSAGE,
            "is_emergency": True,
            "tool_calls_executed": [],
            "model_used": "clinical-safety-triage",
        }

    # 2. Check if Groq client is configured
    client = get_groq_client()
    if not client:
        logger.info("Groq client not available. Using deterministic rule-based fallback.")
        fallback_reply = generate_rule_based_fallback(context, user_message)
        return {
            "role": "assistant",
            "content": fallback_reply,
            "is_emergency": False,
            "tool_calls_executed": [],
            "model_used": "rule-based-circuit-breaker",
        }

    # 3. Assemble Conversation Context for ReAct Loop
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": CLINICAL_SYSTEM_PROMPT}
    ]

    # Append sanitized recent conversation history (max 8 turns)
    for msg in message_history[-8:]:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})

    # Append current user prompt
    messages.append({"role": "user", "content": user_message})

    tool_calls_executed: List[Dict[str, Any]] = []
    turn_count = 0

    # 4. ReAct Tool Calling Loop
    try:
        while turn_count < MAX_REACT_TURNS:
            turn_count += 1
            response = await chat_completion_with_fallback(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1,
            )

            choice = response.choices[0]
            msg_obj = choice.message

            # If model returned tool calls, execute them
            if hasattr(msg_obj, "tool_calls") and msg_obj.tool_calls:
                # Append assistant tool call request message
                messages.append(msg_obj)

                for tc in msg_obj.tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        parsed_args = {}

                    logger.info(f"Agent executing tool '{fn_name}' with args {parsed_args}")
                    tool_res = execute_agent_tool(context, fn_name, parsed_args)

                    tool_calls_executed.append({
                        "tool": fn_name,
                        "arguments": parsed_args,
                        "result_summary": "success" if "error" not in tool_res else tool_res.get("error"),
                    })

                    # Append tool response
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(tool_res),
                    })
                # Continue loop to allow model to synthesize tool results
                continue

            # Model produced final textual answer
            raw_text = msg_obj.content or ""
            if DISCLAIMER_TEXT not in raw_text:
                final_text = raw_text.strip() + f"\n\n*{DISCLAIMER_TEXT}*"
            else:
                final_text = raw_text.strip()

            audit_event(
                event_type="AI_AGENT_TURN_COMPLETED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="agent_conversation",
                target_id=session_turn_id,
                action="CHAT_RESPONSE",
                status="SUCCESS",
            )

            return {
                "role": "assistant",
                "content": clean_mojibake(final_text),
                "is_emergency": False,
                "tool_calls_executed": tool_calls_executed,
                "model_used": getattr(response, "model", "llama-3.3-70b-versatile"),
            }

        # If max turns reached without final text, synthesize tool executions
        fallback_msg = (
            "I have processed your request with the hospital system. "
            "Please check your appointments in the portal to review the updated details.\n\n"
            f"*{DISCLAIMER_TEXT}*"
        )
        return {
            "role": "assistant",
            "content": fallback_msg,
            "is_emergency": False,
            "tool_calls_executed": tool_calls_executed,
            "model_used": "multi-turn-finalizer",
        }

    except Exception as e:
        logger.error(f"Error in ReAct execution loop: {e}. Falling back to circuit breaker.")
        audit_event(
            event_type="AI_AGENT_CIRCUIT_BREAKER_TRIGGERED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource="agent_conversation",
            target_id=session_turn_id,
            action="ERROR_FALLBACK",
            status="WARNING",
        )
        return {
            "role": "assistant",
            "content": generate_rule_based_fallback(context, user_message),
            "is_emergency": False,
            "tool_calls_executed": tool_calls_executed,
            "model_used": "circuit-breaker-fallback",
        }
