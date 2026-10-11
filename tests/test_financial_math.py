
import pytest


def test_expected_loss_formula():
    pd = 0.02
    lgd = 0.45
    ead = 25_000_000

    expected_loss = pd * lgd * ead

    assert expected_loss == pytest.approx(225_000)


def test_incremental_expected_loss():
    baseline_pd = 0.02
    stressed_pd = 0.025
    lgd = 0.45
    ead = 25_000_000

    baseline_el = baseline_pd * lgd * ead
    stressed_el = stressed_pd * lgd * ead

    assert baseline_el == pytest.approx(225_000)
    assert stressed_el == pytest.approx(281_250)
    assert stressed_el - baseline_el == pytest.approx(56_250)
