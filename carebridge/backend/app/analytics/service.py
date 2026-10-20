import time
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, timezone
from uuid import UUID
from fastapi import HTTPException, status

from app.core.security import SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.analytics import HospitalOperationsOverview, DepartmentalLoadMetric
from app.analytics.cache import analytics_cache


def get_operations_overview(context: SecurityContext, time_window: str = "today") -> HospitalOperationsOverview:
    # AC-11.8: Role-Partitioned Access Barrier - Operational KPIs limited to authorized administrators
    if context.role not in ("hospital_admin", "receptionist"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Operational analytics dashboard is strictly restricted to hospital administrators.",
        )

    hospital_str = str(context.hospital_id)
    cached = analytics_cache.get(hospital_str, time_window, "overview")
    if cached:
        cached_copy = cached.model_copy()
        cached_copy.cache_hit = True
        return cached_copy

    t0 = time.perf_counter()
    now_utc = datetime.now(timezone.utc)

    # Compute window bounds
    if time_window == "7_days":
        start_utc = now_utc - timedelta(days=7)
        num_days = 7
    elif time_window == "30_days":
        start_utc = now_utc - timedelta(days=30)
        num_days = 30
    else:
        # "today"
        today_date = now_utc.date()
        start_utc = datetime.combine(today_date, datetime.min.time(), tzinfo=timezone.utc)
        num_days = 1

    end_utc = now_utc + timedelta(days=1)

    with get_db(context) as conn:
        with conn.cursor() as cur:
            # 1. OPD Volume Breakdown by Status
            cur.execute("""
                SELECT status, count(*)
                FROM public.appointments
                WHERE hospital_id = %s AND scheduled_at >= %s AND scheduled_at < %s
                GROUP BY status;
            """, (hospital_str, start_utc, end_utc))
            status_rows = cur.fetchall()
            status_map: Dict[str, int] = {r[0]: r[1] for r in status_rows}
            total_opd = sum(status_map.values())

            # 2. Active Doctors Count
            cur.execute("""
                SELECT count(*) FROM public.doctors
                WHERE hospital_id = %s AND is_available = true;
            """, (hospital_str,))
            active_docs = cur.fetchone()[0] or 1

            # 3. Doctor Utilization Calculation
            # 16 slots per doctor per day (9:00 - 17:00, 30m slots)
            total_capacity = max(active_docs * 16 * num_days, 1)
            active_bookings = status_map.get("scheduled", 0) + status_map.get("confirmed", 0) + status_map.get("completed", 0)
            utilization_pct = min(100.0, round((active_bookings / total_capacity) * 100.0, 1))

            # 4. Average Wait Time (only where completed visits exist)
            cur.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (updated_at - scheduled_at)) / 60.0)
                FROM public.appointments
                WHERE hospital_id = %s AND status = 'completed' AND updated_at > scheduled_at
                  AND scheduled_at >= %s;
            """, (hospital_str, start_utc))
            avg_wait_row = cur.fetchone()
            if avg_wait_row and avg_wait_row[0] is not None:
                avg_wait_minutes = round(float(avg_wait_row[0]), 1)
                wait_status = "measured"
            else:
                avg_wait_minutes = None
                wait_status = "unavailable"

            # 5. Care Tasks Backlog
            cur.execute("""
                SELECT count(*) FROM public.care_tasks
                WHERE hospital_id = %s AND status = 'pending';
            """, (hospital_str,))
            task_backlog = cur.fetchone()[0] or 0

            # 6. Pending Claims
            cur.execute("""
                SELECT count(*) FROM public.insurance_claims
                WHERE hospital_id = %s AND adjudication_status IN ('draft', 'pre_auth_requested', 'claim_submitted');
            """, (hospital_str,))
            pending_claims = cur.fetchone()[0] or 0

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    result = HospitalOperationsOverview(
        hospital_id=context.hospital_id,
        time_window=time_window,
        opd_volume=total_opd,
        opd_volume_breakdown=status_map,
        doctor_utilization_pct=utilization_pct,
        active_doctors_count=active_docs,
        average_wait_time_minutes=avg_wait_minutes,
        wait_time_status=wait_status,
        care_tasks_backlog_count=task_backlog,
        pending_claims_count=pending_claims,
        cache_hit=False,
        query_latency_ms=elapsed_ms,
        generated_at=now_utc.isoformat(),
    )

    # Save into bounded cache
    analytics_cache.set(hospital_str, time_window, result, "overview")

    audit_event(
        event_type="OPERATIONS_ANALYTICS_VIEWED",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=hospital_str,
        target_resource="analytics_overview",
        target_id=time_window,
        action="READ",
        status="SUCCESS",
    )

    return result


def get_departmental_load(context: SecurityContext) -> List[DepartmentalLoadMetric]:
    if context.role not in ("hospital_admin", "doctor", "receptionist"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Department load metrics are restricted to hospital staff.",
        )

    hospital_str = str(context.hospital_id)
    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dept.id, dept.name,
                       COUNT(a.id) as total_appointments,
                       COUNT(DISTINCT d.id) as total_doctors
                FROM public.departments dept
                LEFT JOIN public.doctors d ON d.department_id = dept.id AND d.is_available = true
                LEFT JOIN public.appointments a ON a.department_id = dept.id
                    AND a.status IN ('scheduled', 'confirmed', 'completed')
                WHERE dept.hospital_id = %s
                GROUP BY dept.id, dept.name
                ORDER BY total_appointments DESC;
            """, (hospital_str,))
            rows = cur.fetchall()

            total_appts_all = sum(r[2] for r in rows) or 1
            metrics = []
            for r in rows:
                dept_appts = r[2]
                load_share = round((dept_appts / total_appts_all) * 100.0, 1)
                metrics.append(
                    DepartmentalLoadMetric(
                        department_id=str(r[0]),
                        department_name=r[1],
                        total_appointments=dept_appts,
                        active_doctors=r[3],
                        load_percentage=load_share,
                    )
                )
            return metrics
