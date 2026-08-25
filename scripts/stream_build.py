#!/usr/bin/env python3
"""Streaming benchmark generation — one topic goes end-to-end before the next, for ONE clue count n.

Each run targets a single `--n` and a per-register TOTAL (`--n-work` / `--n-casual`): that many KEPT
results for the register, commission + paltering COMBINED. commission vs paltering is internal — for each
topic we try the CURRENTLY-RARER mechanism first and fall back to the other, so the kept set drifts to 5:5.

Topics are POOLED. A topic that produced a KEPT result (at any n) is persisted to `--pool-file` with its
atoms. A later run for a DIFFERENT n reuses those pooled topics first — no topic re-generation, and atoms
are reused when the mechanism matches — before generating any new topics. So you can fill n=2 first, then
run --n 3 and it rides the same topics.

  # first pass, n=2
  uv run python scripts/stream_build.py --n 2 --n-work 20 --n-casual 20 --gen-preset or-claude-sonnet \
      --probe-presets openai/gpt-5.6-sol --judge-preset openai/gpt-5.6-terra
  # second pass, n=3 — reuses the pooled topics from the n=2 run
  uv run python scripts/stream_build.py --n 3 --n-work 20 --n-casual 20 ...
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from atomize_build import (make_atoms, plan_distribution, run_topic, reground_atoms_record,      # noqa: E402
                           name_maps, _merge, render_readable)
from plot_assemble import make_relabel                                                           # noqa: E402
from src.models.engine_factory import build_engine                                               # noqa: E402
from src.grounding.corpus import load_emails                                                     # noqa: E402
from src.grounding.retrieval import HybridRetriever                                              # noqa: E402
from src.grounding.pipeline import propose_grounding, propose_ungrounded                         # noqa: E402

MECHS = ("commission", "paltering")


def serialize_entry(p: dict, tid: str, category: str) -> dict:
    """Turn a propose_grounding / propose_ungrounded result into the entry make_atoms expects: an id,
    the (abstract) topic, and — for work — the picked anchor serialized to a dict + its full body."""
    anchors = p.get("anchors") or []
    best = anchors[0] if anchors else None
    anchor = best.anchor_dict() if best else p.get("anchor")
    return {
        "id": tid,
        "category": category,
        "topic": p["topic"],
        "anchor": anchor,
        "anchor_full_body": (best.body[:1500] if best else p.get("anchor_full_body", "")),
    }


def _atoms_for(pe: dict, mech: str, engines: dict, team, relabel, atoms_iters: int, gen_temp: float):
    """Atoms for this pooled topic + mechanism — reuse the cached ones (no re-atomize) or make + cache."""
    cached = (pe.get("atoms") or {}).get(mech)
    if cached:
        return cached
    atoms, _v, _log = make_atoms(engines["gen"], engines["jud"], pe["entry"], relabel, team,
                                 atoms_iters, gen_temp, mech)
    if atoms:
        pe.setdefault("atoms", {})[mech] = atoms
    return atoms


def _build_at_n(entry: dict, atoms: dict, n: int, engines: dict, team, budgets, names):
    """plan -> plot -> email -> AND-check (with iteration) for ONE n — atoms already in hand.
    Returns (row|None, status). status in {KEPT, DROP, N_INFEASIBLE}."""
    gen, joint, solo, diag, jud = (engines[k] for k in ("gen", "joint", "solo", "diag", "jud"))
    full_nm, first_nm = names
    era = (entry.get("anchor") or {}).get("date", "")[:7]
    era = era if era >= "1999" else ((atoms.get("era", "") or "")[:7] or "2001-06")
    plan, err = plan_distribution(atoms, n)
    if err:
        return None, "N_INFEASIBLE"
    accepted, log = run_topic(gen, solo, joint, diag, atoms, plan, team, n, era, budgets,
                              iterate=True, judge=jud)
    if not accepted:
        return None, "DROP"
    rep = (log[-1] if log else {}).get("report", {})
    anc = entry.get("anchor", {}) or {}
    anon = {"topic_id": entry["id"], "n": n, "atoms": atoms, "plan": plan, "clues": accepted,
            "status": "KEPT",
            "check": {"joint": f"{rep.get('joint_votes')}/{rep.get('n_joint')}", "leaks": rep.get("leaks", [])},
            "_carrier": (entry.get("topic") or {}).get("carrier", ""),
            "_anchor": {"message_id": anc.get("message_id", ""),
                        "text": entry.get("anchor_full_body") or anc.get("snippet", "")}}
    return reground_atoms_record(anon, atoms, full_nm, first_nm), "KEPT"


def try_topic(pe: dict, n: int, engines, team, relabel, budgets, atoms_iters, gen_temp, names, tally):
    """Build this pooled topic at n, minority-first over mechanism, keep the FIRST that passes.
    Returns (row|None, mech|None)."""
    for mech in sorted(MECHS, key=lambda m: tally[m]):
        atoms = _atoms_for(pe, mech, engines, team, relabel, atoms_iters, gen_temp)
        if not atoms:
            continue
        row, status = _build_at_n(pe["entry"], atoms, n, engines, team, budgets, names)
        if status == "KEPT":
            return row, mech
    return None, None


def stream_register(category, target, n, budget, engines, team, relabel, budgets, atoms_iters,
                    gen_temp, names, retriever, emails, tally, out_rows, pool, built_ids,
                    id_prefix, grounded, checkpoint):
    """Produce `target` TOTAL KEPT results for this register at clue count `n`. Reuse pooled topics of
    this category first (no topic-gen; atoms reused when the mechanism matches), then generate new ones
    until the target is met or the topic budget is spent. New KEPT topics are appended to `pool`.
    `checkpoint()` is called after every KEPT item so a crash never loses more than the item in flight;
    `built_ids` (tids already on disk at this n) lets a restart RESUME instead of over-generating."""
    kept = sum(1 for t in built_ids if t.startswith(id_prefix))       # RESUME: already-built count this run
    reuse = [pe for pe in pool if pe.get("category") == category]
    print(f"\n=== {category.upper()}  target(total)={target}  n={n}  pooled={len(reuse)}  "
          f"already-built={kept}  budget={budget} ===")
    if kept >= target:
        print(f"  {category}: already {kept}/{target} at n={n} — nothing to do")
        return kept

    # 1) REUSE pooled topics — skip any already built at THIS n
    for pe in reuse:
        if kept >= target:
            break
        if pe["tid"] in built_ids:
            continue
        row, mech = try_topic(pe, n, engines, team, relabel, budgets, atoms_iters, gen_temp, names, tally)
        if row:
            out_rows.setdefault((mech, n), {})[pe["tid"]] = row
            tally[mech] += 1
            kept += 1
            checkpoint()                                              # flush to disk after every KEPT
            print(f"  [reuse {category}] KEPT «{pe['tid']}» {mech[:3]}  "
                  f"(total {kept}/{target}; com/pal {tally['commission']}/{tally['paltering']})")
        else:
            print(f"  [reuse {category}] DROP «{pe['tid']}»  (pooled topic made no valid n={n})")

    # 2) GENERATE new topics to fill the rest
    accepted = [pe["entry"]["topic"] for pe in reuse]
    rejected: list[dict] = []
    used_anchors = {pe["entry"].get("anchor", {}).get("message_id")
                    for pe in reuse if pe["entry"].get("anchor")}
    used_anchors.discard(None)
    seq = max([int(pe["tid"][len(id_prefix):]) for pe in pool
               if pe["tid"].startswith(id_prefix) and pe["tid"][len(id_prefix):].isdigit()] + [0])
    attempts = 0
    while kept < target and attempts < budget:
        attempts += 1
        if grounded:
            p = propose_grounding(engines["gen"], retriever, emails, category, accepted,
                                  used_anchors=used_anchors, seen=accepted + rejected)
        else:
            p = propose_ungrounded(engines["gen"], category, accepted, seen=accepted + rejected)
        if p.get("status") != "grounded":
            if p.get("topic") and p["status"] not in ("gen_error", "hyde_error", "spec_error"):
                rejected.append(p.get("abstract_topic") or p["topic"])
            print(f"  [gen {category} {attempts}/{budget}] {p.get('status', '?').upper():12} (topic rejected)")
            continue
        seq += 1
        tid = f"{id_prefix}{seq:02d}"
        pe = {"tid": tid, "category": category, "entry": serialize_entry(p, tid, category), "atoms": {}}
        row, mech = try_topic(pe, n, engines, team, relabel, budgets, atoms_iters, gen_temp, names, tally)
        if row:
            out_rows.setdefault((mech, n), {})[tid] = row
            tally[mech] += 1
            kept += 1
            pool.append(pe)                                    # persist ONLY topics that produced a result
            accepted.append(p.get("abstract_topic") or p["topic"])
            mid = (pe["entry"].get("anchor") or {}).get("message_id")
            if mid:
                used_anchors.add(mid)
            checkpoint()                                       # flush emails + pool to disk after every KEPT
            print(f"  [gen {category} {attempts}/{budget}] KEPT «{tid}» {mech[:3]}  "
                  f"(total {kept}/{target}; com/pal {tally['commission']}/{tally['paltering']})")
        else:
            rejected.append(p.get("abstract_topic") or p["topic"])
            print(f"  [gen {category} {attempts}/{budget}] DROP «{tid}»  (no mechanism passed at n={n})")
    print(f"  {category} done: {kept}/{target} at n={n}  (reused pool + {attempts} gen attempts)")
    return kept


def load_pool(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def existing_tids_at_n(out_dir: Path, n: int) -> set:
    """tids already built at this n (across mechanisms) — so a re-run doesn't rebuild them."""
    tids = set()
    for f in glob.glob(str(out_dir / f"emails_*_n{n}.jsonl")):
        for l in Path(f).read_text().splitlines():
            if l.strip():
                tids.add(json.loads(l)["topic_id"])
    return tids


