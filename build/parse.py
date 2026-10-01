"""Sections of one title PDF of the Indiana Code (iga.in.gov/ic/<year>/Title_<n>.pdf), with PyMuPDF.

The PDFs are typeset the same way in every edition from 2017: 10 pt Times on a text block from x=126 to x=486.
- A section starts with a bold row "IC 6-1.1-17-16.2" and its bold heading to the right (wrapping onto further bold rows).
  A bold "IC" row with fewer than four parts starts a title, article or chapter: its table of contents is skipped, and
  its own words are kept (they say when a whole chapter or article was repealed).
- Inside a section, italic rows are the source note ("As added by P.L.5-1988, SEC.1. Amended by ...") and the publisher's
  version notes ("Note: This version of section effective until 7-1-2027. ..."); roman rows are the statute text.
- A paragraph starts on an indented row (x > 126) after a short row (the text is justified to x=486, so a row that ends
  well short of it ends its paragraph), or after a row at another indent, or on a row with more than one cell (a table
  row). Continuation rows sit at x=126 or, for numbered subdivisions, at the paragraph's own hanging indent.
  The indent of a paragraph's first row gives its depth: 139.3 for "Sec." and (a), 148.3 for (1), 157.4 for (A) ...
- The footer "Indiana Code <year>" (at the foot of every page) is page furniture and dropped.

Every row of every page is assigned to exactly one section or heading block; `check` counts the characters both ways.
"""

from __future__ import annotations

import re
from typing import Any

LEFT = 126.0
RIGHT = 486.0
STEP = 9.05
FIRST = 139.3

_IC_RUN = re.compile(r"^IC (\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)*)(?: +(\S.*))?$")
_DESIG = re.compile(r"^\((?:[a-zA-Z]{1,5}|\d{1,3}[A-Za-z]?|\d+\.\d+)\)\s")
_FOOTER = re.compile(r"^Indiana Code \d{4}$")


