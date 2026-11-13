"""Summarise the GPU time of the inference kernels from their pulled logs into results/compute.json.

Run after pulling the grid kernel outputs: python3 tools/compute_summary.py
Standard library only. Seconds are the generation time of each run (the slower of the two data-parallel workers).
"""
from __future__ import annotations

import json
from pathlib import Path

KERNELS = {"gridqwen": "Qwen/Qwen2.5-1.5B-Instruct", "gridphi": "microsoft/Phi-4-mini-instruct", "gridolmo": "allenai/Olmo-3-7B-Instruct"}
GPUS_PER_SESSION = 2


def summarise(log_path: Path) -> dict:
    seconds: dict[str, float] = {}
    calls: dict[str, int] = {}
    for event in json.loads(log_path.read_text()):
        line = event.get("data", "")
        if line.startswith('{"shard"'):
            rec = json.loads(line)
            seconds[rec["run"]] = max(seconds.get(rec["run"], 0.0), rec["seconds"])
            calls[rec["run"]] = calls.get(rec["run"], 0) + rec["calls"]
    return {"runs": {r: {"seconds": round(seconds[r], 1), "calls": calls[r]} for r in seconds},
            "seconds": round(sum(seconds.values()), 1), "calls": sum(calls.values())}


def main() -> None:
    models = {m: summarise(Path(f"kaggle/pulled/{k}/uw-injection-{k}.log")) for k, m in KERNELS.items()}
    total = sum(v["seconds"] for v in models.values())
    out = {"gpus_per_session": GPUS_PER_SESSION, "gpu": "NVIDIA Tesla T4", "models": models,
           "session_hours": round(total / 3600, 2), "gpu_hours": round(GPUS_PER_SESSION * total / 3600, 2),
           "calls": sum(v["calls"] for v in models.values())}
    Path("results/compute.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("session_hours", "gpu_hours", "calls")}))


if __name__ == "__main__":
    main()
