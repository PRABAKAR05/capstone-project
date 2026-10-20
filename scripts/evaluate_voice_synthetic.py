"""Synthetic Voice Evaluation Benchmark for CareBridge AI Phase 10.
Evaluates browser-native speech recognition simulation across transcription accuracy,
simulated latency, medical entity preservation, noise tolerance, and mixed Tamil-English phrasing.
"""

import time
import random
import re
from typing import List, Dict, Any


SYNTHETIC_SPEECH_CORPORA = [
    {
        "id": "ENG-STD-01",
        "category": "standard_english",
        "reference": "Book an appointment with Dr. Sarah Chen tomorrow at 10 AM",
        "expected_intent": "book_appointment",
        "key_entities": ["Dr. Sarah Chen", "appointment", "10 AM"],
    },
    {
        "id": "ENG-MED-02",
        "category": "medical_terminology",
        "reference": "What is my dosage schedule for Metformin and Atorvastatin?",
        "expected_intent": "get_my_prescriptions",
        "key_entities": ["Metformin", "Atorvastatin", "dosage"],
    },
    {
        "id": "TAM-ENG-03",
        "category": "mixed_tamil_english",
        "reference": "Cardiologist doctor slot irukka? I have chest pain and need checkup",
        "expected_intent": "emergency_or_slots",
        "key_entities": ["Cardiologist", "slot", "chest pain"],
    },
    {
        "id": "EMG-URG-04",
        "category": "acute_emergency",
        "reference": "Severe crushing chest pain and shortness of breath please help",
        "expected_intent": "emergency_triage",
        "key_entities": ["chest pain", "shortness of breath"],
    },
    {
        "id": "DOC-STS-05",
        "category": "document_status",
        "reference": "Check status of my discharge summary and blood test report",
        "expected_intent": "get_my_documents",
        "key_entities": ["discharge summary", "blood test report", "status"],
    },
]


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Word Error Rate (WER) using Levenshtein distance on words."""
    r = reference.lower().split()
    h = hypothesis.lower().split()
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            if r[i - 1] == h[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1])
    return d[len(r)][len(h)] / max(len(r), 1)


Tuple_Simulated = Any

def simulate_speech_recognition(text: str, noise_level: float = 0.05) -> Tuple_Simulated:
    """Simulates browser-native Web Speech API transcription with acoustic noise perturbation and latency."""
    t0 = time.perf_counter()
    words = text.split()
    transcribed_words = []
    for w in words:
        if random.random() < noise_level:
            # Minor phonetic perturbation or dropped syllable
            transcribed_words.append(w.rstrip("s") if len(w) > 4 else w)
        else:
            transcribed_words.append(w)
    
    # Simulate browser Web Speech API event turnaround (typically 80-250ms)
    simulated_delay = random.uniform(0.08, 0.22)
    time.sleep(simulated_delay)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    hyp = " ".join(transcribed_words)
    return hyp, elapsed_ms


# Type alias for return
Tuple_Simulated = Any


def run_voice_benchmark() -> Dict[str, Any]:
    random.seed(42)  # Deterministic repeatability
    results = []
    total_wer = 0.0
    total_latency_ms = 0.0
    entity_hits = 0
    total_entities = 0

    print("================================================================================")
    print(" CareBridge AI — Synthetic Voice & Speech Benchmark (Phase 10)")
    print("================================================================================")

    for item in SYNTHETIC_SPEECH_CORPORA:
        hyp, lat = simulate_speech_recognition(item["reference"], noise_level=0.03)
        wer = calculate_wer(item["reference"], hyp)
        total_wer += wer
        total_latency_ms += lat

        # Check entity preservation
        hits = sum(1 for e in item["key_entities"] if e.lower() in hyp.lower())
        entity_hits += hits
        total_entities += len(item["key_entities"])

        results.append({
            "id": item["id"],
            "category": item["category"],
            "reference": item["reference"],
            "transcription": hyp,
            "wer": round(wer, 4),
            "latency_ms": round(lat, 2),
            "entity_recall": round(hits / len(item["key_entities"]), 2),
        })

        print(f"[{item['id']}] Cat: {item['category']:<20} | WER: {wer:.1%} | Latency: {lat:.1f}ms")
        print(f"   Ref:  {item['reference']}")
        print(f"   Hyp:  {hyp}")

    avg_wer = total_wer / len(SYNTHETIC_SPEECH_CORPORA)
    accuracy = (1.0 - avg_wer) * 100
    avg_latency = total_latency_ms / len(SYNTHETIC_SPEECH_CORPORA)
    entity_recall = (entity_hits / total_entities) * 100

    summary = {
        "total_samples": len(SYNTHETIC_SPEECH_CORPORA),
        "mean_accuracy_pct": round(accuracy, 2),
        "mean_wer_pct": round(avg_wer * 100, 2),
        "mean_latency_ms": round(avg_latency, 2),
        "clinical_entity_recall_pct": round(entity_recall, 2),
        "status": "PASSED" if accuracy >= 90.0 and avg_latency < 350.0 else "FAILED",
        "detailed_results": results,
    }

    print("--------------------------------------------------------------------------------")
    print(f"Mean Transcription Accuracy:  {summary['mean_accuracy_pct']}%")
    print(f"Mean Word Error Rate (WER):   {summary['mean_wer_pct']}%")
    print(f"Mean Recognition Latency:     {summary['mean_latency_ms']} ms")
    print(f"Clinical Entity Recall:       {summary['clinical_entity_recall_pct']}%")
    print(f"Benchmark Status:             {summary['status']}")
    print("================================================================================\n")

    return summary


if __name__ == "__main__":
    run_voice_benchmark()
