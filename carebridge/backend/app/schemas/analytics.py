from typing import Dict, Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class HospitalOperationsOverview(BaseModel):
    hospital_id: UUID
    time_window: str = Field(default="today", description="'today', '7_days', '30_days'")
    opd_volume: int = Field(..., description="Total OPD appointments in window")
    opd_volume_breakdown: Dict[str, int] = Field(default_factory=dict)
    doctor_utilization_pct: float = Field(..., ge=0, le=100)
    active_doctors_count: int
    average_wait_time_minutes: Optional[float] = None
    wait_time_status: str = Field(default="measured", description="'measured' or 'unavailable'")
    care_tasks_backlog_count: int
    pending_claims_count: int
    cache_hit: bool = False
    query_latency_ms: float
    generated_at: str


class DepartmentalLoadMetric(BaseModel):
    department_id: str
    department_name: str
    total_appointments: int
    active_doctors: int
    load_percentage: float
