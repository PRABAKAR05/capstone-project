import os
import json
import hmac
import hashlib
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional

AUDIT_SALT = os.getenv("AUDIT_SALT", "carebridge-secure-audit-salt-2026")
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
AUDIT_LOG_FILE = os.path.join(LOG_DIR, "audit.jsonl")

# Setup logger
audit_logger = logging.getLogger("carebridge.audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False

if not audit_logger.handlers:
    # 100 MB per file, up to 10 backup archives
    handler = RotatingFileHandler(
        AUDIT_LOG_FILE,
        maxBytes=100 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    audit_logger.addHandler(handler)
    
    # Try setting secure file permissions (POSIX 0600)
    try:
        os.chmod(AUDIT_LOG_FILE, 0o600)
    except Exception:
        pass

def mask_ip(ip_address: Optional[str]) -> str:
    if not ip_address:
        return "unknown"
    if "." in ip_address:
        # IPv4: mask to /24
        parts = ip_address.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
    elif ":" in ip_address:
        # IPv6: mask prefix
        parts = ip_address.split(":")
        return f"{parts[0]}:{parts[1]}:xxxx:xxxx"
    return "masked"

def pseudonymize_id(entity_id: Optional[str]) -> Optional[str]:
    if not entity_id:
        return None
    h = hmac.new(AUDIT_SALT.encode("utf-8"), str(entity_id).encode("utf-8"), hashlib.sha256)
    return h.hexdigest()[:16]

def audit_event(
    event_type: str,
    actor_id: str,
    actor_role: str,
    hospital_id: str,
    target_resource: str,
    target_id: Optional[str] = None,
    action: str = "READ",
    status: str = "SUCCESS",
    client_ip: Optional[str] = None,
):
    """
    Emits a structured zero-PHI audit record.
    Never logs patient names, health descriptions, symptoms, or credentials.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor_id": str(actor_id),
        "actor_role": str(actor_role),
        "hospital_id": str(hospital_id),
        "target_resource": target_resource,
        "target_pseudonym": pseudonymize_id(target_id) if target_id else None,
        "action": action,
        "status": status,
        "client_ip_masked": mask_ip(client_ip),
    }
    audit_logger.info(json.dumps(record))
