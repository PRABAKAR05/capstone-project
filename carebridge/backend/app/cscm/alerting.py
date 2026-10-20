"""CSCM Alerting & Care Coordination Integration.

Provides gated Care Task generation for cross-sensor telemetry anomalies.
Enforces confidence threshold gating (>=0.85) and 15-minute per-device alert cooldowns.
"""

import threading
import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict

from app.care_tasks.service import insert_care_task
from app.schemas.cscm import ChannelAttribution

logger = logging.getLogger("carebridge.cscm.alerting")

# Thread-safe cooldown registry: (hospital_id, patient_id, device_id) -> last_alert_time
_cooldown_lock = threading.Lock()
_cooldown_tracker: Dict[Tuple[UUID, UUID, str], datetime] = {}
COOLDOWN_WINDOW_MINUTES = 15


def check_and_trigger_telemetry_care_task(
    cur,
    hospital_id: UUID,
    patient_id: UUID,
    device_id: str,
    anomaly_probability: float,
    threshold: float,
    attributions: List[ChannelAttribution],
    actor_id: Optional[UUID] = None,
) -> Tuple[bool, Optional[UUID], str]:
    """Checks gating criteria and triggers an urgent Care Task if threshold and cooldown allow.

    Returns:
        (task_created: bool, task_id: Optional[UUID], reason: str)
    """
    # 1. Threshold gating (must be >= threshold, default 0.85)
    if anomaly_probability < threshold:
        return False, None, "below_threshold"

    # 2. Cooldown check (minimum 15 minutes between automated alerts for the same device)
    now = datetime.now(timezone.utc)
    key = (hospital_id, patient_id, device_id)

    with _cooldown_lock:
        last_time = _cooldown_tracker.get(key)
        if last_time and (now - last_time) < timedelta(minutes=COOLDOWN_WINDOW_MINUTES):
            remaining = int((timedelta(minutes=COOLDOWN_WINDOW_MINUTES) - (now - last_time)).total_seconds() / 60)
            logger.info(
                "Telemetry anomaly task suppressed for patient %s, device %s: cooldown active (%d min remaining)",
                patient_id, device_id, remaining
            )
            return False, None, f"cooldown_active_{remaining}m_remaining"

        # Update cooldown timestamp
        _cooldown_tracker[key] = now

    # 3. Format grounded task details
    elevated_channels = [
        f"{a.channel_name} (divergence: {a.relative_divergence_pct}%)"
        for a in attributions
        if a.divergence_status == "elevated_graph_divergence"
    ]
    channel_summary = ", ".join(elevated_channels) if elevated_channels else "Multiple cross-sensor relations"

    title = "IoMT Telemetry Advisory: Cross-Sensor Inconsistency Detected"
    description = (
        f"Automated CSCM-IoMT Advisory Trigger: Cross-sensor inconsistency detected on device '{device_id}' "
        f"with anomaly confidence {anomaly_probability * 100:.1f}% (threshold: {threshold * 100:.0f}%). "
        f"Elevated graph relation channels: {channel_summary}. "
        f"Advisory integrity warning only. Does not replace clinical assessment or certified biomedical equipment inspection. "
        f"Mandatory action: Biomedical engineering or clinical staff must inspect sensor leads and verify vital readings."
    )
    patient_instructions = (
        "Your clinical team is reviewing your bedside monitoring telemetry connections. "
        "No action is required from you."
    )

    try:
        task_id = insert_care_task(
            cur=cur,
            hospital_id=hospital_id,
            patient_id=patient_id,
            title=title,
            description=description,
            task_type="other",
            priority="urgent",
            assigned_role="doctor",
            patient_instructions=patient_instructions,
            actor_id=actor_id,
            actor_role="system",
        )
        logger.warning(
            "Created automated Care Task %s for IoMT anomaly on patient %s (device %s)",
            task_id, patient_id, device_id
        )
        return True, task_id, "task_created"
    except Exception as e:
        logger.error("Failed to insert telemetry care task: %s", e)
        return False, None, f"error: {str(e)}"


def reset_alert_cooldowns():
    """Testing helper to clear cooldown tracker."""
    with _cooldown_lock:
        _cooldown_tracker.clear()
