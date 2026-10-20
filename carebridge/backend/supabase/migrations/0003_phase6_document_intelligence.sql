-- Phase 6: Document Intelligence & Clinician Verification Schema

-- 1. Clinical Documents Table
CREATE TABLE IF NOT EXISTS public.clinical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    uploaded_by UUID NOT NULL REFERENCES auth.users(id),
    document_type TEXT NOT NULL CHECK (document_type IN ('discharge_summary', 'lab_report', 'prescription', 'referral', 'other')),
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    ocr_status TEXT NOT NULL DEFAULT 'pending' CHECK (ocr_status IN ('pending', 'processing', 'completed', 'failed')),
    raw_text TEXT,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_clinical_documents_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_clinical_documents_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_clinical_documents_tenant_patient 
    ON public.clinical_documents(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_documents_tenant_status 
    ON public.clinical_documents(hospital_id, ocr_status);
CREATE INDEX IF NOT EXISTS idx_clinical_documents_uploaded_by 
    ON public.clinical_documents(uploaded_by);

-- 2. Extracted Entities Table
CREATE TABLE IF NOT EXISTS public.extracted_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL,
    document_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    entity_category TEXT NOT NULL CHECK (entity_category IN ('diagnosis', 'medication', 'lab_result', 'vital_sign', 'allergy', 'metadata')),
    extracted_data JSONB NOT NULL,
    confidence_score NUMERIC(3, 2),
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected', 'edited')),
    verified_by UUID REFERENCES auth.users(id),
    verified_at TIMESTAMPTZ,
    doctor_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_extracted_entities_document FOREIGN KEY (hospital_id, document_id)
        REFERENCES public.clinical_documents(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_extracted_entities_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_extracted_entities_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_extracted_entities_tenant_doc 
    ON public.extracted_entities(hospital_id, document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_tenant_patient 
    ON public.extracted_entities(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_tenant_status 
    ON public.extracted_entities(hospital_id, verification_status);

-- 3. Enable RLS
ALTER TABLE public.clinical_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_documents FORCE ROW LEVEL SECURITY;

ALTER TABLE public.extracted_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.extracted_entities FORCE ROW LEVEL SECURITY;

-- 4. RLS Policies for clinical_documents
DROP POLICY IF EXISTS clinical_documents_select ON public.clinical_documents;
CREATE POLICY clinical_documents_select ON public.clinical_documents
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.has_patient_access(hospital_id, patient_id)
    );

DROP POLICY IF EXISTS clinical_documents_insert ON public.clinical_documents;
CREATE POLICY clinical_documents_insert ON public.clinical_documents
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.has_patient_access(hospital_id, patient_id)
        AND uploaded_by = (SELECT auth.uid())
    );

DROP POLICY IF EXISTS clinical_documents_update ON public.clinical_documents;
CREATE POLICY clinical_documents_update ON public.clinical_documents
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR (uploaded_by = (SELECT auth.uid()) AND ocr_status = 'pending')
        )
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR (uploaded_by = (SELECT auth.uid()) AND ocr_status = 'pending')
        )
    );

-- 5. RLS Policies for extracted_entities
DROP POLICY IF EXISTS extracted_entities_select ON public.extracted_entities;
CREATE POLICY extracted_entities_select ON public.extracted_entities
    FOR SELECT TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.has_patient_access(hospital_id, patient_id)
    );

DROP POLICY IF EXISTS extracted_entities_insert ON public.extracted_entities;
CREATE POLICY extracted_entities_insert ON public.extracted_entities
    FOR INSERT TO authenticated
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND (
            public.is_hospital_staff(hospital_id)
            OR (
                public.has_patient_access(hospital_id, patient_id)
                AND verification_status = 'pending'
            )
        )
    );

DROP POLICY IF EXISTS extracted_entities_update ON public.extracted_entities;
CREATE POLICY extracted_entities_update ON public.extracted_entities
    FOR UPDATE TO authenticated
    USING (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    )
    WITH CHECK (
        hospital_id = public.get_auth_hospital_id()
        AND public.is_hospital_staff(hospital_id)
    );

-- Grants
GRANT SELECT, INSERT, UPDATE ON public.clinical_documents TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.extracted_entities TO authenticated;
GRANT ALL ON public.clinical_documents TO service_role;
GRANT ALL ON public.extracted_entities TO service_role;
