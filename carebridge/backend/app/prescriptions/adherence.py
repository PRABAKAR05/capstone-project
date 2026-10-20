"""Medication adherence scheduling and compliance calculations for CareBridge AI.

Features:
- Deterministic frequency to daily time-slot mapping.
- Rolling 30-day scheduled doses vs logged doses calculation.
- Adherence rating badge generator.
"""

from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor


FREQUENCY_INTERVALS: Dict[str, List[str]] = {
    "once daily": ["08:00"],
    "qd": ["08:00"],
    "daily": ["08:00"],
    "morning": ["08:00"],
    "twice daily": ["08:00", "20:00"],
    "bid": ["08:00", "20:00"],
    "three times daily": ["08:00", "14:00", "20:00"],
    "tid": ["08:00", "14:00", "20:00"],
    "four times daily": ["08:00", "12:00", "16:00", "20:00"],
    "qid": ["08:00", "12:00", "16:00", "20:00"],
    "every 8 hours": ["06:00", "14:00", "22:00"],
    "every 12 hours": ["08:00", "20:00"],
    "bedtime": ["21:00"],
    "qhs": ["21:00"],
    "as needed": [],
    "prn": [],
}


def get_frequency_times(frequency: str) -> List[str]:
    """Resolves standard daily times for a frequency description."""
    norm = frequency.strip().lower()
    for key, times in FREQUENCY_INTERVALS.items():
        if key in norm or norm in key:
            return times
    # Default fallback: once daily at 08:00
    return ["08:00"]


def calculate_adherence_metrics(
    hospital_id: str,
    patient_id: str,
    db_conn,
    window_days: int = 30
) -> Dict:
    """
    Calculates patient medication adherence over the past `window_days`.
    Only scheduled doses up to current time (T_now) are included in the denominator.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    # 1. Fetch active/recent prescription items for patient
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                pi.id AS item_id,
                pi.drug_name,
                pi.dosage,
                pi.frequency,
                pi.instructions,
                pi.duration_days,
                p.id AS prescription_id,
                p.issued_at,
                p.valid_until,
                p.status AS prescription_status
            FROM public.prescription_items pi
            JOIN public.prescriptions p ON p.id = pi.prescription_id
            WHERE p.hospital_id = %s
              AND p.patient_id = %s
              AND p.status IN ('prescribed', 'ready_for_pickup', 'dispensed', 'completed')
              AND p.issued_at >= %s
            ORDER BY p.issued_at DESC
            """,
            (hospital_id, patient_id, window_start)
        )
        items = cur.fetchall()

        # 2. Fetch all adherence logs for this patient in the window
        cur.execute(
            """
            SELECT 
                id,
                prescription_item_id,
                scheduled_time,
                taken_at,
                status,
                notes
            FROM public.medication_adherence_logs
            WHERE hospital_id = %s
              AND patient_id = %s
              AND scheduled_time >= %s
            ORDER BY scheduled_time ASC
            """,
            (hospital_id, patient_id, window_start)
        )
        logs = cur.fetchall()

    # Index logs by (item_id, scheduled_date_hour)
    log_map: Dict[str, Dict] = {}
    taken_count = 0
    skipped_count = 0

    for l in logs:
        item_id = str(l["prescription_item_id"])
        sched_iso = l["scheduled_time"].isoformat()
        key = f"{item_id}_{sched_iso}"
        log_map[key] = l

        status = l.get("status")
        if status in ("taken", "late"):
            taken_count += 1
        elif status == "skipped":
            skipped_count += 1

    total_scheduled = 0
    today_doses: List[Dict] = []
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(now.date(), time.max).replace(tzinfo=timezone.utc)

    for item in items:
        item_id = str(item["item_id"])
        freq_times = get_frequency_times(item["frequency"])
        if not freq_times:
            continue

        issued_at = item["issued_at"]
        duration_days = min(int(item.get("duration_days", 30)), window_days)

        start_date = max(issued_at.date(), window_start.date())
        end_date = min((issued_at + timedelta(days=duration_days)).date(), now.date())

        # Iterate days
        current_date = start_date
        while current_date <= end_date:
            for time_str in freq_times:
                hh, mm = map(int, time_str.split(":"))
                sched_dt = datetime.combine(current_date, time(hh, mm)).replace(tzinfo=timezone.utc)

                # Only include in denominator if sched_dt <= now
                if sched_dt <= now and sched_dt >= window_start:
                    total_scheduled += 1

                # If scheduled for today, add to today's schedule
                if today_start <= sched_dt <= today_end:
                    key = f"{item_id}_{sched_dt.isoformat()}"
                    log_entry = log_map.get(key)
                    dose_status = log_entry["status"] if log_entry else ("missed" if sched_dt < (now - timedelta(hours=2)) else "pending")
                    
                    today_doses.append({
                        "prescription_item_id": item_id,
                        "prescription_id": str(item["prescription_id"]),
                        "drug_name": item["drug_name"],
                        "dosage": item["dosage"],
                        "instructions": item["instructions"],
                        "scheduled_time": sched_dt.isoformat(),
                        "status": dose_status,
                        "log_id": str(log_entry["id"]) if log_entry else None,
                        "taken_at": log_entry["taken_at"].isoformat() if log_entry and log_entry.get("taken_at") else None,
                    })

            current_date += timedelta(days=1)

    # Sort today's doses by scheduled time
    today_doses.sort(key=lambda x: x["scheduled_time"])

    # Calculate compliance rate
    if total_scheduled == 0:
        adherence_percentage = 100.0
    else:
        adherence_percentage = round((taken_count / total_scheduled) * 100.0, 1)
        adherence_percentage = min(100.0, max(0.0, adherence_percentage))

    missed_count = max(0, total_scheduled - taken_count - skipped_count)

    # Rating badge
    if adherence_percentage >= 90.0:
        badge = "Excellent"
        badge_variant = "success"
    elif adherence_percentage >= 75.0:
        badge = "Good"
        badge_variant = "secondary"
    elif adherence_percentage >= 50.0:
        badge = "Needs Attention"
        badge_variant = "warning"
    else:
        badge = "Critical"
        badge_variant = "destructive"

    return {
        "patient_id": patient_id,
        "evaluation_window_days": window_days,
        "total_scheduled_doses": total_scheduled,
        "taken_count": taken_count,
        "skipped_count": skipped_count,
        "missed_count": missed_count,
        "adherence_percentage": adherence_percentage,
        "rating_badge": badge,
        "rating_variant": badge_variant,
        "today_schedule": today_doses
    }
