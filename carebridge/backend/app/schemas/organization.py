from uuid import UUID
from typing import Optional
from zoneinfo import available_timezones
from pydantic import BaseModel, field_validator

class HospitalResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    license_number: Optional[str] = None
    address: str
    contact_email: str
    contact_phone: str
    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError(f"Invalid IANA timezone identifier: {v}")
        return v

class DepartmentResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    name: str
    code: str
    head_of_department: Optional[str] = None
