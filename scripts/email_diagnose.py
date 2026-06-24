#!/usr/bin/env python3
"""Validate the feedback chain on T07: probe -> diagnose (LLM picks failure modes from the 9) ->
WRONG_VICTIM triggers an added `reliance` atom -> regenerate -> re-probe, and see whether the
blind reader now reads the misled party as the intended victim.

  uv run python scripts/email_diagnose.py
"""
import sys, json, re
from pathlib import Path
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from email_generate import (atomize, distribute, voice_rewrite, render, probe, match,
                               build_team, secret_block, load_cards, extract_json)
from plot_assemble import load_plot_secrets, load_plot_topics
from src.models.engine_factory import build_engine

DIAG = Path("prompts/email_diagnose.md")
VENDORS = ["gpt-5", "grok-4.3", "gemini-3.1"]


def plabel(s):
    m = re.search(r"Person [A-J]", s or ""); return m.group(0) if m else ""


def clues_block(clues, atoms):
    roles = {a["id"]: a["role"] for a in atoms}
    out = ["ATOMS:"] + [f"  {a['id']} [{a['role']}] {a['fact']}" for a in atoms]
    for c in clues:
        car = ", ".join(f"{x}:{roles.get(x, '?')}" for x in c.get("carries", []))
        out += [f"\nCLUE {c['i']} carries [{car}]:", render(c.get("messages"))]
    return "\n".join(out)


def joint_probe(engines, clues):
    allm = sorted((m for c in clues for m in (c.get("messages") or [])), key=lambda m: m.get("date", ""))
    return [probe(e, render(allm)) for e in engines]


def diagnose(engine, clues, atoms, intended, joint_recon, leakage):
    p = (DIAG.read_text()
         .replace("<<ACTOR>>", intended["actor"]).replace("<<VICTIM>>", intended["victim"])
         .replace("<<TRUE>>", intended["true_fact"]).replace("<<FALSE>>", intended["false_belief"])
         .replace("<<VICTIM_LABEL>>", plabel(intended["victim"]))
         .replace("<<CLUES>>", clues_block(clues, atoms))
         .replace("<<JOINT>>", json.dumps(joint_recon, ensure_ascii=False))
         .replace("<<LEAKAGE>>", leakage))
    return extract_json(engine.generate(p, max_tokens=2500, temperature=0.0)[0])


def gen_set(gen, plot, sblock, era, team, cards, atoms, n):
    clues = distribute(gen, "T07", sblock, plot, atoms, team, era, n)
    abi = {a["id"]: a for a in atoms}
    return [voice_rewrite(gen, c, abi, cards) for c in clues]


def show_probe(engines, clues, intended):
    recon = joint_probe(engines, clues)
    out = []
    for v, r in zip(VENDORS, recon):
        m = match(engines[0], intended, r) if (r and r.get("hidden")) else None
        ok = bool(m and m.get("match"))
        print(f"    [{v:9}] whom={ (r or {}).get('whom','')!r:26} match={ok}")
        out.append((r, ok))
    return out


def main():
    n = 3
    secrets = load_plot_secrets("benchmark_pool/plot_generation.json")
    meta = load_plot_topics("benchmark_pool/plot_generation.json")
    plot, mt = secrets["T07"], meta["T07"]
    sblock, era, team, cards = secret_block(plot, mt), mt["era"], build_team(), load_cards()
    vlab = plabel(plot["victim"])
    print(f"INTENDED victim = {vlab}  ({plot['victim'][:60]})\n")

    gen = build_engine("api", "or-claude-sonnet")
    engines = [build_engine("api", p) for p in ["or-gpt-5", "x-ai/grok-4.3",
                                                "google/gemini-3.1-pro-preview"]]

    print("=== ROUND 0 — atomize + distribute (no reliance) ===")
    atoms = atomize(gen, "T07", sblock, plot)
    print("  roles:", [a["role"] for a in atoms])
    clues = gen_set(gen, plot, sblock, era, team, cards, atoms, n)
    print("  blind read (step 1 probe + step 2 match):")
    recon = show_probe(engines, clues, plot)

    rep = next((r for r, ok in recon if r and r.get("hidden")), recon[0][0])
    print("\n=== step 3 — LLM diagnoser picks failure modes from the 9 ===")
    dg = diagnose(engines[0], clues, atoms, plot, rep,
                  "Solo/subset probes: no single clue or proper subset reveals the concealment.")
    print("  ", json.dumps(dg, ensure_ascii=False))

    if not (dg and dg.get("modes")):
        print("\n(no failure modes diagnosed — stopping)"); return

    # Feed the diagnoser's OWN overall revision back to the generator (full regenerate), and iterate.
    actions = dg.get("revision", "")
    for attempt in (1, 2, 3):
        print(f"\n=== ROUND {attempt} — feed the diagnoser's own action(s) back to distribute, re-probe ===")
        print("   feedback:", actions[:200])
        cl = distribute(gen, "T07", sblock, plot, atoms, team, era, n, feedback=actions)
        abi = {a["id"]: a for a in atoms}
        cl = [voice_rewrite(gen, c, abi, cards) for c in cl]
        recon = show_probe(engines, cl, plot)
        hits = sum(ok for r, ok in recon)                       # majority must MATCH (whom == victim)
        if hits >= 2:
            print(f"  -> FIXED: majority ({hits}/3) match the intended victim {vlab}"); return
        rep = next((r for r, ok in recon if r and r.get("hidden")), recon[0][0])
        dg2 = diagnose(engines[0], cl, atoms, plot, rep, "no single clue or subset leaks")
        modes = [m.get("mode") for m in (dg2 or {}).get("modes", [])]
        print("   re-diagnosed modes:", modes)
        actions = (dg2 or {}).get("revision", "")
        if not actions:
            print("  -> diagnoser reports clean; stopping"); return
    print("  -> still not fixed after 3 attempts")


if __name__ == "__main__":
    main()
