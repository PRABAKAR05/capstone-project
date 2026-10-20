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
