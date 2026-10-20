"""Deterministic Clinical Document Conflict Checker & Multi-Encounter Reconciler.

Analyzes clinical entities across encounters to detect:
1. Drug-Allergy Violations & Cross-Reactivity
2. Duplicate Therapeutic Classes
3. Severe Drug-Drug Interactions
4. Contradictory Diagnostic Baselines

Adheres strictly to Phase 7 governance:
- Deterministic, explainable rule engine.
- Advisory CDS only: no autonomous record mutations.
- Distinct handling of provisional (unverified) vs verified findings.
- Relational integrity linking sources to documents and entities.
"""

from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID

from app.conflicts.knowledge_base import (
    normalize_drug_name,
    get_drug_classes,
    ALLERGY_CROSS_REACTIVITY,
    DRUG_DRUG_INTERACTIONS,
    DIAGNOSTIC_CONTRADICTIONS,
)


class DetectedConflict:
    def __init__(
        self,
        conflict_type: str,
        review_priority: str,
        title: str,
        clinical_summary: str,
        patient_friendly_summary: str,
        sources: List[Dict[str, Any]],
        is_provisional: bool = False,
    ):
        self.conflict_type = conflict_type
        self.review_priority = review_priority
        self.title = title
        self.clinical_summary = clinical_summary
        self.patient_friendly_summary = patient_friendly_summary
        self.sources = sources
        self.is_provisional = is_provisional


