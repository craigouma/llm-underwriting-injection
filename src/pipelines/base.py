"""Common interface for the three architectures and the cached-output backend."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from src.documents import Bundle

APPROVE, REFER, DECLINE = "approve", "refer", "decline"


@dataclass(frozen=True)
class Decision:
    outcome: str
    score: float | None
    extracted_fields: dict | None
    flags: tuple[str, ...]
    raw_model_output: str | None


class Pipeline(Protocol):
    def run(self, bundle: Bundle) -> Decision: ...


def bundle_key(bundle: Bundle) -> str:
    return f"{bundle.applicant_id}|{bundle.attack_id or 'clean'}"


def job_key(task: str, phrasing: int, bundle: Bundle) -> str:
    return f"{task}|p{phrasing}|{bundle_key(bundle)}"


class Backend(Protocol):
    def complete(self, key: str) -> str: ...


class ReplayBackend:
    """Reads raw model outputs cached by the Kaggle inference kernel. Never calls a model."""

    def __init__(self, outputs: Mapping[str, str]):
        self.outputs = outputs

    @classmethod
    def from_jsonl(cls, paths: Iterable[Path], model: str, run: str = "main") -> "ReplayBackend":
        out: dict[str, str] = {}
        for path in paths:
            with Path(path).open() as fh:
                for line in fh:
                    row = json.loads(line)
                    if row["model"] == model and row["run"] == run:
                        out[row["key"]] = row["text"]
        return cls(out)

    def complete(self, key: str) -> str:
        return self.outputs[key]


_FENCE = re.compile(r"^```(?:json)?\s*\n(.*)\n```$", re.S)


def strict_json(text: str) -> dict | None:
    """Parse a single JSON object, allowing only one surrounding markdown code fence."""
    body = text.strip()
    m = _FENCE.match(body)
    if m:
        body = m.group(1).strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


REFUSAL = re.compile(r"\b(I can(?:'|no)t|I cannot|I(?:'m| am) (?:sorry|unable)|I won't|as an AI)\b", re.I)
