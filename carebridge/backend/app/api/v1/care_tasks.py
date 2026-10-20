from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_security_context, SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.care_task import (
    CareTaskCreateRequest,
    CareTaskCompleteRequest,
    CareTaskCancelRequest,
    CareTaskResponse,
    CareTaskPendingCountsResponse,
)
from app.care_tasks.service import insert_care_task

router = APIRouter(prefix="/care-tasks", tags=["care-tasks"])


@router.post("", response_model=CareTaskResponse, status_code=status.HTTP_201_CREATED)
def create_care_task(
    body: CareTaskCreateRequest,
    context: SecurityContext = Depends(get_security_context),
):
    """Create a new manual care coordination task.
    Restricted to authenticated hospital staff.
    """
    if context.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Care tasks can only be created by hospital clinical and coordination staff."
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # 1. Verify patient belongs to this hospital
            cur.execute("""
                SELECT id FROM public.patients
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(body.patient_id)))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")

            task_id = insert_care_task(
                cur=cur,
                hospital_id=context.hospital_id,
                patient_id=body.patient_id,
                title=body.title,
                description=body.description,
                task_type=body.task_type,
                priority=body.priority,
                assigned_role=body.assigned_role,
                encounter_id=body.encounter_id,
                patient_instructions=body.patient_instructions,
                assigned_to=body.assigned_to,
                due_date=body.due_date,
                actor_id=context.user_id,
                actor_role=context.role,
            )

            cur.execute("""
                SELECT id, hospital_id, patient_id, encounter_id, task_type,
                       priority, status, title, description, patient_instructions,
                       assigned_role, assigned_to, due_date, completed_by, completed_at,
                       completion_notes, created_at, updated_at
                FROM public.care_tasks
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(task_id)))
            row = cur.fetchone()

            return CareTaskResponse(
                id=row[0],
                hospital_id=row[1],
                patient_id=row[2],
                encounter_id=row[3],
                task_type=row[4],
                priority=row[5],
                status=row[6],
                title=row[7],
                description=row[8],
                patient_instructions=row[9],
                assigned_role=row[10],
                assigned_to=row[11],
                due_date=row[12],
                completed_by=row[13],
                completed_at=row[14],
                completion_notes=row[15],
                created_at=row[16],
                updated_at=row[17],
            )


@router.get("", response_model=List[CareTaskResponse])
def list_care_tasks(
    patient_id: Optional[UUID] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    assigned_role: Optional[str] = Query(None),
    assigned_to: Optional[UUID] = Query(None),
    priority: Optional[str] = Query(None),
    context: SecurityContext = Depends(get_security_context),
):
    """List care coordination tasks. Patient callers receive sanitized views."""
    with get_db(context) as conn:
        with conn.cursor() as cur:
            resolved_patient_id = patient_id
            is_patient_caller = context.role == "patient"

            if is_patient_caller:
                cur.execute("""
                    SELECT patient_id FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id)))
                account_rows = cur.fetchall()
                allowed_patient_ids = {r[0] for r in account_rows}

                if not allowed_patient_ids:
                    return []

                if resolved_patient_id:
                    if resolved_patient_id not in allowed_patient_ids:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient tasks not found.")
                else:
                    resolved_patient_id = list(allowed_patient_ids)[0]

            query = """
                SELECT id, hospital_id, patient_id, encounter_id, task_type,
                       priority, status, title, description, patient_instructions,
                       assigned_role, assigned_to, due_date, completed_by, completed_at,
                       completion_notes, created_at, updated_at
                FROM public.care_tasks
                WHERE hospital_id = %s
            """
            params: List[object] = [str(context.hospital_id)]

            if resolved_patient_id:
                query += " AND patient_id = %s"
                params.append(str(resolved_patient_id))

            if is_patient_caller:
                query += " AND patient_instructions IS NOT NULL"

            if status_param:
                query += " AND status = %s"
                params.append(status_param)

            if assigned_role:
                query += " AND assigned_role = %s"
                params.append(assigned_role)

            if assigned_to:
                query += " AND assigned_to = %s"
                params.append(str(assigned_to))

            if priority:
                query += " AND priority = %s"
                params.append(priority)

            query += """
                ORDER BY 
                  CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'routine' THEN 3 ELSE 4 END,
                  due_date ASC NULLS LAST, created_at DESC;
            """

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            return [
                CareTaskResponse(
                    id=r[0],
                    hospital_id=r[1],
                    patient_id=r[2],
                    encounter_id=r[3],
                    task_type=r[4],
                    priority=r[5],
                    status=r[6],
                    title=r[7],
                    description=None if is_patient_caller else r[8],
                    patient_instructions=r[9],
                    assigned_role=r[10],
                    assigned_to=r[11],
                    due_date=r[12],
                    completed_by=None if is_patient_caller else r[13],
                    completed_at=r[14],
                    completion_notes=None if is_patient_caller else r[15],
                    created_at=r[16],
                    updated_at=r[17],
                )
                for r in rows
            ]


@router.get("/notifications/pending-counts", response_model=CareTaskPendingCountsResponse)
def get_pending_task_counts(
    context: SecurityContext = Depends(get_security_context),
):
    """Returns counts of pending and urgent tasks for hospital staff workstation badges."""
    if context.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff task notifications only accessible by hospital personnel."
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE priority = 'urgent' AND status IN ('pending', 'claimed', 'in_progress')) as urgent_count,
                    COUNT(*) FILTER (WHERE priority = 'high' AND status IN ('pending', 'claimed', 'in_progress')) as high_count,
                    COUNT(*) FILTER (WHERE status IN ('pending', 'claimed', 'in_progress')) as total_pending,
                    COUNT(*) FILTER (WHERE assigned_to = %s AND status IN ('claimed', 'in_progress')) as claimed_by_me
                FROM public.care_tasks
                WHERE hospital_id = %s;
            """, (str(context.user_id), str(context.hospital_id)))
            row = cur.fetchone()
            return CareTaskPendingCountsResponse(
                urgent_count=row[0] if row else 0,
                high_count=row[1] if row else 0,
                total_pending=row[2] if row else 0,
                claimed_by_me_count=row[3] if row else 0,
            )


