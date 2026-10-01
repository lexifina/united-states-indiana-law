# How this history was made, and how to make it again

## Short version

```sh
cd build
python net.py                         # every title PDF of every edition (cached; one request every 5 seconds)
sha256sum -c DATA-SHA256SUMS          # (after decompressing the cache) the PDFs are the ones this history was built from
python build.py parse                 # needs PyMuPDF (pip install pymupdf==1.25.5)
python build.py repo ../../rebuilt
git -C ../../rebuilt log --format=%H  # the same commits, with the same hashes
```

The last change commit is `80c729bf1f8e1e6a7f890891e73bfb01e8b01734`.

## Sources

| What | Where | Requests | Retrieved |
| --- | --- | ---: | --- |
| robots.txt | `https://iga.in.gov/robots.txt` | 1 | 2026-10-28 |
| Each title of each yearly edition, 2017-2026 | `https://iga.in.gov/ic/<year>/Title_<n>.pdf` for titles 1-6, 7.1, 8-36 | 360 | 2026-10-28 |

329 of the PDFs hold sections; titles 17, 18 and 19 are one-page notes that the titles were repealed.
The cache is 3,362 MB (gzip). Every response is listed with its sha256 in `build/DATA-SHA256SUMS` (sha256 of that
list: `3dd76141ddc3f4d5697d53842ae3a72b474c40b2e1cedc69b58d5c9f911c2af7`). Requests were made one at a time, 5 seconds apart, with the user agent
`Mozilla/5.0 (compatible; Lexifina state law history; +https://lexifina.com/watch)`. The host served every PDF to that
user agent (`200`/`206 application/pdf`); none was refused, and no other user agent was used. A file the host does not
have answers with its web application's HTML page; the fetcher records that as absent.

**robots.txt, checked 28 October 2026** (`https://iga.in.gov/robots.txt`, `text/plain`, 144 bytes):

```
User-agent: Googlebot
User-agent: Bingbot
User-agent: Slurp
Disallow: /search/
Disallow: /pdf-documents/
Request-rate: 1/5
Visit-time: 0300-1200
```

The only group names Googlebot, Bingbot and Slurp; there is no `*` group and nothing for ClaudeBot, anthropic-ai or
Claude-Web, and `/ic/` is not disallowed for anyone. This build kept to that group's rate anyway: one request every 5
seconds. (An earlier survey on 2026-10-28 found that `/robots.txt` returned the web application's HTML page; on the day
of the build it returned the file above.) The site's API (`api.iga.in.gov`) needs a key and was not used, and neither
were the Acts (`/pdf-documents/`, which the group above disallows for those crawlers).

## The build, step by step

1. `python net.py` fetched every title PDF, newest edition first (360 requests).
2. `python build.py parse` read each PDF into sections in a container from Lexifina's backend image (PyMuPDF 1.25.5).
   For every section, every word printed in it is checked to be in what was read, in order; no PDF had a mismatch.
3. `python build.py repo <out>` (Python 3.12.10, git 2.46.0.windows.1) wrote the history with `git fast-import`: the
   2017 edition, then each later edition's changes in date order, then the documentation commit, dated
   2026-10-01.

`build/build.py` has git blob `7e8efa4dfc42f4be900cd4d95de093914c347cdd`, the same file as `scripts/state-law/in/build.py` in Lexifina's repository.

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
   before the next edition's date (or 2026-10-28 for the last edition). The next edition's text then follows.
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
