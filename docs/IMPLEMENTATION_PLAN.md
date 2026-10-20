# CareBridge AI — Phase 0 Implementation Plan
**Date:** 2026-10-14  
**Status:** PROPOSED — Awaiting Owner Approval

---

## Recommended Implementation Phases

| Phase | Title | Priority | Depends On |
|-------|-------|----------|-----------|
| 0 | Repository Audit | ✅ In Progress | — |
| 1 | Foundation (monorepo, tooling, env) | 🔴 Critical | Phase 0 |
| 2 | Supabase Schema + Auth + RLS | 🔴 Critical | Phase 1 |
| 3 | Core Hospital Workflows (patients, doctors, appointments) | 🔴 Critical | Phase 2 |
| 4 | Premium UI & Design System | 🟠 High | Phase 3 |
| 5 | Groq Integration + AI Orchestration Layer | 🟠 High | Phase 2 |
| 6 | Document Intelligence (OCR, extraction) | 🟠 High | Phase 2, 5 |
| 7 | Document Conflict Checker | 🟠 High | Phase 6 |
| 8 | Care Coordination Tasks | 🟡 Medium | Phase 3, 5 |
| 9 | Prescription Intelligence | 🟡 Medium | Phase 6 |
| 10 | Patient Conversational Assistant + Voice | 🟡 Medium | Phase 5, 3 |
| 11 | Insurance Module + Analytics Dashboard | 🟡 Medium | Phase 3 |
| 12 | CSCM Service Integration | 🟡 Medium | Phase 2 |
| 13 | Security Hardening + Testing | 🔴 Critical | All phases |
| 14 | Release Assessment | 🟠 High | Phase 13 |

---

## Proposed Phase 1: Foundation

### What it covers
1. Create monorepo structure: `carebridge/` directory with `frontend/`, `backend/`, `cscm-service/`
2. Initialize Next.js + TypeScript + Tailwind CSS + shadcn/ui frontend
3. Initialize FastAPI Python backend skeleton
4. Set up `.env.example` with all required variables (no secret values)
5. Restore `scripts/run_all_evals.py` to its original state
6. Commit current working state to git
7. Verify local development startup works

### What it explicitly excludes
- Database schema (Phase 2)
- Auth (Phase 2)
- Any AI integration (Phase 5+)
- Any business logic (Phase 3+)

---

## Questions Requiring Your Decision Before Phase 1

1. **Repository structure:** Should CareBridge AI live inside the existing `capstone_PRABAKAR` folder as a subdirectory (e.g., `carebridge/`), or should it be a **separate new repository**?

2. **Node.js environment:** Is Node.js already installed on your machine? (Run `node --version` to check.)

3. **Supabase project:** Do you already have a Supabase project created, or should I guide you to create one during Phase 1?

4. **Groq API key:** Do you have a Groq API key ready? (It will be stored only in a local `.env` file, never committed.)

5. **Hospital name for seed data:** What is the name of the hospital you want to use for synthetic demonstration data?
