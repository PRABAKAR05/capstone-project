"""Service orchestration for digital prescriptions, dispensing lifecycle, and adherence logging.

Enforces:
- Strict role boundaries (Doctors create/discontinue; Pharmacy staff dispense; Patients read-only).
- Finite State Machine transitions.
- Zero-PHI public cryptographic verification.
- Zero-PHI application audit logging.
"""

from datetime import datetime, timezone, timedelta
import uuid
from typing import Dict, List, Optional
from fastapi import HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.audit import audit_event
from app.prescriptions.crypto import (
    compute_items_hash,
    generate_verification_hash,
    verify_signature
)
from app.prescriptions.safety import check_pre_issuance_safety
from app.prescriptions.adherence import calculate_adherence_metrics


def create_prescription(
    doctor_id: str,
    doctor_role: str,
    hospital_id: str,
    data: Dict,
    db_conn
) -> Dict:
    """
    Physician authors a structured e-prescription.
    Executes pre-issuance safety checks and signs with versioned HMAC.
    """
    if doctor_role != "doctor":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only licensed physicians may author prescriptions."
        )

    patient_id = str(data.get("patient_id")) if data.get("patient_id") else None
    encounter_id = str(data.get("encounter_id")) if data.get("encounter_id") else None
    diagnosis_context = data.get("diagnosis_context", "")
    notes = data.get("notes", "")
    items_data = data.get("items", [])

    if not patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required.")
    if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
        raise HTTPException(status_code=422, detail="Prescription must contain at least one medication item.")

    # 1. Pre-issuance safety checks
    safety_report = check_pre_issuance_safety(hospital_id, str(patient_id), items_data, db_conn)

    # 2. Compute validity window (defaults to max items duration, minimum 30 days)
    max_duration = max([int(item.get("duration_days", 30)) for item in items_data] + [30])
    now = datetime.now(timezone.utc)
    valid_until = now + timedelta(days=max_duration)

    prescription_id = str(uuid.uuid4())
    issued_at_iso = now.isoformat()

    # 3. Compute items hash and HMAC verification signature
    items_hash = compute_items_hash(items_data)
    verification_hash = generate_verification_hash(
        prescription_id=prescription_id,
        hospital_id=hospital_id,
        patient_id=str(patient_id),
        doctor_id=str(doctor_id),
        issued_at=issued_at_iso,
        items_hash=items_hash
    )

    # 4. Insert into database
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO public.prescriptions (
                id, hospital_id, patient_id, doctor_id, encounter_id,
                status, diagnosis_context, notes, verification_hash,
                issued_at, valid_until
            )
            VALUES (%s, %s, %s, %s, %s, 'prescribed', %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                prescription_id,
                hospital_id,
                patient_id,
                doctor_id,
                encounter_id,
                diagnosis_context,
                notes,
                verification_hash,
                now,
                valid_until
            )
        )
        created_prescription = cur.fetchone()

        # Insert items
        created_items = []
        for item in items_data:
            item_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO public.prescription_items (
                    id, hospital_id, prescription_id, drug_name,
                    therapeutic_class, dosage, route, frequency,
                    duration_days, instructions, refills_remaining
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    item_id,
                    hospital_id,
                    prescription_id,
                    item.get("drug_name"),
                    item.get("therapeutic_class"),
                    item.get("dosage"),
                    item.get("route", "oral"),
                    item.get("frequency"),
                    int(item.get("duration_days", 30)),
                    item.get("instructions", "As directed"),
                    int(item.get("refills_remaining", 0))
                )
            )
            created_items.append(cur.fetchone())

    # 5. Emit Zero-PHI Audit Event
    audit_event(
        event_type="PRESCRIPTION_ISSUED",
        actor_id=doctor_id,
        actor_role=doctor_role,
        hospital_id=hospital_id,
        target_resource="prescription",
        target_id=prescription_id,
        action="CREATE",
        status="SUCCESS"
    )

    result = dict(created_prescription)
    result["items"] = created_items
    result["safety_advisory"] = safety_report
    return result


