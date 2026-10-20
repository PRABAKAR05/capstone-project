from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
import psycopg2
from psycopg2 import errors
from app.core.security import get_security_context, SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentStatusUpdate,
    AppointmentResponse,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])

VALID_TRANSITIONS = {
    "scheduled": ["confirmed", "cancelled"],
    "confirmed": ["in_progress", "cancelled", "no_show"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
    "no_show": [],
}

@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            # 1. Verify patient access
            if context.role == "patient":
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(payload.patient_id)))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not accessible")

            # 2. Check future scheduled time
            now_utc = datetime.now(timezone.utc)
            if payload.scheduled_at <= now_utc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot schedule appointments in the past")

            ends_at = payload.scheduled_at + timedelta(minutes=payload.duration_minutes)
            appointment_id = uuid4()

            # 3. Attempt insert inside transaction
            try:
                cur.execute("""
                    INSERT INTO public.appointments (
                        id, hospital_id, patient_id, doctor_id, department_id,
                        scheduled_at, ends_at, status, reason_for_visit
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'scheduled', %s
                    ) RETURNING created_at, updated_at;
                """, (
                    str(appointment_id), str(context.hospital_id), str(payload.patient_id),
                    str(payload.doctor_id), str(payload.department_id),
                    payload.scheduled_at, ends_at, payload.reason_for_visit
                ))
                created_at, updated_at = cur.fetchone()
            except errors.ExclusionViolation:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Appointment slot unavailable: The requested doctor already has a booking during this interval.",
                )
            except errors.ForeignKeyViolation:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Referenced doctor or department does not exist in this hospital.",
                )

            audit_event(
                event_type="APPOINTMENT_CREATED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="appointment",
                target_id=str(appointment_id),
                action="CREATE",
                status="SUCCESS",
                client_ip=request.client.host if request.client else None,
            )

            return AppointmentResponse(
                id=appointment_id,
                hospital_id=context.hospital_id,
                patient_id=payload.patient_id,
                doctor_id=payload.doctor_id,
                department_id=payload.department_id,
                scheduled_at=payload.scheduled_at,
                ends_at=ends_at,
                status="scheduled",
                reason_for_visit=payload.reason_for_visit,
                clinical_notes=None,
                created_at=created_at,
                updated_at=updated_at,
            )

