# CareBridge AI — Clinical Frontend Application

**Modern, Multi-Persona Clinical Workstation & Patient Portal**

Built on **Next.js 16.4.0 (Turbopack)**, **React 19.3.0**, and **Tailwind CSS v4**, the CareBridge AI frontend provides secure, role-specialized interfaces for hospital administrators, doctors, nurses, laboratory technicians, and patients.

---

## Key Capabilities

- **Role-Based Workstations:** Distinct layouts and permission boundaries tailored for 5 canonical healthcare personas:
  - **Hospital Administrator (`/admin`):** System metrics, operational analytics, and role governance.
  - **Physician Workstation (`/doctor`):** Real-time IoMT bedside telemetry, clinical entity extraction, medication conflict reviews, and cryptographic e-prescriptions.
  - **Nurse Care Station (`/nurse`, `/tasks`):** Bedside triage queue, vitals monitoring, care task claiming, and completion notes.
  - **Diagnostic Laboratory (`/lab`):** Specimen accessioning and test logging with demographics-masked patient protection.
  - **Patient & Family Portal (`/portal`):** Appointment scheduling (`/portal/book`), caregiver authorization (`/portal/caregivers`), and document records (`/portal/documents`).
- **Interactive IoMT Telemetry Monitor:** Real-time multi-channel physiological sensor display (`IoMTMonitorCard`) with one-click False Data Injection (FDI) attack simulation to demonstrate live GAT anomaly detection.
- **Dual-Mode Authentication:** Seamlessly supports both Supabase Auth sessions and FastAPI native authentication tokens with automatic fallback and session persistence.
- **Public e-Prescription Verification (`/verify-prescription/[hash]`):** Zero-PII public verification interface enabling pharmacies and patients to validate digital signature integrity.
- **Interactive Guided Demo (`/demo`):** Pre-configured persona switching allowing instant evaluation of all 5 clinical workflows without manual re-authentication.

---

## Application Route Structure

```
app/
├── (auth)/
│   └── login/                  # Dual-auth login supporting native & Supabase auth
├── (dashboard)/
│   ├── admin/                  # Hospital admin analytics & governance
│   ├── doctor/                 # Physician workstation & patient telemetry
│   │   └── documents/[id]/     # Clinical document entity viewer & verification
│   ├── nurse/                  # Nurse station & bedside vitals
│   ├── lab/                    # Diagnostic laboratory workstation (demographics masked)
│   └── tasks/                  # Inter-disciplinary clinical care task board
├── (portal)/
│   └── portal/                 # Patient & family self-service portal
│       ├── book/               # Multi-specialty appointment booking
│       ├── caregivers/         # Caregiver authorization & proxy access
│       └── documents/          # Secure medical records & lab reports
├── demo/                       # Interactive multi-role guided demonstration
├── verify-prescription/[hash]/ # Public zero-PII cryptographic prescription verification
├── layout.tsx                  # Global root layout with theme & auth providers
└── page.tsx                    # Landing page with platform overview & quick access
```

---

## Tech Stack & Architecture

- **Framework:** Next.js 16.4.0 (App Router, Turbopack, Partial Prerendering)
- **UI Library:** React 19.3.0
- **Styling:** Tailwind CSS v4 with custom clinical design system
- **Icons:** Lucide React
- **Component Primitives:** Radix UI accessible headless components
- **State & Context:** React Context (`auth-context.tsx`) with optimistic local storage caching
- **API Client:** Type-safe fetch wrapper (`lib/api.ts`) with RFC 7807 Problem Details error handling

---

## Local Development Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Configuration
Create `.env.local` in this directory:
```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### 3. Run Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Production Build & Verification

```bash
# Run ESLint validation
npm run lint

# Run Next.js production build with Turbopack & TypeScript checks
npm run build

# Start production server
npm run start
```

All 19 static and dynamic routes compile cleanly with zero TypeScript errors.
