-- CareBridge AI — Migration: 0008_phase15_retire_roles.sql
-- Description: Deprecate 'receptionist' and 'caregiver', enforce 5 canonical roles, freeze historical rows, update security functions, constraints, triggers, and DAC procedure.

BEGIN;

-- Configure strict DDL timeouts to prevent hung locks
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

-- ============================================================================
-- 0. Private DAC Schema & Transaction-Bound Correction Table
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS carebridge_internal;
REVOKE ALL ON SCHEMA carebridge_internal FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA carebridge_internal TO postgres;

-- Transaction-bound correction table: strictly private to executing transaction XID
CREATE TABLE IF NOT EXISTS carebridge_internal.active_corrections (
    xid BIGINT NOT NULL,
    record_id UUID NOT NULL,
    operation TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp(),
    PRIMARY KEY (xid, record_id, operation)
);
REVOKE ALL ON TABLE carebridge_internal.active_corrections FROM PUBLIC, anon, authenticated, service_role;
GRANT ALL ON TABLE carebridge_internal.active_corrections TO postgres;

-- Key table strictly managed out-of-band; zero hardcoded secrets in DDL
CREATE TABLE IF NOT EXISTS carebridge_internal.auth_secrets (
    key_name TEXT PRIMARY KEY,
    secret_value TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
    rotated_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);
REVOKE ALL ON TABLE carebridge_internal.auth_secrets FROM PUBLIC, anon, authenticated, service_role;
GRANT ALL ON TABLE carebridge_internal.auth_secrets TO postgres;

-- Tier 1 Authoritative Database Audit Log Table
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    actor_id UUID,
    target_entity TEXT NOT NULL,
    target_id UUID,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.audit_logs TO authenticated;
GRANT ALL ON public.audit_logs TO postgres;

-- Fail closed if dba_hmac_key was not provisioned out-of-band prior to migration
DO $$
DECLARE
    v_secret TEXT;
BEGIN
    SELECT secret_value INTO v_secret 
    FROM carebridge_internal.auth_secrets 
    WHERE key_name = 'dba_hmac_key';

    IF v_secret IS NULL OR length(v_secret) < 64 THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: dba_hmac_key is missing or has insufficient entropy (<64 hex chars). Out-of-band provisioning required before migration.';
    END IF;
END $$;

