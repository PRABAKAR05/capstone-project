-- Phase 7: Clinical Document Conflict Checker & Multi-Encounter Reconciler Schema

-- 1. Clinical Conflicts Table
CREATE TABLE IF NOT EXISTS public.clinical_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN (
        'drug_allergy',
        'duplicate_therapy',
        'drug_drug_interaction',
        'diagnostic_discrepancy',
        'temporal_inconsistency',
        'other'
    )),
    review_priority TEXT NOT NULL CHECK (review_priority IN ('high', 'moderate', 'low')),
    title TEXT NOT NULL,
    clinical_summary TEXT NOT NULL,
    patient_friendly_summary TEXT NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'unresolved' CHECK (resolution_status IN (
        'unresolved',
        'acknowledged_with_rationale',
        'resolved_via_order_change'
    )),
    acknowledged_by UUID REFERENCES auth.users(id),
    acknowledged_at TIMESTAMPTZ,
    clinician_rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_clinical_conflicts_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_clinical_conflicts_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_clinical_conflicts_tenant_patient 
    ON public.clinical_conflicts(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_conflicts_tenant_status 
    ON public.clinical_conflicts(hospital_id, resolution_status);
CREATE INDEX IF NOT EXISTS idx_clinical_conflicts_tenant_priority
    ON public.clinical_conflicts(hospital_id, review_priority);

-- 2. Clinical Conflict Sources (Relational Link Table)
CREATE TABLE IF NOT EXISTS public.clinical_conflict_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    conflict_id UUID NOT NULL,
    document_id UUID,
    entity_id UUID,
    role_in_conflict TEXT NOT NULL CHECK (role_in_conflict IN (
        'prescribed_medication',
        'documented_allergy',
        'interacting_medication',
        'conflicting_diagnosis',
        'baseline_evidence'
    )),
    citation_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_conflict_sources_conflict FOREIGN KEY (hospital_id, conflict_id)
        REFERENCES public.clinical_conflicts(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_conflict_sources_document FOREIGN KEY (hospital_id, document_id)
        REFERENCES public.clinical_documents(hospital_id, id) ON DELETE SET NULL,
    CONSTRAINT fk_conflict_sources_entity FOREIGN KEY (hospital_id, entity_id)
        REFERENCES public.extracted_entities(hospital_id, id) ON DELETE SET NULL,
    CONSTRAINT uq_clinical_conflict_sources_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_conflict_sources_conflict 
    ON public.clinical_conflict_sources(hospital_id, conflict_id);
CREATE INDEX IF NOT EXISTS idx_conflict_sources_entity 
    ON public.clinical_conflict_sources(hospital_id, entity_id);
CREATE INDEX IF NOT EXISTS idx_conflict_sources_document 
    ON public.clinical_conflict_sources(hospital_id, document_id);

-- 3. Enable RLS
ALTER TABLE public.clinical_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_conflicts FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinical_conflict_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_conflict_sources FORCE ROW LEVEL SECURITY;

-- 4. RLS Policies for clinical_conflicts
DROP POLICY IF EXISTS clinical_conflicts_select ON public.clinical_conflicts;
CREATE POLICY clinical_conflicts_select ON public.clinical_conflicts
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR public.has_patient_access(hospital_id, patient_id)
        )
    );

DROP POLICY IF EXISTS clinical_conflicts_insert ON public.clinical_conflicts;
CREATE POLICY clinical_conflicts_insert ON public.clinical_conflicts
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

DROP POLICY IF EXISTS clinical_conflicts_update ON public.clinical_conflicts;
CREATE POLICY clinical_conflicts_update ON public.clinical_conflicts
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- 5. RLS Policies for clinical_conflict_sources
DROP POLICY IF EXISTS clinical_conflict_sources_select ON public.clinical_conflict_sources;
CREATE POLICY clinical_conflict_sources_select ON public.clinical_conflict_sources
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND EXISTS (
            SELECT 1 FROM public.clinical_conflicts c
            WHERE c.hospital_id = clinical_conflict_sources.hospital_id
              AND c.id = clinical_conflict_sources.conflict_id
              AND (
                  public.is_hospital_staff(c.hospital_id)
                  OR public.has_patient_access(c.hospital_id, c.patient_id)
              )
        )
    );

DROP POLICY IF EXISTS clinical_conflict_sources_insert ON public.clinical_conflict_sources;
CREATE POLICY clinical_conflict_sources_insert ON public.clinical_conflict_sources
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- Grants
GRANT SELECT, INSERT, UPDATE ON public.clinical_conflicts TO authenticated;
GRANT SELECT, INSERT ON public.clinical_conflict_sources TO authenticated;
GRANT ALL ON public.clinical_conflicts TO service_role;
GRANT ALL ON public.clinical_conflict_sources TO service_role;
