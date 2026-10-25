import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from app.core.security import SecurityContext
from app.core.audit import audit_event
from app.schemas.chat import (
    ChatTurnRequest,
    ChatTurnResponse,
    ChatMessage,
    ChatCitation,
    ActionConfirmation,
)
from app.chat.prompts import (
    CONVERSATIONAL_SYSTEM_PROMPT,
    DISCLAIMER_TEXT,
    EMERGENCY_DISPATCH_MESSAGE,
    MEDICATION_DOSAGE_REFUSAL_MESSAGE,
    detect_red_flag_symptoms,
    detect_medication_dosage_query,
)
from app.chat.tools import (
    CHAT_TOOL_DEFINITIONS,
    execute_chat_tool,
)
from app.agent.client import (
    chat_completion_with_fallback,
    get_groq_client,
    PRIMARY_MODEL,
)

logger = logging.getLogger("carebridge.chat.engine")

MAX_REACT_TURNS = 5

def clean_mojibake(text: str) -> str:
    """Normalize corrupted special characters, currency symbols, and broken multi-byte encoding."""
    if not text:
        return text

    # 1. Regex repair for UTF-8 byte sequences erroneously decoded as Latin-1 (ISO-8859-1)
    def _fix_latin1_match(m):
        try:
            return m.group(0).encode("latin-1").decode("utf-8")
        except Exception:
            return m.group(0)

    text = re.sub(r"[\u0080-\u00ff]{2,}", _fix_latin1_match, text)

    # 2. Comprehensive replacements for multi-byte, CP1252, Latin-1, and ambiguous unicode sequences
    replacements = [
        # Bullet variations
        ("\u00e2\u0080\u00a2", "•"),
        ("\u00e2\u20ac\u00a2", "•"),
        ("â€¢", "•"),
        # Narrow NBSP & NBSP variations -> standard space
        ("\u00e2\u0080\u00af", " "),
        ("\u00e2\u20ac\u00af", " "),
        ("â€¯", " "),
        ("\u202f", " "),
        ("\u00a0", " "),
        # Hyphens & Dashes
        ("\u00e2\u0080\u0091", "-"),
        ("\u00e2\u20ac\u0091", "-"),
        ("\u00e2\u20ac\u2018", "-"),
        ("â€\u2011", "-"),
        ("â€‘", "-"),
        ("\u00e2\u0080\u0093", "-"),
        ("\u00e2\u20ac\u0093", "-"),
        ("â€“", "-"),
        ("\u00e2\u0080\u0094", "-"),
        ("\u00e2\u20ac\u0094", "-"),
        ("â€”", "-"),
        ("\u2011", "-"),
        ("\u2012", "-"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        # Quotes & Apostrophes
        ("\u00e2\u0080\u0098", "'"),
        ("\u00e2\u0080\u0099", "'"),
        ("â€˜", "'"),
        ("â€™", "'"),
        ("\u00e2\u0080\u009c", '"'),
        ("\u00e2\u0080\u009d", '"'),
        ("â€œ", '"'),
        ("â€\x9d", '"'),
        ("â€", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u201c", '"'),
        ("\u201d", '"'),
        # Currency & formatting artifacts
        ("₹", "INR "),
        ("?_", " "),
        ("??", "-"),
    ]
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    return text


Tuple_Response = Tuple[str, bool, bool, Optional[ActionConfirmation], List[ChatCitation], List[Dict[str, Any]]]


def generate_grounded_fallback(
    context: SecurityContext,
    user_message: str,
) -> Tuple_Response:
    """Deterministic, grounded response when external LLM is offline or unconfigured.
    Directly queries database tools matching user's navigational intent.
    """
    lower = user_message.lower()
    citations: List[ChatCitation] = []
    tools_executed: List[Dict[str, Any]] = []

    if any(w in lower for w in ("emergency", "chest pain", "shortness of breath", "heart attack")):
        return EMERGENCY_DISPATCH_MESSAGE, True, False, None, citations, tools_executed

    if any(w in lower for w in ("prescription", "medication", "medicine", "pill", "tablet", "adherence")):
        res, cits = execute_chat_tool(context, "get_my_prescriptions", {})
        citations.extend(cits)
        tools_executed.append({"tool": "get_my_prescriptions", "status": "success"})
        prescriptions = res.get("prescriptions", [])
        if prescriptions:
            lines = ["Here are your current active prescriptions:"]
            for p in prescriptions:
                items_str = ", ".join([f"{it['medication_name']} ({it['dosage']}, {it['frequency']})" for it in p["items"]])
                lines.append(f"• **Prescription by {p['doctor_name']}** [{p['status'].upper()}]: {items_str}")
                lines.append(f"  *Adherence Compliance:* {p['adherence_score']} | *Verify:* [Public Link]({p['verification_url']})")
            lines.append("\n*Remember: CareBridge AI cannot modify or advise on unprescribed dosages. Please consult your physician for changes.*")
            lines.append(f"\n*{DISCLAIMER_TEXT}*")
            return "\n".join(lines), False, False, None, citations, tools_executed
        else:
            return (
                "You currently have no active digital prescriptions on record in this hospital.\n\n"
                f"*{DISCLAIMER_TEXT}*",
                False, False, None, citations, tools_executed
            )

    if any(w in lower for w in ("document", "report", "lab", "discharge", "scan", "record")):
        res, cits = execute_chat_tool(context, "get_my_documents", {})
        citations.extend(cits)
        tools_executed.append({"tool": "get_my_documents", "status": "success"})
        docs = res.get("documents", [])
        if docs:
            lines = ["Here is the status of your uploaded clinical documents:"]
            for d in docs:
                status_icon = "✅" if d["status"] == "completed" else "⏳" if d["status"] == "pending" else "⚠️"
                lines.append(f"• {status_icon} **{d['filename']}** ({d['document_type']}): Status: **{d['status'].upper()}**")
            lines.append("\nYou can view full extracted clinical entities in your **Documents** tab.")
            lines.append(f"\n*{DISCLAIMER_TEXT}*")
            return "\n".join(lines), False, False, None, citations, tools_executed
        else:
            return (
                "You have no uploaded clinical documents on record. You can upload clinical records in the **Documents** section.\n\n"
                f"*{DISCLAIMER_TEXT}*",
                False, False, None, citations, tools_executed
            )

    if any(w in lower for w in ("task", "care plan", "instruction", "follow up", "follow-up", "checklist")):
        res, cits = execute_chat_tool(context, "get_my_care_tasks", {})
        citations.extend(cits)
        tools_executed.append({"tool": "get_my_care_tasks", "status": "success"})
        tasks = res.get("care_tasks", [])
        if tasks:
            lines = ["Here are your active care coordination tasks:"]
            for t in tasks:
                badge = "🔴" if t["priority"] == "urgent" else "🟡" if t["priority"] == "high" else "🟢"
                lines.append(f"• {badge} **{t['title']}** [{t['status'].upper()}] - {t['description']}")
            lines.append(f"\n*{DISCLAIMER_TEXT}*")
            return "\n".join(lines), False, False, None, citations, tools_executed
        else:
            return (
                "You have no pending care plan tasks at this time.\n\n"
                f"*{DISCLAIMER_TEXT}*",
                False, False, None, citations, tools_executed
            )

    if any(w in lower for w in ("staff", "shift", "overview", "unclaimed", "operations", "metric")) and context.role not in ("patient", "caregiver"):
        res, cits = execute_chat_tool(context, "get_staff_workflow_summary", {})
        citations.extend(cits)
        tools_executed.append({"tool": "get_staff_workflow_summary", "status": "success"})
        lines = [
            "**Hospital Staff Shift Operations Overview:**",
            f"• **Appointments Scheduled Today:** {res.get('appointments_today', 0)}",
            f"• **Unclaimed Care Tasks:** {res.get('unclaimed_care_tasks', 0)}",
            f"• **Pending Documents for Verification:** {res.get('pending_documents', 0)}",
            f"• **Active Clinical Conflicts:** {res.get('open_clinical_conflicts', 0)}",
        ]
        return "\n".join(lines), False, False, None, citations, tools_executed

    if any(w in lower for w in ("doctor", "specialist", "physician", "department")):
        res, cits = execute_chat_tool(context, "search_doctors", {})
        citations.extend(cits)
        tools_executed.append({"tool": "search_doctors", "status": "success"})
        docs = res.get("doctors", [])[:5]
        lines = ["Here are available hospital specialists:"]
        for d in docs:
            lines.append(f"• **{d['name']}** — {d['specialty']} ({d['department']}) | OPD Room: {d['opd_room']}")
        lines.append("\nWould you like to check available consultation slots with any of these specialists?")
        lines.append(f"\n*{DISCLAIMER_TEXT}*")
        return "\n".join(lines), False, False, None, citations, tools_executed

    if any(w in lower for w in ("appointment", "visit", "schedule", "my appointment")):
        res, cits = execute_chat_tool(context, "get_my_appointments", {})
        citations.extend(cits)
        tools_executed.append({"tool": "get_my_appointments", "status": "success"})
        appts = res.get("appointments", [])
        if appts:
            lines = ["Here are your upcoming appointments:"]
            for a in appts:
                lines.append(f"• **{a['doctor_name']}** ({a['department']}) on {a['scheduled_at']} [Status: {a['status'].upper()}] - Token #{a.get('token_number')}")
            lines.append(f"\n*{DISCLAIMER_TEXT}*")
            return "\n".join(lines), False, False, None, citations, tools_executed
        else:
            return (
                "You have no upcoming appointments scheduled. To book a consultation, simply tell me which doctor or specialty you need.\n\n"
                f"*{DISCLAIMER_TEXT}*",
                False, False, None, citations, tools_executed
            )

    # General hospital information fallback
    res, cits = execute_chat_tool(context, "lookup_hospital_info", {})
    citations.extend(cits)
    return (
        f"Hello! I am CareBridge AI, your hospital assistant for **{res.get('hospital_name', 'CareBridge Health')}**.\n\n"
        "I can help you with:\n"
        "• Finding doctors and booking consultation appointments\n"
        "• Checking your active prescriptions and adherence schedule\n"
        "• Tracking your uploaded medical documents\n"
        "• Viewing your care coordination checklist\n\n"
        "How may I assist you today?\n\n"
        f"*{DISCLAIMER_TEXT}*",
        False, False, None, citations, tools_executed
    )


async def run_conversational_turn(
    context: SecurityContext,
    request: ChatTurnRequest,
) -> ChatTurnResponse:
    """Executes a complete turn of the Conversational AI Assistant.
    Enforces deterministic emergency triage, dosage inquiry barriers, confirmation safeguards for sensitive actions,
    grounded server-side tool calling, and zero-PHI structured audit logging.
    """
    conversation_id = request.conversation_id or str(uuid4())
    user_message = request.message.strip()

    # 1. Deterministic Emergency Interception (Zero LLM latency)
    if detect_red_flag_symptoms(user_message):
        audit_event(
            event_type="CHAT_EMERGENCY_TRIGGERED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource="conversational_triage",
            target_id=conversation_id,
            action="EMERGENCY_DISPATCH",
            status="CRITICAL",
        )
        return ChatTurnResponse(
            conversation_id=conversation_id,
            role="assistant",
            content=EMERGENCY_DISPATCH_MESSAGE,
            is_emergency=True,
            requires_confirmation=False,
            pending_action=None,
            citations=[],
            tool_calls_executed=[],
            model_used="deterministic-clinical-triage",
        )

    # 2. Deterministic Medication Dosage Query Refusal (AC-10.6)
    if detect_medication_dosage_query(user_message):
        audit_event(
            event_type="CHAT_DOSAGE_INQUIRY_REFUSED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource="conversational_medication_safety",
            target_id=conversation_id,
            action="DOSAGE_REFUSAL",
            status="BLOCKED",
        )
        return ChatTurnResponse(
            conversation_id=conversation_id,
            role="assistant",
            content=MEDICATION_DOSAGE_REFUSAL_MESSAGE,
            is_emergency=False,
            requires_confirmation=False,
            pending_action=None,
            citations=[],
            tool_calls_executed=[],
            model_used="deterministic-dosage-guardrail",
        )

    # 3. Handle Confirmed Action Execution if client submitted one
    if request.confirmed_action:
        act = request.confirmed_action
        action_name = act.action_type
        args = act.parameters
        tool_res, citations = execute_chat_tool(context, action_name, args)

        audit_event(
            event_type="CHAT_CONFIRMED_ACTION_EXECUTED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource=action_name,
            target_id=conversation_id,
            action="EXECUTE_CONFIRMED",
            status="SUCCESS" if "error" not in tool_res else "FAILED",
        )

        if "error" in tool_res:
            reply_text = f"Action could not be completed: {tool_res['error']}"
        else:
            reply_text = tool_res.get("message", f"The action '{action_name}' was successfully completed.")

        return ChatTurnResponse(
            conversation_id=conversation_id,
            role="assistant",
            content=reply_text,
            is_emergency=False,
            requires_confirmation=False,
            pending_action=None,
            citations=citations,
            tool_calls_executed=[{"tool": action_name, "status": "executed"}],
            model_used="action-confirmation-executor",
        )

    # 4. Check LLM availability
    groq_client = get_groq_client()
    if not groq_client:
        logger.info("Groq client unavailable. Using grounded deterministic fallback.")
        content, is_em, req_conf, pending, citations, tools_done = generate_grounded_fallback(context, user_message)
        
        audit_event(
            event_type="CHAT_TURN_COMPLETED",
            actor_id=str(context.user_id),
            actor_role=context.role,
            hospital_id=str(context.hospital_id),
            target_resource="conversational_ai",
            target_id=conversation_id,
            action="TURN_COMPLETED",
            status="SUCCESS",
        )

        return ChatTurnResponse(
            conversation_id=conversation_id,
            role="assistant",
            content=clean_mojibake(content),
            is_emergency=is_em,
            requires_confirmation=req_conf,
            pending_action=pending,
            citations=citations,
            tool_calls_executed=tools_done,
            model_used="grounded-deterministic-fallback",
        )

    # 5. Assemble Context for Model with Tools
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": CONVERSATIONAL_SYSTEM_PROMPT}
    ]

    for h in (request.history or [])[-8:]:
        if h.role in ("user", "assistant") and h.content:
            messages.append({"role": h.role, "content": h.content})

    messages.append({"role": "user", "content": user_message})

    all_citations: List[ChatCitation] = []
    tools_executed: List[Dict[str, Any]] = []
    turn_count = 0
    final_content = ""

    try:
        while turn_count < MAX_REACT_TURNS:
            turn_count += 1
            response = await chat_completion_with_fallback(
                messages=messages,
                tools=CHAT_TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1,
            )

            choice = response.choices[0]
            msg = choice.message

            # Check if LLM requested tool execution
            if msg.tool_calls:
                # Append assistant tool call message to history
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}

                    # AC-10.4: Sensitive action confirmation check
                    if fn_name in ("book_appointment", "cancel_appointment"):
                        desc = f"Book consultation with doctor {args.get('doctor_id', '')} at {args.get('scheduled_at', '')}" if fn_name == "book_appointment" else f"Cancel appointment {args.get('appointment_id', '')}"
                        pending_action = ActionConfirmation(
                            action_type=fn_name,
                            parameters=args,
                            description=desc,
                        )
                        confirm_prompt = (
                            f"I am ready to { 'book' if fn_name == 'book_appointment' else 'cancel' } this appointment.\n\n"
                            f"**Action Summary:** {desc}\n\n"
                            "Please click **Confirm** below to finalize this change."
                        )
                        return ChatTurnResponse(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=confirm_prompt,
                            is_emergency=False,
                            requires_confirmation=True,
                            pending_action=pending_action,
                            citations=all_citations,
                            tool_calls_executed=tools_executed,
                            model_used=PRIMARY_MODEL,
                        )

                    tool_output, tool_citations = execute_chat_tool(context, fn_name, args)
                    all_citations.extend(tool_citations)
                    tools_executed.append({"tool": fn_name, "args": args, "status": "success"})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_output, default=str),
                    })

                # Continue next ReAct turn
                continue
            else:
                final_content = msg.content or ""
                break

    except Exception as e:
        logger.error(f"Error during conversational turn: {e}. Falling back to grounded response.")
        content, is_em, req_conf, pending, citations, tools_done = generate_grounded_fallback(context, user_message)
        return ChatTurnResponse(
            conversation_id=conversation_id,
            role="assistant",
            content=clean_mojibake(content),
            is_emergency=is_em,
            requires_confirmation=req_conf,
            pending_action=pending,
            citations=citations,
            tool_calls_executed=tools_done,
            model_used="grounded-deterministic-fallback",
        )

    # 6. Audit Logging (Zero-PHI)
    audit_event(
        event_type="CHAT_TURN_COMPLETED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="conversational_ai",
        target_id=conversation_id,
        action="TURN_COMPLETED",
        status="SUCCESS",
    )

    return ChatTurnResponse(
        conversation_id=conversation_id,
        role="assistant",
        content=clean_mojibake(final_content),
        is_emergency=False,
        requires_confirmation=False,
        pending_action=None,
        citations=all_citations,
        tool_calls_executed=tools_executed,
        model_used=PRIMARY_MODEL,
    )
