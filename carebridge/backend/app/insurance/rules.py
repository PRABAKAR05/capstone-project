from typing import Dict, Any, List, Optional
from datetime import date, datetime, timezone

RULE_VERSION = "v1.0"

CATEGORY_SUB_LIMITS: Dict[str, float] = {
    "specialist_consultation": 5000.0,
    "general_consultation": 2500.0,
    "diagnostic_imaging": 15000.0,
    "inpatient_surgery": 250000.0,
    "daycare_procedure": 50000.0,
    "emergency_care": 75000.0,
}


def calculate_deterministic_estimate(
    policy: Dict[str, Any],
    requested_amount: float,
    procedure_category: str = "general_consultation",
) -> Dict[str, Any]:
    """Evaluates synthetic policy rules deterministically against requested procedure costs.
    Enforces reproducible calculations, explicit exclusion matching, and missing-data review states.
    Strictly zero guessing or autonomous financial commitments.
    """
    now_utc_str = datetime.now(timezone.utc).isoformat()

    # 1. Check for Missing or Ambiguous Policy Attributes
    missing_fields = []
    for field in ("sum_insured_inr", "remaining_balance_inr", "valid_until", "status", "copay_percentage"):
        if field not in policy or policy[field] is None:
            missing_fields.append(field)

    if missing_fields or requested_amount <= 0:
        return {
            "estimate_status": "insufficient_information",
            "rule_version": RULE_VERSION,
            "requested_amount_inr": round(float(requested_amount), 2),
            "applicable_limit_inr": 0.0,
            "deductible_applied_inr": 0.0,
            "copay_percentage": float(policy.get("copay_percentage") or 0.0),
            "estimated_insurer_pays_inr": 0.0,
            "estimated_patient_copay_inr": round(float(requested_amount), 2),
            "matched_exclusion": None,
            "missing_information": missing_fields,
            "calculation_breakdown": {
                "error": "Incomplete policy parameters; unable to compute deterministic estimate."
            },
            "disclaimer": "Insufficient policy information to compute estimate. Please provide full active policy details.",
            "calculated_at": now_utc_str,
        }

    # 2. Check Policy Expiry & Status
    today = date.today()
    valid_until = policy["valid_until"]
    if isinstance(valid_until, str):
        valid_until = date.fromisoformat(valid_until)

    valid_from = policy.get("valid_from")
    if isinstance(valid_from, str):
        valid_from = date.fromisoformat(valid_from)

    if policy.get("status") != "active" or valid_until < today or (valid_from and valid_from > today):
        reason = "policy_expired" if valid_until < today else f"policy_status_{policy.get('status')}"
        return {
            "estimate_status": "insufficient_information",
            "rule_version": RULE_VERSION,
            "requested_amount_inr": round(float(requested_amount), 2),
            "applicable_limit_inr": 0.0,
            "deductible_applied_inr": 0.0,
            "copay_percentage": float(policy.get("copay_percentage", 0.0)),
            "estimated_insurer_pays_inr": 0.0,
            "estimated_patient_copay_inr": round(float(requested_amount), 2),
            "matched_exclusion": reason,
            "missing_information": [reason],
            "calculation_breakdown": {
                "ineligibility_reason": f"Policy is inactive or outside validity window ({valid_from} to {valid_until})."
            },
            "disclaimer": f"Policy is not active or valid for the requested date window ({valid_from} to {valid_until}).",
            "calculated_at": now_utc_str,
        }

    # 3. Match Exclusions
    exclusions = policy.get("exclusions") or []
    norm_proc = procedure_category.strip().lower()
    matched_exclusion = None
    for ex in exclusions:
        if ex.strip().lower() == norm_proc or ex.strip().lower() in norm_proc:
            matched_exclusion = ex
            break

    if matched_exclusion:
        return {
            "estimate_status": "review_required",
            "rule_version": RULE_VERSION,
            "requested_amount_inr": round(float(requested_amount), 2),
            "applicable_limit_inr": 0.0,
            "deductible_applied_inr": 0.0,
            "copay_percentage": float(policy.get("copay_percentage", 0.0)),
            "estimated_insurer_pays_inr": 0.0,
            "estimated_patient_copay_inr": round(float(requested_amount), 2),
            "matched_exclusion": matched_exclusion,
            "missing_information": [],
            "calculation_breakdown": {
                "exclusion_rule": f"Procedure category '{procedure_category}' matches exclusion: '{matched_exclusion}'."
            },
            "calculated_at": now_utc_str,
        }

    # 4. Deterministic Financial Math: Category Limits, Deductible, Co-pay & Caps
    remaining_balance = float(policy.get("remaining_balance_inr", 0.0))
    deductible = float(policy.get("deductible_inr", 0.0))
    copay_pct = float(policy.get("copay_percentage", 10.0)) / 100.0

    category_limit = CATEGORY_SUB_LIMITS.get(norm_proc, remaining_balance)
    applicable_limit = min(remaining_balance, category_limit)

    # Step A: Cap claimable amount by applicable limit
    capped_requested_amount = min(requested_amount, applicable_limit)
    excess_over_limit = max(0.0, requested_amount - applicable_limit)

    # Step B: Apply deductible
    deductible_applied = min(deductible, capped_requested_amount)
    claimable_after_deductible = max(0.0, capped_requested_amount - deductible_applied)

    # Step C: Apply Co-pay Percentage
    calculated_copay = claimable_after_deductible * copay_pct
    calculated_insurer_pays = claimable_after_deductible * (1.0 - copay_pct)

    # Step D: Cap by Remaining Policy Sum Insured
    if calculated_insurer_pays > remaining_balance:
        shortfall = calculated_insurer_pays - remaining_balance
        final_insurer_pays = remaining_balance
        final_patient_copay = calculated_copay + deductible_applied + excess_over_limit + shortfall
    else:
        final_insurer_pays = calculated_insurer_pays
        final_patient_copay = calculated_copay + deductible_applied + excess_over_limit

    return {
        "estimate_status": "estimate_available",
        "rule_version": RULE_VERSION,
        "requested_amount_inr": round(float(requested_amount), 2),
        "applicable_limit_inr": round(applicable_limit, 2),
        "deductible_applied_inr": round(deductible_applied, 2),
        "copay_percentage": round(copay_pct * 100.0, 2),
        "estimated_insurer_pays_inr": round(final_insurer_pays, 2),
        "estimated_patient_copay_inr": round(final_patient_copay, 2),
        "matched_exclusion": None,
        "missing_information": [],
        "calculation_breakdown": {
            "requested_amount": round(requested_amount, 2),
            "applicable_limit": round(applicable_limit, 2),
            "excess_over_limit": round(excess_over_limit, 2),
            "deductible_applied": round(deductible_applied, 2),
            "claimable_amount": round(claimable_after_deductible, 2),
            "copay_ratio": round(copay_pct, 2),
            "patient_copay_share": round(calculated_copay, 2),
            "insurer_share_pre_cap": round(calculated_insurer_pays, 2),
            "remaining_balance_cap": round(remaining_balance, 2),
            "final_insurer_coverage": round(final_insurer_pays, 2),
            "final_patient_out_of_pocket": round(final_patient_copay, 2),
        },
        "disclaimer": "Informational estimate only based on hospital policy rules. Not a guarantee of coverage or formal claim approval.",
        "calculated_at": now_utc_str,
    }
