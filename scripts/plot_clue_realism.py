#!/usr/bin/env python3
"""Validity check: do the planted clue emails blend into real Enron mail, or are they detectable
artifacts? We featurize emails two ways -- STYLOMETRIC (topic-agnostic: length/punctuation/format/
function-words -> catches synthetic style) and LEXICAL (tf-idf -> topic+wording) -- project to 2D,
and measure each clue's distance to the nearest REAL email against the real-to-real distance spread.

If clues sit inside the real cloud (kNN-distance AUC ~ 0.5), recovery cannot be a "spot the fake"
shortcut. If a per-email detector could separate them (AUC -> 1), that is a shortcut threat.

  blue = 200 random real Enron emails      red = planted clue emails
Pure numpy + matplotlib (offline box, no neural embedder cached).
"""
import json
import random
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from email_finalize import clue_to_thread                                     # noqa: E402
from src.grounding.retrieval import tokenize, STOP, WORD                      # noqa: E402

NOISE_BLUE, CLUE_RED = "#2563EB", "#DC2626"
WORK = set(f"T{n:02d}" for n in list(range(1, 11)) + list(range(21, 26)))
CONFIGS = [("commission", 2, "benchmark_pool/emails_commission_n2.jsonl"),
           ("commission", 3, "benchmark_pool/emails_commission_n3.jsonl"),
           ("paltering", 2, "benchmark_pool/emails_paltering_n2.jsonl"),
           ("paltering", 3, "benchmark_pool/emails_paltering_n3.jsonl")]
PER_FILE = 5
N_NOISE = 200
SEED = 20260817


def email_text(subject, body):
    return (subject or "") + "\n" + (body or "")


def stylo(text):
    """Topic-agnostic style features."""
    t = text or ""
    words = WORD.findall(t.lower())
    letters = [c for c in t if c.isalpha()]
    lines = t.split("\n")
    nw = max(1, len(words))
    nc = max(1, len(t))
    sent = max(1, len(re.findall(r"[.!?]+", t)))
    caps_words = sum(1 for w in re.findall(r"[A-Za-z]{2,}", t) if w.isupper())
    return [
        np.log1p(len(t)),                                        # length
        np.log1p(len(words)),                                    # word count
        np.mean([len(w) for w in words]) if words else 0,        # avg word len
        len(lines),                                              # line count
        len(t) / max(1, len(lines)),                             # avg line len
        sum(1 for c in t if not c.isalnum() and not c.isspace()) / nc,   # punct ratio
        sum(c.isdigit() for c in t) / nc,                        # digit ratio
        (sum(c.isupper() for c in letters) / max(1, len(letters))),      # uppercase ratio
        t.count(",") / nw,                                       # commas / word
        sent / nw,                                               # sentence enders / word
        caps_words / nw,                                         # ALLCAPS words / word
        sum(1 for w in words if w in STOP) / nw,                 # function-word ratio
        float(bool(re.search(r"Forwarded by|-----|Original Message|@ECT|cc:", t))),  # header marker
        len(words) / sent,                                       # words / sentence
        len(set(words)) / nw,                                    # type/token
    ]


def pca2(X):
    Xc = X - X.mean(0)
    u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    return u[:, :2] * s[:2]


def nearest_real_dist(X, is_real):
    """For each row, Euclidean distance to the nearest REAL row (excluding itself)."""
    real = X[is_real]
    d = np.zeros(len(X))
    for i in range(len(X)):
        dd = np.linalg.norm(real - X[i], axis=1)
        if is_real[i]:                                   # exclude self
            dd[np.argmin(dd)] = np.inf
        d[i] = dd.min()
    return d


