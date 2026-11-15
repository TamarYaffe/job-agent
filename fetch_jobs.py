"""
Job Search Agent - Stage 2: fetch jobs from public career-page APIs.

Run:  python fetch_jobs.py
Output: prints matching jobs and saves them to jobs.csv
"""
import csv
import html as htmllib
import re
from urllib.parse import urljoin, urlparse

import requests

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

# ---- Sources -------------------------------------------------------------
# Add companies here (see the chat for how to find each company's ID).
# Found with discover_sources.py
GREENHOUSE_BOARDS = ["riskified", "tripactions", "appsflyer", "taboola", "wizinc",
                     "axonius", "yotpo", "similarweb", "transmitsecurity",
                     "catonetworks", "payoneer", "jfrog", "forter", "bigid",
                     "island", "nice", "gongio", "orcasecurity", "via", "apiiro",
                     "duda", "torq", "nanit", "obligo", "alta"]
LEVER_COMPANIES = ["walkme", "cloudinary"]
ASHBY_BOARDS = ["honeybook", "moonactive", "unit", "melio-payments"]
SMARTRECRUITERS_COMPANIES = ["armis", "abbvie", "servicenow"]
WORKDAY_SITES = [        # (company name, careers site URL)
    ("NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"),
    ("Intel", "https://intel.wd1.myworkdayjobs.com/External"),
    ("Salesforce", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"),
    ("Applied Materials", "https://amat.wd1.myworkdayjobs.com/External"),
    ("Mastercard", "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers"),
    ("Medtronic", "https://medtronic.wd1.myworkdayjobs.com/MedtronicCareers"),
    ("Motorola Solutions", "https://motorolasolutions.wd5.myworkdayjobs.com/Careers"),
    ("HP", "https://hp.wd5.myworkdayjobs.com/ExternalCareerSite"),
    ("Marvell", "https://marvell.wd1.myworkdayjobs.com/MarvellCareers"),
    ("KLA", "https://kla.wd1.myworkdayjobs.com/Search"),
    ("Abbott", "https://abbott.wd5.myworkdayjobs.com/abbottcareers"),
    ("Thermo Fisher", "https://thermofisher.wd5.myworkdayjobs.com/ThermoFisherCareers"),
    ("PayPal", "https://paypal.wd1.myworkdayjobs.com/jobs"),
    # Candidates after PayPal in the discovery list. If one of them isn't valid,
    # the run just prints an [error] line for it and continues.
    ("Moody's", "https://moodys.wd5.myworkdayjobs.com/External"),
    ("Cadence", "https://cadence.wd1.myworkdayjobs.com/External_Careers"),
    ("Synopsys", "https://synopsys.wd1.myworkdayjobs.com/Careers"),
    ("Samsung", "https://sec.wd3.myworkdayjobs.com/Samsung_Careers"),
    ("Western Digital", "https://wdc.wd1.myworkdayjobs.com/WD_External_Career_Site"),
    ("Cisco", "https://cisco.wd5.myworkdayjobs.com/Cisco_Careers"),
    ("Booking.com", "https://bookinggroup.wd5.myworkdayjobs.com/BookingGroup"),
    ("Red Hat", "https://redhat.wd5.myworkdayjobs.com/Jobs"),
    ("Zoom", "https://zoom.wd5.myworkdayjobs.com/Zoom"),
    ("Autodesk", "https://autodesk.wd1.myworkdayjobs.com/Ext"),
    ("Akamai", "https://akamai.wd1.myworkdayjobs.com/akamaicareers"),
]
INCLUDE_AMAZON = True

# ---- Favorite biotech / medtech companies --------------------------------
# Jobs from these companies get a ⭐ in the sheet and their own section in the email.
FAVORITE_COMPANIES = ["Aidoc", "Immunai", "Scopio Labs", "Eleos Health", "TytoCare",
                      "CytoReason", "Nucleai", "Navina", "Theator", "K Health"]

# Known job boards of the favorites
GREENHOUSE_BOARDS += ["aidocmedical", "eleoshealth", "khealthcareers"]
# Companies on Comeet: (name, careers page). The script reads the page to find
# the Comeet API details automatically.
COMEET_PAGES = [
    ("Immunai", "https://www.comeet.com/jobs/immunai/37.009"),
    ("CytoReason", "https://www.comeet.com/jobs/cytoreason/16.002"),
    ("Navina", "https://www.navina.ai/careers"),
    ("Scopio Labs", "https://scopiolabs.com/careers/"),
]
# Not connected yet (their careers pages load jobs only inside a browser):
# Nucleai, TytoCare, Theator - follow them with LinkedIn job alerts instead.
# Companies with their own careers page: (name, page, link pattern, default location)
HTML_PAGES = []
# WordPress sites: job pages are read from the site's sitemap.
# (name, site, path that job pages start with, default location)
WP_SITEMAP_SITES = []
# Favorites whose job board we haven't confirmed yet: (name, IDs to try).
# Each run tries Greenhouse / Lever / Ashby with these IDs and uses the first that works.
AUTO_DETECT = []

# Friendly names for IDs that don't look like the company name
COMPANY_NAMES = {"tripactions": "Navan", "wizinc": "Wiz", "catonetworks": "Cato Networks",
                 "transmitsecurity": "Transmit Security", "appsflyer": "AppsFlyer",
                 "jfrog": "JFrog", "bigid": "BigID", "walkme": "WalkMe",
                 "nice": "NICE", "similarweb": "Similarweb", "gongio": "Gong",
                 "orcasecurity": "Orca Security", "honeybook": "HoneyBook",
                 "moonactive": "Moon Active", "melio-payments": "Melio",
                 "abbvie": "AbbVie", "servicenow": "ServiceNow",
                 "aidocmedical": "Aidoc", "eleoshealth": "Eleos Health",
                 "khealthcareers": "K Health"}

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
    # Greenhouse has a US and an EU server; try the US one first.
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                     params={"content": "true"}, timeout=30)
    if r.status_code == 404:
        r = requests.get(f"https://boards-api.eu.greenhouse.io/v1/boards/{board}/jobs",
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


def fetch_ashby(board):
    """Ashby public job board API (used by many startups)."""
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}", timeout=30)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        places = [j.get("location") or ""] + [
            (s.get("location") or "") for s in (j.get("secondaryLocations") or [])]
        jobs.append({
            "company": COMPANY_NAMES.get(board, board.capitalize()),
            "title": j.get("title", ""),
            "location": ", ".join(p for p in places if p),
            "url": j.get("jobUrl", ""),
            "description": j.get("descriptionPlain", ""),
        })
    return jobs


