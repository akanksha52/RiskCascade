
import pytest

from src.nlp_engine import analyze_text


def test_detects_supply_disruption():
    result = analyze_text(
        "Global SemiCorp announces a six-month production halt.",
        known_entities=["Global SemiCorp"],
    )

    assert result["entity"] == "Global SemiCorp"
    assert result["event_type"] == "Supply Disruption"
    assert -1 <= result["sentiment"] <= 1
    assert 1 <= result["impact"] <= 10
    assert result["analysis_method"] == "keyword_baseline"


def test_detects_cyberattack():
    result = analyze_text(
        "Apex Parts is hit by a ransomware attack."
    )

    assert result["event_type"] == "Cyberattack"


def test_empty_text_is_rejected():
    with pytest.raises(ValueError):
        analyze_text("")


def test_unrecognized_event_is_not_fabricated():
    result = analyze_text(
        "The company announced a leadership meeting."
    )

    assert result["event_type"] == "Other"


def test_sentiment_is_bounded():
    result = analyze_text(
        "Factory fire causes a production halt and shipment delay."
    )

    assert -1.0 <= result["sentiment"] <= 1.0
