from typing import Dict, Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TelemetryPoint(BaseModel):
    timestamp: str
    values: Dict[str, Optional[float]] = Field(
        ...,
        description="Sensor readings by channel name (e.g. HR, NISysABP, NIDiasABP, NIMAP, Temp)"
    )


class TelemetryWindowRequest(BaseModel):
    patient_id: UUID
    device_id: str = Field(default="iomt-bedside-node-01")
    dataset_name: str = Field(default="physionet")
    telemetry_points: Optional[List[TelemetryPoint]] = None
    raw_window: Optional[List[List[float]]] = None  # (T, C) array


class ChannelAttribution(BaseModel):
    channel_name: str
    divergence_score: float = Field(..., description="L2 magnitude of aggregated relation divergence along physiological edges")
    relative_divergence_pct: float = Field(..., ge=0.0, le=100.0)
    divergence_status: str = Field(default="normal_concordance", description="'normal_concordance' or 'elevated_graph_divergence'")
    clinical_significance: str = Field(
        ...,
        description="Transparent mathematical edge residual description without hardware fault proof"
    )


class CSCMVerificationResponse(BaseModel):
    hospital_id: UUID
    patient_id: UUID
    device_id: str
    detection_status: str = Field(..., description="'baseline_consistent' or 'inconsistency_detected'")
    display_message: str = Field(..., description="Calibrated safe wording")
    anomaly_probability: float = Field(..., ge=0.0, le=1.0)
    anomaly_logit: float
    threshold: float = Field(default=0.85)
    is_anomaly: bool
    channel_attributions: List[ChannelAttribution]
    disclaimer: str = Field(
        default="Advisory integrity warning only. Does not replace clinical assessment or certified biomedical equipment inspection."
    )
    inference_latency_ms: float
    model_version: str = "CSCM-v1.0 (Physiology-Aware Graph)"
    automated_task_created: bool = False
    care_task_id: Optional[UUID] = None
    created_at: str


class AttackSimulationRequest(BaseModel):
    patient_id: UUID
    device_id: str = Field(default="iomt-bedside-node-01")
    attack_type: str = Field(default="coordinated_scaling", description="'coordinated_scaling', 'coordinated_drift', 'single_channel_drift'")
    target_channels: Optional[List[str]] = Field(default=None, description="Channels to perturb. Defaults to physiological pair (NISysABP, NIMAP)")
    intensity: float = Field(default=1.35, description="Perturbation multiplier or drift magnitude")


class AttackSimulationResponse(BaseModel):
    simulation_id: str
    attack_type: str
    attacked_channels: List[str]
    clean_readings: List[Dict[str, Any]]
    perturbed_readings: List[Dict[str, Any]]
    verification_result: CSCMVerificationResponse


class BenchmarkResponse(BaseModel):
    cold_load_latency_ms: float
    mean_inference_latency_ms: float
    p95_inference_latency_ms: float
    total_benchmarked_windows: int
    device_type: str = "CPU"
    weights_only_verified: bool = True