def _rows(page) -> list[dict[str, Any]]:
    """The page's rows, top to bottom: lines on the same baseline merged, left to right, into cells."""
    lines = []
    for b in page.get_text("dict", sort=False)["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            spans = [s for s in l["spans"] if s["text"]]
            text = "".join(s["text"] for s in spans)
            if not text.strip():
                continue
            fonts = [s["font"] for s in spans if s["text"].strip()]
            size = max((s["size"] for s in spans), default=10)
            lines.append({"x0": l["bbox"][0], "x1": l["bbox"][2], "y": round(l["bbox"][3], 0), "text": text,
                          "bold": bool(fonts) and all("Bold" in f for f in fonts),
                          "italic": bool(fonts) and all("Italic" in f for f in fonts), "size": size})
    lines.sort(key=lambda r: (r["y"], r["x0"]))
    rows: list[dict[str, Any]] = []
    for l in lines:
        if rows and abs(rows[-1]["y"] - l["y"]) <= 1.5:
            rows[-1]["cells"].append(l)
        else:
            rows.append({"y": l["y"], "cells": [l]})
    for r in rows:
        cells = r["cells"]
        r["x0"] = cells[0]["x0"]
        r["x1"] = cells[-1]["x1"]
        r["bold"] = cells[0]["bold"]
        r["italic"] = all(c["italic"] for c in cells)
        r["size"] = max(c["size"] for c in cells)
        r["texts"] = [c["text"].strip() for c in cells]
    return rows


def _join(a: str, b: str) -> str:
    if a.endswith("-") and not a.endswith(" -"):
        return a + b
    return a + " " + b


def _depth(x: float) -> int:
    return max(0, round((x - FIRST) / STEP))


_NOTE = re.compile(r"^(?:Note|Revisor's [Nn]ote):")
_ENDS = re.compile(r"(?:[;:.]|\band|\bor)$")


def parse(pdf: bytes) -> dict[str, Any]:
    """{"sections": [version, ...] in print order, "blocks": [heading block, ...], ...}.

    A version is {"sid", "heading", "items": [[kind, depth, text], ...]} with kind "text" (statute text, including the
    bracketed recodification citations printed with it), "note" (an italic note: "Note: This version of section ..." or
    "Revisor's note: ...") or "history" (the source note). A heading block is {"cid", "lines"}: the words printed under
    a title, article or chapter heading before its table of contents.
    """
    import fitz  # PyMuPDF, in Lexifina's backend image

    doc = fitz.open(stream=pdf, filetype="pdf")
    sections: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None   # the section or heading block being read
    kind = ""                            # "section" | "block"
    in_heading = False
    prev: dict[str, Any] | None = None   # the previous row of the section, for paragraph breaks

    for page in doc:
        rows = _rows(page)
        for i, r in enumerate(rows):
            text = " ".join(t for t in r["texts"] if t)
            # The footer is the page's last row (at y=720, or higher on a short last page); 11 pt, 10 pt in 2018.
            if i == len(rows) - 1 and _FOOTER.match(text):
                continue
            # The citation and heading are usually two runs; sometimes one ("IC 36-4-1-4.1 Repealed").
            m = _IC_RUN.match(r["texts"][0]) if r["bold"] and r["x0"] < LEFT + 2 else None
            if m:
                rest = " ".join(([m.group(2)] if m.group(2) else []) + r["texts"][1:]).strip()
                if len(m.group(1).split("-")) == 4:
                    cur = {"sid": m.group(1), "heading": rest, "items": [], "raw": [text]}
                    sections.append(cur)
                    kind = "section"
                else:
                    cur = {"cid": m.group(1), "lines": [rest] if rest else []}
                    blocks.append(cur)
                    kind = "block"
                in_heading = True
                prev = None
                continue
            if cur is None:
                cur = {"cid": "", "lines": []}
                blocks.append(cur)
                kind = "block"
            if kind == "block":
                # The block's own words, not its table of contents ("Art. 1." / "Ch. 1." / "1-1-1-1" entries).
                if cur.get("toc"):
                    continue
                if re.match(r"^(Art|Ch)\. \d", r["texts"][0]) or re.match(r"^\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?){3}$", r["texts"][0]):
                    cur["toc"] = True
                    continue
                cur["lines"].append(text)
                continue
            cur["raw"].append(text)
            items = cur["items"]
            if in_heading and r["bold"] and r["x0"] > LEFT + 40:
                cur["heading"] = _join(cur["heading"], text) if cur["heading"] else text
                continue
            in_heading = False
            indented = r["x0"] > LEFT + 1
            short_before = prev is not None and prev["x1"] < RIGHT - 12
            if r["italic"]:
                note = bool(_NOTE.match(text))
                is_new = (prev is None or not prev["italic"] or note or short_before
                          or (indented and abs(prev["x0"] - r["x0"]) > 1))
                if is_new:
                    items.append(["note" if note else "history", 0, text])
                else:
                    items[-1][2] = _join(items[-1][2], text)
                prev = r
                continue
            table = len(r["texts"]) > 1
            is_new = (prev is None or prev["italic"] or table or len(prev["texts"]) > 1 or short_before
                      or text.startswith("Sec. ")
                      or (indented and (abs(prev["x0"] - r["x0"]) > 1
                                        or (_DESIG.match(text) and bool(_ENDS.search(items[-1][2]))))))
            if is_new or not items:
                items.append(["text", _depth(r["x0"]), " | ".join(t for t in r["texts"] if t) if table else text])
            else:
                items[-1][2] = _join(items[-1][2], text)
            prev = r
    # The check: every word of every row of a section is in what was read from it, in order.
    squash = lambda t: re.sub(r"\s+", "", t)
    bad = []
    for s in sections:
        raw = squash("".join(s.pop("raw")))
        got = squash("IC " + s["sid"] + s["heading"] + "".join(t for _, _, t in s["items"]))
        if raw != got.replace("|", "") and raw != got:
            n = next((i for i, (a, b) in enumerate(zip(raw, got)) if a != b), min(len(raw), len(got)))
            bad.append([s["sid"], raw[max(0, n - 40):n + 40], got[max(0, n - 40):n + 40]])
    meta = doc.metadata or {}
    return {"sections": sections, "blocks": [{"cid": b["cid"], "lines": b["lines"]} for b in blocks],
            "created": meta.get("creationDate", ""), "pages": doc.page_count, "mismatch": bad}

