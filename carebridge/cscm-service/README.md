# CareBridge AI — CSCM-IoMT Inference Microservice

**Real-Time Physiology-Aware Cross-Sensor Consistency Modeling in IoMT**

This microservice provides real-time model inference for evaluating the physiological consistency of IoMT multi-channel time-series data. It bridges the deep-learning research models developed in `src/` with the CareBridge clinical platform.

---

## Architectural Role

In modern hospital Intensive Care Units (ICUs) and ambulatory settings, bedside monitors continuously stream multi-modal vital signs (Heart Rate, Blood Pressure, Respiratory Rate, Oxygen Saturation, Skin Conductance).

The CSCM service:
1. Receives multi-channel sensor windows from bedside IoMT gateways or simulation drivers.
2. Applies the trained Graph Attention Network (GAT) consistency model (`models/`).
3. Computes cross-sensor spatial-temporal divergence against physiological invariant priors.
4. Returns an anomaly probability, binary classification (`baseline_consistent` vs. `inconsistency_detected`), and individual channel attribution scores.

---

## Endpoints

### 1. Health & Status
- **`GET /health`**  
  Returns service status, model checkpoint availability, and environment telemetry.

### 2. Consistency Prediction
- **`POST /predict`**  
  Evaluates a sensor window payload for potential False Data Injection attacks or physiological anomalies.

#### Sample Request:
```json
{
  "dataset": "physionet",
  "channels": ["HR", "RespRate", "NISysABP", "NIDiasABP", "SpO2"],
  "readings": [
    [75.0, 76.0, 74.0, 75.0],
    [16.0, 16.0, 17.0, 16.0],
    [120.0, 118.0, 122.0, 119.0],
    [80.0, 78.0, 81.0, 79.0],
    [98.0, 99.0, 98.0, 98.0]
  ]
}
```

#### Sample Response:
```json
{
  "is_anomalous": false,
  "anomaly_score": 0.042,
  "confidence": 0.958,
  "attack_detected": false,
  "channel_inconsistencies": {}
}
```

---

## Running the Service

```bash
# In carebridge/cscm-service
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```
Interactive Swagger documentation: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
