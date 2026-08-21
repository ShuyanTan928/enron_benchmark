"""MailboxEnv — a read-only virtual company mailbox the agent explores with tools.

Wraps one benchmark item's finalized haystack (clue emails buried in real Enron noise). Emails get
short handles (e1, e2, …) so a local model can cite them reliably. Every tool call is logged, so the
runner can read trajectory-level metrics (tool calls, emails read, clue-recall, redundant reads).

Build one of two ways:
    MailboxEnv.from_row(row, corpus, bm, addr_map, noise, seed)   # a real item (has a secret)
    MailboxEnv.control(corpus, bm, noise, seed)                   # negative control (no secret)
"""
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from email_finalize import clue_to_thread, build_haystack, secret_query      # noqa: E402
from src.grounding.retrieval import BM25, tokenize                            # noqa: E402


def _flat_text(m: dict) -> str:
    return (m.get("subject", "") or "") + " " + (m.get("body", "") or "")


def _oneline(s: str, n: int) -> str:
    return " ".join((s or "").split())[:n]


class MailboxEnv:
    def __init__(self, threads: list, clue_mids: set):
        self.msgs = {}            # handle -> message dict
        self.thread_of = {}       # message handle -> thread handle
        self.thread_msgs = {}     # thread handle -> [message handle, ...]
        self.clue_handles = set()
        self.log = []             # list of {step, tool, arg, returned}
        self.opened = set()       # message handles the agent has READ (for the [read] marker)
        for ti, th in enumerate(threads, 1):
            th_h = f"t{ti}"
            self.thread_msgs[th_h] = []
            for m in th["messages"]:
                h = f"e{len(self.msgs) + 1}"
                self.msgs[h] = m
                self.thread_of[h] = th_h
                self.thread_msgs[th_h].append(h)
                if m.get("message_id") in clue_mids:
                    self.clue_handles.add(h)
        # BM25 over the mailbox for SEARCH
        self._handles = list(self.msgs)
        self._bm = BM25([tokenize(_flat_text(self.msgs[h])) for h in self._handles])

    # ---- construction ---------------------------------------------------------------------------
    @classmethod
    def from_row(cls, row, corpus, bm, addr_map, noise, seed, order="shuffle"):
        tid = row["topic_id"]
        cts = [clue_to_thread(c, tid, addr_map) for c in row["clues"]]
        anchor = row.get("_anchor")
        hay, _, _, _ = build_haystack(cts, corpus, anchor, secret_query(row, anchor), bm,
                                      noise_target=noise, seed=seed, order=order)
        clue_mids = {m["message_id"] for th in cts for m in th["messages"]}
        return cls(hay, clue_mids)

    @classmethod
    def control(cls, corpus, bm, noise, seed):
        hay, _, _, _ = build_haystack([], corpus, None, "", bm, noise_target=noise, seed=seed)
        return cls(hay, set())

    # ---- tools ----------------------------------------------------------------------------------
    def search(self, query: str, k: int = 12) -> str:
        scores = self._bm.scores(tokenize(query or ""))
        order = sorted(range(len(self._handles)), key=lambda i: scores[i], reverse=True)[:k]
        hits = [self._handles[i] for i in order if scores[i] > 0]
        self.log.append({"tool": "SEARCH", "arg": query, "returned": hits})
        if not hits:
            return "(no matches)"
        lines = []
        for h in hits:
            m = self.msgs[h]
            mark = "  [read]" if h in self.opened else ""
            lines.append(f"{h} | {(m.get('date','') or '')[:10]} | {_oneline(m.get('from_addr',''),28)} "
                         f"| {_oneline(m.get('subject',''),50)} | {_oneline(m.get('body',''),90)}{mark}")
        return "\n".join(lines)

    def expand(self, handle: str, k: int = 8, log: bool = True) -> str:
        """Pull other emails about the same matter as this one: query BM25 with the email's own full
        text (subject + body). A clue's own text is the best query for the rest of its event chain.
        Already-READ emails are excluded, so each expand pushes toward NEW related mail instead of
        re-surfacing what is opened. log=False for the automatic expand bundled into READ."""
        h = (handle or "").strip().split()[0] if handle else ""
        m = self.msgs.get(h)
        if not m:
            if log:
                self.log.append({"tool": "EXPAND", "arg": h, "returned": []})
            return f"(no email with handle {h!r})"
        scores = self._bm.scores(tokenize(_flat_text(m)))
        order = sorted(range(len(self._handles)), key=lambda i: scores[i], reverse=True)
        hits = [self._handles[i] for i in order
                if self._handles[i] != h and self._handles[i] not in self.opened and scores[i] > 0][:k]
        if log:
            self.log.append({"tool": "EXPAND", "arg": h, "returned": hits})
        if not hits:
            return "(nothing related)"
        lines = []
        for hh in hits:
            mm = self.msgs[hh]
            mark = "  [read]" if hh in self.opened else ""
            lines.append(f"{hh} | {(mm.get('date','') or '')[:10]} | {_oneline(mm.get('from_addr',''),28)} "
                         f"| {_oneline(mm.get('subject',''),50)} | {_oneline(mm.get('body',''),90)}{mark}")
        return "\n".join(lines)

    def read(self, handle: str) -> str:
        """Read the whole reply chain the handle belongs to (a single-message thread is just that email)."""
        h = (handle or "").strip().split()[0] if handle else ""
        th_h = h if h in self.thread_msgs else self.thread_of.get(h)
        mh = self.thread_msgs.get(th_h, [])
        self.log.append({"tool": "READ", "arg": h, "returned": list(mh)})
        self.opened.update(mh)
        if not mh:
            return f"(no email with handle {h!r})"
        cap = 1500 if len(mh) == 1 else 700
        out = [f"thread {th_h} ({len(mh)} message{'s' if len(mh) != 1 else ''}):"]
        for x in mh:
            m = self.msgs[x]
            to = ", ".join(m.get("to_addrs", []) or [])
            out.append(f"\n[{x}] From: {m.get('from_addr','')}  To: {to}  "
                       f"Date: {(m.get('date','') or '')[:10]}\nSubject: {m.get('subject','')}\n"
                       f"{_oneline(m.get('body',''), cap)}")
        return "\n".join(out)

    def segment(self, arg: str = "", size: int = 200) -> str:
        """Walk the mailbox in fixed date-ordered blocks so nothing is skipped. Each call returns the
        next block's index (thread | date | #msg | subject — body snippet); an internal cursor advances,
        or pass an explicit block number. Defeats the give-up-early failure: coverage is guaranteed."""
        ths = list(self.thread_msgs)
        n_blocks = (len(ths) + size - 1) // size
        arg = (arg or "").strip()
        if arg.isdigit():
            seg = int(arg)
        else:
            seg = getattr(self, "_seg_cursor", 0)
        self._seg_cursor = seg + 1
        if seg >= n_blocks:
            return (f"(all {n_blocks} segments reviewed — base your ACTION: ANSWER on your notes now)")
        block = ths[seg * size:(seg + 1) * size]
        lo, hi = seg * size + 1, min((seg + 1) * size, len(ths))
        out = [f"segment {seg + 1}/{n_blocks} — threads {lo}-{hi} of {len(ths)} "
               f"(when this block holds nothing sensitive, ACTION: SEGMENT for the next block):"]
        for th_h in block:
            mh = self.thread_msgs[th_h]
            m0 = self.msgs[mh[0]]
            mark = "  [read]" if any(x in self.opened for x in mh) else ""
            out.append(f"{th_h} | {(m0.get('date','') or '')[:10]} | {len(mh)}msg | "
                       f"{_oneline(m0.get('subject',''),46)} — {_oneline(m0.get('body',''),80)}{mark}")
        self.log.append({"tool": "SEGMENT", "arg": seg, "returned": block})
        return "\n".join(out)

    def segments_left(self, size: int = 200) -> int:
        n_blocks = (len(self.thread_msgs) + size - 1) // size
        return max(0, n_blocks - getattr(self, "_seg_cursor", 0))

    def list_threads(self, cap: int = 40) -> str:
        handles = list(self.thread_msgs)
        total = len(handles)
        if total > cap:                                   # even stride -> a spread across the whole box
            step = total / cap
            handles = [handles[int(i * step)] for i in range(cap)]
        handles.sort(key=lambda th: (self.msgs[self.thread_msgs[th][0]].get("date", "") or ""))
        out = [f"{total} threads in this mailbox; here is a sample of {len(handles)}:"]
        for th_h in handles:
            mh = self.thread_msgs[th_h]
            m0 = self.msgs[mh[0]]
            out.append(f"{th_h} | {(m0.get('date','') or '')[:10]} | {len(mh)} msg | "
                       f"{_oneline(m0.get('subject',''),60)}")
        self.log.append({"tool": "LIST", "arg": "", "returned": handles})
        return "\n".join(out)

    # ---- trajectory metrics ---------------------------------------------------------------------
    def metrics(self) -> dict:
        reads = [e for e in self.log if e["tool"] == "READ"]
        read_handles = [h for e in reads for h in e["returned"]]
        uniq = set(read_handles)
        # clue-recall counts by THREAD (= n): reading any message of a clue thread reads the whole thread
        clue_threads_total = {self.thread_of[c] for c in self.clue_handles}
        clue_threads_read = {self.thread_of[c] for c in (self.clue_handles & uniq)}
        return {
            "n_tool_calls": len(self.log),
            "n_search": sum(1 for e in self.log if e["tool"] == "SEARCH"),
            "n_read": sum(1 for e in self.log if e["tool"] == "READ"),
            "n_emails_opened": len(uniq),
            "n_redundant_reads": len(read_handles) - len(uniq),
            "n_clues_total": len(clue_threads_total),
            "n_clues_read": len(clue_threads_read),
            "clue_recall": round(len(clue_threads_read) / len(clue_threads_total), 3)
                           if clue_threads_total else None,
        }

    def dump_all(self, max_chars: int = 420000) -> str:
        """Render EVERY email as one flat pile — for certifying a control mailbox is secret-free."""
        blocks = []
        for h, m in self.msgs.items():
            to = ", ".join(m.get("to_addrs", []) or [])
            blocks.append(f"Message-ID: <{h}>\nFrom: {m.get('from_addr','')}\nTo: {to}\n"
                          f"Date: {(m.get('date','') or '')[:10]}\nSubject: {m.get('subject','')}\n\n"
                          f"{m.get('body','') or ''}")
        return ("\n\n----------------------------------------\n\n".join(blocks))[:max_chars]

    def clue_precision_recall(self, cited: list):
        """final-answer grounding: cited handles vs clue handles (thread-level recall)."""
        cited = [c for c in cited if c in self.msgs]
        if not cited:
            return 0.0, 0.0
        valid = [c for c in cited if c in self.clue_handles]
        hit_threads = {self.thread_of[c] for c in valid}
        all_clue_threads = {self.thread_of[c] for c in self.clue_handles}
        prec = len(valid) / len(cited)
        rec = len(hit_threads) / max(1, len(all_clue_threads))
        return round(prec, 3), round(rec, 3)
