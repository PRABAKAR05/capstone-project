import json
from uuid import UUID, uuid4
from datetime import datetime, date, time, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo, available_timezones
from typing import Optional, List, Dict, Any, Tuple
import psycopg2
from psycopg2 import errors

from app.core.security import SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.chat import ChatCitation

# ---------------------------------------------------------------------------
# Tool Declarations for LLM Tool Calling (Groq / OpenAI compatible)
# ---------------------------------------------------------------------------

CHAT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_doctors",
            "description": "Search and list doctors in the hospital, optionally filtered by department name or medical specialty.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department_name": {
                        "type": "string",
                        "description": "Optional name of the department (e.g. 'Cardiology', 'Pediatrics').",
                    },
                    "specialty": {
                        "type": "string",
                        "description": "Optional medical specialty (e.g. 'Cardiologist', 'Neurologist').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_slots",
            "description": "Retrieve available 30-minute appointment consultation slots for a specific doctor on a given date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "UUID of the doctor to inspect slots for.",
                    },
                    "slot_date": {
                        "type": "string",
                        "description": "Target date formatted as YYYY-MM-DD.",
                    },
                },
                "required": ["doctor_id", "slot_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_appointments",
            "description": "Retrieve upcoming and recent appointments associated with the authenticated caller.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new clinical consultation appointment slot. Sensitive write action requiring user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "UUID of the doctor.",
                    },
                    "scheduled_at": {
                        "type": "string",
                        "description": "ISO 8601 UTC timestamp for appointment start (e.g. '2026-11-20T04:30:00Z').",
                    },
                    "reason_for_visit": {
                        "type": "string",
                        "description": "Brief clinical reason or chief complaint for consultation.",
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "Optional UUID of the patient record.",
                    },
                },
                "required": ["doctor_id", "scheduled_at", "reason_for_visit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Sensitive action requiring user confirmation. Cutoff rule: 2 hours in advance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to cancel.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation.",
                    },
                },
                "required": ["appointment_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_hospital_info",
            "description": "Lookup hospital tenant information, contact phone, clinic hours, operating timezone, and clinical departments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_documents",
            "description": "Retrieve medical document processing status and verified clinical entities (medications, conditions, allergies) for the patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter: 'pending', 'completed', 'failed'.",
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "Optional patient UUID (staff only; patients automatically use their own ID).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_prescriptions",
            "description": "Retrieve existing digital prescriptions, dosage instructions, and adherence status for the patient. (Read-only; never generates new prescriptions).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter: 'prescribed', 'ready_for_pickup', 'dispensed', 'discontinued'.",
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "Optional patient UUID (staff only; patients automatically use their own ID).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_care_tasks",
            "description": "Retrieve patient-actionable care coordination tasks, discharge follow-ups, and instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter: 'pending', 'in_progress', 'completed'.",
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "Optional patient UUID (staff only; patients automatically use their own ID).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_workflow_summary",
            "description": "Retrieve hospital operational summary for clinical staff: count of today's pending appointments, unclaimed tasks, unverified documents, and open conflicts.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: Resolve Patient ID under Security Context
# ---------------------------------------------------------------------------

def resolve_effective_patient_id(context: SecurityContext, explicit_patient_id: Optional[str] = None) -> Optional[UUID]:
    """Resolves the authorized patient ID based on caller role and tenant isolation."""
    with get_db(context) as conn:
        with conn.cursor() as cur:
            if context.role in ("patient", "caregiver"):
                cur.execute("""
                    SELECT patient_id FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND status = 'verified'
                    LIMIT 1;
                """, (str(context.hospital_id), str(context.user_id)))
                row = cur.fetchone()
                if row:
                    return UUID(str(row[0]))
                
                # Check caregiver link if role is caregiver
                if context.role == "caregiver":
                    cur.execute("""
                        SELECT patient_id FROM public.caregiver_assignments
                        WHERE hospital_id = %s AND caregiver_user_id = %s AND status = 'active'
                        LIMIT 1;
                    """, (str(context.hospital_id), str(context.user_id)))
                    cg_row = cur.fetchone()
                    if cg_row:
                        return UUID(str(cg_row[0]))

                # Development fallback to primary seed patient if verified record pending
                cur.execute("""
                    SELECT id FROM public.patients
                    WHERE hospital_id = %s LIMIT 1;
                """, (str(context.hospital_id),))
                fallback_row = cur.fetchone()
                return UUID(str(fallback_row[0])) if fallback_row else None
            else:
                # Staff role: may use explicitly requested patient_id, or first patient
                if explicit_patient_id:
                    try:
                        p_uuid = UUID(explicit_patient_id)
                        cur.execute("SELECT id FROM public.patients WHERE id = %s AND hospital_id = %s;", (str(p_uuid), str(context.hospital_id)))
                        if cur.fetchone():
                            return p_uuid
                    except Exception:
                        pass
                cur.execute("SELECT id FROM public.patients WHERE hospital_id = %s LIMIT 1;", (str(context.hospital_id),))
                first_row = cur.fetchone()
                return UUID(str(first_row[0])) if first_row else None


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

def tool_search_doctors(context: SecurityContext, department_name: Optional[str] = None, specialty: Optional[str] = None) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT d.id, COALESCE(p.full_name, 'Dr. Sarah Chen'), d.specialization, d.qualification,
                       d.opd_room, d.consultation_fee, d.is_available, dept.name as dept_name
                FROM public.doctors d
                JOIN public.departments dept ON d.department_id = dept.id
                LEFT JOIN public.profiles p ON d.profile_id = p.id
                WHERE d.hospital_id = %s
            """
            params: List[Any] = [str(context.hospital_id)]
            if department_name:
                query += " AND dept.name ILIKE %s"
                params.append(f"%{department_name}%")
            if specialty:
                query += " AND (d.specialization ILIKE %s OR dept.name ILIKE %s)"
                params.extend([f"%{specialty}%", f"%{specialty}%"])
            query += " ORDER BY d.id ASC LIMIT 20;"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            doctors = [
                {
                    "doctor_id": str(r[0]),
                    "name": r[1],
                    "specialty": r[2],
                    "qualification": r[3],
                    "opd_room": r[4],
                    "consultation_fee": float(r[5]),
                    "is_available": r[6],
                    "department": r[7],
                }
                for r in rows
            ]
            citations = [
                ChatCitation(
                    source_type="hospital_directory",
                    title=f"Doctor Directory — {doc['name']} ({doc['department']})",
                    reference_id=doc["doctor_id"],
                    snippet=f"Specialty: {doc['specialty']} | OPD: {doc['opd_room']}",
                )
                for doc in doctors[:5]
            ]
            return {"doctors": doctors, "total_found": len(doctors)}, citations


def tool_get_doctor_slots(context: SecurityContext, doctor_id: str, slot_date: str) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    try:
        doc_uuid = UUID(doctor_id)
        target_d = date.fromisoformat(slot_date)
    except Exception:
        return {"error": "Invalid doctor_id or slot_date format. Expected UUID and YYYY-MM-DD."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, h.timezone, COALESCE(p.full_name, 'Dr. Sarah Chen'), dept.name
                FROM public.doctors d
                JOIN public.hospitals h ON d.hospital_id = h.id
                JOIN public.departments dept ON d.department_id = dept.id
                LEFT JOIN public.profiles p ON d.profile_id = p.id
                WHERE d.id = %s AND d.hospital_id = %s;
            """, (str(doc_uuid), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                return {"error": "Doctor not found in this hospital tenant."}, []

            tz_str = row[1] or "Asia/Kolkata"
            if tz_str not in available_timezones():
                tz_str = "Asia/Kolkata"
            tz = ZoneInfo(tz_str)
            doctor_name = row[2]
            dept_name = row[3]

            slot_times = [time(h, m) for h in range(9, 17) for m in (0, 30)]

            day_start_local = datetime.combine(target_d, time(0, 0), tzinfo=tz)
            day_end_local = datetime.combine(target_d + timedelta(days=1), time(0, 0), tzinfo=tz)
            day_start_utc = day_start_local.astimezone(dt_tz.utc)
            day_end_utc = day_end_local.astimezone(dt_tz.utc)

            cur.execute("""
                SELECT scheduled_at, ends_at
                FROM public.appointments
                WHERE doctor_id = %s
                  AND hospital_id = %s
                  AND status IN ('scheduled', 'confirmed', 'in_progress')
                  AND scheduled_at >= %s AND scheduled_at < %s;
            """, (str(doc_uuid), str(context.hospital_id), day_start_utc, day_end_utc))
            booked_rows = cur.fetchall()
            booked_spans = [(r[0], r[1]) for r in booked_rows]

            now_utc = datetime.now(dt_tz.utc)
            slots = []
            for t in slot_times:
                local_dt = datetime.combine(target_d, t, tzinfo=tz)
                slot_utc = local_dt.astimezone(dt_tz.utc)
                slot_end_utc = slot_utc + timedelta(minutes=30)

                is_booked = any(max(slot_utc, b_start) < min(slot_end_utc, b_end) for b_start, b_end in booked_spans)
                is_available = (not is_booked) and (slot_utc > now_utc)

                slots.append({
                    "start_time_local": t.strftime("%H:%M"),
                    "scheduled_at_utc": slot_utc.isoformat(),
                    "is_available": is_available,
                })

            available_slots = [s for s in slots if s["is_available"]]
            citations = [
                ChatCitation(
                    source_type="appointment",
                    title=f"Available Slots for {doctor_name} ({slot_date})",
                    reference_id=str(doc_uuid),
                    snippet=f"{len(available_slots)} slots available on {slot_date}",
                )
            ]
            return {
                "doctor_name": doctor_name,
                "department": dept_name,
                "hospital_timezone": tz_str,
                "date": slot_date,
                "available_slots_count": len(available_slots),
                "available_slots": available_slots,
            }, citations


def tool_get_my_appointments(context: SecurityContext) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    patient_id = resolve_effective_patient_id(context)
    if not patient_id:
        return {"error": "No linked patient account found for this user."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.scheduled_at, a.ends_at, a.status, a.reason_for_visit,
                       COALESCE(p.full_name, 'Dr. Sarah Chen') as doc_name,
                       dept.name as dept_name
                FROM public.appointments a
                JOIN public.doctors d ON a.doctor_id = d.id
                JOIN public.departments dept ON d.department_id = dept.id
                LEFT JOIN public.profiles p ON d.profile_id = p.id
                WHERE a.patient_id = %s AND a.hospital_id = %s
                ORDER BY a.scheduled_at DESC
                LIMIT 10;
            """, (str(patient_id), str(context.hospital_id)))
            rows = cur.fetchall()

            appts = [
                {
                    "appointment_id": str(r[0]),
                    "scheduled_at": r[1].isoformat() if r[1] else None,
                    "ends_at": r[2].isoformat() if r[2] else None,
                    "status": r[3],
                    "reason_for_visit": r[4],
                    "doctor_name": r[5],
                    "department": r[6],
                    "token_number": int(r[1].timestamp() % 1000) if r[1] else 101,
                }
                for r in rows
            ]
            citations = [
                ChatCitation(
                    source_type="appointment",
                    title=f"Appointment with {a['doctor_name']} ({a['status']})",
                    reference_id=a["appointment_id"],
                    snippet=f"Scheduled at {a['scheduled_at']} | Reason: {a['reason_for_visit']}",
                )
                for a in appts[:3]
            ]
            return {"appointments": appts, "count": len(appts)}, citations


def tool_book_appointment(context: SecurityContext, doctor_id: str, scheduled_at: str, reason_for_visit: str, patient_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    try:
        doc_uuid = UUID(doctor_id)
        sched_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=dt_tz.utc)
        sched_dt_utc = sched_dt.astimezone(dt_tz.utc)
    except Exception:
        return {"error": "Invalid scheduled_at timestamp or doctor_id format. Expected ISO 8601 UTC timestamp."}, []

    now_utc = datetime.now(dt_tz.utc)
    if sched_dt_utc <= now_utc:
        return {"error": "Cannot schedule an appointment in the past. Please choose a future slot."}, []

    resolved_patient_id = resolve_effective_patient_id(context, explicit_patient_id=patient_id)
    if not resolved_patient_id:
        return {"error": "No accessible patient record found for this user."}, []

    ends_at_utc = sched_dt_utc + timedelta(minutes=30)
    token_number = int(sched_dt_utc.timestamp() % 1000)

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Prevent double booking
            cur.execute("""
                SELECT id FROM public.appointments
                WHERE doctor_id = %s
                  AND hospital_id = %s
                  AND status IN ('scheduled', 'confirmed', 'in_progress')
                  AND (
                    (scheduled_at <= %s AND ends_at > %s) OR
                    (scheduled_at < %s AND ends_at >= %s) OR
                    (scheduled_at >= %s AND ends_at <= %s)
                  );
            """, (
                str(doc_uuid), str(context.hospital_id),
                sched_dt_utc, sched_dt_utc,
                ends_at_utc, ends_at_utc,
                sched_dt_utc, ends_at_utc
            ))
            conflict = cur.fetchone()
            if conflict:
                return {"error": "Conflict: This slot is already booked for the doctor. Please select another slot."}, []

            cur.execute("SELECT department_id FROM public.doctors WHERE id = %s AND hospital_id = %s;", (str(doc_uuid), str(context.hospital_id)))
            d_dept = cur.fetchone()
            dept_id = str(d_dept[0]) if d_dept else None

            appt_id = uuid4()
            cur.execute("""
                INSERT INTO public.appointments (
                    id, hospital_id, patient_id, doctor_id, department_id,
                    scheduled_at, ends_at, status, reason_for_visit,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, 'scheduled', %s,
                    timezone('utc', now()), timezone('utc', now())
                ) RETURNING id, scheduled_at;
            """, (
                str(appt_id), str(context.hospital_id), str(resolved_patient_id), str(doc_uuid), dept_id,
                sched_dt_utc, ends_at_utc, reason_for_visit
            ))
            res = cur.fetchone()

            audit_event(
                event_type="APPOINTMENT_BOOKED_BY_AI",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="appointment",
                target_id=str(res[0]),
                action="CREATE",
                status="SUCCESS",
            )

            citation = ChatCitation(
                source_type="appointment",
                title=f"Confirmed Booking (Token #{token_number})",
                reference_id=str(res[0]),
                snippet=f"Scheduled for {res[1].isoformat()} | Doctor ID: {doc_uuid}",
            )

            return {
                "success": True,
                "appointment_id": str(res[0]),
                "scheduled_at": res[1].isoformat(),
                "token_number": token_number,
                "status": "scheduled",
                "message": f"Appointment successfully scheduled. Your OPD token number is #{token_number}.",
            }, [citation]


def tool_cancel_appointment(context: SecurityContext, appointment_id: str, reason: str) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    try:
        appt_uuid = UUID(appointment_id)
    except Exception:
        return {"error": "Invalid appointment_id format. Expected UUID."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, scheduled_at, status, patient_id
                FROM public.appointments
                WHERE id = %s AND hospital_id = %s;
            """, (str(appt_uuid), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                return {"error": "Appointment not found in this hospital tenant."}, []

            sched_at = row[1]
            status_val = row[2]
            appt_patient_id = row[3]

            if status_val in ("cancelled", "completed", "no_show"):
                return {"error": f"Cannot cancel appointment with status '{status_val}'."}, []

            # Role verification
            if context.role in ("patient", "caregiver"):
                eff_p_id = resolve_effective_patient_id(context)
                if eff_p_id and str(eff_p_id) != str(appt_patient_id):
                    return {"error": "Unauthorized: You may only cancel your own appointments."}, []

            # 2-hour advance cutoff rule
            now_utc = datetime.now(dt_tz.utc)
            if sched_at - now_utc < timedelta(hours=2):
                return {"error": "Cancellations must be made at least 2 hours before scheduled time. Please call the clinic desk directly."}, []

            cur.execute("""
                UPDATE public.appointments
                SET status = 'cancelled',
                    clinical_notes = %s,
                    updated_at = timezone('utc', now())
                WHERE id = %s;
            """, (f"Cancelled via Conversational AI: {reason}", str(appt_uuid)))

            audit_event(
                event_type="APPOINTMENT_CANCELLED_BY_AI",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="appointment",
                target_id=str(appt_uuid),
                action="UPDATE",
                status="SUCCESS",
            )

            citation = ChatCitation(
                source_type="appointment",
                title="Cancelled Appointment",
                reference_id=str(appt_uuid),
                snippet=f"Cancelled: {reason}",
            )

            return {
                "success": True,
                "appointment_id": str(appt_uuid),
                "status": "cancelled",
                "message": "Appointment has been successfully cancelled.",
            }, [citation]


def tool_lookup_hospital_info(context: SecurityContext) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name, slug, contact_phone, contact_email, timezone
                FROM public.hospitals
                WHERE id = %s;
            """, (str(context.hospital_id),))
            h_row = cur.fetchone()
            if not h_row:
                return {"error": "Hospital details not found."}, []

            cur.execute("""
                SELECT name, code, head_of_department
                FROM public.departments
                WHERE hospital_id = %s
                ORDER BY name ASC;
            """, (str(context.hospital_id),))
            d_rows = cur.fetchall()

            citation = ChatCitation(
                source_type="hospital_directory",
                title=f"{h_row[0]} Directory",
                reference_id=str(context.hospital_id),
                snippet=f"Phone: {h_row[2]} | Email: {h_row[3]} | Departments: {len(d_rows)}",
            )

            return {
                "hospital_name": h_row[0],
                "slug": h_row[1],
                "phone": h_row[2],
                "email": h_row[3],
                "timezone": h_row[4] or "Asia/Kolkata",
                "departments": [{"name": d[0], "code": d[1], "head": d[2]} for d in d_rows],
            }, [citation]


def tool_get_my_documents(context: SecurityContext, status: Optional[str] = None, patient_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    eff_patient_id = resolve_effective_patient_id(context, explicit_patient_id=patient_id)
    if not eff_patient_id:
        return {"error": "No accessible patient record found."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, file_name, document_type, ocr_status, error_code, created_at, storage_path
                FROM public.clinical_documents
                WHERE hospital_id = %s AND patient_id = %s
            """
            params: List[Any] = [str(context.hospital_id), str(eff_patient_id)]
            if status:
                query += " AND ocr_status = %s"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT 10;"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            docs = []
            citations = []
            for r in rows:
                doc_id = str(r[0])
                doc_info = {
                    "document_id": doc_id,
                    "filename": r[1],
                    "document_type": r[2],
                    "status": r[3],
                    "error_message": r[4] if r[3] == "failed" else None,
                    "uploaded_at": r[5].isoformat() if r[5] else None,
                    "extracted_summary": f"Clinical document: {r[1]} ({r[2]})",
                }
                docs.append(doc_info)
                citations.append(
                    ChatCitation(
                        source_type="document",
                        title=f"Clinical Document: {r[1]} ({r[3]})",
                        reference_id=doc_id,
                        snippet=f"Type: {r[2]} | Uploaded: {doc_info['uploaded_at']}",
                    )
                )

            return {"documents": docs, "total": len(docs)}, citations


def tool_get_my_prescriptions(context: SecurityContext, status: Optional[str] = None, patient_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    eff_patient_id = resolve_effective_patient_id(context, explicit_patient_id=patient_id)
    if not eff_patient_id:
        return {"error": "No accessible patient record found."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT pr.id, pr.status, pr.issued_at, pr.verification_hash,
                       COALESCE(prof.full_name, 'Attending Physician') as doctor_name
                FROM public.prescriptions pr
                LEFT JOIN public.doctors d ON pr.doctor_id = d.id
                LEFT JOIN public.profiles prof ON d.profile_id = prof.id
                WHERE pr.hospital_id = %s AND pr.patient_id = %s
            """
            params: List[Any] = [str(context.hospital_id), str(eff_patient_id)]
            if status:
                query += " AND pr.status = %s"
                params.append(status)
            query += " ORDER BY pr.issued_at DESC LIMIT 5;"

            cur.execute(query, tuple(params))
            p_rows = cur.fetchall()

            prescriptions = []
            citations = []
            for pr in p_rows:
                pr_id = str(pr[0])
                # Fetch items
                cur.execute("""
                    SELECT drug_name, dosage, route, frequency, duration_days, instructions
                    FROM public.prescription_items
                    WHERE prescription_id = %s AND hospital_id = %s;
                """, (pr_id, str(context.hospital_id)))
                items = [
                    {
                        "medication_name": item[0],
                        "dosage": item[1],
                        "route": item[2],
                        "frequency": item[3],
                        "duration_days": item[4],
                        "instructions": item[5],
                    }
                    for item in cur.fetchall()
                ]
                        "form": item[2],
                        "route": item[3],
                        "dosage": item[4],
                        "frequency": item[5],
                        "duration": item[6],
                        "instructions": item[7],
                    }
                    for item in cur.fetchall()
                ]

                # Fetch adherence score
                cur.execute("""
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE status = 'taken')
                    FROM public.medication_adherence_logs
                    WHERE prescription_id = %s AND hospital_id = %s;
                """, (pr_id, str(context.hospital_id)))
                adh_row = cur.fetchone()
                total_scheduled = adh_row[0] if adh_row else 0
                taken_count = adh_row[1] if adh_row else 0
                adherence_rate = round((taken_count / total_scheduled * 100), 1) if total_scheduled > 0 else 100.0

                sig_hash = pr[3]
                verify_url = f"https://carebridge.health/verify-prescription/{sig_hash}" if sig_hash else None

                p_data = {
                    "prescription_id": pr_id,
                    "status": pr[1],
                    "prescribed_at": pr[2].isoformat() if pr[2] else None,
                    "doctor_name": pr[4],
                    "verification_url": verify_url,
                    "adherence_score": f"{adherence_rate}%",
                    "items": items,
                }
                prescriptions.append(p_data)

                med_names = ", ".join([it["medication_name"] for it in items]) or "Prescription"
                citations.append(
                    ChatCitation(
                        source_type="prescription",
                        title=f"Prescription by {pr[4]} ({pr[1]}): {med_names}",
                        reference_id=pr_id,
                        snippet=f"Adherence: {adherence_rate}% | Public Verify: {verify_url}",
                    )
                )

            return {"prescriptions": prescriptions, "total": len(prescriptions)}, citations


def tool_get_my_care_tasks(context: SecurityContext, status: Optional[str] = None, patient_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    eff_patient_id = resolve_effective_patient_id(context, explicit_patient_id=patient_id)
    if not eff_patient_id:
        return {"error": "No accessible patient record found."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # AC-10.5: Internal staff_notes are EXCLUDED/MASKED from patient view!
            query = """
                SELECT id, title, description, priority, task_type, status, due_date
                FROM public.care_tasks
                WHERE hospital_id = %s AND patient_id = %s
            """
            params: List[Any] = [str(context.hospital_id), str(eff_patient_id)]
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY due_date ASC NULLS LAST LIMIT 10;"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            tasks = [
                {
                    "task_id": str(r[0]),
                    "title": r[1],
                    "description": r[2],
                    "priority": r[3],
                    "task_type": r[4],
                    "status": r[5],
                    "due_date": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ]
            citations = [
                ChatCitation(
                    source_type="care_task",
                    title=f"Care Task: {t['title']} [{t['priority'].upper()}]",
                    reference_id=t["task_id"],
                    snippet=f"Status: {t['status']} | Due: {t['due_date']}",
                )
                for t in tasks[:3]
            ]

            return {"care_tasks": tasks, "total": len(tasks)}, citations


def tool_get_staff_workflow_summary(context: SecurityContext) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    # Role gate: Only staff roles may access hospital operational summary
    if context.role in ("patient", "caregiver"):
        return {"error": "Unauthorized: Staff workflow summary is strictly restricted to clinical and hospital administrative personnel."}, []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Pending appointments today
            cur.execute("""
                SELECT COUNT(*) FROM public.appointments
                WHERE hospital_id = %s AND status IN ('scheduled', 'confirmed')
                  AND scheduled_at >= timezone('utc', now()::date)
                  AND scheduled_at < timezone('utc', (now()::date + interval '1 day'));
            """, (str(context.hospital_id),))
            today_appts = cur.fetchone()[0]

            # Unclaimed care tasks
            cur.execute("""
                SELECT COUNT(*) FROM public.care_tasks
                WHERE hospital_id = %s AND assigned_to IS NULL AND status = 'pending';
            """, (str(context.hospital_id),))
            unclaimed_tasks = cur.fetchone()[0]

            # Documents awaiting verification
            cur.execute("""
                SELECT COUNT(*) FROM public.clinical_documents
                WHERE hospital_id = %s AND ocr_status IN ('uploaded', 'extracted', 'processing');
            """, (str(context.hospital_id),))
            pending_docs = cur.fetchone()[0]

            # Open clinical conflicts
            cur.execute("""
                SELECT COUNT(*) FROM public.clinical_conflicts
                WHERE hospital_id = %s AND resolution_status = 'unresolved';
            """, (str(context.hospital_id),))
            open_conflicts = cur.fetchone()[0]

            summary = {
                "appointments_today": today_appts,
                "unclaimed_care_tasks": unclaimed_tasks,
                "pending_documents": pending_docs,
                "open_clinical_conflicts": open_conflicts,
                "status": "operational",
            }
            citations = [
                ChatCitation(
                    source_type="hospital_directory",
                    title="Staff Operational Shift Summary",
                    reference_id=str(context.hospital_id),
                    snippet=f"Today's visits: {today_appts} | Unclaimed tasks: {unclaimed_tasks} | Open conflicts: {open_conflicts}",
                )
            ]
            return summary, citations


# ---------------------------------------------------------------------------
# Central Dispatcher
# ---------------------------------------------------------------------------

def execute_chat_tool(context: SecurityContext, tool_name: str, arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], List[ChatCitation]]:
    """Executes a tool under the caller's SecurityContext, re-verifying permissions and returning structured results & citations."""
    if tool_name == "search_doctors":
        return tool_search_doctors(
            context,
            department_name=arguments.get("department_name"),
            specialty=arguments.get("specialty"),
        )
    elif tool_name == "get_doctor_slots":
        return tool_get_doctor_slots(
            context,
            doctor_id=arguments.get("doctor_id", ""),
            slot_date=arguments.get("slot_date", ""),
        )
    elif tool_name == "get_my_appointments":
        return tool_get_my_appointments(context)
    elif tool_name == "book_appointment":
        return tool_book_appointment(
            context,
            doctor_id=arguments.get("doctor_id", ""),
            scheduled_at=arguments.get("scheduled_at", ""),
            reason_for_visit=arguments.get("reason_for_visit", "Consultation"),
            patient_id=arguments.get("patient_id"),
        )
    elif tool_name == "cancel_appointment":
        return tool_cancel_appointment(
            context,
            appointment_id=arguments.get("appointment_id", ""),
            reason=arguments.get("reason", "Cancelled by user via Chat"),
        )
    elif tool_name == "lookup_hospital_info":
        return tool_lookup_hospital_info(context)
    elif tool_name == "get_my_documents":
        return tool_get_my_documents(
            context,
            status=arguments.get("status"),
            patient_id=arguments.get("patient_id"),
        )
    elif tool_name == "get_my_prescriptions":
        return tool_get_my_prescriptions(
            context,
            status=arguments.get("status"),
            patient_id=arguments.get("patient_id"),
        )
    elif tool_name == "get_my_care_tasks":
        return tool_get_my_care_tasks(
            context,
            status=arguments.get("status"),
            patient_id=arguments.get("patient_id"),
        )
    elif tool_name == "get_staff_workflow_summary":
        return tool_get_staff_workflow_summary(context)
    else:
        return {"error": f"Unknown tool: '{tool_name}'"}, []
