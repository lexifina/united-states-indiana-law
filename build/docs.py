"""The documentation files of the Indiana Code git history, filled in by build.py with the figures of each build."""

from __future__ import annotations

import json

EX = "title-35/35-42-1/35-42-1-1.md"

ROBOTS = """User-agent: Googlebot
User-agent: Bingbot
User-agent: Slurp
Disallow: /search/
Disallow: /pdf-documents/
Request-rate: 1/5
Visit-time: 0300-1200"""


def readme(i: dict) -> str:
    return f"""# Git for the Indiana Code

The Indiana Code, section by section, as a git history: the {i['years'][0]} edition as the starting point, then a commit
for each change in each later edition, to {i['record_to']}. **Each commit is a change taking effect.** Its author is the
act that made it, where the section's source note names one new act, and its date is the day the change took effect
where the code prints that day; otherwise the edition's date, and the commit message says so.

| The question | The command |
| --- | --- |
| What did IC 35-42-1-1 say on 1 August 2021? | `python tools/in_.py on 2021-08-01 {EX}` |
| Which act wrote each line? | `git blame {EX}` |
| What changed between two dates? | `python tools/in_.py diff 2018-01-01 2026-07-01 {EX} --words` |
| Everything one act changed | `python tools/in_.py act P.L.174-2019` |
| Every change to a section, with its dates | `python tools/in_.py log {EX}` |
| The most amended sections of a title | `git log --format= --name-only -- title-6 \\| sort \\| uniq -c \\| sort -rn \\| head` |

`tools/in_.py` needs only Python 3 and git. It picks the text by each commit's `In-force:` date, so the answer does not
depend on your time zone or the time of day.

## What is here

{i['titles']} titles, {i['chapters']} chapters and {i['sections']} section files. There are {i['commits']} commits: the
{i['years'][0]} edition ({i['baseline_sections']} sections) and Title 31 from the 2018 edition (the 2017 PDF of Title 31
holds only its table of contents), {i['act']} credited to one act, {i['edition']} credited to an
edition (the source notes of their sections name no new act, or more than one), and this documentation. Of the change
commits, {i['note_dated']} are dated by an effective date the code prints, and {i['edition_dated']} by the edition.

Each section is one Markdown file, `title-<t>/<t>-<article>-<chapter>/<section>.md`. The first line is the citation
and heading; then one paragraph or designated provision per line (`- (a)`, `  - (1)`, `    - (A)`), so `git blame`
names a change for every provision; then the section's source note ("As added by P.L.5-1988, SEC.1. Amended by ...").
A repealed section keeps the code's one-line entry ("Repealed" with its source note). A section that stops being
printed at all (because its whole chapter or article was repealed or moved) becomes a one-line note saying so, with the
chapter's or article's repeal line where the code prints one.

## How a change is dated and credited

The text comes from the Indiana General Assembly's yearly PDF of each title, {i['years'][0]} to {i['years'][-1]}.

- **Dated by a printed date.** Where a section is printed in more than one version, the code says when each takes
  effect ("Note: This version of section effective 1-1-2026."). A change to such a version is dated that day, and a
  version printed as taking effect after an edition is committed on its own date, up to {i['built']}.
- **Dated by the edition.** Otherwise the change is dated 1 July of the edition's year. Each edition prints the acts of
  that year's session, and a SECTION of an act takes effect on 1 July after its enactment unless it says otherwise
  (IC 1-1-3-3(b)). Acts that take effect on passage or on another day are not told apart from those here; the acts
  themselves were not read. The commit message says which kind of date it has.
- **Credited to an act** when the section's source note gained exactly one act since the edition before. The act is
  the author ("P.L.174-2019 (Acts of Indiana 2019)") and is in the `Law:` trailer. Otherwise the change is credited to
  the edition, and the message lists the acts each section's note gained.

Commits are dated at noon UTC.

## What it does not show

- **Before {i['years'][0]}.** The history starts from the {i['years'][0]} edition; the earlier yearly PDFs are not published.
- **More than one change in a year.** Between two editions only the later text is available, so two acts amending one
  section in one session are one commit credited to the edition, unless the code printed them as separate versions.
- **The exact day of most changes.** See above: most are dated 1 July, the statutory default, not the act's own date.
- **Future changes** taking effect after {i['built']}: they are printed in the {i['years'][-1]} edition but not on `main`.
- **Official status.** These are the Indiana General Assembly's published PDFs read as text. For anything that matters,
  read the code and the act.

## How it is built

From the yearly title PDFs at `https://iga.in.gov/ic/<year>/Title_<n>.pdf`, read with PyMuPDF. The build script is in
[`build/`](build/) with the checksums of every PDF it read; it makes no network requests when it writes the history, and
the same PDFs give the same commits. [REPRODUCE.md](REPRODUCE.md) records the sources, the robots.txt check, the commands,
the decisions made by hand and what AI models did; [CHANGES.md](CHANGES.md) records how the history changes.

Lexifina keeps the US Code ([lexifina/united-states-law](https://github.com/lexifina/united-states-law)) and other
states' laws in the same form, as part of [lexifina/global-law](https://github.com/lexifina/global-law).

Built by [Lexifina](https://lexifina.com). For corrections, open an issue.

## License

See [LICENSE.md](LICENSE.md): the statute text is the law of Indiana; the history, messages, tools and documentation are
released under CC BY 4.0.
"""


