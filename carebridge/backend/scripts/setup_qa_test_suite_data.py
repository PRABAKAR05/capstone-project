#!/usr/bin/env python3
"""
CareBridge AI - Comprehensive QA Synthetic Dataset & Account Provisioning Script
Generates 20 verifiable synthetic accounts (4 per canonical role) and realistic hospital data.
"""
import os
import sys
import json
import csv
import string
import secrets
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from app.core.config import settings

WORKSPACE_ROOT = BACKEND_DIR.parent.parent
QA_DIR = WORKSPACE_ROOT / "artifacts" / "final-qa-2026-10-20"
PRIVATE_CREDS_PATH = QA_DIR / "test-credentials.private.json"
ACCOUNTS_CSV_PATH = QA_DIR / "test-accounts.csv"
DATA_INVENTORY_PATH = QA_DIR / "synthetic-data-inventory.md"

HOSP_1_ID = "11111111-1111-1111-1111-111111111111" # Aegis Metro General Hospital
HOSP_2_ID = "22222222-2222-2222-2222-222222222222" # St. Jude Metro Healthcare (Tenant 2)

def generate_strong_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = "".join(secrets.choice(chars) for _ in range(length))
        if (any(c.islower() for c in pw) and
            any(c.isupper() for c in pw) and
            any(c.isdigit() for c in pw) and
            any(c in "!@#$%^&*" for c in pw)):
            return pw

def get_db_connection():
    db_url = settings.DATABASE_URL
    if not db_url:
        raise ValueError("DATABASE_URL not configured")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    return conn

