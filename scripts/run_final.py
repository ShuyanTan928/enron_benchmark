#!/usr/bin/env python3
"""Unattended overnight run of the FINAL benchmark plan (all API, Sonnet judge).

G1 (3 cheap testers)  : n2+n3, noise {0,100,300,600} x3   -- full difficulty sweep
G2 (2 reasoning flags): n3,    noise {600}        x3       -- one hard data point

Runs each model sequentially (robust vs OpenRouter rate limits; each run_eval is internally
parallel=8). Per-model raw.csv is written incrementally, so a mid-run failure keeps finished rows and
the orchestrator continues to the next model. When all are done it writes a combined COMPARISON table.

  uv run python scripts/run_final.py
"""
import csv
import os
import subprocess
import time
from pathlib import Path

ROOT = Path("/work6/shuyant/enron_benchmark")
OUT = ROOT / "results/eval_final"
LOG = OUT / "run.log"
N2N3 = "benchmark_pool/emails_lying_n2.jsonl:n2,benchmark_pool/emails_lying_n3.jsonl:n3"
N3 = "benchmark_pool/emails_lying_n3.jsonl:n3"
JUDGE = "anthropic/claude-sonnet-4.6"

RUNS = [   # (preset, clues, noise, solve_max_tokens)  -- order: proven-cheap first, reasoning last
    ("google/gemini-2.5-flash",    N2N3, "0,100,300,600", 3000),
    ("anthropic/claude-haiku-4.5", N2N3, "0,100,300,600", 2000),
    ("deepseek/deepseek-v4-pro",   N2N3, "0,100,300,600", 2000),
    ("openai/gpt-5.4",             N3,   "600",           4000),
    ("google/gemini-2.5-pro",      N3,   "600",           4000),
]


def log(msg):
    OUT.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load_env():
    """Inject .env (OPENROUTER_API_KEY etc.) so the subprocesses have the key regardless of shell."""
    env = dict(os.environ)
    ef = ROOT / ".env"
    if ef.exists():
        for ln in ef.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env["TMPDIR"] = str(ROOT / ".cache_run/tmp")
    env["UV_CACHE_DIR"] = str(ROOT / ".cache_run/uv")
    return env


def main():
    env = load_env()
    log(f"FINAL run: {len(RUNS)} models, judge={JUDGE}. key_present={bool(env.get('OPENROUTER_API_KEY'))}")
    for preset, clues, noise, smt in RUNS:
        slug = preset.replace("/", "_")
        outdir = OUT / slug
        cmd = ["uv", "run", "python", "scripts/run_eval.py", "--engine", "api", "--preset", preset,
               "--judge-engine", "api", "--judge-preset", JUDGE, "--clues", clues, "--noise", noise,
               "--reps", "3", "--parallel", "8", "--max-ctx", "1000000",
               "--solve-max-tokens", str(smt), "--out", str(outdir)]
        t0 = time.time()
        log(f"START {preset}  noise={noise}  clues={'n2+n3' if clues == N2N3 else 'n3'}")
        try:
            with LOG.open("a") as f:
                rc = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
            rows = sum(1 for _ in (outdir / "raw.csv").open()) - 1 if (outdir / "raw.csv").exists() else 0
            log(f"DONE  {preset}  rc={rc}  rows={rows}  ({time.time()-t0:.0f}s)")
        except Exception as e:
            log(f"ERROR {preset}: {e}")

    # -------- combined comparison table --------
    log("building COMPARISON table")
    cells = {}          # (model, config, noise) -> dict of means
    models, keys = [], []
    for preset, clues, noise, smt in RUNS:
        slug = preset.replace("/", "_")
        raw = OUT / slug / "raw.csv"
        if not raw.exists():
            continue
        models.append(preset)
        rows = list(csv.DictReader(raw.open()))
        for cfg in ("n2", "n3"):
            for nz in sorted({r["noise"] for r in rows if r["config"] == cfg}, key=int):
                c = [r for r in rows if r["config"] == cfg and r["noise"] == nz]
                if not c:
                    continue
                k = (cfg, nz)
                if k not in keys:
                    keys.append(k)
                cells[(preset, cfg, nz)] = {
                    "final": sum(float(r["final"]) for r in c) / len(c),
                    "found": sum(int(r["found"]) for r in c) / len(c),
                    "secret": sum(int(r["secret_score"]) for r in c) / len(c),
                    "recall": sum(float(r["recall"]) for r in c) / len(c)}
    keys.sort(key=lambda k: (k[0], int(k[1])))
    comp = OUT / "COMPARISON.csv"
    with comp.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model"] + [f"{c}@{n}" for c, n in keys])
        for m in models:
            w.writerow([m] + [f"{cells[(m, c, n)]['final']:.3f}" if (m, c, n) in cells else ""
                              for c, n in keys])
    # pretty text
    txt = [f"FINAL = mean(found*secret_match * recall*precision), Sonnet judge\n",
           "model".ljust(30) + "".join(f"{c}@{n}".rjust(9) for c, n in keys)]
    for m in models:
        txt.append(m.ljust(30) + "".join(
            (f"{cells[(m, c, n)]['final']:.3f}".rjust(9) if (m, c, n) in cells else "-".rjust(9))
            for c, n in keys))
    (OUT / "COMPARISON.txt").write_text("\n".join(txt) + "\n")
    log("WROTE " + str(comp) + " and COMPARISON.txt")
    log("ALL DONE")


if __name__ == "__main__":
    main()
