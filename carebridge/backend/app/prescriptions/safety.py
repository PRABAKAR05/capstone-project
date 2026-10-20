"""Pre-issuance Clinical Decision Support safety check for digital prescriptions.

Checks proposed prescription items against:
1. Internal item-to-item interactions (e.g. concurrent ACE-I + ARB, Opioid + Benzodiazepine).
2. Existing active prescriptions for the patient.
3. Documented patient allergies (via extracted_entities allergy matrix).

Deterministic and explainable CDS advisory.
"""

from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.conflicts.knowledge_base import (
    DRUG_DRUG_INTERACTIONS,
    ALLERGY_CROSS_REACTIVITY,
    get_drug_classes,
    normalize_drug_name
)


def evaluate_proposed_items_safety(
    proposed_items: List[Dict],
    existing_active_items: List[Dict],
    patient_allergies: List[str]
) -> Dict:
    """
    Evaluates proposed prescription items against internal interactions,
    active prescription items, and documented allergies.
    """
    conflicts: List[Dict] = []

    # 1. Internal check between proposed items
    num_items = len(proposed_items)
    for i in range(num_items):
        item_a = proposed_items[i]
        drug_a = item_a.get("drug_name", "")
        classes_a = get_drug_classes(drug_a)
        norm_a = normalize_drug_name(drug_a)

        # Allergy check for item_a
        for allergy_term in patient_allergies:
            norm_allergy = normalize_drug_name(allergy_term)
            if norm_allergy in norm_a or norm_a in norm_allergy:
                conflicts.append({
                    "conflict_type": "allergy_conflict",
                    "severity": "high",
                    "title": f"Documented Direct Allergy Alert: {drug_a.title()}",
                    "description": f"Patient has a documented allergy to '{allergy_term}'. Prescribing '{drug_a}' poses immediate hypersensitivity risk.",
                    "patient_advisory": f"Your doctor is verifying your recorded allergy to {allergy_term} before prescribing this medication.",
                    "involved_drugs": [drug_a, allergy_term]
                })

            for allergen_key, rules in ALLERGY_CROSS_REACTIVITY.items():
                if allergen_key in norm_allergy or norm_allergy in allergen_key:
                    for target_pattern, severity, clinical_desc in rules:
                        if target_pattern in classes_a or any(target_pattern.lower() in c.lower() for c in classes_a):
                            conflicts.append({
                                "conflict_type": "allergy_conflict",
                                "severity": severity,
                                "title": f"Cross-Reactive Allergy Alert: {drug_a.title()}",
                                "description": f"Documented allergy to '{allergy_term}' cross-reacts with therapeutic class {target_pattern}. {clinical_desc}",
                                "patient_advisory": f"Your care team is confirming this medication is safe given your recorded sensitivity to {allergy_term}.",
                                "involved_drugs": [drug_a, allergy_term]
                            })

        # Internal pair-wise checks
        for j in range(i + 1, num_items):
            item_b = proposed_items[j]
            drug_b = item_b.get("drug_name", "")
            classes_b = get_drug_classes(drug_b)
            norm_b = normalize_drug_name(drug_b)

            # Duplicate drug or class
            if norm_a and norm_b and norm_a == norm_b:
                conflicts.append({
                    "conflict_type": "duplicate_therapy",
                    "severity": "high",
                    "title": f"Duplicate Drug Prescribed: {drug_a.title()}",
                    "description": f"'{drug_a}' is prescribed multiple times in the same order.",
                    "patient_advisory": f"Your doctor is confirming your exact dosage for {drug_a}.",
                    "involved_drugs": [drug_a, drug_b]
                })

            # Check drug-drug interaction matrix
            for class_1, class_2, severity, title, clinical_desc, patient_phrase in DRUG_DRUG_INTERACTIONS:
                if (class_1 in classes_a and class_2 in classes_b) or (class_2 in classes_a and class_1 in classes_b):
                    conflicts.append({
                        "conflict_type": "drug_interaction",
                        "severity": severity,
                        "title": title,
                        "description": clinical_desc,
                        "patient_advisory": patient_phrase,
                        "involved_drugs": [drug_a, drug_b]
                    })

    # 2. Check proposed items against existing active prescription items
    for item_a in proposed_items:
        drug_a = item_a.get("drug_name", "")
        classes_a = get_drug_classes(drug_a)
        norm_a = normalize_drug_name(drug_a)

        for active_item in existing_active_items:
            drug_b = active_item.get("drug_name", "")
            classes_b = get_drug_classes(drug_b)
            norm_b = normalize_drug_name(drug_b)

            if norm_a and norm_b and norm_a == norm_b:
                conflicts.append({
                    "conflict_type": "duplicate_therapy",
                    "severity": "high",
                    "title": f"Active Prescription Redundancy: {drug_a.title()}",
                    "description": f"Patient already has an active prescription for '{drug_b}'. Consider dose titration or discontinuing previous prescription.",
                    "patient_advisory": f"Your doctor is verifying your current active prescription for {drug_a}.",
                    "involved_drugs": [drug_a, drug_b]
                })

            for class_1, class_2, severity, title, clinical_desc, patient_phrase in DRUG_DRUG_INTERACTIONS:
                if (class_1 in classes_a and class_2 in classes_b) or (class_2 in classes_a and class_1 in classes_b):
                    conflicts.append({
                        "conflict_type": "drug_interaction",
                        "severity": severity,
                        "title": title,
                        "description": f"Interaction between newly prescribed '{drug_a}' and active '{drug_b}': {clinical_desc}",
                        "patient_advisory": patient_phrase,
                        "involved_drugs": [drug_a, drug_b]
                    })

    # Calculate max severity
    severity_order = {"urgent": 4, "high": 3, "moderate": 2, "low": 1}
    max_sev = "none"
    max_rank = 0
    for c in conflicts:
        rank = severity_order.get(c.get("severity", "low"), 1)
        if rank > max_rank:
            max_rank = rank
            max_sev = c.get("severity", "low")

    return {
        "has_conflicts": len(conflicts) > 0,
        "max_severity": max_sev,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "advisory_summary": f"Detected {len(conflicts)} potential conflict(s)" if conflicts else "No safety conflicts detected."
    }


