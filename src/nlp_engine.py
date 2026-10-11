
import re

EVENT_RULES = {
    "Supply Disruption": [
        "production halt", "factory fire", "supply disruption",
        "shipment delay", "production shutdown", "shortage",
        "plant shutdown", "supplier disruption",
    ],
    "Cyberattack": [
        "cyberattack", "ransomware", "data breach",
        "network intrusion", "malware",
    ],
    "Regulatory Penalty": [
        "regulatory penalty", "fined", "regulatory investigation",
        "sanctioned", "compliance violation",
    ],
    "Credit Deterioration": [
        "debt downgrade", "default", "missed payment",
        "liquidity crisis", "debt restructuring",
    ],
}

NEGATIVE_TERMS = {
    "fire", "halt", "shutdown", "disruption", "delay",
    "ransomware", "breach", "default", "downgrade",
    "penalty", "crisis", "loss", "shortage", "fraud",
    "recall", "sanctions", "attack", "missed payment",
}

POSITIVE_TERMS = {
    "recovered", "resumed", "growth", "profit increase",
    "successful", "resolved", "record revenue", "expansion",
}


def analyze_text(text: str, known_entities=None) -> dict:
    """Analyze text using transparent keyword-based baseline rules."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input text must be a non-empty string.")

    normalized = re.sub(r"\s+", " ", text.lower()).strip()

    
    detected_event = "Other"
    matched_terms = []

    # Prefer the most specific/high-risk matching category.
    priority = [
        "Cyberattack",
        "Regulatory Penalty",
        "Credit Deterioration",
        "Supply Disruption",
    ]

    for event_type in priority:
        keywords = EVENT_RULES[event_type]
        matches = [word for word in keywords if word in normalized]
        if matches:
            detected_event = event_type
            matched_terms = matches
            break
        
        
    negative_count = sum(term in normalized for term in NEGATIVE_TERMS)
    positive_count = sum(term in normalized for term in POSITIVE_TERMS)

    # Transparent heuristic, not a trained sentiment model.
    sentiment = (positive_count - negative_count) / max(
        positive_count + negative_count, 1
    )
    sentiment = max(-1.0, min(1.0, sentiment))

    # A baseline heuristic, not a calibrated financial impact prediction.
    impact = min(
        10,
        1 + 2 * negative_count + len(matched_terms)
    )

    entity = None
    if known_entities:
        matches = [
            name for name in known_entities
            if name.lower() in normalized
        ]
        if matches:
            entity = max(matches, key=len)

    return {
        "entity": entity,
        "event_type": detected_event,
        "sentiment": float(sentiment),
        "impact": int(impact),
        "evidence": matched_terms,
        "analysis_method": "keyword_baseline",
        "confidence": None,
    }
