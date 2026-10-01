# Git for the Indiana Code

The Indiana Code, section by section, as a git history: the 2017 edition as the starting point, then a commit
for each change in each later edition, to 2026-10-01. **Each commit is a change taking effect.** Its author is the
act that made it, where the section's source note names one new act, and its date is the day the change took effect
where the code prints that day; otherwise the edition's date, and the commit message says so.

| The question | The command |
| --- | --- |
| What did IC 35-42-1-1 say on 1 August 2021? | `python tools/in_.py on 2021-08-01 title-35/35-42-1/35-42-1-1.md` |
| Which act wrote each line? | `git blame title-35/35-42-1/35-42-1-1.md` |
| What changed between two dates? | `python tools/in_.py diff 2018-01-01 2026-07-01 title-35/35-42-1/35-42-1-1.md --words` |
| Everything one act changed | `python tools/in_.py act P.L.174-2019` |
| Every change to a section, with its dates | `python tools/in_.py log title-35/35-42-1/35-42-1-1.md` |
| The most amended sections of a title | `git log --format= --name-only -- title-6 \| sort \| uniq -c \| sort -rn \| head` |

`tools/in_.py` needs only Python 3 and git. It picks the text by each commit's `In-force:` date, so the answer does not
depend on your time zone or the time of day.

## What is here

33 titles, 7832 chapters and 88915 section files. There are 2146 commits: the
2017 edition (69275 sections) and Title 31 from the 2018 edition (the 2017 PDF of Title 31
holds only its table of contents), 2068 credited to one act, 75 credited to an
edition (the source notes of their sections name no new act, or more than one), and this documentation. Of the change
commits, 294 are dated by an effective date the code prints, and 1849 by the edition.

Each section is one Markdown file, `title-<t>/<t>-<article>-<chapter>/<section>.md`. The first line is the citation
and heading; then one paragraph or designated provision per line (`- (a)`, `  - (1)`, `    - (A)`), so `git blame`
names a change for every provision; then the section's source note ("As added by P.L.5-1988, SEC.1. Amended by ...").
A repealed section keeps the code's one-line entry ("Repealed" with its source note). A section that stops being
printed at all (because its whole chapter or article was repealed or moved) becomes a one-line note saying so, with the
chapter's or article's repeal line where the code prints one.

## How a change is dated and credited

The text comes from the Indiana General Assembly's yearly PDF of each title, 2017 to 2026.

- **Dated by a printed date.** Where a section is printed in more than one version, the code says when each takes
  effect ("Note: This version of section effective 1-1-2026."). A change to such a version is dated that day, and a
  version printed as taking effect after an edition is committed on its own date, up to 2026-10-28.
- **Dated by the edition.** Otherwise the change is dated 1 July of the edition's year. Each edition prints the acts of
  that year's session, and a SECTION of an act takes effect on 1 July after its enactment unless it says otherwise
  (IC 1-1-3-3(b)). Acts that take effect on passage or on another day are not told apart from those here; the acts
  themselves were not read. The commit message says which kind of date it has.
- **Credited to an act** when the section's source note gained exactly one act since the edition before. The act is
  the author ("P.L.174-2019 (Acts of Indiana 2019)") and is in the `Law:` trailer. Otherwise the change is credited to
  the edition, and the message lists the acts each section's note gained.

Commits are dated at noon UTC.

## What it does not show

- **Before 2017.** The history starts from the 2017 edition; the earlier yearly PDFs are not published.
- **More than one change in a year.** Between two editions only the later text is available, so two acts amending one
  section in one session are one commit credited to the edition, unless the code printed them as separate versions.
- **The exact day of most changes.** See above: most are dated 1 July, the statutory default, not the act's own date.
- **Future changes** taking effect after 2026-10-28: they are printed in the 2026 edition but not on `main`.
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
