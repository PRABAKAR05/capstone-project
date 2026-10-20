#!/usr/bin/env python3
"""
CareBridge AI - Stage 1: Out-of-band Secrets Provisioning
File: carebridge/backend/supabase/provision_dba_secrets.py

Secure, out-of-band provisioning of DBA HMAC secrets with permission validation and overwrite prevention.
"""
import os
import sys
import stat
import secrets
import argparse
import subprocess
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

KEYS_DIR = Path.home() / ".carebridge" / "keys"
KEY_FILE_PATH = KEYS_DIR / "dba_hmac.key"
ATTESTATION_KEY_PATH = KEYS_DIR / "sandbox_attestation.key"
SNAPSHOT_KEY_PATH = KEYS_DIR / "snapshot_hmac.key"

def ensure_keys_exist():
    """Generates 256-bit cryptographically secure keys if not already present."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    for name, path in [
        ("DBA HMAC Key", KEY_FILE_PATH),
        ("Sandbox Attestation Key", ATTESTATION_KEY_PATH),
        ("Snapshot HMAC Key", SNAPSHOT_KEY_PATH)
    ]:
        if not path.exists():
            key_val = secrets.token_hex(32) # 64 hex characters = 256 bits
            path.write_text(key_val)
            print(f"Generated new {name} at: {path}")
            restrict_permissions(path)
        else:
            restrict_permissions(path)

def restrict_permissions(key_path: Path) -> None:
    """Restricts file permissions to owner-only."""
    if sys.platform == "win32":
        try:
            username = os.environ.get("USERNAME") or os.environ.get("USER")
            domain = os.environ.get("USERDOMAIN")
            principal = f"{domain}\\{username}" if domain and username else username
            if principal:
                subprocess.run(
                    ["icacls", str(key_path), "/grant:r", f"{principal}:(F)"],
                    capture_output=True,
                    check=False
                )
        except Exception:
            pass
    else:
        try:
            key_path.chmod(0o600)
        except Exception:
            pass

def verify_key_file_permissions(key_path: Path) -> None:
    """Fails closed if the secret key file is readable by any other user or process."""
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found at: {key_path}")

    if sys.platform == "win32":
        cmd = ["icacls", str(key_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.lower()
        for prohibited_principal in ("everyone", "builtin\\users", "authenticated users"):
            if prohibited_principal in output and ("(r)" in output or "(f)" in output or "(m)" in output):
                # Try to restrict it automatically
                restrict_permissions(key_path)
                result2 = subprocess.run(cmd, capture_output=True, text=True, check=True)
                if prohibited_principal in result2.stdout.lower() and ("(r)" in result2.stdout.lower() or "(f)" in result2.stdout.lower()):
                    raise PermissionError(
                        f"INSECURE_KEY_PERMISSIONS: Windows key file {key_path} has open permissions granted to {prohibited_principal}. "
                        "Run icacls to restrict access strictly to the owner."
                    )
    else:
        file_stat = key_path.stat()
        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077 != 0:
            raise PermissionError(
                f"INSECURE_KEY_PERMISSIONS: Key file {key_path} has mode {oct(mode)}. "
                "Must be chmod 0400 or 0600 (owner-only access)."
            )

def provision_secret(db_conn_str: str, force_rotate: bool = False, ticket_id: str = None) -> None:
    ensure_keys_exist()
    verify_key_file_permissions(KEY_FILE_PATH)
    secret_key = KEY_FILE_PATH.read_text().strip()
    if len(secret_key) < 64:
        raise ValueError("INSUFFICIENT_ENTROPY: Secret key must contain at least 64 hex characters (256-bit entropy).")

    conn = psycopg2.connect(db_conn_str)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS carebridge_internal;
                REVOKE ALL ON SCHEMA carebridge_internal FROM PUBLIC, anon, authenticated, service_role;
                GRANT USAGE ON SCHEMA carebridge_internal TO postgres;
                
                CREATE TABLE IF NOT EXISTS carebridge_internal.auth_secrets (
                    key_name TEXT PRIMARY KEY,
                    secret_value TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                    rotated_at TIMESTAMPTZ DEFAULT timezone('utc', now())
                );
                REVOKE ALL ON TABLE carebridge_internal.auth_secrets FROM PUBLIC, anon, authenticated, service_role;
                GRANT ALL ON TABLE carebridge_internal.auth_secrets TO postgres;
            """)

            # Overwrite prevention check
            cur.execute("SELECT secret_value FROM carebridge_internal.auth_secrets WHERE key_name = 'dba_hmac_key';")
            existing = cur.fetchone()
            if existing and not force_rotate:
                print("Key dba_hmac_key is already provisioned in carebridge_internal.auth_secrets.")
                return

            if existing and force_rotate:
                if not ticket_id or len(ticket_id.strip()) < 4:
                    raise ValueError("TICKET_REQUIRED: Rotating an existing key requires a valid change ticket ID.")
                cur.execute("""
                    UPDATE carebridge_internal.auth_secrets
                    SET secret_value = %s, rotated_at = timezone('utc', now())
                    WHERE key_name = 'dba_hmac_key';
                """, (secret_key,))
                print("Rotated dba_hmac_key successfully.")
            else:
                cur.execute("""
                    INSERT INTO carebridge_internal.auth_secrets (key_name, secret_value)
                    VALUES ('dba_hmac_key', %s);
                """, (secret_key,))
                print("Provisioned dba_hmac_key successfully.")

        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision DBA HMAC secrets out-of-band")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL")
    parser.add_argument("--force-rotate-key", action="store_true", help="Rotate existing key")
    parser.add_argument("--ticket-id", type=str, default=None, help="Change ticket ID for rotation")
    args = parser.parse_args()

    db_url = args.db_url
    if not db_url:
        load_dotenv("carebridge/backend/.env")
        db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        print("Error: No DATABASE_URL provided or found in .env")
        sys.exit(1)

    provision_secret(db_url, force_rotate=args.force_rotate_key, ticket_id=args.ticket_id)
