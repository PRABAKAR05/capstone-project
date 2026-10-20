-- CareBridge AI — Migration Rollback: 0002_phase3_down.sql
-- Description: Reversible teardown for migration 0002

DROP POLICY IF EXISTS patient_accounts_update ON public.patient_accounts;
CREATE POLICY patient_accounts_update ON public.patient_accounts
FOR UPDATE TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR user_id = (SELECT auth.uid())
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
);

DROP POLICY IF EXISTS patient_accounts_select ON public.patient_accounts;
CREATE POLICY patient_accounts_select ON public.patient_accounts
FOR SELECT TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR user_id = (SELECT auth.uid())
);

DROP FUNCTION IF EXISTS public.is_patient_record_owner(UUID, UUID);

ALTER TABLE public.hospitals 
DROP COLUMN IF EXISTS timezone;
