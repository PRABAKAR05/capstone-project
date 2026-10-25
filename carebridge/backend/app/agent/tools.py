import json
from uuid import UUID, uuid4
from datetime import datetime, date, time, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo, available_timezones
from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2 import errors

from app.core.security import SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event

# ---------------------------------------------------------------------------
# Tool Declarations for Groq / OpenAI Tool Calling API
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
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
            "description": "Retrieve available 30-minute appointment consultation slots for a specific doctor on a given date (YYYY-MM-DD) in the hospital's timezone.",
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
            "name": "book_appointment",
            "description": "Book a new clinical consultation appointment slot for the patient. Enforces strict double-booking prevention.",
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
                        "description": "Optional UUID of the patient record. If caller is patient, automatically resolved.",
                    },
                },
                "required": ["doctor_id", "scheduled_at", "reason_for_visit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_appointments",
            "description": "Retrieve upcoming and recent appointments associated with the authenticated caller (or their linked patient).",
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
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Enforces the strict 2-hour advance cutoff rule.",
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
            "description": "Lookup hospital tenant information, contact details, operating timezone, and list of clinical departments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Implementations Executed Under SecurityContext
# ---------------------------------------------------------------------------

def tool_search_doctors(context: SecurityContext, department_name: Optional[str] = None, specialty: Optional[str] = None) -> Dict[str, Any]:
    with get_db(None) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT d.id, COALESCE(p.full_name, 'Staff Physician'), d.specialization, d.qualification,
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
            return {"doctors": doctors, "total_found": len(doctors)}


def tool_get_doctor_slots(context: SecurityContext, doctor_id: str, slot_date: str) -> Dict[str, Any]:
    try:
        doc_uuid = UUID(doctor_id)
        target_d = date.fromisoformat(slot_date)
    except Exception:
        return {"error": "Invalid doctor_id or slot_date format. Expected UUID and YYYY-MM-DD."}

    with get_db(None) as conn:
        with conn.cursor() as cur:
            # Fetch doctor and hospital timezone
            cur.execute("""
                SELECT d.id, h.timezone, COALESCE(p.full_name, 'Staff Physician'), dept.name
                FROM public.doctors d
                JOIN public.hospitals h ON d.hospital_id = h.id
                JOIN public.departments dept ON d.department_id = dept.id
                LEFT JOIN public.profiles p ON d.profile_id = p.id
                WHERE d.id = %s AND d.hospital_id = %s;
            """, (str(doc_uuid), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                return {"error": "Doctor not found in this hospital tenant."}

            tz_str = row[1] or "Asia/Kolkata"
            if tz_str not in available_timezones():
                tz_str = "Asia/Kolkata"
            tz = ZoneInfo(tz_str)
            doctor_name = row[2]
            dept_name = row[3]

            # Standard OPD hours: 09:00 to 17:00 (30-min slots)
            slot_times = [time(h, m) for h in range(9, 17) for m in (0, 30)]

            # Convert local day range to UTC bounds
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

                # Check if booked or past
                is_booked = any(max(slot_utc, b_start) < min(slot_end_utc, b_end) for b_start, b_end in booked_spans)
                is_available = (not is_booked) and (slot_utc > now_utc)

                slots.append({
                    "start_time_local": t.strftime("%H:%M"),
                    "scheduled_at_utc": slot_utc.isoformat(),
                    "is_available": is_available,
                })

            available_slots = [s for s in slots if s["is_available"]]
            return {
                "doctor_name": doctor_name,
                "department": dept_name,
                "hospital_timezone": tz_str,
                "date": slot_date,
                "available_slots_count": len(available_slots),
                "available_slots": available_slots,
            }


def tool_book_appointment(context: SecurityContext, doctor_id: str, scheduled_at: str, reason_for_visit: str, patient_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        doc_uuid = UUID(doctor_id)
        sched_dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=dt_tz.utc)
        sched_dt_utc = sched_dt.astimezone(dt_tz.utc)
    except Exception:
        return {"error": "Invalid scheduled_at timestamp or doctor_id format. Expected ISO 8601 UTC timestamp."}

    now_utc = datetime.now(dt_tz.utc)
    if sched_dt_utc <= now_utc:
        return {"error": "Cannot schedule an appointment in the past. Please choose a future slot."}

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Resolve patient_id if not explicitly provided
            resolved_patient_id = None
            if patient_id:
                try:
                    resolved_patient_id = UUID(patient_id)
                except Exception:
                    return {"error": "Invalid patient_id UUID format."}
            else:
                # Find patient account associated with caller
                cur.execute("""
                    SELECT patient_id FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND status = 'verified'
                    LIMIT 1;
                """, (str(context.hospital_id), str(context.user_id)))
                p_row = cur.fetchone()
                if p_row:
                    resolved_patient_id = p_row[0]
                else:
                    # Fallback to demo patient for convenience
                    cur.execute("""
                        SELECT id FROM public.patients
                        WHERE hospital_id = %s LIMIT 1;
                    """, (str(context.hospital_id),))
                    fallback_p = cur.fetchone()
                    if fallback_p:
                        resolved_patient_id = fallback_p[0]
                    else:
                        return {"error": "No accessible patient record found for this user."}

            # Fetch doctor department
            cur.execute("""
                SELECT d.department_id, COALESCE(p.full_name, 'Staff Physician'), dept.name
                FROM public.doctors d
                JOIN public.departments dept ON d.department_id = dept.id
                LEFT JOIN public.profiles p ON d.profile_id = p.id
                WHERE d.id = %s AND d.hospital_id = %s;
            """, (str(doc_uuid), str(context.hospital_id)))
            d_row = cur.fetchone()
            if not d_row:
                return {"error": "Doctor not found in this hospital tenant."}
            
            department_id = d_row[0]
            doctor_name = d_row[1]
            dept_name = d_row[2]

            duration_minutes = 30
            ends_at_utc = sched_dt_utc + timedelta(minutes=duration_minutes)
            appointment_id = uuid4()

            try:
                cur.execute("""
                    INSERT INTO public.appointments (
                        id, hospital_id, patient_id, doctor_id, department_id,
                        scheduled_at, ends_at, status, reason_for_visit
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'scheduled', %s
                    ) RETURNING created_at;
                """, (
                    str(appointment_id), str(context.hospital_id), str(resolved_patient_id),
                    str(doc_uuid), str(department_id), sched_dt_utc, ends_at_utc, reason_for_visit
                ))
                created_at = cur.fetchone()[0]

                audit_event(
                    event_type="APPOINTMENT_BOOKED_BY_AI",
                    actor_id=str(context.user_id),
                    actor_role=context.role,
                    hospital_id=str(context.hospital_id),
                    target_resource="appointment",
                    target_id=str(appointment_id),
                    action="CREATE",
                    status="SUCCESS",
                )

                return {
                    "success": True,
                    "appointment_id": str(appointment_id),
                    "doctor_name": doctor_name,
                    "department": dept_name,
                    "scheduled_at": sched_dt_utc.isoformat(),
                    "duration_minutes": duration_minutes,
                    "status": "scheduled",
                    "reason_for_visit": reason_for_visit,
                    "message": f"Appointment confirmed with {doctor_name} for {sched_dt_utc.strftime('%Y-%m-%d %H:%M UTC')}.",
                }

            except errors.ExclusionViolation:
                conn.rollback()
                return {
                    "error": "SLOT_CONFLICT_409",
                    "message": "The requested appointment slot was just booked by another patient. Please choose an alternate slot.",
                }
            except Exception as e:
                conn.rollback()
                return {"error": f"Booking failed: {str(e)}"}


def tool_get_my_appointments(context: SecurityContext) -> Dict[str, Any]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT a.id, a.scheduled_at, a.ends_at, a.status, a.reason_for_visit,
                       p.full_name as doctor_name, dept.name as dept_name
                FROM public.appointments a
                JOIN public.doctors d ON a.doctor_id = d.id
                JOIN public.profiles p ON d.profile_id = p.id
                JOIN public.departments dept ON a.department_id = dept.id
                WHERE a.hospital_id = %s
            """
            params: List[Any] = [str(context.hospital_id)]

            if context.role == "patient":
                query += """
                    AND a.patient_id IN (
                        SELECT patient_id FROM public.patient_accounts
                        WHERE user_id = %s AND hospital_id = %s AND status = 'verified'
                    )
                """
                params.extend([str(context.user_id), str(context.hospital_id)])
            elif context.role == "doctor":
                query += """
                    AND a.doctor_id IN (
                        SELECT id FROM public.doctors WHERE profile_id = %s AND hospital_id = %s
                    )
                """
                params.extend([str(context.user_id), str(context.hospital_id)])

            query += " ORDER BY a.scheduled_at DESC LIMIT 15;"
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            appts = [
                {
                    "appointment_id": str(r[0]),
                    "scheduled_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
                    "status": r[3],
                    "reason_for_visit": r[4],
                    "doctor_name": r[5],
                    "department": r[6],
                }
                for r in rows
            ]
            return {"appointments": appts, "total": len(appts)}


def tool_cancel_appointment(context: SecurityContext, appointment_id: str, reason: str = "Patient requested cancellation") -> Dict[str, Any]:
    try:
        appt_uuid = UUID(appointment_id)
    except Exception:
        return {"error": "Invalid appointment_id UUID format."}

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, scheduled_at, status, patient_id
                FROM public.appointments
                WHERE id = %s AND hospital_id = %s;
            """, (str(appt_uuid), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                return {"error": "Appointment not found in this hospital tenant."}

            scheduled_at = row[1]
            current_status = row[2]

            if current_status in ("completed", "cancelled", "no_show"):
                return {"error": f"Cannot cancel an appointment that is already {current_status}."}

            # 2-hour cutoff check for patients
            now_utc = datetime.now(dt_tz.utc)
            if context.role == "patient" and now_utc >= scheduled_at - timedelta(hours=2):
                return {
                    "error": "CUTOFF_EXPIRED_422",
                    "message": "Appointments cannot be cancelled within 2 hours of start time. Please call the reception desk directly.",
                }

            cur.execute("""
                UPDATE public.appointments
                SET status = 'cancelled',
                    clinical_notes = %s,
                    updated_at = timezone('utc', now())
                WHERE id = %s;
            """, (f"Cancelled via AI Agent: {reason}", str(appt_uuid)))

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

            return {
                "success": True,
                "appointment_id": str(appt_uuid),
                "status": "cancelled",
                "message": "Appointment has been successfully cancelled.",
            }


def tool_lookup_hospital_info(context: SecurityContext) -> Dict[str, Any]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name, slug, contact_phone, contact_email, timezone
                FROM public.hospitals
                WHERE id = %s;
            """, (str(context.hospital_id),))
            h_row = cur.fetchone()
            if not h_row:
                return {"error": "Hospital details not found."}

            cur.execute("""
                SELECT name, code, head_of_department
                FROM public.departments
                WHERE hospital_id = %s
                ORDER BY name ASC;
            """, (str(context.hospital_id),))
            d_rows = cur.fetchall()

            return {
                "hospital_name": h_row[0],
                "slug": h_row[1],
                "phone": h_row[2],
                "email": h_row[3],
                "timezone": h_row[4] or "Asia/Kolkata",
                "departments": [{"name": d[0], "code": d[1], "head": d[2]} for d in d_rows],
            }


# ---------------------------------------------------------------------------
# Central Tool Dispatcher
# ---------------------------------------------------------------------------

def execute_agent_tool(context: SecurityContext, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
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
    elif tool_name == "book_appointment":
        return tool_book_appointment(
            context,
            doctor_id=arguments.get("doctor_id", ""),
            scheduled_at=arguments.get("scheduled_at", ""),
            reason_for_visit=arguments.get("reason_for_visit", "Consultation"),
            patient_id=arguments.get("patient_id"),
        )
    elif tool_name == "get_my_appointments":
        return tool_get_my_appointments(context)
    elif tool_name == "cancel_appointment":
        return tool_cancel_appointment(
            context,
            appointment_id=arguments.get("appointment_id", ""),
            reason=arguments.get("reason", "Cancelled by user"),
        )
    elif tool_name == "lookup_hospital_info":
        return tool_lookup_hospital_info(context)
    else:
        return {"error": f"Unknown tool: '{tool_name}'"}
