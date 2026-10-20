"""Deterministic Clinical Knowledge Base for CareBridge AI.

Defines validated dictionaries for:
- Therapeutic drug classes
- Allergy and cross-reactivity matrices
- High-risk drug-drug interaction pairs
- Incompatible/contradictory diagnostic classifications

Advisory Clinical Decision Support: strictly explainable rules, no reliance on black-box LLMs.
"""

from typing import Dict, List, Set, Tuple, Optional


DRUG_CLASSES: Dict[str, Set[str]] = {
    "ACE_INHIBITOR": {
        "lisinopril", "enalapril", "ramipril", "captopril", "benazepril",
        "fosinopril", "quinapril", "perindopril", "trandolapril"
    },
    "ARB": {
        "losartan", "valsartan", "irbesartan", "candesartan", "telmisartan",
        "olmesartan", "eprosartan", "azilsartan"
    },
    "BETA_BLOCKER": {
        "metoprolol", "atenolol", "carvedilol", "bisoprolol", "propranolol",
        "labetalol", "nebivolol", "sotalol", "timolol"
    },
    "STATIN": {
        "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin",
        "fluvastatin", "pitavastatin", "lipitor", "crestor", "zocor"
    },
    "NSAID": {
        "ibuprofen", "naproxen", "celecoxib", "diclofenac", "meloxicam",
        "ketorolac", "indomethacin", "etodolac", "nabumetone", "piroxicam",
        "advil", "motrin", "aleve", "voltaren", "celebrex"
    },
    "ANTICOAGULANT": {
        "warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban",
        "heparin", "enoxaparin", "fondaparinux", "coumadin", "eliquis", "xarelto", "pradaxa", "lovenox"
    },
    "ANTIPLATELET": {
        "aspirin", "clopidogrel", "ticagrelor", "prasugrel", "dipyridamole",
        "plavix", "brilinta", "effient"
    },
    "BENZODIAZEPINE": {
        "alprazolam", "lorazepam", "diazepam", "clonazepam", "temazepam",
        "midazolam", "chlordiazepoxide", "xanax", "ativan", "valium", "klonopin"
    },
    "OPIOID": {
        "oxycodone", "hydrocodone", "morphine", "fentanyl", "tramadol",
        "codeine", "hydromorphone", "methadone", "buprenorphine", "oxymorphone",
        "percocet", "vicodin", "norco", "dilaudid", "duragesic", "ultram"
    },
    "SSRI": {
        "sertraline", "fluoxetine", "escitalopram", "citalopram", "paroxetine",
        "fluvoxamine", "zoloft", "prozac", "lexapro", "celexa", "paxil"
    },
    "SNRI": {
        "duloxetine", "venlafaxine", "desvenlafaxine", "milnacipran", "levomilnacipran",
        "cymbalta", "effexor", "pristiq"
    },
    "MACROLIDE": {
        "azithromycin", "clarithromycin", "erythromycin", "zithromax", "biaxin"
    },
    "FLUOROQUINOLONE": {
        "ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin", "cipro", "levaquin", "avelox"
    },
    "PENICILLIN": {
        "penicillin", "penicillin v", "penicillin g", "amoxicillin", "ampicillin",
        "piperacillin", "amoxicillin-clavulanate", "augmentin", "zosyn", "unasyn", "oxacillin", "nafcillin"
    },
    "CEPHALOSPORIN": {
        "cephalexin", "cefuroxime", "ceftriaxone", "cefazolin", "cefdinir",
        "cefepime", "cefotaxime", "cefaclor", "keflex", "rocephin", "ancef", "omnicef"
    },
    "SULFONAMIDE": {
        "sulfamethoxazole", "trimethoprim-sulfamethoxazole", "bactrim", "septra",
        "sulfasalazine", "sulfadiazine"
    },
    "PPI": {
        "omeprazole", "pantoprazole", "esomeprazole", "lansoprazole", "rabeprazole",
        "prilosec", "protonix", "nexium", "prevacid"
    }
}


