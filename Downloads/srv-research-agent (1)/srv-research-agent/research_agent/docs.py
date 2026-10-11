"""Load the research pack. Each file starts with source / url / published / type lines, then '---'."""
import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

KEYS = {
    "source": "source", "publisher": "source",
    "url": "url", "link": "url",
    "published": "date", "published on": "date", "publication date": "date", "date": "date",
    "type": "doc_type",
}
LINE = re.compile(
    r"^[#>*\s_\-]*(source|publisher|url|link|published on|published|publication date|date|type)\s*[:：]\s*(.+?)\s*$", re.I)

# Text aimed at an AI/summariser is never legitimate content of a financial document.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?)",
    r"(note|message|instructions?) (for|to) (ai|llm|assistants?|language models?|summari[sz]ation)",
    r"do not mention (this|these|that) (note|instruction|message)",
    r"disregard (all |any )?(previous|prior|above) ",
    r"(you are|act as) (now )?an? (ai|assistant|language model)",
    r"in your (summary|response|answer|brief),? (state|say|write|claim) that",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


def find_injection(text: str) -> List[str]:
    hits = []
    for rx in _INJ:
        m = rx.search(text)
        if m:
            hits.append(m.group(0))
    return hits


@dataclass
class Doc:
    id: str
    filename: str
    text: str
    source: str = ""
    url: str = ""
    date: str = ""
    doc_type: str = ""
    injection: List[str] = field(default_factory=list)

    def label(self) -> str:
        flag = "  ⚠ injection-like text" if self.injection else ""
        return f"[{self.id}] {self.source or self.filename} — {self.date or 'date n/a'}{flag}"

    def age_days(self, today: date) -> Optional[int]:
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"):
            try:
                return (today - datetime.strptime(self.date.strip(), fmt).date()).days
            except ValueError:
                continue
        return None


def _clean(v: str) -> str:
    return re.sub(r"[*_`]", "", v).strip()


def parse_header(text: str) -> dict:
    meta = {}
    for line in text.splitlines()[:20]:
        m = LINE.match(line)
        if m:
            meta.setdefault(KEYS[m.group(1).lower()], _clean(m.group(2)))
    return meta


def load_pack(folder: str) -> list:
    paths = sorted(p for p in Path(folder).iterdir()
                   if p.suffix.lower() in {".md", ".txt", ".html", ".htm", ".csv", ".json"}
                   and not p.name.lower().startswith("readme"))  # placeholder/readme files are not documents
    docs = []
    for i, p in enumerate(paths, 1):
        raw = p.read_text(encoding="utf-8", errors="replace")
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw)) if p.suffix.lower() in {".html", ".htm"} else raw
        meta = parse_header(text)
        # injection scan runs on the RAW file so hidden HTML comments are included
        docs.append(Doc(id=f"S{i}", filename=p.name, text=text, injection=find_injection(raw), **meta))
    return docs
