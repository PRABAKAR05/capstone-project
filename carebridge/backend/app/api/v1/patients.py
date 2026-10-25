import random
from uuid import UUID, uuid4
from typing import List, Union, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from app.core.security import get_security_context, SecurityContext, require_role
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.patient import PatientCreate, PatientResponse, PatientDemographicsOnly

router = APIRouter(prefix="/patients", tags=["patients"])

def generate_mrn() -> str:
    year = datetime.now(timezone.utc).year
    rand_num = random.randint(10000, 99999)
    return f"MRN-{year}-{rand_num}"

@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    request: Request,
    context: SecurityContext = Depends(require_role(["hospital_admin", "doctor"])),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            patient_id = uuid4()
            mrn = generate_mrn()
            cur.execute("""
                INSERT INTO public.patients (
                    id, hospital_id, mrn, first_name, last_name, date_of_birth,
                    gender, blood_group, phone, email, address,
                    emergency_contact_name, emergency_contact_phone
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING created_at, updated_at;
            """, (
                str(patient_id), str(context.hospital_id), mrn,
                payload.first_name, payload.last_name, payload.date_of_birth,
                payload.gender, payload.blood_group, payload.phone,
                payload.email, payload.address,
                payload.emergency_contact_name, payload.emergency_contact_phone
            ))
            row = cur.fetchone()
            created_at, updated_at = row[0], row[1]

            audit_event(
                event_type="PATIENT_RECORD_CREATED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="patient",
                target_id=str(patient_id),
                action="CREATE",
                status="SUCCESS",
                client_ip=request.client.host if request.client else None,
            )

            return PatientResponse(
                id=patient_id,
                hospital_id=context.hospital_id,
                mrn=mrn,
                first_name=payload.first_name,
                last_name=payload.last_name,
                date_of_birth=payload.date_of_birth,
                gender=payload.gender,
                blood_group=payload.blood_group,
                phone=payload.phone,
                email=payload.email,
                address=payload.address,
                emergency_contact_name=payload.emergency_contact_name,
                emergency_contact_phone=payload.emergency_contact_phone,
                created_at=created_at,
                updated_at=updated_at,
            )

@router.get("", response_model=List[Union[PatientResponse, PatientDemographicsOnly]])
def search_patients(
    query: Optional[str] = Query(None, description="Search by MRN, name or phone"),
    context: SecurityContext = Depends(get_security_context),
):
    if context.role == "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients cannot browse patient master list")

    with get_db(context) as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT id, hospital_id, mrn, first_name, last_name, date_of_birth,
                       gender, blood_group, phone, email, address,
                       emergency_contact_name, emergency_contact_phone, created_at, updated_at
                FROM public.patients
                WHERE hospital_id = %s
            """
            params = [str(context.hospital_id)]
            if query:
                sql += " AND (mrn ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s)"
                pattern = f"%{query}%"
                params.extend([pattern, pattern, pattern, pattern])
            sql += " ORDER BY created_at DESC LIMIT 50;"

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

            results = []
            for r in rows:
                if context.role == "lab_technician":
                    masked_first = f"{r[3][0]}***" if r[3] else "—"
                    masked_last = f"{r[4][0]}***" if r[4] else "—"
                    masked_phone = f"*****{r[8][-4:]}" if r[8] and len(r[8]) >= 4 else "*****"
                    results.append(
                        PatientDemographicsOnly(
                            id=r[0], hospital_id=r[1], mrn=r[2], first_name=masked_first,
                            last_name=masked_last, date_of_birth=r[5], gender=r[6],
                            blood_group=r[7], phone=masked_phone,
                            emergency_contact_name="Restricted (Lab Masked)", emergency_contact_phone="Restricted",
                        )
                    )
                else:
                    results.append(
                        PatientResponse(
                            id=r[0], hospital_id=r[1], mrn=r[2], first_name=r[3],
                            last_name=r[4], date_of_birth=r[5], gender=r[6],
                            blood_group=r[7], phone=r[8], email=r[9], address=r[10],
                            emergency_contact_name=r[11], emergency_contact_phone=r[12],
                            created_at=r[13], updated_at=r[14],
                        )
                    )
            return results

@router.get("/me", response_model=PatientResponse)
def get_my_patient_profile(
    context: SecurityContext = Depends(get_security_context),
):
    """
    Returns the authenticated patient's profile record dynamically resolved via patient_accounts.
    """
    if context.role != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated patient accounts may access /patients/me",
        )

    with get_db(None) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.hospital_id, p.mrn, p.first_name, p.last_name, p.date_of_birth,
                       p.gender, p.blood_group, p.phone, p.email, p.address,
                       p.emergency_contact_name, p.emergency_contact_phone, p.created_at, p.updated_at
                FROM public.patient_accounts pa
                JOIN public.patients p ON pa.patient_id = p.id
                WHERE pa.hospital_id = %s AND pa.user_id = %s AND pa.status = 'verified'
                LIMIT 1;
            """, (str(context.hospital_id), str(context.user_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No linked verified patient profile found for this user account.",
                )
            return PatientResponse(
                id=row[0], hospital_id=row[1], mrn=row[2], first_name=row[3],
                last_name=row[4], date_of_birth=row[5], gender=row[6],
                blood_group=row[7], phone=row[8], email=row[9], address=row[10],
                emergency_contact_name=row[11], emergency_contact_phone=row[12],
                created_at=row[13], updated_at=row[14],
            )

@router.get("/{patient_id}", response_model=Union[PatientResponse, PatientDemographicsOnly])
def get_patient_by_id(
    patient_id: UUID,
    request: Request,
    context: SecurityContext = Depends(get_security_context),
):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            # Check tenant and patient access
            cur.execute("""
                SELECT id, hospital_id, mrn, first_name, last_name, date_of_birth,
                       gender, blood_group, phone, email, address,
                       emergency_contact_name, emergency_contact_phone, created_at, updated_at
                FROM public.patients
                WHERE id = %s AND hospital_id = %s;
            """, (str(patient_id), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

            # Patient role verification
            if context.role == "patient":
                cur.execute("""
                    SELECT status FROM public.patient_accounts
                    WHERE hospital_id = %s AND user_id = %s AND patient_id = %s;
                """, (str(context.hospital_id), str(context.user_id), str(patient_id)))
                link = cur.fetchone()
                if not link or link[0] != "verified":
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

            audit_event(
                event_type="PATIENT_RECORD_ACCESSED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="patient",
                target_id=str(patient_id),
                action="READ",
                status="SUCCESS",
                client_ip=request.client.host if request.client else None,
            )

            if context.role == "lab_technician":
                masked_first = f"{row[3][0]}***" if row[3] else "—"
                masked_last = f"{row[4][0]}***" if row[4] else "—"
                masked_phone = f"*****{row[8][-4:]}" if row[8] and len(row[8]) >= 4 else "*****"
                return PatientDemographicsOnly(
                    id=row[0], hospital_id=row[1], mrn=row[2], first_name=masked_first,
                    last_name=masked_last, date_of_birth=row[5], gender=row[6],
                    blood_group=row[7], phone=masked_phone,
                    emergency_contact_name="Restricted (Lab Masked)", emergency_contact_phone="Restricted",
                )
            return PatientResponse(
                id=row[0], hospital_id=row[1], mrn=row[2], first_name=row[3],
                last_name=row[4], date_of_birth=row[5], gender=row[6],
                blood_group=row[7], phone=row[8], email=row[9], address=row[10],
                emergency_contact_name=row[11], emergency_contact_phone=row[12],
                created_at=row[13], updated_at=row[14],
            )
