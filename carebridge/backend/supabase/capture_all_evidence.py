import os
import subprocess
import time

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
evidence_dir = os.path.abspath(os.path.join("docs", "phase-reports", "phase-14-evidence"))
os.makedirs(evidence_dir, exist_ok=True)

routes_desktop = [
    ("01_landing_page_desktop.png", "http://localhost:3000/"),
    ("02_guided_demo_desktop.png", "http://localhost:3000/demo"),
    ("03_login_page_desktop.png", "http://localhost:3000/login"),
    ("04_portal_patient_desktop.png", "http://localhost:3000/portal"),
    ("05_portal_book_desktop.png", "http://localhost:3000/portal/book"),
    ("06_portal_caregivers_desktop.png", "http://localhost:3000/portal/caregivers"),
    ("07_portal_documents_desktop.png", "http://localhost:3000/portal/documents"),
    ("08_receptionist_queue_desktop.png", "http://localhost:3000/receptionist"),
    ("09_receptionist_verify_desktop.png", "http://localhost:3000/receptionist/verify-caregivers"),
    ("10_doctor_workstation_desktop.png", "http://localhost:3000/doctor"),
    ("11_doctor_doc_viewer_desktop.png", "http://localhost:3000/doctor/documents/11111111-0008-0000-0000-000000000001"),
    ("12_tasks_board_desktop.png", "http://localhost:3000/tasks"),
    ("13_admin_analytics_desktop.png", "http://localhost:3000/admin"),
    ("14_verify_prescription_desktop.png", "http://localhost:3000/verify-prescription/hash_syn_rx_0001_abcdef1234567890"),
    ("15_not_found_desktop.png", "http://localhost:3000/_not-found"),
]

routes_mobile = [
    ("16_landing_page_mobile.png", "http://localhost:3000/"),
    ("17_guided_demo_mobile.png", "http://localhost:3000/demo"),
    ("18_login_page_mobile.png", "http://localhost:3000/login"),
    ("19_portal_patient_mobile.png", "http://localhost:3000/portal"),
    ("20_doctor_workstation_mobile.png", "http://localhost:3000/doctor"),
]

print(f"Starting Visual QA Screenshot Evidence Capture to: {evidence_dir}\n")

captured = []
failed = []

# Desktop
for filename, url in routes_desktop:
    out_path = os.path.join(evidence_dir, filename)
    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1280,800",
        f"--screenshot={out_path}",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        sz = os.path.getsize(out_path)
        print(f"Captured [Desktop 1280x800]: {filename:35} | {sz:7} bytes | URL: {url}")
        captured.append((filename, sz))
    else:
        print(f"FAILED [Desktop]: {filename} | URL: {url}")
        failed.append(filename)
    time.sleep(1)

# Mobile
for filename, url in routes_mobile:
    out_path = os.path.join(evidence_dir, filename)
    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=375,667",
        f"--screenshot={out_path}",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        sz = os.path.getsize(out_path)
        print(f"Captured [Mobile 375x667]:  {filename:35} | {sz:7} bytes | URL: {url}")
        captured.append((filename, sz))
    else:
        print(f"FAILED [Mobile]: {filename} | URL: {url}")
        failed.append(filename)
    time.sleep(1)

print(f"\nVisual QA Capture Complete: {len(captured)} captured, {len(failed)} failed.")
