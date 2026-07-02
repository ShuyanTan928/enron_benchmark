#!/usr/bin/env python3
"""gemma prober re-check of the FIXED T02/T06: does {a1,a3} still leak? (it did before the fix)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

FILE = "benchmark_pool/emails_lying_n3_fixcheck.jsonl"
MIN_FREE = 50000


def wait_gpus():
    while True:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"], text=True)
        cards = sorted(((int(i), int(f)) for i, n, f in (x.split(",") for x in out.strip().splitlines())
                        if "A100 80GB" in n), key=lambda c: -c[1])
        if len(cards) >= 2 and cards[1][1] >= MIN_FREE:
            print(f"GPUs ready {cards[:2]}", flush=True)
            return [cards[0][0], cards[1][0]], min(0.85, round((cards[1][1] - 3000) / 81920, 2))
        print(f"waiting for 2x A100-80 >= {MIN_FREE}; {cards}", flush=True)
        time.sleep(120)


idxs, gpu_mem = wait_gpus()
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, idxs))
sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
import email_generate as EG
from src.models.engine_factory import build_engine

eng = build_engine("vllm", "gemma4-31b", tp=2, gpu_mem=gpu_mem)
solo = joint = [eng]
print("\n===== gemma AND re-check on FIXED T02/T06 (was: {a1,a3} leaked) =====", flush=True)
for line in Path(FILE).read_text().splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    intended = {k: r["answer"][k] for k in ("actor", "victim", "true_fact", "false_belief")}
    ok, rep = EG.validate(solo, joint, r["clues"], intended, solo_thresh=1, joint_thresh=1)
    flag = "  <-- STILL LEAKS" if rep["leaks"] else "  ✓ clean (no subset leak)"
    print(f"  {r['topic_id']}: AND_ok={ok}  joint={rep['joint_votes']}/{rep['n_joint']}  "
          f"leaks={rep['leaks']}{flag}", flush=True)
print("DONE", flush=True)
