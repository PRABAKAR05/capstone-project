# Contributing to CareBridge AI

Thank you for your interest in contributing to **CareBridge AI**! We welcome contributions from software engineers, clinical informaticists, security researchers, and data scientists.

---

## Code of Conduct & Core Invariants

CareBridge AI handles healthcare operations and IoMT cybersecurity. To ensure safety, reliability, and academic rigor, all contributors must adhere to these non-negotiable rules:

1. **Zero-PHI Policy:** Never commit real patient identifiers, medical records, or live institutional keys. All test fixtures must use synthetic data.
2. **CSCM-IoMT Research Invariant:** The foundational research assets located in `src/`, `models/`, `data/`, and `configs/` represent published academic benchmarks. They are strictly read-only and immutable.
3. **Multi-Tenant Boundaries:** All database queries and API endpoints must enforce hospital scoping (`hospital_id`).
4. **Deterministic Testing:** All pull requests must pass the automated test suites (`pytest` and `npm run lint` / `npm run build`) before being merged.

---

## Development Workflow

### 1. Branching Model
- `main` / `master`: Production-ready, fully verified releases.
- `develop`: Ongoing feature integration.
- `feature/<name>`: New feature implementations.
- `fix/<name>`: Bug fixes and security patches.

### 2. Setting Up Your Environment
Follow the instructions in [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md) to set up your local Python 3.13 and Node.js 20 environments.

### 3. Code Standards
- **Python (Backend):**
  - Follow PEP 8 style guidelines.
  - Use type hints for all function arguments and returns.
  - Format with Black / Flake8 standards.
- **TypeScript / React (Frontend):**
  - Follow Next.js App Router idioms.
  - Strict TypeScript mode enabled — avoid `any` types.
  - Run `npm run lint` to ensure zero ESLint errors.
- **SQL / Supabase:**
  - Every schema addition must include both an up migration (`000X_*_schema.sql`) and down migration (`000X_*_down.sql`).
  - Tables must have Row Level Security enabled.

---

## Testing Requirements

Before opening a pull request, run all test suites locally:

```bash
# 1. Run CareBridge Backend Tests
$env:PYTHONPATH="carebridge/backend"
pytest carebridge/backend/tests/ -v

# 2. Run CSCM Research Tests
pytest tests/ -v

# 3. Validate Frontend Build & Lint
cd carebridge/frontend
npm run lint
npm run build

# 4. Verify Post-Audit Integrity Gate
python verify_phase15_post_audit.py
```

---

## Submitting Pull Requests

1. Fork the repository and create your branch from `develop`.
2. Commit your changes with descriptive, conventional commit messages (e.g. `feat(prescriptions): add tamper detection check`).
3. Ensure all tests and lint checks pass.
4. Submit a Pull Request targeting `develop`, filling out the provided PR template.