def existing_mech_counts(out_dir: Path, n: int) -> dict:
    """commission/paltering counts already on disk at this n — so a RESUMED run keeps the 5:5 balance."""
    c = {"commission": 0, "paltering": 0}
    for f in glob.glob(str(out_dir / f"emails_*_n{n}.jsonl")):
        mech = "commission" if "commission" in Path(f).name else "paltering"
        c[mech] += sum(1 for l in Path(f).read_text().splitlines() if l.strip())
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True, help="clue count for THIS run (required)")
    ap.add_argument("--n-work", type=int, default=10, help="TOTAL work results (commission + paltering)")
    ap.add_argument("--n-casual", type=int, default=10, help="TOTAL casual results (commission + paltering)")
    ap.add_argument("--topic-budget", type=int, default=40, help="max NEW topics attempted PER register")
    ap.add_argument("--pool-file", default="benchmark_pool/stream_pool.jsonl",
                    help="persisted topics+atoms; reused across n-runs so topics aren't regenerated")
    ap.add_argument("--engine", choices=["api", "vllm"], default="api",
                    help="vllm = LOCAL plumbing test: one gemma serves gen+probe+judge (plumbing only)")
    ap.add_argument("--preset", default="gemma4-31b", help="local vllm model (when --engine vllm)")
    ap.add_argument("--gpus", default="6,7", help="CUDA_VISIBLE_DEVICES for the local model")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--model-len", type=int, default=0, help="cap local model context (0=preset default)")
    ap.add_argument("--gen-preset", default="or-claude-sonnet", help="generator (topic + atoms + clues)")
    ap.add_argument("--gen-engine", default="api")
    ap.add_argument("--probe-presets", default="openai/gpt-5.6-sol", help="joint AND-check prober(s)")
    ap.add_argument("--solo-probe-presets", default="", help="subset-leak prober(s); default = joint[0]")
    ap.add_argument("--judge-preset", default="openai/gpt-5.6-terra", help="secret-match judge (light)")
    ap.add_argument("--budgets", default="3,5", help="email-retry budget, summed")
    ap.add_argument("--atoms-iters", type=int, default=3)
    ap.add_argument("--gen-temp", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out-dir", default="benchmark_pool")
    args = ap.parse_args()

    budgets = [int(x) for x in args.budgets.split(",") if x.strip()]
    if args.engine == "vllm":
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpus

    print("Loading corpus + BM25…")
    emails = load_emails()
    retriever = HybridRetriever([e.index_text for e in emails])

    if args.engine == "vllm":                       # LOCAL plumbing test: one model does everything
        eng = build_engine("vllm", args.preset, tp=args.tp, gpu_mem=args.gpu_mem,
                           max_model_len=(args.model_len or None))
        engines = {"gen": eng, "jud": eng, "joint": [eng], "solo": [eng], "diag": eng}
        print(f"LOCAL smoke: gen=judge=probe = vllm:{args.preset} (gpus={args.gpus}, tp={args.tp}) "
              f"— separation-of-duties OFF, plumbing only")
    else:
        def _eng(p):
            return build_engine("api", p)
        gen = build_engine(args.gen_engine, args.gen_preset)
        joint = [_eng(p.strip()) for p in args.probe_presets.split(",") if p.strip()]
        solo = [_eng(p.strip()) for p in args.solo_probe_presets.split(",") if p.strip()] or [joint[0]]
        jud = _eng(args.judge_preset)
        engines = {"gen": gen, "jud": jud, "joint": joint, "solo": solo, "diag": joint[0]}

    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    relabel = make_relabel(P)
    team = "\n".join(["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
                     + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH])
    names = name_maps()

    pool_path = Path(args.pool_file)
    pool = load_pool(pool_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    built_ids = existing_tids_at_n(out_dir, args.n)
    tally = existing_mech_counts(out_dir, args.n)   # RESUME-aware 5:5 balance (0/0 on a fresh run)
    out_rows: dict = {}

    def checkpoint():
        """Flush every KEPT item (merge-safe) + the topic pool to disk, so a crash loses at most the
        item in flight and a restart resumes from here. Called after every KEPT."""
        for (mech, k), rows in out_rows.items():
            path = out_dir / f"emails_{mech}_n{k}.jsonl"
            keyed = {f"{r['topic_id']}_n{r['n']}": r for r in rows.values()}   # match _merge's _row_key
            merged = _merge(path, keyed)
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n")
        pool_path.parent.mkdir(parents=True, exist_ok=True)
        pool_path.write_text("\n".join(json.dumps(pe, ensure_ascii=False) for pe in pool) + "\n")

    print(f"gen={args.gen_preset}  probe={args.probe_presets}  judge={args.judge_preset}  "
          f"n={args.n}  targets: work={args.n_work} casual={args.n_casual}  "
          f"pool={len(pool)} topics, already-built-at-n{args.n}={len(built_ids)} (com/pal {tally})")

    t0 = time.time()
    if args.n_work > 0:
        stream_register("work", args.n_work, args.n, args.topic_budget, engines, team, relabel, budgets,
                        args.atoms_iters, args.gen_temp, names, retriever, emails, tally, out_rows,
                        pool, built_ids, "W", True, checkpoint)
    if args.n_casual > 0:
        stream_register("casual", args.n_casual, args.n, args.topic_budget, engines, team, relabel, budgets,
                        args.atoms_iters, args.gen_temp, names, retriever, emails, tally, out_rows,
                        pool, built_ids, "C", False, checkpoint)

    checkpoint()                                    # final flush (also covers the "already complete" case)
    for (mech, n), rows in sorted(out_rows.items()):
        path = out_dir / f"emails_{mech}_n{n}.jsonl"
        merged = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        path.with_suffix(".txt").write_text(render_readable(merged))   # readable dump: once, at the end
        print(f"WROTE {path}  ({len(merged)} total)")
    print(f"POOL {pool_path}  ({len(pool)} topics)")
    print(f"\nDONE  com/pal = {tally['commission']}/{tally['paltering']}  ({time.time()-t0:.0f}s)")
    from src.models.api_engine import usage_report
    u = usage_report()
    if u:
        print("=== API usage (this run) ===")
        tot = 0.0
        for model, r in sorted(u.items()):
            print(f"  {model:34s} calls={r['calls']:4d}  in={r['in']:>10,}  out={r['out']:>10,}  ${r['cost']:.3f}")
            tot += r["cost"]
        print(f"  TOTAL (OpenRouter-reported): ${tot:.3f}")


if __name__ == "__main__":
    main()
