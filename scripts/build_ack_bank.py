#!/usr/bin/env python3
"""Mine real terse acknowledgment replies from the Enron corpus -> benchmark_pool/ack_bank.json.

The a2 clue ("the actor holds/received the record") used to end with a fixed synthetic ack —
`C replies "received and noted"` — which (a) never appears in the real corpus (0 / 517k messages)
and (b) got cloned across every generated item. This bank replaces it: real, terse, name-free
receipt replies the way Enron people actually wrote them ("got it.", "will do", "Received.",
"Noted. thanks", ...). atomize_build.plot_example() samples one at random per call, so the a2
surface varies instead of cloning one phrase.

A kept ack is a very short reply whose whole body is built ONLY from receipt vocabulary (no names,
no numbers, no chatter), so it reads naturally in any "Person X replies '<ack>'" slot.

  uv run python scripts/build_ack_bank.py
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from plot_assemble import scrub_corp

MAILDIR = Path("data/enron/maildir")
OUT = Path("benchmark_pool/ack_bank.json")

ACK_START = re.compile(
    r"^(thanks?|thank you|got it|received|noted|will do|will file|will keep|filed|logged|"
    r"understood|acknowledged|confirmed|all set|good to go|on it)\b", re.I)
CUT = re.compile(r"^\s*(>|-{3,}|_{3,}|from:|to:|sent:|subject:|cc:|original message|forwarded)", re.I)
NAME_SIG = re.compile(r"^\s*[-–]*\s*[A-Z][a-z]+(\s+[A-Z]\.?)?(\s+[A-Z][a-z]+)?\s*$")
DROP = re.compile(r"\b(bye|crush|baby|buddy|grouch|god|news|idea|job|lunch|beer|fun|luck|deal|cool|sir)\b"
                  r"|[!?]|[:;]-?[)(dpDP]", re.I)   # chatter, exclamations, emoticons
# a "clean" ack is built ONLY from receipt vocabulary — no names, no off-topic words
VOCAB = {"thanks", "thank", "you", "got", "it", "received", "noted", "will", "do", "does",
         "file", "filed", "filing", "log", "logged", "keep", "kept", "confirmed", "confirm",
         "understood", "acknowledged", "all", "set", "good", "to", "go", "done", "on", "much",
         "again", "now", "here", "in", "have", "this", "for", "the", "a", "so",
         "great", "perfect", "fine", "and", "of", "receipt", "your", "yours", "message",
         "note", "am", "i", "we", "ll", "ve", "record", "copy", "them", "that"}


def body_of(text: str) -> list[str]:
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip():   # skip headers
        i += 1
    out = []
    for ln in lines[i + 1:]:
        if CUT.match(ln): break
        out.append(ln)
    while out and not out[0].strip(): out.pop(0)
    while out and not out[-1].strip(): out.pop()
    return out


def clean(body: list[str]) -> str | None:
    ne = [l.strip() for l in body if l.strip()]
    if not ne: return None
    if len(ne) >= 2 and NAME_SIG.match(ne[-1]) and not ACK_START.match(ne[-1]):
        ne = ne[:-1]                              # drop a trailing bare-name signature line
    if not (1 <= len(ne) <= 2): return None
    joined = re.sub(r"\s{2,}", " ", " ".join(ne)).strip()
    if not ACK_START.match(joined): return None
    if DROP.search(joined): return None
    if "http" in joined.lower() or "@" in joined or "www." in joined: return None
    if re.search(r"\d", joined): return None
    if not (6 <= len(joined) <= 40): return None
    toks = re.findall(r"[a-z]+", joined.lower())
    if not toks or any(t not in VOCAB for t in toks):      # any non-receipt word (a name) -> drop
        return None
    if any(toks.count(t) >= 3 for t in set(toks)):
        return None                                        # "thanks thanks thanks" / "thank you x3" — degenerate
    return scrub_corp(joined).strip()


def main():
    seen, acks = set(), []
    files = [p for p in MAILDIR.rglob("*") if p.is_file()]
    print(f"scanning {len(files)} files ...", flush=True)
    for p in files:
        try:
            c = clean(body_of(p.read_text(errors="ignore")))
        except Exception:
            continue
        if not c: continue
        key = re.sub(r"[^a-z]", "", c.lower())
        if key in seen: continue
        seen.add(key); acks.append(c)
    acks.sort(key=lambda s: (len(s), s.lower()))
    OUT.write_text(json.dumps(acks, ensure_ascii=False, indent=2))
    print(f"-> {OUT}  ({len(acks)} acks)")
    for a in acks: print("   ", repr(a))


if __name__ == "__main__":
    main()
