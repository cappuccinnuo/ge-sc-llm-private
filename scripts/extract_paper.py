"""Extract the paper's text so the evaluation protocol can be read rather than inferred.

Run under the base env (Python 3.9), which is where pypdf is installed:
    conda activate base && python scripts/extract_paper.py
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[1]
PDF = REPO / "data/MANDO-LLM-TOSEM25.pdf"
OUT = REPO / "data/MANDO-LLM-TOSEM25.txt"

reader = PdfReader(str(PDF))
print(f"pages: {len(reader.pages)}")

pages = []
for i, page in enumerate(reader.pages):
    try:
        pages.append(page.extract_text() or "")
    except Exception as exc:
        pages.append("")
        print(f"  page {i+1} failed: {exc}")

text = "\n".join(f"\n===== PAGE {i+1} =====\n{t}" for i, t in enumerate(pages))
OUT.write_text(text, encoding="utf8")
print(f"wrote {len(text)} chars -> {OUT}")

# locate the sections we care about
WANTED = [
    "Two-Phase", "two-phase", "Coarse-Grained", "Fine-Grained",
    "Parameter Setting", "parameter setting", "Experimental Setup",
    "train", "fold", "repeat", "Tokenizer", "tokenizer",
]
print("\nsection headings found:")
for i, t in enumerate(pages):
    for line in t.split("\n"):
        s = line.strip()
        if re.match(r"^\d+(\.\d+)*\s+[A-Z]", s) and len(s) < 80:
            print(f"  p{i+1:3d}  {s}")
