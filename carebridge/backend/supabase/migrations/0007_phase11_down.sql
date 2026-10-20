-- Rollback Migration 0007: Phase 11 Insurance & Claims Module
DROP POLICY IF EXISTS tenant_isolation_insurance_claims ON public.insurance_claims;
DROP POLICY IF EXISTS tenant_isolation_patient_insurance ON public.patient_insurance_policies;

DROP TABLE IF EXISTS public.insurance_claims CASCADE;
DROP TABLE IF EXISTS public.patient_insurance_policies CASCADE;
