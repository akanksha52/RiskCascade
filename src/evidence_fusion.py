
"""Combine FinBERT, Qwen, and keyword results into an auditable risk signal."""

from typing import Any


SUPPORTED_EVENTS = {
    "Supply Disruption",
    "Cyberattack",
    "Regulatory Penalty",
    "Credit Deterioration",
}

def fuse_evidence(
    article: dict,
    finbert_result: dict | None,
    llm_result: dict | None,
    keyword_result: dict | None,
    known_entities: list[str],
    mapped_events: set[str] | None = None,
) -> dict[str, Any]:
    """Fuse model outputs without hiding disagreements or inventing evidence.

    This function does not calculate financial loss or automatically approve
    a risk event. It identifies whether a signal is sufficiently supported
    to be considered for human-reviewed stress analysis.
    """
    text = article.get("text", "")
    quality = article.get("evidence_quality", "unknown")
    reasons: list[str] = []

    finbert_result = finbert_result or {}
    llm_result = llm_result or {}
    keyword_result = keyword_result or {}

    llm_event = llm_result.get("event_type", "Other")
    keyword_event = keyword_result.get("event_type", "Other")

    if llm_event not in SUPPORTED_EVENTS:
        llm_event = "Other"

    if keyword_event not in SUPPORTED_EVENTS:
        keyword_event = "Other"

    quote = llm_result.get("evidence", "")
    quote_verified = bool(
        isinstance(quote, str) and quote.strip() and quote in text
    )

    if not quote_verified:
        reasons.append("No exact supporting quote verified in source text.")

    if quality != "full_text":
        reasons.append(
            f"Source quality is {quality}; substantive full text is unavailable."
        )

    company = llm_result.get("company")
    company_in_source = bool(
        isinstance(company, str)
        and company.strip()
        and company.casefold() in text.casefold()
    )

    graph_entity = None
    if company_in_source:
        graph_entity = next(
            (
                entity for entity in known_entities
                if entity.casefold() == company.casefold()
            ),
            None,
        )

    if not company_in_source:
        reasons.append("No verified company name was extracted from the source.")
    elif graph_entity is None:
        reasons.append("Company does not exactly match an exposure-graph entity.")

    disagreement = (
        llm_event != "Other"
        and keyword_event != "Other"
        and llm_event != keyword_event
    )

    if disagreement:
        reasons.append(
            f"Event classifiers disagree: Qwen={llm_event}; "
            f"keywords={keyword_event}."
        )

    if llm_event == "Other" and keyword_event == "Other":
        reasons.append("Neither event classifier identified a supported event.")

    event_type = (
        llm_event
        if llm_event != "Other" and not disagreement
        else keyword_event
        if keyword_event != "Other" and not disagreement
        else "Other"
    )

    if event_type == "Other":
        reasons.append("No unambiguous supported event is available.")

    mapped_events = mapped_events or set()
    event_mapped = event_type in mapped_events

    if event_type != "Other" and not event_mapped:
        reasons.append("Event has no configured risk-factor mapping.")

    # A model's self-reported confidence is not a calibrated probability.
    try:
        confidence = float(llm_result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    if not 0.0 <= confidence <= 1.0:
        confidence = 0.0
        reasons.append("LLM confidence value was invalid.")

    # This is eligibility for further human review, not automatic approval.
    eligible_for_review = all([
        quote_verified,
        quality == "full_text",
        company_in_source,
        graph_entity is not None,
        event_type != "Other",
        not disagreement,
        event_mapped,
    ])

    decision = (
        "eligible_for_stress_review"
        if eligible_for_review
        else "needs_review"
    )

    if not reasons:
        reasons.append("Evidence checks passed; human approval is still required.")

    return {
        "article_id": article.get("article_id"),
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "source_url": article.get("url", ""),
        "evidence_quality": quality,
        "company": company if company_in_source else None,
        "graph_entity": graph_entity,
        "llm_event": llm_event,
        "keyword_event": keyword_event,
        "event_type": event_type,
        "event_disagreement": disagreement,
        "evidence_quote": quote if quote_verified else "",
        "evidence_verified": quote_verified,
        "finbert_sentiment": finbert_result.get("sentiment"),
        "finbert_label": finbert_result.get("label"),
        "keyword_sentiment": keyword_result.get("sentiment"),
        "impact_score": keyword_result.get("impact"),
        "llm_confidence": confidence,
        "event_mapped": event_mapped,
        "decision": decision,
        "eligible_for_stress_review": eligible_for_review,
        "reasons": reasons,
    }
