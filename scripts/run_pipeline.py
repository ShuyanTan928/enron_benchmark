#!/usr/bin/env python3
"""Full gemma4-31B demo: Step 1 -> 2 -> 3 for example topics, dumped to a readable txt.

Loads gemma ONCE, then for each topic:
  STEP 1 : the topic (from topics_v2.json — gemma-generated in step 1)
  STEP 2 : generate planted-secret plot + judge (A-G) -> iterate   (gemma gen + gemma judge)
  STEP 3 : split into clues + AND-validate (solo/joint probe + match) -> iterate (all gemma)
scrub_corp is applied to the model OUTPUTS before dumping, and an anonymization check (Enron +
the 10 cast real names) is reported per step, so anonymization + structure can be eyeballed.

Usage:
  CUDA_VISIBLE_DEVICES=0,1 uv run python scripts/run_pipeline.py --topics T02,T05
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import plot_iterate as s2
import email_generate as s3
import email_finalize as s4
from plot_assemble import scrub_corp

PEOPLE = json.loads(Path("benchmark_pool/people.json").read_text())["people"]


def banner(t):
    return "\n" + "=" * 80 + "\n  " + t + "\n" + "=" * 80


def anon_check(text):
    bad = []
    if re.search(r"\benron\b", text, re.I):
        bad.append("Enron")
    for p in PEOPLE:
        for nm in {p["real_name"], p["real_name"].split()[0], p["real_name"].split()[-1]}:
            if re.search(r"\b" + re.escape(nm) + r"\b", text):
                bad.append(nm)
    return sorted(set(bad))


def fmt_clue(c):
    out = [f"  ── clue {c.get('i')}   carries={c.get('carries')}"]
    for m in c.get("messages", []):
        to = ", ".join(m.get("to", []) or [])
        cc = ", ".join(m.get("cc", []) or [])
        out.append(f"     From: {m.get('from')}   To: {to}" + (f"   Cc: {cc}" if cc else "")
                   + f"   ({m.get('date')})")
        out.append(f"     Subject: {m.get('subject')}")
        out.append(f"       {scrub_corp(m.get('body', ''))}")
    return "\n".join(out)


def assemble(script, *extra):
    subprocess.run([sys.executable, f"scripts/{script}", *extra], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="T02,T05")
    ap.add_argument("--engine", choices=["vllm", "api"], default="vllm")
    ap.add_argument("--preset", default="gemma4-31b")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--noise", type=int, default=30, help="Step 4 noise emails per topic")
    ap.add_argument("--out", default="benchmark_pool/demo_pipeline_t02_t05.txt")
    args = ap.parse_args()
    tids = args.topics.split(",")

    topics = {t["id"]: t for t in json.loads(Path("benchmark_pool/topics_v2.json").read_text())["topics"]}
    corpus = [json.loads(l) for l in Path("data/enron_10/threads.jsonl").read_text().splitlines() if l.strip()]
    anon_addr, anon_text = s4.build_anonymizers(PEOPLE)
    for tid in tids:
        assemble("plot_assemble.py", "--topic", tid, "--outdir", "/tmp/demo_s2")

    from src.models.engine_factory import build_engine
    print(f"loading {args.engine}:{args.preset} tp={args.tp} ...")
    eng = build_engine(args.engine, args.preset, tp=args.tp)

    report = []
    for tid in tids:
        t = topics[tid]
        a = t["enron_anchor"]
        anchor_txt = scrub_corp(a.get("snippet") or a.get("body", ""))
        report.append("\n".join([
            banner(f"STEP 1 — Topic {tid}: {t.get('name')}   (gemma-generated topic)"),
            f"category  : {t.get('category')}",
            f"secret    : {t.get('secret')}",
            f"either_or : {t.get('either_or')}",
            "ANCHOR (real corpus email, company scrubbed):",
            f"  From: {scrub_corp(str(a.get('from')))}   Subject: {scrub_corp(str(a.get('subject')))}   ({str(a.get('date'))[:10]})",
            f"  {anchor_txt}",
            f"[anon check] residual cast/Enron in shown text: {anon_check(anchor_txt) or 'CLEAN'}",
        ]))
        print(f"[{tid}] step1 done")

        # ---------- STEP 2 ----------
        base = Path(f"/tmp/demo_s2/{tid}.txt").read_text()
        ctx = s2.context_of(base)
        prompt, secret, log = base, None, []
        for it in range(1, args.max_iters + 1):
            raw = eng.generate(prompt, max_tokens=3072, temperature=0.5)[0]
            cand = s2.extract_json(raw)
            if not cand:
                log.append(f"  iter{it}: parse_fail")
                prompt = base + "\n\n## CORRECTION\nReturn ONE JSON object, nothing else."
                continue
            v, _ = s2.judge(eng, ctx, cand)
            ok = s2.all_pass(v)
            verds = {c: (v.get(c) or {}).get("verdict") for c in s2.CRITERIA} if v else None
            log.append(f"  iter{it}: {'PASS' if ok else 'fail'}  {verds}")
            if ok:
                secret = cand
                break
            prompt = base + "\n\n## CORRECTION REQUIRED\n" + s2.feedback_from(v)
        block = [banner(f"STEP 2 — Planted secret {tid}   (gemma gen + gemma A-G judge)"),
                 "judge iterations:", *log]
        if secret:
            plot = scrub_corp(secret.get("plot", ""))
            block += [f"\nactor     : {scrub_corp(secret.get('actor',''))}",
                      f"victim    : {scrub_corp(secret.get('victim',''))}",
                      f"casting   : {secret.get('casting_note')}",
                      f"true_fact : {scrub_corp(secret.get('true_fact',''))}",
                      f"false     : {scrub_corp(secret.get('false_belief',''))}",
                      f"PLOT:\n{plot}",
                      f"\n[anon check] residual cast/Enron in plot: {anon_check(plot) or 'CLEAN'}"]
        else:
            block += ["\n** DROPPED — no candidate passed the A-G judge in "
                      f"{args.max_iters} iters **"]
        report.append("\n".join(block))
        print(f"[{tid}] step2 done (kept={secret is not None})")
        if not secret:
            continue

        # ---------- STEP 3 ----------
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        tmp.write_text(json.dumps(secret, ensure_ascii=False) + "\n")
        assemble("email_assemble.py", "--secrets", str(tmp), "--topic", tid,
                 "--n", str(args.n), "--outdir", "/tmp/demo_s3")
        base3 = Path(f"/tmp/demo_s3/{tid}.txt").read_text()
        prompt, clues, log = base3, None, []
        for it in range(1, args.max_iters + 1):
            raw = eng.generate(prompt, max_tokens=3500, temperature=0.5)[0]
            parsed = s3.extract_json(raw)
            cl = (parsed or {}).get("clues")
            if not cl:
                log.append(f"  iter{it}: parse_fail")
                prompt = base3 + "\n\n## REVISE\nReturn ONE JSON object with a 'clues' array."
                continue
            okk, rep = s3.validate(eng, cl, secret)
            log.append(f"  iter{it}: {'PASS' if okk else 'fail'}  "
                       f"leaks={rep['leaks']} joint_ok={rep['joint_ok']}")
            if okk:
                clues = cl
                break
            prompt = base3 + "\n\n## REVISE\n" + s3.feedback_from(rep)
        block = [banner(f"STEP 3 — Distributed clues {tid}   (n={args.n}, gemma gen + gemma AND-validation)"),
                 "validation iterations (solo must NOT leak, joint MUST recover):", *log, ""]
        if clues:
            block += [fmt_clue(c) for c in clues]
            allbody = " ".join(scrub_corp(m.get("body", "")) for c in clues for m in c.get("messages", []))
            block += [f"\n[anon check] residual cast/Enron across clue bodies: {anon_check(allbody) or 'CLEAN'}"]
        else:
            block += [f"** DROPPED — clues failed AND-validation in {args.max_iters} iters **"]
        report.append("\n".join(block))
        print(f"[{tid}] step3 done (kept={clues is not None})")
        if not clues:
            continue

        # ---------- STEP 4 ----------
        obj = {"topic_id": tid, "clues": clues}
        clue_threads, planted = s4.step3_to_threads(obj)
        haystack, noise, flat = s4.build_haystack(
            clue_threads, corpus, anon_addr, anon_text, noise_target=args.noise, seed=20260620)
        clue_ids = {mid for p in planted for mid in p["message_ids"]}
        b4 = [banner(f"STEP 4 — Full-email format + embed into corpus  {tid}   (mechanical, no model)"),
              "converted clue emails (threads.jsonl schema, anonymized addresses):", ""]
        for th in clue_threads:
            for m in th["messages"]:
                b4 += [f"  message_id : {m['message_id']}",
                       f"  from -> to : {m['from_addr']}  ->  {', '.join(m['to_addrs'])}"
                       + (f"   cc {', '.join(m['cc_addrs'])}" if m['cc_addrs'] else ""),
                       f"  date       : {m['date']}    in_reply_to: {m['in_reply_to']}    words: {m['word_count']}",
                       f"  subject    : {m['subject']}",
                       f"  body       : {m['body']}", ""]
        clue_body = " ".join(m.get("body", "") for t in clue_threads for m in t["messages"])
        b4.append(f"[anon check] residual cast/Enron in clue emails: {anon_check(clue_body) or 'CLEAN'}")
        b4 += ["",
               f"embedded: {len(clue_ids)} clue emails + {len(flat) - len(clue_ids)} noise emails "
               f"= {len(flat)} total, interleaved by date into one mailbox",
               "",
               "mailbox preview (date-sorted; <<CLUE marks the planted deception):"]
        for m in flat[:16]:
            mark = "   <<CLUE" if m["message_id"] in clue_ids else ""
            b4.append(f"  {(m.get('date') or '')[:10]}  {m['from_addr']:26}  "
                      f"{(m.get('subject') or '(no subject)')[:40]:40}{mark}")
        b4.append(f"\n[note] noise threads relabeled best-effort (10 cast -> Person addresses, "
                  f"company -> [firm]); stranger names tolerated per policy.")
        report.append("\n".join(b4))
        print(f"[{tid}] step4 done ({len(clue_ids)} clue + {len(flat)-len(clue_ids)} noise emails)")

    Path(args.out).write_text("\n\n".join(report) + "\n")
    print(f"\nWROTE {args.out}")


if __name__ == "__main__":
    main()
