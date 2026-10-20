-- Phase 8: Care Coordination Workflows & Multi-Disciplinary Task Engine Schema

-- 1. Care Tasks Table
CREATE TABLE IF NOT EXISTS public.care_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    encounter_id UUID REFERENCES public.appointments(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL CHECK (task_type IN (
        'discharge_follow_up',
        'post_op_check',
        'medication_reconciliation',
        'specialist_referral',
        'lab_review',
        'patient_outreach',
        'caregiver_briefing',
        'other'
    )),
    priority TEXT NOT NULL CHECK (priority IN ('urgent', 'high', 'routine', 'low')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending',
        'claimed',
        'in_progress',
        'completed',
        'cancelled'
    )),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    patient_instructions TEXT,  -- Patient-facing actionable phrasing (NULL if internal only)
    assigned_role TEXT NOT NULL CHECK (assigned_role IN ('doctor', 'nurse', 'case_manager', 'receptionist', 'any_staff')),
    assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    due_date TIMESTAMPTZ,
    completed_by UUID REFERENCES auth.users(id),
    completed_at TIMESTAMPTZ,
    completion_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_care_tasks_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_care_tasks_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_patient 
    ON public.care_tasks(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_status 
    ON public.care_tasks(hospital_id, status);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_role 
    ON public.care_tasks(hospital_id, assigned_role);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_assigned_to 
    ON public.care_tasks(hospital_id, assigned_to);

-- 2. Enable RLS
ALTER TABLE public.care_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.care_tasks FORCE ROW LEVEL SECURITY;

-- 3. RLS Policies for care_tasks
DROP POLICY IF EXISTS care_tasks_select ON public.care_tasks;
CREATE POLICY care_tasks_select ON public.care_tasks
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR (
                public.has_patient_access(hospital_id, patient_id)
                AND patient_instructions IS NOT NULL
            )
        )
    );

DROP POLICY IF EXISTS care_tasks_insert ON public.care_tasks;
CREATE POLICY care_tasks_insert ON public.care_tasks
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

DROP POLICY IF EXISTS care_tasks_update ON public.care_tasks;
CREATE POLICY care_tasks_update ON public.care_tasks
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- Grants
GRANT SELECT, INSERT, UPDATE ON public.care_tasks TO authenticated;
GRANT ALL ON public.care_tasks TO service_role;
