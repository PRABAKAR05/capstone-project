-- CareBridge AI — Migration: 0001_phase2_schema.sql
-- Description: Core schema, composite tenant constraints, hardened security functions, RLS, and exclusion constraints
-- Phase 2 Minimum Foundation

-- 1. Enable Required PostgreSQL Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Custom ENUM Types
DO $$ BEGIN
    CREATE TYPE public.user_role AS ENUM (
        'hospital_admin',
        'doctor',
        'nurse',
        'receptionist',
        'lab_technician',
        'patient'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE public.appointment_status AS ENUM (
        'scheduled',
        'confirmed',
        'in_progress',
        'completed',
        'cancelled',
        'no_show'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE public.account_link_status AS ENUM (
        'pending_verification',
        'verified',
        'revoked'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 3. Core Tables

-- 3.1 Hospitals (Tenant Root)
CREATE TABLE IF NOT EXISTS public.hospitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    license_number TEXT UNIQUE,
    address TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_hospitals_id UNIQUE (id)
);

-- 3.2 Departments
CREATE TABLE IF NOT EXISTS public.departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    head_of_department TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_departments_tenant_code UNIQUE (hospital_id, code),
    CONSTRAINT uq_departments_tenant_id UNIQUE (hospital_id, id)
);

-- 3.3 Profiles (Linked to auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE RESTRICT,
    role public.user_role NOT NULL DEFAULT 'patient',
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_profiles_tenant_id UNIQUE (hospital_id, id)
);
CREATE INDEX IF NOT EXISTS idx_profiles_tenant_role ON public.profiles(hospital_id, role);

-- 3.4 Doctors
CREATE TABLE IF NOT EXISTS public.doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    department_id UUID NOT NULL,
    license_number TEXT NOT NULL,
    specialization TEXT NOT NULL,
    qualification TEXT NOT NULL,
    opd_room TEXT,
    consultation_fee NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (consultation_fee >= 0),
    is_available BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_doctors_profile FOREIGN KEY (hospital_id, profile_id)
        REFERENCES public.profiles(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_doctors_department FOREIGN KEY (hospital_id, department_id)
        REFERENCES public.departments(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_doctors_profile UNIQUE (profile_id),
    CONSTRAINT uq_doctors_license_per_hospital UNIQUE (hospital_id, license_number),
    CONSTRAINT uq_doctors_tenant_id UNIQUE (hospital_id, id)
);
CREATE INDEX IF NOT EXISTS idx_doctors_tenant_dept ON public.doctors(hospital_id, department_id);

-- 3.5 Patients (Authoritative PMI)
CREATE TABLE IF NOT EXISTS public.patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE RESTRICT,
    mrn TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth DATE NOT NULL CHECK (date_of_birth <= CURRENT_DATE),
    gender TEXT NOT NULL CHECK (gender IN ('male', 'female', 'other')),
    blood_group TEXT CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_patients_mrn_per_hospital UNIQUE (hospital_id, mrn),
    CONSTRAINT uq_patients_tenant_id UNIQUE (hospital_id, id)
);
CREATE INDEX IF NOT EXISTS idx_patients_tenant_mrn ON public.patients(hospital_id, mrn);

-- 3.6 Patient Accounts (Explicit Account-to-Patient Linking)
CREATE TABLE IF NOT EXISTS public.patient_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL,
    user_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    relationship TEXT NOT NULL DEFAULT 'self' CHECK (relationship IN ('self', 'parent', 'guardian', 'caregiver', 'spouse')),
    status public.account_link_status NOT NULL DEFAULT 'pending_verification',
    verified_at TIMESTAMPTZ,
    verified_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_patient_accounts_user FOREIGN KEY (hospital_id, user_id)
        REFERENCES public.profiles(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_patient_accounts_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_patient_accounts_verifier FOREIGN KEY (hospital_id, verified_by)
        REFERENCES public.profiles(hospital_id, id) ON DELETE SET NULL,
    CONSTRAINT uq_user_patient_link UNIQUE (user_id, patient_id),
    CONSTRAINT uq_patient_accounts_tenant_id UNIQUE (hospital_id, id)
);
CREATE INDEX IF NOT EXISTS idx_patient_accounts_lookup ON public.patient_accounts(user_id, status);

-- 3.7 Appointments (With Doctor Overbooking Exclusion Constraint)
CREATE TABLE IF NOT EXISTS public.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    doctor_id UUID NOT NULL,
    department_id UUID NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status public.appointment_status NOT NULL DEFAULT 'scheduled',
    reason_for_visit TEXT,
    clinical_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_appointment_times CHECK (ends_at > scheduled_at),
    CONSTRAINT fk_appointments_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_appointments_doctor FOREIGN KEY (hospital_id, doctor_id)
        REFERENCES public.doctors(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_appointments_department FOREIGN KEY (hospital_id, department_id)
        REFERENCES public.departments(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_appointments_tenant_id UNIQUE (hospital_id, id),
    CONSTRAINT exclude_doctor_double_booking EXCLUDE USING gist (
        doctor_id WITH =,
        tstzrange(scheduled_at, ends_at, '[)') WITH &&
    ) WHERE (status NOT IN ('cancelled', 'no_show'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_schedule ON public.appointments(hospital_id, doctor_id, scheduled_at);

-- 4. Hardened Security Definer Helper Functions
-- Revoke all default execution permissions from PUBLIC
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- 4.1 Current User Hospital ID
CREATE OR REPLACE FUNCTION public.get_auth_hospital_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT p.hospital_id
    FROM public.profiles p
    WHERE p.id = (SELECT auth.uid())
      AND p.is_active = true
    LIMIT 1;
$$;

-- 4.2 Current User Role
CREATE OR REPLACE FUNCTION public.get_auth_role()
RETURNS public.user_role
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT p.role
    FROM public.profiles p
    WHERE p.id = (SELECT auth.uid())
      AND p.is_active = true
    LIMIT 1;
$$;

-- 4.3 Check Hospital Staff Status
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

-- 4.4 Check Patient Access (Staff OR Verified Patient/Caregiver)
CREATE OR REPLACE FUNCTION public.has_patient_access(check_hospital_id UUID, check_patient_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT (
        public.is_hospital_staff(check_hospital_id)
        OR
        EXISTS (
            SELECT 1
            FROM public.patient_accounts pa
            WHERE pa.hospital_id = check_hospital_id
              AND pa.user_id = (SELECT auth.uid())
              AND pa.patient_id = check_patient_id
              AND pa.status = 'verified'
        )
    );
$$;

-- Explicit Execution Grants to authenticated users
GRANT EXECUTE ON FUNCTION public.get_auth_hospital_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_auth_role() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_hospital_staff(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.has_patient_access(UUID, UUID) TO authenticated;

-- 5. Profile Privilege Lockdown Trigger
CREATE OR REPLACE FUNCTION public.protect_profile_privilege_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    executing_role public.user_role;
    is_service_role BOOLEAN;
BEGIN
    -- Check if executing context is Supabase service_role
    is_service_role := (SELECT current_user = 'service_role' OR auth.jwt() ->> 'role' = 'service_role');
    
    IF is_service_role THEN
        RETURN NEW;
    END IF;

    executing_role := public.get_auth_role();

    -- Ordinary users cannot change hospital_id, role, or is_active
    IF (OLD.hospital_id IS DISTINCT FROM NEW.hospital_id) THEN
        RAISE EXCEPTION 'Security Violation: hospital_id cannot be modified.';
    END IF;

    IF (OLD.role IS DISTINCT FROM NEW.role) THEN
        IF executing_role != 'hospital_admin' THEN
            RAISE EXCEPTION 'Security Violation: Only hospital administrators can change roles.';
        END IF;
    END IF;

    IF (OLD.is_active IS DISTINCT FROM NEW.is_active) THEN
        IF executing_role != 'hospital_admin' THEN
            RAISE EXCEPTION 'Security Violation: Only hospital administrators can change account activation status.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_protect_profile_privilege_fields ON public.profiles;
CREATE TRIGGER trg_protect_profile_privilege_fields
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE FUNCTION public.protect_profile_privilege_fields();

-- 6. Enable Row Level Security (RLS) on All Tables
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

-- 7. Define Comprehensive RLS Policies

-- 7.1 Hospitals Policies
DROP POLICY IF EXISTS hospitals_select ON public.hospitals;
CREATE POLICY hospitals_select ON public.hospitals
FOR SELECT TO authenticated
USING (id = public.get_auth_hospital_id());

-- 7.2 Departments Policies
DROP POLICY IF EXISTS departments_select ON public.departments;
CREATE POLICY departments_select ON public.departments
FOR SELECT TO authenticated
USING (hospital_id = public.get_auth_hospital_id());

DROP POLICY IF EXISTS departments_write ON public.departments;
CREATE POLICY departments_write ON public.departments
FOR ALL TO authenticated
USING (hospital_id = public.get_auth_hospital_id() AND public.get_auth_role() = 'hospital_admin')
WITH CHECK (hospital_id = public.get_auth_hospital_id() AND public.get_auth_role() = 'hospital_admin');

-- 7.3 Profiles Policies
DROP POLICY IF EXISTS profiles_select ON public.profiles;
CREATE POLICY profiles_select ON public.profiles
FOR SELECT TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR id = (SELECT auth.uid())
);

DROP POLICY IF EXISTS profiles_update ON public.profiles;
CREATE POLICY profiles_update ON public.profiles
FOR UPDATE TO authenticated
USING (
    id = (SELECT auth.uid())
    OR (hospital_id = public.get_auth_hospital_id() AND public.get_auth_role() = 'hospital_admin')
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
);

-- 7.4 Doctors Policies
DROP POLICY IF EXISTS doctors_select ON public.doctors;
CREATE POLICY doctors_select ON public.doctors
FOR SELECT TO authenticated
USING (hospital_id = public.get_auth_hospital_id());

DROP POLICY IF EXISTS doctors_write ON public.doctors;
CREATE POLICY doctors_write ON public.doctors
FOR ALL TO authenticated
USING (
    hospital_id = public.get_auth_hospital_id()
    AND (
        public.get_auth_role() = 'hospital_admin'
        OR profile_id = (SELECT auth.uid())
    )
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
);

-- 7.5 Patients Policies
DROP POLICY IF EXISTS patients_select ON public.patients;
CREATE POLICY patients_select ON public.patients
FOR SELECT TO authenticated
USING (
    hospital_id = public.get_auth_hospital_id()
    AND public.has_patient_access(hospital_id, id)
);

DROP POLICY IF EXISTS patients_insert ON public.patients;
CREATE POLICY patients_insert ON public.patients
FOR INSERT TO authenticated
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
    AND public.get_auth_role() IN ('hospital_admin', 'receptionist', 'doctor')
);

DROP POLICY IF EXISTS patients_update ON public.patients;
CREATE POLICY patients_update ON public.patients
FOR UPDATE TO authenticated
USING (
    hospital_id = public.get_auth_hospital_id()
    AND public.get_auth_role() IN ('hospital_admin', 'receptionist', 'doctor')
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
);

-- 7.6 Patient Accounts Policies
DROP POLICY IF EXISTS patient_accounts_select ON public.patient_accounts;
CREATE POLICY patient_accounts_select ON public.patient_accounts
FOR SELECT TO authenticated
USING (
    (hospital_id = public.get_auth_hospital_id() AND public.is_hospital_staff(hospital_id))
    OR user_id = (SELECT auth.uid())
);

DROP POLICY IF EXISTS patient_accounts_insert ON public.patient_accounts;
CREATE POLICY patient_accounts_insert ON public.patient_accounts
FOR INSERT TO authenticated
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
    AND (
        public.is_hospital_staff(hospital_id)
        OR (user_id = (SELECT auth.uid()) AND status = 'pending_verification')
    )
);

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

-- 7.7 Appointments Policies
DROP POLICY IF EXISTS appointments_select ON public.appointments;
CREATE POLICY appointments_select ON public.appointments
FOR SELECT TO authenticated
USING (
    hospital_id = public.get_auth_hospital_id()
    AND public.has_patient_access(hospital_id, patient_id)
);

DROP POLICY IF EXISTS appointments_insert ON public.appointments;
CREATE POLICY appointments_insert ON public.appointments
FOR INSERT TO authenticated
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
    AND public.has_patient_access(hospital_id, patient_id)
    AND (
        public.is_hospital_staff(hospital_id)
        OR (public.get_auth_role() = 'patient' AND status = 'scheduled')
    )
);

DROP POLICY IF EXISTS appointments_update ON public.appointments;
CREATE POLICY appointments_update ON public.appointments
FOR UPDATE TO authenticated
USING (
    hospital_id = public.get_auth_hospital_id()
    AND public.has_patient_access(hospital_id, patient_id)
)
WITH CHECK (
    hospital_id = public.get_auth_hospital_id()
    AND (
        public.is_hospital_staff(hospital_id)
        OR (public.get_auth_role() = 'patient' AND status = 'cancelled')
    )
);
