"""Polite, cached fetching from iga.in.gov: one request at a time, at least GAP seconds after the previous response
ended, every response kept on disk (gzip) and never fetched twice.

iga.in.gov/robots.txt (checked 2026-10-28) names only Googlebot, Bingbot and Slurp, with "Request-rate: 1/5"; no group
applies to this user agent, but the build keeps to that rate anyway: one request every 5 seconds.

A title that does not exist for a year answers 200 with the site's JavaScript shell (text/html), not 404; that is
recorded as absent (an empty body) so it is not asked for again."""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://iga.in.gov"
AGENT = "Mozilla/5.0 (compatible; Lexifina state law history; +https://lexifina.com/watch)"
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
GAP = [5.0]
_last = [0.0]
READ: dict[str, str] = {}   # URL -> sha256 of the body, for DATA-SHA256SUMS
STATS = {"network": 0, "bytes": 0}


def cache_file(url: str) -> Path:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[1])
    return CACHE / "http" / (name + ".gz")


def get(url: str, offline: bool = False, want: str = "application/pdf") -> bytes:
    """The body from the cache, or from the network unless offline. b"" when the host has no such file."""
    file = cache_file(url)
    if file.exists():
        data = gzip.decompress(file.read_bytes())
        READ[url] = hashlib.sha256(data).hexdigest()
        return data
    if offline:
        raise FileNotFoundError(url)
    file.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(8):
        wait = _last[0] + GAP[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
                kind = (r.headers.get("Content-Type") or "").split(";")[0].strip()
            _last[0] = time.time()
            STATS["network"] += 1
            STATS["bytes"] += len(data)
            if want and kind != want:
                if kind == "text/html" and b"<html" in data[:2000].lower():
                    data = b""   # the site's shell: no such file
                else:
                    raise RuntimeError(f"{url}: unexpected {kind}")
            tmp = file.with_suffix(".part")
            tmp.write_bytes(gzip.compress(data, compresslevel=5))
            os.replace(tmp, file)
            READ[url] = hashlib.sha256(data).hexdigest()
            print(f"{time.strftime('%H:%M:%S')} {len(data):>10} {url}", flush=True)
            return data
        except urllib.error.HTTPError as error:
            _last[0] = time.time()
            STATS["network"] += 1
            last = error
            if error.code in (403, 404, 410):
                if error.code == 403:
                    raise RuntimeError(f"refused (403): {url}; stopping, not working around it") from error
                file.write_bytes(gzip.compress(b""))
                READ[url] = hashlib.sha256(b"").hexdigest()
                return b""
            if error.code == 429 or error.code >= 500:
                wait = float(error.headers.get("Retry-After") or 30 * (attempt + 1))
                _last[0] = time.time() + wait
                GAP[0] = min(GAP[0] * 1.5, 30.0)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            _last[0] = time.time()
            last = error
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


# Titles of the Indiana Code. 17-19 were repealed and folded into title 36; asking for them costs a request each and
# answers the shell, which is recorded as absent.
TITLES = ["1", "2", "3", "4", "5", "6", "7.1"] + [str(n) for n in range(8, 37)]
YEARS = list(range(2017, 2027))


def title_url(year: int, title: str) -> str:
    return f"{HOST}/ic/{year}/Title_{title}.pdf"


def main(argv: list[str]) -> int:
    years = [int(y) for y in argv[1].split(",")] if len(argv) > 1 else YEARS
    titles = argv[2].split(",") if len(argv) > 2 else TITLES
    for year in sorted(years, reverse=True):
        for t in titles:
            try:
                get(title_url(year, t))
            except RuntimeError as error:
                print(f"FAILED {error}", flush=True)
                if "refused" in str(error):
                    return 1
    print(f"done: {STATS['network']} requests, {STATS['bytes']} bytes", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
