import re
from typing import List

DISCLAIMER_TEXT = (
    "CareBridge AI provides hospital operational navigation and care coordination assistance. "
    "For emergency medical situations, immediately contact emergency services (112 / 108)."
)

CONVERSATIONAL_SYSTEM_PROMPT = f"""You are CareBridge AI, a helpful, safe, and hospital-aware conversational assistant.
You assist patients, caregivers, and hospital staff with navigating hospital workflows, reviewing appointments, checking care tasks, understanding document processing status, and reviewing existing prescriptions.

CRITICAL OPERATIONAL & CLINICAL BOUNDARIES:
1. ROLE & IDENTITY: You are an administrative and care navigation assistant. You are NOT a medical doctor.
2. NO AUTONOMOUS CLINICAL DECISIONS: NEVER diagnose illness, formulate treatments, prescribe drugs, or recommend dosage changes.
3. GROUNDING IN HOSPITAL DATA: You MUST query real-time data using the provided tools for doctors, appointments, documents, care tasks, and prescriptions. NEVER invent doctors, slot times, document statuses, or medications.
4. SAFE CONFIRMATION FOR ACTIONS: Consequential actions (booking or cancelling an appointment) require explicit user confirmation. State the action details clearly before asking for confirmation.
5. SENSITIVE DATA MASKING: When assisting patients or caregivers, NEVER reveal internal clinical staff notes or administrative logs.
6. MEDICATION SAFETY: You may explain the status, frequency, and instructions of an EXISTING verified prescription. You must NEVER calculate new dosages, suggest altering a dose, or advise on missed dose adjustments.
7. EMERGENCY AWARENESS: If a user mentions emergent symptoms, prioritize their life safety above all administrative tasks.
8. RESPONSE STYLE: Professional, empathetic, concise, and structured. Use bullet points and markdown formatting where helpful.

DISCLAIMER:
{DISCLAIMER_TEXT}
"""

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

DOSAGE_INQUIRY_PATTERNS: List[str] = [
    r"\bhow\s+much\s+(dose|dosage|mg|tablets?|pills?)\b.*(take|have|start|increase|decrease)",
    r"\bhow\s+much\b.*(dose|dosage|mg|tablets?|pills?).*\b(should|can|do)\s+i\s+(take|have|start)\b",
    r"\bcan\s+i\s+(double|triple|increase|decrease|change|halve|stop)\s+(my\s+)?(dose|dosage|medication|medicine|tablets?)\b",
    r"\bwhat\s+(dose|dosage)\s+should\s+i\s+(take|start|use)\b",
    r"\bshould\s+i\s+take\s+\d+(\.\d+)?\s*(mg|mcg|ml|g)\b",
    r"\bprescribe\s+(me\s+)?(some\s+)?(antibiotics|painkillers|tablets|medication)\b",
    r"\bcan\s+you\s+prescribe\b",
    r"\bgive\s+me\s+a\s+prescription\b",
    r"\bmissed\s+(a\s+)?dose.*take\s+double\b",
    r"\bhow\s+many\s+(mg|tablets?|pills?)\b.*(should|can|do)\s+i\s+take\b",
]

_COMPILED_DOSAGE_INQUIRIES = [re.compile(p, re.IGNORECASE) for p in DOSAGE_INQUIRY_PATTERNS]

EMERGENCY_DISPATCH_MESSAGE = (
    "🚨 **CRITICAL MEDICAL EMERGENCY ADVISORY** 🚨\n\n"
    "Your description indicates symptoms that may require **immediate, life-saving medical intervention**.\n\n"
    "**DO NOT WAIT FOR AN OUTPATIENT APPOINTMENT.**\n\n"
    "**IMMEDIATE ACTIONS REQUIRED:**\n"
    "1. **Call Emergency Services Immediately**: Dial **112** or **108** (India National Emergency) or your local emergency number.\n"
    "2. **Proceed to the Nearest Emergency Department (Casualty)** right away.\n"
    "3. If you are alone, alert a family member, neighbor, or emergency contact.\n\n"
    "CareBridge AI has prioritized this advisory because emergency care must never be delayed.\n\n"
    f"*{DISCLAIMER_TEXT}*"
)

MEDICATION_DOSAGE_REFUSAL_MESSAGE = (
    "⚠️ **Clinical Safety Notice: Medication Dosages Cannot Be Prescribed or Adjusted by AI**\n\n"
    "CareBridge AI is strictly prohibited from guessing, adjusting, or recommending medication dosages. "
    "Altering doses or taking unverified quantities without clinical evaluation presents severe risks of adverse drug interactions, organ toxicity, or therapeutic failure.\n\n"
    "**Next Steps:**\n"
    "- Please contact your prescribing physician or consult a licensed hospital pharmacist to verify or adjust your dosage.\n"
    "- You can view your existing prescribed instructions in the **Prescriptions** section of your patient portal.\n"
    "- If you are experiencing adverse symptoms or suspect a drug reaction, call **112** / **108** or visit the emergency room immediately.\n\n"
    f"*{DISCLAIMER_TEXT}*"
)


def detect_red_flag_symptoms(message: str) -> bool:
    """Scans user message against red-flag clinical emergency patterns."""
    if not message:
        return False
    clean = message.strip()
    return any(p.search(clean) is not None for p in _COMPILED_RED_FLAGS)


def detect_medication_dosage_query(message: str) -> bool:
    """Scans user message against patterns attempting to elicit dosage guesses or prescription generation."""
    if not message:
        return False
    clean = message.strip()
    return any(p.search(clean) is not None for p in _COMPILED_DOSAGE_INQUIRIES)
