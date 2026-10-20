"""CSCM-IoMT API Endpoints.

Provides physiology-aware cross-sensor consistency evaluation, live telemetry streaming,
and configurable FDIA attack simulations for connected medical devices.
Strictly restricted to verified clinical and administrative staff ('doctor', 'hospital_admin').
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request

from app.core.security import require_role, SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.core.rate_limit import check_rate_limit, heavy_inference_limiter
from app.schemas.cscm import (
    TelemetryWindowRequest,
    CSCMVerificationResponse,
    AttackSimulationRequest,
    AttackSimulationResponse,
    BenchmarkResponse,
)
from app.cscm.engine import CSCMInferenceEngine
from app.cscm.telemetry import telemetry_service, CHANNELS
from app.cscm.alerting import check_and_trigger_telemetry_care_task

router = APIRouter(prefix="/cscm", tags=["cscm-iomt"])

# In-process singleton engine for PhysioNet graph (seed 42)
_engine = CSCMInferenceEngine(dataset_name="physionet", seed=42, threshold=0.85)


def _verify_patient_in_hospital(cur, patient_id: UUID, hospital_id: UUID):
    """Ensures caller has tenant access to the specified patient."""
    cur.execute(
        "SELECT id FROM public.patients WHERE id = %s AND hospital_id = %s;",
        (str(patient_id), str(hospital_id))
    )
    if not cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found in this hospital tenant."
        )


@router.post("/verify", response_model=CSCMVerificationResponse, status_code=status.HTTP_200_OK)
def verify_telemetry_window(
    payload: TelemetryWindowRequest,
    context: SecurityContext = Depends(require_role(["doctor", "hospital_admin"])),
):
    """Evaluates multi-channel IoMT telemetry consistency using read-only CSCM inference.

    Gated automated Care Task dispatch occurs if anomaly probability >= 0.85 and cooldown allows.
    """
    with get_db(context) as conn:
        with conn.cursor() as cur:
            _verify_patient_in_hospital(cur, payload.patient_id, context.hospital_id)

            # Resolve window matrix (T, C)
            if payload.raw_window is not None:
                window_data = np.array(payload.raw_window, dtype=np.float32)
            elif payload.telemetry_points:
                rows = []
                for pt in payload.telemetry_points:
                    row = [pt.values.get(ch, np.nan) for ch in CHANNELS]
                    rows.append(row)
                window_data = np.array(rows, dtype=np.float32)
            else:
                # Deterministic baseline window for patient
                window_data = telemetry_service.get_baseline_window_for_patient(payload.patient_id)

            # Run in-process CSCM inference
            eval_result = _engine.evaluate_window(window_data)

            # Gated Care Task check
            task_created = False
            care_task_id = None
            if eval_result["is_anomaly"]:
                task_created, care_task_id, reason = check_and_trigger_telemetry_care_task(
                    cur=cur,
                    hospital_id=context.hospital_id,
                    patient_id=payload.patient_id,
                    device_id=payload.device_id,
                    anomaly_probability=eval_result["anomaly_probability"],
                    threshold=eval_result["threshold"],
                    attributions=eval_result["channel_attributions"],
                    actor_id=context.user_id,
                )

            # Zero-PHI audit trail
            audit_event(
                event_type="IOMT_TELEMETRY_VERIFIED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="iomt_device",
                target_id=payload.device_id,
                action="VERIFY",
                status="SUCCESS",
            )

            return CSCMVerificationResponse(
                hospital_id=context.hospital_id,
                patient_id=payload.patient_id,
                device_id=payload.device_id,
                detection_status=eval_result["detection_status"],
                display_message=eval_result["display_message"],
                anomaly_probability=eval_result["anomaly_probability"],
                anomaly_logit=eval_result["anomaly_logit"],
                threshold=eval_result["threshold"],
                is_anomaly=eval_result["is_anomaly"],
                channel_attributions=eval_result["channel_attributions"],
                disclaimer=eval_result["disclaimer"],
                inference_latency_ms=eval_result["inference_latency_ms"],
                model_version=eval_result["model_version"],
                automated_task_created=task_created,
                care_task_id=care_task_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )


@router.get("/stream", status_code=status.HTTP_200_OK)
def get_patient_telemetry_stream(
    patient_id: UUID = Query(...),
    device_id: str = Query("iomt-bedside-node-01"),
    context: SecurityContext = Depends(require_role(["doctor", "hospital_admin"])),
):
    """Retrieves current multi-channel IoMT telemetry stream and real-time consistency status."""
    with get_db(context) as conn:
        with conn.cursor() as cur:
            _verify_patient_in_hospital(cur, patient_id, context.hospital_id)

    window = telemetry_service.get_baseline_window_for_patient(patient_id)
    readings = telemetry_service.format_telemetry_readings(window)
    eval_result = _engine.evaluate_window(window)

    audit_event(
        event_type="IOMT_STREAM_READ",
        actor_id=str(context.user_id),
        actor_role=context.role,
        hospital_id=str(context.hospital_id),
        target_resource="iomt_device",
        target_id=device_id,
        action="READ",
        status="SUCCESS",
    )

    return {
        "patient_id": patient_id,
        "device_id": device_id,
        "readings": readings,
        "verification": eval_result,
    }


@router.post("/simulate-attack", response_model=AttackSimulationResponse, status_code=status.HTTP_200_OK)
def simulate_attack_scenario(
    payload: AttackSimulationRequest,
    request: Request,
    context: SecurityContext = Depends(require_role(["doctor", "hospital_admin"])),
):
    """Simulates coordinated False Data Injection Attack on live IoMT channels to test detection."""
    check_rate_limit(request, heavy_inference_limiter, client_key=str(context.user_id))

    with get_db(context) as conn:
        with conn.cursor() as cur:
            _verify_patient_in_hospital(cur, payload.patient_id, context.hospital_id)

            clean_window = telemetry_service.get_baseline_window_for_patient(payload.patient_id)
            perturbed_window, attacked_channels = telemetry_service.apply_fdia_attack(
                base_window=clean_window,
                attack_type=payload.attack_type,
                target_channels=payload.target_channels,
                intensity=payload.intensity,
            )

            eval_result = _engine.evaluate_window(perturbed_window)

            # Gated Care Task check
            task_created = False
            care_task_id = None
            if eval_result["is_anomaly"]:
                task_created, care_task_id, _ = check_and_trigger_telemetry_care_task(
                    cur=cur,
                    hospital_id=context.hospital_id,
                    patient_id=payload.patient_id,
                    device_id=payload.device_id,
                    anomaly_probability=eval_result["anomaly_probability"],
                    threshold=eval_result["threshold"],
                    attributions=eval_result["channel_attributions"],
                    actor_id=context.user_id,
                )

            clean_readings = telemetry_service.format_telemetry_readings(clean_window)
            perturbed_readings = telemetry_service.format_telemetry_readings(perturbed_window)

            audit_event(
                event_type="IOMT_ATTACK_SIMULATION",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="iomt_device",
                target_id=payload.device_id,
                action="SIMULATE",
                status="SUCCESS",
            )

            verification_response = CSCMVerificationResponse(
                hospital_id=context.hospital_id,
                patient_id=payload.patient_id,
                device_id=payload.device_id,
                detection_status=eval_result["detection_status"],
                display_message=eval_result["display_message"],
                anomaly_probability=eval_result["anomaly_probability"],
                anomaly_logit=eval_result["anomaly_logit"],
                threshold=eval_result["threshold"],
                is_anomaly=eval_result["is_anomaly"],
                channel_attributions=eval_result["channel_attributions"],
                disclaimer=eval_result["disclaimer"],
                inference_latency_ms=eval_result["inference_latency_ms"],
                model_version=eval_result["model_version"],
                automated_task_created=task_created,
                care_task_id=care_task_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            return AttackSimulationResponse(
                simulation_id=f"sim_{uuid4().hex[:10]}",
                attack_type=payload.attack_type,
                attacked_channels=attacked_channels,
                clean_readings=clean_readings,
                perturbed_readings=perturbed_readings,
                verification_result=verification_response,
            )


@router.get("/benchmarks", response_model=BenchmarkResponse, status_code=status.HTTP_200_OK)
def get_cscm_latency_benchmarks(
    context: SecurityContext = Depends(require_role(["doctor", "hospital_admin"])),
):
    """Instruments and reports separate cold-load latency and warm inference latency."""
    bench = _engine.benchmark_inference(num_iterations=25)
    return BenchmarkResponse(**bench)
