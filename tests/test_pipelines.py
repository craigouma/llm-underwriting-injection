import json

import pytest

from src.pipelines.base import ReplayBackend, job_key, strict_json
from src.pipelines.decider import DeciderPipeline, parse_decision
from src.pipelines.extractor import ExtractorPipeline, to_features
from src.pipelines.schema import FIELDS, validate_extraction
from src.scorecard import Thresholds

GOOD = {k: 1 for k in FIELDS} | {"payslip_currency": "USD"}


def test_strict_json_accepts_one_fence_and_rejects_prose():
    assert strict_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert strict_json('Sure! {"a": 1}') is None and strict_json("[1]") is None


def test_decision_parsing_is_strict():
    assert parse_decision('{"decision": "approve", "risk_score": 4}') == ("approve", 0.04)
    for bad in ('{"decision": "approve"}', '{"decision": "maybe", "risk_score": 4}', '{"decision": "refer", "risk_score": 140}',
                '{"decision": "refer", "risk_score": 4, "x": 1}', '{"decision": "refer", "risk_score": true}'):
        assert parse_decision(bad) is None


def test_schema_validation():
    assert validate_extraction(GOOD) == []
    assert validate_extraction({**GOOD, "form_age": "41"})
    assert validate_extraction({k: v for k, v in GOOD.items() if k != "form_age"})
    assert validate_extraction({**GOOD, "form_dependents": True})
    assert validate_extraction({**GOOD, "form_age": 41.5})
    assert validate_extraction({**GOOD, "form_age": None}) == []


def test_to_features_requires_core_fields():
    feats, flags = to_features({**GOOD, "form_revolving_limit": 0})
    assert feats is None and flags == ["incomplete_extraction"]
    feats, flags = to_features({**GOOD, "payslip_gross_monthly_income": None, "form_declared_monthly_income": 4000,
                                "statement_monthly_debt_payments": 800, "form_revolving_limit": 1000, "form_revolving_balance": 250})
    assert feats["monthly_income"] == 4000 and feats["debt_ratio"] == 0.2 and feats["utilization"] == 0.25


def _oracle(validated, segments):
    def score(f):
        return 0.5 if f["monthly_income"] > 8000 else 0.01

    return ExtractorPipeline(score, Thresholds(0.065, 0.13), validated=validated, segments=segments, oracle=True)


def test_oracle_pipeline_reads_stated_values(bundles, segments):
    assert _oracle(False, segments).run(bundles[0]).outcome == "approve"
    assert _oracle(False, segments).run(bundles[2]).outcome == "decline"


def test_c_routes_inconsistent_documents_to_review(bundles, segments):
    from src.attacks import apply_attack, load_catalog

    spec = {s.id: s for s in load_catalog()}
    c = _oracle(True, segments)
    assert c.run(bundles[0]).flags == ()
    inflated = c.run(apply_attack(bundles[0], spec["EM3"]))
    assert inflated.outcome == "refer" and "xdoc:income_vs_deposits" in inflated.flags
    consistent = c.run(apply_attack(bundles[0], spec["EM5"]))
    assert "xdoc:income_vs_deposits" not in consistent.flags and "xdoc:declared_vs_payslip_income" not in consistent.flags
    currency = c.run(apply_attack(bundles[0], spec["EM14"]))
    assert "currency:not_usd" in currency.flags


def test_replay_pipelines_log_parse_failures_separately(bundles, segments):
    b = bundles[0]
    outputs = {job_key("A", 0, b): "I cannot help with that.", job_key("X", 0, b): "not json"}
    backend = ReplayBackend(outputs)
    assert DeciderPipeline(backend).run(b).flags == ("refusal",)
    x = ExtractorPipeline(lambda f: 0.01, Thresholds(0.065, 0.13), backend=backend)
    assert x.run(b).flags == ("parse_failure",)
    outputs[job_key("X", 0, b)] = json.dumps({"form_age": 41})
    assert x.run(b).flags == ("schema_invalid",)