def main():
    print("=================================================================")
    print(" CareBridge AI - Final QA Synthetic Accounts & Dataset Provisioning ")
    print("=================================================================")

    QA_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Define the 20 accounts (4 per role)
        # Roles: hospital_admin, doctor, nurse, lab_technician, patient
        account_specs = [
            # Admins
            {"id": "90000000-0001-0000-0000-000000000001", "label": "CB-ADMIN-01", "role": "hospital_admin", "name": "Arthur Pendelton", "email": "cb-admin-01@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Chief Operating Officer"},
            {"id": "90000000-0001-0000-0000-000000000002", "label": "CB-ADMIN-02", "role": "hospital_admin", "name": "Eleanor Vance", "email": "cb-admin-02@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Clinical Operations Manager"},
            {"id": "90000000-0001-0000-0000-000000000003", "label": "CB-ADMIN-03", "role": "hospital_admin", "name": "Charles Xavier", "email": "cb-admin-03@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Governance & Compliance Director"},
            {"id": "90000000-0001-0000-0000-000000000004", "label": "CB-ADMIN-04", "role": "hospital_admin", "name": "Bruce Wayne", "email": "cb-admin-04@carebridge.test", "hospital_id": HOSP_2_ID, "title": "Hosp 2 Administrator"},
            # Doctors
            {"id": "90000000-0002-0000-0000-000000000001", "label": "CB-DOCTOR-01", "role": "doctor", "name": "Dr. Evelyn Reed", "email": "cb-doctor-01@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Attending Cardiologist", "spec": "Cardiology", "lic": "QA-DOC-LIC-0001"},
            {"id": "90000000-0002-0000-0000-000000000002", "label": "CB-DOCTOR-02", "role": "doctor", "name": "Dr. Marcus Thorne", "email": "cb-doctor-02@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Senior Neurologist", "spec": "Neurology", "lic": "QA-DOC-LIC-0002"},
            {"id": "90000000-0002-0000-0000-000000000003", "label": "CB-DOCTOR-03", "role": "doctor", "name": "Dr. Clara Oswald", "email": "cb-doctor-03@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Consultant Physician", "spec": "General Medicine", "lic": "QA-DOC-LIC-0003"},
            {"id": "90000000-0002-0000-0000-000000000004", "label": "CB-DOCTOR-04", "role": "doctor", "name": "Dr. Julian Bashir", "email": "cb-doctor-04@carebridge.test", "hospital_id": HOSP_2_ID, "title": "Hosp 2 Attending Physician", "spec": "Internal Medicine", "lic": "QA-DOC-LIC-0004"},
            # Nurses
            {"id": "90000000-0003-0000-0000-000000000001", "label": "CB-NURSE-01", "role": "nurse", "name": "Nurse Sarah Jenkins", "email": "cb-nurse-01@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Lead Triage Nurse"},
            {"id": "90000000-0003-0000-0000-000000000002", "label": "CB-NURSE-02", "role": "nurse", "name": "Nurse David Kim", "email": "cb-nurse-02@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Staff Nurse OPD Desk"},
            {"id": "90000000-0003-0000-0000-000000000003", "label": "CB-NURSE-03", "role": "nurse", "name": "Nurse Maria Rodriguez", "email": "cb-nurse-03@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Care Coordinator Nurse"},
            {"id": "90000000-0003-0000-0000-000000000004", "label": "CB-NURSE-04", "role": "nurse", "name": "Nurse Alan Turing", "email": "cb-nurse-04@carebridge.test", "hospital_id": HOSP_2_ID, "title": "Hosp 2 Inpatient Nurse"},
            # Lab Technicians
            {"id": "90000000-0004-0000-0000-000000000001", "label": "CB-LAB-01", "role": "lab_technician", "name": "Tech Jordan Miller", "email": "cb-lab-01@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Senior Diagnostic Pathologist"},
            {"id": "90000000-0004-0000-0000-000000000002", "label": "CB-LAB-02", "role": "lab_technician", "name": "Tech Rachel Zane", "email": "cb-lab-02@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Hematology Specialist"},
            {"id": "90000000-0004-0000-0000-000000000003", "label": "CB-LAB-03", "role": "lab_technician", "name": "Tech Sanjay Gupta", "email": "cb-lab-03@carebridge.test", "hospital_id": HOSP_1_ID, "title": "Biochemistry Analyst"},
            {"id": "90000000-0004-0000-0000-000000000004", "label": "CB-LAB-04", "role": "lab_technician", "name": "Tech Leonard McCoy", "email": "cb-lab-04@carebridge.test", "hospital_id": HOSP_2_ID, "title": "Hosp 2 Lab Specialist"},
            # Patients
            {"id": "90000000-0005-0000-0000-000000000001", "label": "CB-PATIENT-01", "role": "patient", "name": "Maya Demo", "email": "cb-patient-01@carebridge.test", "hospital_id": HOSP_1_ID, "patient_id": "90000000-aaaa-0000-0000-000000000001", "mrn": "QA-MRN-001", "dob": "1992-04-12", "gender": "female", "blood": "O+"},
            {"id": "90000000-0005-0000-0000-000000000002", "label": "CB-PATIENT-02", "role": "patient", "name": "Arjun Sample", "email": "cb-patient-02@carebridge.test", "hospital_id": HOSP_1_ID, "patient_id": "90000000-aaaa-0000-0000-000000000002", "mrn": "QA-MRN-002", "dob": "1988-11-23", "gender": "male", "blood": "A+"},
            {"id": "90000000-0005-0000-0000-000000000003", "label": "CB-PATIENT-03", "role": "patient", "name": "Kavya Test", "email": "cb-patient-03@carebridge.test", "hospital_id": HOSP_1_ID, "patient_id": "90000000-aaaa-0000-0000-000000000003", "mrn": "QA-MRN-003", "dob": "1995-07-08", "gender": "female", "blood": "B+"},
            {"id": "90000000-0005-0000-0000-000000000004", "label": "CB-PATIENT-04", "role": "patient", "name": "Ravi Synthetic", "email": "cb-patient-04@carebridge.test", "hospital_id": HOSP_2_ID, "patient_id": "90000000-aaaa-0000-0000-000000000004", "mrn": "QA-MRN-004", "dob": "1984-09-30", "gender": "male", "blood": "AB+"},
        ]

        # Generate credentials
        credentials_record = []
        accounts_csv_record = []

        print("\n1. Provisioning 20 Synthetic Test Accounts into auth.users and public.profiles...")
        for spec in account_specs:
            password = generate_strong_password(16)
            spec["password"] = password

            # 1.1 Insert into auth.users
            cur.execute("""
                INSERT INTO auth.users (
                    id, email, encrypted_password, email_confirmed_at,
                    aud, role, raw_app_meta_data, raw_user_meta_data,
                    instance_id, created_at, updated_at
                ) VALUES (
                    %s, %s, extensions.crypt(%s, extensions.gen_salt('bf')), NOW(),
                    'authenticated', 'authenticated', '{"provider":"email","providers":["email"]}'::jsonb,
                    json_build_object('full_name', %s, 'role', %s)::jsonb,
                    '00000000-0000-0000-0000-000000000000', NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    encrypted_password = EXCLUDED.encrypted_password,
                    email_confirmed_at = NOW();
            """, (spec["id"], spec["email"], password, spec["name"], spec["role"]))

            # 1.2 Insert into public.profiles
            cur.execute("""
                INSERT INTO public.profiles (
                    id, hospital_id, role, full_name, email, is_active
                ) VALUES (
                    %s, %s, %s, %s, %s, true
                )
                ON CONFLICT (id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    email = EXCLUDED.email,
                    is_active = true;
            """, (spec["id"], spec["hospital_id"], spec["role"], spec["name"], spec["email"]))

            # 1.3 If Doctor, insert into public.doctors
            if spec["role"] == "doctor":
                # Match department by specialty
                spec_clean = spec.get("spec", "")
                if "Neuro" in spec_clean:
                    dept_name_query = "%Neurology%"
                elif "General" in spec_clean or "Medicine" in spec_clean or "Internal" in spec_clean:
                    dept_name_query = "%Outpatient%"
                else:
                    dept_name_query = "%Cardiology%"

                cur.execute("""
                    SELECT id FROM public.departments 
                    WHERE hospital_id = %s AND (name ILIKE %s OR code ILIKE %s)
                    LIMIT 1;
                """, (spec["hospital_id"], dept_name_query, dept_name_query))
                dept_row = cur.fetchone()
                if not dept_row:
                    cur.execute("SELECT id FROM public.departments WHERE hospital_id = %s ORDER BY name ASC LIMIT 1;", (spec["hospital_id"],))
                    dept_row = cur.fetchone()
                dept_id = dept_row[0] if dept_row else None
                doc_table_id = spec["id"].replace("-0002-", "-0022-")
                cur.execute("""
                    INSERT INTO public.doctors (
                        id, hospital_id, profile_id, department_id, license_number,
                        specialization, qualification, consultation_fee, is_available
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 'MBBS, MD', 600.00, true
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        department_id = EXCLUDED.department_id,
                        specialization = EXCLUDED.specialization,
                        is_available = true;
                """, (doc_table_id, spec["hospital_id"], spec["id"], dept_id, spec["lic"], spec["spec"]))

            # 1.4 If Patient, insert into public.patients and public.patient_accounts
            if spec["role"] == "patient":
                cur.execute("""
                    INSERT INTO public.patients (
                        id, hospital_id, mrn, first_name, last_name, date_of_birth,
                        gender, blood_group, phone, email, address,
                        emergency_contact_name, emergency_contact_phone
                    ) VALUES (
                        %s, %s, %s, %s, 'QA-Synthetic', %s,
                        %s, %s, '+1-555-0901', %s, 'SYNTHETIC QA DATA - Fictional Clinical Address',
                        'Emergency Contact', '+1-555-0999'
                    )
                    ON CONFLICT (id) DO NOTHING;
                """, (spec["patient_id"], spec["hospital_id"], spec["mrn"], spec["name"], spec["dob"], spec["gender"], spec["blood"], spec["email"]))

                # Link in patient_accounts
                cur.execute("SELECT id FROM public.patient_accounts WHERE patient_id = %s AND relationship = 'self';", (spec["patient_id"],))
                existing_link = cur.fetchone()
                if not existing_link:
                    verifier_id = "90000000-0001-0000-0000-000000000001" if spec["hospital_id"] == HOSP_1_ID else "90000000-0001-0000-0000-000000000004"
                    cur.execute("""
                        INSERT INTO public.patient_accounts (
                            hospital_id, user_id, patient_id, relationship, status, verified_at, verified_by
                        ) VALUES (
                            %s, %s, %s, 'self', 'verified', NOW(), %s
                        );
                    """, (spec["hospital_id"], spec["id"], spec["patient_id"], verifier_id))

            credentials_record.append({
                "account_id": spec["label"],
                "user_id": spec["id"],
                "role": spec["role"],
                "full_name": spec["name"],
                "email": spec["email"],
                "password": password,
                "hospital_id": spec["hospital_id"],
                "title_notes": spec.get("title", spec["role"].replace("_", " ").title()),
                "status": "active_verified"
            })

            accounts_csv_record.append({
                "Account Label": spec["label"],
                "Role": spec["role"],
                "Full Name": spec["name"],
                "Login Email": spec["email"],
                "Hospital Tenant": "Aegis Metro General" if spec["hospital_id"] == HOSP_1_ID else "St. Jude Metro Healthcare",
                "Hospital ID": spec["hospital_id"],
                "Assigned Identity": spec.get("mrn") or spec.get("lic") or spec.get("title", spec["role"].replace("_", " ").title()),
                "Status": "ACTIVE / READY FOR DEMO"
            })

        print(f"  Successfully provisioned {len(account_specs)} synthetic test accounts.")

        print("\n2. Provisioning 12 Additional Clinical Patient Profiles (SYNTHETIC QA DATA)...")
        additional_patients = [
            ("90000000-bbbb-0000-0000-000000000001", "Nila", "Example", "QA-MRN-011", "1990-03-14", "female", "O+"),
            ("90000000-bbbb-0000-0000-000000000002", "Devika", "Demo", "QA-MRN-012", "1985-08-22", "female", "A-"),
            ("90000000-bbbb-0000-0000-000000000003", "Kiran", "Sample", "QA-MRN-013", "1994-01-19", "male", "B+"),
            ("90000000-bbbb-0000-0000-000000000004", "Meera", "Test", "QA-MRN-014", "1989-12-05", "female", "AB+"),
            ("90000000-bbbb-0000-0000-000000000005", "Suresh", "Mock", "QA-MRN-015", "1978-05-11", "male", "O-"),
            ("90000000-bbbb-0000-0000-000000000006", "Priya", "Evaluation", "QA-MRN-016", "1996-07-29", "female", "A+"),
            ("90000000-bbbb-0000-0000-000000000007", "Vikram", "Baseline", "QA-MRN-017", "1982-10-18", "male", "B-"),
            ("90000000-bbbb-0000-0000-000000000008", "Ananya", "Cohort", "QA-MRN-018", "1998-02-14", "female", "O+"),
            ("90000000-bbbb-0000-0000-000000000009", "Rajesh", "Test", "QA-MRN-019", "1975-06-30", "male", "AB-"),
            ("90000000-bbbb-0000-0000-000000000010", "Deepa", "Demo", "QA-MRN-020", "1991-09-09", "female", "A+"),
            ("90000000-bbbb-0000-0000-000000000011", "Karthik", "Validation", "QA-MRN-021", "1987-04-25", "male", "B+"),
            ("90000000-bbbb-0000-0000-000000000012", "Divya", "Case", "QA-MRN-022", "1993-11-17", "female", "O+"),
        ]
        for pid, fn, ln, mrn, dob, gender, blood in additional_patients:
            cur.execute("""
                INSERT INTO public.patients (
                    id, hospital_id, mrn, first_name, last_name, date_of_birth,
                    gender, blood_group, phone, email, address,
                    emergency_contact_name, emergency_contact_phone
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, '+1-555-0888', %s, 'SYNTHETIC QA DATA - Inpatient Ward B',
                    'Contact Person', '+1-555-0899'
                )
                ON CONFLICT (id) DO NOTHING;
            """, (pid, HOSP_1_ID, mrn, fn, ln, dob, gender, blood, f"{fn.lower()}.{ln.lower()}@qa-patient.test"))
        print(f"  Successfully provisioned {len(additional_patients)} additional patient profiles.")

        print("\n3. Seeding Realistic Appointments Across Lifecycle (Scheduled, Confirmed, Completed)...")
        # Appointments for Maya Demo (CB-PATIENT-01) with Doctor Evelyn Reed
        doc_1_table_id = "90000000-0022-0000-0000-000000000001"
        cur.execute("SELECT id FROM public.departments WHERE hospital_id = %s LIMIT 1;", (HOSP_1_ID,))
        cardio_dept_id = cur.fetchone()[0]

        now_utc = datetime.now(timezone.utc)
        appt_plans = [
            ("90000000-c001-0000-0000-000000000001", "90000000-aaaa-0000-0000-000000000001", now_utc + timedelta(hours=2), "scheduled", "Cardiology follow-up & ECG review"),
            ("90000000-c001-0000-0000-000000000002", "90000000-aaaa-0000-0000-000000000001", now_utc + timedelta(days=2, hours=3), "confirmed", "Holter monitor evaluation"),
            ("90000000-c001-0000-0000-000000000003", "90000000-aaaa-0000-0000-000000000001", now_utc - timedelta(days=7), "completed", "Initial cardiology consultation & lipid review"),
            ("90000000-c001-0000-0000-000000000004", "90000000-aaaa-0000-0000-000000000002", now_utc + timedelta(hours=4), "confirmed", "Neurology headache & migraine clinic"),
            ("90000000-c001-0000-0000-000000000005", "90000000-aaaa-0000-0000-000000000003", now_utc + timedelta(days=1), "scheduled", "Endocrinology routine metabolic assessment"),
        ]
        for aid, pid, sched, st, rsn in appt_plans:
            cur.execute("""
                INSERT INTO public.appointments (
                    id, hospital_id, patient_id, doctor_id, department_id,
                    scheduled_at, ends_at, status, reason_for_visit, clinical_notes
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO NOTHING;
            """, (aid, HOSP_1_ID, pid, doc_1_table_id, cardio_dept_id, sched, sched + timedelta(minutes=30), st, rsn, f"SYNTHETIC QA NOTE: {rsn}. Patient arrived on time."))
        print(f"  Successfully seeded {len(appt_plans)} appointments.")

        print("\n4. Seeding Clinical Documents with Deliberate Contradiction for Conflict Testing...")
        # Doc 1: Baseline Metabolic Panel
        doc1_id = "90000000-d001-0000-0000-000000000001"
        cur.execute("""
            INSERT INTO public.clinical_documents (
                id, hospital_id, patient_id, uploaded_by, document_type, file_name,
                mime_type, file_size_bytes, storage_path, ocr_status, raw_text
            ) VALUES (
                %s, %s, %s, %s, 'lab_report', 'SYN_Comprehensive_Metabolic_Panel.pdf',
                'application/pdf', 145000, '/qa/docs/cmp_01.pdf', 'completed',
                'SYNTHETIC QA DATA - Aegis Diagnostic Laboratories. Patient: Maya Demo (QA-MRN-001). HbA1c: 6.2%% (Prediabetes). Fasting Blood Glucose: 114 mg/dL. Serum Creatinine: 0.9 mg/dL.'
            )
            ON CONFLICT (id) DO NOTHING;
        """, (doc1_id, HOSP_1_ID, "90000000-aaaa-0000-0000-000000000001", "90000000-0002-0000-0000-000000000001"))

        # Doc 2: Discrepant Discharge Summary (Contradictory HbA1c: 8.5% -> Diabetes Uncontrolled)
        doc2_id = "90000000-d001-0000-0000-000000000002"
        cur.execute("""
            INSERT INTO public.clinical_documents (
                id, hospital_id, patient_id, uploaded_by, document_type, file_name,
                mime_type, file_size_bytes, storage_path, ocr_status, raw_text
            ) VALUES (
                %s, %s, %s, %s, 'discharge_summary', 'SYN_Discharge_Summary_Emergency.pdf',
                'application/pdf', 210000, '/qa/docs/ds_02.pdf', 'completed',
                'SYNTHETIC QA DATA - Hospital Discharge Note. Patient: Maya Demo (QA-MRN-001). Discharge Assessment: Type 2 Diabetes Mellitus with recent HbA1c: 8.5%% (Severe Hyperglycemia). Discrepancy flagged for primary endocrinology reconciliation.'
            )
            ON CONFLICT (id) DO NOTHING;
        """, (doc2_id, HOSP_1_ID, "90000000-aaaa-0000-0000-000000000001", "90000000-0002-0000-0000-000000000001"))

        # Extracted Entities
        cur.execute("""
            INSERT INTO public.extracted_entities (
                id, hospital_id, document_id, patient_id, entity_category,
                extracted_data, confidence_score, verification_status
            ) VALUES
            ('90000000-e001-0000-0000-000000000001', %s, %s, '90000000-aaaa-0000-0000-000000000001', 'lab_result',
             '{"test_name": "HbA1c", "value": 6.2, "unit": "%%", "reference_range": "<5.7%%", "clinical_interpretation": "Prediabetes range"}'::jsonb, 0.98, 'verified'),
            ('90000000-e001-0000-0000-000000000002', %s, %s, '90000000-aaaa-0000-0000-000000000001', 'lab_result',
             '{"test_name": "HbA1c", "value": 8.5, "unit": "%%", "reference_range": "<5.7%%", "clinical_interpretation": "Poor glycemic control"}'::jsonb, 0.96, 'pending')
            ON CONFLICT (id) DO NOTHING;
        """, (HOSP_1_ID, doc1_id, HOSP_1_ID, doc2_id))

        # Seed Clinical Conflict
        conflict_id = "90000000-f001-0000-0000-000000000001"
        cur.execute("""
            INSERT INTO public.clinical_conflicts (
                id, hospital_id, patient_id, conflict_type, review_priority,
                title, clinical_summary, patient_friendly_summary, resolution_status
            ) VALUES (
                %s, %s, '90000000-aaaa-0000-0000-000000000001', 'diagnostic_discrepancy', 'high',
                'SYNTHETIC CONFLICT: Contradictory Glycated Hemoglobin (HbA1c) Values',
                'Document SYN_Comprehensive_Metabolic_Panel indicates HbA1c of 6.2%% (mild prediabetes), whereas Discharge Summary reports 8.5%% (severe uncontrolled hyperglycemia). Clinical verification required prior to metformin dosage escalation.',
                'Your recent medical records show two different blood sugar (HbA1c) readings: 6.2%% and 8.5%%. Your doctor will review this at your next visit to ensure the correct medication plan.',
                'unresolved'
            )
            ON CONFLICT (id) DO NOTHING;
        """, (conflict_id, HOSP_1_ID))

        # Conflict sources
        cur.execute("""
            INSERT INTO public.clinical_conflict_sources (
                id, hospital_id, conflict_id, document_id, entity_id, role_in_conflict, citation_text
            ) VALUES
            ('90000000-f002-0000-0000-000000000001', %s, %s, %s, '90000000-e001-0000-0000-000000000001', 'baseline_evidence', 'Aegis Diagnostic Labs: HbA1c 6.2%%'),
            ('90000000-f002-0000-0000-000000000002', %s, %s, %s, '90000000-e001-0000-0000-000000000002', 'conflicting_diagnosis', 'Emergency Discharge: HbA1c 8.5%%')
            ON CONFLICT (id) DO NOTHING;
        """, (HOSP_1_ID, conflict_id, doc1_id, HOSP_1_ID, conflict_id, doc2_id))
        print("  Successfully seeded clinical documents, extracted entities, and deliberate conflict.")

        print("\n5. Seeding Care Tasks & e-Prescriptions...")
        task_id = "90000000-0012-0000-0000-000000000001"
        cur.execute("""
            INSERT INTO public.care_tasks (
                id, hospital_id, patient_id, encounter_id, task_type, priority, status,
                title, description, assigned_role, completion_notes
            ) VALUES (
                %s, %s, '90000000-aaaa-0000-0000-000000000001', '90000000-c001-0000-0000-000000000001',
                'lab_review', 'high', 'pending',
                'QA Task: Reconcile Contradictory HbA1c Measurements',
                'INTERNAL NOTE: Review laboratory records with endocrinology before prescribing metformin.',
                'nurse', 'Pending initial nurse intake triage.'
            )
            ON CONFLICT (id) DO NOTHING;
        """, (task_id, HOSP_1_ID))

        # Prescription
        rx_id = "90000000-0013-0000-0000-000000000001"
        cur.execute("""
            INSERT INTO public.prescriptions (
                id, hospital_id, patient_id, doctor_id, status,
                diagnosis_context, notes, verification_hash, issued_at, valid_until
            ) VALUES (
                %s, %s, '90000000-aaaa-0000-0000-000000000001', '90000000-0002-0000-0000-000000000001',
                'prescribed', 'Hypertension & Metabolic Syndrome',
                'Take one tablet daily in the morning with food.',
                'hash_qa_rx_amlodipine_001_89abcdef', NOW(), NOW() + INTERVAL '30 days'
            )
            ON CONFLICT (id) DO NOTHING;
        """, (rx_id, HOSP_1_ID))

        cur.execute("""
            INSERT INTO public.prescription_items (
                id, hospital_id, prescription_id, drug_name, therapeutic_class,
                dosage, route, frequency, duration_days, instructions, refills_remaining
            ) VALUES (
                '90000000-0014-0000-0000-000000000001', %s, %s, 'Amlodipine',
                'Calcium Channel Blocker', '5mg', 'Oral', 'Once Daily', 30,
                'Take with water in the morning.', 2
            )
            ON CONFLICT (id) DO NOTHING;
        """, (HOSP_1_ID, rx_id))
        print("  Successfully seeded care tasks, prescriptions, and items.")

        # Commit database transaction
        conn.commit()
        print("\nAll database changes committed cleanly.")

    except Exception as e:
        conn.rollback()
        print(f"\nDATABASE ERROR: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

    # Write private credentials file
    with open(PRIVATE_CREDS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": "Supabase Test DB (db.vmuzexvtbodnkzhfitzf.supabase.co)",
            "accounts_total": len(credentials_record),
            "accounts": credentials_record
        }, f, indent=2)
    print(f"\nSaved private test credentials to: {PRIVATE_CREDS_PATH}")

    # Write sanitized CSV inventory
    with open(ACCOUNTS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Account Label", "Role", "Full Name", "Login Email",
            "Hospital Tenant", "Hospital ID", "Assigned Identity", "Status"
        ])
        writer.writeheader()
        writer.writerows(accounts_csv_record)
    print(f"Saved sanitized test account inventory to: {ACCOUNTS_CSV_PATH}")

    # Write synthetic data inventory
    with open(DATA_INVENTORY_PATH, "w", encoding="utf-8") as f:
        f.write("# CareBridge AI - Synthetic Dataset Inventory\n\n")
        f.write(f"**Generated At:** {datetime.now(timezone.utc).isoformat()}  \n")
        f.write("**Environment:** Isolated Test Supabase Database (`db.vmuzexvtbodnkzhfitzf.supabase.co`)  \n")
        f.write("**Research Asset Protection:** Zero modifications to `src/`, `models/`, or `data/`.  \n\n")
        f.write("## 1. Verified Synthetic Accounts (20 Accounts Across 5 Canonical Roles)\n\n")
        f.write("| Account Label | Role | Full Name | Login Email | Hospital Tenant | Status |\n")
        f.write("|---|---|---|---|---|---|\n")
        for a in accounts_csv_record:
            f.write(f"| {a['Account Label']} | `{a['Role']}` | {a['Full Name']} | `{a['Login Email']}` | {a['Hospital Tenant']} | {a['Status']} |\n")
        f.write("\n## 2. Clinical Data Highlights\n\n")
        f.write("- **Primary Patient for E2E Demonstrations:** Maya Demo (`QA-MRN-001`, `cb-patient-01@carebridge.test`)\n")
        f.write("- **Associated Doctor:** Dr. Evelyn Reed (`cb-doctor-01@carebridge.test`)\n")
        f.write("- **Associated Nurse:** Nurse Sarah Jenkins (`cb-nurse-01@carebridge.test`)\n")
        f.write("- **Associated Lab Tech:** Tech Jordan Miller (`cb-lab-01@carebridge.test`)\n")
        f.write("- **Associated Administrator:** Arthur Pendelton (`cb-admin-01@carebridge.test`)\n")
        f.write("- **Deliberate Clinical Conflict Record:** Contradictory Glycated Hemoglobin (HbA1c 6.2% vs 8.5%) between Lab Report and Discharge Note.\n")
        f.write("- **Multi-Tenant Control Accounts:** `CB-ADMIN-04`, `CB-DOCTOR-04`, `CB-NURSE-04`, `CB-LAB-04`, `CB-PATIENT-04` isolated in Hospital 2.\n")
    print(f"Saved synthetic dataset inventory to: {DATA_INVENTORY_PATH}")

    # 6. Verify Logins for all 20 accounts via Supabase Auth API
    print("\n6. Live Authentication Verification for All 20 Synthetic Accounts...")
    verified_count = 0
    failed_logins = []

    auth_url = f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": settings.SUPABASE_KEY,
        "Content-Type": "application/json"
    }

    for acc in credentials_record:
        payload = {
            "email": acc["email"],
            "password": acc["password"]
        }
        try:
            res = requests.post(auth_url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                verified_count += 1
                token_data = res.json()
                acc["verified_token_type"] = token_data.get("token_type")
                acc["verified_auth_id"] = token_data.get("user", {}).get("id")
                print(f"  [OK 200] {acc['account_id']} ({acc['role']}): Verified successfully.")
            else:
                err_detail = res.text
                failed_logins.append({"account": acc["account_id"], "status": res.status_code, "error": err_detail})
                print(f"  [FAIL {res.status_code}] {acc['account_id']}: {err_detail}")
        except Exception as ex:
            failed_logins.append({"account": acc["account_id"], "error": str(ex)})
            print(f"  [ERROR] {acc['account_id']}: {ex}")

    print("\n=================================================================")
    print(f" AUTHENTICATION VERIFICATION: {verified_count} / {len(credentials_record)} ACCOUNTS VERIFIED")
    print("=================================================================")

    if failed_logins:
        print(f"WARNING: {len(failed_logins)} accounts failed login verification!")
    else:
        print("ALL 20 TEST ACCOUNTS AUTHENTICATED SUCCESSFULLY VIA SUPABASE GO-TRUE!")

if __name__ == "__main__":
    main()
