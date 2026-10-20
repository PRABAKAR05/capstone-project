"""Cryptographic signing and verification for CareBridge digital prescriptions.

Generates tamper-evident HMAC-SHA256 signatures with key ID versioning (v1).
Supports QR payload verification and zero-PII validation.
"""

import hashlib
import hmac
import json
from typing import Dict, List, Optional
from app.core.config import settings


KEY_VERSION = "v1"


def compute_items_hash(items: List[Dict]) -> str:
    """
    Computes a deterministic SHA-256 hash of prescription items.
    Items are sorted by normalized drug name, dosage, and frequency.
    """
    normalized_items = []
    for item in items:
        normalized_items.append({
            "drug_name": str(item.get("drug_name", "")).strip().lower(),
            "dosage": str(item.get("dosage", "")).strip().lower(),
            "frequency": str(item.get("frequency", "")).strip().lower(),
            "route": str(item.get("route", "oral")).strip().lower(),
            "duration_days": int(item.get("duration_days", 0)),
        })
    normalized_items.sort(key=lambda x: (x["drug_name"], x["dosage"], x["frequency"]))
    canonical = json.dumps(normalized_items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_verification_hash(
    prescription_id: str,
    hospital_id: str,
    patient_id: str,
    doctor_id: str,
    issued_at: str,
    items_hash: str,
    secret_key: Optional[str] = None
) -> str:
    """
    Generates a versioned HMAC-SHA256 signature for a canonical prescription payload.
    Format: "v1:<hex_hmac>"
    """
    secret = secret_key or settings.PRESCRIPTION_SIGNING_SECRET
    payload = {
        "doctor_id": str(doctor_id),
        "hospital_id": str(hospital_id),
        "issued_at": str(issued_at),
        "items_hash": str(items_hash),
        "patient_id": str(patient_id),
        "prescription_id": str(prescription_id),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{KEY_VERSION}:{digest}"


def verify_signature(
    prescription_id: str,
    hospital_id: str,
    patient_id: str,
    doctor_id: str,
    issued_at: str,
    items_hash: str,
    verification_hash: str,
    secret_key: Optional[str] = None
) -> bool:
    """
    Verifies that the verification_hash matches the canonical payload.
    Checks key version and performs constant-time comparison.
    """
    if not verification_hash or not verification_hash.startswith(f"{KEY_VERSION}:"):
        return False

    expected_hash = generate_verification_hash(
        prescription_id=prescription_id,
        hospital_id=hospital_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
        issued_at=issued_at,
        items_hash=items_hash,
        secret_key=secret_key
    )
    return hmac.compare_digest(expected_hash, verification_hash)
