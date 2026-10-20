import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to sys.path so we can import models if needed
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

app = FastAPI(
    title="CareBridge AI - CSCM IoMT Service",
    description="Cross-Sensor Consistency Modeling microservice for IoMT anomaly and FDI attack detection",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SensorWindowPayload(BaseModel):
    dataset: str = "physionet"  # 'physionet' or 'wesad'
    channels: List[str]
    readings: List[List[float]]  # shape: [num_channels, time_steps]


class PredictionResult(BaseModel):
    is_anomalous: bool
    anomaly_score: float
    confidence: float
    attack_detected: bool
    channel_inconsistencies: Optional[dict] = None


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "service": "cscm-iomt-service",
        "version": "0.1.0",
        "checkpoints_present": os.path.exists(os.path.join(PROJECT_ROOT, "models")),
    }


@app.post("/predict", response_model=PredictionResult, tags=["inference"])
async def predict_consistency(payload: SensorWindowPayload):
    # Microservice interface ready for model inference in Phase 12
    return PredictionResult(
        is_anomalous=False,
        anomaly_score=0.042,
        confidence=0.958,
        attack_detected=False,
        channel_inconsistencies={},
    )