def normalize_drug_name(name: str) -> str:
    """Sanitize and lowercase a drug or allergen name."""
    if not name:
        return ""
    clean = name.lower().strip()
    # Remove common dosage/form tails like ' 20mg', ' oral tablet', etc.
    for token in ["oral", "tablet", "capsule", "injection", "solution", "mg", "mcg", "g", "daily", "bid", "tid", "qid"]:
        clean = clean.replace(f" {token}", "")
    return clean.strip(" ,.-/")


def get_drug_classes(drug_name: str) -> List[str]:
    """Find all therapeutic classes matching the normalized drug name."""
    norm = normalize_drug_name(drug_name)
    classes = []
    for cls_name, members in DRUG_CLASSES.items():
        for member in members:
            if member in norm or norm in member:
                classes.append(cls_name)
                break
    return classes


# Allergy Cross-Reactivity Matrix
# (Allergen Term) -> List of (Target Pattern/Class, Review Priority, Clinical Context)
ALLERGY_CROSS_REACTIVITY: Dict[str, List[Tuple[str, str, str]]] = {
    "penicillin": [
        (
            "PENICILLIN",
            "high",
            "Documented Penicillin allergy: direct beta-lactam class member prescribed. High risk of immediate type I hypersensitivity or anaphylaxis."
        ),
        (
            "CEPHALOSPORIN",
            "moderate",
            "Documented Penicillin allergy: cephalosporin prescribed. Approx 2-5% cross-reactivity risk due to shared beta-lactam core structure."
        ),
    ],
    "amoxicillin": [
        (
            "PENICILLIN",
            "high",
            "Documented Amoxicillin allergy: beta-lactam penicillin class prescribed. High risk of allergic reaction."
        ),
        (
            "CEPHALOSPORIN",
            "moderate",
            "Documented Amoxicillin allergy: cephalosporin prescribed. Beta-lactam cross-reactivity warning."
        ),
    ],
    "sulfa": [
        (
            "SULFONAMIDE",
            "high",
            "Documented Sulfa allergy: sulfonamide antimicrobial prescribed. Risk of severe cutaneous adverse reactions (SCARs/Stevens-Johnson syndrome)."
        ),
    ],
    "sulfonamide": [
        (
            "SULFONAMIDE",
            "high",
            "Documented Sulfonamide allergy: sulfonamide agent prescribed."
        ),
    ],
    "aspirin": [
        (
            "NSAID",
            "high",
            "Documented Aspirin sensitivity/allergy: NSAID prescribed. Risk of cross-reactive bronchospasm (aspirin-exacerbated respiratory disease) or anaphylactoid reaction."
        ),
        (
            "ANTIPLATELET",
            "high",
            "Documented Aspirin allergy: aspirin or salicylic antiplatelet prescribed."
        ),
    ],
    "ibuprofen": [
        (
            "NSAID",
            "high",
            "Documented NSAID (Ibuprofen) allergy: non-steroidal anti-inflammatory prescribed."
        ),
    ],
    "codeine": [
        (
            "OPIOID",
            "high",
            "Documented Codeine/Opioid allergy: opioid analgesic prescribed. High risk of systemic adverse reaction."
        ),
    ],
    "morphine": [
        (
            "OPIOID",
            "high",
            "Documented Morphine/Opioid allergy: opioid analgesic prescribed."
        ),
    ]
}