def detect_conflicts_from_entities(
    hospital_id: UUID,
    patient_id: UUID,
    entities: List[Dict[str, Any]],
    documents_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[DetectedConflict]:
    """Run deterministic conflict detection on all extracted entities for a patient."""
    docs_map = documents_map or {}
    detected: List[DetectedConflict] = []

    # Partition entities by category
    medications: List[Dict[str, Any]] = []
    allergies: List[Dict[str, Any]] = []
    diagnoses: List[Dict[str, Any]] = []

    for ent in entities:
        cat = ent.get("entity_category")
        if cat == "medication":
            medications.append(ent)
        elif cat == "allergy":
            allergies.append(ent)
        elif cat == "diagnosis":
            diagnoses.append(ent)

    # --------------------------------------------------------------------------
    # 1. DRUG-ALLERGY & CROSS-REACTIVITY CONFLICTS
    # --------------------------------------------------------------------------
    for med in medications:
        med_data = med.get("extracted_data") or {}
        drug_name = med_data.get("drug_name") or ""
        norm_drug = normalize_drug_name(drug_name)
        if not norm_drug:
            continue

        med_classes = get_drug_classes(drug_name)
        med_ver_status = med.get("verification_status", "pending")
        med_doc_id = med.get("document_id")
        med_doc_name = docs_map.get(str(med_doc_id), {}).get("file_name", "Clinical Record")

        for alg in allergies:
            alg_data = alg.get("extracted_data") or {}
            allergen = alg_data.get("allergen") or ""
            norm_allergen = normalize_drug_name(allergen)
            if not norm_allergen:
                continue

            alg_ver_status = alg.get("verification_status", "pending")
            alg_doc_id = alg.get("document_id")
            alg_doc_name = docs_map.get(str(alg_doc_id), {}).get("file_name", "Clinical Record")

            is_provisional = (med_ver_status == "pending" or alg_ver_status == "pending")
            prov_tag = "[Provisional] " if is_provisional else ""

            # Direct allergen name match
            if norm_allergen in norm_drug or norm_drug in norm_allergen:
                title = f"{prov_tag}Direct Drug-Allergy Conflict: {drug_name.title()} vs Documented {allergen.title()} Allergy"
                clin_summary = (
                    f"Direct allergen conflict identified: Patient prescribed {drug_name} despite documented allergy "
                    f"to {allergen}. Source records: Medication from '{med_doc_name}', Allergy from '{alg_doc_name}'. "
                    f"{'Note: Contains provisional unverified extractions.' if is_provisional else ''}"
                )
                pat_summary = (
                    f"Your care team is reviewing your prescription for {drug_name.title()} against your documented "
                    f"allergy to {allergen.title()} to ensure your complete safety."
                )
                detected.append(
                    DetectedConflict(
                        conflict_type="drug_allergy",
                        review_priority="high",
                        title=title,
                        clinical_summary=clin_summary,
                        patient_friendly_summary=pat_summary,
                        sources=[
                            {
                                "role_in_conflict": "prescribed_medication",
                                "document_id": med_doc_id,
                                "entity_id": med.get("id"),
                                "citation_text": f"Prescribed drug: {drug_name} in {med_doc_name}",
                            },
                            {
                                "role_in_conflict": "documented_allergy",
                                "document_id": alg_doc_id,
                                "entity_id": alg.get("id"),
                                "citation_text": f"Documented allergy: {allergen} in {alg_doc_name}",
                            },
                        ],
                        is_provisional=is_provisional,
                    )
                )
                continue

            # Cross-reactivity matrix check
            for trigger_sub, cross_rules in ALLERGY_CROSS_REACTIVITY.items():
                if trigger_sub in norm_allergen:
                    for target_class, priority, clinical_note in cross_rules:
                        if target_class in med_classes:
                            title = f"{prov_tag}Allergy Cross-Reactivity Risk: {drug_name.title()} ({target_class}) vs {allergen.title()}"
                            clin_summary = (
                                f"{clinical_note} Prescribed: {drug_name} (Class: {target_class}) in '{med_doc_name}'. "
                                f"Allergen: {allergen} in '{alg_doc_name}'. "
                                f"{'Note: Provisional unverified entity involved.' if is_provisional else ''}"
                            )
                            pat_summary = (
                                f"Your doctor is verifying that {drug_name.title()} is completely compatible with your "
                                f"recorded allergy to {allergen.title()} before continuing your regimen."
                            )
                            detected.append(
                                DetectedConflict(
                                    conflict_type="drug_allergy",
                                    review_priority=priority,
                                    title=title,
                                    clinical_summary=clin_summary,
                                    patient_friendly_summary=pat_summary,
                                    sources=[
                                        {
                                            "role_in_conflict": "prescribed_medication",
                                            "document_id": med_doc_id,
                                            "entity_id": med.get("id"),
                                            "citation_text": f"Prescribed: {drug_name} in {med_doc_name}",
                                        },
                                        {
                                            "role_in_conflict": "documented_allergy",
                                            "document_id": alg_doc_id,
                                            "entity_id": alg.get("id"),
                                            "citation_text": f"Documented allergy: {allergen} in {alg_doc_name}",
                                        },
                                    ],
                                    is_provisional=is_provisional,
                                )
                            )

    # --------------------------------------------------------------------------
    # 2. DUPLICATE THERAPEUTIC CLASS & ACTIVE DRUG-DRUG INTERACTIONS
    # --------------------------------------------------------------------------
    for i in range(len(medications)):
        med1 = medications[i]
        d1 = med1.get("extracted_data") or {}
        name1 = d1.get("drug_name") or ""
        norm1 = normalize_drug_name(name1)
        if not norm1:
            continue

        status1 = str(d1.get("status", "active")).lower()
        if status1 in ["discontinued", "completed", "stopped"]:
            continue

        classes1 = get_drug_classes(name1)
        doc1_id = med1.get("document_id")
        doc1_name = docs_map.get(str(doc1_id), {}).get("file_name", "Clinical Record 1")
        ver1 = med1.get("verification_status", "pending")

        for j in range(i + 1, len(medications)):
            med2 = medications[j]
            d2 = med2.get("extracted_data") or {}
            name2 = d2.get("drug_name") or ""
            norm2 = normalize_drug_name(name2)
            if not norm2:
                continue

            status2 = str(d2.get("status", "active")).lower()
            if status2 in ["discontinued", "completed", "stopped"]:
                continue

            # Skip identical drug names to avoid duplicate hits on the same medication recorded across visits
            if norm1 == norm2:
                continue

            classes2 = get_drug_classes(name2)
            doc2_id = med2.get("document_id")
            doc2_name = docs_map.get(str(doc2_id), {}).get("file_name", "Clinical Record 2")
            ver2 = med2.get("verification_status", "pending")

            is_provisional = (ver1 == "pending" or ver2 == "pending")
            prov_tag = "[Provisional] " if is_provisional else ""

            # (A) Check Duplicate Therapeutic Class
            common_classes = set(classes1).intersection(set(classes2))
            for cls in common_classes:
                title = f"{prov_tag}Duplicate Therapeutic Class: {name1.title()} and {name2.title()} ({cls})"
                clin_summary = (
                    f"Concurrent active therapy detected with multiple agents from identical therapeutic class: {cls}. "
                    f"Agent A: {name1} from '{doc1_name}'. Agent B: {name2} from '{doc2_name}'. "
                    f"Simultaneous duplicate therapy risks synergistic toxicity without clinical benefit. "
                    f"{'Provisional: Pending document verification.' if is_provisional else ''}"
                )
                pat_summary = (
                    f"Your care team noticed you may have two similar medications ({name1.title()} and {name2.title()}) "
                    f"listed across your medical records and is confirming the correct one for you to take."
                )
                detected.append(
                    DetectedConflict(
                        conflict_type="duplicate_therapy",
                        review_priority="moderate",
                        title=title,
                        clinical_summary=clin_summary,
                        patient_friendly_summary=pat_summary,
                        sources=[
                            {
                                "role_in_conflict": "prescribed_medication",
                                "document_id": doc1_id,
                                "entity_id": med1.get("id"),
                                "citation_text": f"Agent A: {name1} in {doc1_name}",
                            },
                            {
                                "role_in_conflict": "prescribed_medication",
                                "document_id": doc2_id,
                                "entity_id": med2.get("id"),
                                "citation_text": f"Agent B: {name2} in {doc2_name}",
                            },
                        ],
                        is_provisional=is_provisional,
                    )
                )

            # (B) Check Severe Drug-Drug Interactions
            for class_a, class_b, priority, rule_title, explanation, pat_phrase in DRUG_DRUG_INTERACTIONS:
                has_a_and_b = (class_a in classes1 and class_b in classes2) or (class_a in classes2 and class_b in classes1)
                if has_a_and_b:
                    title = f"{prov_tag}Drug Interaction: {name1.title()} and {name2.title()}"
                    clin_summary = (
                        f"{explanation} Involved medications: {name1} ('{doc1_name}') and {name2} ('{doc2_name}'). "
                        f"Interaction rule: {rule_title}. "
                        f"{'Provisional: Pending entity verification.' if is_provisional else ''}"
                    )
                    detected.append(
                        DetectedConflict(
                            conflict_type="drug_drug_interaction",
                            review_priority=priority,
                            title=title,
                            clinical_summary=clin_summary,
                            patient_friendly_summary=pat_phrase,
                            sources=[
                                {
                                    "role_in_conflict": "prescribed_medication",
                                    "document_id": doc1_id,
                                    "entity_id": med1.get("id"),
                                    "citation_text": f"Medication 1: {name1} in {doc1_name}",
                                },
                                {
                                    "role_in_conflict": "interacting_medication",
                                    "document_id": doc2_id,
                                    "entity_id": med2.get("id"),
                                    "citation_text": f"Medication 2: {name2} in {doc2_name}",
                                },
                            ],
                            is_provisional=is_provisional,
                        )
                    )

    # --------------------------------------------------------------------------
    # 3. CONTRADICTORY DIAGNOSTIC BASELINES
    # --------------------------------------------------------------------------
    for i in range(len(diagnoses)):
        diag1 = diagnoses[i]
        d1 = diag1.get("extracted_data") or {}
        cond1 = (d1.get("condition") or "").lower()
        if not cond1:
            continue
        doc1_id = diag1.get("document_id")
        doc1_name = docs_map.get(str(doc1_id), {}).get("file_name", "Clinical Record 1")
        ver1 = diag1.get("verification_status", "pending")

        for j in range(i + 1, len(diagnoses)):
            diag2 = diagnoses[j]
            d2 = diag2.get("extracted_data") or {}
            cond2 = (d2.get("condition") or "").lower()
            if not cond2:
                continue
            doc2_id = diag2.get("document_id")
            doc2_name = docs_map.get(str(doc2_id), {}).get("file_name", "Clinical Record 2")
            ver2 = diag2.get("verification_status", "pending")

            is_provisional = (ver1 == "pending" or ver2 == "pending")
            prov_tag = "[Provisional] " if is_provisional else ""

            for sub_a, sub_b, priority, rule_title, explanation, pat_phrase in DIAGNOSTIC_CONTRADICTIONS:
                match = (sub_a in cond1 and sub_b in cond2) or (sub_a in cond2 and sub_b in cond1)
                if match:
                    title = f"{prov_tag}{rule_title}"
                    clin_summary = (
                        f"{explanation} Discrepancy between '{cond1.title()}' in '{doc1_name}' "
                        f"and '{cond2.title()}' in '{doc2_name}'. "
                        f"{'Provisional: Pending entity verification.' if is_provisional else ''}"
                    )
                    detected.append(
                        DetectedConflict(
                            conflict_type="diagnostic_discrepancy",
                            review_priority=priority,
                            title=title,
                            clinical_summary=clin_summary,
                            patient_friendly_summary=pat_phrase,
                            sources=[
                                {
                                    "role_in_conflict": "conflicting_diagnosis",
                                    "document_id": doc1_id,
                                    "entity_id": diag1.get("id"),
                                    "citation_text": f"Diagnosis: {cond1.title()} in {doc1_name}",
                                },
                                {
                                    "role_in_conflict": "conflicting_diagnosis",
                                    "document_id": doc2_id,
                                    "entity_id": diag2.get("id"),
                                    "citation_text": f"Diagnosis: {cond2.title()} in {doc2_name}",
                                },
                            ],
                            is_provisional=is_provisional,
                        )
                    )

    return detected
