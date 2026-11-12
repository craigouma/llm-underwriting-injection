"""Extraction schema shared by the prompt, the validator and the oracle."""
from __future__ import annotations

from jsonschema import Draft202012Validator

NUMBER_FIELDS = ("payslip_gross_monthly_income", "statement_avg_monthly_deposits", "statement_monthly_debt_payments",
                 "form_declared_monthly_income", "form_declared_monthly_debt", "form_revolving_limit", "form_revolving_balance")
INTEGER_FIELDS = ("form_age", "form_dependents", "form_open_credit_lines", "form_real_estate_loans",
                  "form_late_30_59", "form_late_60_89", "form_late_90_plus")
STRING_FIELDS = ("payslip_currency",)
FIELDS = NUMBER_FIELDS + INTEGER_FIELDS + STRING_FIELDS

FIELD_HELP = {
    "payslip_gross_monthly_income": "number, gross pay per month on the payslip",
    "payslip_currency": "string, ISO currency code of the payslip amounts, for example \"USD\"",
    "statement_avg_monthly_deposits": "number, average monthly deposits on the bank statement",
    "statement_monthly_debt_payments": "number, average monthly loan and credit repayments on the bank statement",
    "form_declared_monthly_income": "number, gross monthly income declared on the application form",
    "form_declared_monthly_debt": "number, monthly debt repayments declared on the application form",
    "form_age": "integer, applicant age in years",
    "form_dependents": "integer, number of dependants",
    "form_open_credit_lines": "integer, open credit accounts and loans",
    "form_real_estate_loans": "integer, real estate loans or mortgages",
    "form_revolving_limit": "number, total revolving credit limit",
    "form_revolving_balance": "number, current revolving balance",
    "form_late_30_59": "integer, times 30-59 days late in the last 24 months",
    "form_late_60_89": "integer, times 60-89 days late in the last 24 months",
    "form_late_90_plus": "integer, times 90 or more days late in the last 24 months",
}

_SCHEMA = {
    "type": "object",
    "required": list(FIELDS),
    "properties": {**{k: {"type": ["number", "null"]} for k in NUMBER_FIELDS},
                   **{k: {"type": ["integer", "null"]} for k in INTEGER_FIELDS},
                   **{k: {"type": ["string", "null"]} for k in STRING_FIELDS}},
}
_VALIDATOR = Draft202012Validator(_SCHEMA)


def validate_extraction(obj: dict) -> list[str]:
    """Schema errors for an extraction object. Booleans are rejected because JSON Schema treats them apart from numbers."""
    errors = [e.message[:80] for e in _VALIDATOR.iter_errors(obj)]
    errors += [f"bool:{k}" for k in FIELDS if isinstance(obj.get(k), bool)]
    return errors
