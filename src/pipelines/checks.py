"""Architecture C checks. All rules are fixed in code before any experiment (see docs/preregistration.md)."""
from __future__ import annotations

from src.segments import Segments

RANGES = {
    "payslip_gross_monthly_income": (300, 200_000), "statement_avg_monthly_deposits": (0, 400_000),
    "statement_monthly_debt_payments": (0, 200_000), "form_declared_monthly_income": (300, 200_000),
    "form_declared_monthly_debt": (0, 200_000), "form_age": (18, 100), "form_dependents": (0, 15),
    "form_open_credit_lines": (0, 60), "form_real_estate_loans": (0, 20), "form_revolving_limit": (0, 2_000_000),
    "form_revolving_balance": (0, 4_000_000), "form_late_30_59": (0, 24), "form_late_60_89": (0, 24), "form_late_90_plus": (0, 24),
}
CROSS_FIELDS = ("payslip_gross_monthly_income", "statement_avg_monthly_deposits", "form_declared_monthly_income",
                "statement_monthly_debt_payments", "form_declared_monthly_debt")
DEPOSIT_RATIO_BAND = (0.60, 1.10)  # deposits divided by gross pay: take-home is 60% to 100% of gross, with up to 10% other credits
INCOME_TOLERANCE = 0.05
DEBT_TOLERANCE, DEBT_FLOOR = 0.10, 50.0
EXPECTED_CURRENCY = "USD"


def run_checks(fields: dict, features: dict, segments: Segments) -> list[str]:
    flags: list[str] = []
    for name, (lo, hi) in RANGES.items():
        value = fields.get(name)
        if value is not None and not lo <= value <= hi:
            flags.append(f"range:{name}")
    if not 0 <= features["utilization"] <= 2:
        flags.append("range:utilization")
    if fields.get("payslip_currency") not in (None, EXPECTED_CURRENCY):
        flags.append("currency:not_usd")
    for name in CROSS_FIELDS:
        if fields.get(name) is None:
            flags.append(f"missing:{name}")

    gross, deposits = fields.get("payslip_gross_monthly_income"), fields.get("statement_avg_monthly_deposits")
    if gross and deposits is not None and not DEPOSIT_RATIO_BAND[0] <= deposits / gross <= DEPOSIT_RATIO_BAND[1]:
        flags.append("xdoc:income_vs_deposits")
    declared = fields.get("form_declared_monthly_income")
    if gross and declared is not None and abs(declared - gross) > INCOME_TOLERANCE * max(declared, gross):
        flags.append("xdoc:declared_vs_payslip_income")
    stmt_debt, declared_debt = fields.get("statement_monthly_debt_payments"), fields.get("form_declared_monthly_debt")
    if stmt_debt is not None and declared_debt is not None and abs(stmt_debt - declared_debt) > max(DEBT_TOLERANCE * max(stmt_debt, declared_debt), DEBT_FLOOR):
        flags.append("xdoc:declared_vs_statement_debt")

    age = fields.get("form_age")
    if age is not None:
        if segments.outside_band("monthly_income", age, features["monthly_income"]):
            flags.append("segment:income")
        if segments.outside_band("debt_ratio", age, features["debt_ratio"], lower=0.0):
            flags.append("segment:debt_ratio")
        if segments.outside_band("utilization", age, features["utilization"], lower=0.0):
            flags.append("segment:utilization")
    return flags
