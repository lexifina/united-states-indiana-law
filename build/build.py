"""Builds a git history of the Indiana Code from the yearly title PDFs of the Indiana General Assembly.

    python net.py                         # download every title of every edition, 2017-2026 (cached; one request / 5 s)
    python build.py parse                 # read the PDFs into sections (needs PyMuPDF: run it in Lexifina's backend image)
    python build.py repo <out>            # write the history with git fast-import (standard library and git only)

Source: https://iga.in.gov/ic/<year>/Title_<n>.pdf, the Indiana Code as published each year by the Legislative Services
Agency. iga.in.gov/robots.txt (checked 2026-10-28) names only Googlebot, Bingbot and Slurp; /ic/ is not disallowed.

The 2017 edition is one baseline commit. Then, for each later edition, every section whose words changed is a commit:
- Dated by a stated effective date where the code prints one: the publisher's note on a version of a section ("Note:
  This version of section effective 1-1-2026.") in this edition or the one before. Otherwise dated by the edition
  (1 July of its year, the default effective date of IC 1-1-3-3(b): see EDITION_DAY), and the message says so.
- Credited to the act when exactly one new act appears in the section's source note ("As added by P.L.123-2019,
  SEC.4." / "Amended by ..."); otherwise to the edition, with the acts named in the message.
Where an edition prints a future version of a section (effective after the edition's date and by RECORD_TO), that
version is committed on its date. The repo step makes no network requests, and the same inputs give the same commits.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import net  # noqa: E402

PARSED = net.CACHE / "parsed"
COMMITTER = ("Lexifina", "state-law-history@lexifina.com")
FIRST = 2017
RECORD_TO = "2026-10-28"   # the day this history was built: future versions in force by then are on main
# The day an edition is read as of, and the date of a change it shows without a printed date: 1 July of its year. Each
# edition prints the acts of that year's session, and a SECTION of an act takes effect on 1 July after enactment unless
# it says otherwise (IC 1-1-3-3(b)). Where the code prints a version's own dates ("effective until 7-1-2027"), those
# choose the version in force on that day.
EDITION_DAY = "07-01"

# ---- Parsing ----


def cmd_parse(args: argparse.Namespace) -> None:
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    PARSED.mkdir(parents=True, exist_ok=True)
    jobs = [(y, t) for y in net.YEARS for t in net.TITLES]
    todo = []
    for y, t in jobs:
        out = PARSED / f"{y}_{t}.json.gz"
        pdf_file = net.cache_file(net.title_url(y, t))
        if not pdf_file.exists():
            print(f"missing {y} title {t}: run net.py", flush=True)
            continue
        if out.exists() and not args.force:
            continue
        todo.append((y, t))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        running = set()
        it = iter(todo)
        for job in it:
            running.add(pool.submit(_parse_one, *job))
            if len(running) >= args.workers * 2:
                done, running = wait(running, return_when=FIRST_COMPLETED)
                for f in done:
                    print(f.result(), flush=True)
        for f in running:
            print(f.result(), flush=True)


def _parse_one(year: int, title: str) -> str:
    import parse

    pdf = net.get(net.title_url(year, title), offline=True)
    sha = hashlib.sha256(pdf).hexdigest()
    result = parse.parse(pdf) if pdf else {"sections": [], "blocks": [], "created": "", "pages": 0, "mismatch": []}
    result["sha256"] = sha
    out = PARSED / f"{year}_{title}.json.gz"
    out.write_bytes(gzip.compress(json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8"), mtime=0))
    return f"{year} title {title}: {len(result['sections'])} sections, {result['pages']} pages, {len(result['mismatch'])} mismatches"


_CHECKED: dict[tuple[int, str], bool] = {}   # (year, title) -> whether it has sections


def parsed(year: int, title: str) -> dict:
    """The parsed title, checked against the cached PDF it was read from."""
    data = json.loads(gzip.decompress((PARSED / f"{year}_{title}.json.gz").read_bytes()))
    if (year, title) not in _CHECKED:
        pdf = net.get(net.title_url(year, title), offline=True)
        if data["sha256"] != hashlib.sha256(pdf).hexdigest():
            sys.exit(f"parsed {year} title {title} is not from the cached PDF; run build.py parse --force")
        _CHECKED[(year, title)] = bool(data["sections"])
    return data


def has_sections(year: int, title: str) -> bool:
    if (year, title) not in _CHECKED:
        parsed(year, title)
    return _CHECKED[(year, title)]


# ---- Versions and dates ----

_D = r"(\d{1,2})-(\d{1,2})-(\d{4})"
_UNTIL = re.compile(r"effective until " + _D)
_FROM = re.compile(r"effective " + _D)
_PL = re.compile(r"P\.L\.(\d+)-(\d{4})(?:,\s*SEC\.\s*([\d.]+))?|Acts (\d{4}), P\.L\.(\d+)(?:,\s*SEC\.\s*([\d.]+))?")


def _iso(m: re.Match) -> str:
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"


def edition_day(year: int) -> str:
    return f"{year}-{EDITION_DAY}"


_EFFECTIVE = re.compile(r"^Effective " + _D + r"\.$")


def window(version: dict) -> tuple[str, str]:
    """(from, until) of a version, from its publisher's note; "" where the note states none. A section not yet in
    force is printed with a line "Effective 9-1-2025." above its text; that is its start."""
    for kind, _, text in version["items"]:
        m = _EFFECTIVE.match(text)
        if m:
            return (_iso(m), "")
        if kind != "note" or not text.startswith("Note:"):
            continue
        head = re.split(r"\.\s+See\b", text, maxsplit=1)[0]   # the sentence about this version, not the other one
        until = _UNTIL.search(head)
        start = _FROM.search(head)   # "effective 7-1-2027"; never matches "effective until ..."
        return (_iso(start) if start else "", _iso(until) if until else "")
    return ("", "")


def acts(history: list[str]) -> list[tuple[str, str]]:
    """(act, section) cited in a source note, in order: ("P.L.123-2019", "4")."""
    out = []
    for line in history:
        for m in _PL.finditer(line):
            if m.group(1):
                out.append((f"P.L.{m.group(1)}-{m.group(2)}", m.group(3) or ""))
            else:
                out.append((f"Acts {m.group(4)}, P.L.{m.group(5)}", m.group(6) or ""))
    return out


def history_of(versions: list[dict]) -> list[str]:
    return [t for v in versions for k, _, t in v["items"] if k == "history" and not _EFFECTIVE.match(t)]


# ---- Text ----

_MD = re.compile(r"([\\*_`<])")
_DESIG = re.compile(r"^\((?:[a-zA-Z]{1,5}|\d{1,3}[A-Za-z]?|\d+\.\d+)\)\s")


def esc(t: str) -> str:
    t = _MD.sub(r"\\\1", t)
    return ("\\" + t) if re.match(r"^(#|>|[-+] |\d+[.)] )", t) else t


def render_version(v: dict, keep_version_note: bool) -> list[str]:
    body, source = [], []
    for kind, depth, text in v["items"]:
        if kind == "history":
            if not _EFFECTIVE.match(text):   # the start date of a version, used for dating, not text
                source.append(esc(text))
        elif kind == "note":
            if text.startswith("Note:") and not keep_version_note:
                continue
            body.append(esc(text))
        elif _DESIG.match(text):
            body.append("  " * depth + "- " + esc(text))
        else:
            body.append(esc(text))
    return body + ([""] + source if source else [])


def render(sid: str, versions: list[dict]) -> str:
    lines = [f"# IC {sid}. {esc(versions[0]['heading'])}".rstrip(), ""]
    for i, v in enumerate(versions):
        if i:
            lines += ["", f"## IC {sid}. {esc(v['heading'])}".rstrip(), ""]
        lines += render_version(v, len(versions) > 1)
    return "\n".join(lines).rstrip() + "\n"


def repealed_note(sid: str, year: int, block_lines: list[str]) -> str:
    """A section no longer printed: one line saying so, then the heading and note its chapter or article is printed
    with ("Chapter 2.2. Expired" / "As added by ... Expired 7-1-2025 by P.L.108-2019, SEC.37."), where there is one."""
    lines = [f"# IC {sid}. Not in the Indiana Code {year}", "", f"This section is not printed in the Indiana Code {year}."
             + (" Its chapter or article is printed as:" if block_lines else "")]
    lines += [esc(s) for s in block_lines]
    return "\n".join(lines) + "\n"


def file_of(sid: str) -> str:
    parts = sid.split("-")
    return f"title-{parts[0]}/{'-'.join(parts[:3])}/{sid}.md"


def same(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a is b
    return re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)


# ---- Editions ----


def edition(year: int) -> dict:
    """{"present": {sid: [in-force versions]}, "future": {sid: [(from, version)]}, "blocks": {cid: lines},
    "titles": [...], "urls": {title: url}}."""
    present: dict[str, list[dict]] = {}
    future: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    blocks: dict[str, list[str]] = {}
    urls = {}
    day = edition_day(year)
    for t in net.TITLES:
        data = parsed(year, t)
        if not data["sections"]:
            continue
        urls[t] = net.title_url(year, t)
        for b in data["blocks"]:
            if b["cid"]:
                blocks[b["cid"]] = b["lines"]
        by_sid: dict[str, list[dict]] = defaultdict(list)
        for s in data["sections"]:
            by_sid[s["sid"]].append(s)
        for sid, vs in by_sid.items():
            now = []
            for v in vs:
                start, until = window(v)
                if start and start > day:
                    future[sid].append((start, v))
                elif until and until <= day:
                    continue
                else:
                    now.append(v)
            if now:
                present[sid] = now
            elif vs:
                # Every printed version starts later: the section is new from that date.
                pass
    return {"year": year, "day": day, "present": present, "future": dict(future), "blocks": blocks, "urls": urls}


def block_note(ed: dict, sid: str) -> list[str]:
    parts = sid.split("-")
    for n in (3, 2, 1):
        cid = "-".join(parts[:n])
        lines = ed["blocks"].get(cid)
        if lines and re.search(r"\b(Repealed|Expired|Recodified|Renumbered)\b", lines[0], re.I):
            return lines
    return []


_EXPIRED = re.compile(r"Expired " + r"(\d{1,2})-(\d{1,2})-(\d{4})")


# ---- The history ----


def cmd_repo(args: argparse.Namespace) -> None:
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()) and not (out / ".git").exists():
        sys.exit(f"{out} is not empty and is not a git repository; refusing to overwrite it")
    years = [y for y in net.YEARS if y >= args.from_year and any(has_sections(y, t) for t in net.TITLES)]
    # Phase 1: commits as (day, order, key) -> {"files": {path: text}, "notes": [...], ...}
    groups: dict[tuple[str, int, str], dict] = {}

    def add(day: str, order: int, key: str, path: str, text: str | None, note: str, sid: str, cite: str = "") -> None:
        g = groups.setdefault((day, order, key), {"files": {}, "notes": [], "sids": [], "cites": set(), "sources": set()})
        g["files"][path] = text
        g["sids"].append(sid)
        if note:
            g["notes"].append(note)
        if cite:
            g["cites"].add(cite)

    first = edition(years[0])
    for sid, vs in first["present"].items():
        add(first["day"], 0, f"baseline|{first['year']}|", file_of(sid), render(sid, vs), "", sid)
    baseline_count = len(first["present"])
    seen_titles = set(first["urls"])

    state: dict[str, tuple[str, list[str]]] = {sid: (render(sid, vs), history_of(vs)) for sid, vs in first["present"].items()}
    state_day: dict[str, str] = {sid: first["day"] for sid in state}

    def change(day: str, sid: str, text: str, hist: list[str], how: str, ed_year: int, source: str) -> None:
        """Record a change of sid to text on day, crediting the one new act in its source note if there is one."""
        before_text, before_hist = state.get(sid, (None, []))
        if same(before_text, text):
            state[sid] = (text, hist)
            return
        if sid in last_group and day <= state_day[sid]:
            # Not after the change already recorded for this file: the later text replaces it in that commit.
            groups[last_group[sid]]["files"][file_of(sid)] = text
            state[sid] = (text, hist)
            return
        old = {a for a, _ in acts(before_hist)}
        new = [(a, s) for a, s in acts(hist) if a not in old]
        new_acts = sorted({a for a, _ in new})
        dated = how
        if len(new_acts) == 1:
            act = new_acts[0]
            secs = sorted({s for a, s in new if s})
            key = f"act:{act}"
            cite = f"{act}, SEC.{secs[0]}" if len(secs) == 1 else act
            gk = (day, 1, key + f"|{dated}|{ed_year}")
            add(*gk, file_of(sid), text, "", sid, cite)
        else:
            named = ", ".join(new_acts) if new_acts else "no new act"
            gk = (day, 2, f"edition|{dated}|{ed_year}")
            add(*gk, file_of(sid), text, f"IC {sid} ({named})", sid)
        last_group[sid] = gk
        groups_key_sources[(day, sid)] = source
        state[sid] = (text, hist)
        state_day[sid] = day

    groups_key_sources: dict[tuple[str, str], str] = {}
    last_group: dict[str, tuple[str, int, str]] = {}
    pending: dict[str, list[tuple[str, dict]]] = {}

    def apply_future(upto: str, after: str, ed_year: int, ed_url: dict) -> None:
        """Future versions printed in an earlier edition that take effect in (after, upto]."""
        for sid in sorted(pending):
            for start, v in sorted(pending[sid], key=lambda p: p[0]):
                if after < start <= upto:
                    t = sid.split("-")[0]
                    change(start, sid, render(sid, [v]), history_of([v]), "note", ed_year, ed_url.get(t, ""))

    pending = first["future"]
    prev_ed = first
    first = {k: first[k] for k in ("year", "day", "urls")}   # the rest is not needed again
    for y in years[1:]:
        ed = edition(y)
        # 1. Versions the earlier edition printed as taking effect before this edition's day.
        apply_future(ed["day"], prev_ed["day"], prev_ed["year"], prev_ed["urls"])
        # 2. This edition's text.
        # A title missing from every earlier edition (the 2017 Title 31 PDF holds only its table of contents) starts
        # with a baseline of its own from the first edition that prints it.
        for t in sorted(set(ed["urls"]) - seen_titles):
            for sid, vs in ed["present"].items():
                if sid.split("-")[0] == t and sid not in state:
                    add(ed["day"], 0, f"baseline|{ed['year']}|{t}", file_of(sid), render(sid, vs), "", sid)
                    state[sid] = (render(sid, vs), history_of(vs))
                    state_day[sid] = ed["day"]
        seen_titles |= set(ed["urls"])
        for sid in sorted(set(state) | set(ed["present"])):
            t = sid.split("-")[0]
            vs = ed["present"].get(sid)
            if vs is None:
                if sid in state and not state[sid][0].startswith(f"# IC {sid}. Not in the Indiana Code"):
                    if t not in ed["urls"]:
                        continue
                    lines = block_note(ed, sid)
                    # The chapter's note can carry the day: "Expired 7-1-2025 by P.L.108-2019, SEC.37."
                    exp = [_iso(m) for l in lines for m in _EXPIRED.finditer(l)]
                    exp = [d for d in exp if prev_ed["day"] <= d <= ed["day"]]
                    # Credit only the acts the note says ended it, not the one that added the chapter.
                    ended = [re.split(r"\b(?=Repealed|Expired|Recodified|Renumbered)", l, maxsplit=1)[-1] for l in lines[1:]]
                    change(exp[-1] if exp else ed["day"], sid, repealed_note(sid, ed["year"], lines),
                           state[sid][1] + ended, "note" if exp else "edition", ed["year"], ed["urls"].get(t, ""))
                continue
            text = render(sid, vs)
            if same(state.get(sid, (None,))[0], text):
                state[sid] = (text, history_of(vs))
                continue
            starts = [window(v)[0] for v in vs]
            stated = max((s for s in starts if s and s > prev_ed["day"]), default="")
            if stated:
                change(stated, sid, text, history_of(vs), "note", ed["year"], ed["urls"][t])
            else:
                change(ed["day"], sid, text, history_of(vs), "edition", ed["year"], ed["urls"][t])
        pending = ed["future"]
        prev_ed = ed
    last_ed = prev_ed
    apply_future(RECORD_TO, last_ed["day"], last_ed["year"], last_ed["urls"])

    # Phase 2: fast-import, in date order.
    out.mkdir(parents=True, exist_ok=True)
    if not (out / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=out, check=True)
    fi = subprocess.Popen(["git", "fast-import", "--quiet", "--done", "--force"], cwd=out, stdin=subprocess.PIPE)
    w = fi.stdin
    mark = [0]

    def blob(b: bytes) -> None:
        w.write(b"data %d\n" % len(b)); w.write(b); w.write(b"\n")

    def epoch(day: str) -> int:
        return int((datetime.strptime(day, "%Y-%m-%d") - datetime(1970, 1, 1)).total_seconds()) + 12 * 3600

    def commit(author: tuple[str, str], day: str, message: str, files: dict[str, str | None]) -> None:
        mark[0] += 1
        w.write(f"commit refs/heads/main\nmark :{mark[0]}\nauthor {author[0]} <{author[1]}> {epoch(day)} +0000\n"
                f"committer {COMMITTER[0]} <{COMMITTER[1]}> {epoch(day)} +0000\n".encode())
        blob(message.encode("utf-8"))
        if mark[0] > 1:
            w.write(f"from :{mark[0] - 1}\n".encode())
        for path in sorted(files):
            if files[path] is None:
                w.write(f"D {path}\n".encode())
            else:
                w.write(f"M 100644 inline {path}\n".encode()); blob(files[path].encode("utf-8"))
        w.write(b"\n")

    def listed(sids: list[str]) -> str:
        s = sorted(set(sids), key=_sort_key)
        head = ", ".join(f"IC {x}" for x in s[:3]) + (f" and {len(s) - 3} more" if len(s) > 3 else "")
        return f"{len(s)} section{'s' if len(s) != 1 else ''} ({head})" if len(s) > 1 else head

    stats = {"baseline": 0, "act": 0, "edition": 0, "note_dated": 0, "edition_dated": 0}
    last_day = first["day"]
    for (day, order, key) in sorted(groups):
        g = groups[(day, order, key)]
        files = g["files"]
        sources = sorted({groups_key_sources.get((day, s), "") for s in g["sids"]} - {""})
        last_day = max(last_day, day)
        if order == 0:
            _, y, only = key.split("|")
            ts = [only] if only else sorted(first["urls"], key=float)
            what = f"Title {only} of the Indiana Code" if only else "The Indiana Code"
            why = (f"\n\nThe {first['year']} PDF of Title {only} holds only the title's table of contents, so the title "
                   f"starts from the {y} edition." if only else "")
            commit((f"Indiana Code {y}", f"edition-{y}@in-code.invalid"), day,
                   f"{what} as printed in the {y} edition: {len(files)} sections{why}\n\n"
                   f"Each section as in force on {day} by the edition's own notes on versions. The edition is read as of "
                   f"1 July, the day a SECTION of an act takes effect unless it says otherwise (IC 1-1-3-3(b)).\n\n"
                   f"Consolidated: {day}\nPrinted-in: Indiana Code {y}\n"
                   + "".join(f"Source: {net.title_url(int(y), t)}\n" for t in ts), files)
            stats["baseline"] += 1
            continue
        _, dated, ed_year = key.rsplit("|", 2)
        when = (f"The date is one the Indiana Code prints: a version's \"Note: This version of section effective ...\", "
                f"or a chapter's \"Expired <date>\"." if dated == "note" else
                f"Dated by the edition: 1 July of {int(ed_year)}, the day a SECTION of an act of the {int(ed_year)} session takes "
                f"effect unless it says otherwise (IC 1-1-3-3(b)). The Indiana Code {ed_year} prints no other date for this "
                f"change, and the act itself was not read, so a different effective date in the act would not show here.")
        stats["note_dated" if dated == "note" else "edition_dated"] += 1
        src = "".join(f"Source: {u}\n" for u in sources)
        if order == 1:
            act = key.split("|", 1)[0].split(":", 1)[1]
            m = re.match(r"P\.L\.(\d+)-(\d{4})", act) or re.match(r"Acts (\d{4}), P\.L\.(\d+)", act)
            n, yr = (m.group(1), m.group(2)) if act.startswith("P.L.") else (m.group(2), m.group(1))
            cites = sorted(g["cites"])
            law = cites[0] if len(cites) == 1 else act
            commit((f"{act} (Acts of Indiana {yr})", f"in-{yr}-pl-{n}@session-law.invalid"), day,
                   f"{act} takes effect: changes {listed(g['sids'])}\n\n{when}\n\nIn-force: {day}\nLaw: {law}\n{src}"
                   + (f"Printed-in: Indiana Code {ed_year}\n" if dated == "edition" else ""), files)
            stats["act"] += 1
        else:
            notes = "\n".join(f"- {x}" for x in sorted(g["notes"], key=lambda s: _sort_key(s.split()[1])))
            commit((f"Indiana Code {ed_year}", f"edition-{ed_year}@in-code.invalid"), day,
                   f"Changes printed in the Indiana Code {ed_year}, act not named: {listed(g['sids'])}\n\n{when} Each section's source note names no new act, "
                   f"or more than one, so these changes are credited to the edition:\n\n{notes}\n\n"
                   f"In-force: {day}\nPrinted-in: Indiana Code {ed_year}\n{src}", files)
            stats["edition"] += 1
    w.write(b"done\n"); w.close(); fi.wait()
    last = subprocess.run(["git", "rev-parse", "main"], cwd=out, capture_output=True, text=True).stdout.strip()

    # The documentation commit, dated the last in-force date.
    from docs import CHANGES, LICENSE, corpus, readme, reproduce

    files_now = subprocess.run(["git", "ls-tree", "-r", "--name-only", "main"], cwd=out, capture_output=True, text=True).stdout.split()
    manifest = "".join(f"{h}  {u}\n" for u, h in sorted(net.READ.items()))
    info = {
        "sections": len(files_now), "titles": len({f.split("/")[0] for f in files_now}),
        "chapters": len({"/".join(f.split("/")[:2]) for f in files_now}), "baseline_sections": baseline_count,
        "first_day": first["day"], "record_to": last_day, "built": RECORD_TO, "years": years,
        "commits": sum(stats[k] for k in ("baseline", "act", "edition")) + 1, **stats,
        "downloads": sum(1 for u in net.READ if u.endswith(".pdf")),
        "present_pdfs": sum(1 for y in years for t in net.TITLES if has_sections(y, t)),
        "bytes": sum(net.cache_file(u).stat().st_size for u in net.READ),
        "data_sha256": hashlib.sha256(manifest.encode()).hexdigest(), "last": last, "python": sys.version.split()[0],
        "git": subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.split()[-1],
        "blob": subprocess.run(["git", "hash-object", str(Path(__file__).resolve())], capture_output=True, text=True).stdout.strip(),
    }
    fi = subprocess.Popen(["git", "fast-import", "--quiet", "--done", "--force"], cwd=out, stdin=subprocess.PIPE)
    w = fi.stdin
    tool = (HERE / "tool.py").read_text(encoding="utf-8")
    docs = {
        "README.md": readme(info), "REPRODUCE.md": reproduce(info), "CHANGES.md": CHANGES, "LICENSE.md": LICENSE,
        "corpus.json": corpus(info), "tools/in_.py": tool,
        **{f"build/{n}": (HERE / n).read_text(encoding="utf-8") for n in ("build.py", "net.py", "parse.py", "docs.py", "tool.py")},
        "build/DATA-SHA256SUMS": manifest,
    }
    w.write(f"commit refs/heads/main\nmark :1\nauthor {COMMITTER[0]} <{COMMITTER[1]}> {epoch(last_day)} +0000\n"
            f"committer {COMMITTER[0]} <{COMMITTER[1]}> {epoch(last_day)} +0000\n".encode())
    blob(b"Documentation, the tool, and the build with the checksums of its data\n")
    w.write(f"from {last}\n".encode())
    for path in sorted(docs):
        w.write(f"M 100644 inline {path}\n".encode()); blob(docs[path].encode("utf-8"))
    w.write(b"\ndone\n"); w.close(); fi.wait()
    subprocess.run(["git", "checkout", "-q", "-f", "main"], cwd=out, check=True)
    print(json.dumps({k: v for k, v in info.items() if k not in ("years",)}, indent=1))


def _is_repeal(v: dict) -> bool:
    return any(k == "note" and "repeal of section" in t for k, _, t in v["items"])


def _sort_key(sid: str) -> list:
    out = []
    for p in sid.split("-"):
        for q in p.split("."):
            out.append(int(q) if q.isdigit() else 0)
        out.append(-1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse"); p.add_argument("--force", action="store_true"); p.add_argument("--workers", type=int, default=12)
    r = sub.add_parser("repo"); r.add_argument("out"); r.add_argument("--from-year", type=int, default=FIRST, help=argparse.SUPPRESS)
    a = ap.parse_args()
    {"parse": cmd_parse, "repo": cmd_repo}[a.cmd](a)


if __name__ == "__main__":
    main()
