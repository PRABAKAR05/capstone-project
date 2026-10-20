"""Care Coordination Task Service.

Provides helpers for:
- Manual task authoring
- Automated event-driven task generation (post-consultation follow-up, high-priority conflict reconciliation)
- Zero-PHI audit logging
"""

from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from app.core.audit import audit_event


def insert_care_task(
    cur,
    hospital_id: UUID,
    patient_id: UUID,
    title: str,
    description: str,
    task_type: str,
    priority: str = "routine",
    assigned_role: str = "any_staff",
    encounter_id: Optional[UUID] = None,
    patient_instructions: Optional[str] = None,
    assigned_to: Optional[UUID] = None,
    due_date: Optional[datetime] = None,
    actor_id: Optional[UUID] = None,
    actor_role: str = "system",
) -> UUID:
    """Inserts a care task record with tenant isolation and zero-PHI audit logging."""
    task_id = uuid4()
    if not due_date:
        # Default due date: 48 hours for urgent, 5 days for routine
        hours = 48 if priority in ("urgent", "high") else 120
        due_date = datetime.now(timezone.utc) + timedelta(hours=hours)

    cur.execute("""
        INSERT INTO public.care_tasks (
            id, hospital_id, patient_id, encounter_id, task_type,
            priority, status, title, description, patient_instructions,
            assigned_role, assigned_to, due_date
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, 'pending', %s, %s, %s,
            %s, %s, %s
        ) RETURNING id;
    """, (
        str(task_id), str(hospital_id), str(patient_id),
        str(encounter_id) if encounter_id else None, task_type,
        priority, title, description, patient_instructions,
        assigned_role, str(assigned_to) if assigned_to else None,
        due_date,
    ))

    audit_event(
        event_type="TASK_CREATED",
        actor_id=str(actor_id or "00000000-0000-0000-0000-000000000000"),
        actor_role=actor_role,
        hospital_id=str(hospital_id),
        target_resource="care_task",
        target_id=str(task_id),
        action="CREATE",
        status="SUCCESS",
    )

    return task_id


def auto_trigger_post_consultation_task(
    cur,
    hospital_id: UUID,
    patient_id: UUID,
    encounter_id: UUID,
    clinical_notes: Optional[str],
    actor_id: Optional[UUID] = None,
) -> Optional[UUID]:
    """Generates an automated care coordination task following doctor consultation completion."""
    # Check if a task already exists for this encounter
    cur.execute("""
        SELECT id FROM public.care_tasks
        WHERE hospital_id = %s AND encounter_id = %s AND task_type = 'post_op_check';
    """, (str(hospital_id), str(encounter_id)))
    if cur.fetchone():
        return None

    title = "Post-Consultation Patient Check & Care Protocol Follow-Up"
    description = (
        f"Automated care coordination: Attending clinician completed examination. "
        f"Perform 48-hour clinical outreach, assess symptom trajectory, and confirm patient comprehension of care plan."
    )
    patient_instructions = (
        "Please follow your doctor's care guidance and monitor your symptoms. "
        "A member of your clinical care team will check in with you within 48 hours."
    )

    return insert_care_task(
        cur=cur,
        hospital_id=hospital_id,
        patient_id=patient_id,
        title=title,
        description=description,
        task_type="post_op_check",
        priority="routine",
        assigned_role="nurse",
        encounter_id=encounter_id,
        patient_instructions=patient_instructions,
        actor_id=actor_id,
        actor_role="doctor",
    )


def auto_trigger_conflict_reconciliation_task(
    cur,
    hospital_id: UUID,
    patient_id: UUID,
    conflict_id: UUID,
    conflict_title: str,
    review_priority: str,
    actor_id: Optional[UUID] = None,
) -> Optional[UUID]:
    """Generates a high-priority medication reconciliation task upon high review-priority document conflict."""
    # Check if a pending task for this conflict already exists
    title = f"Urgent Care Coordination: Reconcile Medication Discrepancy"
    cur.execute("""
        SELECT id FROM public.care_tasks
        WHERE hospital_id = %s AND patient_id = %s AND task_type = 'medication_reconciliation'
          AND status IN ('pending', 'claimed', 'in_progress');
    """, (str(hospital_id), str(patient_id)))
    if cur.fetchone():
        return None

    description = (
        f"Automated clinical decision support trigger: Phase 7 reconciler identified potential discrepancy ({conflict_title}). "
        f"Review active prescriptions against outside health records and record clinical disposition."
    )
    patient_instructions = (
        "Your clinical care team is reviewing your active medication list. "
        "Please reach out if you have questions before starting any new prescription."
    )

    priority = "urgent" if review_priority == "high" else "high"

    return insert_care_task(
        cur=cur,
        hospital_id=hospital_id,
        patient_id=patient_id,
        title=title,
        description=description,
        task_type="medication_reconciliation",
        priority=priority,
        assigned_role="nurse",
        patient_instructions=patient_instructions,
        actor_id=actor_id,
        actor_role="system",
    )
