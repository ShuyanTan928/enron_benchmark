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
import sys
import textwrap
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.grounding.retrieval import BM25, tokenize          # noqa: E402  (BM25 over the corpus to find the event cluster)

# --- Enron-native normalization -------------------------------------------------------------
# Real Enron plaintext mail is pure ASCII, hard-wrapped at ~75 cols. The generator emits long
# unwrapped paragraphs with em-dashes / curly quotes — a one-regex giveaway for the planted
# emails. Normalize at assembly time so a clue message is byte-shape-indistinguishable from corpus.
_ASCII_SUBS = {
    "—": "--", "–": "-", "‒": "-", "―": "--",        # em/en/figure/horiz dash
    "‘": "'", "’": "'", "“": '"', "”": '"',          # curly quotes
    "…": "...", "•": "-", "·": "-", "‐": "-", "‑": "-",
    " ": " ", " ": " ", " ": " ", "​": "", "﻿": "",
}


def to_ascii(s: str) -> str:
    for k, v in _ASCII_SUBS.items():
        s = s.replace(k, v)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def normalize_body(body: str, width: int = 75) -> str:
    """ASCII-fold and hard-wrap each line to ~width cols (preserving blank lines / line breaks),
    matching the real corpus shape (median max line 77, ~61% wrapped)."""
    out = []
    for line in to_ascii(body or "").split("\n"):
        if line.strip() == "":
            out.append("")
        else:
            out.extend(textwrap.wrap(line, width=width, break_long_words=False,
                                     break_on_hyphens=False) or [""])
    return "\n".join(out)


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


def scrub_labels(text: str) -> str:
    """Strip anonymized-label residue (Person A-J) that survived name-regrounding inside filenames /
    handles — e.g. 'Portfolio_Audit_H.pdf', 'MedCert_PersonC_Oct13.pdf' — which would otherwise leak
    the anonymization scheme. The residue is only a HANDLE, so stripping it consistently across clues
    keeps the shared-reference link intact."""
    if not text:
        return text
    text = re.sub(r"[_-]?Person[ _]?[A-J](?![A-Za-z])", "", text)   # PersonC / _PersonC (also before '_')
    text = re.sub(r"[_-]([A-J])(?=[_.])", "", text)         # _H. , _H_
    text = re.sub(r"\b([A-J])[_-](?=[A-Z])", "", text)      # H_Status -> Status
    text = re.sub(r"[_-]{2,}", "_", text)                   # collapse doubled separators
    return text


def clamp_era(date: str) -> str:
    """Force an out-of-corpus year into the 1999-2002 range (default 2001), preserving month/day, so a
    generator's anachronistic date (e.g. 2024-05-10) does not stick out in a 2000-2001 haystack."""
    mo = re.match(r"(\d{4})(-\d{2}-\d{2}.*)$", date or "")
    if mo and not (1999 <= int(mo.group(1)) <= 2002):
        return "2001" + mo.group(2)
    return date or ""


