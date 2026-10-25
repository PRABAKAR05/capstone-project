-- CareBridge AI — Synthetic Seed Dataset
-- strictly non-clinical, fictional test data for multi-tenant and RLS verification

-- 1. Insert Hospitals
INSERT INTO public.hospitals (id, name, slug, license_number, address, contact_email, contact_phone)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'Aegis Metro General Hospital', 'aegis-metro-general', 'HOSP-TN-2026-001', '100 Mount Road, Chennai, Tamil Nadu', 'admin@aegis-hospital.example.com', '+91-44-28001000'),
    ('22222222-2222-2222-2222-222222222222', 'St. Jude Regional Infirmary', 'st-jude-regional', 'HOSP-TN-2026-002', '45 Avinashi Road, Coimbatore, Tamil Nadu', 'contact@stjude-hospital.example.com', '+91-422-24002000')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;

-- 2. Insert Departments
INSERT INTO public.departments (id, hospital_id, name, code, head_of_department)
VALUES
    ('11111111-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'Cardiology', 'CARD', 'Dr. Aris Thorne'),
    ('11111111-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'Neurology', 'NEUR', 'Dr. Maya Lin'),
    ('11111111-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', 'Outpatient Department', 'OPD', 'Dr. Rajesh Sundaram'),
    ('22222222-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'Emergency & Diagnostics', 'EMRG', 'Dr. Gregory House')
ON CONFLICT (hospital_id, code) DO NOTHING;

-- 3. Insert Synthetic Patients
INSERT INTO public.patients (id, hospital_id, mrn, first_name, last_name, date_of_birth, gender, blood_group, phone, email, address, emergency_contact_name, emergency_contact_phone)
VALUES
    ('11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'SYN-PAT-001', 'Alice', 'Vance', '1985-04-12', 'female', 'O+', '+91-9876543210', 'alice.vance.synthetic@example.com', '7 Lotus Ave, Chennai', 'Eli Vance', '+91-9876543219'),
    ('11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', 'SYN-PAT-002', 'Bob', 'Pendelton', '1972-11-03', 'male', 'A+', '+91-9876543211', 'bob.pendelton.synthetic@example.com', '12 Lake View Road, Chennai', 'Sarah Pendelton', '+91-9876543220'),
    ('22222222-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222', 'SYN-STJ-001', 'David', 'Bowman', '1968-01-30', 'male', 'B+', '+91-9876543212', 'david.bowman.synthetic@example.com', '88 Cross Cut Road, Coimbatore', 'Frank Poole', '+91-9876543221')
ON CONFLICT (hospital_id, mrn) DO NOTHING;

-- 4. Insert Test Auth Users
INSERT INTO auth.users (id, aud, role, email)
VALUES 
    ('70000000-0000-0000-0000-000000000001', 'authenticated', 'authenticated', 'admin1@aegis.example.com'),
    ('70000000-0000-0000-0000-000000000002', 'authenticated', 'authenticated', 'doc1@aegis.example.com'),
    ('70000000-0000-0000-0000-000000000003', 'authenticated', 'authenticated', 'rec1@aegis.example.com'),
    ('70000000-0000-0000-0000-000000000033', 'authenticated', 'authenticated', 'labtech1@aegis.example.com'),
    ('70000000-0000-0000-0000-000000000004', 'authenticated', 'authenticated', 'patuser1@example.com'),
    ('70000000-0000-0000-0000-000000000005', 'authenticated', 'authenticated', 'inactive@example.com'),
    ('70000000-0000-0000-0000-000000000006', 'authenticated', 'authenticated', 'hosp2doc@stjude.example.com'),
    ('70000000-0000-0000-0000-000000000007', 'authenticated', 'authenticated', 'caregiver@example.com')
ON CONFLICT (id) DO NOTHING;

-- 5. Insert Test Profiles
INSERT INTO public.profiles (id, hospital_id, role, full_name, email, is_active)
VALUES
    ('70000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'hospital_admin', 'Admin 1', 'admin1@aegis.example.com', true),
    ('70000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'doctor', 'Doctor 1', 'doc1@aegis.example.com', true),
    ('70000000-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111', 'receptionist', 'Receptionist 1', 'rec1@aegis.example.com', true),
    ('70000000-0000-0000-0000-000000000033', '11111111-1111-1111-1111-111111111111', 'lab_technician', 'Lab Tech 1', 'labtech1@aegis.example.com', true),
    ('70000000-0000-0000-0000-000000000004', '11111111-1111-1111-1111-111111111111', 'patient', 'Patient User 1', 'patuser1@example.com', true),
    ('70000000-0000-0000-0000-000000000005', '11111111-1111-1111-1111-111111111111', 'patient', 'Inactive User', 'inactive@example.com', false),
    ('70000000-0000-0000-0000-000000000006', '22222222-2222-2222-2222-222222222222', 'doctor', 'Hosp2 Doctor', 'hosp2doc@stjude.example.com', true),
    ('70000000-0000-0000-0000-000000000007', '11111111-1111-1111-1111-111111111111', 'patient', 'Caregiver User', 'caregiver@example.com', true)
ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active;

-- 6. Insert Test Doctors
INSERT INTO public.doctors (id, hospital_id, profile_id, department_id, license_number, specialization, qualification, consultation_fee)
VALUES
    ('71111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', '70000000-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000001', 'LIC-PH3-DOC1', 'Cardiology', 'MD', 500.00)
ON CONFLICT (id) DO NOTHING;

-- 7. Insert Test Patient Account Links
INSERT INTO public.patient_accounts (hospital_id, user_id, patient_id, relationship, status)
VALUES
    ('11111111-1111-1111-1111-111111111111', '70000000-0000-0000-0000-000000000004', '11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'self', 'verified')
ON CONFLICT DO NOTHING;

-- 8. Insert Synthetic Patient Insurance Policies
INSERT INTO public.patient_insurance_policies (
    id, hospital_id, patient_id, provider_name, policy_number,
    policy_holder_name, relation_to_patient, sum_insured_inr,
    remaining_balance_inr, copay_percentage, deductible_inr,
    exclusions, valid_from, valid_until, status
) VALUES (
    '88888888-8888-8888-8888-888888888881',
    '11111111-1111-1111-1111-111111111111',
    '11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'Star Health Comprehensive',
    'POL-STAR-2026-001',
    'Alice Vance',
    'self',
    500000.00,
    450000.00,
    10.00,
    1000.00,
    '["cosmetic_surgery"]'::jsonb,
    '2026-01-01',
    '2027-01-01',
    'active'
) ON CONFLICT (id) DO NOTHING;
