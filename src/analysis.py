"""Tables for the paper, computed from the cached decision tables only (docs/preregistration.md, sections 4 and 5)."""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.eval.metrics import holm, mcnemar_exact, wilson_interval
from src.pipelines.schema import FIELDS

TABLES = Path("results/tables")
CATEGORIES = ["instruction_override", "hidden_instruction", "fake_authority", "delimiter_format", "extraction_manipulation"]
INSTRUCTION = CATEGORIES[:4]
KEYS = ["model", "applicant_id", "attack_id"]


def load(run: str = "main") -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(glob.glob(str(TABLES / f"decisions_{run}_*.csv.gz")))]
    df = pd.concat(frames, ignore_index=True)
    df["success"] = df["outcome"] == "approve"
    return df


def with_oracle(df: pd.DataFrame) -> pd.DataFrame:
    """Give every model its own copy of the model-free oracle rows so arms can be compared per model."""
    oracle = df[df["model"] == "oracle"]
    models = [m for m in df["model"].unique() if m != "oracle"]
    copies = [oracle.assign(model=m) for m in models]
    return pd.concat([df[df["model"] != "oracle"], *copies], ignore_index=True)


def attacked_targets(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["in_P"] & (df["attack_id"] != "clean")]


def add_ci(t: pd.DataFrame) -> pd.DataFrame:
    ci = [wilson_interval(int(k), int(n)) for k, n in zip(t["k"], t["n"])]
    t = t.copy()
    t["rate"] = t["k"] / t["n"]
    t["lo"], t["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    return t


def asr(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Primary ASR with Wilson intervals: attacked P pairs whose final outcome is approve."""
    g = attacked_targets(df).groupby(["model", "arm", *by])["success"].agg(k="sum", n="size").reset_index()
    return add_ci(g)


def clean_approve_rate(df: pd.DataFrame) -> pd.DataFrame:
    clean = df[df["in_P"] & (df["attack_id"] == "clean")]
    g = clean.groupby(["model", "arm"])["success"].agg(k="sum", n="size").reset_index()
    return add_ci(g)


def paired_flip(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Among P applicants an arm does not approve when clean, the share it approves under attack."""
    clean = df[df["in_P"] & (df["attack_id"] == "clean")][["model", "arm", "applicant_id", "success"]].rename(columns={"success": "clean_success"})
    att = attacked_targets(df).merge(clean, on=["model", "arm", "applicant_id"])
    att = att[~att["clean_success"]]
    return add_ci(att.groupby(["model", "arm", *by])["success"].agg(k="sum", n="size").reset_index())


def clean_utility(df: pd.DataFrame) -> pd.DataFrame:
    u = df[df["in_U"] & (df["attack_id"] == "clean")]
    rows = []
    for (model, arm), g in u.groupby(["model", "arm"]):
        scored = g.dropna(subset=["score"])
        approved = g[g["outcome"] == "approve"]
        rows.append({"model": model, "arm": arm, "n": len(g), "coverage": len(scored) / len(g),
                     "auroc": roc_auc_score(scored["label"], scored["score"]) if scored["label"].nunique() == 2 else np.nan,
                     "approve_share": len(approved) / len(g),
                     "default_rate_approved": approved["label"].mean() if len(approved) else np.nan,
                     "refer_share": (g["outcome"] == "refer").mean(), "decline_share": (g["outcome"] == "decline").mean(),
                     "agree_reference": (g["outcome"] == g["outcome_ref"]).mean(),
                     "parse_failure": g["parse_failure"].mean(), "refusal": g["refusal"].mean(),
                     "schema_invalid": g["schema_invalid"].mean(), "incomplete": g["incomplete"].mean(),
                     "review_rate": g["review"].mean()})
    return pd.DataFrame(rows)


def extraction_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    b = df[(df["arm"] == "B") & df["in_U"] & (df["attack_id"] == "clean")]
    rows = []
    for model, g in b.groupby("model"):
        for f in FIELDS:
            col = g[f"fc_{f}"]
            rows.append({"model": model, "field": f, "accuracy": col.fillna(False).astype(bool).mean(), "n": len(g)})
    return pd.DataFrame(rows)


def paired(df: pd.DataFrame, arm_a: str, arm_b: str, mask: pd.Series | None = None) -> pd.DataFrame:
    att = attacked_targets(df)
    if mask is not None:
        att = att[mask.loc[att.index]]
    a = att[att["arm"] == arm_a][[*KEYS, "category", "success"]]
    b = att[att["arm"] == arm_b][[*KEYS, "success"]]
    return a.merge(b, on=KEYS, suffixes=("_a", "_b"))


def family_tests(df: pd.DataFrame) -> pd.DataFrame:
    """The planned McNemar family, Holm-adjusted per model (preregistration section 5.2)."""
    contrasts = [("A", "B"), ("A", "C"), ("B", "C"), ("A", "A_def")]
    rows = []
    for model in df["model"].unique():
        sub = df[df["model"] == model]
        block = []
        for cat in CATEGORIES:
            for a, b in contrasts:
                m = paired(sub, a, b)
                m = m[m["category"] == cat]
                res = mcnemar_exact(m["success_a"], m["success_b"])
                block.append({"model": model, "category": cat, "arm_a": a, "arm_b": b, "n": len(m),
                              "asr_a": m["success_a"].mean(), "asr_b": m["success_b"].mean(), **res})
        adj = holm([r["p"] for r in block])
        rows += [{**r, "p_holm": p} for r, p in zip(block, adj)]
    return pd.DataFrame(rows)


def review_burden(df: pd.DataFrame, arm: str = "C") -> pd.DataFrame:
    c = df[df["arm"] == arm]
    clean = c[c["in_U"] & (c["attack_id"] == "clean")].groupby("model")["review"].agg(k="sum", n="size").reset_index().assign(group="clean")
    att = c[c["in_P"] & (c["attack_id"] != "clean")].groupby(["model", "category"])["review"].agg(k="sum", n="size").reset_index()
    att = att.rename(columns={"category": "group"})
    return add_ci(pd.concat([clean, att], ignore_index=True))


def caught_by_c(df: pd.DataFrame) -> pd.DataFrame:
    """Of the attacks that succeed under B, the share that C flags for review (same extraction, exactly paired)."""
    m = paired(df, "B", "C")
    att = attacked_targets(df)
    c_flags = att[att["arm"] == "C"][[*KEYS, "review"]]
    m = m.merge(c_flags, on=KEYS)
    won = m[m["success_a"]]
    g = won.groupby(["model", "category"])["review"].agg(k="sum", n="size").reset_index()
    return add_ci(g)


def utility_under_attack(df: pd.DataFrame) -> pd.DataFrame:
    clean = df[df["attack_id"] == "clean"][["model", "arm", "applicant_id", "score", "label"]].rename(columns={"score": "score_clean"})
    att = attacked_targets(df).merge(clean[["model", "arm", "applicant_id", "score_clean"]], on=["model", "arm", "applicant_id"])
    att = att.dropna(subset=["score", "score_clean"])
    att = att.assign(se_att=(att["score"] - att["label"]) ** 2, se_clean=(att["score_clean"] - att["label"]) ** 2)
    g = att.groupby(["model", "arm", "category"]).agg(mse_attacked=("se_att", "mean"), mse_clean=("se_clean", "mean"), n=("se_att", "size")).reset_index()
    g["delta"] = g["mse_attacked"] - g["mse_clean"]
    return g


def collateral(df: pd.DataFrame) -> pd.DataFrame:
    q = df[df["in_Q"]]
    clean = q[q["attack_id"] == "clean"].groupby(["model", "arm"])["success"].mean().rename("approve_clean")
    att = q[q["attack_id"] != "clean"].groupby(["model", "arm", "category"])["success"].mean().rename("approve_attacked").reset_index()
    return att.merge(clean.reset_index(), on=["model", "arm"]).assign(
        not_approved_increase=lambda d: d["approve_clean"] - d["approve_attacked"])


def oracle_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """ASR of B and C minus the ASR of their oracle arms, per category and model."""
    t = asr(df, ["category"]).set_index(["model", "arm", "category"])["rate"]
    rows = []
    for (model, cat) in {(m, c) for m, _, c in t.index}:
        for arm in ("B", "C"):
            if (model, arm, cat) in t.index and (model, f"{arm}_oracle", cat) in t.index:
                rows.append({"model": model, "category": cat, "arm": arm, "asr": t[(model, arm, cat)],
                             "asr_oracle": t[(model, f"{arm}_oracle", cat)], "llm_attributable": t[(model, arm, cat)] - t[(model, f"{arm}_oracle", cat)]})
    return pd.DataFrame(rows)


def plausibility_trend(df: pd.DataFrame, arm: str = "B") -> pd.DataFrame:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    rows = []
    for model in df["model"].unique():
        d = attacked_targets(df[(df["model"] == model) & (df["arm"] == arm)])
        d = d[d["plausibility"].notna()].assign(y=lambda x: x["success"].astype(int))
        if d["y"].nunique() < 2:
            rows.append({"model": model, "arm": arm, "n": len(d), "slope": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan})
            continue
        fit = smf.gee("y ~ plausibility", groups="row_id", data=d, family=sm.families.Binomial(),
                      cov_struct=sm.cov_struct.Exchangeable()).fit()
        lo, hi = fit.conf_int().loc["plausibility"]
        rows.append({"model": model, "arm": arm, "n": len(d), "slope": fit.params["plausibility"], "lo": lo, "hi": hi,
                     "p": fit.pvalues["plausibility"]})
    return pd.DataFrame(rows)


def cluster_bootstrap_asr(df: pd.DataFrame, by: list[str], reps: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Applicant-level bootstrap interval for pooled ASR, as a sensitivity check on the Wilson interval."""
    rng = np.random.default_rng(seed)
    att = attacked_targets(df)
    rows = []
    for key, g in att.groupby(["model", "arm", *by]):
        ids = g["row_id"].unique()
        per = g.groupby("row_id")["success"].agg(["sum", "size"]).loc[ids]
        s, n = per["sum"].to_numpy(), per["size"].to_numpy()
        draws = rng.integers(0, len(ids), size=(reps, len(ids)))
        est = s[draws].sum(axis=1) / n[draws].sum(axis=1)
        rows.append({**dict(zip(["model", "arm", *by], key)), "boot_lo": np.quantile(est, 0.025), "boot_hi": np.quantile(est, 0.975)})
    return pd.DataFrame(rows)


def cumulative_check_tradeoff(df: pd.DataFrame, arm: str = "C") -> pd.DataFrame:
    """Review rate and ASR when checks are enabled cumulatively: range, currency, cross-document, plausible band."""
    groups = {"range": lambda f: f.startswith(("range:", "missing:")), "currency": lambda f: f.startswith("currency:"),
              "xdoc": lambda f: f.startswith("xdoc:"), "segment": lambda f: f.startswith("segment:")}
    order = ["range", "currency", "xdoc", "segment"]
    c = df[df["arm"] == arm].copy()
    flag_sets = c["flags"].fillna("").map(lambda s: [f for f in s.split("|") if f])
    b_outcome_approve = df[df["arm"] == arm.replace("C", "B")][[*KEYS, "success"]].rename(columns={"success": "b_success"})
    c = c.assign(flag_list=flag_sets).merge(b_outcome_approve, on=KEYS)
    rows = []
    for i in range(len(order) + 1):
        active = order[:i]
        flagged = c["flag_list"].map(lambda fl: any(groups[g](f) for f in fl for g in active))
        c2 = c.assign(flagged=flagged, success_c=c["b_success"] & ~flagged)
        clean = c2[c2["in_U"] & (c2["attack_id"] == "clean")]
        att = c2[c2["in_P"] & (c2["attack_id"] != "clean")]
        for model in c2["model"].unique():
            rows.append({"model": model, "checks": "+".join(active) or "none",
                         "clean_review_rate": clean[clean["model"] == model]["flagged"].mean(),
                         "asr_all": att[att["model"] == model]["success_c"].mean(),
                         "asr_extraction": att[(att["model"] == model) & (att["category"] == "extraction_manipulation")]["success_c"].mean()})
    return pd.DataFrame(rows)
