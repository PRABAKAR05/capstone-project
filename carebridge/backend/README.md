# CareBridge AI — Clinical Backend & Security Gateway

**High-Performance FastAPI Medical Gateway with Zero-PHI Audit Trails & Multi-Tenancy**

The CareBridge backend serves as the core orchestration and security gateway for the CareBridge AI clinical platform, powered by **FastAPI 0.12.0** and **Python 3.13.2**.

---

## Architectural Principles

1. **Strict Multi-Tenant Isolation:** Enforces hospital-level scoping across all endpoints and database queries. A user in Hospital A cannot access or mutate records in Hospital B.
2. **Zero-PHI Structured Audit Trail:** All authentication events, security checks, state transitions, and sensitive queries generate structured records in `logs/audit.jsonl` without leaking Protected Health Information (PHI).
3. **Cryptographic Integrity:** End-to-end digital signatures on e-prescriptions (HMAC-SHA256) and administrative database corrections.
4. **RFC 7807 Error Compliance:** API error responses adhere to standard Problem Details formatting (`detail`, `title`, `status`, `invalid_params`).

---

## Directory Structure

```
backend/
├── app/
│   ├── api/                    # Route handlers grouped by clinical domain
│   │   ├── auth.py             # Dual-mode authentication & token issuance
│   │   ├── patients.py         # Patient registration & demographics
│   │   ├── appointments.py     # Scheduling & status state machines
│   │   ├── prescriptions.py    # e-Prescribing & tamper-evident verification
│   │   ├── conflicts.py        # Clinical conflict review & override rationale
│   │   ├── care_tasks.py       # Interdisciplinary task queue & claiming
│   │   ├── documents.py        # Medical record upload & entity extraction
│   │   ├── cscm.py             # Edge IoMT proxy & attack simulation
│   │   └── admin.py            # Analytics, audit log query, tenant metrics
│   ├── core/                   # Security middleware, JWT validation, config
│   │   ├── config.py           # Pydantic v2 application settings
│   │   ├── security.py         # Cryptographic token decoding & role extraction
│   │   ├── audit.py            # Zero-PHI audit logger singleton
│   │   └── database.py         # Supabase PostgreSQL client connection pool
│   ├── models/                 # Database ORM and relational models
│   ├── schemas/                # Pydantic v2 validation schemas
│   └── services/               # Core business logic & clinical algorithms
├── logs/
│   └── audit.jsonl             # Immutable structured security audit log
├── supabase/                   # Supabase migrations, RLS policies, seed scripts
├── tests/                      # Comprehensive integration test suite (128 tests)
├── uploads/                    # Local staging for uploaded medical documents
├── .env                        # Local environment configuration (git-ignored)
├── main.py                     # Application entry point & router mounting
└── requirements.txt            # Python dependencies
```

---

## API Endpoints Reference

### Authentication & Identity
- `POST /api/v1/auth/login` — Native API login for all 5 personas; returns signed JWT.
- `GET /api/v1/auth/me` — Returns current authenticated user profile, role, and hospital tenant.

### Clinical Care & Workflows
- `GET /patients` — Query patient roster (masked for lab technicians).
- `POST /patients` — Register new patient under current hospital tenant.
- `GET /appointments` — List hospital appointments with status filtering.
- `POST /appointments` — Create appointment with doctor slot validation.
- `POST /appointments/{id}/cancel` — Cancel appointment with state machine protection.

### e-Prescribing & Pharmacovigilance
- `GET /prescriptions` — List hospital prescriptions.
- `POST /prescriptions` — Create e-prescription with pre-issuance conflict checks & digital signature.
- `GET /verify-prescription/{hash}` — Public zero-PII cryptographic verification endpoint.
- `POST /prescriptions/{id}/dispense` — Transition prescription to dispensed (Pharmacy role).

### Clinical Conflicts & Safety
- `GET /conflicts` — List detected drug-allergy and duplicate therapy conflicts.
- `POST /conflicts/{id}/acknowledge` — Clinician override requiring mandatory rationale.

### Care Tasks & Nursing
- `GET /care-tasks` — Task board for doctors and nurses.
- `POST /care-tasks/{id}/claim` — Claim care task for active practitioner.
- `POST /care-tasks/{id}/complete` — Complete task with mandatory resolution notes.

### IoMT Edge Integration
- `GET /api/v1/cscm/stream` — Bedside multi-channel physiological data stream.
- `POST /api/v1/cscm/simulate-attack` — Trigger synthetic False Data Injection (FDI) attack for demo & testing.

---

## Local Development & Setup

### 1. Environment Setup
```bash
python -m venv .venv
# Activate environment
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate    # Linux / macOS

pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```ini
ENVIRONMENT=development
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:3000

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-publishable-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
DATABASE_URL=your_supabase_postgresql_connection_uri_here

GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
CSCM_SERVICE_URL=http://127.0.0.1:8001
```

### 3. Run the Server
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
Alternative ReDoc UI: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Test Suite Execution

The backend contains **128 automated end-to-end integration and security tests**:

```bash
# Set PYTHONPATH and execute pytest
pytest tests/ -v
```

All 128 tests pass cleanly, covering:
- Cryptographic JWT validation & tampering detection
- Hospital tenant isolation barriers
- Role-based access control (RBAC) enforcement
- Non-repudiation of e-prescription signatures
- Zero-PHI compliance in audit logs
- IoMT telemetry stream integration
