"""Run shell steps on Kaggle with this repository's code, then pull back selected files.

Standard library only; needs the Kaggle CLI. The repository files listed in INCLUDE are zipped
into the kernel script itself, so one push carries the code. Inputs from Kaggle datasets or other
kernels are found by file name and linked into the working copy.

Example:
  python3 tools/kaggle_job.py prep --step "python -m pytest -q" --step "python -m src.train_scorecard" \
      --dataset brycecf/give-me-some-credit-dataset --link cs-training.csv=data/raw/cs-training.csv \
      --collect results/scorecard --collect data/splits.csv
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

OWNER = "carloscrou"
INCLUDE = ["src", "tests", "tools", "kaggle/infer", "data/attacks", "data/splits.csv", "data/segments.json", "results/scorecard"]
PULL_ROOT = Path("kaggle/pulled")

RUNNER = '''\
import base64, glob, io, os, shutil, subprocess, sys, tempfile, zipfile
PAYLOAD = "{payload}"
JOB = {job}
root = tempfile.mkdtemp() + "/repo"
os.makedirs(root)
zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))).extractall(root)
for name, dest in JOB["links"].items():
    hits = glob.glob("/kaggle/input/**/" + name, recursive=True)
    print("LINK", name, "->", hits[:1], flush=True)
    if hits:
        os.makedirs(os.path.dirname(os.path.join(root, dest)) or root, exist_ok=True)
        os.symlink(hits[0], os.path.join(root, dest))
env = dict(os.environ, PYTHONPATH=root, PYTHONUNBUFFERED="1")
code = 0
for step in JOB["steps"]:
    print("STEP", step, flush=True)
    rc = subprocess.run(step, shell=True, cwd=root, env=env).returncode
    print("STEP_RC", rc, flush=True)
    if rc != 0:
        code = rc
        break
for path in JOB["collect"]:
    src, dst = os.path.join(root, path), os.path.join("/kaggle/working/collect", path)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
sys.exit(code)
'''


def build_payload(include: list[str]) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in include:
            p = Path(item)
            files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else []
            for f in files:
                if "__pycache__" not in f.parts and f.suffix != ".pyc":
                    z.write(f, f.as_posix())
    return base64.b64encode(buf.getvalue()).decode()


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--step", action="append", required=True)
    ap.add_argument("--collect", action="append", default=[])
    ap.add_argument("--link", action="append", default=[], help="filename=dest/in/repo")
    ap.add_argument("--dataset", action="append", default=[])
    ap.add_argument("--kernel", action="append", default=[], help="other kernel whose output is an input")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--internet", action="store_true")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--timeout", type=int, default=3000)
    a = ap.parse_args()

    slug = f"uw-injection-{a.name}"
    kdir = Path("kaggle/jobs") / a.name
    kdir.mkdir(parents=True, exist_ok=True)
    job = {"steps": a.step, "collect": a.collect, "links": dict(x.split("=", 1) for x in a.link)}
    (kdir / "script.py").write_text(RUNNER.format(payload=build_payload(INCLUDE), job=json.dumps(job)))
    (kdir / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{OWNER}/{slug}", "title": slug, "code_file": "script.py", "language": "python", "kernel_type": "script",
        "is_private": "true", "enable_gpu": str(a.gpu).lower(), "enable_tpu": "false", "enable_internet": str(a.internet).lower(),
        "dataset_sources": a.dataset, "competition_sources": [], "kernel_sources": a.kernel, "model_sources": []}, indent=2))

    push = ["kaggle", "kernels", "push", "-p", str(kdir)] + (["--accelerator", "NvidiaTeslaT4"] if a.gpu else [])
    print(sh(push))
    if a.no_wait:
        return
    deadline = time.time() + a.timeout
    status = ""
    while time.time() < deadline:
        time.sleep(15)
        status = sh(["kaggle", "kernels", "status", f"{OWNER}/{slug}"])
        if any(s in status for s in ("COMPLETE", "ERROR", "CANCEL")):
            break
    print(status)
    dest = PULL_ROOT / a.name
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    print(sh(["kaggle", "kernels", "output", f"{OWNER}/{slug}", "-p", str(dest)])[-300:])
    log = next(dest.glob("*.log"), None)
    if log:
        print("---- log tail ----")
        print("\n".join(log.read_text().splitlines()[-40:]))
    sys.exit(0 if "COMPLETE" in status else 1)


if __name__ == "__main__":
    main()
