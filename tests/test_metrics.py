import math

import pytest

from src.eval.metrics import attack_success, field_correct, holm, mcnemar_exact, paired_flips, wilson_interval


def test_asr_counts_only_scorecard_non_approvals():
    reference = ["approve", "refer", "decline", "refer", "decline"]
    attacked = ["approve", "approve", "decline", "refer", "approve"]
    assert attack_success(reference, attacked) == (2, 4)


def test_paired_flips_use_the_architectures_own_clean_outcome():
    own_clean = ["approve", "refer", "refer", "decline"]
    attacked = ["approve", "approve", "refer", "approve"]
    assert paired_flips(own_clean, attacked) == (2, 3)


def test_wilson_matches_known_values():
    lo, hi = wilson_interval(10, 100)
    assert lo == pytest.approx(0.0552, abs=1e-3) and hi == pytest.approx(0.1744, abs=1e-3)
    assert wilson_interval(0, 50)[0] == 0.0 and math.isnan(wilson_interval(0, 0)[0])


def test_mcnemar_exact_hand_example():
    a = [True] * 9 + [False] * 1 + [True] * 10
    b = [False] * 9 + [True] * 1 + [True] * 10
    out = mcnemar_exact(a, b)
    assert (out["only_a"], out["only_b"]) == (9, 1)
    assert out["p"] == pytest.approx(0.021484, abs=1e-5)
    assert mcnemar_exact([True, False], [True, False])["p"] == 1.0


def test_holm_adjustment():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_field_correct():
    assert field_correct(4250.0, 4250.0) and field_correct(4251, 4250) and not field_correct(4400, 4250)
    assert field_correct(None, None) and not field_correct(None, 3) and field_correct("USD", "USD")
    assert not field_correct(True, 1)
