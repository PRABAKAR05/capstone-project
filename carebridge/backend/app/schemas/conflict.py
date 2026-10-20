from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

ConflictType = Literal[
    "drug_allergy",
    "duplicate_therapy",
    "drug_drug_interaction",
    "diagnostic_discrepancy",
    "temporal_inconsistency",
    "other",
]

ReviewPriority = Literal["high", "moderate", "low"]
ResolutionStatus = Literal["unresolved", "acknowledged_with_rationale", "resolved_via_order_change"]

RoleInConflict = Literal[
    "prescribed_medication",
    "documented_allergy",
    "interacting_medication",
    "conflicting_diagnosis",
    "baseline_evidence",
]


class ClinicalConflictSourceBase(BaseModel):
    role_in_conflict: RoleInConflict
    citation_text: str
    document_id: Optional[UUID] = None
    entity_id: Optional[UUID] = None


class ClinicalConflictSourceResponse(ClinicalConflictSourceBase):
    id: UUID
    hospital_id: UUID
    conflict_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ClinicalConflictResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    conflict_type: ConflictType
    review_priority: ReviewPriority
    title: str
    clinical_summary: Optional[str] = None  # None for patient/caregiver views
    patient_friendly_summary: str
    resolution_status: ResolutionStatus
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    clinician_rationale: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sources: Optional[List[ClinicalConflictSourceResponse]] = None

    class Config:
        from_attributes = True


class AcknowledgeConflictRequest(BaseModel):
    rationale: str = Field(
        ...,
        min_length=10,
        description="Mandatory clinical rationale explaining medical decision context",
    )


class ConflictScanResponse(BaseModel):
    patient_id: UUID
    scanned_documents_count: int
    scanned_entities_count: int
    conflicts_detected: int
    conflicts: List[ClinicalConflictResponse]


class ConflictNotificationCountResponse(BaseModel):
    high_priority_count: int
    moderate_priority_count: int
    total_unresolved: int
