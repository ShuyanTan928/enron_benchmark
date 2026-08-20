"""Output-time anonymization — swap real Enron identities for same-initial fictional ones, consistently
across a mailbox and its answer key, so a model cannot lean on Enron priors (recite a known scandal by
name). Reads benchmark_pool/pseudonyms.json.

Substitutions apply most-specific-first so nothing gets half-clobbered:
  full email -> domain -> full name -> first/last name alone -> company token.
"""
import json
import re
from pathlib import Path


def build_subs(pseudo_path="benchmark_pool/pseudonyms.json", people_path="benchmark_pool/people.json"):
    P = json.loads(Path(pseudo_path).read_text())
    people = json.loads(Path(people_path).read_text())["people"]
    real_email = {p["real_name"]: p["real_email"] for p in people}
    subs = []                                                   # (compiled, repl), applied in order
    for real_name, fake in P["people"].items():                 # 1. full email addresses
        if real_name in real_email:
            subs.append((re.compile(re.escape(real_email[real_name]), re.I), fake["email"]))
    for d, fd in P.get("domain", {}).items():                   # 2. any remaining @domain
        subs.append((re.compile(re.escape(d), re.I), fd))
    for real_name, fake in P["people"].items():                 # 3. full names
        subs.append((re.compile(r'\b' + re.escape(real_name) + r'\b'), fake["name"]))
    for real_name, fake in P["people"].items():                 # 4. first + last name alone
        rf, rl = real_name.split()[0], real_name.split()[-1]
        ff, fl = fake["name"].split()[0], fake["name"].split()[-1]
        subs.append((re.compile(r'\b' + re.escape(rf) + r'\b'), ff))
        subs.append((re.compile(r'\b' + re.escape(rl) + r'\b'), fl))
    for c, fc in P.get("companies", {}).items():                # 5. company tokens (case variants listed)
        subs.append((re.compile(r'\b' + re.escape(c) + r'\b'), fc))
    return subs


def anon_text(s, subs):
    s = s or ""
    for pat, repl in subs:
        s = pat.sub(repl, s)
    return s


def anon_msg(m, subs):
    m["subject"] = anon_text(m.get("subject", ""), subs)
    m["body"] = anon_text(m.get("body", ""), subs)
    m["from_addr"] = anon_text(m.get("from_addr", ""), subs)
    m["to_addrs"] = [anon_text(x, subs) for x in (m.get("to_addrs") or [])]
    m["cc_addrs"] = [anon_text(x, subs) for x in (m.get("cc_addrs") or [])]
    return m


def anon_env(env, subs):
    """Rewrite every email in a built MailboxEnv, then rebuild its BM25 index so SEARCH stays consistent."""
    from src.agent.mailbox_env import _flat_text
    from src.grounding.retrieval import BM25, tokenize
    for h in env.msgs:
        anon_msg(env.msgs[h], subs)
    env._bm = BM25([tokenize(_flat_text(env.msgs[h])) for h in env._handles])
    return env


def anon_answer(ans, subs):
    """Anonymize the answer-key strings so the recovery judge compares like-for-like."""
    return {k: (anon_text(v, subs) if isinstance(v, str) else v) for k, v in (ans or {}).items()}
