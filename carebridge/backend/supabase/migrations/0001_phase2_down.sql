-- CareBridge AI — Migration Rollback: 0001_phase2_down.sql
-- Description: Reversible teardown script for Phase 2 schema (local / disposable test DB only)

DROP TRIGGER IF EXISTS trg_protect_profile_privilege_fields ON public.profiles;
DROP FUNCTION IF EXISTS public.protect_profile_privilege_fields();
DROP FUNCTION IF EXISTS public.has_patient_access(UUID, UUID);
DROP FUNCTION IF EXISTS public.is_hospital_staff(UUID);
DROP FUNCTION IF EXISTS public.get_auth_role();
DROP FUNCTION IF EXISTS public.get_auth_hospital_id();

DROP TABLE IF EXISTS public.appointments CASCADE;
DROP TABLE IF EXISTS public.patient_accounts CASCADE;
DROP TABLE IF EXISTS public.patients CASCADE;
DROP TABLE IF EXISTS public.doctors CASCADE;
DROP TABLE IF EXISTS public.profiles CASCADE;
DROP TABLE IF EXISTS public.departments CASCADE;
DROP TABLE IF EXISTS public.hospitals CASCADE;

DROP TYPE IF EXISTS public.account_link_status;
DROP TYPE IF EXISTS public.appointment_status;
DROP TYPE IF EXISTS public.user_role;
