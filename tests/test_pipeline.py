import pytest

from src.pipeline import RiskCascadeEngine


def test_supplier_shock_propagates_in_correct_order():
    engine = RiskCascadeEngine()

    result = engine.process_event({
        "entity": "Global SemiCorp",
        "event_type": "Supply Disruption",
        "sentiment": -0.8,
        "impact": 9,
        "evidence": [],
    })

    stresses = result["stresses"]

    # Initial shock: 0.04 * 0.9 * 0.9 * 0.75 = 0.0243
    assert stresses["Global SemiCorp"] == pytest.approx(0.0243)

    # Each downstream edge applies its dependency weight and attenuation.
    assert stresses["Tier-1 Auto Controls"] == pytest.approx(0.00972)
    assert stresses["MegaMotors Inc"] == pytest.approx(0.002916)


def test_expected_loss_uses_borrower_pd():
    engine = RiskCascadeEngine()

    result = engine.process_event({
        "entity": "Global SemiCorp",
        "event_type": "Supply Disruption",
        "sentiment": -0.8,
        "impact": 9,
        "evidence": [],
    })

    # Baseline EL includes both synthetic bank exposures.
    assert result["baseline_el"] == pytest.approx(405_000)

    # MegaMotors stressed PD = 1.8% + 0.2916% = 2.0916%
    # Facility A stressed EL = 2.0916% * 45% * ₹25,000,000
    # Facility B remains at baseline EL = ₹202,500.
    assert result["stressed_el"] == pytest.approx(437_805)
    assert result["delta_el"] == pytest.approx(32_805)


def test_unknown_entity_is_rejected():
    engine = RiskCascadeEngine()

    with pytest.raises(ValueError, match="not found"):
        engine.process_event({
            "entity": "Unknown Company",
            "event_type": "Supply Disruption",
        })


def test_unknown_event_type_is_rejected():
    engine = RiskCascadeEngine()

    with pytest.raises(ValueError, match="No FactorLens mapping"):
        engine.process_event({
            "entity": "Global SemiCorp",
            "event_type": "Unknown Event",
        })


def test_cyberattack_only_affects_its_own_exposure_chain():
    engine = RiskCascadeEngine()

    result = engine.process_event({
        "entity": "Apex Parts",
        "event_type": "Cyberattack",
        "sentiment": -0.8,
        "impact": 7,
        "evidence": [],
    })

    # Initial shock: 0.02 * 0.7 * 0.9 * 0.75 = 0.00945
    assert result["stresses"]["Apex Parts"] == pytest.approx(0.00945)

    # Auto Systems Integrator receives 0.00945 * 0.75 * 0.5.
    assert result["stresses"]["Auto Systems Integrator"] == pytest.approx(
        0.00354375
    )

    exposures = {
        item["exposure"]: item
        for item in result["exposures"]
    }

    # Facility A is isolated from the Apex Parts chain.
    assert exposures["Syndicated Loan Facility A"]["delta_el"] == pytest.approx(0)

    # Facility B's borrower PD increases by 0.354375 percentage points.
    assert exposures["Syndicated Loan Facility B"]["delta_el"] == pytest.approx(
        23_920.3125
    )

    assert result["delta_el"] == pytest.approx(23_920.3125)