def clue_to_thread(clue: dict, topic_id: str, addr_map: dict) -> dict:
    """One clue (1 email, or a <=2-email chain) -> one real-schema threads.jsonl thread."""
    msgs, prev = [], None
    for j, m in enumerate(clue.get("messages", [])):
        mid = f"{abs(hash((topic_id, clue.get('i'), j))) % 10**8}.{1075849000000 + j}.javamail.evans@thyme"
        body = normalize_body(scrub_labels(m.get("body", "") or ""))   # ASCII + hard-wrap + label scrub
        msgs.append({
            "message_id": mid,
            "from_addr": name_to_addr(m.get("from", ""), addr_map),
            "to_addrs": [name_to_addr(x, addr_map) for x in (m.get("to") or [])],
            "cc_addrs": [name_to_addr(x, addr_map) for x in (m.get("cc") or [])],
            "bcc_addrs": [],
            "subject": to_ascii(scrub_labels(m.get("subject", "") or "")),
            "date": _iso(clamp_era(m.get("date", "")), j),                # anachronistic year -> corpus era
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


def _thread_text(t: dict) -> str:
    return (t.get("subject", "") or "") + " " + " ".join(m.get("body", "") or "" for m in t["messages"])


def event_cluster_tids(anchor: dict, query: str, corpus_threads, bm: BM25, *, topn: int,
                       floor: float) -> set:
    """thread_ids of the real corpus mail that would CONTRADICT the planted secret, so that none of it
    lands in the haystack. Two ways in:

      1. the anchor's own thread, matched exactly by message_id;
      2. everything the corpus says about the SECRET'S CARRIER — BM25 over `query` (the carrier and the
         true_fact), top-N over an absolute and a relative floor.

    (2) is keyed on the secret, not on the anchor's text, because the secret is what the haystack must
    not contradict. The anchor donates the carrier and is then beside the point: retrieving on its whole
    body pulls in whatever else it happened to be about, and misses real mail about the carrier that the
    anchor never mentioned."""
    anchor = anchor or {}
    mid = anchor.get("message_id", "")
    tids = set()
    if mid:                                                 # 1. exact: the anchor's own thread
        for t in corpus_threads:
            if any(m.get("message_id") == mid for m in t["messages"]):
                tids.add(t["thread_id"])
    if (query or "").strip():                               # 2. related: BM25 top-N over the SECRET
        sc = bm.scores(tokenize(query))
        order = sorted(range(len(corpus_threads)), key=lambda i: sc[i], reverse=True)
        top = float(sc[order[0]]) if len(order) else 0.0
        for i in order[:topn]:
            if sc[i] >= floor and sc[i] >= 0.15 * top:
                tids.add(corpus_threads[i]["thread_id"])
    return tids


def secret_query(obj: dict, anchor: dict | None) -> str:
    """What the haystack must not contradict: the carrier + the truth. Falls back to the anchor's text
    for older records that predate the carrier field."""
    ans = obj.get("answer") or {}
    parts = [obj.get("_carrier", ""), ans.get("true_fact", ""), ans.get("concealment", "")]
    q = " ".join(p for p in parts if p).strip()
    return q or ((anchor or {}).get("text", "") or "")


def build_haystack(clue_threads, corpus_threads, anchor, query, bm, *, noise_target: int, seed: int,
                   related_topn: int = 20, related_floor: float = 2.0):
    """Excise the real event cluster, borrow its ids for the clues, then mix the clue threads with
    noise sampled UNCHANGED from the rest of the corpus and scatter them randomly through the pile.

    (1) Find the anchor's thread + every thread the corpus has about the secret's carrier, and pull
        them ALL out of the noise pool — they tell the true story and must never appear in the haystack.
    (2) Borrow REAL Message-IDs for the clue messages, PRIORITY = ids from those removed cluster
        threads (so the anchor's own id now belongs to a clue, not to any corpus mail in the pile);
        every source thread is out of the pile, so no clue id can collide with a noise id.
    (3) If the cluster doesn't yield enough ids, pull whole RANDOM threads out of the pool and borrow
        theirs too (removed from noise, so still no collision)."""
    rng = random.Random(seed)
    clue_tids = {ct["thread_id"] for ct in clue_threads}

    cluster_tids = event_cluster_tids(anchor, query, corpus_threads, bm, topn=related_topn,
                                      floor=related_floor)
    cluster = [t for t in corpus_threads if t["thread_id"] in cluster_tids]
    cand = [t for t in corpus_threads
            if t["thread_id"] not in cluster_tids and t["thread_id"] not in clue_tids]
    rng.shuffle(cand)

    n_need = sum(len(ct["messages"]) for ct in clue_threads)
    cluster_ids = [m["message_id"] for t in cluster for m in t["messages"] if m.get("message_id")]
    rng.shuffle(cluster_ids)
    borrow = list(cluster_ids)                              # (2) cluster ids first
    pulled = 0
    while len(borrow) < n_need and pulled < len(cand):      # (3) fallback: pull whole random threads
        borrow += [m["message_id"] for m in cand[pulled]["messages"] if m.get("message_id")]
        pulled += 1
    cand = cand[pulled:]                                    # the pulled threads leave the noise pool
    if len(borrow) < n_need:
        raise SystemExit(f"corpus too small to borrow {n_need} message ids (have {len(borrow)})")

    bi = 0
    for ct in clue_threads:
        idmap = {}
        for m in ct["messages"]:
            idmap[m["message_id"]] = borrow[bi]
            m["message_id"] = borrow[bi]
            bi += 1
        for m in ct["messages"]:                            # relink the chain to the borrowed ids
            if m.get("in_reply_to") in idmap:
                m["in_reply_to"] = idmap[m["in_reply_to"]]
            m["references"] = [idmap.get(r, r) for r in (m.get("references") or [])]

    noise, n = [], 0
    for t in cand:
        if n >= noise_target:
            break
        keep = t["messages"][: max(1, noise_target - n)]
        noise.append({**t, "messages": keep, "n_messages": len(keep)})
        n += len(keep)

    haystack = clue_threads + noise
    rng.shuffle(haystack)                       # scatter clue threads randomly (not a date cluster)
    flat = [m for th in haystack for m in th["messages"]]
    return haystack, noise, flat, sorted(cluster_tids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all", help="topic id (e.g. T02) or 'all'")
    ap.add_argument("--clues", default="benchmark_pool/email_generation_n2.jsonl")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--noise", type=int, default=100, help="target number of noise emails")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--outdir", default="data/benchmark")
    ap.add_argument("--topics", default="", help="topics file (id->anchor) used ONLY for records that "
                    "lack a self-carried _anchor; the record's _anchor always wins")
    ap.add_argument("--related-topn", type=int, default=20, help="max related threads to excise per topic")
    ap.add_argument("--related-floor", type=float, default=2.0, help="min BM25 score for a related thread")
    args = ap.parse_args()

    objs = [json.loads(l) for l in Path(args.clues).read_text().splitlines() if l.strip()]
    objs = [o for o in objs if o.get("status", "KEPT") == "KEPT"]
    if args.topic != "all":
        objs = [o for o in objs if o.get("topic_id") == args.topic]
    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}

    # id -> anchor fallback for legacy records that don't self-carry _anchor
    topics_anchor = {}
    if args.topics:
        for kept in json.loads(Path(args.topics).read_text()).get("kept", []):
            a = kept.get("anchor", {}) or {}
            topics_anchor[kept.get("id")] = {"message_id": a.get("message_id", ""),
                                             "text": kept.get("anchor_full_body") or a.get("snippet", "")}

    bm = BM25([tokenize(_thread_text(t)) for t in corpus])   # one index over the corpus, reused per topic

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"{'topic':5} {'clues':5} {'noise':5} {'cut':4} {'total':5}  file")
    for obj in objs:
        tid = obj.get("topic_id", "T??")
        anchor = obj.get("_anchor") or topics_anchor.get(tid)
        if not anchor:
            print(f"  WARNING {tid}: no anchor (record has no _anchor, not in --topics) — event cluster NOT excised")
        clue_threads = [clue_to_thread(c, tid, addr_map) for c in obj.get("clues", [])]
        haystack, noise, flat, cut = build_haystack(
            clue_threads, corpus, anchor, secret_query(obj, anchor), bm,
            noise_target=args.noise, seed=args.seed,
            related_topn=args.related_topn, related_floor=args.related_floor)
        planted = [{"clue_i": c.get("i"), "carries": c.get("carries"),    # after id-borrowing
                    "message_ids": [m["message_id"] for m in th["messages"]]}
                   for c, th in zip(obj.get("clues", []), clue_threads)]

        hp = outdir / f"{tid}_haystack.jsonl"
        with hp.open("w") as f:
            for t in haystack:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        (outdir / f"{tid}_answer.json").write_text(json.dumps(
            {"topic_id": tid, "answer": obj.get("answer", {}), "planted": planted,
             "clue_message_ids": [mid for p in planted for mid in p["message_ids"]],
             "excised_event_threads": cut},
            ensure_ascii=False, indent=2))
        n_clue = sum(len(p["message_ids"]) for p in planted)
        print(f"{tid:5} {n_clue:5} {len(flat) - n_clue:5} {len(cut):4} {len(flat):5}  {hp}")


if __name__ == "__main__":
    main()
