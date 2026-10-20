# CareBridge AI — Local Development Setup & Deployment Runbook

**Document:** `docs/LOCAL_SETUP.md`  
**Phase:** 14 — Final Capstone Packaging  
**Date:** 2026-10-16  
**Status:** Verified for Python 3.13 & Node.js 18+  
**Author:** Antigravity (Advanced Agentic Pair Programmer)

---

## 1. System Architecture Overview

CareBridge AI operates as a unified healthcare platform with an in-process, decoupled research adapter:

1. **Frontend (`carebridge/frontend`)**: Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui (Port 3000).
2. **Backend (`carebridge/backend`)**: FastAPI (Python 3.13) + SQLAlchemy + Supabase SDK + Groq Llama-3.3-70B (Port 8000).
3. **In-Process CSCM-IoMT Adapter (`carebridge/backend/app/cscm`)**: Zero-cost, in-process PyTorch adapter executing read-only inference on preserved vital sign consistency models without separate microservice overhead.
4. **Database (Supabase PostgreSQL)**: Cloud-hosted PostgreSQL with Row-Level Security (RLS) and multi-tenant partitioning.

---

## 2. Prerequisites & System Requirements

- **Operating System**: Windows 10/11, macOS, or Linux.
- **Node.js**: v18.0.0 or higher (v20+ recommended).
- **Python**: 3.13.x (with `pip` and standard development headers).
- **Git**: 2.30+ for version control.
- **Hardware**: Minimum 8 GB RAM (16 GB recommended for local PyTorch model inference).

---

## 3. Environment Configuration

Copy the template environment configuration:

```powershell
cp carebridge/.env.example carebridge/backend/.env
cp carebridge/.env.example carebridge/frontend/.env.local
```

### Backend Environment Variables (`carebridge/backend/.env`)

```ini
# Supabase PostgreSQL Database Connection (refer to carebridge/.env.example)
DATABASE_URL=your_supabase_postgresql_connection_uri_here
SUPABASE_URL=https://[YOUR_PROJECT_ID].supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
SUPABASE_JWT_SECRET=your-32-byte-secret-key-minimum-256-bits

# Groq Cloud AI Inference (Llama-3.3-70B)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# In-Memory Rate Limiting (Requests per Window)
RATE_LIMIT_BURST_CAP=30
RATE_LIMIT_WINDOW_SECONDS=60

# Telemetry Anomaly Alerting
CSCM_ALERT_THRESHOLD=0.85
CSCM_COOLDOWN_MINUTES=15
```

### Frontend Environment Variables (`carebridge/frontend/.env.local`)

```ini
NEXT_PUBLIC_SUPABASE_URL=https://[YOUR_PROJECT_ID].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## 4. Database Setup & Sequential Migrations

Database tables, Row-Level Security (RLS) policies, and foreign-key constraints are managed in `carebridge/backend/supabase/migrations/`.

Run migrations sequentially in your Supabase SQL Editor or via the Supabase CLI:

```sql
-- 1. Foundation: Multi-tenant schema, hospital organizations, auth triggers & RLS
\i carebridge/backend/supabase/migrations/0001_phase2_schema.sql

-- 2. Scheduling: Hospital timezone support & doctor availability
\i carebridge/backend/supabase/migrations/0002_phase3_hospital_timezone.sql

-- 3. Document Intelligence: Clinical document metadata & extracted entities
\i carebridge/backend/supabase/migrations/0003_phase6_document_intelligence.sql

-- 4. Clinical Conflicts: Cross-document discrepancy records & evidence
\i carebridge/backend/supabase/migrations/0004_phase7_clinical_conflicts.sql

-- 5. Care Tasks: Priority task management & biomedical alert dispatch
\i carebridge/backend/supabase/migrations/0005_phase8_care_tasks.sql

-- 6. E-Prescriptions: Tamper-evident authoring & SHA-256 integrity hashes
\i carebridge/backend/supabase/migrations/0006_phase9_prescriptions.sql

-- 7. Insurance & Analytics: Pre-auth claims, co-pays, and aggregation views
\i carebridge/backend/supabase/migrations/0007_phase11_insurance_analytics.sql

-- 8. Synthetic Seed Data: Populate Hospital 1 & Hospital 2 test records
\i carebridge/backend/supabase/seed.sql
```

---

## 5. Quick Start (Step-by-Step)

### Terminal 1: Backend API Service

```powershell
# Navigate to backend directory
cd carebridge/backend

# Activate Python 3.13 virtual environment (if using venv)
# .\venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
python -m uvicorn main:app --reload --port 8000
```

- **Interactive API Documentation (Swagger)**: `http://localhost:8000/docs`
- **Alternative ReDoc**: `http://localhost:8000/redoc`
- **Health Check Endpoint**: `http://localhost:8000/health`

### Terminal 2: Frontend Web Application

```powershell
# Navigate to frontend directory
cd carebridge/frontend

# Install dependencies
npm install

# Start Next.js development server on port 3000
npm run dev
```

- **Web Application Portal**: `http://localhost:3000`
- **Doctor Workstation**: `http://localhost:3000/doctor`
- **Receptionist Desk**: `http://localhost:3000/receptionist`
- **Admin Dashboard**: `http://localhost:3000/admin`

---

## 6. Running Automated Test Suites

### Running the Full Unified Backend Regression Suite (Phases 2–13)

```powershell
cd carebridge/backend
python -m pytest tests/ -v
```

### Running Specific Test Suites
```powershell
# Security audit & multi-portal E2E tests
python -m pytest tests/test_phase13_security_e2e.py -v

# CSCM-IoMT research integration tests
python -m pytest tests/test_phase12_cscm_integration.py -v

# Clinical conflict detection tests
python -m pytest tests/test_phase7_conflicts.py -v
```

### Building Frontend for Production
```powershell
cd carebridge/frontend
npm run build
```

---

## 7. Troubleshooting & Common Issues

### Issue 1: Database Connection Pool Drops Idle Connections
- **Symptom**: `OperationalError: SSL connection has been closed unexpectedly` during idle test pauses.
- **Root Cause**: Cloud PostgreSQL free pools drop idle sockets without TCP FIN packets.
- **Solution**: Handled automatically in `app/core/database.py` via connection health pings (`SELECT 1;`). Ensure pool recycle is configured:
  ```python
  engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
  ```

### Issue 2: PyTorch Model Loading on CPU
- **Symptom**: `AssertionError: Torch not compiled with CUDA enabled` when loading checkpoints.
- **Solution**: The in-process adapter explicitly maps weights to CPU:
  ```python
  checkpoint = torch.load(model_path, map_location=torch.device("cpu"), weights_only=True)
  ```

### Issue 3: InsecureKeyLengthWarning in PyJWT
- **Symptom**: `InsecureKeyLengthWarning: The HMAC key is 22 bytes long...`
- **Solution**: Update `SUPABASE_JWT_SECRET` in `.env` to a secure 32+ byte string ($\ge 256$ bits of entropy).