@router.get("/{id}", response_model=CareTaskResponse)
def get_care_task(
    id: UUID,
    context: SecurityContext = Depends(get_security_context),
):
    """Retrieve full detail for a single care coordination task."""
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, patient_id, encounter_id, task_type,
                       priority, status, title, description, patient_instructions,
                       assigned_role, assigned_to, due_date, completed_by, completed_at,
                       completion_notes, created_at, updated_at
                FROM public.care_tasks
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(id)))
            r = cur.fetchone()
            if not r:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

            is_patient_caller = context.role == "patient"
            if is_patient_caller:
                patient_id = r[2]
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(patient_id)))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

                if not r[9]:  # patient_instructions is None
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

            return CareTaskResponse(
                id=r[0],
                hospital_id=r[1],
                patient_id=r[2],
                encounter_id=r[3],
                task_type=r[4],
                priority=r[5],
                status=r[6],
                title=r[7],
                description=None if is_patient_caller else r[8],
                patient_instructions=r[9],
                assigned_role=r[10],
                assigned_to=r[11],
                due_date=r[12],
                completed_by=None if is_patient_caller else r[13],
                completed_at=r[14],
                completion_notes=None if is_patient_caller else r[15],
                created_at=r[16],
                updated_at=r[17],
            )


@router.post("/{id}/claim", response_model=CareTaskResponse)
def claim_care_task(
    id: UUID,
    context: SecurityContext = Depends(get_security_context),
):
    """Claim an open pool care task for the authenticated staff member (soft-lock model).
    Patients are strictly prohibited (HTTP 403).
    """
    if context.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Care tasks can only be claimed by authorized hospital personnel."
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, assigned_to FROM public.care_tasks
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

            cur.execute("""
                UPDATE public.care_tasks
                SET status = 'claimed',
                    assigned_to = %s,
                    updated_at = timezone('utc'::text, now())
                WHERE hospital_id = %s AND id = %s
                RETURNING id, hospital_id, patient_id, encounter_id, task_type,
                          priority, status, title, description, patient_instructions,
                          assigned_role, assigned_to, due_date, completed_by, completed_at,
                          completion_notes, created_at, updated_at;
            """, (str(context.user_id), str(context.hospital_id), str(id)))
            updated = cur.fetchone()

            audit_event(
                event_type="TASK_CLAIMED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="care_task",
                target_id=str(id),
                action="CLAIM",
                status="SUCCESS",
            )

            return CareTaskResponse(
                id=updated[0],
                hospital_id=updated[1],
                patient_id=updated[2],
                encounter_id=updated[3],
                task_type=updated[4],
                priority=updated[5],
                status=updated[6],
                title=updated[7],
                description=updated[8],
                patient_instructions=updated[9],
                assigned_role=updated[10],
                assigned_to=updated[11],
                due_date=updated[12],
                completed_by=updated[13],
                completed_at=updated[14],
                completion_notes=updated[15],
                created_at=updated[16],
                updated_at=updated[17],
            )


