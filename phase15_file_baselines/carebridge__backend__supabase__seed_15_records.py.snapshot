import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    raise ValueError("DATABASE_URL not found")

HOSP_ID = '11111111-0001-0000-0000-000000000001'

conn = psycopg2.connect(db_url)
conn.autocommit = False
cur = conn.cursor()

try:
    cur.execute("BEGIN;")

    print("\n--- 1. Seeding Hospitals (15 Synthetic Branches) ---")
    hosp_sql = """
        INSERT INTO public.hospitals (
            id, name, slug, license_number, address, contact_email, contact_phone, is_active, timezone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        hid = f"11111111-0001-0000-0000-{i:012d}"
        slug = f"syn-hosp-{i:02d}"
        name = f"SYN CareBridge Central Hospital Branch {i:02d}"
        lic = f"SYN-HOSP-LIC-{i:04d}"
        email = f"contact{i:02d}@syn-hospital.test"
        cur.execute(hosp_sql, (hid, name, slug, lic, f"{i*10} Health Tech Blvd, Metro City", email, f"+1-555-01{i:02d}", True, "Asia/Kolkata"))
    print("  15 Synthetic hospitals seeded.")

    print("\n--- 2. Seeding Departments (15 Medical Specialties) ---")
    dept_sql = """
        INSERT INTO public.departments (
            id, hospital_id, name, code, head_of_department
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    dept_names = [
        ("Cardiology", "CARD"), ("Neurology", "NEUR"), ("Oncology", "ONCO"),
        ("Endocrinology", "ENDO"), ("Pulmonology", "PULM"), ("Orthopedics", "ORTH"),
        ("Gastroenterology", "GAST"), ("Nephrology", "NEPH"), ("Dermatology", "DERM"),
        ("Pediatrics", "PEDI"), ("General Medicine", "GMED"), ("Emergency Medicine", "EMER"),
        ("Biomedical Engineering", "BIOM"), ("Radiology", "RADI"), ("Psychiatry", "PSYC")
    ]
    for i in range(1, 16):
        did = f"11111111-0002-0000-0000-{i:012d}"
        name, code = dept_names[i-1]
        cur.execute(dept_sql, (did, HOSP_ID, f"SYN-{name}", f"SYN-{code}-{i:02d}", f"Dr. SYN Head {i:02d}"))
    print("  15 Synthetic departments seeded.")

    print("\n--- 3. Seeding Auth Users & Profiles (15 Doctors + 15 Patients + Admin + Receptionist) ---")
    user_sql = """
        INSERT INTO auth.users (
            id, email, aud, role, instance_id, created_at, updated_at
        ) VALUES (%s, %s, 'authenticated', 'authenticated', '00000000-0000-0000-0000-000000000000', NOW(), NOW())
        ON CONFLICT (id) DO NOTHING;
    """
    profile_sql = """
        INSERT INTO public.profiles (
            id, hospital_id, role, full_name, email, phone, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    # 15 distinct doctors (UIDs 1..15)
    for i in range(1, 16):
        uid = f"11111111-0003-0000-0000-{i:012d}"
        email = f"syn.doctor{i:02d}@carebridge.test"
        cur.execute(user_sql, (uid, email))
        cur.execute(profile_sql, (uid, HOSP_ID, "doctor", f"Dr. SYN Doctor {i:02d}, MD", email, f"+1-555-02{i:02d}", True))

    # 15 distinct patients (UIDs 16..30)
    for i in range(1, 16):
        uid = f"11111111-0003-0000-0000-{15+i:012d}"
        email = f"syn.patient{i:02d}@carebridge.test"
        cur.execute(user_sql, (uid, email))
        cur.execute(profile_sql, (uid, HOSP_ID, "patient", f"SYN Patient User {i:02d}", email, f"+1-555-03{i:02d}", True))

    # Admin (UID 31), Receptionist (UID 32)
    admin_uid = "11111111-0003-0000-0000-000000000031"
    cur.execute(user_sql, (admin_uid, "syn.admin@carebridge.test"))
    cur.execute(profile_sql, (admin_uid, HOSP_ID, "hospital_admin", "SYN Chief Admin", "syn.admin@carebridge.test", "+1-555-0401", True))

    rec_uid = "11111111-0003-0000-0000-000000000032"
    cur.execute(user_sql, (rec_uid, "syn.receptionist@carebridge.test"))
    cur.execute(profile_sql, (rec_uid, HOSP_ID, "receptionist", "SYN Lead Receptionist", "syn.receptionist@carebridge.test", "+1-555-0402", True))
    print("  32 Synthetic auth users & profiles seeded.")

    print("\n--- 4. Seeding Doctors (15 Distinct Doctor Credentials) ---")
    doc_sql = """
        INSERT INTO public.doctors (
            id, hospital_id, profile_id, department_id, license_number, specialization,
            qualification, opd_room, consultation_fee, is_available
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        doc_id = f"11111111-0004-0000-0000-{i:012d}"
        prof_id = f"11111111-0003-0000-0000-{i:012d}"
        dept_id = f"11111111-0002-0000-0000-{i:012d}"
        cur.execute(doc_sql, (
            doc_id, HOSP_ID, prof_id, dept_id,
            f"SYN-MED-LIC-{i:04d}", dept_names[i-1][0], "MBBS, MD, DM",
            f"OPD-{100+i}", 500.00 + (i * 50), True
        ))
    print("  15 Synthetic doctors seeded.")

    print("\n--- 5. Seeding Patients (15 Clinical Patients) ---")
    pat_sql = """
        INSERT INTO public.patients (
            id, hospital_id, mrn, first_name, last_name, date_of_birth, gender,
            blood_group, phone, email, address, emergency_contact_name, emergency_contact_phone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    genders = ["male", "female", "other", "female", "male"] # lowercase
    bloods = ["O+", "A+", "B+", "AB+", "O-"]
    for i in range(1, 16):
        pid = f"11111111-0005-0000-0000-{i:012d}"
        cur.execute(pat_sql, (
            pid, HOSP_ID, f"SYN-MRN-{i:03d}", f"SyntheticFirst{i:02d}", f"SyntheticLast{i:02d}",
            f"198{i%10}-0{((i%9)+1):01d}-15", genders[i%5], bloods[i%5],
            f"+1-555-03{i:02d}", f"patient{i:02d}@syn-records.test",
            f"Suite {i*12}, Silicon Park, Bangalore", f"EmergencyContact {i:02d}", f"+1-555-99{i:02d}"
        ))
    print("  15 Synthetic patients seeded.")

    print("\n--- 6. Seeding Patient Accounts (15 User-Patient Relationship Accounts) ---")
    acc_sql = """
        INSERT INTO public.patient_accounts (
            id, hospital_id, user_id, patient_id, relationship, status, verified_at, verified_by
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        aid = f"11111111-0006-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        uid = f"11111111-0003-0000-0000-{15+i:012d}" # Distinct patient user
        cur.execute(acc_sql, (aid, HOSP_ID, uid, pid, "self", "verified", admin_uid))
    print("  15 Synthetic patient accounts seeded.")

    print("\n--- 7. Seeding Appointments (15 Scheduled, Confirmed & Completed Visits) ---")
    apt_sql = """
        INSERT INTO public.appointments (
            id, hospital_id, patient_id, doctor_id, department_id, scheduled_at, ends_at,
            status, reason_for_visit, clinical_notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    apt_statuses = ["scheduled", "confirmed", "in_progress", "completed", "scheduled"]
    for i in range(1, 16):
        apt_id = f"11111111-0007-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        doc_id = f"11111111-0004-0000-0000-{i:012d}" # Distinct doctor per appointment avoids exclusion lock!
        dept_id = f"11111111-0002-0000-0000-{i:012d}"
        status = apt_statuses[i % len(apt_statuses)]
        cur.execute(apt_sql, (
            apt_id, HOSP_ID, pid, doc_id, dept_id,
            f"2026-10-18 {8+(i%8):02d}:00:00+00", f"2026-10-18 {8+(i%8):02d}:30:00+00",
            status, f"Routine follow-up for condition #{i:02d}", f"Patient stable. Evaluated by {dept_names[i-1][0]}."
        ))
    print("  15 Synthetic appointments seeded.")

    print("\n--- 8. Seeding Clinical Documents (15 Lab Reports & Discharge Summaries) ---")
    doc_file_sql = """
        INSERT INTO public.clinical_documents (
            id, hospital_id, patient_id, uploaded_by, document_type, file_name,
            mime_type, file_size_bytes, storage_path, ocr_status, raw_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        cdoc_id = f"11111111-0008-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        doc_uid = f"11111111-0003-0000-0000-{i:012d}" # auth.users doctor id
        cur.execute(doc_file_sql, (
            cdoc_id, HOSP_ID, pid, doc_uid, "lab_report" if i%2==1 else "discharge_summary",
            f"SYN_LabReport_{i:02d}.pdf", "application/pdf", 1024 * (100 + i),
            f"/storage/clinical_documents/syn_{i:02d}.pdf", "completed",
            f"SYNTHETIC CLINICAL REPORT: Patient MRN SYN-MRN-{i:03d}. Fasting Blood Glucose: {110+i*5} mg/dL, HbA1c: {6.5+i*0.2:.1f}%."
        ))
    print("  15 Synthetic clinical documents seeded.")

    print("\n--- 9. Seeding Extracted Entities (15 Clinical Biomarkers & Diagnoses) ---")
    ent_sql = """
        INSERT INTO public.extracted_entities (
            id, hospital_id, document_id, patient_id, entity_category,
            extracted_data, confidence_score, verification_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        eid = f"11111111-0009-0000-0000-{i:012d}"
        cdoc_id = f"11111111-0008-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        data = {
            "test_name": "Fasting Blood Glucose" if i%2==1 else "Serum Creatinine",
            "value": 110 + i * 5 if i%2==1 else round(0.8 + (i * 0.1), 2),
            "unit": "mg/dL",
            "reference_range": "70-100 mg/dL" if i%2==1 else "0.7-1.3 mg/dL",
            "clinical_interpretation": "Elevated - Pre-diabetic marker" if i%2==1 else "Normal renal profile"
        }
        cur.execute(ent_sql, (
            eid, HOSP_ID, cdoc_id, pid, "lab_result", json.dumps(data), 0.95, "verified"
        ))
    print("  15 Synthetic extracted entities seeded.")

    print("\n--- 10. Seeding Clinical Conflicts (15 Drug-Drug & Duplicate Conflicts) ---")
    conf_sql = """
        INSERT INTO public.clinical_conflicts (
            id, hospital_id, patient_id, conflict_type, review_priority,
            title, clinical_summary, patient_friendly_summary, resolution_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        cid = f"11111111-0010-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        cur.execute(conf_sql, (
            cid, HOSP_ID, pid, "drug_drug_interaction" if i%2==1 else "duplicate_therapy",
            "high" if i%3==1 else "moderate", f"SYN Conflict Alert #{i:02d}",
            f"Potential adverse interaction detected between prescribed Medication #{i:02d} and historical therapy.",
            "Please consult your physician before combining these two medications.", "unresolved"
        ))
    print("  15 Synthetic clinical conflicts seeded.")

    print("\n--- 11. Seeding Clinical Conflict Sources (15 Junction Links with Full Schema) ---")
    csrc_sql = """
        INSERT INTO public.clinical_conflict_sources (
            id, hospital_id, conflict_id, document_id, entity_id, role_in_conflict, citation_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        csid = f"11111111-0011-0000-0000-{i:012d}"
        cid = f"11111111-0010-0000-0000-{i:012d}"
        cdoc_id = f"11111111-0008-0000-0000-{i:012d}"
        eid = f"11111111-0009-0000-0000-{i:012d}"
        cur.execute(csrc_sql, (
            csid, HOSP_ID, cid, cdoc_id, eid,
            "baseline_evidence", f"Referenced biomarker finding in SYN Document #{i:02d}"
        ))
    print("  15 Synthetic clinical conflict sources seeded.")

    print("\n--- 12. Seeding Care Tasks (15 Tasks including IoMT Alarms) ---")
    task_sql = """
        INSERT INTO public.care_tasks (
            id, hospital_id, patient_id, encounter_id, task_type, priority, status,
            title, description, assigned_role, completion_notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        tid = f"11111111-0012-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        apt_id = f"11111111-0007-0000-0000-{i:012d}"
        ttype = "medication_reconciliation" if i%2==1 else "lab_review"
        cur.execute(task_sql, (
            tid, HOSP_ID, pid, apt_id, ttype, "high" if i%2==1 else "routine",
            "pending" if i%2==1 else "completed",
            f"SYN Care Task #{i:02d}: Clinical Review",
            f"Perform clinical protocol follow-up for patient MRN SYN-MRN-{i:03d}.",
            "doctor" if i%2==1 else "nurse",
            f"Care task #{i:02d} verified by clinical coordination."
        ))
    print("  15 Synthetic care tasks seeded.")

    print("\n--- 13. Seeding Prescriptions (15 Tamper-Evident e-Prescriptions) ---")
    rx_sql = """
        INSERT INTO public.prescriptions (
            id, hospital_id, patient_id, doctor_id, encounter_id, status,
            diagnosis_context, notes, verification_hash, issued_at, valid_until
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '30 days')
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        rx_id = f"11111111-0013-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        doc_uid = f"11111111-0003-0000-0000-{i:012d}" # auth.users doctor id!
        apt_id = f"11111111-0007-0000-0000-{i:012d}"
        cur.execute(rx_sql, (
            rx_id, HOSP_ID, pid, doc_uid, apt_id, "prescribed",
            f"Hypertensive Disorder Stage {1+(i%2)}", f"Take with water after meals. Regimen #{i:02d}.",
            f"hash_syn_rx_{i:04d}_abcdef1234567890"
        ))
    print("  15 Synthetic prescriptions seeded.")

    print("\n--- 14. Seeding Prescription Items (15 Medication Line Items) ---")
    rx_item_sql = """
        INSERT INTO public.prescription_items (
            id, hospital_id, prescription_id, drug_name, therapeutic_class,
            dosage, route, frequency, duration_days, instructions, refills_remaining
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    drugs = [
        ("Amlodipine", "Calcium Channel Blocker", "5mg", "Oral", "Once Daily", 30),
        ("Metformin", "Biguanide Antidiabetic", "500mg", "Oral", "Twice Daily", 30),
        ("Atorvastatin", "HMG-CoA Reductase Inhibitor", "20mg", "Oral", "Once Daily at Bedtime", 30),
        ("Losartan", "Angiotensin II Receptor Antagonist", "50mg", "Oral", "Once Daily", 30),
        ("Omeprazole", "Proton Pump Inhibitor", "20mg", "Oral", "Once Daily Before Breakfast", 14)
    ]
    for i in range(1, 16):
        rx_item_id = f"11111111-0014-0000-0000-{i:012d}"
        rx_id = f"11111111-0013-0000-0000-{i:012d}"
        drug_name, th_class, dosage, route, freq, dur = drugs[(i - 1) % len(drugs)]
        cur.execute(rx_item_sql, (
            rx_item_id, HOSP_ID, rx_id, drug_name, th_class,
            dosage, route, freq, dur, f"Follow schedule #{i:02d}.", 2
        ))
    print("  15 Synthetic prescription items seeded.")

    print("\n--- 15. Seeding Medication Adherence Logs (15 Patient Logs) ---")
    adh_sql = """
        INSERT INTO public.medication_adherence_logs (
            id, hospital_id, patient_id, prescription_item_id, scheduled_time, taken_at, status, notes
        ) VALUES (%s, %s, %s, %s, NOW() - INTERVAL '1 day', NOW() - INTERVAL '23 hours', %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        adh_id = f"11111111-0015-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        rx_item_id = f"11111111-0014-0000-0000-{i:012d}"
        cur.execute(adh_sql, (
            adh_id, HOSP_ID, pid, rx_item_id, "taken" if i%3!=0 else "missed",
            f"Adherence confirmed via patient portal for day {i:02d}."
        ))
    print("  15 Synthetic medication adherence logs seeded.")

    print("\n--- 16. Seeding Patient Insurance Policies (15 Health Policies) ---")
    pol_sql = """
        INSERT INTO public.patient_insurance_policies (
            id, hospital_id, patient_id, provider_name, policy_number,
            policy_holder_name, relation_to_patient, sum_insured_inr, remaining_balance_inr,
            copay_percentage, deductible_inr, exclusions, valid_from, valid_until, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '2026-01-01', '2027-01-01', 'active')
        ON CONFLICT (id) DO NOTHING;
    """
    providers = ["Star Health Premier", "HDFC ERGO Health", "Care Health Care Advantage", "ICICI Lombard Complete", "Max Bupa ReAssure"]
    for i in range(1, 16):
        pol_id = f"11111111-0016-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        pname = providers[(i - 1) % len(providers)]
        cur.execute(pol_sql, (
            pol_id, HOSP_ID, pid, pname, f"POL-SYN-2026-{i:04d}",
            f"SyntheticFirst{i:02d} SyntheticLast{i:02d}", "self",
            1000000.00, 850000.00 - (i * 10000), 10.00, 2500.00,
            json.dumps(["cosmetic_surgery", "experimental_therapy"])
        ))
    print("  15 Synthetic insurance policies seeded.")

    print("\n--- 17. Seeding Insurance Claims (15 Pre-Auth & Inpatient Claims) ---")
    claim_sql = """
        INSERT INTO public.insurance_claims (
            id, hospital_id, policy_id, patient_id, appointment_id, claim_type,
            requested_amount_inr, approved_amount_inr, patient_copay_amount_inr,
            adjudication_status, denial_reason, settlement_reference, rule_version,
            calculation_breakdown
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """
    for i in range(1, 16):
        claim_id = f"11111111-0017-0000-0000-{i:012d}"
        pol_id = f"11111111-0016-0000-0000-{i:012d}"
        pid = f"11111111-0005-0000-0000-{i:012d}"
        apt_id = f"11111111-0007-0000-0000-{i:012d}"
        req = 15000.00 + (i * 1000)
        app = req * 0.90
        copay = req * 0.10
        breakdown = {
            "requested": req,
            "deductible_applied": 0,
            "copay_percentage": 10.0,
            "patient_payable": copay,
            "insurer_payable": app
        }
        cur.execute(claim_sql, (
            claim_id, HOSP_ID, pol_id, pid, apt_id, "cashless_settlement",
            req, app, copay, "claim_submitted" if i%3!=0 else "pre_auth_approved",
            None, f"SETTLE-SYN-{i:05d}", "v1.2-rule-engine", json.dumps(breakdown)
        ))
    print("  15 Synthetic insurance claims seeded.")

    cur.execute("COMMIT;")
    print("\n=======================================================")
    print("SUCCESS: ALL 17 TABLES SEEDED WITH 15 SYNTHETIC RECORDS")
    print("=======================================================")

except Exception as e:
    cur.execute("ROLLBACK;")
    print(f"\nSEEDING FAILED: {e}")
    raise
finally:
    conn.close()
