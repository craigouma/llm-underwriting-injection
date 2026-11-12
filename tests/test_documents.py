import re

from src.documents import APPLICATION_DATE, make_bundle

NUMBER = re.compile(r"[\d,]+(?:\.\d+)?")


def numbers(text: str) -> set[float]:
    return {float(m.replace(",", "")) for m in NUMBER.findall(text) if m.replace(",", "").replace(".", "").isdigit()}


def test_stated_values_match_row(rows, bundles):
    for row, b in zip(rows, bundles):
        s = b.stated
        assert s.payslip_gross_monthly_income == row["monthly_income"] == s.form_declared_monthly_income
        assert s.form_age == row["age"] and s.form_dependents == row["dependents"]
        assert s.form_open_credit_lines == row["open_lines"] and s.form_real_estate_loans == row["real_estate_loans"]
        assert (s.form_late_30_59, s.form_late_60_89, s.form_late_90_plus) == (row["late_30_59"], row["late_60_89"], row["late_90"])
        assert abs(s.statement_monthly_debt_payments - row["debt_ratio"] * row["monthly_income"]) <= 0.5
        assert abs(s.form_revolving_balance / s.form_revolving_limit - row["utilization"]) <= 0.01
        assert s.form_declared_monthly_debt == s.statement_monthly_debt_payments


def test_deposits_are_consistent_with_net_pay(bundles):
    for b in bundles:
        ratio = b.stated.statement_avg_monthly_deposits / b.stated.payslip_gross_monthly_income
        assert 0.68 <= ratio <= 0.96


def test_documents_state_the_values(bundles):
    for b in bundles:
        s = b.stated
        assert numbers(b.docs["payslip"]) >= {s.payslip_gross_monthly_income}
        assert numbers(b.docs["bank_statement"]) >= {s.statement_avg_monthly_deposits, s.statement_monthly_debt_payments} - {0.0}
        form = numbers(b.docs["application_form"])
        assert {float(s.form_age), s.form_revolving_limit} <= form
        assert b.applicant_id in b.docs["application_form"]


def test_date_of_birth_agrees_with_age(bundles):
    from datetime import date

    for b in bundles:
        dob = date.fromisoformat(b.style.dob)
        years = (APPLICATION_DATE - dob).days / 365.25
        assert b.stated.form_age <= years < b.stated.form_age + 1.01


def test_generation_is_deterministic(rows):
    assert make_bundle(rows[0], 5).docs == make_bundle(rows[0], 5).docs
    assert make_bundle(rows[0], 5).docs != make_bundle(rows[0], 6).docs
