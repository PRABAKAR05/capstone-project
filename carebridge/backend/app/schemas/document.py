from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

DocumentType = Literal["discharge_summary", "lab_report", "prescription", "referral", "other"]
OCRStatus = Literal["pending", "processing", "completed", "failed"]
EntityCategory = Literal["diagnosis", "medication", "lab_result", "vital_sign", "allergy", "metadata"]
VerificationStatus = Literal["pending", "verified", "rejected", "edited"]

# --- Structured Clinical Extraction Models ---
class DiagnosisItem(BaseModel):
    condition: str
    icd_code: Optional[str] = None
    status: Optional[str] = "active"
    page: Optional[int] = 1
    confidence: Optional[float] = 0.95

class MedicationItem(BaseModel):
    drug_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = "oral"
    duration: Optional[str] = None
    page: Optional[int] = 1
    confidence: Optional[float] = 0.95

class LabResultItem(BaseModel):
    test_name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    abnormal_flag: Optional[bool] = False
    page: Optional[int] = 1
    confidence: Optional[float] = 0.95

class VitalSignItem(BaseModel):
    vital_name: str
    value: str
    unit: Optional[str] = None
    page: Optional[int] = 1
    confidence: Optional[float] = 0.95

class AllergyItem(BaseModel):
    allergen: str
    reaction: Optional[str] = None
    severity: Optional[str] = "mild"
    page: Optional[int] = 1
    confidence: Optional[float] = 0.95

class ClinicalExtractionResult(BaseModel):
    facility_name: Optional[str] = None
    report_date: Optional[str] = None
    provider_name: Optional[str] = None
    document_summary: Optional[str] = None
    diagnoses: List[DiagnosisItem] = Field(default_factory=list)
    medications: List[MedicationItem] = Field(default_factory=list)
    lab_results: List[LabResultItem] = Field(default_factory=list)
    vital_signs: List[VitalSignItem] = Field(default_factory=list)
    allergies: List[AllergyItem] = Field(default_factory=list)

# --- Document API Request & Response Schemas ---
class ClinicalDocumentResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    uploaded_by: UUID
    document_type: DocumentType
    file_name: str
    mime_type: str
    file_size_bytes: int
    storage_path: str
    ocr_status: OCRStatus
    raw_text: Optional[str] = None
    error_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ExtractedEntityResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    document_id: UUID
    patient_id: UUID
    entity_category: EntityCategory
    extracted_data: Dict[str, Any]
    confidence_score: Optional[float] = None
    verification_status: VerificationStatus
    verified_by: Optional[UUID] = None
    verified_at: Optional[datetime] = None
    doctor_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class EntityVerifyItem(BaseModel):
    id: UUID
    verification_status: Literal["verified", "rejected", "edited"]
    edited_data: Optional[Dict[str, Any]] = None
    doctor_notes: Optional[str] = None

class DocumentVerificationRequest(BaseModel):
    entities: List[EntityVerifyItem]

class UnreadDocumentCountResponse(BaseModel):
    unread_count: int
    pending_verification_count: int
