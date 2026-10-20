import os
import sys
import json
import logging
from pathlib import Path
from fastapi.testclient import TestClient
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

load_dotenv(backend_dir / ".env")

from main import app
from app.core.security import verify_jwt_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_auth")

def run_auth_verification():
    creds_path = Path("artifacts/final-qa-2026-10-20/test-credentials.private.json")
    if not creds_path.exists():
        logger.error(f"Credentials file {creds_path} not found.")
        sys.exit(1)

    with open(creds_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("accounts", [])
    logger.info(f"Loaded {len(accounts)} synthetic accounts from {creds_path}")

    client = TestClient(app)
    results = []
    all_passed = True

    # 1. Test authenticating each of the 20 accounts
    for acc in accounts:
        email = acc["email"]
        password = acc["password"]
        role = acc["role"]
        label = acc.get("account_id", acc.get("full_name", email))

        res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        if res.status_code != 200:
            logger.error(f"FAIL: {label} ({email}) status {res.status_code}: {res.text}")
            all_passed = False
            results.append({"label": label, "email": email, "role": role, "status": "FAIL", "code": res.status_code})
            continue

        body = res.json()
        token = body.get("access_token")
        user = body.get("user", {})

        # Cryptographically verify the token
        try:
            claims = verify_jwt_token(token)
            assert claims["sub"] == user["id"]
            assert claims["aud"] == "authenticated"
            token_valid = True
        except Exception as e:
            logger.error(f"Token verification failed for {label}: {e}")
            token_valid = False
            all_passed = False

        # Test authenticated call to /api/v1/hospitals/me
        hosp_res = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token}"})
        hosp_ok = hosp_res.status_code == 200

        if hosp_ok and token_valid:
            logger.info(f"PASS: {label} [{role}] authenticated successfully (Hospital: {hosp_res.json().get('name')})")
            results.append({"label": label, "email": email, "role": role, "status": "PASS", "code": 200})
        else:
            logger.error(f"FAIL: {label} [{role}] hospital lookup status {hosp_res.status_code}")
            all_passed = False
            results.append({"label": label, "email": email, "role": role, "status": "FAIL", "code": hosp_res.status_code})

    # 2. Test negative cases
    # A. Incorrect password
    bad_pass_res = client.post("/api/v1/auth/login", json={"email": accounts[0]["email"], "password": "WrongPassword!999"})
    assert bad_pass_res.status_code == 401, f"Expected 401 on wrong password, got {bad_pass_res.status_code}"
    logger.info("PASS: Wrong password returns 401 Unauthorized")

    # B. Non-existent email
    bad_email_res = client.post("/api/v1/auth/login", json={"email": "nonexistent_doctor_xyz@hospital.org", "password": "AnyPassword!123"})
    assert bad_email_res.status_code == 401, f"Expected 401 on non-existent user, got {bad_email_res.status_code}"
    logger.info("PASS: Non-existent user returns 401 Unauthorized")

    # C. Missing credentials
    missing_res = client.post("/api/v1/auth/login", json={"email": "bad-email", "password": ""})
    assert missing_res.status_code == 422, f"Expected 422 validation error, got {missing_res.status_code}"
    logger.info("PASS: Malformed email/empty password returns 422 Validation Error")

    # Save summary report
    out_file = Path("artifacts/final-qa-2026-10-20/test-results/api-results/auth-verification-summary.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_accounts": len(accounts),
            "passed": sum(1 for r in results if r["status"] == "PASS"),
            "failed": sum(1 for r in results if r["status"] == "FAIL"),
            "negative_checks_passed": 3,
            "results": results
        }, f, indent=2)

    logger.info(f"Verification complete. Total: {len(accounts)}, Passed: {sum(1 for r in results if r['status'] == 'PASS')}")
    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    run_auth_verification()
