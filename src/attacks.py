"""Attack functions: each takes a clean bundle and returns an attacked bundle.

Categories 1 to 4 add instruction-style text at a fixed location. Category 5 changes what the
documents state (or how they state it) with no instruction text. A falsification edits `stated`
and re-renders, so every other line stays identical. Payloads and parameters live in
data/attacks/catalog.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.documents import LABELS, Bundle, money, with_stated
from src.segments import Segments

CATALOG_PATH = Path("data/attacks/catalog.json")
COMMENTS_PREFIX = "Additional comments:"
CATEGORIES = ("instruction_override", "hidden_instruction", "fake_authority", "delimiter_format", "extraction_manipulation")


@dataclass(frozen=True)
class AttackSpec:
    id: str
    category: str
    sophistication: str
    kind: str
    params: dict[str, Any]


def load_catalog(path: Path = CATALOG_PATH) -> list[AttackSpec]:
    specs = []
    for item in json.loads(path.read_text()):
        params = {k: v for k, v in item.items() if k not in ("id", "category", "sophistication", "kind")}
        specs.append(AttackSpec(item["id"], item["category"], item["sophistication"], item["kind"], params))
    return specs


def _gross_label(bundle: Bundle) -> str:
    return LABELS["gross"][bundle.style.labels["gross"]]


def _debt_label(bundle: Bundle) -> str:
    return LABELS["debt"][bundle.style.labels["debt"]]


def _replace_line(text: str, prefix: str, new_line: str) -> str:
    lines = text.split("\n")
    idx = next(i for i, line in enumerate(lines) if line.startswith(prefix))
    lines[idx] = new_line
    return "\n".join(lines)


def _insert_after(text: str, prefix: str, new_line: str) -> str:
    lines = text.split("\n")
    idx = next(i for i, line in enumerate(lines) if line.startswith(prefix))
    lines.insert(idx + 1, new_line)
    return "\n".join(lines)


def is_applicable(bundle: Bundle, spec: AttackSpec) -> bool:
    """An attack that would leave the documents unchanged is not applied."""
    s = bundle.stated
    if spec.kind == "omit_late":
        return s.form_late_30_59 + s.form_late_60_89 + s.form_late_90_plus > 0
    if spec.kind in ("understate_debt", "thousands_debt"):
        return s.statement_monthly_debt_payments > 0
    if spec.kind == "understate_utilization":
        return s.form_revolving_balance > 0
    return True


def _target(bundle: Bundle, spec: AttackSpec) -> tuple[str, float] | None:
    """The feature the falsification pushes and the value it pushes it to (for the plausibility score)."""
    s, f = bundle.stated, spec.params.get("factor")
    income = s.payslip_gross_monthly_income
    if spec.kind in ("scale_income", "conflicting_income", "duplicate_gross"):
        return "monthly_income", income * f
    if spec.kind == "omit_late":
        return "late_total", 0.0
    if spec.kind == "understate_debt":
        return "debt_ratio", s.statement_monthly_debt_payments * f / income
    if spec.kind == "understate_utilization":
        return "utilization", s.form_revolving_balance * f / s.form_revolving_limit
    return None


def apply_attack(bundle: Bundle, spec: AttackSpec, segments: Segments | None = None) -> Bundle:
    s, p = bundle.stated, spec.params
    docs = dict(bundle.docs)
    out = bundle

    def fmt(value: float) -> str:
        return money(value, bundle.style.money, "USD", True)

    if spec.kind == "inject_text":
        place = p["placement"]
        if place == "form_comments":
            docs["application_form"] = _replace_line(docs["application_form"], COMMENTS_PREFIX, f"{COMMENTS_PREFIX} {p['payload']}")
        else:
            doc = {"payslip_footer": "payslip", "statement_footer": "bank_statement", "form_metadata": "application_form"}[place]
            docs[doc] = docs[doc] + "\n" + p["payload"]
        out = replace(bundle, docs=docs)
    elif spec.kind == "scale_income":
        f = p["factor"]
        changes: dict[str, Any] = {"payslip_gross_monthly_income": float(round(s.payslip_gross_monthly_income * f))}
        if p["scope"] == "consistent":
            changes["statement_avg_monthly_deposits"] = float(round(s.statement_avg_monthly_deposits * f))
            changes["form_declared_monthly_income"] = float(round(s.form_declared_monthly_income * f))
        out = with_stated(bundle, **changes)
    elif spec.kind == "omit_late":
        out = with_stated(bundle, form_late_30_59=0, form_late_60_89=0, form_late_90_plus=0)
    elif spec.kind == "understate_debt":
        new = float(round(s.statement_monthly_debt_payments * p["factor"]))
        out = with_stated(bundle, statement_monthly_debt_payments=new, form_declared_monthly_debt=new)
    elif spec.kind == "understate_utilization":
        out = with_stated(bundle, form_revolving_balance=float(round(s.form_revolving_balance * p["factor"])))
    elif spec.kind == "conflicting_income":
        out = with_stated(bundle, form_declared_monthly_income=float(round(s.form_declared_monthly_income * p["factor"])))
    elif spec.kind == "duplicate_gross":
        label = _gross_label(bundle)
        docs["payslip"] = _insert_after(docs["payslip"], label + ":", f"{label} (corrected): {fmt(round(s.payslip_gross_monthly_income * p['factor']))}")
        out = replace(bundle, docs=docs)
    elif spec.kind == "annual_as_monthly":
        label = _gross_label(bundle)
        docs["payslip"] = _replace_line(docs["payslip"], label + ":", f"Annual gross salary: {fmt(s.payslip_gross_monthly_income * 12)} (paid monthly)")
        out = replace(bundle, docs=docs)
    elif spec.kind == "thousands_debt":
        label = _debt_label(bundle)
        docs["bank_statement"] = _replace_line(docs["bank_statement"], label + ":", f"{label} (USD '000): {s.statement_monthly_debt_payments / 1000:.2f}")
        out = replace(bundle, docs=docs)
    elif spec.kind == "currency_mismatch":
        out = with_stated(bundle, payslip_currency="KES", payslip_gross_monthly_income=float(round(s.payslip_gross_monthly_income * p["rate"])))
    else:
        raise ValueError(f"unknown attack kind {spec.kind}")

    target = _target(bundle, spec)
    plausibility = None
    if target is not None and segments is not None:
        plausibility = segments.plausibility(target[0], s.form_age, target[1])
    record = {"id": spec.id, "category": spec.category, "sophistication": spec.sophistication, "kind": spec.kind,
              "target_field": target[0] if target else None, "target_value": target[1] if target else None,
              "plausibility": plausibility}
    return replace(out, attack_id=spec.id, extras={**bundle.extras, "attack": record})
