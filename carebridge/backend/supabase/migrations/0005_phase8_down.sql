-- Phase 8 Rollback Migration
DROP POLICY IF EXISTS care_tasks_update ON public.care_tasks;
DROP POLICY IF EXISTS care_tasks_insert ON public.care_tasks;
DROP POLICY IF EXISTS care_tasks_select ON public.care_tasks;

DROP TABLE IF EXISTS public.care_tasks;
