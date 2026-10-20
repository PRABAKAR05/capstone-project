from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_security_context, SecurityContext
from app.core.database import get_db
from app.schemas.organization import HospitalResponse, DepartmentResponse

router = APIRouter(prefix="", tags=["organization"])

@router.get("/hospitals/me", response_model=HospitalResponse)
def get_current_hospital(context: SecurityContext = Depends(get_security_context)):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, slug, license_number, address, contact_email, contact_phone, timezone
                FROM public.hospitals
                WHERE id = %s AND is_active = true;
            """, (str(context.hospital_id),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
            return HospitalResponse(
                id=row[0],
                name=row[1],
                slug=row[2],
                license_number=row[3],
                address=row[4],
                contact_email=row[5],
                contact_phone=row[6],
                timezone=row[7],
            )

@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(context: SecurityContext = Depends(get_security_context)):
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, name, code, head_of_department
                FROM public.departments
                WHERE hospital_id = %s
                ORDER BY name;
            """, (str(context.hospital_id),))
            rows = cur.fetchall()
            return [
                DepartmentResponse(
                    id=r[0],
                    hospital_id=r[1],
                    name=r[2],
                    code=r[3],
                    head_of_department=r[4],
                )
                for r in rows
            ]
