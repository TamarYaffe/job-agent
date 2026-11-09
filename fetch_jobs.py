"""
Job Search Agent - Stage 2: fetch jobs from public career-page APIs.

Run:  python fetch_jobs.py
Output: prints matching jobs and saves them to jobs.csv
"""
import csv
from urllib.parse import urlparse

import requests

# ---- Sources -------------------------------------------------------------
# Add companies here (see the chat for how to find each company's ID).
# Found with discover_sources.py
GREENHOUSE_BOARDS = ["riskified", "tripactions", "appsflyer", "taboola", "wizinc",
                     "axonius", "yotpo", "similarweb", "transmitsecurity",
                     "catonetworks", "payoneer", "jfrog", "forter", "bigid",
                     "island", "nice"]
LEVER_COMPANIES = ["walkme", "cloudinary"]
WORKDAY_SITES = [        # (company name, careers site URL)
    ("NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"),
    ("Intel", "https://intel.wd1.myworkdayjobs.com/External"),
    ("Salesforce", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"),
    ("Applied Materials", "https://amat.wd1.myworkdayjobs.com/External"),
    ("Mastercard", "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers"),
]
INCLUDE_AMAZON = True

# Friendly names for IDs that don't look like the company name
COMPANY_NAMES = {"tripactions": "Navan", "wizinc": "Wiz", "catonetworks": "Cato Networks",
                 "transmitsecurity": "Transmit Security", "appsflyer": "AppsFlyer",
                 "jfrog": "JFrog", "bigid": "BigID", "walkme": "WalkMe",
                 "nice": "NICE", "similarweb": "Similarweb"}

# ---- Filters -------------------------------------------------------------
TITLE_KEYWORDS = ["analyst", "analytics", "data", "bi ", "business",
                  "operations", "ops", "project", "program", "product",
                  "planning", "configuration", "supply", "procurement",
                  "implementation", "onboarding", "process", "coordinator"]
# Junior-only: titles with these words are skipped before the AI step (saves quota)
SENIOR_WORDS = ["senior", "sr.", "sr ", "staff", "principal", "director",
                "head of", "vp", "vice president", "lead", "manager, ", "architect"]
# Wrong field: matched a keyword ("product", "data"...) but never fits the profile
EXCLUDE_WORDS = ["designer", "devops", "developer", "software engineer",
                 "data engineer", "ml engineer", "mlops", "ml ops", "firmware",
                 "counsel", "platform engineer", "security engineer", "pentest"]
LOCATIONS = ["israel", "tel aviv", "tel-aviv","ramat gan", "givatayim", "herzliya",
             "petah tikva", "petach tikva", "ra'anana", "raanana", "kfar saba",
             "hod hasharon", "rosh haayin", "rosh ha'ayin", "airport city",
             "or yehuda", "holon", "bat yam", "rishon", "rehovot", "netanya",
             "bnei brak", "modiin", "yokneam"]


def fetch_workday(company, site_url, search="Israel", max_jobs=1000):
    """Any company on Workday (NVIDIA, Intel...). This is the JSON endpoint
    their careers sites call (unofficial - may need updating if it changes)."""
    host = urlparse(site_url).netloc                  # nvidia.wd5.myworkdayjobs.com
    tenant = host.split(".")[0]                       # nvidia
    site = urlparse(site_url).path.strip("/").split("/")[-1]   # NVIDIAExternalCareerSite
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    base = f"https://{host}/{site}"
    jobs, offset = [], 0
    while offset < max_jobs:
        r = requests.post(url, json={"appliedFacets": {}, "limit": 20,
                                     "offset": offset, "searchText": search},
                          timeout=30)
        r.raise_for_status()
        data = r.json()
        if offset == 0 and data.get("total"):
            max_jobs = min(max_jobs, data["total"])  # stop at the real total
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for p in postings:
            jobs.append({
                "company": company,
                "title": p.get("title", ""),
                "location": p.get("locationsText", ""),
                "url": base + p.get("externalPath", ""),
                "description": "",
            })
        offset += 20
    return jobs


def fetch_greenhouse(board):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                     params={"content": "true"}, timeout=30)
    r.raise_for_status()
    return [{
        "company": COMPANY_NAMES.get(board, board.capitalize()),
        "title": j.get("title", ""),
        "location": (j.get("location") or {}).get("name", ""),
        "url": j.get("absolute_url", ""),
        "description": j.get("content", ""),
    } for j in r.json().get("jobs", [])]


