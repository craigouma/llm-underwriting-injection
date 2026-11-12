import pytest

from src.attacks import apply_attack, is_applicable, load_catalog

CATALOG = load_catalog()
TEXT_ATTACKS = [s for s in CATALOG if s.kind == "inject_text"]
VALUE_ATTACKS = [s for s in CATALOG if s.kind != "inject_text"]


def changed_docs(clean, attacked):
    return [d for d in clean.docs if clean.docs[d] != attacked.docs[d]]


def test_catalog_shape():
    ids = [s.id for s in CATALOG]
    assert len(ids) == len(set(ids)) == 26
    assert {s.sophistication for s in CATALOG} == {"low", "medium", "high"}
    assert {s.category for s in CATALOG} == {"instruction_override", "hidden_instruction", "fake_authority", "delimiter_format", "extraction_manipulation"}


@pytest.mark.parametrize("spec", TEXT_ATTACKS, ids=lambda s: s.id)
def test_text_attack_adds_payload_and_keeps_everything_else(bundles, spec):
    clean = bundles[0]
    attacked = apply_attack(clean, spec)
    assert spec.params["payload"] in "\n".join(attacked.docs.values())
    changed = changed_docs(clean, attacked)
    assert len(changed) == 1
    original = clean.docs[changed[0]].split("\n")
    kept = [line for line in attacked.docs[changed[0]].split("\n") if line in original]
    removed = [line for line in original if line not in attacked.docs[changed[0]]]
    assert set(removed) <= {"Additional comments: None"}
    assert len(kept) >= len(original) - 1
    assert attacked.stated == clean.stated and attacked.attack_id == spec.id


@pytest.mark.parametrize("spec", VALUE_ATTACKS, ids=lambda s: s.id)
def test_value_attack_changes_only_the_targeted_lines(bundles, segments, spec):
    clean = bundles[2]  # has late payments, debt and a revolving balance, so every attack applies
    assert is_applicable(clean, spec)
    attacked = apply_attack(clean, spec, segments)
    before = "\n".join(clean.docs.values()).split("\n")
    after = "\n".join(attacked.docs.values()).split("\n")
    diff_before = [l for l in before if l not in after]
    diff_after = [l for l in after if l not in before]
    assert 1 <= len(diff_after) <= 6 and len(diff_before) <= 6
    assert attacked.attack_id == spec.id
    assert "Ignore" not in "\n".join(attacked.docs.values())  # no instruction text in category 5


def test_scale_income_scopes(bundles):
    spec = {s.id: s for s in CATALOG}
    one = apply_attack(bundles[0], spec["EM2"])
    allp = apply_attack(bundles[0], spec["EM5"])
    assert one.stated.payslip_gross_monthly_income == round(bundles[0].stated.payslip_gross_monthly_income * 1.5)
    assert one.stated.statement_avg_monthly_deposits == bundles[0].stated.statement_avg_monthly_deposits
    assert allp.stated.statement_avg_monthly_deposits == round(bundles[0].stated.statement_avg_monthly_deposits * 1.5)
    assert allp.stated.form_declared_monthly_income == round(bundles[0].stated.form_declared_monthly_income * 1.5)


def test_format_attacks_keep_the_stated_value_the_oracle_reads(bundles):
    spec = {s.id: s for s in CATALOG}
    for attack_id in ("EM11", "EM12", "EM13"):
        attacked = apply_attack(bundles[0], spec[attack_id])
        assert attacked.stated == bundles[0].stated


def test_inapplicable_attacks_are_detected(bundles):
    spec = {s.id: s for s in CATALOG}
    assert not is_applicable(bundles[1], spec["EM7"])  # no late payments to omit
    assert not is_applicable(bundles[1], spec["EM8"])  # no debt to understate


def test_plausibility_is_highest_for_typical_values(bundles, segments):
    spec = {s.id: s for s in CATALOG}
    mild = apply_attack(bundles[0], spec["EM1"], segments).extras["attack"]["plausibility"]
    extreme = apply_attack(bundles[0], spec["EM3"], segments).extras["attack"]["plausibility"]
    assert mild is not None and extreme is not None and 0 <= extreme <= mild <= 1
