-- Phase 9: Prescription Intelligence, Digital Generation & Adherence Tracker Schema

-- 1. Prescriptions Table
CREATE TABLE IF NOT EXISTS public.prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    doctor_id UUID NOT NULL REFERENCES auth.users(id),
    encounter_id UUID REFERENCES public.appointments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'prescribed' CHECK (status IN (
        'prescribed',
        'ready_for_pickup',
        'dispensed',
        'completed',
        'discontinued'
    )),
    diagnosis_context TEXT,
    notes TEXT,
    discontinuation_rationale TEXT,
    verification_hash TEXT NOT NULL,  -- Format: "v1:<hex_hmac_sha256>"
    issued_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    valid_until TIMESTAMPTZ NOT NULL,
    dispensed_by UUID REFERENCES auth.users(id),
    dispensed_at TIMESTAMPTZ,
    dispensing_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_prescriptions_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_prescriptions_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_prescriptions_tenant_patient 
    ON public.prescriptions(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_tenant_status 
    ON public.prescriptions(hospital_id, status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor 
    ON public.prescriptions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_verification_hash
    ON public.prescriptions(verification_hash);

-- 2. Prescription Items Table
CREATE TABLE IF NOT EXISTS public.prescription_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    prescription_id UUID NOT NULL,
    drug_name TEXT NOT NULL,
    therapeutic_class TEXT,
    dosage TEXT NOT NULL,
    route TEXT NOT NULL DEFAULT 'oral',
    frequency TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    instructions TEXT NOT NULL,
    refills_remaining INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_prescription_items_parent FOREIGN KEY (hospital_id, prescription_id)
        REFERENCES public.prescriptions(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_prescription_items_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_prescription_items_parent 
    ON public.prescription_items(hospital_id, prescription_id);

-- 3. Medication Adherence Logs Table
CREATE TABLE IF NOT EXISTS public.medication_adherence_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    prescription_item_id UUID NOT NULL,
    scheduled_time TIMESTAMPTZ NOT NULL,
    taken_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('taken', 'skipped', 'late', 'missed')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_adherence_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_adherence_item FOREIGN KEY (hospital_id, prescription_item_id)
        REFERENCES public.prescription_items(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_adherence_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_adherence_patient_time 
    ON public.medication_adherence_logs(hospital_id, patient_id, scheduled_time);

-- 4. Enable Row-Level Security
ALTER TABLE public.prescriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prescriptions FORCE ROW LEVEL SECURITY;

ALTER TABLE public.prescription_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prescription_items FORCE ROW LEVEL SECURITY;

ALTER TABLE public.medication_adherence_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medication_adherence_logs FORCE ROW LEVEL SECURITY;

-- 5. RLS Policies: prescriptions
DROP POLICY IF EXISTS prescriptions_select ON public.prescriptions;
CREATE POLICY prescriptions_select ON public.prescriptions
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS prescriptions_insert ON public.prescriptions;
CREATE POLICY prescriptions_insert ON public.prescriptions
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

DROP POLICY IF EXISTS prescriptions_update ON public.prescriptions;
CREATE POLICY prescriptions_update ON public.prescriptions
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- 6. RLS Policies: prescription_items
DROP POLICY IF EXISTS prescription_items_select ON public.prescription_items;
CREATE POLICY prescription_items_select ON public.prescription_items
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR EXISTS (
                SELECT 1 FROM public.prescriptions p 
                WHERE p.id = prescription_id 
                AND public.has_patient_access(p.hospital_id, p.patient_id)
            )
        )
    );

DROP POLICY IF EXISTS prescription_items_insert ON public.prescription_items;
CREATE POLICY prescription_items_insert ON public.prescription_items
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- 7. RLS Policies: medication_adherence_logs
DROP POLICY IF EXISTS adherence_logs_select ON public.medication_adherence_logs;
CREATE POLICY adherence_logs_select ON public.medication_adherence_logs
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS adherence_logs_insert ON public.medication_adherence_logs;
CREATE POLICY adherence_logs_insert ON public.medication_adherence_logs
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS adherence_logs_update ON public.medication_adherence_logs;
CREATE POLICY adherence_logs_update ON public.medication_adherence_logs
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

-- 8. Grants
GRANT SELECT, INSERT, UPDATE ON public.prescriptions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.prescription_items TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.medication_adherence_logs TO authenticated;
GRANT ALL ON public.prescriptions TO service_role;
GRANT ALL ON public.prescription_items TO service_role;
GRANT ALL ON public.medication_adherence_logs TO service_role;
