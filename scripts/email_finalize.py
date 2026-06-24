"""Stage 4 — embed the (already re-grounded) clue emails into the real Enron corpus.

Mechanical only (no model). Re-grounding to real identities happened at Step-3 save time, so the
clue messages already carry real names (Tana Jones, …) and real bodies (Enron, not "[firm]"). Here
each clue message becomes a real threads.jsonl-schema message — names -> real @enron.com addresses
(benchmark_pool/people.json), a <=2-email chain becomes one in-reply-to thread — and the clue threads
are mixed into noise threads sampled UNCHANGED from the real corpus, then interleaved by date into one
mailbox the detector reads. An answer key records which message_ids are the planted deception.

Provenance (the `planted` message_ids, the `_source` tag) is held out — only From/To/Date/Subject/Body
are rendered to the test model.

  uv run python scripts/email_finalize.py --clues benchmark_pool/email_generation_n2.jsonl --noise 100
  uv run python scripts/email_finalize.py --topic T02 --noise 80
"""
import argparse
import json
import random
import re
from pathlib import Path


def name_to_addr(name: str, addr_map: dict) -> str:
    name = (name or "").strip()
    if name in addr_map:
        return addr_map[name]
    return (name.lower().replace(" ", ".") or "unknown") + "@enron.com"


def _iso(date: str, j: int) -> str:
    """YYYY-MM-DD -> ISO with an ordered time so chained messages sort in send order."""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""):
        return f"{date}T{9 + 4 * j:02d}:00:00"
    return date or ""


def clue_to_thread(clue: dict, topic_id: str, addr_map: dict) -> dict:
    """One clue (1 email, or a <=2-email chain) -> one real-schema threads.jsonl thread."""
    msgs, prev = [], None
    for j, m in enumerate(clue.get("messages", [])):
        mid = f"{abs(hash((topic_id, clue.get('i'), j))) % 10**8}.{1075849000000 + j}.javamail.evans@thyme"
        body = m.get("body", "") or ""
        msgs.append({
            "message_id": mid,
            "from_addr": name_to_addr(m.get("from", ""), addr_map),
            "to_addrs": [name_to_addr(x, addr_map) for x in (m.get("to") or [])],
            "cc_addrs": [name_to_addr(x, addr_map) for x in (m.get("cc") or [])],
            "bcc_addrs": [],
            "subject": m.get("subject", "") or "",
            "date": _iso(m.get("date", ""), j),
            "in_reply_to": prev,
            "references": [prev] if prev else [],
            "body": body,
            "word_count": len(body.split()),
            "_source": "clue",                            # held out — never shown to the model
        })
        prev = mid
    return {
        "thread_id": f"clue.{topic_id}.c{clue.get('i')}",
        "subject": msgs[0]["subject"] if msgs else "",
        "messages": msgs,
        "participants": sorted({a for m in msgs for a in [m["from_addr"], *m["to_addrs"]]}),
        "date_first": msgs[0]["date"] if msgs else "",
        "date_last": msgs[-1]["date"] if msgs else "",
        "n_messages": len(msgs),
    }


def build_haystack(clue_threads, corpus_threads, *, noise_target: int, seed: int):
    """Mix clue threads with noise threads sampled UNCHANGED from the real corpus (whole threads,
    truncate on overshoot), then interleave every message by date."""
    rng = random.Random(seed)
    used = {ct["thread_id"] for ct in clue_threads}
    cand = [t for t in corpus_threads if t.get("thread_id") not in used]
    rng.shuffle(cand)

    noise, n = [], 0
    for t in cand:
        if n >= noise_target:
            break
        keep = t["messages"][: max(1, noise_target - n)]
        noise.append({**t, "messages": keep, "n_messages": len(keep)})
        n += len(keep)

    haystack = clue_threads + noise
    flat = [m for th in haystack for m in th["messages"]]
    flat.sort(key=lambda m: (m.get("date") or "", m.get("message_id") or ""))
    return haystack, noise, flat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all", help="topic id (e.g. T02) or 'all'")
    ap.add_argument("--clues", default="benchmark_pool/email_generation_n2.jsonl")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--noise", type=int, default=100, help="target number of noise emails")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--outdir", default="data/benchmark")
    args = ap.parse_args()

    objs = [json.loads(l) for l in Path(args.clues).read_text().splitlines() if l.strip()]
    objs = [o for o in objs if o.get("status", "KEPT") == "KEPT"]
    if args.topic != "all":
        objs = [o for o in objs if o.get("topic_id") == args.topic]
    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"{'topic':5} {'clues':5} {'noise':5} {'total':5}  file")
    for obj in objs:
        tid = obj.get("topic_id", "T??")
        clue_threads = [clue_to_thread(c, tid, addr_map) for c in obj.get("clues", [])]
        planted = [{"clue_i": c.get("i"), "carries": c.get("carries"),
                    "message_ids": [m["message_id"] for m in th["messages"]]}
                   for c, th in zip(obj.get("clues", []), clue_threads)]
        haystack, noise, flat = build_haystack(clue_threads, corpus, noise_target=args.noise, seed=args.seed)

        hp = outdir / f"{tid}_haystack.jsonl"
        with hp.open("w") as f:
            for t in haystack:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        (outdir / f"{tid}_answer.json").write_text(json.dumps(
            {"topic_id": tid, "answer": obj.get("answer", {}), "planted": planted,
             "clue_message_ids": [mid for p in planted for mid in p["message_ids"]]},
            ensure_ascii=False, indent=2))
        n_clue = sum(len(p["message_ids"]) for p in planted)
        print(f"{tid:5} {n_clue:5} {len(flat) - n_clue:5} {len(flat):5}  {hp}")


if __name__ == "__main__":
    main()
