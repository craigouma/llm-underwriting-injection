"""Architectures B and C: the LLM only extracts fields. A scorecard decides. C adds code-level checks."""
from __future__ import annotations

from typing import Callable, Mapping

from src.documents import Bundle
from src.pipelines.base import REFER, Backend, Decision, job_key, strict_json
from src.pipelines.checks import run_checks
from src.pipelines.schema import validate_extraction
from src.scorecard import Thresholds
from src.segments import Segments

ScoreFn = Callable[[Mapping[str, float]], float]


def to_features(fields: Mapping) -> tuple[dict[str, float] | None, list[str]]:
    """Deterministic mapping from extracted fields to scorecard features. The payslip is the primary income source."""
    income = fields.get("payslip_gross_monthly_income")
    if income is None:
        income = fields.get("form_declared_monthly_income")
    debt = fields.get("statement_monthly_debt_payments")
    if debt is None:
        debt = fields.get("form_declared_monthly_debt")
    limit, balance = fields.get("form_revolving_limit"), fields.get("form_revolving_balance")
    needed = [fields.get(k) for k in ("form_age", "form_dependents", "form_open_credit_lines", "form_real_estate_loans",
                                      "form_late_30_59", "form_late_60_89", "form_late_90_plus")]
    if None in (income, debt, limit, balance, *needed) or income <= 0 or limit <= 0:
        return None, ["incomplete_extraction"]
    return {"utilization": balance / limit, "age": fields["form_age"], "late_30_59": fields["form_late_30_59"],
            "debt_ratio": debt / income, "monthly_income": income, "open_lines": fields["form_open_credit_lines"],
            "late_90": fields["form_late_90_plus"], "real_estate_loans": fields["form_real_estate_loans"],
            "late_60_89": fields["form_late_60_89"], "dependents": fields["form_dependents"]}, []


class ExtractorPipeline:
    """`validated=True` is architecture C. `backend=None` with `oracle=True` reads the stated values directly,
    which gives the reference arm that isolates what the LLM adds."""

    def __init__(self, score_fn: ScoreFn, thresholds: Thresholds, backend: Backend | None = None, validated: bool = False,
                 segments: Segments | None = None, phrasing: int = 0, oracle: bool = False):
        if validated and segments is None:
            raise ValueError("architecture C needs segments")
        if not oracle and backend is None:
            raise ValueError("a backend is required unless oracle=True")
        self.score_fn, self.thresholds, self.backend = score_fn, thresholds, backend
        self.validated, self.segments, self.phrasing, self.oracle = validated, segments, phrasing, oracle

    def run(self, bundle: Bundle) -> Decision:
        raw: str | None = None
        if self.oracle:
            fields = bundle.stated.as_dict()
        else:
            raw = self.backend.complete(job_key("X", self.phrasing, bundle))
            fields = strict_json(raw)
            if fields is None:
                return Decision(REFER, None, None, ("parse_failure",), raw)
            errors = validate_extraction(fields)
            if errors:
                return Decision(REFER, None, fields, ("schema_invalid",), raw)
        features, flags = to_features(fields)
        if features is None:
            return Decision(REFER, None, fields, tuple(flags), raw)
        pd_value = self.score_fn(features)
        outcome = self.thresholds.outcome(pd_value)
        if self.validated:
            flags = run_checks(fields, features, self.segments)
            if flags:
                outcome = REFER
        return Decision(outcome, pd_value, fields, tuple(flags), raw)