def auc(clue_scores, real_scores):
    """P(clue is more outlying than real) via rank; 0.5 = indistinguishable, 1 = clue always outlier."""
    c = np.asarray(clue_scores)[:, None]
    r = np.asarray(real_scores)[None, :]
    return float((c > r).mean() + 0.5 * (c == r).mean())


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}

    # ---- clue emails ----
    clue_rows = []          # (text, mech, n, reg, tid)
    for mech, n, path in CONFIGS:
        rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        rows = [r for r in rows if r.get("status") == "KEPT"]
        work = [r for r in rows if r["topic_id"] in WORK]
        casual = [r for r in rows if r["topic_id"] not in WORK]
        pick = work[:3] + casual[:2]
        pick = (pick + rows)[:PER_FILE] if len(pick) < PER_FILE else pick[:PER_FILE]
        for r in pick:
            reg = "work" if r["topic_id"] in WORK else "casual"
            th = [clue_to_thread(c, r["topic_id"], addr_map) for c in r["clues"]]
            for t in th:
                for m in t["messages"]:
                    clue_rows.append((email_text(m.get("subject", ""), m.get("body", "")),
                                      mech, n, reg, r["topic_id"]))

    # ---- real noise emails ----
    corpus = [json.loads(l) for l in Path("data/enron_10/threads.jsonl").read_text().splitlines() if l.strip()]
    msgs = [m for t in corpus for m in t["messages"]]
    noise = random.sample(msgs, N_NOISE)
    real_texts = [email_text(m.get("subject", ""), m.get("body", "")) for m in noise]

    texts = real_texts + [c[0] for c in clue_rows]
    is_real = np.array([True] * len(real_texts) + [False] * len(clue_rows))
    print(f"clue emails: {len(clue_rows)}  |  real noise: {len(real_texts)}")
    from collections import Counter
    print("clue breakdown:", dict(Counter((c[1], f"n{c[2]}", c[3]) for c in clue_rows)))

    # ---- STYLOMETRIC space ----
    S = np.array([stylo(t) for t in texts], float)
    S = (S - S[is_real].mean(0)) / (S[is_real].std(0) + 1e-9)     # z vs real distribution
    S2 = pca2(S)
    ds = nearest_real_dist(S, is_real)
    auc_s = auc(ds[~is_real], ds[is_real])

    # ---- LEXICAL tf-idf space ----
    docs = [tokenize(t) for t in texts]
    df = Counter(w for d in docs for w in set(d))
    vocab = {w: i for i, w in enumerate(w for w, c in df.items() if c >= 2)}
    idf = {w: np.log(len(docs) / df[w]) for w in vocab}
    L = np.zeros((len(docs), len(vocab)))
    for i, d in enumerate(docs):
        tf = Counter(d)
        for w, c in tf.items():
            if w in vocab:
                L[i, vocab[w]] = (c / max(1, len(d))) * idf[w]
    L /= (np.linalg.norm(L, axis=1, keepdims=True) + 1e-9)         # L2 -> cosine
    L2 = pca2(L)
    dl = nearest_real_dist(L, is_real)
    auc_l = auc(dl[~is_real], dl[is_real])

    print(f"\nSTYLOMETRIC  kNN-dist AUC={auc_s:.3f}  median real={np.median(ds[is_real]):.2f} "
          f"clue={np.median(ds[~is_real]):.2f}")
    print(f"LEXICAL      kNN-dist AUC={auc_l:.3f}  median real={np.median(dl[is_real]):.2f} "
          f"clue={np.median(dl[~is_real]):.2f}")

    # ---- figure ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.2))
    for a, XY, title, aucv in [(ax[0], S2, "Stylometric (style / format)", auc_s),
                               (ax[1], L2, "Lexical (topic / wording)", auc_l)]:
        a.scatter(XY[is_real, 0], XY[is_real, 1], s=16, c=NOISE_BLUE, alpha=0.35,
                  linewidths=0, label=f"real Enron ({is_real.sum()})")
        a.scatter(XY[~is_real, 0], XY[~is_real, 1], s=42, c=CLUE_RED, alpha=0.9,
                  edgecolors="white", linewidths=0.6, label=f"planted clue ({(~is_real).sum()})")
        a.set_title(f"{title}\nkNN-distance AUC = {aucv:.2f}", fontsize=12)
        a.set_xlabel("PC1"); a.set_ylabel("PC2")
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(labelsize=8)
        a.legend(frameon=False, fontsize=9, loc="best")

    # kNN distance distribution (stylometric)
    a = ax[2]
    bins = np.linspace(0, max(ds.max(), 1e-6), 26)
    a.hist(ds[is_real], bins=bins, color=NOISE_BLUE, alpha=0.55, density=True, label="real -> nearest real")
    a.hist(ds[~is_real], bins=bins, color=CLUE_RED, alpha=0.6, density=True, label="clue -> nearest real")
    a.axvline(np.median(ds[is_real]), color=NOISE_BLUE, ls="--", lw=1.5)
    a.axvline(np.median(ds[~is_real]), color=CLUE_RED, ls="--", lw=1.5)
    a.set_title("Stylometric kNN-distance to real mail", fontsize=12)
    a.set_xlabel("distance to nearest real email"); a.set_ylabel("density")
    a.spines[["top", "right"]].set_visible(False)
    a.tick_params(labelsize=8)
    a.legend(frameon=False, fontsize=9)

    fig.suptitle("Do planted clues blend into real Enron mail?  (AUC~0.5 = indistinguishable, ~1 = detectable artifact)",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    out = Path("results/validity"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "clue_realism.png", dpi=150, bbox_inches="tight")
    print(f"\nWROTE {out}/clue_realism.png")


if __name__ == "__main__":
    main()
