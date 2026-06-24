"""Load and clean the enron_10 corpus into flat email records for retrieval.

Each record is one message with its substantive prose (forwarding boilerplate /
headers / routing tags stripped) plus the real From/To/date/subject we need to fill
`enron_anchor`. Real identities are kept here — anonymisation to Person-labels happens
later, in Step 2.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

ENRON10 = Path("data/enron_10")

# ---------------------------------------------------------------------------
# Body cleaning (shared logic with the old resolve_anchors retriever)
# ---------------------------------------------------------------------------

def clean_body(body: str) -> str:
    """Strip forwarding dividers / header lines / routing tags / signature & contact blocks
    so the text is the substantive prose, not Lotus-Notes forward boilerplate. Verbatim —
    only boilerplate is removed, no paraphrase or truncation of substantive content."""
    b = body or ""
    b = re.sub(r"-{3,}.*?-{3,}", " ", b)                                  # ---- Forwarded by ... ----
    b = re.sub(r"\bForwarded by[^\n]*", " ", b, flags=re.I)
    b = re.sub(r"\b(From|To|cc|bcc|Sent|Subject|Date)\s*:\s*[^\n]*", " ", b, flags=re.I)
    b = re.sub(r"[\w.+-]+@[\w.-]+", " ", b)                               # emails
    # signature / contact blocks (address / phone / fax)
    b = re.sub(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b\s*\(?\s*(phone|fax|cell|tel|telephone|direct|office|mobile|main)?\s*\)?",
               " ", b, flags=re.I)                                        # 713-853-5620 (phone)
    b = re.sub(r"\(\s*(phone|fax|cell|tel|telephone|direct|office|mobile|main)\s*\)", " ", b, flags=re.I)
    b = re.sub(r"\bEB\s*\d{3,4}[a-z]?\b", " ", b)                         # Enron building/room code EB 3801a
    b = re.sub(r"\b\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+"
               r"(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Suite|Ste|Floor|Fl)\b\.?",
               " ", b)                                                    # 1400 Smith Street
    b = re.sub(r"\b[A-Z][a-zA-Z]+,\s+[A-Z][a-zA-Z]{2,}\s+\d{5}(?:-\d{4})?\b", " ", b)  # Houston, Texas 77002
    b = re.sub(r"\b/?(HOU|ECT|ECC|NA|LON|CAL|ENRON|Corp|EnronXGate)\b(/\w+)*", " ", b)  # routing tags
    b = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b(\s+\d{1,2}:\d{2}\s*[AP]M)?", " ", b)  # inline dates
    b = re.sub(r"\s+/\s+,", ",", b)                                       # leftover " / ," from stripped routing
    return re.sub(r"\s+", " ", b).strip()


@dataclass
class Email:
    idx: int
    message_id: str
    thread_id: str
    from_addr: str
    from_name: str
    to_addrs: list[str]
    to_names: list[str]
    date: str
    subject: str
    body: str            # cleaned substantive prose
    index_text: str      # subject + body, what BM25 indexes

    def snippet(self, n: int = 280) -> str:
        return self.body[:n]

    def anchor_dict(self) -> dict:
        """The real-email fields written into a topic's enron_anchor."""
        return {
            "message_id": self.message_id,
            "from": self.from_name,
            "from_addr": self.from_addr,
            "to": self.to_names[:4],
            "date": self.date[:10],
            "subject": self.subject,
            "snippet": self.snippet(400),
        }

    def for_judge(self, n: int = 320) -> dict:
        """Compact view handed to the listwise fit-judge."""
        return {
            "id": self.idx,
            "from": self.from_name,
            "to": ", ".join(self.to_names[:3]),
            "date": self.date[:10],
            "subject": self.subject,
            "snippet": self.snippet(n),
        }


def load_emails(enron10_dir: Path = ENRON10, min_chars: int = 25) -> list[Email]:
    """Flatten threads.jsonl into cleaned Email records (dropping empty / boilerplate-only
    messages). Address -> display-name mapping comes from users.json (falls back to the
    raw address for outside parties)."""
    enron10_dir = Path(enron10_dir)
    users = json.loads((enron10_dir / "users.json").read_text())
    addr2name = {u["email"]: u["display_name"] for u in users}

    def name(addr: str) -> str:
        if not addr:
            return ""
        return addr2name.get(addr, addr.split("@")[0].replace(".", " ").title())

    emails: list[Email] = []
    with open(enron10_dir / "threads.jsonl") as f:
        for line in f:
            r = json.loads(line)
            for m in r["messages"]:
                subject = (m.get("subject") or "").strip()
                body = clean_body(m.get("body", ""))
                index_text = f"{subject} {body}".strip()
                if len(index_text) < min_chars:
                    continue
                to_addrs = m.get("to_addrs") or []
                emails.append(Email(
                    idx=len(emails),
                    message_id=m.get("message_id", ""),
                    thread_id=r.get("thread_id", ""),
                    from_addr=m.get("from_addr", "") or "",
                    from_name=name(m.get("from_addr", "")),
                    to_addrs=to_addrs,
                    to_names=[name(a) for a in to_addrs],
                    date=(m.get("date") or "")[:19],
                    subject=subject,
                    body=body,
                    index_text=index_text,
                ))
    return emails


if __name__ == "__main__":
    em = load_emails()
    print(f"{len(em)} cleaned emails")
    for e in em[:3]:
        print(f"  [{e.idx}] {e.date[:10]} {e.from_name} -> {', '.join(e.to_names[:2])} | {e.subject[:40]}")
        print(f"        {e.snippet(120)}")
