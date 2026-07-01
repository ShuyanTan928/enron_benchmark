#!/usr/bin/env python3
"""Self-scheduling launcher for the secret-recovery eval sweep.

Polls the mixed-GPU box (4x A100-80 + 4x A800-40) until two A100-80 cards are free enough, then:
  1. runs a SMOKE (2 topics, noise 0, 1 rep) and gates on it actually recovering a secret;
  2. if the smoke passes, launches the FULL sweep (n2+n3, noise 0..100, 5 reps).

Everything is logged to results/eval_rubric/run.log. CUDA_DEVICE_ORDER=PCI_BUS_ID is forced so the
picked indices match nvidia-smi. Runs unattended — no human in the loop.
"""
import csv
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/work6/shuyant/enron_benchmark")
LOG = ROOT / "results/eval_rubric/run.log"
MIN_FREE_MIB = 50000          # per A100-80 card, for tp=2 (31 GB shard + >=15 GB KV region)
POLL_S = 120


def log(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def free_a100s():
    """Return [(index, free_mib)] for A100-80 cards, most-free first."""
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,name,memory.free", "--format=csv,noheader,nounits"],
        text=True)
    cards = []
    for ln in out.strip().splitlines():
        idx, name, free = [x.strip() for x in ln.split(",")]
        if "A100 80GB" in name:
            cards.append((int(idx), int(free)))
    return sorted(cards, key=lambda c: -c[1])


def wait_for_gpus():
    while True:
        cards = free_a100s()
        top2 = cards[:2]
        if len(top2) == 2 and top2[1][1] >= MIN_FREE_MIB:
            idxs = [c[0] for c in top2]
            min_free = top2[1][1]
            gpu_mem = min(0.85, round((min_free - 3000) / 81920, 2))
            log(f"GPUs ready: {top2} -> CUDA_VISIBLE_DEVICES={idxs} gpu_mem={gpu_mem}")
            return idxs, gpu_mem
        log(f"waiting for 2x A100-80 >= {MIN_FREE_MIB} MiB free; current: {cards}")
        time.sleep(POLL_S)


def run(cmd, env, tag):
    log(f"RUN {tag}: {' '.join(cmd)}")
    with LOG.open("a") as f:
        p = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
    log(f"{tag} exit={p.returncode}")
    return p.returncode


def smoke_ok(raw: Path) -> bool:
    if not raw.exists():
        return False
    rows = list(csv.DictReader(raw.open()))
    got = sum(int(r["found"]) for r in rows)
    log(f"smoke rows={len(rows)} found_total={got}")
    return len(rows) >= 2 and got >= 1     # at noise 0 the tester must recover >=1 secret


def main():
    idxs, gpu_mem = wait_for_gpus()
    env = dict(os.environ)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in idxs)
    env["TMPDIR"] = str(ROOT / ".cache_run/tmp")
    env["UV_CACHE_DIR"] = str(ROOT / ".cache_run/uv")
    (ROOT / ".cache_run/tmp").mkdir(parents=True, exist_ok=True)

    base = ["uv", "run", "python", "scripts/run_eval.py", "--engine", "vllm",
            "--preset", "gemma4-31b", "--tp", "2", "--gpu_mem", str(gpu_mem)]

    smoke = base + ["--clues", "benchmark_pool/emails_lying_n2.jsonl:n2",
                    "--topics", "T02,T09", "--noise", "0", "--reps", "1",
                    "--out", "results/smoke_rubric"]
    if run(smoke, env, "SMOKE") != 0 or not smoke_ok(ROOT / "results/smoke_rubric/raw.csv"):
        log("SMOKE FAILED — aborting before full run. Inspect results/smoke_rubric + this log.")
        sys.exit(1)
    log("SMOKE PASSED — launching full sweep.")

    full = base + ["--clues", "benchmark_pool/emails_lying_n2.jsonl:n2,"
                              "benchmark_pool/emails_lying_n3.jsonl:n3",
                   "--noise", "0,10,20,30,40,50,100", "--reps", "5",
                   "--out", "results/eval_rubric"]
    rc = run(full, env, "FULL")
    log(f"FULL sweep done exit={rc}. summary -> results/eval_rubric/summary.csv")


if __name__ == "__main__":
    main()
