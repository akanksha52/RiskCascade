"""Local, evidence-grounded risk extraction using Ollama."""
import json
import re

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"

ALLOWED_EVENTS = {
    "Supply Disruption",
    "Cyberattack",
    "Regulatory Penalty",
    "Credit Deterioration",
    "Other",
}


def analyze_risk_with_llm(text: str) -> dict:
    """Extract a risk event using only evidence contained in the supplied text."""
    if not text or not text.strip():
        raise ValueError("Article text cannot be empty.")

    prompt = f"""
You are a cautious financial risk analyst.
Analyze only the text between <article> and </article>.
Do not use outside knowledge or invent missing information.

Return one JSON object with exactly these fields:
{{
  "company": string or null,
  "event_type": one of [
    "Supply Disruption", "Cyberattack",
    "Regulatory Penalty", "Credit Deterioration", "Other"
  ],
  "risk_event": string,
  "evidence": string,
  "confidence": number from 0 to 1
}}

Rules:
- company must be the exact company name explicitly present in the text.
- If no company name is explicitly present, use null.
- evidence must be a verbatim, contiguous quote from the supplied text.
- If no supporting evidence exists, use an empty string and confidence 0.
- Do not treat generic phrases such as "the company" as company names.
- Do not infer a company from outside knowledge.
- Return JSON only. No markdown or commentary.

<article>
{text[:1500]}
</article>
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract financial risk signals. "
                        "Never invent entities or evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=180,
    )
    response.raise_for_status()

    content = response.json()["message"]["content"]
    result = json.loads(content)

    required = {
        "company",
        "event_type",
        "risk_event",
        "evidence",
        "confidence",
    }
    if not isinstance(result, dict) or not required.issubset(result):
        raise ValueError("LLM output does not match the required schema.")

    company = result["company"]
    if company is not None:
        if not isinstance(company, str) or not company.strip():
            company = None
        elif company.casefold() not in text.casefold():
            company = None

    event_type = result["event_type"]
    if event_type not in ALLOWED_EVENTS:
        event_type = "Other"

    evidence = result["evidence"]
    if not isinstance(evidence, str) or evidence not in text:
        evidence = ""

    confidence = result["confidence"]
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))
    if not evidence:
        confidence = 0.0

    risk_event = result["risk_event"]
    if not isinstance(risk_event, str):
        risk_event = "Unspecified risk event"

    return {
        "company": company,
        "event_type": event_type,
        "risk_event": risk_event,
        "evidence": evidence,
        "confidence": confidence,
        "model": MODEL_NAME,
        "method": "Local Ollama LLM",
    }