def reproduce(i: dict) -> str:
    mb = i["bytes"] / 1e6
    return f"""# How this history was made, and how to make it again

## Short version

```sh
cd build
python net.py                         # every title PDF of every edition (cached; one request every 5 seconds)
sha256sum -c DATA-SHA256SUMS          # (after decompressing the cache) the PDFs are the ones this history was built from
python build.py parse                 # needs PyMuPDF (pip install pymupdf==1.25.5)
python build.py repo ../../rebuilt
git -C ../../rebuilt log --format=%H  # the same commits, with the same hashes
```

The last change commit is `{i['last']}`.

## Sources

| What | Where | Requests | Retrieved |
| --- | --- | ---: | --- |
| robots.txt | `https://iga.in.gov/robots.txt` | 1 | 2026-10-28 |
| Each title of each yearly edition, {i['years'][0]}-{i['years'][-1]} | `https://iga.in.gov/ic/<year>/Title_<n>.pdf` for titles 1-6, 7.1, 8-36 | {i['downloads']} | 2026-10-28 |

{i['present_pdfs']} of the PDFs hold sections; titles 17, 18 and 19 are one-page notes that the titles were repealed.
The cache is {mb:,.0f} MB (gzip). Every response is listed with its sha256 in `build/DATA-SHA256SUMS` (sha256 of that
list: `{i['data_sha256']}`). Requests were made one at a time, 5 seconds apart, with the user agent
`Mozilla/5.0 (compatible; Lexifina state law history; +https://lexifina.com/watch)`. The host served every PDF to that
user agent (`200`/`206 application/pdf`); none was refused, and no other user agent was used. A file the host does not
have answers with its web application's HTML page; the fetcher records that as absent.

**robots.txt, checked 28 October 2026** (`https://iga.in.gov/robots.txt`, `text/plain`, 144 bytes):

```
{ROBOTS}
```

The only group names Googlebot, Bingbot and Slurp; there is no `*` group and nothing for ClaudeBot, anthropic-ai or
Claude-Web, and `/ic/` is not disallowed for anyone. This build kept to that group's rate anyway: one request every 5
seconds. (An earlier survey on 2026-10-28 found that `/robots.txt` returned the web application's HTML page; on the day
of the build it returned the file above.) The site's API (`api.iga.in.gov`) needs a key and was not used, and neither
were the Acts (`/pdf-documents/`, which the group above disallows for those crawlers).

## The build, step by step

1. `python net.py` fetched every title PDF, newest edition first ({i['downloads']} requests).
2. `python build.py parse` read each PDF into sections in a container from Lexifina's backend image (PyMuPDF 1.25.5).
   For every section, every word printed in it is checked to be in what was read, in order; no PDF had a mismatch.
3. `python build.py repo <out>` (Python {i['python']}, git {i['git']}) wrote the history with `git fast-import`: the
   {i['years'][0]} edition, then each later edition's changes in date order, then the documentation commit, dated
   {i['record_to']}.

`build/build.py` has git blob `{i['blob']}`, the same file as `scripts/state-law/in/build.py` in Lexifina's repository.

## Decisions made by hand

1. **Which version of a section an edition shows.** An edition can print a section in several versions, each with a
   note such as "This version of section effective until 7-1-2027" or "effective 7-1-2027". The text shown for an
   edition is every version in force on 1 July of its year by those notes. Where two versions are in force at once (two
   acts amended the section without reconciling them; the code prints both), the file holds both, each with its note.
2. **Dating.** A change is dated by the effective date the code prints for that version where there is one after the
   edition before; otherwise 1 July of the edition's year, the default effective date of IC 1-1-3-3(b). The acts were
   not read, so changes that took effect on passage or on another unprinted day are dated 1 July. The messages say
   which date a commit has.
3. **A version printed as taking effect later** is committed on its date when that is after its edition and on or
   before the next edition's date (or {i['built']} for the last edition). The next edition's text then follows.
4. **Credit.** The acts in a section's source note (`P.L.<n>-<year>`, and older `Acts <year>, P.L.<n>`) are compared
   with the edition before. Exactly one new act: it is the author. None or several: the edition is, and the message
   lists them.
5. **Text.** Rows are joined into paragraphs by their layout (indent, and justified rows ending short); words broken at
   a hyphen at the end of a row are joined without a space. Depth comes from the indent. The footer "Indiana Code
   <year>" is dropped. The bracketed recodification citations ("[Pre-1973 Recodification Citation: ...]") and revisor's
   notes are printed in the code with the section and are kept. Table rows are written one row per line, cells
   separated by " | ". Two texts that differ only in spacing are the same.
6. **Sections no longer printed** (their chapter or article repealed or recodified) become a one-line note in the
   edition where they disappear.

## What AI models did

This repository was built on 28 October 2026 in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus
5.5** (model id `claude-opus-5-5`), from a goal set by the user at Lexifina: to bring all US law into git, in the same
form as the US Code history. The model wrote the scripts in `build/`, `tools/in_.py` and these documents, and ran the
commands above. **No model wrote or edited legal text, and no model is called when the history is built.** Every word
comes from the Indiana General Assembly's PDFs; every date from the code's own notes or the edition year; every act
citation from the sections' source notes. The work has not been reviewed line by line by a lawyer.
"""


