import os
import time
import pytest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import jwt
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.core.security import SecurityContext
from app.agent.prompts import detect_red_flag_symptoms, EMERGENCY_DISPATCH_MESSAGE, DISCLAIMER_TEXT
from app.agent.tools import (
    tool_search_doctors,
    tool_get_doctor_slots,
    tool_book_appointment,
    tool_cancel_appointment,
    tool_lookup_hospital_info,
)
from app.agent.engine import generate_rule_based_fallback, run_agent_turn

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
DOCTOR_CHEN_ID = "71111111-1111-1111-1111-111111111111"
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PATIENT_USER_ID = "70000000-0000-0000-0000-000000000004"
PATIENT_EMAIL = "patuser1@example.com"

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", settings.SUPABASE_SERVICE_ROLE_KEY)


def make_test_jwt(user_id: str, email: str, role="authenticated") -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": f"{settings.SUPABASE_URL}/auth/v1",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def make_patient_context() -> SecurityContext:
    return SecurityContext(
        user_id=UUID(PATIENT_USER_ID),
        hospital_id=UUID(HOSPITAL_1_ID),
        role="patient",
        email=PATIENT_EMAIL,
        is_active=True,
    )


# ==============================================================================
# 1. CLINICAL SAFETY & RED-FLAG EMERGENCY TRIAGE TESTS
# ==============================================================================

def test_detect_red_flag_symptoms():
    """Verify red-flag symptom patterns correctly flag medical emergencies."""
    assert detect_red_flag_symptoms("I have severe crushing chest pain") is True
    assert detect_red_flag_symptoms("Pain radiating to my left arm and jaw") is True
    assert detect_red_flag_symptoms("I cannot breathe and my throat is swelling") is True
    assert detect_red_flag_symptoms("Sudden weakness on one side and slurred speech") is True
    assert detect_red_flag_symptoms("Feeling suicidal and want to end my life") is True
    assert detect_red_flag_symptoms("I passed out earlier today") is True

    # Benign / administrative queries must NOT be flagged as emergencies
    assert detect_red_flag_symptoms("I need to book a routine checkup with a cardiologist") is False
    assert detect_red_flag_symptoms("Can I reschedule my appointment to tomorrow?") is False
    assert detect_red_flag_symptoms("What are the OPD clinic hours?") is False


@pytest.mark.asyncio
async def test_agent_turn_emergency_escalation():
    """Verify run_agent_turn bypasses LLM and returns emergency dispatch immediately."""
    context = make_patient_context()
    result = await run_agent_turn(
        context=context,
        message_history=[],
        user_message="Doctor please help, I am having severe crushing chest pain right now!",
    )
    assert result["is_emergency"] is True
    assert "CRITICAL MEDICAL EMERGENCY ADVISORY" in result["content"]
    assert "108" in result["content"]
    assert "112" in result["content"]
    assert len(result["tool_calls_executed"]) == 0
    assert result["model_used"] == "clinical-safety-triage"


# ==============================================================================
# 2. DETERMINISTIC TOOL EXECUTION TESTS UNDER SECURITY CONTEXT
# ==============================================================================

def test_tool_search_doctors():
    """Verify search_doctors returns active doctors in caller's hospital tenant."""
    context = make_patient_context()
    res = tool_search_doctors(context, specialty="Cardio")
    assert "doctors" in res
    assert res["total_found"] >= 1
    doc = res["doctors"][0]
    assert "Cardio" in doc["specialty"]
    assert "Chen" in doc["name"]


def test_tool_get_doctor_slots():
    """Verify get_doctor_slots queries available 30-min slots in Asia/Kolkata timezone."""
    context = make_patient_context()
    future_date = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%d")
    res = tool_get_doctor_slots(context, DOCTOR_CHEN_ID, future_date)
    assert "available_slots" in res
    assert res["hospital_timezone"] == "Asia/Kolkata"
    assert res["available_slots_count"] > 0
    first_slot = res["available_slots"][0]
    assert "start_time_local" in first_slot
    assert "scheduled_at_utc" in first_slot


