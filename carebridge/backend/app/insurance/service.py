from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import psycopg2
from psycopg2.extras import Json

from app.core.security import SecurityContext
from app.core.database import get_db
from app.core.audit import audit_event
from app.schemas.insurance import (
    InsurancePolicyCreate,
    InsurancePolicyResponse,
    PreAuthEstimateRequest,
    PreAuthEstimateResponse,
    ClaimSubmitRequest,
    ClaimAdjudicateRequest,
    ClaimResponse,
)
from app.insurance.rules import calculate_deterministic_estimate, RULE_VERSION


def verify_patient_access(cur, context: SecurityContext, patient_id: UUID):
    """Ensures patient callers only access authorized patient records."""
    if context.role == "patient":
        cur.execute("""
            SELECT 1 FROM public.patient_accounts
            WHERE hospital_id = %s AND user_id = %s AND patient_id = %s AND status = 'verified';
        """, (str(context.hospital_id), str(context.user_id), str(patient_id)))
        if not cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not accessible.",
            )


def register_patient_policy(context: SecurityContext, payload: InsurancePolicyCreate) -> InsurancePolicyResponse:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            verify_patient_access(cur, context, payload.patient_id)
            policy_id = uuid4()
            cur.execute("""
                INSERT INTO public.patient_insurance_policies (
                    id, hospital_id, patient_id, provider_name, policy_number,
                    policy_holder_name, relation_to_patient, sum_insured_inr,
                    remaining_balance_inr, copay_percentage, deductible_inr,
                    exclusions, valid_from, valid_until, status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, 'active'
                ) RETURNING created_at, updated_at;
            """, (
                str(policy_id), str(context.hospital_id), str(payload.patient_id),
                payload.provider_name, payload.policy_number, payload.policy_holder_name,
                payload.relation_to_patient, payload.sum_insured_inr, payload.sum_insured_inr,
                payload.copay_percentage, payload.deductible_inr,
                Json(payload.exclusions), payload.valid_from, payload.valid_until
            ))
            row = cur.fetchone()

            audit_event(
                event_type="INSURANCE_POLICY_REGISTERED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="patient_insurance_policy",
                target_id=str(policy_id),
                action="CREATE",
                status="SUCCESS",
            )

            return InsurancePolicyResponse(
                id=policy_id,
                hospital_id=context.hospital_id,
                patient_id=payload.patient_id,
                provider_name=payload.provider_name,
                policy_number=payload.policy_number,
                policy_holder_name=payload.policy_holder_name,
                relation_to_patient=payload.relation_to_patient,
                sum_insured_inr=payload.sum_insured_inr,
                remaining_balance_inr=payload.sum_insured_inr,
                copay_percentage=payload.copay_percentage,
                deductible_inr=payload.deductible_inr,
                exclusions=payload.exclusions,
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
                status="active",
                created_at=row[0],
                updated_at=row[1],
            )


def get_patient_policies(context: SecurityContext, patient_id: UUID) -> List[InsurancePolicyResponse]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            verify_patient_access(cur, context, patient_id)
            cur.execute("""
                SELECT id, hospital_id, patient_id, provider_name, policy_number,
                       policy_holder_name, relation_to_patient, sum_insured_inr,
                       remaining_balance_inr, copay_percentage, deductible_inr,
                       exclusions, valid_from, valid_until, status, created_at, updated_at
                FROM public.patient_insurance_policies
                WHERE hospital_id = %s AND patient_id = %s
                ORDER BY created_at DESC;
            """, (str(context.hospital_id), str(patient_id)))
            rows = cur.fetchall()

            return [
                InsurancePolicyResponse(
                    id=r[0],
                    hospital_id=r[1],
                    patient_id=r[2],
                    provider_name=r[3],
                    policy_number=r[4],
                    policy_holder_name=r[5],
                    relation_to_patient=r[6],
                    sum_insured_inr=float(r[7]),
                    remaining_balance_inr=float(r[8]),
                    copay_percentage=float(r[9]),
                    deductible_inr=float(r[10]),
                    exclusions=r[11] if isinstance(r[11], list) else [],
                    valid_from=r[12],
                    valid_until=r[13],
                    status=r[14],
                    created_at=r[15],
                    updated_at=r[16],
                )
                for r in rows
            ]


