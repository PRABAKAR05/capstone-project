-- Phase 9 Down Migration
DROP TABLE IF EXISTS public.medication_adherence_logs CASCADE;
DROP TABLE IF EXISTS public.prescription_items CASCADE;
DROP TABLE IF EXISTS public.prescriptions CASCADE;
