#!/usr/bin/env python3
"""Agentic evaluation — a find-secrets ReAct agent explores a virtual mailbox with tools and must
recover a distributed-clue concealment WITHOUT ever being told the benchmark's structure.

The agent only knows "dig up private/undisclosed facts about the people in this mailbox". It searches
and reads under a tool budget (it never reads the whole mailbox); success = it recovered the planted
secret, scored against the answer key + the true clue emails.

  --control  no-secret mailbox     (false-positive / hallucination rate)
  --certify  with --control: resample until a strong blind prober recovers NOTHING (mailbox is clean)
  --reps N   repeat each cell       (variance / reliability)

Tester can be local/cheap (gemma, luna); only the JUDGE is a strong API model.

  uv run python scripts/run_agent.py --engine vllm --preset gemma4-31b --tp 2 \
      --judge-preset openai/gpt-5.6-terra --topics T01,T06 --budget 15 --reps 1 \
      --clues benchmark_pool/emails_commission_n2.jsonl:com_n2 --out results/agent/smoke
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from email_finalize import _thread_text                                       # noqa: E402
from src.grounding.retrieval import BM25, tokenize                            # noqa: E402
from src.models.engine_factory import build_engine                           # noqa: E402
from src.agent.mailbox_env import MailboxEnv                                  # noqa: E402
from src.agent.react_agent import run_agent                                  # noqa: E402
from src.agent.anonymize import build_subs, anon_env, anon_answer            # noqa: E402

SOLVE = Path("prompts/eval_solve.md")                       # strong blind prober (control certification)
JUDGE_RECOVER = Path("prompts/agent_recover_judge.md")      # match on compromising fact + person


def first_json(out: str):
    i = out.find("{")
    while i != -1:
        depth = 0
        for j in range(i, len(out)):
            if out[j] == "{":
                depth += 1
            elif out[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(out[i:j + 1])
                    except Exception:
                        break
        i = out.find("{", i + 1)
    return None


def judge_recover(engine, answer: dict, secret: str, prompt_path=JUDGE_RECOVER) -> bool:
    p = (Path(prompt_path).read_text()
         .replace("<<CONCEALMENT>>", answer.get("concealment", ""))
         .replace("<<ACTOR>>", answer.get("actor", "")).replace("<<VICTIM>>", answer.get("victim", ""))
         .replace("<<TRUE>>", answer.get("true_fact", "")).replace("<<FALSE>>", answer.get("false_belief", ""))
         .replace("<<SECRET>>", secret or "(blank)"))
    out = engine.generate([p], max_tokens=200, temperature=0.0)[0]
    return bool((first_json(out) or {}).get("match"))


def certify_clean(prober, env) -> bool:
    """A control mailbox is CERTIFIED secret-free iff a strong blind prober, reading the WHOLE
    mailbox, recovers nothing. This is the correct null for the agent false-positive metric."""
    prompt = SOLVE.read_text().replace("<<EMAILS>>", env.dump_all())
    out = prober.generate([prompt], max_tokens=400, temperature=0.0)[0]
    return not bool((first_json(out) or {}).get("found"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="vllm")
    ap.add_argument("--preset", required=True, help="tester (local/cheap ok)")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.6)
    ap.add_argument("--model-len", type=int, default=0)
    ap.add_argument("--judge-engine", default="api")
    ap.add_argument("--judge-preset", default="openai/gpt-5.6-terra")
    ap.add_argument("--clues", default="benchmark_pool/emails_commission_n2.jsonl:com_n2")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--topics", default="all")
    ap.add_argument("--react-prompt", default="prompts/agent_secrets.md",
                    help="find-secrets system prompt (the one agent design)")
    ap.add_argument("--reflect", action="store_true", help="Reflexion self-check before accepting an answer")
    ap.add_argument("--recover-judge", default="prompts/agent_recover_judge.md",
                    help="recovery judge; matches on compromising fact + person (not victim/direction)")
    ap.add_argument("--no-judge", action="store_true",
                    help="skip the paid recovery judge; still fills found/clue_recall/ev_recall/ev_precision")
    ap.add_argument("--control", action="store_true", help="no-secret mailbox (false-positive test)")
    ap.add_argument("--certify", action="store_true",
                    help="with --control: resample until a strong prober recovers NOTHING "
                         "(guarantees the mailbox is secret-free)")
    ap.add_argument("--noise", type=int, default=200, help="number of noise THREADS (whole threads)")
    ap.add_argument("--all-noise", action="store_true",
                    help="use the ENTIRE corpus as noise, ordered chronologically (clues land on their dates)")
    ap.add_argument("--budget", type=int, default=25, help="max tool calls before forced answer")
    ap.add_argument("--read-before-answer", action=argparse.BooleanOptionalAction, default=True,
                    help="block ANSWER right after a SEARCH with unread hits (read a result first)")
    ap.add_argument("--window", type=int, default=10,
                    help="keep the last N turns in full in the prompt; older turns compress to a stub")
    ap.add_argument("--rerank", type=int, default=0,
                    help="SEARCH retrieves this many BM25 candidates, then the model reranks (0=off)")
    ap.add_argument("--rerank-show", type=int, default=8, help="how many reranked hits to show the agent")
    ap.add_argument("--scan", action="store_true",
                    help="segment-scan mode: force full date-ordered coverage before concluding no-secret")
    ap.add_argument("--min-invest", type=int, default=0,
                    help="floor on SEARCH/READ before any ANSWER; 0=off, -1=auto (= the topic's clue count n)")
    ap.add_argument("--synth-every", type=int, default=0,
                    help="inject a compositional-review note every N emails opened (0=off)")
    ap.add_argument("--anonymize", default="",
                    help="path to pseudonyms.json; swaps real identities in the mailbox + answer key")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=1024,
                    help="per agent turn; needs headroom so a verbose model reaches its ACTION line")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--out", default="results/agent/run")
    args = ap.parse_args()

    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}
    bm = BM25([tokenize(_thread_text(t)) for t in corpus])

    configs = []
    for spec in args.clues.split(","):
        path, _, label = spec.partition(":")
        rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        rows = [r for r in rows if r.get("status") == "KEPT"]
        if args.topics != "all":
            keep = set(args.topics.split(","))
            rows = [r for r in rows if r["topic_id"] in keep]
        configs.append((label or Path(path).stem, rows))

    engine = build_engine(args.engine, args.preset, tp=args.tp, gpu_mem=args.gpu_mem,
                          max_model_len=(args.model_len or None))
    need_judge = (args.certify and args.control) or (not args.control and not args.no_judge)
    judge = build_engine(args.judge_engine, args.judge_preset) if need_judge else None

    sys_react = Path(args.react_prompt).read_text()
    subs = build_subs(args.anonymize) if args.anonymize else None

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    fields = ["config", "topic", "control", "rep", "budget",
              "found", "secret_match", "ev_recall", "ev_precision", "final", "false_positive",
              "n_tool_calls", "n_search", "n_read", "n_emails_opened", "n_redundant_reads",
              "n_clues_total", "n_clues_read", "clue_recall", "turns", "budget_hit",
              "certified", "latency_s", "tester_chars", "secret"]
    fcsv = (outdir / "rows.csv").open("w", newline="")
    w = csv.DictWriter(fcsv, fieldnames=fields)
    w.writeheader()
    ftraj = (outdir / "trajectories.jsonl").open("w")

    tag = ("control(false-positive)" if args.control else "recover") + ("+certify" if args.certify else "")
    print(f"tester={args.preset}  judge={args.judge_preset}  {tag}  budget={args.budget}  "
          f"reps={args.reps}  noise={args.noise}  configs={[c[0] for c in configs]}")

    for label, rows in configs:
        for rep in range(args.reps):
            seed = args.seed + rep
            for row in rows:
                tid = row["topic_id"]
                certified = ""
                if args.control:
                    s, tries = seed, 0
                    env = MailboxEnv.control(corpus, bm, args.noise, s)
                    if args.certify:
                        while not certify_clean(judge, env) and tries < 6:
                            s += 1000
                            tries += 1
                            env = MailboxEnv.control(corpus, bm, args.noise, s)
                        certified = int(tries < 6)      # 1 = prober found nothing (clean)
                else:
                    env = MailboxEnv.from_row(row, corpus, bm, addr_map,
                                              0 if args.all_noise else args.noise, seed,
                                              order="date" if args.all_noise else "shuffle")

                if subs:
                    anon_env(env, subs)

                min_invest = len(row.get("clues", [])) if args.min_invest < 0 else args.min_invest
                res = run_agent(engine, env, sys_react, budget=args.budget,
                                read_before_answer=args.read_before_answer, window=args.window,
                                rerank=args.rerank, rerank_show=args.rerank_show,
                                synth_every=args.synth_every, scan_cover=args.scan,
                                min_investigate=min_invest,
                                max_tokens=args.max_tokens, temperature=args.temp,
                                reflect=args.reflect)
                m = env.metrics()
                ans = row.get("answer", {})
                if subs:
                    ans = anon_answer(ans, subs)
                rowd = {"config": label, "topic": tid, "control": int(args.control), "rep": rep,
                        "budget": args.budget, **m, "turns": res["turns"],
                        "budget_hit": int(res["budget_hit"]), "certified": certified,
                        "latency_s": res["latency_s"], "tester_chars": res["gen_chars"], "secret": "",
                        "found": "", "secret_match": "", "ev_recall": "", "ev_precision": "",
                        "final": "", "false_positive": ""}

                obj = first_json(res["final_raw"]) or {}
                found = bool(obj.get("found"))
                secret = (obj.get("secret") or "").strip()
                cites = [str(c).strip() for c in (obj.get("evidence_email_ids") or [])]
                prec, rec = env.clue_precision_recall(cites)
                rowd["found"] = int(found)
                rowd["secret"] = secret[:400]
                if args.control:
                    rowd["false_positive"] = int(found)   # any secret claimed = hallucination
                else:
                    rowd["ev_recall"] = rec               # free: cited handles vs true clue threads
                    rowd["ev_precision"] = prec
                    if args.no_judge:
                        rowd["secret_match"] = ""
                        rowd["final"] = ""
                    else:
                        match = judge_recover(judge, ans, secret, args.recover_judge) if found else False
                        rowd["secret_match"] = int(match)
                        rowd["final"] = round(int(found) * int(match) * rec * prec, 3)

                w.writerow(rowd)
                fcsv.flush()
                ftraj.write(json.dumps({"config": label, "topic": tid, "rep": rep,
                                        "final_raw": res["final_raw"], "transcript": res["transcript"],
                                        "metrics": m}, ensure_ascii=False) + "\n")
                tail = (f"false_pos={rowd['false_positive']}" if args.control else
                        f"found={rowd['found']} ev_recall={rowd['ev_recall']}" if args.no_judge else
                        f"found={rowd['found']} match={rowd['secret_match']} final={rowd['final']}")
                print(f"  [{label}] {tid} rep{rep}: {tail}  "
                      f"(tools={m['n_tool_calls']} read={m['n_emails_opened']} "
                      f"clue_recall={m['clue_recall']} {res['latency_s']}s)")

    fcsv.close()
    ftraj.close()
    print(f"\nWROTE {outdir}/rows.csv  +  trajectories.jsonl")


if __name__ == "__main__":
    main()