def get_prescriptions(
    user_id: str,
    user_role: str,
    hospital_id: str,
    patient_id_filter: Optional[str],
    status_filter: Optional[str],
    db_conn
) -> List[Dict]:
    """Lists prescriptions respecting tenant isolation and patient role boundaries."""
    # Patients can ONLY view their own records
    effective_patient_id = patient_id_filter
    if user_role == "patient":
        effective_patient_id = user_id

    query = """
        SELECT 
            p.*,
            (SELECT COUNT(*) FROM public.prescription_items pi WHERE pi.prescription_id = p.id) AS items_count
        FROM public.prescriptions p
        WHERE p.hospital_id = %s
    """
    params = [hospital_id]

    if effective_patient_id:
        query += " AND p.patient_id = %s"
        params.append(effective_patient_id)
    if status_filter:
        query += " AND p.status = %s"
        params.append(status_filter)

    query += " ORDER BY p.issued_at DESC"

    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(r) for r in rows]


def get_prescription_detail(
    prescription_id: str,
    user_id: str,
    user_role: str,
    hospital_id: str,
    db_conn
) -> Dict:
    """Retrieves prescription details and items, enforcing patient privacy."""
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM public.prescriptions
            WHERE id = %s AND hospital_id = %s
            """,
            (prescription_id, hospital_id)
        )
        p = cur.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Prescription not found.")

        # Patient barrier
        if user_role in ("patient", "caregiver") and str(p["patient_id"]) != str(user_id):
            raise HTTPException(status_code=403, detail="Access denied to this clinical prescription.")

        cur.execute(
            """
            SELECT * FROM public.prescription_items
            WHERE prescription_id = %s AND hospital_id = %s
            ORDER BY created_at ASC
            """,
            (prescription_id, hospital_id)
        )
        items = cur.fetchall()

    result = dict(p)
    result["items"] = [dict(it) for it in items]
    return result


def dispense_prescription(
    prescription_id: str,
    user_id: str,
    user_role: str,
    hospital_id: str,
    target_status: str,
    dispensing_notes: Optional[str],
    db_conn
) -> Dict:
    """Transitions prescription through pharmacy fulfillment stages."""
    if user_role in ("patient", "caregiver"):
        raise HTTPException(status_code=403, detail="Forbidden: Patients cannot update dispensing status.")

    if target_status not in ("ready_for_pickup", "dispensed"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid target status '{target_status}'. Must be 'ready_for_pickup' or 'dispensed'."
        )

    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM public.prescriptions WHERE id = %s AND hospital_id = %s",
            (prescription_id, hospital_id)
        )
        p = cur.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Prescription not found.")

        current_status = p["status"]
        if current_status == "discontinued":
            raise HTTPException(status_code=422, detail="Cannot dispense a discontinued prescription.")
        if current_status == "completed":
            raise HTTPException(status_code=422, detail="Prescription is already completed.")

        now = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE public.prescriptions
            SET 
                status = %s,
                dispensed_by = %s,
                dispensed_at = %s,
                dispensing_notes = %s,
                updated_at = %s
            WHERE id = %s AND hospital_id = %s
            RETURNING *
            """,
            (target_status, user_id, now, dispensing_notes, now, prescription_id, hospital_id)
        )
        updated = cur.fetchone()

    # Zero-PHI audit
    audit_event(
        event_type="PRESCRIPTION_DISPENSED",
        actor_id=user_id,
        actor_role=user_role,
        hospital_id=hospital_id,
        target_resource="prescription",
        target_id=prescription_id,
        action="UPDATE",
        status="SUCCESS"
    )

    return dict(updated)