CHANGES = """# Changes and updates

Newest first. Lexifina's global-law repository keeps the log for every corpus (`CHANGELOG.md` there).

## 28 October 2026

First build: every title of the Indiana Code from the 2017 edition to the 2026 edition, from the Indiana General
Assembly's yearly title PDFs, one commit per act per effective date where the code names the act and prints the date.
"""

LICENSE = """# License

The text of the Indiana Code in the `title-*` folders is the law of the State of Indiana, as published by the Indiana
General Assembly. The title PDFs it was read from carry no copyright notice, and no statement about copyright in the
code was found on the site. The law itself is not subject to copyright: Georgia v. Public.Resource.Org, Inc., 590 U.S.
255 (2020).

The arrangement of the history (which commits exist, their dates and authors), the commit messages, the tools and the
documentation are © Lexifina, released under the Creative Commons Attribution 4.0 International License (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/
"""


def corpus(i: dict) -> str:
    return json.dumps({
        "corpus": "us/indiana/statutes", "code": "IN", "name": "Indiana Code", "label": "Indiana statutes", "language": "en",
        "history_from": str(i["years"][0]), "record_to": i["record_to"],
        "record_note": f"Every title of the Indiana Code from the {i['years'][0]} edition to the {i['years'][-1]} edition, from the Indiana General Assembly's yearly title PDFs; built {i['built']}.",
        "in_force_trailer": "In-force", "baseline_trailer": "Consolidated", "has_future_branch": False,
        "author": "the act named in the section's source note when exactly one new act appears; otherwise the edition",
        "granularity": "one commit per act per date; the date is the effective date the code prints for a version, otherwise 1 July of the edition year (IC 1-1-3-3(b))",
        "scope": {
            "when_absent": "the code records no case-by-case scope; an act's application provisions are in the act",
            "default_reach": {"rule": "presumption against retroactivity: a statute applies prospectively unless it states that it is retroactive",
                              "authority": "O'Laughlin v. Barton, No. 82S01-9002-CV-131 (Ind. 1991)", "decided_here": False},
        },
        "tool": "tools/in_.py",
    }, indent=2) + "\n"