def fetch_lever(company):
    r = requests.get(f"https://api.lever.co/v0/postings/{company}",
                     params={"mode": "json"}, timeout=30)
    r.raise_for_status()
    return [{
        "company": COMPANY_NAMES.get(company, company.capitalize()),
        "title": j.get("text", ""),
        "location": (j.get("categories") or {}).get("location", ""),
        "url": j.get("hostedUrl", ""),
        "description": j.get("descriptionPlain", ""),
    } for j in r.json()]


def fetch_amazon(max_jobs=500):
    """amazon.jobs has a public JSON search (unofficial)."""
    jobs, offset = [], 0
    while offset < max_jobs:
        r = requests.get("https://www.amazon.jobs/en/search.json",
                         params={"loc_query": "Israel", "result_limit": 100,
                                 "offset": offset}, timeout=30)
        r.raise_for_status()
        batch = r.json().get("jobs", [])
        if not batch:
            break
        for j in batch:
            if j.get("country_code") not in ("ISR", "IL"):
                continue
            jobs.append({
                "company": "Amazon",
                "title": j.get("title", ""),
                "location": f"Israel, {j.get('city', '')}",
                "url": "https://www.amazon.jobs" + j.get("job_path", ""),
                "description": j.get("description", ""),
            })
        offset += 100
    return jobs


def is_relevant(job):
    title = job["title"].lower() + " "
    location = job["location"].lower()
    # Jobs with several sites show "2 Locations" instead of a city name,
    # so we keep them and let the AI scoring stage check them later.
    multi_location = "locations" in location
    in_israel = multi_location or any(loc in location for loc in LOCATIONS)
    title_match = any(k in title for k in TITLE_KEYWORDS)
    too_senior = any(w in title for w in SENIOR_WORDS)
    wrong_field = any(w in title for w in EXCLUDE_WORDS)
    return in_israel and title_match and not too_senior and not wrong_field


def collect_all():
    sources = [(f"workday:{name}", lambda n=name, u=url: fetch_workday(n, u))
               for name, url in WORKDAY_SITES]
    if INCLUDE_AMAZON:
        sources.append(("amazon", fetch_amazon))
    sources += [(f"greenhouse:{b}", lambda b=b: fetch_greenhouse(b)) for b in GREENHOUSE_BOARDS]
    sources += [(f"lever:{c}", lambda c=c: fetch_lever(c)) for c in LEVER_COMPANIES]

    all_jobs = []
    for name, fetch in sources:
        try:
            jobs = fetch()
            print(f"[ok]    {name}: {len(jobs)} jobs")
            all_jobs += jobs
        except Exception as e:  # one broken source shouldn't stop the rest
            print(f"[error] {name}: {e}")
    return all_jobs


if __name__ == "__main__":
    jobs = collect_all()
    relevant = [j for j in jobs if is_relevant(j)]
    print(f"\nTotal: {len(jobs)} | Relevant: {len(relevant)}\n")
    for j in relevant:
        print(f"- {j['company']} | {j['title']} | {j['location']}\n  {j['url']}")

    with open("jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "title", "location", "url", "description"])
        writer.writeheader()
        writer.writerows(relevant)
    print("\nSaved to jobs.csv")

    from sheets import save_new_jobs
    new_jobs = save_new_jobs(relevant)
    print(f"Google Sheets: {len(new_jobs)} new jobs added "
          f"({len(relevant) - len(new_jobs)} were already there)")

    from scorer import score_pending
    score_pending()

    # Stage 5: email digest of this run's new jobs (or "nothing new")
    from sheets import get_jobs_by_urls
    from notifier import send_digest
    send_digest(get_jobs_by_urls({j["url"] for j in new_jobs}))
