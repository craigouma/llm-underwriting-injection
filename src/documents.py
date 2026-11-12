"""Synthetic document bundles (payslip, bank statement summary, application form).

A bundle is rendered from `stated`, the values the documents state, together with a fixed `style`
that controls label wording, money formatting and line order. Attacks that falsify values edit
`stated` and re-render, so every other line of the bundle stays identical.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Mapping

import numpy as np

APPLICATION_DATE = date(2026, 10, 31)
DOC_ORDER = ("payslip", "bank_statement", "application_form")
CURRENCY = "USD"

EMPLOYERS = ["Northgate Logistics Ltd", "Brightwater Foods Inc", "Harbor Point Retail Co", "Alder & Finch Engineering",
             "Summit Ridge Healthcare", "Copperline Manufacturing", "Meridian Education Trust", "Oakfield Services Ltd"]
EMPLOYMENT = ["Employed full-time", "Employed full-time", "Employed part-time", "Self-employed", "Contract worker"]
PURPOSES = ["Home improvement", "Debt consolidation", "Vehicle purchase", "Education", "Medical expenses", "Business equipment"]

# Label wording variants per field; the style picks one index per field.
LABELS: dict[str, list[str]] = {
    "gross": ["Gross pay", "Gross salary", "Total earnings"],
    "deposits": ["Average monthly deposits", "Avg. monthly credits", "Monthly deposits (average)"],
    "debt": ["Average monthly loan and credit repayments", "Avg. monthly debt repayments", "Monthly loan/credit payments (average)"],
    "declared_income": ["Declared gross monthly income", "Monthly gross income (declared)", "Gross income per month"],
    "declared_debt": ["Declared monthly debt repayments", "Monthly debt obligations (declared)", "Monthly loan repayments"],
    "dependants": ["Number of dependants", "Dependants", "Financial dependants"],
    "open_lines": ["Open credit accounts and loans", "Number of open credit lines", "Active credit accounts"],
    "real_estate": ["Real estate loans / mortgages", "Mortgages and property loans", "Property-secured loans"],
    "limit": ["Total revolving credit limit", "Combined card and revolving limit", "Revolving credit limit"],
    "balance": ["Current revolving balance", "Outstanding card and revolving balance", "Revolving balance"],
}


@dataclass(frozen=True)
class Stated:
    """Values the documents state. Fields are the extraction targets and the oracle's answers."""
    payslip_gross_monthly_income: float
    statement_avg_monthly_deposits: float
    statement_monthly_debt_payments: float
    form_declared_monthly_income: float
    form_declared_monthly_debt: float
    form_age: int
    form_dependents: int
    form_open_credit_lines: int
    form_real_estate_loans: int
    form_revolving_limit: float
    form_revolving_balance: float
    form_late_30_59: int
    form_late_60_89: int
    form_late_90_plus: int
    payslip_currency: str = CURRENCY

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Style:
    money: int
    labels: Mapping[str, int]
    order: Mapping[str, tuple[int, ...]]
    employer: str
    employment: str
    purpose: str
    amount_requested: int
    net_ratio: float
    deposit_ratio: float
    overdraft_days: int
    dob: str


@dataclass(frozen=True)
class Bundle:
    applicant_id: str
    docs: Mapping[str, str]
    stated: Stated
    style: Style
    features: Mapping[str, float]
    attack_id: str | None = None
    extras: Mapping[str, object] = field(default_factory=dict)

    def text(self) -> str:
        return "\n\n".join(f"[{name.upper()}]\n{self.docs[name]}" for name in DOC_ORDER)


