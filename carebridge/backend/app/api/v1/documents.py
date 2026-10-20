from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Response, status, Request
import psycopg2
from psycopg2.extras import Json

from app.core.security import get_security_context, SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.document import (
    ClinicalDocumentResponse,
    ExtractedEntityResponse,
    DocumentVerificationRequest,
    UnreadDocumentCountResponse
)
from app.documents.storage import (
    validate_file_signature,
    save_document_file,
    read_document_file
)
from app.documents.extractor import (
    extract_text,
    extract_clinical_entities
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=ClinicalDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    patient_id: UUID = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    context: SecurityContext = Depends(get_security_context),
):
    if document_type not in ('discharge_summary', 'lab_report', 'prescription', 'referral', 'other'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document_type. Allowed: discharge_summary, lab_report, prescription, referral, other."
        )

    # 1. Read file bytes and validate magic bytes & size
    content = await file.read()
    detected_mime, clean_filename = validate_file_signature(content, file.filename or "document.pdf")
    doc_id = uuid4()

    # 2. Extract text locally
    raw_text, ocr_status, error_code = extract_text(content, detected_mime)

    # 3. Extract structured entities (augmented by Groq for synthetic clinical text)
    extraction_result = await extract_clinical_entities(raw_text, document_type)

    # 4. Save file to storage
    storage_path = save_document_file(
        hospital_id=context.hospital_id,
        patient_id=patient_id,
        doc_id=doc_id,
        filename=clean_filename,
        content=content
    )

    # 5. Persist document & entities in database
    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Check patient access for patient callers
            if context.role == "patient":
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(patient_id)))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not accessible.")

            # Insert clinical_documents record
            cur.execute("""
                INSERT INTO public.clinical_documents (
                    id, hospital_id, patient_id, uploaded_by, document_type,
                    file_name, mime_type, file_size_bytes, storage_path,
                    ocr_status, raw_text, error_code
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                ) RETURNING created_at, updated_at;
            """, (
                str(doc_id), str(context.hospital_id), str(patient_id), str(context.user_id), document_type,
                clean_filename, detected_mime, len(content), storage_path,
                ocr_status, raw_text, error_code
            ))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save document.")
            created_at, updated_at = row

            # Insert extracted entities
            # We map diagnoses, medications, lab results, vitals, allergies
            entities_to_insert = []
            for d in extraction_result.diagnoses:
                entities_to_insert.append(("diagnosis", d.model_dump(), d.confidence))
            for m in extraction_result.medications:
                entities_to_insert.append(("medication", m.model_dump(), m.confidence))
            for l in extraction_result.lab_results:
                entities_to_insert.append(("lab_result", l.model_dump(), l.confidence))
            for v in extraction_result.vital_signs:
                entities_to_insert.append(("vital_sign", v.model_dump(), v.confidence))
            for a in extraction_result.allergies:
                entities_to_insert.append(("allergy", a.model_dump(), a.confidence))

            for category, data, confidence in entities_to_insert:
                cur.execute("""
                    INSERT INTO public.extracted_entities (
                        id, hospital_id, document_id, patient_id,
                        entity_category, extracted_data, confidence_score,
                        verification_status
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s,
                        %s, %s, %s,
                        'pending'
                    );
                """, (
                    str(context.hospital_id), str(doc_id), str(patient_id),
                    category, Json(data), confidence
                ))

    # 6. Audit logging (Zero-PHI)
    audit_event(
        event_type="DOCUMENT_UPLOADED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="clinical_document",
        target_id=str(doc_id),
        action="CREATE",
        status="SUCCESS",
        client_ip=request.client.host if request.client else None,
    )

    return ClinicalDocumentResponse(
        id=doc_id,
        hospital_id=context.hospital_id,
        patient_id=patient_id,
        uploaded_by=context.user_id,
        document_type=document_type,
        file_name=clean_filename,
        mime_type=detected_mime,
        file_size_bytes=len(content),
        storage_path=storage_path,
        ocr_status=ocr_status,
        raw_text=raw_text,
        error_code=error_code,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("", response_model=List[ClinicalDocumentResponse])
def list_documents(
    patient_id: Optional[UUID] = Query(None),
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            if context.role == "patient":
                # Must query only for authorized patients
                cur.execute("""
                    SELECT cd.id, cd.hospital_id, cd.patient_id, cd.uploaded_by,
                           cd.document_type, cd.file_name, cd.mime_type, cd.file_size_bytes,
                           cd.storage_path, cd.ocr_status, cd.raw_text, cd.error_code,
                           cd.created_at, cd.updated_at
                    FROM public.clinical_documents cd
                    JOIN public.patient_accounts pa 
                      ON pa.patient_id = cd.patient_id 
                     AND pa.hospital_id = cd.hospital_id
                    WHERE cd.hospital_id = %s
                      AND pa.user_id = %s
                      AND pa.status = 'verified'
                      AND (%s::uuid IS NULL OR cd.patient_id = %s)
                    ORDER BY cd.created_at DESC;
                """, (str(context.hospital_id), str(context.user_id), str(patient_id) if patient_id else None, str(patient_id) if patient_id else None))
            else:
                cur.execute("""
                    SELECT id, hospital_id, patient_id, uploaded_by,
                           document_type, file_name, mime_type, file_size_bytes,
                           storage_path, ocr_status, raw_text, error_code,
                           created_at, updated_at
                    FROM public.clinical_documents
                    WHERE hospital_id = %s
                      AND (%s::uuid IS NULL OR patient_id = %s)
                    ORDER BY created_at DESC;
                """, (str(context.hospital_id), str(patient_id) if patient_id else None, str(patient_id) if patient_id else None))

            rows = cur.fetchall()
            return [
                ClinicalDocumentResponse(
                    id=r[0],
                    hospital_id=r[1],
                    patient_id=r[2],
                    uploaded_by=r[3],
                    document_type=r[4],
                    file_name=r[5],
                    mime_type=r[6],
                    file_size_bytes=r[7],
                    storage_path=r[8],
                    ocr_status=r[9],
                    raw_text=r[10],
                    error_code=r[11],
                    created_at=r[12],
                    updated_at=r[13],
                )
                for r in rows
            ]


@router.get("/notifications/unread-count", response_model=UnreadDocumentCountResponse)
def get_unread_document_count(
    context: SecurityContext = Depends(get_security_context),
):
    """
    Returns unread/pending document task count for the doctor workstation badge.
    """
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT cd.id)
                FROM public.clinical_documents cd
                JOIN public.extracted_entities ee 
                  ON ee.document_id = cd.id 
                 AND ee.hospital_id = cd.hospital_id
                WHERE cd.hospital_id = %s
                  AND ee.verification_status = 'pending';
            """, (str(context.hospital_id),))
            pending_count = cur.fetchone()[0]

            return UnreadDocumentCountResponse(
                unread_count=pending_count,
                pending_verification_count=pending_count
            )


@router.get("/{document_id}", response_model=ClinicalDocumentResponse)
def get_document(
    document_id: UUID,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, patient_id, uploaded_by,
                       document_type, file_name, mime_type, file_size_bytes,
                       storage_path, ocr_status, raw_text, error_code,
                       created_at, updated_at
                FROM public.clinical_documents
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(document_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            # If patient, verify access to patient
            if context.role == "patient":
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(row[2])))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    audit_event(
        event_type="DOCUMENT_ACCESSED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="clinical_document",
        target_id=str(document_id),
        action="READ",
        status="SUCCESS",
        client_ip=request.client.host if request.client else None,
    )

    return ClinicalDocumentResponse(
        id=row[0],
        hospital_id=row[1],
        patient_id=row[2],
        uploaded_by=row[3],
        document_type=row[4],
        file_name=row[5],
        mime_type=row[6],
        file_size_bytes=row[7],
        storage_path=row[8],
        ocr_status=row[9],
        raw_text=row[10],
        error_code=row[11],
        created_at=row[12],
        updated_at=row[13],
    )


@router.get("/{document_id}/entities", response_model=List[ExtractedEntityResponse])
def get_document_entities(
    document_id: UUID,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Check document exists and caller has access
            cur.execute("""
                SELECT patient_id FROM public.clinical_documents
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(document_id)))
            doc_row = cur.fetchone()
            if not doc_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            if context.role == "patient":
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(doc_row[0])))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            cur.execute("""
                SELECT id, hospital_id, document_id, patient_id,
                       entity_category, extracted_data, confidence_score,
                       verification_status, verified_by, verified_at,
                       doctor_notes, created_at, updated_at
                FROM public.extracted_entities
                WHERE hospital_id = %s AND document_id = %s
                ORDER BY created_at ASC;
            """, (str(context.hospital_id), str(document_id)))
            rows = cur.fetchall()

            return [
                ExtractedEntityResponse(
                    id=r[0],
                    hospital_id=r[1],
                    document_id=r[2],
                    patient_id=r[3],
                    entity_category=r[4],
                    extracted_data=r[5],
                    confidence_score=float(r[6]) if r[6] is not None else None,
                    verification_status=r[7],
                    verified_by=r[8],
                    verified_at=r[9],
                    doctor_notes=r[10],
                    created_at=r[11],
                    updated_at=r[12],
                )
                for r in rows
            ]


