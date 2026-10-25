from uuid import UUID
from datetime import datetime, date, time, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo, available_timezones
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import get_security_context, SecurityContext
from app.core.database import get_db
from app.schemas.appointment import DoctorSlotsResponse, DoctorSlot

router = APIRouter(prefix="/doctors", tags=["doctors"])

@router.get("", response_model=List[dict])
def list_doctors(
    department_id: Optional[UUID] = None,
    context: SecurityContext = Depends(get_security_context),
):
    # Use unconstrained db connection so patient callers can view the public doctor directory
    with get_db(None) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT d.id, d.hospital_id, d.profile_id, d.department_id, d.license_number,
                       d.specialization, d.qualification, d.opd_room, d.consultation_fee,
                       d.is_available, p.full_name, p.email
                FROM public.doctors d
                JOIN public.profiles p ON d.profile_id = p.id
                WHERE d.hospital_id = %s
            """
            params = [str(context.hospital_id)]
            if department_id:
                query += " AND d.department_id = %s"
                params.append(str(department_id))
            query += " ORDER BY p.full_name;"
            
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "hospital_id": r[1],
                    "profile_id": r[2],
                    "department_id": r[3],
                    "license_number": r[4],
                    "specialization": r[5],
                    "qualification": r[6],
                    "opd_room": r[7],
                    "consultation_fee": float(r[8]),
                    "is_available": r[9],
                    "full_name": r[10],
                    "email": r[11],
                }
                for r in rows
            ]

@router.get("/{doctor_id}/slots", response_model=DoctorSlotsResponse)
def get_doctor_slots(
    doctor_id: UUID,
    slot_date: str = Query(..., description="Target date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    context: SecurityContext = Depends(get_security_context),
):
    # Use unconstrained db connection so patient callers can view schedule slots
    with get_db(None) as conn:
        with conn.cursor() as cur:
            # 1. Fetch doctor & hospital timezone
            cur.execute("""
                SELECT d.id, h.timezone
                FROM public.doctors d
                JOIN public.hospitals h ON d.hospital_id = h.id
                WHERE d.id = %s AND d.hospital_id = %s;
            """, (str(doctor_id), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
            
            hosp_tz_str = row[1] or "Asia/Kolkata"
            if hosp_tz_str not in available_timezones():
                hosp_tz_str = "Asia/Kolkata"
            
            tz = ZoneInfo(hosp_tz_str)
            try:
                target_date = date.fromisoformat(slot_date)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")

            # 2. Fetch booked appointments for this doctor on target date
            cur.execute("""
                SELECT scheduled_at, ends_at
                FROM public.appointments
                WHERE doctor_id = %s AND hospital_id = %s
                  AND status NOT IN ('cancelled', 'no_show')
                  AND scheduled_at >= %s::timestamptz - interval '1 day'
                  AND scheduled_at <= %s::timestamptz + interval '2 days';
            """, (str(doctor_id), str(context.hospital_id), slot_date, slot_date))
            booked_intervals = cur.fetchall()

            # 3. Generate candidate slots (09:00 to 17:00, 30-min intervals)
            slots: List[DoctorSlot] = []
            curr_time = time(9, 0)
            end_operating_time = time(17, 0)
            
            while curr_time < end_operating_time:
                local_dt = datetime.combine(target_date, curr_time, tzinfo=tz)
                # Check for spring-forward gap (nonexistent time)
                # In Python zoneinfo, nonexistent times raise or adjust when converting
                try:
                    utc_start = local_dt.astimezone(dt_tz.utc)
                    utc_end = (local_dt + timedelta(minutes=30)).astimezone(dt_tz.utc)
                except Exception:
                    # Nonexistent spring gap: skip
                    curr_time = (datetime.combine(target_date, curr_time) + timedelta(minutes=30)).time()
                    continue

                # Check if booked
                is_available = True
                for b_start, b_end in booked_intervals:
                    # Overlap condition: not (utc_end <= b_start or utc_start >= b_end)
                    if not (utc_end <= b_start or utc_start >= b_end):
                        is_available = False
                        break

                slots.append(
                    DoctorSlot(
                        start_time=utc_start.isoformat(),
                        end_time=utc_end.isoformat(),
                        local_start_time=curr_time.strftime("%H:%M"),
                        is_available=is_available,
                    )
                )

                curr_time = (datetime.combine(target_date, curr_time) + timedelta(minutes=30)).time()

            return DoctorSlotsResponse(
                hospital_timezone=hosp_tz_str,
                date=slot_date,
                slots=slots,
            )