-- Transaction-bound, safely owned SECURITY DEFINER helper function for trigger checks
CREATE OR REPLACE FUNCTION carebridge_internal.is_correction_authorized(p_record_id UUID, p_operation TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, carebridge_internal, pg_temp
AS $$
DECLARE
    v_found BOOLEAN;
BEGIN
    -- Match strictly on current transaction ID, target record, and expected operation
    SELECT EXISTS (
        SELECT 1 FROM carebridge_internal.active_corrections
        WHERE xid = txid_current() 
          AND record_id = p_record_id 
          AND operation = p_operation
    ) INTO v_found;

    -- If authorized, consume immediately within this transaction
    IF v_found THEN
        DELETE FROM carebridge_internal.active_corrections
        WHERE xid = txid_current() 
          AND record_id = p_record_id 
          AND operation = p_operation;
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$;

REVOKE ALL ON FUNCTION carebridge_internal.is_correction_authorized(UUID, TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION carebridge_internal.is_correction_authorized(UUID, TEXT) TO authenticated, service_role, postgres;

-- ============================================================================
-- 1. Update Security Function: is_hospital_staff
-- ============================================================================
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
          AND p.role IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician')
          AND p.is_active = true
    );
$$;

-- ============================================================================
-- 2. Update care_tasks Constraint & Semantic Reassignment of Receptionist Tasks
-- ============================================================================
UPDATE public.care_tasks
SET assigned_role = CASE
        -- Intake, scheduling, discharge follow-up, insurance intake -> case_manager
        WHEN task_type IN ('intake', 'scheduling', 'discharge_coordination', 'insurance_followup')
             OR title ILIKE '%schedule%' OR title ILIKE '%intake%' OR title ILIKE '%insurance%' OR title ILIKE '%coordination%'
            THEN 'case_manager'
        -- Direct patient check-in triage, vital prep -> nurse
        WHEN task_type IN ('triage', 'vital_prep', 'clinical_prep')
             OR title ILIKE '%triage%' OR title ILIKE '%vital%' OR title ILIKE '%prep%'
            THEN 'nurse'
        -- General facility desk / operational tasks -> any_staff
        ELSE 'any_staff'
    END,
    description = CASE 
        WHEN description IS NULL OR trim(description) = '' 
            THEN '[Migrated from retired receptionist queue]'
        ELSE description || ' [Migrated from retired receptionist queue]'
    END
WHERE assigned_role = 'receptionist';

ALTER TABLE public.care_tasks DROP CONSTRAINT IF EXISTS care_tasks_assigned_role_check;
ALTER TABLE public.care_tasks ADD CONSTRAINT care_tasks_assigned_role_check 
    CHECK (assigned_role IN ('doctor', 'nurse', 'case_manager', 'any_staff'));

-- ============================================================================
-- 3. Transition patient_accounts Caregiver Links & Restrict Relationships
-- ============================================================================
UPDATE public.patient_accounts
SET status = 'revoked',
    verified_at = NULL,
    verified_by = NULL
WHERE relationship != 'self'
  AND status != 'revoked';

ALTER TABLE public.patient_accounts DROP CONSTRAINT IF EXISTS patient_accounts_relationship_check;
ALTER TABLE public.patient_accounts ADD CONSTRAINT patient_accounts_relationship_check
    CHECK (
        (relationship = 'self') OR
        (status = 'revoked' AND relationship IN ('caregiver', 'parent', 'guardian', 'spouse'))
    );

-- Trigger strictly forbidding non-self links, blocking deletes on all rows, enforcing disjunctive three-path self-link authorization across all paths
CREATE OR REPLACE FUNCTION public.trg_patient_accounts_self_only()
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, carebridge_internal, pg_temp
AS $$
DECLARE
    current_actor UUID;
    v_actor_role public.user_role;
    v_actor_hospital UUID;
    v_actor_active BOOLEAN;
    v_patient_hospital UUID;
BEGIN
    -- Check transaction-bound DAC helper function
    IF carebridge_internal.is_correction_authorized(OLD.id, 'RECTIFY_PATIENT_ACCOUNT_METADATA') THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END IF;

    -- 1. DELETE Protection: Block deletion of ANY patient_accounts record (self or non-self)
    IF TG_OP = 'DELETE' THEN
        IF OLD.relationship != 'self' THEN
            RAISE EXCEPTION 'HISTORICAL_LINK_IMMUTABLE: Historical non-self account link % is frozen and cannot be deleted.', OLD.id;
        ELSE
            RAISE EXCEPTION 'PATIENT_LINK_CANNOT_BE_DELETED: Patient self-account link % is permanent and cannot be deleted.', OLD.id;
        END IF;
    END IF;

    -- 2. INSERT Protection (Three Explicit, Disjunctive Authorization Paths):
    IF TG_OP = 'INSERT' THEN
        -- Relationship MUST be 'self'
        IF NEW.relationship != 'self' THEN
            RAISE EXCEPTION 'RELATIONSHIP_VIOLATION: Only relationship = self is permitted for new patient accounts.';
        END IF;

        current_actor := auth.uid();

        -- Path A: Direct Superuser Database Context (auth.uid() IS NULL)
        IF current_actor IS NULL THEN
            -- Strictly fail closed: Block PostgREST API requests and non-superuser sessions
            IF nullif(current_setting('request.jwt.claim.role', true), '') IS NOT NULL 
               OR SESSION_USER NOT IN ('postgres', 'supabase_admin') 
               OR CURRENT_USER NOT IN ('postgres', 'supabase_admin') THEN
                RAISE EXCEPTION 'UNAUTHORIZED_ACCOUNT_BINDING: Null-identity insertion is prohibited. PostgREST API requests and non-superuser sessions cannot create patient account links without an authenticated user context.';
            END IF;

        -- Path B & C: Authenticated User Context (auth.uid() IS NOT NULL)
        ELSE
            SELECT role, hospital_id, is_active 
            INTO v_actor_role, v_actor_hospital, v_actor_active
            FROM public.profiles 
            WHERE id = current_actor;

            -- Path B: Patient Self-Service Registration
            IF v_actor_role = 'patient' THEN
                -- Must bind strictly to caller's own auth user ID
                IF NEW.user_id != current_actor THEN
                    RAISE EXCEPTION 'UNAUTHORIZED_ACCOUNT_BINDING: Patients can only create self-links for their own authenticated user ID.';
                END IF;
                -- Patients can NEVER self-insert with status = 'verified'
                IF NEW.status != 'pending_verification' THEN
                    RAISE EXCEPTION 'STATUS_ESCALATION_PROHIBITED: Patient self-service registration must have status = pending_verification.';
                END IF;
                -- Patients cannot supply verification audit fields
                IF NEW.verified_by IS NOT NULL OR NEW.verified_at IS NOT NULL THEN
                    RAISE EXCEPTION 'STATUS_ESCALATION_PROHIBITED: Patient self-service registration cannot specify verification audit fields.';
                END IF;

            -- Path C: Hospital Staff Desk Registration (hospital_admin or nurse)
            ELSIF v_actor_role IN ('hospital_admin', 'nurse') AND v_actor_active = true THEN
                SELECT hospital_id INTO v_patient_hospital FROM public.patients WHERE id = NEW.patient_id;
                IF v_actor_hospital != v_patient_hospital THEN
                    RAISE EXCEPTION 'CROSS_TENANT_VIOLATION: Staff cannot create patient links outside their own hospital.';
                END IF;
                
                -- If staff inserts pre-verified link, verified_by must match the acting staff member
                IF NEW.status = 'verified' THEN
                    IF NEW.verified_by IS NULL OR NEW.verified_by != current_actor THEN
                        RAISE EXCEPTION 'INVALID_VERIFIER: Verified link created by staff must set verified_by to the acting staff member ID.';
                    END IF;
                    IF NEW.verified_at IS NULL THEN
                        NEW.verified_at := timezone('utc', now());
                    END IF;
                END IF;

            -- All other roles (doctor, lab_technician, inactive staff) are blocked from creating patient account links
            ELSE
                RAISE EXCEPTION 'UNAUTHORIZED_ACCOUNT_BINDING: Role % is not authorized to create patient account links.', v_actor_role;
            END IF;
        END IF;

        -- Enforce 1:1 patient account isolation across all paths
        IF EXISTS (
            SELECT 1 FROM public.patient_accounts 
            WHERE patient_id = NEW.patient_id 
              AND relationship = 'self' 
              AND status IN ('verified', 'pending_verification')
        ) THEN
            RAISE EXCEPTION 'PATIENT_ALREADY_LINKED: Patient record % already has an active or pending self-link.', NEW.patient_id;
        END IF;
    END IF;

    -- 3. UPDATE Protection: Historical non-self records are strictly immutable
    IF TG_OP = 'UPDATE' AND OLD.relationship != 'self' THEN
        RAISE EXCEPTION 'HISTORICAL_LINK_IMMUTABLE: Historical non-self account link % is frozen and cannot be modified.', OLD.id;
    END IF;

    -- 4. UPDATE Protection on Self-Links:
    IF TG_OP = 'UPDATE' THEN
        -- 4a. Identity columns (id, user_id, patient_id) are strictly immutable
        IF NEW.id != OLD.id OR NEW.user_id != OLD.user_id OR NEW.patient_id != OLD.patient_id THEN
            RAISE EXCEPTION 'IDENTITY_IMMUTABLE: Identity columns (id, user_id, patient_id) cannot be modified on patient_accounts.';
        END IF;

        -- 4b. Relationship must remain 'self'
        IF NEW.relationship != 'self' THEN
            RAISE EXCEPTION 'RELATIONSHIP_VIOLATION: Cannot modify relationship from self to %.', NEW.relationship;
        END IF;

        -- 4c. Verified status cannot have NULL verified_by
        IF NEW.status = 'verified' AND NEW.verified_by IS NULL THEN
            RAISE EXCEPTION 'STATUS_ESCALATION_PROHIBITED: Status cannot be set to verified without verified_by.';
        END IF;
    END IF;

    -- 5. Unified Verifier Validation on Status Transitions to 'verified' (from pending or revoked):
    IF TG_OP = 'UPDATE' AND NEW.status = 'verified' AND OLD.status != 'verified' THEN
        current_actor := auth.uid();
        
        -- Prevent patient self-verification or self-reactivation
        IF current_actor IS NOT NULL AND current_actor = NEW.user_id THEN
            RAISE EXCEPTION 'STATUS_ESCALATION_PROHIBITED: Patients cannot self-verify their own patient accounts.';
        END IF;

        -- verified_by must be explicitly present
        IF NEW.verified_by IS NULL THEN
            RAISE EXCEPTION 'STATUS_ESCALATION_PROHIBITED: Status cannot be set to verified without verified_by.';
        END IF;

        -- Rigorous Verifier Validation across ALL paths:
        -- verified_by MUST be an active staff member (hospital_admin or nurse) in the patient's hospital
        IF NOT EXISTS (
            SELECT 1 
            FROM public.profiles v
            JOIN public.patients p ON p.id = NEW.patient_id
            WHERE v.id = NEW.verified_by
              AND v.hospital_id = p.hospital_id
              AND v.is_active = true
              AND v.role IN ('hospital_admin', 'nurse')
        ) THEN
            RAISE EXCEPTION 'INVALID_VERIFIER: verified_by % must be an active hospital_admin or nurse in the patient hospital.', NEW.verified_by;
        END IF;

        IF NEW.verified_at IS NULL THEN
            NEW.verified_at := timezone('utc', now());
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_patient_accounts_self ON public.patient_accounts;
CREATE TRIGGER trg_patient_accounts_self
    BEFORE INSERT OR UPDATE OR DELETE ON public.patient_accounts
    FOR EACH ROW
    EXECUTE FUNCTION public.trg_patient_accounts_self_only();

-- ============================================================================
-- 4. Safe, Deterministic Receptionist Profile Migration & Canonical Enforcement
-- ============================================================================
-- Step 4a: Precondition check and deterministic migration of designated synthetic evaluation account
DO $$
DECLARE
    matched_id UUID;
    match_count INT;
BEGIN
    SELECT count(*), max(id::text)::uuid INTO match_count, matched_id
    FROM public.profiles
    WHERE id = '11111111-0003-0000-0000-000000000032'
      AND email IN ('rec1@aegis.example.com', 'syn.receptionist@carebridge.test')
      AND role = 'receptionist';

    IF match_count != 1 THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: Expected exactly 1 synthetic receptionist profile matching ID and email, found %', match_count;
    END IF;

    UPDATE public.profiles
    SET role = 'nurse',
        full_name = full_name || ' (Charge Nurse)',
        updated_at = timezone('utc', now())
    WHERE id = matched_id;
END $$;

-- Step 4b: Deactivate any remaining receptionist accounts cleanly without modifying role
UPDATE public.profiles
SET is_active = false,
    updated_at = timezone('utc', now())
WHERE role = 'receptionist';

-- Step 4c: Add composite check constraint for active profiles
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS check_profiles_canonical_role;
ALTER TABLE public.profiles ADD CONSTRAINT check_profiles_canonical_role
    CHECK (
        (is_active = false AND role = 'receptionist') OR
        (role IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician', 'patient'))
    );

-- Step 4d: Trigger enforcing canonical roles, unforgeable role authorization, freezing legacy accounts, and blocking privilege escalation on INSERT
CREATE OR REPLACE FUNCTION public.trg_enforce_canonical_profiles()
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, carebridge_internal, pg_temp
AS $$
DECLARE
    current_actor UUID;
    v_actor_role public.user_role;
    v_actor_hospital UUID;
    v_actor_active BOOLEAN;
BEGIN
    -- Check transaction-bound DAC helper function
    IF carebridge_internal.is_correction_authorized(OLD.id, 'RECTIFY_LEGACY_PROFILE_METADATA') 
       OR carebridge_internal.is_correction_authorized(OLD.id, 'ANONYMIZE_LEGACY_PROFILE_PII') THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END IF;

    -- 1. Block DELETE of any legacy profile with a retired role
    IF TG_OP = 'DELETE' AND OLD.role NOT IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician', 'patient') THEN
        RAISE EXCEPTION 'CANONICAL_ROLE_VIOLATION: Legacy profile % with retired role % is immutable and cannot be deleted.', OLD.id, OLD.role;
    END IF;

    -- 2. Block ANY update to an existing row that has a retired role (strictly frozen)
    IF TG_OP = 'UPDATE' AND OLD.role NOT IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician', 'patient') THEN
        RAISE EXCEPTION 'CANONICAL_ROLE_VIOLATION: Legacy profile % with retired role % is immutable and cannot be updated.', OLD.id, OLD.role;
    END IF;

    -- 3. Strict Profile INSERT Authorization (Preventing Privilege Escalation on Signup/Creation)
    IF TG_OP = 'INSERT' THEN
        -- 3a. Reject retired roles outright
        IF NEW.role NOT IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician', 'patient') THEN
            RAISE EXCEPTION 'CANONICAL_ROLE_VIOLATION: Role % is retired and prohibited for new profiles.', NEW.role;
        END IF;

        current_actor := auth.uid();

        -- Case 1: Headless / Direct Database Context (auth.uid() IS NULL)
        IF current_actor IS NULL THEN
            -- Strictly fail closed: Block PostgREST API requests and non-superuser sessions
            IF nullif(current_setting('request.jwt.claim.role', true), '') IS NOT NULL 
               OR SESSION_USER NOT IN ('postgres', 'supabase_admin') 
               OR CURRENT_USER NOT IN ('postgres', 'supabase_admin') THEN
                RAISE EXCEPTION 'UNAUTHORIZED_PROFILE_CREATION: Direct profile insertion without authenticated actor requires direct postgres or supabase_admin database session.';
            END IF;

        -- Case 2: Authenticated User Context (auth.uid() IS NOT NULL)
        ELSE
            -- Identity binding: When a user creates their own profile (e.g. self-service signup)
            IF NEW.id = current_actor THEN
                -- Users registering themselves can ONLY register with role = 'patient'
                IF NEW.role != 'patient' THEN
                    RAISE EXCEPTION 'UNAUTHORIZED_PROFILE_CREATION: Self-service registration can only create profiles with role = patient. Cannot self-assign role %.', NEW.role;
                END IF;
            ELSE
                -- Staff/Admin user provisioning another user's profile
                -- Actor MUST be an active hospital_admin in the SAME hospital
                IF NOT EXISTS (
                    SELECT 1 FROM public.profiles
                    WHERE id = current_actor
                      AND hospital_id = NEW.hospital_id
                      AND role = 'hospital_admin'
                      AND is_active = true
                ) THEN
                    RAISE EXCEPTION 'CROSS_TENANT_VIOLATION: Creating staff profiles or profiles for other users requires active hospital_admin credentials in the target hospital.';
                END IF;
            END IF;
        END IF;
    END IF;

    -- 4. Block modifying a canonical role to a retired role
    IF TG_OP = 'UPDATE' AND NEW.role NOT IN ('hospital_admin', 'doctor', 'nurse', 'lab_technician', 'patient') THEN
        RAISE EXCEPTION 'CANONICAL_ROLE_VIOLATION: Cannot modify role to retired role %.', NEW.role;
    END IF;

    -- 5. Role Modification Authorization Check (Fail-Closed, Kernel-Level Role Identity):
    IF TG_OP = 'UPDATE' AND NEW.role != OLD.role THEN
        current_actor := auth.uid();
        
        -- If running without Supabase JWT context:
        IF current_actor IS NULL THEN
            -- Only direct connections by PostgreSQL superuser / DBA roles are authorized
            IF nullif(current_setting('request.jwt.claim.role', true), '') IS NOT NULL 
               OR SESSION_USER NOT IN ('postgres', 'supabase_admin') 
               OR CURRENT_USER NOT IN ('postgres', 'supabase_admin') THEN
                RAISE EXCEPTION 'UNAUTHORIZED_ROLE_CHANGE: Missing authenticated actor context. Direct role changes require postgres or supabase_admin database session.';
            END IF;
        ELSE
            -- When running via Supabase JWT context (authenticated, anon):
            -- A user can NEVER change or promote their own role
            IF current_actor = OLD.id THEN
                RAISE EXCEPTION 'UNAUTHORIZED_ROLE_CHANGE: Users cannot modify or promote their own role.';
            END IF;
            
            -- Actor MUST be an active hospital_admin in the same hospital
            IF NOT EXISTS (
                SELECT 1 FROM public.profiles
                WHERE id = current_actor
                  AND hospital_id = OLD.hospital_id
                  AND role = 'hospital_admin'
                  AND is_active = true
            ) THEN
                RAISE EXCEPTION 'CROSS_TENANT_VIOLATION: Only active hospital_admin in the patient hospital can modify user roles.';
            END IF;
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_profiles_canonical_role ON public.profiles;
CREATE TRIGGER trg_profiles_canonical_role
    BEFORE INSERT OR UPDATE OR DELETE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.trg_enforce_canonical_profiles();

-- ============================================================================
-- 5. Locked-Down Administrative Correction Procedure
-- ============================================================================
CREATE OR REPLACE FUNCTION public.admin_correct_historical_record(
    p_operation TEXT,
    p_record_id UUID,
    p_new_value TEXT,
    p_justification TEXT,
    p_ticket_id TEXT,
    p_timestamp TIMESTAMPTZ,
    p_dba_signature TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, carebridge_internal, pg_temp
AS $$
DECLARE
    actor_id UUID;
    v_actor_hospital UUID;
    v_target_hospital UUID;
    v_actor_desc TEXT;
    v_secret TEXT;
    v_ts_str TEXT;
    v_payload TEXT;
    v_expected_signature TEXT;
    old_data JSONB;
BEGIN
    -- 0. Concurrency Serialization: Acquire transaction-scoped exclusive advisory lock on the target record
    PERFORM pg_advisory_xact_lock(hashtext('admin_correction:' || p_record_id::text));

    -- 0a. Strict Precondition Validation on ALL Signed Parameters (Eliminating NULL-propagation vulnerabilities)
    IF p_ticket_id IS NULL OR length(trim(p_ticket_id)) < 4 THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: Valid p_ticket_id (min 4 chars) is required and cannot be null.';
    END IF;
    IF p_operation IS NULL OR length(trim(p_operation)) = 0 THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: p_operation cannot be null or empty.';
    END IF;
    IF p_record_id IS NULL THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: p_record_id cannot be null.';
    END IF;
    IF p_new_value IS NULL THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: p_new_value cannot be null.';
    END IF;
    IF p_justification IS NULL OR length(trim(p_justification)) < 10 THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: Detailed p_justification (min 10 chars) is required and cannot be null.';
    END IF;
    IF p_timestamp IS NULL THEN
        RAISE EXCEPTION 'PRECONDITION_FAILED: p_timestamp cannot be null.';
    END IF;

    -- 0b. Strict Operation Whitelist (Zero Dynamic SQL)
    IF p_operation NOT IN ('RECTIFY_LEGACY_PROFILE_METADATA', 'ANONYMIZE_LEGACY_PROFILE_PII', 'RECTIFY_PATIENT_ACCOUNT_METADATA') THEN
        RAISE EXCEPTION 'INVALID_OPERATION: Operation % is not permitted. Only predefined statutory rectifications allowed.', p_operation;
    END IF;

    actor_id := auth.uid();
    
    -- 1. Dual-Context Authorization & Tenant Boundary Enforcement:
    IF actor_id IS NOT NULL THEN
        -- Interactive Session: Must be active hospital_admin in public.profiles
        SELECT hospital_id INTO v_actor_hospital
        FROM public.profiles 
        WHERE id = actor_id AND role = 'hospital_admin' AND is_active = true;

        IF v_actor_hospital IS NULL THEN
            RAISE EXCEPTION 'ADMIN_CORRECTION_FORBIDDEN: Interactive corrections require active hospital_admin credentials.';
        END IF;

        -- Strict Tenant Boundary Enforcement: Ensure target entity belongs to caller hospital
        IF p_operation IN ('RECTIFY_LEGACY_PROFILE_METADATA', 'ANONYMIZE_LEGACY_PROFILE_PII') THEN
            SELECT hospital_id INTO v_target_hospital FROM public.profiles WHERE id = p_record_id;
            IF v_target_hospital != v_actor_hospital THEN
                RAISE EXCEPTION 'CROSS_TENANT_VIOLATION: Hospital admin cannot rectify profiles belonging to another hospital.';
            END IF;
        ELSIF p_operation = 'RECTIFY_PATIENT_ACCOUNT_METADATA' THEN
            SELECT p.hospital_id INTO v_target_hospital 
            FROM public.patient_accounts pa
            JOIN public.patients p ON p.id = pa.patient_id
            WHERE pa.id = p_record_id;
            IF v_target_hospital != v_actor_hospital THEN
                RAISE EXCEPTION 'CROSS_TENANT_VIOLATION: Hospital admin cannot rectify patient accounts belonging to another hospital.';
            END IF;
        END IF;

        v_actor_desc := 'hospital_admin:' || actor_id || ':hospital:' || v_actor_hospital;
    ELSE
        -- Headless Service/DBA Session: Check SESSION_USER (unforgeable original connecting role)
        IF SESSION_USER NOT IN ('service_role', 'postgres', 'supabase_admin') THEN
            RAISE EXCEPTION 'ADMIN_CORRECTION_FORBIDDEN: Headless execution requires service_role, postgres, or supabase_admin database session.';
        END IF;
        
        -- Signature presence check
        IF p_dba_signature IS NULL OR length(trim(p_dba_signature)) != 64 THEN
            RAISE EXCEPTION 'ADMIN_CORRECTION_FORBIDDEN: Headless execution requires valid 64-character hex cryptographic p_dba_signature.';
        END IF;

        -- Timestamp Freshness Check (300-second acceptance window to prevent replay)
        IF abs(extract(epoch from (clock_timestamp() - p_timestamp))) > 300 THEN
            RAISE EXCEPTION 'SIGNATURE_EXPIRED: Timestamp is outside 300-second acceptance window.';
        END IF;

        SELECT secret_value INTO v_secret FROM carebridge_internal.auth_secrets WHERE key_name = 'dba_hmac_key';
        IF v_secret IS NULL OR length(v_secret) < 64 THEN
            RAISE EXCEPTION 'KEY_ERROR: System HMAC key not configured or invalid in carebridge_internal.';
        END IF;

        -- Format UTC timestamp strictly into ISO 8601 string: YYYY-MM-DDTHH:MI:SSZ
        v_ts_str := to_char(p_timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');

        -- Unambiguous Canonical Length-Prefixed Netstring Framing:
        v_payload := length(p_ticket_id)::text || ':' || p_ticket_id || ';' ||
                     length(p_operation)::text || ':' || p_operation || ';' ||
                     length(p_record_id::text)::text || ':' || p_record_id::text || ';' ||
                     length(p_new_value)::text || ':' || p_new_value || ';' ||
                     length(p_justification)::text || ':' || p_justification || ';' ||
                     length(v_ts_str)::text || ':' || v_ts_str || ';';

        -- Fail closed if payload evaluated to NULL
        IF v_payload IS NULL THEN
            RAISE EXCEPTION 'CRYPTO_ERROR: Constructed payload evaluated to NULL.';
        END IF;

        v_expected_signature := encode(
            hmac(v_payload, v_secret, 'sha256'),
            'hex'
        );

        -- Fail closed if expected signature evaluated to NULL
        IF v_expected_signature IS NULL THEN
            RAISE EXCEPTION 'CRYPTO_ERROR: Computed HMAC signature evaluated to NULL.';
        END IF;

        -- Fail closed with explicit NULL-safe comparison
        IF p_dba_signature IS DISTINCT FROM v_expected_signature THEN
            RAISE EXCEPTION 'INVALID_DBA_SIGNATURE: Cryptographic HMAC-SHA256 signature verification failed.';
        END IF;

        actor_id := '00000000-0000-0000-0000-000000000000';
        v_actor_desc := 'service_role:' || SESSION_USER;
    END IF;

    -- 4. Authorize via private DAC table (Bound strictly to current transaction XID, target record, and operation)
    INSERT INTO carebridge_internal.active_corrections (xid, record_id, operation)
    VALUES (txid_current(), p_record_id, p_operation)
    ON CONFLICT (xid, record_id, operation) DO NOTHING;

    -- 5. Execute Whitelisted Static Operation
    IF p_operation = 'RECTIFY_LEGACY_PROFILE_METADATA' THEN
        SELECT to_jsonb(p) INTO old_data FROM public.profiles p WHERE id = p_record_id AND role = 'receptionist';
        IF old_data IS NULL THEN RAISE EXCEPTION 'RECORD_NOT_FOUND: Legacy profile % not found.', p_record_id; END IF;
        
        UPDATE public.profiles 
        SET full_name = p_new_value, updated_at = timezone('utc', now()) 
        WHERE id = p_record_id AND role = 'receptionist';

    ELSIF p_operation = 'ANONYMIZE_LEGACY_PROFILE_PII' THEN
        SELECT to_jsonb(p) INTO old_data FROM public.profiles p WHERE id = p_record_id AND role = 'receptionist';
        IF old_data IS NULL THEN RAISE EXCEPTION 'RECORD_NOT_FOUND: Legacy profile % not found.', p_record_id; END IF;
        
        UPDATE public.profiles 
        SET full_name = 'Redacted Historical User', 
            email = 'anonymized-' || p_record_id || '@redacted.local',
            updated_at = timezone('utc', now()) 
        WHERE id = p_record_id AND role = 'receptionist';

    ELSIF p_operation = 'RECTIFY_PATIENT_ACCOUNT_METADATA' THEN
        SELECT to_jsonb(pa) INTO old_data FROM public.patient_accounts pa WHERE id = p_record_id AND relationship != 'self';
        IF old_data IS NULL THEN RAISE EXCEPTION 'RECORD_NOT_FOUND: Historical account link % not found.', p_record_id; END IF;
        
        UPDATE public.patient_accounts 
        SET updated_at = timezone('utc', now()) 
        WHERE id = p_record_id;
    END IF;

    -- 6. Atomic Transactional Audit Log Record
    INSERT INTO public.audit_logs (
        event_type, actor_id, target_entity, target_id, details
    ) VALUES (
        'ADMIN_HISTORICAL_CORRECTION', actor_id, 'public.' || split_part(p_operation, '_', 2), p_record_id,
        jsonb_build_object(
            'operation', p_operation,
            'actor_desc', v_actor_desc,
            'ticket_id', p_ticket_id,
            'justification', p_justification,
            'timestamp', p_timestamp,
            'old_data', old_data,
            'new_value', p_new_value
        )
    );

    RETURN jsonb_build_object('status', 'SUCCESS', 'operation', p_operation, 'record_id', p_record_id);
END;
$$;

REVOKE ALL ON FUNCTION public.admin_correct_historical_record(TEXT, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_correct_historical_record(TEXT, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT) TO authenticated, service_role, postgres;

COMMIT;
