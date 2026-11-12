"""Kaggle GPU inference: build every prompt of a run from the repository code and cache raw model outputs.

Usage (inside a kernel): python kaggle/infer/infer.py --model Qwen/Qwen2.5-1.5B-Instruct --run pilot
Small models run one worker per GPU (data parallel). `--split` places one copy of a large model across both GPUs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MAX_NEW = {"A": 64, "A_def": 64, "X": 320}


def slug(model: str) -> str:
    return model.replace("/", "__")


def load_jobs(run: str, max_jobs: int | None):
    from src.jobs import build_jobs, select
    from src.segments import Segments

    jobs = build_jobs(select(), Segments.from_json(), run)
    return jobs[:max_jobs] if max_jobs else jobs


def worker(args) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    jobs = load_jobs(args.run, args.max_jobs)
    jobs = jobs[args.shard :: args.nshards]
    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    if args.split:
        model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float16, device_map="auto",
                                                     max_memory={0: "13GiB", 1: "13GiB"}).eval()
        device = model.device
    else:
        model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float16).to("cuda").eval()
        device = "cuda"

    def render(messages: list[dict]) -> str:
        try:
            return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:  # templates without a system role
            merged = [{"role": "user", "content": messages[0]["content"] + "\n\n" + messages[1]["content"]}]
            return tok.apply_chat_template(merged, tokenize=False, add_generation_prompt=True)

    texts = [render(j.messages) for j in jobs]
    lengths = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts]
    order = sorted(range(len(jobs)), key=lambda i: (jobs[i].task == "X", lengths[i]))
    out_path = Path(args.out) / args.run / f"{slug(args.model)}.shard{args.shard}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    start, done, tin, tout = time.time(), 0, 0, 0
    batches, cur, cur_max = [], [], 0
    for i in order:
        new_max = max(cur_max, lengths[i])
        if cur and (new_max * (len(cur) + 1) > args.batch_tokens or len(cur) >= args.max_batch or jobs[i].task != jobs[cur[0]].task):
            batches.append(cur)
            cur, new_max = [], lengths[i]
        cur.append(i)
        cur_max = new_max
    if cur:
        batches.append(cur)

    with out_path.open("w") as fh:
        for b_idx, batch in enumerate(batches):
            task = jobs[batch[0]].task
            enc = tok([texts[i] for i in batch], return_tensors="pt", padding=True, add_special_tokens=False).to(device)
            sample = jobs[batch[0]].temperature > 0
            if sample:
                torch.manual_seed(jobs[batch[0]].seed * 100003 + b_idx)
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=MAX_NEW[task], do_sample=sample,
                                     temperature=jobs[batch[0]].temperature if sample else None, top_p=1.0 if sample else None,
                                     top_k=None, pad_token_id=tok.pad_token_id)
            new = gen[:, enc["input_ids"].shape[1] :]
            for k, i in enumerate(batch):
                text = tok.decode(new[k], skip_special_tokens=True)
                n_out = int((new[k] != tok.pad_token_id).sum())
                fh.write(json.dumps({"key": jobs[i].key, "run": jobs[i].run, "model": args.model, "task": jobs[i].task,
                                     "text": text, "tokens_in": lengths[i], "tokens_out": n_out}) + "\n")
                tin += lengths[i]
                tout += n_out
            fh.flush()
            done += len(batch)
            if b_idx % 10 == 0:
                el = time.time() - start
                print(f"[shard {args.shard}] {done}/{len(jobs)} calls, {done / el:.2f} calls/s, {tin / el:.0f} prompt tok/s", flush=True)
    el = time.time() - start
    print(json.dumps({"shard": args.shard, "model": args.model, "run": args.run, "calls": done, "seconds": round(el, 1),
                      "calls_per_s": round(done / el, 2), "mean_tokens_in": round(tin / max(done, 1)),
                      "mean_tokens_out": round(tout / max(done, 1), 1)}), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--run", default="pilot")
    ap.add_argument("--out", default="results/raw")
    ap.add_argument("--max-jobs", type=int)
    ap.add_argument("--batch-tokens", type=int, default=24000)
    ap.add_argument("--max-batch", type=int, default=64)
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--worker", action="store_true")
    args = ap.parse_args()
    if args.worker or args.split:
        worker(args)
        return
    procs = []
    for shard in range(2):
        cmd = [sys.executable, __file__, "--worker", "--model", args.model, "--run", args.run, "--out", args.out, "--shard", str(shard),
               "--nshards", "2", "--batch-tokens", str(args.batch_tokens), "--max-batch", str(args.max_batch)]
        if args.max_jobs:
            cmd += ["--max-jobs", str(args.max_jobs)]
        procs.append(subprocess.Popen(cmd, env=dict(os.environ, CUDA_VISIBLE_DEVICES=str(shard))))
    codes = [p.wait() for p in procs]
    sys.exit(max(codes))


if __name__ == "__main__":
    main()
