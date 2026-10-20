-- Phase 7 Rollback Migration
DROP POLICY IF EXISTS clinical_conflict_sources_insert ON public.clinical_conflict_sources;
DROP POLICY IF EXISTS clinical_conflict_sources_select ON public.clinical_conflict_sources;
DROP POLICY IF EXISTS clinical_conflicts_update ON public.clinical_conflicts;
DROP POLICY IF EXISTS clinical_conflicts_insert ON public.clinical_conflicts;
DROP POLICY IF EXISTS clinical_conflicts_select ON public.clinical_conflicts;

DROP TABLE IF EXISTS public.clinical_conflict_sources;
DROP TABLE IF EXISTS public.clinical_conflicts;
