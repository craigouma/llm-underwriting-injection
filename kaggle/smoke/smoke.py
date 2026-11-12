"""Kaggle smoke test: GPU, internet, Hugging Face generation speed, vLLM availability."""
import json
import subprocess
import sys
import time

report: dict = {}


def sh(cmd: str, timeout: int = 900) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


report["nvidia_smi"] = sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
report["python"] = sys.version
report["pip"] = sh("pip list 2>/dev/null | grep -i -E '^(torch|transformers|vllm|accelerate|bitsandbytes|flash|xformers|numpy) '")
report["internet"] = sh("curl -s -m 20 -o /dev/null -w '%{http_code}' https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

report["cuda_devices"] = torch.cuda.device_count()
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16).cuda().eval()
report["hf_load_s"] = round(time.time() - t0, 1)

filler = "Gross monthly pay 4,250.00 employer Acme Ltd pay period March. " * 55
msgs = [[{"role": "user", "content": f"Document {i}: {filler}\nReturn JSON with the gross pay."}] for i in range(32)]
texts = [tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs]
enc = tok(texts, return_tensors="pt", padding=True).to("cuda")
report["prompt_tokens_each"] = int(enc["input_ids"].shape[1])
torch.cuda.synchronize()
t0 = time.time()
with torch.no_grad():
    out = model.generate(**enc, max_new_tokens=120, do_sample=False, pad_token_id=tok.pad_token_id)
torch.cuda.synchronize()
report["hf_batch32_s"] = round(time.time() - t0, 2)
report["hf_sample_out"] = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)[:200]
del model
torch.cuda.empty_cache()
json.dump(report, open("/kaggle/working/smoke_report.json", "w"), indent=2)

report["vllm_install"] = sh("pip install -q vllm 2>&1 | tail -5", timeout=1200)
report["vllm_version"] = sh("python -c 'import vllm;print(vllm.__version__)'", timeout=300)
json.dump(report, open("/kaggle/working/smoke_report.json", "w"), indent=2)

vllm_test = r'''
import json, time
from vllm import LLM, SamplingParams
llm = LLM("Qwen/Qwen2.5-1.5B-Instruct", dtype="half", max_model_len=2048, gpu_memory_utilization=0.85, enforce_eager=False)
filler = "Gross monthly pay 4,250.00 employer Acme Ltd pay period March. " * 55
prompts = [f"Document {i}: {filler}\nReturn JSON with the gross pay." for i in range(256)]
t0 = time.time()
outs = llm.generate(prompts, SamplingParams(temperature=0, max_tokens=120))
print(json.dumps({"vllm_256_calls_s": round(time.time() - t0, 2), "sample": outs[0].outputs[0].text[:120]}))
'''
open("/kaggle/working/vllm_test.py", "w").write(vllm_test)
report["vllm_run"] = sh("cd /kaggle/working && python vllm_test.py 2>&1 | tail -15", timeout=1200)
json.dump(report, open("/kaggle/working/smoke_report.json", "w"), indent=2)
print(json.dumps(report, indent=2))
