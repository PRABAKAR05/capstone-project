from typing import List, Dict, Any, Optional
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class InsurancePolicyCreate(BaseModel):
    patient_id: UUID
    provider_name: str = Field(..., min_length=2, max_length=150)
    policy_number: str = Field(..., min_length=3, max_length=100)
    policy_holder_name: str = Field(..., min_length=2, max_length=150)
    relation_to_patient: str = Field(default="self", max_length=50)
    sum_insured_inr: float = Field(..., gt=0)
    copay_percentage: float = Field(default=10.0, ge=0, le=100)
    deductible_inr: float = Field(default=0.0, ge=0)
    exclusions: List[str] = Field(default_factory=list)
    valid_from: date
    valid_until: date


class InsurancePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hospital_id: UUID
    patient_id: UUID
    provider_name: str
    policy_number: str
    policy_holder_name: str
    relation_to_patient: str
    sum_insured_inr: float
    remaining_balance_inr: float
    copay_percentage: float
    deductible_inr: float
    exclusions: List[str]
    valid_from: date
    valid_until: date
    status: str
    created_at: datetime
    updated_at: datetime


class PreAuthEstimateRequest(BaseModel):
    policy_id: UUID
    patient_id: UUID
    procedure_name: str = Field(..., min_length=2, max_length=200)
    procedure_category: str = Field(default="general_consultation")
    requested_amount_inr: float = Field(..., gt=0)
    notes: Optional[str] = None


class PreAuthEstimateResponse(BaseModel):
    estimate_status: str = Field(..., description="'estimate_available', 'insufficient_information', 'review_required'")
    rule_version: str = "v1.0"
    policy_id: UUID
    provider_name: str
    policy_number: str
    requested_amount_inr: float
    applicable_limit_inr: float
    deductible_applied_inr: float
    copay_percentage: float
    estimated_insurer_pays_inr: float
    estimated_patient_copay_inr: float
    matched_exclusion: Optional[str] = None
    missing_information: Optional[List[str]] = Field(default_factory=list)
    calculation_breakdown: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "This estimation is an informational aid calculated using synthetic policy guidelines. "
        "It does NOT guarantee coverage or constitute an official insurer adjudication."
    )
    calculated_at: str


class ClaimSubmitRequest(BaseModel):
    policy_id: UUID
    patient_id: UUID
    appointment_id: Optional[UUID] = None
    claim_type: str = Field(default="pre_auth", description="'pre_auth', 'reimbursement', 'cashless_settlement'")
    requested_amount_inr: float = Field(..., gt=0)
    procedure_category: str = Field(default="general_consultation")


class ClaimAdjudicateRequest(BaseModel):
    adjudication_status: str = Field(..., description="'pre_auth_approved', 'pre_auth_denied', 'settled', 'rejected'")
    approved_amount_inr: Optional[float] = Field(default=0.0, ge=0)
    settlement_reference: Optional[str] = None
    denial_reason: Optional[str] = None


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hospital_id: UUID
    policy_id: UUID
    patient_id: UUID
    appointment_id: Optional[UUID] = None
    claim_type: str
    requested_amount_inr: float
    approved_amount_inr: float
    patient_copay_amount_inr: float
    adjudication_status: str
    denial_reason: Optional[str] = None
    settlement_reference: Optional[str] = None
    adjudicated_by: Optional[UUID] = None
    adjudicated_at: Optional[datetime] = None
    rule_version: Optional[str] = "v1.0"
    calculation_breakdown: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
