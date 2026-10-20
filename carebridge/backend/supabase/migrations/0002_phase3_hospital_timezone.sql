-- CareBridge AI — Migration: 0002_phase3_hospital_timezone.sql
-- Description: Add IANA timezone column to hospitals table with default 'Asia/Kolkata' and enable patient-owned caregiver revocation

ALTER TABLE public.hospitals 
ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata';

-- Function: Check if user owns the authoritative patient record (verified 'self' account)
CREATE OR REPLACE FUNCTION public.is_patient_record_owner(check_hospital_id UUID, check_patient_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.patient_accounts pa
        WHERE pa.hospital_id = check_hospital_id
          AND pa.user_id = (SELECT auth.uid())
          AND pa.patient_id = check_patient_id
          AND pa.relationship = 'self'
          AND pa.status = 'verified'
    );
$$;

GRANT EXECUTE ON FUNCTION public.is_patient_record_owner(UUID, UUID) TO authenticated;

-- Update RLS policies on patient_accounts to permit patient-owned caregiver revocation and review
DROP POLICY IF EXISTS patient_accounts_select ON public.patient_accounts;
CREATE POLICY patient_accounts_select ON public.patient_accounts
FOR SELECT TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR user_id = (SELECT auth.uid())
    OR public.is_patient_record_owner(hospital_id, patient_id)
);

DROP POLICY IF EXISTS patient_accounts_update ON public.patient_accounts;
CREATE POLICY patient_accounts_update ON public.patient_accounts
FOR UPDATE TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR user_id = (SELECT auth.uid())
    OR public.is_patient_record_owner(hospital_id, patient_id)
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
);
