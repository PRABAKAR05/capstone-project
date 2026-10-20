from uuid import UUID
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

CaregiverRelationship = Literal["self", "parent", "guardian", "caregiver", "spouse"]
CaregiverEvidenceType = Literal[
    "legal_guardianship_order",
    "power_of_attorney",
    "written_patient_consent",
    "birth_certificate_minor"
]
AccountLinkStatus = Literal["pending_verification", "verified", "revoked"]

class CaregiverRequest(BaseModel):
    patient_id: UUID
    relationship: CaregiverRelationship
    evidence_type: CaregiverEvidenceType
    evidence_reference_id: str = Field(..., min_length=3, max_length=100)
    issuing_authority: str = Field(..., min_length=2, max_length=150)
    declaration_signed: bool = True

class CaregiverVerify(BaseModel):
    verification_method: Literal["in_person_inspection", "notarized_consent_verified", "legal_record_lookup"]
    notes: Optional[str] = None

class CaregiverResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    user_id: UUID
    patient_id: UUID
    relationship: str
    status: AccountLinkStatus
    verified_at: Optional[datetime] = None
    verified_by: Optional[UUID] = None
    created_at: datetime