def check_pre_issuance_safety(
    hospital_id: str,
    patient_id: str,
    proposed_items: List[Dict],
    db_conn
) -> Dict:
    """
    Executes database queries to fetch active prescriptions and verified allergies,
    then evaluates safety for the proposed items.
    """
    # 1. Fetch active prescription items
    active_items: List[Dict] = []
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT pi.drug_name, pi.dosage, pi.frequency, pi.therapeutic_class
            FROM public.prescription_items pi
            JOIN public.prescriptions p ON p.id = pi.prescription_id
            WHERE p.hospital_id = %s
              AND p.patient_id = %s
              AND p.status IN ('prescribed', 'ready_for_pickup', 'dispensed')
              AND p.valid_until > timezone('utc'::text, now())
            """,
            (hospital_id, patient_id)
        )
        active_items = cur.fetchall()

    # 2. Fetch documented patient allergies
    allergies: List[str] = []
    with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT extracted_data
            FROM public.extracted_entities
            WHERE hospital_id = %s
              AND patient_id = %s
              AND entity_category = 'allergies'
              AND verification_status IN ('verified', 'pending')
            """,
            (hospital_id, patient_id)
        )
        for row in cur.fetchall():
            data = row.get("extracted_data") or {}
            if isinstance(data, dict):
                allergen = data.get("allergen") or data.get("substance") or data.get("name")
                if allergen:
                    allergies.append(str(allergen))
            elif isinstance(data, str):
                allergies.append(data)

    return evaluate_proposed_items_safety(proposed_items, active_items, allergies)