# Drug-Drug Interaction Rules
# (Class A, Class B) -> (Review Priority, Title, Clinical Explanation, Patient Phrasing)
DRUG_DRUG_INTERACTIONS = [
    (
        "ANTICOAGULANT",
        "NSAID",
        "high",
        "Concurrent Anticoagulant and NSAID Therapy",
        "Concomitant anticoagulant and NSAID therapy synergistically increases gastrointestinal mucosal ulceration and inhibits platelet aggregation, drastically elevating severe bleeding risk.",
        "Your care team is reviewing your pain medications alongside your blood thinner to ensure optimal safety and minimize stomach bleeding risks."
    ),
    (
        "ACE_INHIBITOR",
        "ARB",
        "high",
        "Dual Renin-Angiotensin System Blockade (ACE-I + ARB)",
        "Dual RAAS blockade combining an ACE inhibitor with an ARB provides no additive cardiovascular benefit and significantly increases risks of severe hyperkalemia, acute renal failure, and syncope.",
        "Your doctor is reviewing two blood pressure medicines from closely related classes to confirm the ideal single medication for your regimen."
    ),
    (
        "BENZODIAZEPINE",
        "OPIOID",
        "high",
        "Concomitant Benzodiazepine and Opioid Therapy",
        "FDA Black Box Warning: Concurrent administration of opioids and benzodiazepines increases the risk of severe respiratory depression, profound sedation, coma, and fatal overdose.",
        "Your doctor is carefully reviewing your sedative and pain medications together to monitor for excessive drowsiness and maintain your safety."
    ),
    (
        "ANTICOAGULANT",
        "ANTIPLATELET",
        "high",
        "Dual Antithrombotic Therapy (Anticoagulant + Antiplatelet)",
        "Combination of full-dose anticoagulant with antiplatelet therapy substantially elevates major bleeding risk. Requires documented clinical indication (e.g. recent ACS or stent).",
        "Your care team is evaluating your blood thinner and aspirin/antiplatelet combination to protect your heart while preventing unwanted bleeding."
    ),
    (
        "STATIN",
        "MACROLIDE",
        "moderate",
        "Statin and Macrolide Interaction (CYP3A4 Inhibition)",
        "Macrolide antibiotics (erythromycin, clarithromycin) strongly inhibit CYP3A4, causing significant accumulation of CYP3A4-metabolized statins and increasing rhabdomyolysis risk.",
        "Your doctor is checking your cholesterol medication while you take an antibiotic to prevent temporary muscle stiffness."
    ),
    (
        "SSRI",
        "SNRI",
        "high",
        "Dual Serotonergic Agent Duplication (SSRI + SNRI)",
        "Concomitant use of multiple full-dose serotonergic antidepressants increases risk of Serotonin Syndrome and excessive CNS activation without demonstrated synergistic efficacy.",
        "Your care team is confirming the specific mood and nerve medication plan chosen for your treatment."
    )
]


# Diagnostic Incompatibility Rules
# (Diagnosis Substring A, Diagnosis Substring B) -> (Review Priority, Title, Clinical Explanation, Patient Phrasing)
DIAGNOSTIC_CONTRADICTIONS = [
    (
        "type 1 diabetes",
        "type 2 diabetes",
        "moderate",
        "Contradictory Diabetes Classifications (Type 1 vs Type 2)",
        "Encounter records show divergent classifications between Type 1 and Type 2 Diabetes Mellitus. Requires clarification of etiology, islet autoantibody status, and C-peptide levels.",
        "Your doctor is verifying your past medical records to harmonize the exact diabetes classification documented by outside specialists."
    ),
    (
        "asthma",
        "copd",
        "low",
        "Overlapping Obstructive Airway Diagnoses (Asthma vs COPD)",
        "Records indicate overlapping declarations of Bronchial Asthma and Chronic Obstructive Pulmonary Disease (COPD). Consider Asthma-COPD Overlap Syndrome (ACOS) evaluation.",
        "Your care team is reviewing your respiratory history to ensure tailored inhaler treatments."
    ),
    (
        "hypertension",
        "chronic hypotension",
        "moderate",
        "Contradictory Blood Pressure Baseline Classifications",
        "Records document conflicting long-term vascular states (Essential Hypertension vs Chronic Hypotension). Review active anti-hypertensive titration.",
        "Your doctor is evaluating your blood pressure history to verify current target readings."
    )
]
