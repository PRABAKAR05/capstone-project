-- CareBridge AI — Migration Rollback: 0008_phase15_down.sql
-- Description: Revert Phase 15 constraints, triggers, and restore exact original pre-migration definitions. No DROP CASCADE.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

-- 1. Restore exact original is_hospital_staff definition and permissions
CREATE OR REPLACE FUNCTION public.is_hospital_staff(check_hospital_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.profiles p
        WHERE p.id = (SELECT auth.uid())
          AND p.hospital_id = check_hospital_id
          AND p.role IN ('hospital_admin', 'doctor', 'nurse', 'receptionist', 'lab_technician')
          AND p.is_active = true
    );
$$;
GRANT EXECUTE ON FUNCTION public.is_hospital_staff(UUID) TO anon, authenticated, service_role;

-- 2. Restore exact original care_tasks assigned_role constraint
ALTER TABLE public.care_tasks DROP CONSTRAINT IF EXISTS care_tasks_assigned_role_check;
ALTER TABLE public.care_tasks ADD CONSTRAINT care_tasks_assigned_role_check 
    CHECK (assigned_role IN ('doctor', 'nurse', 'case_manager', 'receptionist', 'any_staff'));

-- 3. Remove canonical role triggers and constraints on profiles
DROP TRIGGER IF EXISTS trg_profiles_canonical_role ON public.profiles;
DROP FUNCTION IF EXISTS public.trg_enforce_canonical_profiles();
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS check_profiles_canonical_role;

-- 4. Remove triggers and restore exact original patient_accounts relationship check
DROP TRIGGER IF EXISTS trg_patient_accounts_self ON public.patient_accounts;
DROP FUNCTION IF EXISTS public.trg_patient_accounts_self_only();
ALTER TABLE public.patient_accounts DROP CONSTRAINT IF EXISTS patient_accounts_relationship_check;
ALTER TABLE public.patient_accounts ADD CONSTRAINT patient_accounts_relationship_check
    CHECK (relationship IN ('self', 'parent', 'guardian', 'caregiver', 'spouse'));

-- 5. Drop administrative correction procedure, helper, tables, and schema in reverse dependency order (No CASCADE)
DROP FUNCTION IF EXISTS public.admin_correct_historical_record(TEXT, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT);
DROP FUNCTION IF EXISTS carebridge_internal.is_correction_authorized(UUID, TEXT);
DROP TABLE IF EXISTS carebridge_internal.active_corrections;
DROP TABLE IF EXISTS carebridge_internal.auth_secrets;
DROP SCHEMA IF EXISTS carebridge_internal;
DROP TABLE IF EXISTS public.audit_logs;

COMMIT;