def fetch_smartrecruiters(company, max_jobs=500):
    """SmartRecruiters public postings API, Israel only."""
    jobs, offset = [], 0
    while offset < max_jobs:
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
                         params={"country": "il", "limit": 100, "offset": offset}, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("content", [])
        for j in batch:
            loc = j.get("location") or {}
            jobs.append({
                "company": COMPANY_NAMES.get(company, (j.get("company") or {}).get("name", company)),
                "title": j.get("name", ""),
                "location": f"Israel, {loc.get('city', '')}",
                "url": f"https://jobs.smartrecruiters.com/{company}/{j.get('id', '')}",
                "description": "",
            })
        offset += 100
        if offset >= data.get("totalFound", 0) or not batch:
            break
    return jobs


def _clean(text):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def fetch_comeet(company, page_url):
    """Comeet careers. Finds the company ID + public token in the careers page,
    then calls Comeet's careers API. Falls back to reading job links from the page."""
    page = requests.get(page_url, headers=BROWSER_HEADERS, timeout=30)
    page.raise_for_status()
    text = page.text

    uid_match = (re.search(r"comeet\.com/jobs/[^/\"']+/([0-9A-F]{2}\.[0-9A-F]{3})", page_url + " " + text)
                 or re.search(r"company[-_]?uid[\"']?\s*[:=]\s*[\"']([0-9A-F]{2}\.[0-9A-F]{3})", text, re.I)
                 or re.search(r"/company/([0-9A-F]{2}\.[0-9A-F]{3})/", text))
    token_match = (re.search(r"[\"']?token[\"']?\s*[:=]\s*[\"']([A-Za-z0-9]{10,})[\"']", text)
                   or re.search(r"data-token=[\"']([A-Za-z0-9]{10,})[\"']", text))

    if uid_match and token_match:
        r = requests.get(f"https://www.comeet.co/careers-api/2.0/company/{uid_match.group(1)}/positions",
                         params={"token": token_match.group(1), "details": "true"}, timeout=30)
        r.raise_for_status()
        jobs, seen = [], set()
        for p in r.json():
            loc = dict(p.get("location") or {})
            if (loc.get("country") or "").upper() in ("IL", "ISR"):
                loc["country"] = "Israel"
            details = " ".join(_clean(d.get("value", "")) for d in (p.get("details") or []))
            # Each job needs its own link (the sheet uses it to avoid duplicates)
            url = p.get("url_comeet_hosted_page") or p.get("url_active_page") or ""
            if not url or url in seen or url.rstrip("/") == page_url.rstrip("/"):
                url = f"{page_url}#{p.get('uid') or p.get('name', '')}"
            seen.add(url)
            jobs.append({
                "company": company,
                "title": p.get("name", ""),
                "location": ", ".join(x for x in (loc.get("country"), loc.get("city") or loc.get("name")) if x),
                "url": url,
                "description": details,
            })
        return jobs

    if re.search(r"don.t have any open positions|no open positions", text, re.I):
        return []   # the page works, the company just isn't hiring right now

    # Fallback: job links on the page look like .../<2 hex>.<3 hex>/<job-title-slug>
    jobs, seen = [], set()
    for href in re.findall(r"href=[\"']([^\"'#]+)[\"']", text):
        m = re.search(r"/([0-9A-F]{2}\.[0-9A-F]{3})/([a-z0-9][a-z0-9-]+)", href)
        if not m:
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        jobs.append({"company": company,
                     "title": m.group(2).replace("-", " ").title(),
                     "location": "Locations unknown",   # the AI step reads the real location
                     "url": url, "description": ""})
    if not jobs:
        raise RuntimeError("no jobs found on the careers page (it may load them with JavaScript)")
    return jobs


