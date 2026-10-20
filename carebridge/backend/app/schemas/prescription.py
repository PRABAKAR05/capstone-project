from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PrescriptionItemSchema(BaseModel):
    drug_name: str = Field(..., min_length=1)
    therapeutic_class: Optional[str] = None
    dosage: str = Field(..., min_length=1)
    route: str = "oral"
    frequency: str = Field(..., min_length=1)
    duration_days: int = Field(default=30, ge=1)
    instructions: str = "As directed"
    refills_remaining: int = Field(default=0, ge=0)


class PrescriptionCreateRequest(BaseModel):
    patient_id: UUID
    encounter_id: Optional[UUID] = None
    diagnosis_context: Optional[str] = None
    notes: Optional[str] = None
    items: List[PrescriptionItemSchema]


class PrescriptionDispenseRequest(BaseModel):
    status: str = Field(..., description="'ready_for_pickup' or 'dispensed'")
    dispensing_notes: Optional[str] = None


class PrescriptionDiscontinueRequest(BaseModel):
    rationale: str = Field(..., min_length=10, description="Mandatory documented clinical rationale")


class AdherenceLogCreateRequest(BaseModel):
    prescription_item_id: UUID
    scheduled_time: datetime
    status: str = Field(..., description="'taken', 'skipped', 'late', or 'missed'")
    notes: Optional[str] = None
