"""Quick check: which favorite-company sources work? (no sheet, no email)
Run:  python3 check_favorites.py > check_output.txt 2>&1"""
import re

import requests

import fetch_jobs as f

checks = [(f"comeet:{n}", lambda n=n, u=u: f.fetch_comeet(n, u)) for n, u in f.COMEET_PAGES]
checks += [(f"wordpress:{n}", lambda n=n, s=s, p=p, l=l: f.fetch_wp_sitemap(n, s, p, l))
           for n, s, p, l in f.WP_SITEMAP_SITES]
checks += [(f"auto:{n}", lambda n=n, s=s: f.fetch_auto(n, s)) for n, s in f.AUTO_DETECT]
checks += [(f"greenhouse:{b}", lambda b=b: f.fetch_greenhouse(b))
           for b in ("aidocmedical", "eleoshealth", "khealthcareers")]

for name, fetch in checks:
    try:
        jobs = fetch()
        relevant = [j for j in jobs if f.is_relevant(j)]
        print(f"[ok]    {name}: {len(jobs)} jobs, {len(relevant)} relevant")
        for j in jobs[:4]:
            print(f"          e.g. {j['title']} | {j['location']} | {j['url'][:90]}")
    except Exception as e:
        print(f"[error] {name}: {str(e)[:200]}")

# Theator's site is a JavaScript app: look inside its script for the hiring system
print("\n--- Theator clues ---")
try:
    page = requests.get("https://theator.io/careers", headers=f.BROWSER_HEADERS, timeout=30).text
    for src in re.findall(r"<script[^>]+src=[\"']([^\"']+)", page):
        js = requests.get(requests.compat.urljoin("https://theator.io/careers", src),
                          headers=f.BROWSER_HEADERS, timeout=30).text
        hits = set(m.group(0) for m in re.finditer(
            r"[^\"'\s]{0,60}(comeet|greenhouse|lever\.co|ashbyhq|workable|breezy|bamboohr|"
            r"smartrecruiters|hibob|getro)[^\"'\s]{0,80}", js, re.I))
        for h in list(hits)[:10]:
            print("  ", h)
        tok = re.findall(r"(?:token|company[-_]?uid)[\"']?\s*[:=]\s*[\"']([^\"']{4,60})", js, re.I)
        if tok:
            print("   token/uid:", tok[:4])
except Exception as e:
    print("  error:", e)
