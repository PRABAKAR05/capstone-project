"""Optional Groq-powered Clinical Narrative Reconciler.

Tested exclusively with synthetic clinical data in accordance with Phase 7 governance:
- Advisory only.
- Never treated as verified clinical advice.
- Provides optional natural-language synthesis for clinician review.
"""

import json
from typing import Dict, Any, Optional
from groq import Groq
from app.core.config import settings


DISCLAIMER = (
    "NOTICE: Advisory synthetic clinical decision assistance only. "
    "Do NOT use as verified medical advice. Final orders require explicit clinician judgement."
)


def reconcile_conflict_narrative_synthetic(
    conflict_title: str,
    clinical_summary: str,
    patient_friendly_summary: str,
) -> Dict[str, Any]:
    """Generates an advisory synthesis for clinician review on synthetic test scenarios."""
    if not settings.GROQ_API_KEY:
        return {
            "disclaimer": DISCLAIMER,
            "synthetic_reconciliation_note": "Groq API key not configured. Using deterministic rule summary.",
            "status": "deterministic_fallback",
        }

    prompt = f"""You are an advisory clinical decision support assistant. You are evaluating a SYNTHETIC medical conflict:
Conflict Title: {conflict_title}
Clinical Summary: {clinical_summary}
Patient Phrasing: {patient_friendly_summary}

Provide a concise, neutral 2-sentence clinical review guideline for the attending physician.
Do NOT give definitive prescriptive orders. Output in JSON format with fields:
"clinical_considerations" (string) and "suggested_monitoring" (string)."""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"{DISCLAIMER} Output strictly valid JSON without conversational wrapper.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data["disclaimer"] = DISCLAIMER
        data["status"] = "ai_assisted_synthetic"
        return data
    except Exception as e:
        return {
            "disclaimer": DISCLAIMER,
            "synthetic_reconciliation_note": f"Rule-based fallback active. Details: {str(e)}",
            "status": "fallback",
        }