def generate_preauth_estimate(context: SecurityContext, payload: PreAuthEstimateRequest) -> PreAuthEstimateResponse:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            verify_patient_access(cur, context, payload.patient_id)
            cur.execute("""
                SELECT id, provider_name, policy_number, sum_insured_inr, remaining_balance_inr,
                       copay_percentage, deductible_inr, exclusions, valid_from, valid_until, status
                FROM public.patient_insurance_policies
                WHERE id = %s AND hospital_id = %s AND patient_id = %s;
            """, (str(payload.policy_id), str(context.hospital_id), str(payload.patient_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insurance policy not found.")

            policy_dict = {
                "id": str(row[0]),
                "provider_name": row[1],
                "policy_number": row[2],
                "sum_insured_inr": float(row[3]),
                "remaining_balance_inr": float(row[4]),
                "copay_percentage": float(row[5]),
                "deductible_inr": float(row[6]),
                "exclusions": row[7] if isinstance(row[7], list) else [],
                "valid_from": row[8],
                "valid_until": row[9],
                "status": row[10],
            }

            est = calculate_deterministic_estimate(
                policy=policy_dict,
                requested_amount=payload.requested_amount_inr,
                procedure_category=payload.procedure_category,
            )

            return PreAuthEstimateResponse(
                estimate_status=est["estimate_status"],
                rule_version=est["rule_version"],
                policy_id=payload.policy_id,
                provider_name=policy_dict["provider_name"],
                policy_number=policy_dict["policy_number"],
                requested_amount_inr=est["requested_amount_inr"],
                applicable_limit_inr=est["applicable_limit_inr"],
                deductible_applied_inr=est["deductible_applied_inr"],
                copay_percentage=est["copay_percentage"],
                estimated_insurer_pays_inr=est["estimated_insurer_pays_inr"],
                estimated_patient_copay_inr=est["estimated_patient_copay_inr"],
                matched_exclusion=est.get("matched_exclusion"),
                missing_information=est.get("missing_information", []),
                calculation_breakdown=est["calculation_breakdown"],
                calculated_at=est["calculated_at"],
            )


def submit_claim(context: SecurityContext, payload: ClaimSubmitRequest) -> ClaimResponse:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            verify_patient_access(cur, context, payload.patient_id)
            # Fetch policy
            cur.execute("""
                SELECT sum_insured_inr, remaining_balance_inr, copay_percentage, deductible_inr,
                       exclusions, valid_from, valid_until, status
                FROM public.patient_insurance_policies
                WHERE id = %s AND hospital_id = %s AND patient_id = %s;
            """, (str(payload.policy_id), str(context.hospital_id), str(payload.patient_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")

            policy_dict = {
                "sum_insured_inr": float(row[0]),
                "remaining_balance_inr": float(row[1]),
                "copay_percentage": float(row[2]),
                "deductible_inr": float(row[3]),
                "exclusions": row[4] if isinstance(row[4], list) else [],
                "valid_from": row[5],
                "valid_until": row[6],
                "status": row[7],
            }

            est = calculate_deterministic_estimate(
                policy=policy_dict,
                requested_amount=payload.requested_amount_inr,
                procedure_category=payload.procedure_category,
            )

            claim_id = uuid4()
            init_status = "pre_auth_requested" if payload.claim_type == "pre_auth" else "claim_submitted"

            cur.execute("""
                INSERT INTO public.insurance_claims (
                    id, hospital_id, policy_id, patient_id, appointment_id,
                    claim_type, requested_amount_inr, approved_amount_inr,
                    patient_copay_amount_inr, adjudication_status, rule_version,
                    calculation_breakdown
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s
                ) RETURNING created_at, updated_at;
            """, (
                str(claim_id), str(context.hospital_id), str(payload.policy_id), str(payload.patient_id),
                str(payload.appointment_id) if payload.appointment_id else None,
                payload.claim_type, payload.requested_amount_inr, est["estimated_insurer_pays_inr"],
                est["estimated_patient_copay_inr"], init_status, RULE_VERSION,
                Json(est["calculation_breakdown"])
            ))
            res = cur.fetchone()

            audit_event(
                event_type="INSURANCE_CLAIM_SUBMITTED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="insurance_claim",
                target_id=str(claim_id),
                action="SUBMIT",
                status="SUCCESS",
            )

            return ClaimResponse(
                id=claim_id,
                hospital_id=context.hospital_id,
                policy_id=payload.policy_id,
                patient_id=payload.patient_id,
                appointment_id=payload.appointment_id,
                claim_type=payload.claim_type,
                requested_amount_inr=payload.requested_amount_inr,
                approved_amount_inr=est["estimated_insurer_pays_inr"],
                patient_copay_amount_inr=est["estimated_patient_copay_inr"],
                adjudication_status=init_status,
                denial_reason=None,
                settlement_reference=None,
                adjudicated_by=None,
                adjudicated_at=None,
                rule_version=RULE_VERSION,
                calculation_breakdown=est["calculation_breakdown"],
                created_at=res[0],
                updated_at=res[1],
            )


def adjudicate_claim(context: SecurityContext, claim_id: UUID, payload: ClaimAdjudicateRequest) -> ClaimResponse:
    # AC-11.5: Staff Adjudication Barrier - Patients strictly prohibited
    if context.role == "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Patients are strictly prohibited from adjudicating insurance claims.",
        )

    with get_db(context) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, hospital_id, policy_id, patient_id, appointment_id,
                       claim_type, requested_amount_inr, approved_amount_inr,
                       patient_copay_amount_inr, adjudication_status, calculation_breakdown
                FROM public.insurance_claims
                WHERE id = %s AND hospital_id = %s;
            """, (str(claim_id), str(context.hospital_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim record not found.")

            # Validate lifecycle transition (AC-11.3)
            current_status = row[9]
            valid_targets = {
                "draft": ["pre_auth_requested", "claim_submitted", "rejected"],
                "pre_auth_requested": ["pre_auth_approved", "pre_auth_denied", "claim_submitted"],
                "pre_auth_approved": ["claim_submitted", "settled"],
                "pre_auth_denied": ["claim_submitted", "rejected"],
                "claim_submitted": ["settled", "rejected"],
                "settled": [],
                "rejected": [],
            }
            if payload.adjudication_status not in valid_targets.get(current_status, []):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from '{current_status}' to '{payload.adjudication_status}'.",
                )

            now_utc = datetime.now(timezone.utc)
            cur.execute("""
                UPDATE public.insurance_claims
                SET adjudication_status = %s,
                    approved_amount_inr = COALESCE(%s, approved_amount_inr),
                    settlement_reference = %s,
                    denial_reason = %s,
                    adjudicated_by = %s,
                    adjudicated_at = %s,
                    updated_at = %s
                WHERE id = %s AND hospital_id = %s
                RETURNING created_at, updated_at;
            """, (
                payload.adjudication_status, payload.approved_amount_inr,
                payload.settlement_reference, payload.denial_reason,
                str(context.user_id), now_utc, now_utc,
                str(claim_id), str(context.hospital_id)
            ))
            up_row = cur.fetchone()

            audit_event(
                event_type="INSURANCE_CLAIM_ADJUDICATED",
                actor_id=str(context.user_id),
                actor_role=context.role,
                hospital_id=str(context.hospital_id),
                target_resource="insurance_claim",
                target_id=str(claim_id),
                action="ADJUDICATE",
                status="SUCCESS",
            )

            return ClaimResponse(
                id=claim_id,
                hospital_id=context.hospital_id,
                policy_id=row[2],
                patient_id=row[3],
                appointment_id=row[4],
                claim_type=row[5],
                requested_amount_inr=float(row[6]),
                approved_amount_inr=float(payload.approved_amount_inr or row[7]),
                patient_copay_amount_inr=float(row[8]),
                adjudication_status=payload.adjudication_status,
                denial_reason=payload.denial_reason,
                settlement_reference=payload.settlement_reference,
                adjudicated_by=context.user_id,
                adjudicated_at=now_utc,
                rule_version=RULE_VERSION,
                calculation_breakdown=row[10] if isinstance(row[10], dict) else {},
                created_at=up_row[0],
                updated_at=up_row[1],
            )


def list_claims(context: SecurityContext, patient_id: Optional[UUID] = None, status_filter: Optional[str] = None) -> List[ClaimResponse]:
    with get_db(context) as conn:
        with conn.cursor() as cur:
            if context.role == "patient":
                if not patient_id:
                    # Resolve patient account
                    cur.execute("""
                        SELECT patient_id FROM public.patient_accounts
                        WHERE hospital_id = %s AND user_id = %s AND status = 'verified'
                        LIMIT 1;
                    """, (str(context.hospital_id), str(context.user_id)))
                    p_row = cur.fetchone()
                    if not p_row:
                        return []
                    patient_id = p_row[0]
                else:
                    verify_patient_access(cur, context, patient_id)

            query = """
                SELECT id, hospital_id, policy_id, patient_id, appointment_id,
                       claim_type, requested_amount_inr, approved_amount_inr,
                       patient_copay_amount_inr, adjudication_status, denial_reason,
                       settlement_reference, adjudicated_by, adjudicated_at,
                       rule_version, calculation_breakdown, created_at, updated_at
                FROM public.insurance_claims
                WHERE hospital_id = %s
            """
            params: List[Any] = [str(context.hospital_id)]
            if patient_id:
                query += " AND patient_id = %s"
                params.append(str(patient_id))
            if status_filter:
                query += " AND adjudication_status = %s"
                params.append(status_filter)
            query += " ORDER BY created_at DESC LIMIT 50;"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            return [
                ClaimResponse(
                    id=r[0],
                    hospital_id=r[1],
                    policy_id=r[2],
                    patient_id=r[3],
                    appointment_id=r[4],
                    claim_type=r[5],
                    requested_amount_inr=float(r[6]),
                    approved_amount_inr=float(r[7]),
                    patient_copay_amount_inr=float(r[8]),
                    adjudication_status=r[9],
                    denial_reason=r[10],
                    settlement_reference=r[11],
                    adjudicated_by=r[12],
                    adjudicated_at=r[13],
                    rule_version=r[14] or RULE_VERSION,
                    calculation_breakdown=r[15] if isinstance(r[15], dict) else {},
                    created_at=r[16],
                    updated_at=r[17],
                )
                for r in rows
            ]