@router.post("/{id}/complete", response_model=CareTaskResponse)
def complete_care_task(
    id: UUID,
    body: CareTaskCompleteRequest,
    context: SecurityContext = Depends(get_security_context),
):
    """Mark a care coordination task completed with mandatory resolution notes.
    Patients are strictly prohibited (HTTP 403).
    """
    if context.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Care tasks can only be resolved by authorized hospital personnel."
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM public.care_tasks
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(id)))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

            cur.execute("""
                UPDATE public.care_tasks
                SET status = 'completed',
                    completed_by = %s,
                    completed_at = timezone('utc'::text, now()),
                    completion_notes = %s,
                    updated_at = timezone('utc'::text, now())
                WHERE hospital_id = %s AND id = %s
                RETURNING id, hospital_id, patient_id, encounter_id, task_type,
                          priority, status, title, description, patient_instructions,
                          assigned_role, assigned_to, due_date, completed_by, completed_at,
                          completion_notes, created_at, updated_at;
            """, (str(context.user_id), body.completion_notes.strip(), str(context.hospital_id), str(id)))
            updated = cur.fetchone()

            audit_event(
                event_type="TASK_COMPLETED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="care_task",
                target_id=str(id),
                action="COMPLETE",
                status="SUCCESS",
            )

            return CareTaskResponse(
                id=updated[0],
                hospital_id=updated[1],
                patient_id=updated[2],
                encounter_id=updated[3],
                task_type=updated[4],
                priority=updated[5],
                status=updated[6],
                title=updated[7],
                description=updated[8],
                patient_instructions=updated[9],
                assigned_role=updated[10],
                assigned_to=updated[11],
                due_date=updated[12],
                completed_by=updated[13],
                completed_at=updated[14],
                completion_notes=updated[15],
                created_at=updated[16],
                updated_at=updated[17],
            )


@router.post("/{id}/cancel", response_model=CareTaskResponse)
def cancel_care_task(
    id: UUID,
    body: CareTaskCancelRequest,
    context: SecurityContext = Depends(get_security_context),
):
    """Cancel a care coordination task with documented cancellation rationale.
    Restricted to doctor and hospital_admin roles.
    """
    if context.role not in ("doctor", "hospital_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Care task cancellation is restricted to physicians and hospital administrators."
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM public.care_tasks
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(id)))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care task not found.")

            cur.execute("""
                UPDATE public.care_tasks
                SET status = 'cancelled',
                    completed_by = %s,
                    completed_at = timezone('utc'::text, now()),
                    completion_notes = %s,
                    updated_at = timezone('utc'::text, now())
                WHERE hospital_id = %s AND id = %s
                RETURNING id, hospital_id, patient_id, encounter_id, task_type,
                          priority, status, title, description, patient_instructions,
                          assigned_role, assigned_to, due_date, completed_by, completed_at,
                          completion_notes, created_at, updated_at;
            """, (str(context.user_id), f"Cancelled: {body.cancellation_reason.strip()}", str(context.hospital_id), str(id)))
            updated = cur.fetchone()

            audit_event(
                event_type="TASK_CANCELLED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="care_task",
                target_id=str(id),
                action="CANCEL",
                status="SUCCESS",
            )

            return CareTaskResponse(
                id=updated[0],
                hospital_id=updated[1],
                patient_id=updated[2],
                encounter_id=updated[3],
                task_type=updated[4],
                priority=updated[5],
                status=updated[6],
                title=updated[7],
                description=updated[8],
                patient_instructions=updated[9],
                assigned_role=updated[10],
                assigned_to=updated[11],
                due_date=updated[12],
                completed_by=updated[13],
                completed_at=updated[14],
                completion_notes=updated[15],
                created_at=updated[16],
                updated_at=updated[17],
            )
