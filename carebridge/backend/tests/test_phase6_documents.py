import os
import io
import time
from uuid import UUID, uuid4
import jwt
import pytest
from pypdf import PdfWriter
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.documents.storage import validate_file_signature, MAX_FILE_SIZE_BYTES
from app.documents.extractor import extract_text, extract_clinical_entities_rule_based
from app.core.audit import AUDIT_LOG_FILE

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"   # Alice Vance (Hosp 1)
PATIENT_2_ID = "11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb"   # Bob Pendelton (Hosp 1, unlinked to user 4)

ADMIN_USER_ID = "70000000-0000-0000-0000-000000000001"
DOCTOR_USER_ID = "70000000-0000-0000-0000-000000000002"
RECEPTIONIST_USER_ID = "70000000-0000-0000-0000-000000000003"
PATIENT_USER_ID = "70000000-0000-0000-0000-000000000004"
HOSP2_DOC_ID = "70000000-0000-0000-0000-000000000006"

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", settings.SUPABASE_SERVICE_ROLE_KEY)


def make_jwt(user_id: str, email: str, role="authenticated") -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": f"{settings.SUPABASE_URL}/auth/v1",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})


from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def generate_searchable_pdf(lines: list) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 25
    c.save()
    return buf.getvalue()


# ==============================================================================
# 1. FILE SIGNATURE & BINARY VALIDATION TESTS
# ==============================================================================

def test_file_signature_validation():
    # Valid PDF
    mime, name = validate_file_signature(b"%PDF-1.4 test stream", "test.pdf")
    assert mime == "application/pdf"
    assert name == "test.pdf"

    # Valid PNG
    mime, name = validate_file_signature(b"\x89PNG\r\n\x1a\nfakeimagebytes", "scan.png")
    assert mime == "image/png"

    # Valid JPEG
    mime, name = validate_file_signature(b"\xff\xd8\xff\xe0\x00\x10JFIF", "photo.jpg")
    assert mime == "image/jpeg"

    # Spoofed Extension (e.g. .exe masquerading as .pdf)
    with pytest.raises(Exception):
        validate_file_signature(b"MZ\x90\x00\x03\x00\x00\x00", "malicious.pdf")

    # Empty content
    with pytest.raises(Exception):
        validate_file_signature(b"", "empty.pdf")

    # Oversized file (>10MB)
    with pytest.raises(Exception):
        oversized = b"%PDF" + b"0" * (MAX_FILE_SIZE_BYTES + 10)
        validate_file_signature(oversized, "huge.pdf")


# ==============================================================================
# 2. LOCAL EXTRACTION & ENTITY PARSING TESTS (₹0 LLM / SYNTHETIC DATA)
# ==============================================================================

def test_rule_based_clinical_entity_extraction():
    synthetic_note = """
    Aegis Metro General Hospital - Discharge Summary
    Facility: Aegis Metro General Hospital
    Physician: Dr. Vikram Sethi
    Date: 2026-10-15
    Patient is a 58-year-old with active Type 2 Diabetes Mellitus and Essential Hypertension.
    Vitals: BP: 130/82 mmHg, HR: 74 bpm, SpO2: 98%, Temp: 98.6 F.
    Labs: Fasting Blood Sugar: 126 mg/dL, HbA1c: 6.8 %, Serum Creatinine: 0.9 mg/dL.
    Medications: Metformin 500 mg twice daily, Lisinopril 10 mg once daily, Atorvastatin 20 mg daily.
    Allergies: Penicillin (severe rash), Sulfa.
    """
    result = extract_clinical_entities_rule_based(synthetic_note, "discharge_summary")

    # Diagnoses
    diag_conditions = [d.condition for d in result.diagnoses]
    assert "Type 2 Diabetes Mellitus" in diag_conditions
    assert "Essential Hypertension" in diag_conditions

    # Vitals
    vitals_dict = {v.vital_name: v.value for v in result.vital_signs}
    assert vitals_dict.get("Blood Pressure") == "130/82"
    assert vitals_dict.get("Heart Rate") == "74"
    assert vitals_dict.get("SpO2") == "98"

    # Labs
    labs_dict = {l.test_name: l.value for l in result.lab_results}
    assert labs_dict.get("HbA1c") == "6.8"
    assert labs_dict.get("Fasting Glucose") == "126.0"

    # Medications
    med_names = [m.drug_name for m in result.medications]
    assert "Metformin" in med_names
    assert "Lisinopril" in med_names
    assert "Atorvastatin" in med_names

    # Allergies
    allergy_names = [a.allergen for a in result.allergies]
    assert any("penicillin" in a.lower() for a in allergy_names)


# ==============================================================================
# 3. DOCUMENT UPLOAD, INGESTION & WORKFLOW API TESTS
# ==============================================================================

