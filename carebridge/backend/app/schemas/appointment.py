from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

AppointmentStatus = Literal["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]

class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    department_id: UUID
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=10, le=240)
    reason_for_visit: Optional[str] = None

class AppointmentReschedule(BaseModel):
    new_scheduled_at: datetime
    override_reason: Optional[str] = None

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    clinical_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    doctor_id: UUID
    department_id: UUID
    scheduled_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    reason_for_visit: Optional[str] = None
    clinical_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class DoctorSlot(BaseModel):
    start_time: str
    end_time: str
    local_start_time: str
    is_available: bool

class DoctorSlotsResponse(BaseModel):
    hospital_timezone: str
    date: str
    slots: List[DoctorSlot]
