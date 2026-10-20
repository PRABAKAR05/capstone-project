-- ==============================================================================
-- CareBridge AI — Migration 0007: Phase 11 Insurance & Claims Module
-- ==============================================================================

-- 1. Patient Insurance Policies
CREATE TABLE IF NOT EXISTS public.patient_insurance_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE RESTRICT,
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
    provider_name VARCHAR(150) NOT NULL, -- e.g. 'Star Health', 'PM-JAY Ayushman Bharat'
    policy_number VARCHAR(100) NOT NULL,
    policy_holder_name VARCHAR(150) NOT NULL,
    relation_to_patient VARCHAR(50) DEFAULT 'self',
    sum_insured_inr NUMERIC(12, 2) NOT NULL DEFAULT 500000.00,
    remaining_balance_inr NUMERIC(12, 2) NOT NULL DEFAULT 500000.00,
    copay_percentage NUMERIC(5, 2) NOT NULL DEFAULT 10.00,
    deductible_inr NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 2. Insurance Claims & Pre-Authorizations
CREATE TABLE IF NOT EXISTS public.insurance_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE RESTRICT,
    policy_id UUID NOT NULL REFERENCES public.patient_insurance_policies(id) ON DELETE RESTRICT,
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES public.appointments(id) ON DELETE SET NULL,
    claim_type VARCHAR(50) NOT NULL CHECK (claim_type IN ('pre_auth', 'reimbursement', 'cashless_settlement')),
    requested_amount_inr NUMERIC(12, 2) NOT NULL,
    approved_amount_inr NUMERIC(12, 2) DEFAULT 0.00,
    patient_copay_amount_inr NUMERIC(12, 2) DEFAULT 0.00,
    adjudication_status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (
        adjudication_status IN ('draft', 'pre_auth_requested', 'pre_auth_approved', 'pre_auth_denied', 'claim_submitted', 'settled', 'rejected')
    ),
    denial_reason TEXT,
    settlement_reference VARCHAR(100),
    adjudicated_by UUID,
    adjudicated_at TIMESTAMPTZ,
    rule_version VARCHAR(20) DEFAULT 'v1.0',
    calculation_breakdown JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- Indexes for tenant and patient lookups
CREATE INDEX IF NOT EXISTS idx_patient_insurance_tenant_patient 
    ON public.patient_insurance_policies (hospital_id, patient_id);

CREATE INDEX IF NOT EXISTS idx_insurance_claims_tenant_status 
    ON public.insurance_claims (hospital_id, adjudication_status);

CREATE INDEX IF NOT EXISTS idx_insurance_claims_tenant_patient 
    ON public.insurance_claims (hospital_id, patient_id);

-- Enable Row-Level Security (RLS)
ALTER TABLE public.patient_insurance_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insurance_claims ENABLE ROW LEVEL SECURITY;

-- RLS Policies for patient_insurance_policies
DROP POLICY IF EXISTS tenant_isolation_patient_insurance ON public.patient_insurance_policies;
DROP POLICY IF EXISTS patient_insurance_policies_select ON public.patient_insurance_policies;
CREATE POLICY patient_insurance_policies_select ON public.patient_insurance_policies
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS patient_insurance_policies_insert ON public.patient_insurance_policies;
CREATE POLICY patient_insurance_policies_insert ON public.patient_insurance_policies
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS patient_insurance_policies_update ON public.patient_insurance_policies;
CREATE POLICY patient_insurance_policies_update ON public.patient_insurance_policies
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- RLS Policies for insurance_claims
DROP POLICY IF EXISTS tenant_isolation_insurance_claims ON public.insurance_claims;
DROP POLICY IF EXISTS insurance_claims_select ON public.insurance_claims;
CREATE POLICY insurance_claims_select ON public.insurance_claims
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS insurance_claims_insert ON public.insurance_claims;
CREATE POLICY insurance_claims_insert ON public.insurance_claims
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS insurance_claims_update ON public.insurance_claims;
CREATE POLICY insurance_claims_update ON public.insurance_claims
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );
