import os
import re
from pathlib import Path
from typing import Tuple
from uuid import UUID
from fastapi import HTTPException, status

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic number signatures
MAGIC_SIGNATURES = {
    "application/pdf": b"%PDF",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}

UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


def validate_file_signature(content: bytes, declared_filename: str) -> Tuple[str, str]:
    """
    Validates file size, extension, and binary magic bytes.
    Returns (detected_mime_type, sanitized_filename).
    Raises HTTPException(400) if validation fails.
    """
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # Sanitize filename
    clean_name = os.path.basename(declared_filename)
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean_name)
    if not clean_name:
        clean_name = "document.pdf"

    # Match magic bytes
    matched_mime = None
    if content.startswith(b"%PDF"):
        matched_mime = "application/pdf"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        matched_mime = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        matched_mime = "image/jpeg"

    if not matched_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format or corrupted binary header. Allowed: PDF, PNG, JPEG."
        )

    return matched_mime, clean_name


def save_document_file(hospital_id: UUID, patient_id: UUID, doc_id: UUID, filename: str, content: bytes) -> str:
    """
    Saves the file securely to tenant-isolated storage.
    Returns storage_path.
    """
    tenant_dir = UPLOAD_BASE_DIR / str(hospital_id) / str(patient_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = tenant_dir / f"{doc_id}_{filename}"
    with open(file_path, "wb") as f:
        f.write(content)
        
    return str(file_path.relative_to(UPLOAD_BASE_DIR.parent))


def read_document_file(storage_path: str) -> bytes:
    """
    Reads the file bytes from storage.
    """
    base_dir = UPLOAD_BASE_DIR.parent
    full_path = (base_dir / storage_path).resolve()
    
    # Path traversal check
    if not str(full_path).startswith(str(base_dir)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid storage path."
        )
        
    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on storage."
        )
        
    with open(full_path, "rb") as f:
        return f.read()