def fetch_html_links(company, page_url, link_pattern, default_location):
    """A company's own careers page: collect links that match link_pattern."""
    page = requests.get(page_url, headers=BROWSER_HEADERS, timeout=30)
    page.raise_for_status()
    jobs, seen = [], set()
    for href, inner in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", page.text, re.S):
        url = urljoin(page_url, href)
        if not re.search(link_pattern, url) or url.rstrip("/") == page_url.rstrip("/") or url in seen:
            continue
        seen.add(url)
        title = _clean(inner) or url.rstrip("/").split("/")[-1].replace("-", " ").title()
        jobs.append({"company": company, "title": title, "location": default_location,
                     "url": url, "description": ""})
    if not jobs:
        raise RuntimeError("no job links found on the careers page")
    return jobs


def fetch_wp_sitemap(company, site, path_prefix, default_location):
    """WordPress careers: list job pages from the site's sitemap (or REST API)."""
    def get(url):
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
        return r if r.status_code == 200 else None

    base = site.rstrip("/") + path_prefix
    # 1) WordPress REST API, if the job post type is public
    r = get(f"{site}/wp-json/wp/v2/{path_prefix.strip('/')}?per_page=100")
    if r is not None:
        try:
            posts = r.json()
        except ValueError:
            posts = None
        if isinstance(posts, list) and posts:
            return [{"company": company, "title": _clean((p.get("title") or {}).get("rendered", "")),
                     "location": default_location, "url": p.get("link", ""), "description": ""}
                    for p in posts]
    # 2) Sitemaps
    urls = set()
    for index in ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml"):
        r = get(site + index)
        if r is None:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        sub = [l for l in locs if l.endswith(".xml") and re.search(r"career|job|position", l, re.I)]
        for sm in sub or [l for l in locs if l.endswith(".xml")][:15]:
            s = get(sm)
            if s is not None:
                urls.update(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", s.text))
        urls.update(l for l in locs if not l.endswith(".xml"))
        if urls:
            break
    job_urls = sorted(u for u in urls if u.startswith(base) and u.rstrip("/") != base.rstrip("/"))
    if not job_urls:
        raise RuntimeError("no job pages found in the sitemap")
    return [{"company": company,
             "title": u.rstrip("/").split("/")[-1].replace("-", " ").title(),
             "location": default_location, "url": u, "description": ""} for u in job_urls]


def fetch_auto(company, slugs):
    """Try Greenhouse / Lever / Ashby with each ID; return the first board that works."""
    for slug in slugs:
        for fetch in (fetch_greenhouse, fetch_lever, fetch_ashby):
            try:
                jobs = fetch(slug)
            except Exception:
                continue
            if jobs:
                for j in jobs:
                    j["company"] = company
                print(f"        (found {company} on {fetch.__name__.replace('fetch_', '')} as '{slug}')")
                return jobs
    raise RuntimeError("no public job board found yet")


def is_favorite(job):
    name = job["company"].lower()
    return any(f.lower() == name for f in FAVORITE_COMPANIES)


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
    sources += [(f"ashby:{b}", lambda b=b: fetch_ashby(b)) for b in ASHBY_BOARDS]
    sources += [(f"smartrecruiters:{c}", lambda c=c: fetch_smartrecruiters(c))
                for c in SMARTRECRUITERS_COMPANIES]
    sources += [(f"comeet:{n}", lambda n=n, u=u: fetch_comeet(n, u)) for n, u in COMEET_PAGES]
    sources += [(f"careers-page:{n}", lambda n=n, u=u, p=p, l=l: fetch_html_links(n, u, p, l))
                for n, u, p, l in HTML_PAGES]
    sources += [(f"wordpress:{n}", lambda n=n, s=s, p=p, l=l: fetch_wp_sitemap(n, s, p, l))
                for n, s, p, l in WP_SITEMAP_SITES]
    sources += [(f"auto:{n}", lambda n=n, s=s: fetch_auto(n, s)) for n, s in AUTO_DETECT]

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
    for j in relevant:
        j["favorite"] = "⭐" if is_favorite(j) else ""
    favorites = sum(1 for j in relevant if j["favorite"])
    print(f"\nTotal: {len(jobs)} | Relevant: {len(relevant)} | From favorite companies: {favorites}\n")
    for j in relevant:
        print(f"- {j['favorite']}{j['company']} | {j['title']} | {j['location']}\n  {j['url']}")

    with open("jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "title", "location", "url", "description",
                                               "favorite"])
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
