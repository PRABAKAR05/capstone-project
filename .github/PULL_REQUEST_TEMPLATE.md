## Description
Please include a summary of the changes and the related issue/ticket.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Security / Performance enhancement

## Security & Architectural Checklist
- [ ] **Zero PHI:** No Protected Health Information or real patient credentials are logged or hardcoded.
- [ ] **Multi-Tenancy:** Tenant isolation (`hospital_id`) is strictly preserved across all SQL queries and API endpoints.
- [ ] **CSCM Invariant:** No modifications made to protected research assets in `src/`, `models/`, or `data/`.
- [ ] **Database Integrity:** Migrations are paired with down-migrations and adhere to foreign key constraints.

## Verification & Testing
- [ ] `carebridge/backend/tests/`: All tests pass cleanly (`pytest tests/`).
- [ ] `carebridge/frontend`: Lint and production build pass with zero errors (`npm run lint`, `npm run build`).
- [ ] CSCM baseline parity verified (`python verify_phase15_post_audit.py`).