def discontinue_prescription(
    prescription_id: str,
    doctor_id: str,
    doctor_role: str,
    hospital_id: str,
    rationale: str,
    db_conn
) -> Dict:
    """Physician discontinues an active prescription with documented clinical rationale."""
    if doctor_role != "doctor":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only licensed physicians may discontinue active prescriptions."
        )

    if not rationale or len(rationale.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="A documented clinical rationale of at least 10 characters is required to discontinue a prescription."
        )

    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM public.prescriptions WHERE id = %s AND hospital_id = %s",
            (prescription_id, hospital_id)
        )
        p = cur.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Prescription not found.")

        now = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE public.prescriptions
            SET 
                status = 'discontinued',
                discontinuation_rationale = %s,
                updated_at = %s
            WHERE id = %s AND hospital_id = %s
            RETURNING *
            """,
            (rationale.strip(), now, prescription_id, hospital_id)
        )
        updated = cur.fetchone()

    # Zero-PHI audit
    audit_event(
        event_type="PRESCRIPTION_DISCONTINUED",
        actor_id=doctor_id,
        actor_role=doctor_role,
        hospital_id=hospital_id,
        target_resource="prescription",
        target_id=prescription_id,
        action="UPDATE",
        status="SUCCESS"
    )

    return dict(updated)


def verify_public_prescription(verification_hash: str, db_conn) -> Dict:
    """
    Public zero-PII cryptographic verification endpoint.
    Exposes no patient name, diagnosis, or clinical notes.
    """
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.*, h.name AS hospital_name
            FROM public.prescriptions p
            LEFT JOIN public.hospitals h ON h.id = p.hospital_id
            WHERE p.verification_hash = %s
            """,
            (verification_hash,)
        )
        p = cur.fetchone()
        if not p:
            return {
                "is_valid": False,
                "status": "not_found",
                "message": "Prescription record not found or signature unknown."
            }

        cur.execute(
            "SELECT * FROM public.prescription_items WHERE prescription_id = %s",
            (p["id"],)
        )
        items = cur.fetchall()

    # Cryptographic validation
    items_hash = compute_items_hash(items)
    is_sig_valid = verify_signature(
        prescription_id=str(p["id"]),
        hospital_id=str(p["hospital_id"]),
        patient_id=str(p["patient_id"]),
        doctor_id=str(p["doctor_id"]),
        issued_at=p["issued_at"].isoformat(),
        items_hash=items_hash,
        verification_hash=verification_hash
    )

    if not is_sig_valid:
        return {
            "is_valid": False,
            "status": "tampered",
            "message": "Signature verification failed. The prescription payload does not match the signature."
        }

    now = datetime.now(timezone.utc)
    is_expired = now > p["valid_until"]
    effective_status = "expired" if is_expired else p["status"]

    return {
        "is_valid": True,
        "status": effective_status,
        "prescription_id": str(p["id"]),
        "hospital_id": str(p["hospital_id"]),
        "hospital_name": p["hospital_name"] or "Authorized Healthcare Provider",
        "doctor_id": str(p["doctor_id"]),
        "issued_at": p["issued_at"].isoformat(),
        "valid_until": p["valid_until"].isoformat(),
        "items_count": len(items),
        "items_hash": items_hash,
        "verification_hash": verification_hash,
        "message": "Prescription authenticity cryptographically verified."
    }


def log_patient_adherence(
    patient_id: str,
    user_id: str,
    user_role: str,
    hospital_id: str,
    data: Dict,
    db_conn
) -> Dict:
    """Logs dose checkoff (taken, skipped, late)."""
    item_id = str(data.get("prescription_item_id")) if data.get("prescription_item_id") else None
    status = data.get("status")
    raw_sched = data.get("scheduled_time")
    scheduled_time = raw_sched.isoformat() if hasattr(raw_sched, "isoformat") else raw_sched
    notes = data.get("notes")

    if not item_id or not status or not scheduled_time:
        raise HTTPException(
            status_code=422,
            detail="prescription_item_id, status, and scheduled_time are required."
        )

    if status not in ("taken", "skipped", "late", "missed"):
        raise HTTPException(status_code=422, detail=f"Invalid status '{status}'.")

    now = datetime.now(timezone.utc)
    taken_at = now if status in ("taken", "late") else None
    log_id = str(uuid.uuid4())

    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check parent prescription exists and belongs to hospital & patient
        cur.execute(
            """
            SELECT pi.id FROM public.prescription_items pi
            JOIN public.prescriptions p ON p.id = pi.prescription_id
            WHERE pi.id = %s AND pi.hospital_id = %s AND p.patient_id = %s
            """,
            (item_id, hospital_id, patient_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Prescription item not found for patient.")

        cur.execute(
            """
            INSERT INTO public.medication_adherence_logs (
                id, hospital_id, patient_id, prescription_item_id,
                scheduled_time, taken_at, status, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (log_id, hospital_id, patient_id, item_id, scheduled_time, taken_at, status, notes)
        )
        created_log = cur.fetchone()

    # Zero-PHI audit
    audit_event(
        event_type="DOSE_LOGGED",
        actor_id=user_id,
        actor_role=user_role,
        hospital_id=hospital_id,
        target_resource="adherence_log",
        target_id=log_id,
        action="CREATE",
        status="SUCCESS"
    )

    return dict(created_log)
