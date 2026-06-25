#!/usr/bin/env python3
"""Build a per-person VOICE card: the persona card (reused from profiles/) with TWO carefully
SELECTED real emails the person actually wrote embedded directly into it, all relabeled to Person
A–J and company-scrubbed so generation stays anonymous.

The two emails are not picked by a length heuristic — an LLM reads a pool of the person's real
authored mail and selects the two that best show their everyday writing voice (typical greeting,
length, diction, sign-off). That selection step is part of card generation. Output:
benchmark_pool/style_bank.json  ->  {label: {real_name, card}}  (card has the examples embedded).

  uv run python scripts/build_style_bank.py
  uv run python scripts/build_style_bank.py --only "Person C,Person F,Person H"
"""
from __future__ import annotations
import argparse
import email
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from plot_assemble import make_relabel, scrub_corp
from src.models.engine_factory import build_engine

MAILDIR = "data/enron/maildir"
PROFILES = Path("profiles")
SCAN_CAP = 800
N_POOL = 14                    # candidates shown to the selector
N_PICK = 2

CUT = re.compile(r"(-{3,}\s*Original Message|-{3,}\s*Forwarded|^_{5,}|^\s*>|^From:\s|^Sent:\s|"
                 r"^To:\s|^Subject:\s)", re.M)


def body_of(path: str) -> tuple[str, str]:
    try:
        msg = email.message_from_string(Path(path).read_text(errors="ignore"))
    except Exception:
        return "", ""
    frm = (msg.get("From") or "").strip().lower()
    payload = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = (part.get_payload(decode=True) or b"").decode("utf-8", "ignore"); break
    else:
        payload = msg.get_payload() or ""
    m = CUT.search(payload)
    if m:
        payload = payload[:m.start()]
    return frm, payload.strip()


def is_clean_prose(b: str) -> bool:
    w = b.split()
    if not (25 <= len(w) <= 140):
        return False
    if b.count("\t") > 2 or b.count("=") > 3:
        return False
    letters = sum(c.isalpha() for c in b)
    if letters and sum(c.isupper() for c in b) / letters > 0.4:
        return False
    return b.count(".") >= 1 and any(c.islower() for c in b)


def harvest_corpus(addr: str, path: str = "data/enron_10/threads.jsonl") -> list[str]:
    """Fallback: authored bodies from the curated corpus (already-extracted text, from_addr-labelled)
    for anyone whose maildir sent folder is missing/sparse (e.g. Carol Clair)."""
    out, seen = [], set()
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        for m in json.loads(line).get("messages", []):
            if (m.get("from_addr") or "").lower() != addr.lower():
                continue
            b = m.get("body", "") or ""
            mc = CUT.search(b)
            if mc:
                b = b[:mc.start()]
            b = re.sub(r"[ \t]+", " ", b).strip()
            if is_clean_prose(b) and b[:40].lower() not in seen:
                seen.add(b[:40].lower()); out.append(b)
        if len(out) >= N_POOL:
            break
    return out


def harvest_raw(addr: str, folders: list[str], cross: bool) -> list[str]:
    files = []
    for f in folders:
        files += [p for p in glob.glob(f + "/*") if os.path.isfile(p)]
    if not cross:
        files = files[:SCAN_CAP]
    out, seen = [], set()
    for p in files:
        frm, b = body_of(p)
        if cross and addr not in frm:
            continue
        if is_clean_prose(b):
            b = re.sub(r"[ \t]+", " ", b).strip()
            k = b[:40].lower()
            if k not in seen:
                seen.add(k); out.append(b)
        if len(out) >= N_POOL:
            break
    return out


SELECT_PROMPT = """You are curating writing-style examples for one person, {role}.
Below are {n} emails they actually sent. Pick the {k} that BEST represent this person's everyday
writing VOICE — genuine authored prose showing their habitual greeting, sentence length, punctuation,
diction and sign-off. Avoid ones that are mostly a quoted/forwarded chain, a bare list, or otherwise
atypical of how they normally write.

{candidates}

Return ONLY a JSON object: {{"pick": [i, j]}}  (0-based indices)."""


def select(engine, role: str, cands: list[str]) -> list[int]:
    block = "\n\n".join(f"[{i}] {c[:600]}" for i, c in enumerate(cands))
    p = SELECT_PROMPT.format(role=role, n=len(cands), k=N_PICK, candidates=block)
    try:
        raw = engine.generate(p, max_tokens=120, temperature=0.0)[0]
        m = re.search(r"\{.*\}", raw, re.S)
        idx = json.loads(m.group(0))["pick"] if m else []
        idx = [i for i in idx if isinstance(i, int) and 0 <= i < len(cands)][:N_PICK]
        if len(idx) == N_PICK:
            return idx
    except Exception:
        pass
    return sorted(range(len(cands)), key=lambda i: abs(len(cands[i].split()) - 55))[:N_PICK]  # fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma list of labels to (re)build; default all")
    ap.add_argument("--preset", default="or-claude-sonnet", help="selector model")
    args = ap.parse_args()

    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    relabel = make_relabel(people)
    alldirs = set(os.listdir(MAILDIR))
    eng = build_engine("api", args.preset)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    bank = {}
    out = Path("benchmark_pool/style_bank.json")
    if out.exists():
        bank = json.loads(out.read_text())

    def folders_for(real):
        ln, fi = real.split()[-1].lower(), real.split()[0][0].lower()
        return [os.path.join(MAILDIR, d, s) for d in alldirs if d.startswith(f"{ln}-{fi}")
                for s in ("sent", "sent_items", "_sent_mail") if os.path.isdir(os.path.join(MAILDIR, d, s))]

    for p in people:
        real, label, addr = p["real_name"], p["label"], p["real_email"]
        if only and label not in only:
            continue
        folders = folders_for(real)
        cands = harvest_raw(addr, folders, cross=False) if folders else []
        if len(cands) < N_PICK:                              # no/sparse sent folder -> curated corpus
            cands = harvest_corpus(addr)

        role = (json.loads((PROFILES / (real.lower().replace(' ', '.') + '.json')).read_text()).get(
            "persona_card", "")[:90] if (PROFILES / (real.lower().replace(' ', '.') + '.json')).exists()
            else p.get("role", "an Enron employee"))
        idx = select(eng, role, cands) if cands else []
        picks = [scrub_corp(relabel(cands[i])) for i in idx]

        pf = PROFILES / (real.lower().replace(" ", ".") + ".json")
        desc = scrub_corp(relabel(json.loads(pf.read_text()).get("persona_card", ""))).strip() if pf.exists() else ""
        ex = "\n\n".join(f"--- a real {label} email ---\n{s}" for s in picks)
        card = (desc + "\n\nTwo emails in this person's own hand (match this voice):\n\n" + ex).strip()

        bank[label] = {"real_name": real, "card": card}
        print(f"  {label} {real:18} pool={len(cands):2} picked={idx}"
              + ("" if len(picks) == N_PICK else "  <-- THIN"))

    out.write_text(json.dumps(bank, ensure_ascii=False, indent=2))
    print(f"\nWROTE {out}")


if __name__ == "__main__":
    main()
