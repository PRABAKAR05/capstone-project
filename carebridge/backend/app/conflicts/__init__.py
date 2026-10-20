"""Conflicts module for CareBridge AI."""
from app.conflicts.detector import detect_conflicts_from_entities, DetectedConflict
from app.conflicts.knowledge_base import (
    DRUG_CLASSES,
    ALLERGY_CROSS_REACTIVITY,
    DRUG_DRUG_INTERACTIONS,
    DIAGNOSTIC_CONTRADICTIONS,
    normalize_drug_name,
    get_drug_classes,
)
from app.conflicts.groq_reconciler import reconcile_conflict_narrative_synthetic

__all__ = [
    "detect_conflicts_from_entities",
    "DetectedConflict",
    "DRUG_CLASSES",
    "ALLERGY_CROSS_REACTIVITY",
    "DRUG_DRUG_INTERACTIONS",
    "DIAGNOSTIC_CONTRADICTIONS",
    "normalize_drug_name",
    "get_drug_classes",
    "reconcile_conflict_narrative_synthetic",
]
