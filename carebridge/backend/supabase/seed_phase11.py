import psycopg2
import json
from app.core.config import settings

def seed_phase11():
    conn = psycopg2.connect(settings.DATABASE_URL)
    with conn.cursor() as cur:
        # Seed demo policy
        cur.execute("""
            INSERT INTO public.patient_insurance_policies (
                id, hospital_id, patient_id, provider_name, policy_number,
                policy_holder_name, relation_to_patient, sum_insured_inr,
                remaining_balance_inr, copay_percentage, deductible_inr,
                exclusions, valid_from, valid_until, status
            ) VALUES (
                '11111111-9999-9999-9999-111111111111',
                '11111111-1111-1111-1111-111111111111',
                '11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                'Star Health Premier Gold',
                'SH-2026-981244',
                'Ananya Sharma',
                'self',
                1000000.00,
                850000.00,
                10.00,
                2000.00,
                '["cosmetic_surgery", "experimental_therapy", "unverified_supplements"]'::jsonb,
                '2026-01-01',
                '2027-01-01',
                'active'
            ) ON CONFLICT (id) DO NOTHING;
        """)

        # Seed demo claim / pre-auth
        cur.execute("""
            INSERT INTO public.insurance_claims (
                id, hospital_id, policy_id, patient_id, claim_type,
                requested_amount_inr, approved_amount_inr, patient_copay_amount_inr,
                adjudication_status, denial_reason, settlement_reference,
                rule_version, calculation_breakdown
            ) VALUES (
                '22222222-9999-9999-9999-222222222222',
                '11111111-1111-1111-1111-111111111111',
                '11111111-9999-9999-9999-111111111111',
                '11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                'pre_auth',
                15000.00,
                13500.00,
                1500.00,
                'pre_auth_approved',
                NULL,
                'PA-AUTH-2026-0041',
                'v1.0',
                '{"base_cost": 15000.0, "covered_eligible": 15000.0, "deductible_applied": 0.0, "copay_ratio": 0.1, "insurer_pays": 13500.0, "patient_copay": 1500.0}'::jsonb
            ) ON CONFLICT (id) DO NOTHING;
        """)
        conn.commit()
    conn.close()
    print("Phase 11 seed records populated successfully.")

if __name__ == "__main__":
    seed_phase11()
