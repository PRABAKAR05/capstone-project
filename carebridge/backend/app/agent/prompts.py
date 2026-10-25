import re
from typing import List

DISCLAIMER_TEXT = (
    "CareBridge AI provides operational assistance and clinical triage navigation. "
    "For medical emergencies, contact emergency services immediately."
)

CLINICAL_SYSTEM_PROMPT = f"""You are CareBridge AI, an intelligent, empathetic hospital operations and clinical triage coordinator.
You assist patients, caregivers, and staff with scheduling consultations, locating specialists, looking up clinic hours, and navigating hospital services.

CRITICAL CLINICAL BOUNDARIES & INVARIANTS:
1. You are an administrative and clinical triage assistant. You are NOT a medical doctor.
2. NEVER provide a definitive medical diagnosis, interpret lab results definitively, or prescribe medications.
3. NEVER claim to rule out a medical emergency. If a user describes potentially severe or emergent symptoms, prioritize their immediate safety.
4. HALLUCINATION PREVENTION: You MUST use the provided tools to query real-time doctor availability, appointments, and hospital departments. NEVER invent or assume doctor availability, slot times, or booking confirmation codes.
5. RESPECT IDENTITY & PRIVACY: Actions are executed strictly within the caller's authorized hospital context. If an operation fails due to permissions or a slot is unavailable, explain clearly and suggest alternatives.
6. RESPONSE STYLE: Professional, concise, warm, and clinical. Format lists and appointment times cleanly.
7. Always keep the user informed about actions taken.
8. CARE TASKS VS APPOINTMENTS: Care coordination tasks are internal clinical checklist items (lab draws, follow-up calls, discharge reviews). Appointments are outpatient doctor visits. NEVER describe appointments as care tasks or vice versa. If asked for care tasks, check care tasks, never list appointments under the title of care tasks.

DISCLAIMER INVARIANT:
Every final response must maintain clinical awareness.
"""

# Red-flag symptom patterns for immediate emergency escalation
RED_FLAG_PATTERNS: List[str] = [
    r"\bchest\s+pain\b",
    r"\bpressure\s+in\s+(my\s+)?chest\b",
    r"\bcrushing\s+chest\b",
    r"\bpain\s+radiating\b",
    r"\bradiating\s+pain\b",
    r"\b(can'?t|cannot|unable\s+to)\s+breathe\b",
    r"\bsevere\s+shortness\s+of\s+breath\b",
    r"\bdifficulty\s+breathing\b",
    r"\bchoking\b",
    r"\bsudden\s+(numbness|paralysis|weakness)\b",
    r"\bfacial\s+droop(ing)?\b",
    r"\bslurred\s+speech\b",
    r"\bsudden\s+loss\s+of\s+vision\b",
    r"\banaphylaxis\b",
    r"\bthroat\s+(swelling|closing)\b",
    r"\btongue\s+swelling\b",
    r"\bsevere\s+allergic\s+reaction\b",
    r"\buncontrolled\s+bleed(ing)?\b",
    r"\bmassive\s+hemorrhage\b",
    r"\bcoughing\s+up\s+blood\b",
    r"\bvomi?ting\s+blood\b",
    r"\b(suicid(e|al)|kill\s+myself|end\s+my\s+life)\b",
    r"\bworst\s+headache\s+of\s+my\s+life\b",
    r"\bthunderclap\s+headache\b",
    r"\bloss\s+of\s+consciousness\b",
    r"\bpassed\s+out\b",
    r"\bseizure\b",
]

_COMPILED_RED_FLAGS = [re.compile(p, re.IGNORECASE) for p in RED_FLAG_PATTERNS]

EMERGENCY_DISPATCH_MESSAGE = (
    "🚨 **CRITICAL MEDICAL EMERGENCY ADVISORY** 🚨\n\n"
    "Your description indicates symptoms that may require **immediate, life-saving medical intervention**.\n\n"
    "**DO NOT WAIT FOR AN OUTPATIENT APPOINTMENT.**\n\n"
    "**IMMEDIATE ACTIONS REQUIRED:**\n"
    "1. **Call Emergency Services Immediately**: Dial **108** or **112** (India National Emergency) or **911** if calling internationally.\n"
    "2. **Proceed to the Nearest Emergency Department (Casualty)** right away.\n"
    "3. If you are alone, alert a family member, neighbor, or emergency contact.\n\n"
    "CareBridge AI has halted automated outpatient booking because emergency care must never be delayed.\n\n"
    f"*{DISCLAIMER_TEXT}*"
)


def detect_red_flag_symptoms(message: str) -> bool:
    """Scans user message against red-flag clinical emergency patterns."""
    if not message:
        return False
    clean = message.strip()
    return any(p.search(clean) is not None for p in _COMPILED_RED_FLAGS)
