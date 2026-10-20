from uuid import UUID
from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr

class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: Literal["male", "female", "other"]
    blood_group: Optional[Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]] = None
    phone: str = Field(..., min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

class PatientResponse(BaseModel):
    id: UUID
    hospital_id: UUID
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str] = None
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class PatientDemographicsOnly(BaseModel):
    id: UUID
    hospital_id: UUID
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    blood_group: Optional[str] = None
    phone: str
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