@router.post("/{document_id}/verify", response_model=List[ExtractedEntityResponse])
def verify_document_entities(
    document_id: UUID,
    payload: DocumentVerificationRequest,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    """
    Clinician verification endpoint.
    Only authorized doctors or hospital administrators can verify extracted clinical entities.
    Non-clinician roles are strictly rejected (HTTP 403).
    """
    if context.role not in ("doctor", "hospital_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only attending doctors or clinical administrators can verify or edit extracted clinical entities."
        )

    now_utc = datetime.now(timezone.utc)
    updated_entities: List[ExtractedEntityResponse] = []

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Check document exists
            cur.execute("""
                SELECT patient_id FROM public.clinical_documents
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(document_id)))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            for item in payload.entities:
                if item.verification_status == "edited" and item.edited_data:
                    cur.execute("""
                        UPDATE public.extracted_entities
                        SET verification_status = %s,
                            extracted_data = %s,
                            doctor_notes = %s,
                            verified_by = %s,
                            verified_at = %s,
                            updated_at = %s
                        WHERE hospital_id = %s AND document_id = %s AND id = %s;
                    """, (
                        item.verification_status,
                        Json(item.edited_data),
                        item.doctor_notes,
                        str(context.user_id),
                        now_utc,
                        now_utc,
                        str(context.hospital_id),
                        str(document_id),
                        str(item.id)
                    ))
                else:
                    cur.execute("""
                        UPDATE public.extracted_entities
                        SET verification_status = %s,
                            doctor_notes = %s,
                            verified_by = %s,
                            verified_at = %s,
                            updated_at = %s
                        WHERE hospital_id = %s AND document_id = %s AND id = %s;
                    """, (
                        item.verification_status,
                        item.doctor_notes,
                        str(context.user_id),
                        now_utc,
                        now_utc,
                        str(context.hospital_id),
                        str(document_id),
                        str(item.id)
                    ))

            # Fetch updated rows
            cur.execute("""
                SELECT id, hospital_id, document_id, patient_id,
                       entity_category, extracted_data, confidence_score,
                       verification_status, verified_by, verified_at,
                       doctor_notes, created_at, updated_at
                FROM public.extracted_entities
                WHERE hospital_id = %s AND document_id = %s
                ORDER BY created_at ASC;
            """, (str(context.hospital_id), str(document_id)))
            rows = cur.fetchall()
            for r in rows:
                updated_entities.append(ExtractedEntityResponse(
                    id=r[0],
                    hospital_id=r[1],
                    document_id=r[2],
                    patient_id=r[3],
                    entity_category=r[4],
                    extracted_data=r[5],
                    confidence_score=float(r[6]) if r[6] is not None else None,
                    verification_status=r[7],
                    verified_by=r[8],
                    verified_at=r[9],
                    doctor_notes=r[10],
                    created_at=r[11],
                    updated_at=r[12],
                ))

    audit_event(
        event_type="ENTITIES_VERIFIED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="clinical_document",
        target_id=str(document_id),
        action="UPDATE",
        status="SUCCESS",
        client_ip=request.client.host if request.client else None,
    )

    return updated_entities


@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT storage_path, mime_type, file_name, patient_id
                FROM public.clinical_documents
                WHERE hospital_id = %s AND id = %s;
            """, (str(context.hospital_id), str(document_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

            storage_path, mime_type, file_name, patient_id = row

            if context.role == "patient":
                cur.execute("""
                    SELECT 1 FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
                """, (str(context.hospital_id), str(context.user_id), str(patient_id)))
                if not cur.fetchone():
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    file_bytes = read_document_file(storage_path)

    audit_event(
        event_type="DOCUMENT_DOWNLOADED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="clinical_document",
        target_id=str(document_id),
        action="READ",
        status="SUCCESS",
        client_ip=request.client.host if request.client else None,
    )

    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'}
    )