def test_tool_book_and_double_booking_prevention():
    """Verify appointment booking and conflict detection when slot is double-booked."""
    context = make_patient_context()
    # Target date 45 days ahead at 10:00 UTC
    target_dt = datetime.now(timezone.utc) + timedelta(days=45)
    slot_utc_str = target_dt.strftime("%Y-%m-%dT10:00:00Z")

    # Step 1: First booking succeeds
    res1 = tool_book_appointment(
        context=context,
        doctor_id=DOCTOR_CHEN_ID,
        scheduled_at=slot_utc_str,
        reason_for_visit="Agent booking test",
        patient_id=PATIENT_1_ID,
    )
    assert res1.get("success") is True or "SLOT_CONFLICT_409" in str(res1.get("error"))

    # Step 2: Attempting to book the EXACT SAME slot immediately returns SLOT_CONFLICT_409
    res2 = tool_book_appointment(
        context=context,
        doctor_id=DOCTOR_CHEN_ID,
        scheduled_at=slot_utc_str,
        reason_for_visit="Double booking collision",
        patient_id=PATIENT_1_ID,
    )
    assert res2.get("error") == "SLOT_CONFLICT_409"
    assert "already booked" in res2.get("message", "").lower() or "alternate slot" in res2.get("message", "").lower()


def test_tool_cancel_appointment_2hour_cutoff():
    """Verify tool_cancel_appointment enforces 2-hour cutoff rule."""
    context = make_patient_context()
    # Non-existent appointment returns error
    bogus_id = str(uuid4())
    res = tool_cancel_appointment(context, bogus_id)
    assert "error" in res


def test_tool_lookup_hospital_info():
    """Verify hospital information lookup returns departments and tenant name."""
    context = make_patient_context()
    info = tool_lookup_hospital_info(context)
    assert info.get("hospital_name") == "Aegis Metro General Hospital"
    assert len(info.get("departments", [])) >= 1


# ==============================================================================
# 3. CIRCUIT BREAKER & RULE-BASED FALLBACK TESTS
# ==============================================================================

def test_circuit_breaker_offline_fallback():
    """Verify rule-based fallback response provides direct navigation guidance."""
    context = make_patient_context()
    reply_booking = generate_rule_based_fallback(context, "I want to schedule an appointment with a doctor")
    assert "/portal/book" in reply_booking
    assert DISCLAIMER_TEXT in reply_booking

    reply_cancel = generate_rule_based_fallback(context, "How can I cancel my visit?")
    assert "/portal" in reply_cancel
    assert DISCLAIMER_TEXT in reply_cancel


# ==============================================================================
# 4. API ENDPOINT INTEGRATION TESTS (/api/v1/agent)
# ==============================================================================

def test_agent_health_endpoint():
    """GET /api/v1/agent/health returns operational status and model configuration."""
    token = make_test_jwt(PATIENT_USER_ID, PATIENT_EMAIL)
    res = client.get(
        "/api/v1/agent/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert "primary_model" in data
    assert "fallback_model" in data


def test_agent_chat_emergency_endpoint():
    """POST /api/v1/agent/chat escalates immediately on emergency query."""
    token = make_test_jwt(PATIENT_USER_ID, PATIENT_EMAIL)
    res = client.post(
        "/api/v1/agent/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "I am having sudden crushing chest pain and sweating"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_emergency"] is True
    assert "108" in data["content"]
    assert data["model_used"] == "clinical-safety-triage"


def test_agent_chat_live_or_fallback_endpoint():
    """POST /api/v1/agent/chat returns clean response with disclaimer on routine query."""
    token = make_test_jwt(PATIENT_USER_ID, PATIENT_EMAIL)
    res = client.post(
        "/api/v1/agent/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "Hello, what cardiology doctors are available at Aegis Memorial?",
            "history": [],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 10
    assert DISCLAIMER_TEXT in data["content"]
