"""Looks inside careers pages for clues about which hiring system they use.
Prints short snippets only (no sheet, no email)."""
import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
PAGES = [
    "https://scopiolabs.com/careers/",
    "https://www.cytoreason.com/CytoReason%20Careers.dc.html",
    "https://www.tytocare.com/careers/",
    "https://www.navina.ai/careers",
    "https://www.navina.ai/positions",
    "https://theator.io/careers",
    "https://nucleai.ai/careers",
]
CLUES = re.compile(r"comeet|greenhouse|lever\.co|ashbyhq|workable|breezy|bamboohr|smartrecruiters|"
                   r"getro|token|company[_-]?uid|\.json", re.I)

for url in PAGES:
    print("=" * 70)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        print(f"{url}\n  status {r.status_code}, final url {r.url}, {len(r.text)} chars")
        text = r.text
        seen = set()
        for m in CLUES.finditer(text):
            snippet = re.sub(r"\s+", " ", text[max(0, m.start() - 60): m.end() + 80])
            key = snippet[40:120]
            if key in seen:
                continue
            seen.add(key)
            print("  ..." + snippet + "...")
            if len(seen) >= 8:
                break
        if not seen:
            print("  (no clues found)")
        scripts = [s for s in re.findall(r"<script[^>]+src=[\"']([^\"']+)", text)
                   if not re.search(r"google|gtag|facebook|hotjar|jquery|wp-includes|cookie", s, re.I)]
        for s in scripts[:6]:
            print("  script:", s[:140])
    except Exception as e:
        print(f"{url}\n  error: {e}")