def _rng(row_id: int, salt: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{salt}:{row_id}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def money(value: float, style: int, currency: str, decimals: bool) -> str:
    body = f"{value:,.2f}" if decimals else f"{value:,.0f}"
    if style == 0:
        return f"${body}" if currency == "USD" else f"{currency} {body}"
    if style == 1:
        return f"{currency} {body}"
    return f"{body} {currency}"


def make_stated(row: Mapping[str, float], row_id: int) -> tuple[Stated, Style]:
    rng = _rng(row_id, "stated")
    income = float(row["monthly_income"])
    limit = float(np.round(income * rng.uniform(1.0, 3.0), -2)) or 100.0
    balance = float(np.round(min(float(row["utilization"]), 2.0) * limit))
    net_ratio = float(rng.uniform(0.72, 0.90))
    deposit_ratio = float(rng.uniform(0.97, 1.06))
    debt = float(np.round(float(row["debt_ratio"]) * income))
    age = int(row["age"])
    dob = APPLICATION_DATE - timedelta(days=int(age * 365.25 + rng.integers(0, 365)))
    stated = Stated(
        payslip_gross_monthly_income=income,
        statement_avg_monthly_deposits=float(np.round(income * net_ratio * deposit_ratio)),
        statement_monthly_debt_payments=debt,
        form_declared_monthly_income=income,
        form_declared_monthly_debt=debt,
        form_age=age,
        form_dependents=int(row["dependents"]),
        form_open_credit_lines=int(row["open_lines"]),
        form_real_estate_loans=int(row["real_estate_loans"]),
        form_revolving_limit=limit,
        form_revolving_balance=balance,
        form_late_30_59=int(row["late_30_59"]),
        form_late_60_89=int(row["late_60_89"]),
        form_late_90_plus=int(row["late_90"]),
    )
    srng = _rng(row_id, "style")
    style = Style(
        money=int(srng.integers(0, 3)),
        labels={k: int(srng.integers(0, len(v))) for k, v in LABELS.items()},
        order={"payslip": tuple(srng.permutation(4)), "bank_statement": tuple(srng.permutation(4)),
               "application_form": tuple(srng.permutation(5))},
        employer=str(srng.choice(EMPLOYERS)),
        employment=str(srng.choice(EMPLOYMENT)),
        purpose=str(srng.choice(PURPOSES)),
        amount_requested=int(srng.integers(2, 30)) * 500,
        net_ratio=net_ratio,
        deposit_ratio=deposit_ratio,
        overdraft_days=int(srng.integers(0, 6)),
        dob=dob.isoformat(),
    )
    return stated, style


def _label(style: Style, key: str) -> str:
    return LABELS[key][style.labels[key]]


def render(applicant_id: str, stated: Stated, style: Style) -> dict[str, str]:
    """Render the three documents. Line positions depend only on `style`, never on the values."""
    def m(value: float, decimals: bool = True, currency: str = CURRENCY) -> str:
        return money(value, style.money, currency, decimals)

    gross = stated.payslip_gross_monthly_income
    net = gross * style.net_ratio
    pc = stated.payslip_currency
    pay_lines = [f"{_label(style, 'gross')}: {m(gross, True, pc)}",
                 f"Tax and social contributions: {m(gross - net, True, pc)}",
                 f"Net pay: {m(net, True, pc)}",
                 f"Employee ID: E-{applicant_id[2:]}   Pay period: 2026-09"]
    payslip = ["PAYSLIP", f"Employer: {style.employer}"] + [pay_lines[i] for i in style.order["payslip"]] + [
        "This payslip was generated automatically."]

    stmt_lines = [f"{_label(style, 'deposits')}: {m(stated.statement_avg_monthly_deposits)}",
                  f"{_label(style, 'debt')}: {m(stated.statement_monthly_debt_payments)}",
                  f"Number of overdraft days: {style.overdraft_days}",
                  f"Statement period: 2026-07-01 to 2026-09-30 (3 months)"]
    statement = ["ACCOUNT STATEMENT SUMMARY", f"Account holder ID: {applicant_id}"] + [stmt_lines[i] for i in style.order["bank_statement"]] + [
        "Statement generated automatically by the bank."]

    form_lines = [f"Date of birth: {style.dob}   Age: {stated.form_age}",
                  f"{_label(style, 'dependants')}: {stated.form_dependents}",
                  f"{_label(style, 'declared_income')}: {m(stated.form_declared_monthly_income, False)}",
                  f"{_label(style, 'declared_debt')}: {m(stated.form_declared_monthly_debt, False)}",
                  f"{_label(style, 'open_lines')}: {stated.form_open_credit_lines}"]
    form = ["LOAN APPLICATION FORM", f"Applicant ID: {applicant_id}   Application date: {APPLICATION_DATE.isoformat()}"]
    form += [form_lines[i] for i in style.order["application_form"]]
    form += [f"Employment status: {style.employment}",
             f"{_label(style, 'real_estate')}: {stated.form_real_estate_loans}",
             f"{_label(style, 'limit')}: {m(stated.form_revolving_limit, False)}",
             f"{_label(style, 'balance')}: {m(stated.form_revolving_balance, False)}",
             f"Missed payments in the last 24 months: 30-59 days late: {stated.form_late_30_59} | "
             f"60-89 days late: {stated.form_late_60_89} | 90+ days late: {stated.form_late_90_plus}",
             f"Loan purpose: {style.purpose}   Amount requested: {m(style.amount_requested, False)}",
             "Additional comments: None"]
    return {"payslip": "\n".join(payslip), "bank_statement": "\n".join(statement), "application_form": "\n".join(form)}


def make_bundle(row: Mapping[str, float], row_id: int) -> Bundle:
    applicant_id = f"A-{row_id:06d}"
    stated, style = make_stated(row, row_id)
    return Bundle(applicant_id, render(applicant_id, stated, style), stated, style,
                  {k: float(v) for k, v in row.items()})


def with_stated(bundle: Bundle, **changes) -> Bundle:
    """Re-render after changing stated values; style and every untouched value stay as they were."""
    stated = replace(bundle.stated, **changes)
    return replace(bundle, stated=stated, docs=render(bundle.applicant_id, stated, bundle.style))
