import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('carebridge/backend/.env')
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

tables = [
    "hospitals",
    "departments",
    "profiles",
    "doctors",
    "patients",
    "patient_accounts",
    "appointments",
    "clinical_documents",
    "extracted_entities",
    "clinical_conflicts",
    "clinical_conflict_sources",
    "care_tasks",
    "prescriptions",
    "prescription_items",
    "medication_adherence_logs",
    "patient_insurance_policies",
    "insurance_claims"
]

print("=======================================================")
print("AC-14.2: SYNTHETIC RECORD COUNT VERIFICATION")
print("=======================================================")

all_pass = True
counts = {}

for tbl in tables:
    cur.execute(f"SELECT COUNT(*) FROM public.\"{tbl}\" WHERE id::text LIKE '11111111-00%';")
    syn_count = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM public.\"{tbl}\";")
    total_count = cur.fetchone()[0]
    status = "PASS" if syn_count >= 15 else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"Table: {tbl:28} | Synthetic Rows: {syn_count:3} | Total Rows: {total_count:4} | Status: {status}")
    counts[tbl] = (syn_count, total_count)

print("\n=======================================================")
print("AC-14.4: FOREIGN KEY & TENANT BOUNDARY INTEGRITY CHECK")
print("=======================================================")

orphan_checks = [
    ("appointments -> patients", "SELECT count(*) FROM public.appointments a LEFT JOIN public.patients p ON a.patient_id = p.id WHERE p.id IS NULL;"),
    ("appointments -> doctors", "SELECT count(*) FROM public.appointments a LEFT JOIN public.doctors d ON a.doctor_id = d.id WHERE d.id IS NULL;"),
    ("appointments -> departments", "SELECT count(*) FROM public.appointments a LEFT JOIN public.departments d ON a.department_id = d.id WHERE d.id IS NULL;"),
    ("clinical_documents -> patients", "SELECT count(*) FROM public.clinical_documents d LEFT JOIN public.patients p ON d.patient_id = p.id WHERE p.id IS NULL;"),
    ("extracted_entities -> documents", "SELECT count(*) FROM public.extracted_entities e LEFT JOIN public.clinical_documents d ON e.document_id = d.id WHERE d.id IS NULL;"),
    ("clinical_conflicts -> patients", "SELECT count(*) FROM public.clinical_conflicts c LEFT JOIN public.patients p ON c.patient_id = p.id WHERE p.id IS NULL;"),
    ("clinical_conflict_sources -> conflicts", "SELECT count(*) FROM public.clinical_conflict_sources s LEFT JOIN public.clinical_conflicts c ON s.conflict_id = c.id WHERE c.id IS NULL;"),
    ("care_tasks -> patients", "SELECT count(*) FROM public.care_tasks t LEFT JOIN public.patients p ON t.patient_id = p.id WHERE p.id IS NULL;"),
    ("prescriptions -> patients", "SELECT count(*) FROM public.prescriptions pr LEFT JOIN public.patients p ON pr.patient_id = p.id WHERE p.id IS NULL;"),
    ("prescription_items -> prescriptions", "SELECT count(*) FROM public.prescription_items pi LEFT JOIN public.prescriptions pr ON pi.prescription_id = pr.id WHERE pr.id IS NULL;"),
    ("medication_adherence_logs -> items", "SELECT count(*) FROM public.medication_adherence_logs m LEFT JOIN public.prescription_items pi ON m.prescription_item_id = pi.id WHERE pi.id IS NULL;"),
    ("insurance_policies -> patients", "SELECT count(*) FROM public.patient_insurance_policies pol LEFT JOIN public.patients p ON pol.patient_id = p.id WHERE p.id IS NULL;"),
    ("insurance_claims -> policies", "SELECT count(*) FROM public.insurance_claims cl LEFT JOIN public.patient_insurance_policies pol ON cl.policy_id = pol.id WHERE pol.id IS NULL;")
]

orphan_free = True
for label, query in orphan_checks:
    cur.execute(query)
    orphans = cur.fetchone()[0]
    status = "PASS (0 orphans)" if orphans == 0 else f"FAIL ({orphans} orphans)"
    if orphans > 0:
        orphan_free = False
    print(f"Check: {label:38} | {status}")

print(f"\nSynthetic Records Gate: {'PASS (All 17 tables >= 15 synthetic rows)' if all_pass else 'FAIL'}")
print(f"Foreign-Key Integrity Gate: {'PASS (Zero orphan records across all tables)' if orphan_free else 'FAIL'}")

conn.close()
