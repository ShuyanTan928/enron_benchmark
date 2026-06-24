"""Step 1 finalizer — promote CHECK-written candidates into the reproducible topic pool.

Deterministic, no model. Reads `ground_topics.py`'s pending/candidates file and emits
`topics_v2.json` in the exact schema Step 2 consumes: each written candidate becomes a topic
with an assigned id (T01..), its real `enron_anchor`, and the `_grounding` / `_check` provenance
pulled from the fit-judge verdict and the CHECK gate. This replaces the old hand-assembly so the
final pool is produced by code (no manual picking) and the whole of Step 1 is reproducible.

Usage:
  uv run python scripts/ground_finalize.py --pending benchmark_pool/step1_pending.json
  uv run python scripts/ground_finalize.py --pending step1_pending.json --out benchmark_pool/topics_v2.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def to_topic(p: dict, idx: int) -> dict:
    t = p.get("topic") or {}
    v = p.get("verdict") or {}
    chk = p.get("check") or {}
    return {
        "id": f"T{idx:02d}",
        "category": t.get("category", "work"),
        "name": t.get("name", ""),
        "secret": t.get("secret", ""),
        "either_or": t.get("either_or", ""),
        "enron_anchor": p.get("anchor"),
        "_grounding": {"carrier": v.get("carrier", ""), "side_shown": v.get("side_shown", "")},
        "_check": {"decision": chk.get("decision", "write"), "reason": chk.get("reason", "")},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", default="benchmark_pool/step1_pending.json")
    ap.add_argument("--out", default="benchmark_pool/topics_v2.json")
    ap.add_argument("--require-write", action="store_true", default=True,
                    help="promote only candidates whose CHECK decision is 'write' (default on)")
    ap.add_argument("--allow-unchecked", dest="require_write", action="store_false",
                    help="also promote grounded-but-unchecked candidates (manual-gate runs)")
    args = ap.parse_args()

    pend = json.loads(Path(args.pending).read_text())
    cands = pend.get("candidates") or []

    kept = []
    for p in cands:
        chk = p.get("check") or {}
        if args.require_write and chk and chk.get("decision") != "write":
            continue                                  # CHECK said regenerate — skip
        kept.append(p)

    topics = [to_topic(p, i) for i, p in enumerate(kept, 1)]
    n_work = sum(1 for t in topics if t["category"] == "work")

    out = {
        "_about": "Step-1 topic pool (CHECK-gated). Each topic = abstract binary secret grounded "
                  "on a REAL enron_10 email. Casting (actor/victim) is done at Step 2 on the "
                  "anchor's real people; identities kept real here. Produced by "
                  "scripts/ground_finalize.py from the pending pool — no hand assembly.",
        "_provenance": {
            "model": pend.get("model"),
            "checker": pend.get("checker"),
            "config": pend.get("config"),
            "promoted": f"{len(topics)} written ({n_work} work / {len(topics) - n_work} casual) "
                        f"of {len(cands)} candidates",
            "pending_file": args.pending,
        },
        "topics": topics,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"WROTE {args.out}  ({len(topics)} topics: {n_work} work / {len(topics)-n_work} casual; "
          f"from {len(cands)} candidates)")
    for t in topics:
        print(f"  {t['id']}  [{t['category']}]  «{t['name']}»  -> "
              f"{(t['enron_anchor'] or {}).get('date','')[:10]}")


if __name__ == "__main__":
    main()