@router.get("", response_model=List[AppointmentResponse])
def list_appointments(
    doctor_id: Optional[UUID] = None,
    patient_id: Optional[UUID] = None,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, hospital_id, patient_id, doctor_id, department_id,
                       scheduled_at, ends_at, status, reason_for_visit, clinical_notes,
                       created_at, updated_at
                FROM public.appointments
                WHERE hospital_id = %s
            """
            params = [str(context.hospital_id)]

            if context.role == "patient":
                query += """ AND patient_id IN (
                    SELECT patient_id FROM public.patient_accounts
                    WHERE user_id = %s AND hospital_id = %s AND status = 'verified'
                )"""
                params.extend([str(context.user_id), str(context.hospital_id)])
            elif doctor_id:
                query += " AND doctor_id = %s"
                params.append(str(doctor_id))
            elif patient_id:
                query += " AND patient_id = %s"
                params.append(str(patient_id))

            query += " ORDER BY scheduled_at ASC LIMIT 100;"
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            return [
                AppointmentResponse(
                    id=r[0], hospital_id=r[1], patient_id=r[2], doctor_id=r[3], department_id=r[4],
                    scheduled_at=r[5], ends_at=r[6], status=r[7], reason_for_visit=r[8],
                    clinical_notes=r[9] if context.role != "lab_technician" else None,
                    created_at=r[10], updated_at=r[11],
                )
                for r in rows
            ]

@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
def update_appointment_status(
    appointment_id: UUID,
    payload: AppointmentStatusUpdate,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, patient_id, doctor_id, department_id,
                       scheduled_at, ends_at, status, reason_for_visit, clinical_notes,
                       created_at, updated_at
                FROM public.appointments
                WHERE id = %s AND hospital_id = %s;
            """, (str(appointment_id), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

            current_status = row[7]

            # 1. State machine validation
            if payload.status not in VALID_TRANSITIONS.get(current_status, []):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Illegal transition: Cannot transition appointment from '{current_status}' to '{payload.status}'",
                )

            # 2. Role permission check (Canonical 5-role RBAC)
            if context.role == "patient":
                if payload.status == "cancelled":
                    if payload.clinical_notes:
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients cannot write clinical notes")
                elif payload.status == "confirmed":
                    # Time-gated patient arrival check-in [-60 min, +30 min]
                    now_utc = datetime.now(timezone.utc)
                    scheduled_at = row[5]
                    if not (scheduled_at - timedelta(minutes=60) <= now_utc <= scheduled_at + timedelta(minutes=30)):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="CHECKIN_WINDOW_CLOSED: Arrival check-in is only available between 60 minutes before and 30 minutes after scheduled appointment time.",
                        )
                    if payload.clinical_notes:
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients cannot write clinical notes")
                else:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients can only cancel appointments or check in for arrival within the active arrival window")
            elif context.role == "nurse":
                if payload.status not in ("confirmed", "cancelled", "no_show"):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nurses can only confirm (desk check-in), cancel, or mark no-show for appointments")
                if payload.clinical_notes:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nurses cannot write clinical consultation notes on appointments")
            elif context.role == "lab_technician":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lab technicians are not authorized to modify appointment status")
            elif context.role not in ("doctor", "hospital_admin"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not authorized to update appointment status")

            new_notes = payload.clinical_notes if payload.clinical_notes else row[9]

            cur.execute("""
                UPDATE public.appointments
                SET status = %s,
                    clinical_notes = %s,
                    updated_at = timezone('utc', now())
                WHERE id = %s
                RETURNING updated_at;
            """, (payload.status, new_notes, str(appointment_id)))
            updated_at = cur.fetchone()[0]

            # Phase 8 Automated Care Coordination Trigger on Consultation Completion
            if payload.status == "completed":
                try:
                    from app.care_tasks.service import auto_trigger_post_consultation_task
                    auto_trigger_post_consultation_task(
                        cur=cur,
                        hospital_id=context.hospital_id,
                        patient_id=row[2],
                        encounter_id=appointment_id,
                        clinical_notes=new_notes,
                        actor_id=context.user_id,
                    )
                except Exception:
                    pass

            audit_event(
                event_type="APPOINTMENT_STATUS_UPDATED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="appointment",
                target_id=str(appointment_id),
                action="UPDATE",
                status="SUCCESS",
                client_ip=request.client.host if request.client else None,
            )

            return AppointmentResponse(
                id=row[0], hospital_id=row[1], patient_id=row[2], doctor_id=row[3], department_id=row[4],
                scheduled_at=row[5], ends_at=row[6], status=payload.status, reason_for_visit=row[8],
                clinical_notes=new_notes, created_at=row[10], updated_at=updated_at,
            )

@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: UUID,
    payload: AppointmentReschedule,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, patient_id, doctor_id, department_id,
                       scheduled_at, ends_at, status, reason_for_visit, clinical_notes
                FROM public.appointments
                WHERE id = %s AND hospital_id = %s FOR UPDATE;
            """, (str(appointment_id), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

            current_status = row[7]
            scheduled_at = row[5]

            # 1. Allowed state check
            if current_status not in ("scheduled", "confirmed"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"INVALID_RESCHEDULE_STATE: Cannot reschedule an appointment in status '{current_status}'",
                )

            # 2. Two-hour cutoff check for patients
            now_utc = datetime.now(timezone.utc)
            if context.role == "patient":
                if now_utc >= scheduled_at - timedelta(hours=2):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="RESCHEDULE_WINDOW_EXPIRED: Cannot reschedule within 2 hours of appointment start time",
                    )

            # 3. Insert new appointment (atomic)
            duration = row[6] - row[5]
            new_ends_at = payload.new_scheduled_at + duration
            new_id = uuid4()

            try:
                cur.execute("""
                    INSERT INTO public.appointments (
                        id, hospital_id, patient_id, doctor_id, department_id,
                        scheduled_at, ends_at, status, reason_for_visit
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'scheduled', %s
                    ) RETURNING created_at, updated_at;
                """, (
                    str(new_id), str(context.hospital_id), str(row[2]),
                    str(row[3]), str(row[4]), payload.new_scheduled_at, new_ends_at,
                    f"Rescheduled from {appointment_id}"
                ))
                new_created_at, new_updated_at = cur.fetchone()

                # Step 4: Cancel old appointment
                cur.execute("""
                    UPDATE public.appointments
                    SET status = 'cancelled',
                        clinical_notes = %s,
                        updated_at = timezone('utc', now())
                    WHERE id = %s;
                """, (f"Rescheduled to {new_id}", str(appointment_id)))

            except errors.ExclusionViolation:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target appointment slot is unavailable due to an existing booking.",
                )

            audit_event(
                event_type="APPOINTMENT_RESCHEDULED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="appointment",
                target_id=str(new_id),
                action="RESCHEDULE",
                status="SUCCESS",
                client_ip=request.client.host if request.client else None,
            )

            return AppointmentResponse(
                id=new_id, hospital_id=context.hospital_id, patient_id=row[2], doctor_id=row[3],
                department_id=row[4], scheduled_at=payload.new_scheduled_at, ends_at=new_ends_at,
                status="scheduled", reason_for_visit=f"Rescheduled from {appointment_id}",
                clinical_notes=None, created_at=new_created_at, updated_at=new_updated_at,
            )
