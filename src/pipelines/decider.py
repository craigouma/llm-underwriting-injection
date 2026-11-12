"""Architecture A: the LLM reads the bundle and returns the decision."""
from __future__ import annotations

from src.documents import Bundle
from src.pipelines.base import APPROVE, DECLINE, REFER, REFUSAL, Backend, Decision, job_key, strict_json

OUTCOMES = (APPROVE, REFER, DECLINE)


def parse_decision(text: str) -> tuple[str, float] | None:
    obj = strict_json(text)
    if obj is None or set(obj) != {"decision", "risk_score"}:
        return None
    risk = obj["risk_score"]
    if obj["decision"] not in OUTCOMES or isinstance(risk, bool) or not isinstance(risk, (int, float)) or not 0 <= risk <= 100:
        return None
    return obj["decision"], float(risk) / 100.0


class DeciderPipeline:
    """`defended=True` is the prompt-level defence variant (tagging plus a warning)."""

    def __init__(self, backend: Backend, defended: bool = False, phrasing: int = 0):
        self.backend, self.defended, self.phrasing = backend, defended, phrasing
        self.task = "A_def" if defended else "A"

    def run(self, bundle: Bundle) -> Decision:
        text = self.backend.complete(job_key(self.task, self.phrasing, bundle))
        parsed = parse_decision(text)
        if parsed is None:
            flag = "refusal" if REFUSAL.search(text) else "parse_failure"
            return Decision(REFER, None, None, (flag,), text)
        outcome, score = parsed
        return Decision(outcome, score, None, (), text)
