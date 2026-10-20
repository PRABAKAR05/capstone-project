# Phase 1 Implementation Plan
**Phase:** 1 — Foundation  
**Status:** PROPOSED — Awaiting Owner Approval  
**Date Proposed:** 2026-10-14

---

## 1. Phase Number and Title
Phase 1 — Foundation (Monorepo Setup, Tooling, Local Dev Environment)

## 2. Business Objective
Establish a stable, runnable local development foundation for CareBridge AI before any features are built. Without this phase, no subsequent phase can be implemented safely.

## 3. Why This Phase is Necessary
The repository currently contains only the CSCM research pipeline. There is no web application, no backend API, no database connection, and no environment configuration. Phase 1 creates the scaffolding on which all future phases depend.

## 4. Existing Features and Files Relevant to This Phase
- `src/` — CSCM research code (must be preserved exactly)
- `models/` — trained checkpoints (must be preserved exactly)
- `scripts/run_all_evals.py` — modified during live demo (must be restored)
- `22MIS0527_Review-1.docx`, `22MIS0527_Review-2.pdf` — user documents (must be preserved)

## 5. Current Implementation Status
- CareBridge AI web platform: ❌ Does not exist
- Research pipeline (CSCM): ✅ Fully implemented and verified

## 6. Exact Scope of Work

### 6.1 Restore modified files
- Restore `scripts/run_all_evals.py` to its original subprocess-based implementation

### 6.2 Create monorepo directory structure
```
carebridge/
├── frontend/          # Next.js application
├── backend/           # FastAPI application  
└── cscm-service/      # Thin wrapper exposing CSCM inference via API
```

### 6.3 Initialize Next.js frontend
- Next.js 14+ with App Router
- TypeScript
- Tailwind CSS
- shadcn/ui component library
- Motion for React (framer-motion)
- ESLint + Prettier configured

### 6.4 Initialize FastAPI backend
- Python virtual environment inside `carebridge/backend/`
- FastAPI skeleton with health check endpoint (`GET /health`)
- CORS configured for localhost frontend
- Uvicorn for local development
- Structured logging

### 6.5 Environment configuration
- `.env.example` with all required variable names (no values)
- `.gitignore` updated to exclude `.env` files from all locations
- `LOCAL_SETUP.md` with step-by-step startup instructions

### 6.6 CSCM service skeleton
- Minimal FastAPI app in `carebridge/cscm-service/`
- Single health check endpoint
- Documents how it will eventually wrap the existing CSCM inference

### 6.7 Verify local development startup
- Frontend: `npm run dev` starts on port 3000 without errors
- Backend: `uvicorn main:app` starts on port 8000 without errors
- CSCM service: starts on port 8001 without errors

## 7. Features Explicitly Excluded
- Database schema — Phase 2
- Authentication — Phase 2
- Supabase connection — Phase 2
- Any business logic — Phase 3+
- Any AI integration — Phase 5+
- Any actual UI screens beyond a placeholder — Phase 4

## 8. Proposed Architecture and Design Decisions
- **Monorepo inside existing repo:** `carebridge/` subdirectory to keep CSCM research and CareBridge AI in one repository (simpler for capstone submission)
- **App Router (Next.js 14):** Modern approach, better suited for server components
- **FastAPI:** Compatible with PyTorch-based CSCM inference, consistent Python environment
- **Separate cscm-service:** Keeps ML inference isolated from business API

## 9. Files and Modules Expected to Change
| File/Directory | Change Type |
|---------------|-------------|
| `scripts/run_all_evals.py` | Restore to original |
| `carebridge/` | Create (new) |
| `carebridge/frontend/` | Create (new, Next.js) |
| `carebridge/backend/` | Create (new, FastAPI) |
| `carebridge/cscm-service/` | Create (new, FastAPI skeleton) |
| `.env.example` | Create (new) |
| `docs/LOCAL_SETUP.md` | Create (new) |
| `.gitignore` | Modify (add carebridge `.env` paths) |

## 10. API Endpoints to Be Added
| Endpoint | Service | Method | Purpose |
|----------|---------|--------|---------|
| `/health` | Backend | GET | Backend health check |
| `/health` | CSCM Service | GET | CSCM service health check |

## 11. Supabase Changes
None in Phase 1. Supabase is configured in Phase 2.

## 12. Groq Changes
None in Phase 1. Groq is configured in Phase 5.

## 13. Security and Privacy Requirements
- No secret values in any committed file
- `.env` files excluded from git
- No real patient data introduced

## 14. UI/UX Requirements
- A placeholder landing page at `/` confirming the app starts
- No actual design work — Phase 4 handles this

## 15. Dependencies and Prerequisites
- Node.js must be installed (requires user to confirm)
- Python 3.11+ available (confirmed: 3.13.2)
- No paid services required

## 16. Risks and Mitigation
| Risk | Mitigation |
|------|-----------|
| Node.js not installed | Ask user to install before starting |
| Port conflicts (3000, 8000, 8001) | Document alternative ports in setup guide |
| Existing CSCM code accidentally modified | Work exclusively inside `carebridge/` |

## 17. Testing Strategy
- Manual verification: all three services start without errors
- `GET /health` returns `{"status": "ok"}` for backend and cscm-service

## 18. Acceptance Criteria
| # | Criterion | Verification |
|---|-----------|-------------|
| AC1 | `scripts/run_all_evals.py` restored to original | Run and confirm subprocess output |
| AC2 | `carebridge/frontend/` starts with `npm run dev` | No build errors, localhost:3000 reachable |
| AC3 | `carebridge/backend/` starts with uvicorn | `GET /health` returns 200 |
| AC4 | `carebridge/cscm-service/` starts with uvicorn | `GET /health` returns 200 |
| AC5 | No secret values in committed files | Git diff reviewed |
| AC6 | `.env.example` documents all required variables | File present and complete |
| AC7 | CSCM research code is unmodified | `git diff src/ models/ scripts/` shows no changes |

## 19. Definition of Done
All 7 acceptance criteria pass. Local development environment is documented and reproducible.

## 20. Rollback Plan
Phase 1 only creates new directories and restores one file. Rollback = delete `carebridge/` and restore `run_all_evals.py` from git.

## 21. Estimated Complexity
Low-Medium. Standard scaffolding work with no complex business logic.

## 22. Cost Implications
₹0. Only free, open-source tooling is used.

## 23. Questions Requiring Owner Decision
1. Should CareBridge live inside `capstone_PRABAKAR/carebridge/` or in a separate repository?
2. Is Node.js installed? (Run: `node --version`)
3. Do you have a Supabase project already?
4. Do you have a Groq API key?
5. What is the name of the hospital for synthetic demo data?