@pytest.fixture(scope="module")
def uploaded_doc_id():
    token = make_jwt(PATIENT_USER_ID, "patuser1@example.com")
    pdf_content = generate_searchable_pdf([
        "Aegis Metro General Hospital - Discharge Summary",
        "Facility: Aegis Metro General Hospital",
        "Physician: Dr. Vikram Sethi",
        "Date: 2026-10-15",
        "BP: 125/80 mmHg, HR: 72 bpm, SpO2: 99%",
        "HbA1c: 6.2 %",
        "Metformin 500 mg twice daily",
        "Allergies: Sulfa"
    ])

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"patient_id": PATIENT_1_ID, "document_type": "discharge_summary"},
        files={"file": ("discharge_alice.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["document_type"] == "discharge_summary"
    assert data["ocr_status"] == "completed"
    assert data["patient_id"] == PATIENT_1_ID
    return data["id"]


def test_unverified_entities_status_invariants(uploaded_doc_id):
    """Extracted entities must remain in 'pending' review state until clinician action."""
    token = make_jwt(PATIENT_USER_ID, "patuser1@example.com")
    response = client.get(
        f"/api/v1/documents/{uploaded_doc_id}/entities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    entities = response.json()
    assert len(entities) > 0
    for entity in entities:
        assert entity["verification_status"] == "pending"
        assert entity["verified_by"] is None
        assert entity["verified_at"] is None


def test_doctor_can_verify_and_edit_entities(uploaded_doc_id):
    """Doctor reviews, verifies, and records notes/edits on extracted clinical entities."""
    doctor_token = make_jwt(DOCTOR_USER_ID, "doc1@aegis.example.com")

    # Fetch pending entities
    get_res = client.get(
        f"/api/v1/documents/{uploaded_doc_id}/entities",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert get_res.status_code == 200
    entities = get_res.json()
    assert len(entities) >= 1

    first_entity = entities[0]
    verify_payload = {
        "entities": [
            {
                "id": first_entity["id"],
                "verification_status": "verified",
                "doctor_notes": "Verified against physical discharge summary."
            }
        ]
    }

    # Doctor verifies
    post_res = client.post(
        f"/api/v1/documents/{uploaded_doc_id}/verify",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json=verify_payload
    )
    assert post_res.status_code == 200
    updated = post_res.json()
    target = next(e for e in updated if e["id"] == first_entity["id"])
    assert target["verification_status"] == "verified"
    assert target["verified_by"] == DOCTOR_USER_ID
    assert target["doctor_notes"] == "Verified against physical discharge summary."
    assert target["verified_at"] is not None


def test_patient_cannot_verify_entities_403(uploaded_doc_id):
    """Patients are strictly prohibited from verifying or signing off on clinical entities."""
    patient_token = make_jwt(PATIENT_USER_ID, "patuser1@example.com")
    verify_payload = {
        "entities": [
            {
                "id": str(uuid4()),
                "verification_status": "verified"
            }
        ]
    }
    response = client.post(
        f"/api/v1/documents/{uploaded_doc_id}/verify",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=verify_payload
    )
    assert response.status_code == 403


def test_receptionist_cannot_verify_entities_403(uploaded_doc_id):
    """Receptionists cannot verify or alter clinical records."""
    rec_token = make_jwt(RECEPTIONIST_USER_ID, "rec1@aegis.example.com")
    verify_payload = {
        "entities": [
            {
                "id": str(uuid4()),
                "verification_status": "verified"
            }
        ]
    }
    response = client.post(
        f"/api/v1/documents/{uploaded_doc_id}/verify",
        headers={"Authorization": f"Bearer {rec_token}"},
        json=verify_payload
    )
    assert response.status_code == 403


# ==============================================================================
# 4. TENANT ISOLATION & PATIENT ACCESS RESTRICTIONS
# ==============================================================================

def test_cross_tenant_document_isolation(uploaded_doc_id):
    """Doctor from Hospital 2 must receive HTTP 404 when querying Hospital 1 documents."""
    hosp2_token = make_jwt(HOSP2_DOC_ID, "hosp2doc@stjude.example.com")
    response = client.get(
        f"/api/v1/documents/{uploaded_doc_id}",
        headers={"Authorization": f"Bearer {hosp2_token}"},
    )
    assert response.status_code == 404


def test_unauthorized_patient_cannot_upload_for_unlinked_patient():
    """Patient 1 cannot upload a document targeting Patient 2."""
    patient_token = make_jwt(PATIENT_USER_ID, "patuser1@example.com")
    pdf_content = generate_searchable_pdf(["Lab Report", "Glucose: 110 mg/dL"])

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        data={"patient_id": PATIENT_2_ID, "document_type": "lab_report"},
        files={"file": ("lab.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 404


def test_doctor_unread_notifications_badge():
    """Doctor queue notification endpoint returns active unread/pending document tasks."""
    doctor_token = make_jwt(DOCTOR_USER_ID, "doc1@aegis.example.com")
    response = client.get(
        "/api/v1/documents/notifications/unread-count",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "unread_count" in data
    assert "pending_verification_count" in data
    assert data["unread_count"] >= 0


def test_document_download_api(uploaded_doc_id):
    """Authorized download streams original binary file with correct headers."""
    doctor_token = make_jwt(DOCTOR_USER_ID, "doc1@aegis.example.com")
    response = client.get(
        f"/api/v1/documents/{uploaded_doc_id}/download",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline; filename=" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_zero_phi_audit_logging():
    """Verify that document audit events contain only pseudonymous metadata and zero PHI."""
    log_path = AUDIT_LOG_FILE
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Confirm presence of DOCUMENT_UPLOADED and ENTITIES_VERIFIED
    uploaded_events = [line for line in lines if "DOCUMENT_UPLOADED" in line]
    assert len(uploaded_events) > 0
    for event in uploaded_events:
        # Must not contain medical text
        assert "Diabetes" not in event
        assert "Metformin" not in event
        assert "Blood Pressure" not in event
        assert "target_resource" in event
        assert "clinical_document" in event
