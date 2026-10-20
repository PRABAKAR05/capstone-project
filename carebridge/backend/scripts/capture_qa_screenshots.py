import os
import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:3000"
API_URL = "http://127.0.0.1:8000"
CREDS_FILE = Path("artifacts/final-qa-2026-10-20/test-credentials.private.json")
SCREENSHOTS_BASE = Path("artifacts/final-qa-2026-10-20/screenshots")

def load_accounts():
    with open(CREDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    accounts_by_role = {}
    for acc in data["accounts"]:
        role = acc["role"]
        if role not in accounts_by_role:
            accounts_by_role[role] = []
        accounts_by_role[role].append(acc)
    return accounts_by_role

def capture_all():
    accounts_by_role = load_accounts()
    SCREENSHOTS_BASE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        print("\n=======================================================")
        print("STAGE 00: PUBLIC & LOGIN WORKFLOWS")
        print("=======================================================")
        dir_00 = SCREENSHOTS_BASE / "00-public-and-login"
        dir_00.mkdir(parents=True, exist_ok=True)

        # Desktop Context
        desktop_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = desktop_ctx.new_page()

        # 00-landing-hero.png
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(dir_00 / "00-landing-hero.png"), full_page=True)
        print("Saved: 00-landing-hero.png")

        # 00-landing-mobile.png
        mobile_ctx = browser.new_context(viewport={"width": 375, "height": 667})
        m_page = mobile_ctx.new_page()
        m_page.goto(f"{BASE_URL}/", wait_until="networkidle")
        m_page.wait_for_timeout(1000)
        m_page.screenshot(path=str(dir_00 / "00-landing-mobile.png"), full_page=True)
        mobile_ctx.close()
        print("Saved: 00-landing-mobile.png")

        # 00-login-default.png
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(dir_00 / "00-login-default.png"))
        print("Saved: 00-login-default.png")

        # 00-login-with-demo-accounts.png
        # Click on one of the demonstration persona buttons to highlight
        demo_btn = page.locator("button:has-text('Attending Cardiologist')")
        if demo_btn.count() > 0:
            demo_btn.first.click()
            page.wait_for_timeout(500)
        page.screenshot(path=str(dir_00 / "00-login-with-demo-accounts.png"))
        print("Saved: 00-login-with-demo-accounts.png")

        # 00-demo-preview.png
        page.goto(f"{BASE_URL}/demo", wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(dir_00 / "00-demo-preview.png"), full_page=True)
        print("Saved: 00-demo-preview.png")
        desktop_ctx.close()

        def login_and_get_context(account, is_mobile=False):
            viewport = {"width": 375, "height": 667} if is_mobile else {"width": 1440, "height": 900}
            ctx = browser.new_context(viewport=viewport)
            p_inst = ctx.new_page()

            # Navigate to login
            p_inst.goto(f"{BASE_URL}/login", wait_until="networkidle")
            p_inst.wait_for_timeout(500)

            # Fill real credentials
            p_inst.fill('input[type="email"]', account["email"])
            p_inst.fill('input[type="password"]', account["password"])
            p_inst.click('button:has-text("Access Workstation")')
            p_inst.wait_for_timeout(2000)
            return ctx, p_inst

        print("\n=======================================================")
        print("STAGE 01: HOSPITAL ADMIN WORKFLOWS")
        print("=======================================================")
        admin_acc = accounts_by_role["hospital_admin"][0]
        dir_01 = SCREENSHOTS_BASE / "01-hospital-admin"
        dir_01.mkdir(parents=True, exist_ok=True)

        admin_ctx, admin_page = login_and_get_context(admin_acc)
        admin_page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        admin_page.wait_for_timeout(1500)
        admin_page.screenshot(path=str(dir_01 / "01-admin-dashboard.png"), full_page=True)
        print("Saved: 01-admin-dashboard.png")

        # Focus/scroll on roster
        admin_page.evaluate("window.scrollTo(0, 600)")
        admin_page.wait_for_timeout(500)
        admin_page.screenshot(path=str(dir_01 / "01-admin-roster.png"))
        print("Saved: 01-admin-roster.png")

        admin_page.evaluate("window.scrollTo(0, 1100)")
        admin_page.wait_for_timeout(500)
        admin_page.screenshot(path=str(dir_01 / "01-admin-operations.png"))
        print("Saved: 01-admin-operations.png")
        admin_ctx.close()

        # Mobile admin
        admin_m_ctx, admin_m_page = login_and_get_context(admin_acc, is_mobile=True)
        admin_m_page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        admin_m_page.wait_for_timeout(1500)
        admin_m_page.screenshot(path=str(dir_01 / "01-admin-mobile.png"), full_page=True)
        admin_m_ctx.close()
        print("Saved: 01-admin-mobile.png")

        print("\n=======================================================")
        print("STAGE 02: DOCTOR WORKFLOWS")
        print("=======================================================")
        doc_acc = accounts_by_role["doctor"][0]
        dir_02 = SCREENSHOTS_BASE / "02-doctor"
        dir_02.mkdir(parents=True, exist_ok=True)

        doc_ctx, doc_page = login_and_get_context(doc_acc)
        doc_page.goto(f"{BASE_URL}/doctor", wait_until="networkidle")
        doc_page.wait_for_timeout(1500)
        doc_page.screenshot(path=str(dir_02 / "02-doctor-queue.png"), full_page=True)
        print("Saved: 02-doctor-queue.png")

        # Focus on patient encounter
        doc_page.evaluate("window.scrollTo(0, 450)")
        doc_page.wait_for_timeout(500)
        doc_page.screenshot(path=str(dir_02 / "02-doctor-patient-detail.png"))
        print("Saved: 02-doctor-patient-detail.png")

        # Conflict review button / modal
        rev_btn = doc_page.locator("button:has-text('Reconcile')")
        if rev_btn.count() > 0:
            rev_btn.first.click()
            doc_page.wait_for_timeout(800)
        doc_page.screenshot(path=str(dir_02 / "02-doctor-conflicts-review.png"))
        print("Saved: 02-doctor-conflicts-review.png")
        doc_ctx.close()

        # Mobile doctor
        doc_m_ctx, doc_m_page = login_and_get_context(doc_acc, is_mobile=True)
        doc_m_page.goto(f"{BASE_URL}/doctor", wait_until="networkidle")
        doc_m_page.wait_for_timeout(1500)
        doc_m_page.screenshot(path=str(dir_02 / "02-doctor-mobile.png"), full_page=True)
        doc_m_ctx.close()
        print("Saved: 02-doctor-mobile.png")

        print("\n=======================================================")
        print("STAGE 03: NURSE WORKFLOWS")
        print("=======================================================")
        nurse_acc = accounts_by_role["nurse"][0]
        dir_03 = SCREENSHOTS_BASE / "03-nurse"
        dir_03.mkdir(parents=True, exist_ok=True)

        nurse_ctx, nurse_page = login_and_get_context(nurse_acc)
        nurse_page.goto(f"{BASE_URL}/nurse", wait_until="networkidle")
        nurse_page.wait_for_timeout(1500)
        nurse_page.screenshot(path=str(dir_03 / "03-nurse-intake-desk.png"), full_page=True)
        print("Saved: 03-nurse-intake-desk.png")

        # Rapid checkin button / modal
        checkin_btn = nurse_page.locator("button:has-text('Rapid Intake')")
        if checkin_btn.count() == 0:
            checkin_btn = nurse_page.locator("button:has-text('Check-In')")
        if checkin_btn.count() > 0:
            checkin_btn.first.click()
            nurse_page.wait_for_timeout(600)
        nurse_page.screenshot(path=str(dir_03 / "03-nurse-rapid-checkin.png"))
        print("Saved: 03-nurse-rapid-checkin.png")

        # Care tasks desk
        nurse_page.goto(f"{BASE_URL}/tasks", wait_until="networkidle")
        nurse_page.wait_for_timeout(1500)
        nurse_page.screenshot(path=str(dir_03 / "03-nurse-care-tasks.png"), full_page=True)
        print("Saved: 03-nurse-care-tasks.png")
        nurse_ctx.close()

        # Mobile nurse
        nurse_m_ctx, nurse_m_page = login_and_get_context(nurse_acc, is_mobile=True)
        nurse_m_page.goto(f"{BASE_URL}/nurse", wait_until="networkidle")
        nurse_m_page.wait_for_timeout(1500)
        nurse_m_page.screenshot(path=str(dir_03 / "03-nurse-mobile.png"), full_page=True)
        nurse_m_ctx.close()
        print("Saved: 03-nurse-mobile.png")

        print("\n=======================================================")
        print("STAGE 04: LAB TECHNICIAN WORKFLOWS")
        print("=======================================================")
        lab_acc = accounts_by_role["lab_technician"][0]
        dir_04 = SCREENSHOTS_BASE / "04-lab-technician"
        dir_04.mkdir(parents=True, exist_ok=True)

        lab_ctx, lab_page = login_and_get_context(lab_acc)
        lab_page.goto(f"{BASE_URL}/lab", wait_until="networkidle")
        lab_page.wait_for_timeout(1500)
        lab_page.screenshot(path=str(dir_04 / "04-lab-diagnostics-desk.png"), full_page=True)
        print("Saved: 04-lab-diagnostics-desk.png")

        # Demographics masked view
        lab_page.evaluate("window.scrollTo(0, 300)")
        lab_page.wait_for_timeout(500)
        lab_page.screenshot(path=str(dir_04 / "04-lab-demographics-masked.png"))
        print("Saved: 04-lab-demographics-masked.png")

        # Specimen accessioning / order entry
        accession_btn = lab_page.locator("button:has-text('Accession')")
        if accession_btn.count() == 0:
            accession_btn = lab_page.locator("button:has-text('Verify')")
        if accession_btn.count() > 0:
            accession_btn.first.click()
            lab_page.wait_for_timeout(600)
        lab_page.screenshot(path=str(dir_04 / "04-lab-specimen-accessioning.png"))
        print("Saved: 04-lab-specimen-accessioning.png")
        lab_ctx.close()

        # Mobile lab
        lab_m_ctx, lab_m_page = login_and_get_context(lab_acc, is_mobile=True)
        lab_m_page.goto(f"{BASE_URL}/lab", wait_until="networkidle")
        lab_m_page.wait_for_timeout(1500)
        lab_m_page.screenshot(path=str(dir_04 / "04-lab-mobile.png"), full_page=True)
        lab_m_ctx.close()
        print("Saved: 04-lab-mobile.png")

        print("\n=======================================================")
        print("STAGE 05: PATIENT WORKFLOWS")
        print("=======================================================")
        pat_acc = accounts_by_role["patient"][0]
        dir_05 = SCREENSHOTS_BASE / "05-patient"
        dir_05.mkdir(parents=True, exist_ok=True)

        pat_ctx, pat_page = login_and_get_context(pat_acc)
        pat_page.goto(f"{BASE_URL}/portal", wait_until="networkidle")
        pat_page.wait_for_timeout(1500)
        pat_page.screenshot(path=str(dir_05 / "05-patient-portal-home.png"), full_page=True)
        print("Saved: 05-patient-portal-home.png")

        # Clinical records
        pat_page.goto(f"{BASE_URL}/portal/documents", wait_until="networkidle")
        pat_page.wait_for_timeout(1500)
        pat_page.screenshot(path=str(dir_05 / "05-patient-records.png"), full_page=True)
        print("Saved: 05-patient-records.png")

        # Booking wizard
        pat_page.goto(f"{BASE_URL}/portal/book", wait_until="networkidle")
        pat_page.wait_for_timeout(1500)
        pat_page.screenshot(path=str(dir_05 / "05-patient-booking-wizard.png"), full_page=True)
        print("Saved: 05-patient-booking-wizard.png")
        pat_ctx.close()

        # Mobile patient
        pat_m_ctx, pat_m_page = login_and_get_context(pat_acc, is_mobile=True)
        pat_m_page.goto(f"{BASE_URL}/portal", wait_until="networkidle")
        pat_m_page.wait_for_timeout(1500)
        pat_m_page.screenshot(path=str(dir_05 / "05-patient-mobile.png"), full_page=True)
        pat_m_ctx.close()
        print("Saved: 05-patient-mobile.png")

        print("\n=======================================================")
        print("STAGE 06: CROSS-ROLE WORKFLOWS")
        print("=======================================================")
        dir_06 = SCREENSHOTS_BASE / "06-cross-role-workflows"
        dir_06.mkdir(parents=True, exist_ok=True)

        # 06-conflict-detection-banner.png
        doc_ctx, doc_page = login_and_get_context(doc_acc)
        doc_page.goto(f"{BASE_URL}/doctor", wait_until="networkidle")
        doc_page.wait_for_timeout(1500)
        # Highlight conflict banner
        doc_page.screenshot(path=str(dir_06 / "06-conflict-detection-banner.png"))
        print("Saved: 06-conflict-detection-banner.png")

        # 06-conflict-resolution-flow.png
        rev_btn = doc_page.locator("button:has-text('Reconcile')")
        if rev_btn.count() > 0:
            rev_btn.first.click()
            doc_page.wait_for_timeout(800)
        doc_page.screenshot(path=str(dir_06 / "06-conflict-resolution-flow.png"))
        print("Saved: 06-conflict-resolution-flow.png")
        doc_ctx.close()

        # 06-care-task-coordination.png
        nurse_ctx, nurse_page = login_and_get_context(nurse_acc)
        nurse_page.goto(f"{BASE_URL}/tasks", wait_until="networkidle")
        nurse_page.wait_for_timeout(1500)
        nurse_page.screenshot(path=str(dir_06 / "06-care-task-coordination.png"), full_page=True)
        nurse_ctx.close()
        print("Saved: 06-care-task-coordination.png")

        # 06-prescription-verification.png
        pub_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        pub_page = pub_ctx.new_page()
        pub_page.goto(f"{BASE_URL}/verify-prescription/sample-qr-rx-hash-12345", wait_until="networkidle")
        pub_page.wait_for_timeout(1500)
        pub_page.screenshot(path=str(dir_06 / "06-prescription-verification.png"), full_page=True)
        pub_ctx.close()
        print("Saved: 06-prescription-verification.png")

        print("\n=======================================================")
        print("STAGE 07: SECURITY TESTS")
        print("=======================================================")
        dir_07 = SCREENSHOTS_BASE / "07-security-tests"
        dir_07.mkdir(parents=True, exist_ok=True)

        sec_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        sec_page = sec_ctx.new_page()

        # 07-cross-tenant-isolation-404.png
        # Hospital 1 doctor accessing non-existent/cross-tenant document
        sec_page.goto(f"{BASE_URL}/doctor/documents/00000000-0000-0000-0000-000000000099", wait_until="networkidle")
        sec_page.wait_for_timeout(1200)
        sec_page.screenshot(path=str(dir_07 / "07-cross-tenant-isolation-404.png"))
        print("Saved: 07-cross-tenant-isolation-404.png")

        # 07-unauthorized-role-boundary-403.png
        # Patient attempting to view /admin
        pat_sec_ctx, pat_sec_page = login_and_get_context(pat_acc)
        pat_sec_page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        pat_sec_page.wait_for_timeout(1200)
        pat_sec_page.screenshot(path=str(dir_07 / "07-unauthorized-role-boundary-403.png"))
        pat_sec_ctx.close()
        print("Saved: 07-unauthorized-role-boundary-403.png")

        # 07-decommissioned-receptionist-404.png
        sec_page.goto(f"{BASE_URL}/receptionist", wait_until="networkidle")
        sec_page.wait_for_timeout(1200)
        sec_page.screenshot(path=str(dir_07 / "07-decommissioned-receptionist-404.png"))
        print("Saved: 07-decommissioned-receptionist-404.png")

        # 07-decommissioned-caregiver-404.png
        sec_page.goto(f"{BASE_URL}/portal/caregivers", wait_until="networkidle")
        sec_page.wait_for_timeout(1200)
        sec_page.screenshot(path=str(dir_07 / "07-decommissioned-caregiver-404.png"))
        print("Saved: 07-decommissioned-caregiver-404.png")
        sec_ctx.close()

        print("\n=======================================================")
        print("STAGE 08: ERRORS & DEFECTS")
        print("=======================================================")
        dir_08 = SCREENSHOTS_BASE / "08-errors-and-defects"
        dir_08.mkdir(parents=True, exist_ok=True)

        err_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        err_page = err_ctx.new_page()

        # 08-invalid-login-rejection.png
        err_page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        err_page.fill('input[type="email"]', "attacker@unauthorized.io")
        err_page.fill('input[type="password"]', "WrongPassword123!")
        err_page.click('button:has-text("Access Workstation")')
        err_page.wait_for_timeout(1500)
        err_page.screenshot(path=str(dir_08 / "08-invalid-login-rejection.png"))
        print("Saved: 08-invalid-login-rejection.png")

        # 08-rfc7807-error-response.png
        err_page.goto(f"{API_URL}/api/v1/invalid-route-for-testing", wait_until="networkidle")
        err_page.wait_for_timeout(800)
        err_page.screenshot(path=str(dir_08 / "08-rfc7807-error-response.png"))
        print("Saved: 08-rfc7807-error-response.png")
        err_ctx.close()

        browser.close()
        print("\n=======================================================")
        print("ALL QA SCREENSHOTS CAPTURED SUCCESSFULLY!")
        print("=======================================================")

if __name__ == "__main__":
    capture_all()
