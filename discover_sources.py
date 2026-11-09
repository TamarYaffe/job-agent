"""
Job Search Agent - source discovery.

Tries every candidate company on Greenhouse, Lever and Workday, counts its
open jobs in Israel, and prints the lists to paste into fetch_jobs.py.

Run:  python3 discover_sources.py      (takes a few minutes)
"""
from fetch_jobs import (LOCATIONS, fetch_amazon, fetch_greenhouse,
                        fetch_lever, fetch_workday)

# Guessed IDs - many will fail, that's expected. The script finds the ones that work.
CANDIDATES = {
    "tech": [
        "riskified", "melio", "navan", "tripactions", "appsflyer", "taboola",
        "tipalti", "lemonade", "papayaglobal", "hibob", "pagaya", "armis",
        "snyk", "wiz", "wizinc", "axonius", "atbay", "honeybook", "yotpo",
        "lightricks", "similarweb", "nayax", "rapyd", "transmitsecurity",
        "walkme", "gong", "fireblocks", "catonetworks", "monday", "fiverr",
        "wix", "payoneer", "jfrog", "sentinelone", "cyberark", "outbrain",
        "forter", "cloudinary", "bigid", "island", "cyera", "orca",
        "playtika", "nice", "amdocs", "mobileye", "unity", "redis",
    ],
    "biotech & health": [
        "immunai", "nucleai", "cytoreason", "quris", "evogene", "compugen",
        "aidoc", "tytocare", "zebramedicalvision", "biolinerx", "pluri",
        "enlivex", "medtronic", "philips",
    ],
}

WORKDAY_CANDIDATES = [
    ("Intel", "https://intel.wd1.myworkdayjobs.com/External"),
    ("Salesforce", "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"),
    ("Applied Materials", "https://amat.wd1.myworkdayjobs.com/External"),
    ("Dell", "https://dell.wd1.myworkdayjobs.com/External"),
    ("Mastercard", "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers"),
    ("Teva", "https://teva.wd3.myworkdayjobs.com/TevaCareers"),
]


def israel_count(jobs):
    return sum(any(loc in j["location"].lower() for loc in LOCATIONS) for j in jobs)


def try_source(fetch):
    try:
        return fetch()
    except Exception:
        return None


if __name__ == "__main__":
    found_gh, found_lever, found_wd = [], [], []

    for group, slugs in CANDIDATES.items():
        print(f"\n== {group} ==")
        for slug in slugs:
            for kind, fetch, found in (("greenhouse", fetch_greenhouse, found_gh),
                                       ("lever", fetch_lever, found_lever)):
                jobs = try_source(lambda: fetch(slug))
                if jobs:
                    n = israel_count(jobs)
                    print(f"  {slug:<22} {kind:<11} {len(jobs):>4} jobs, {n:>3} in Israel")
                    if n:
                        found.append(slug)

    print("\n== workday ==")
    for name, url in WORKDAY_CANDIDATES:
        jobs = try_source(lambda: fetch_workday(name, url, max_jobs=100))
        if jobs:
            print(f"  {name:<22} workday     {len(jobs):>4}+ jobs matching 'Israel'")
            found_wd.append((name, url))
        else:
            print(f"  {name:<22} workday     not found")

    print("\n== amazon ==")
    amazon = try_source(lambda: fetch_amazon(max_jobs=200))
    print(f"  Amazon: {len(amazon)} jobs in Israel" if amazon else "  Amazon: not reachable")

    print("\n\n######## Paste into fetch_jobs.py ########")
    print(f"GREENHOUSE_BOARDS = {found_gh}")
    print(f"LEVER_COMPANIES = {found_lever}")
    print("WORKDAY_SITES = [")
    print('    ("NVIDIA", "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"),')
    for name, url in found_wd:
        print(f'    ("{name}", "{url}"),')
    print("]")
    print(f"INCLUDE_AMAZON = {bool(amazon)}")
