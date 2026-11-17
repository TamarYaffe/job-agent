"""
Job Search Agent - source discovery (round 3).

Tries new candidate companies on every job board the agent knows, counts how many
open jobs each has in Israel and how many pass the agent's filter, and prints the
ones worth adding. Read-only: no sheet, no email, no AI.

Runs on GitHub (Actions tab -> "Discover sources" -> Run workflow), or locally:
    python3 discover_round3.py
"""
from concurrent.futures import ThreadPoolExecutor

from fetch_jobs import (ASHBY_BOARDS, COMEET_PAGES, GREENHOUSE_BOARDS, LEVER_COMPANIES,
                        LOCATIONS, SMARTRECRUITERS_COMPANIES, WORKDAY_SITES, fetch_ashby,
                        fetch_comeet, fetch_greenhouse, fetch_lever, fetch_smartrecruiters,
                        fetch_workday, is_relevant)

SLUGS = [
    # Israeli tech
    "redis", "redislabs", "outbrain", "claroty", "openweb", "zeronetworks", "riversidefm",
    "globale", "global-e", "cybereason", "imperva", "perion", "fundbox", "nextinsurance",
    "hippo", "lightrun", "connecteam", "cymulate", "pentera", "akeyless", "zencity",
    "augury", "taranis", "innoviz", "cellebrite", "kaltura", "freightos", "artlist", "gloat",
    "vcita", "bigpanda", "tufin", "sapiens", "jit", "oxsecurity", "seemplicity", "sentra",
    "teads", "nexxen", "optibus", "riseup", "tipaltisolutions", "sunbit", "skai", "trax",
    "traxretail", "ironsource", "checkmarx", "mixtiles", "sygnia", "firebolt",
    "dreamsecurity", "noma", "nomasecurity", "legitsecurity", "zafran", "wixcom", "wix2",
    "fiverrcareers", "lemonadeinc", "playtikacareers", "commit", "xtend", "addressable",
    "buildots", "elementor", "pagayatech", "earnix", "sapiens", "cloudinary", "personetics",
    "mobileye", "remitly", "rapid7", "snap", "nebius", "datadog", "mongodb", "wiz",
    "atera", "spotinst", "kenshoo", "transmit", "gong", "pecan", "anyvision", "oosto",
    "lili", "papaya-global", "hibob1", "bobhr", "playtech", "888", "evolution",
    # Biotech, medtech, health
    "theator", "sightdiagnostics", "sight", "insightec", "memic", "nyxoah", "beyondair",
    "neteera", "medinol", "zebramedical", "biobeat", "rhythmed", "inspira", "eyeyon",
    "biosensewebster", "carbonhealth", "tytocare1", "nucleaiinc", "quris-ai", "valid",
    "emedgene", "tabula-rasa", "itamar", "cardiosert", "hellohealth", "clalit", "maccabi",
]

WORKDAY = [
    ("CrowdStrike", "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers"),
    ("Palo Alto Networks", "https://paloaltonetworks.wd5.myworkdayjobs.com/Careers"),
    ("Palo Alto Networks", "https://paloaltonetworks.wd1.myworkdayjobs.com/Careers"),
    ("Intuit", "https://intuit.wd1.myworkdayjobs.com/Intuit"),
    ("Johnson & Johnson", "https://jj.wd5.myworkdayjobs.com/JJ"),
    ("Novartis", "https://novartis.wd3.myworkdayjobs.com/Novartis_Careers"),
    ("Stryker", "https://stryker.wd1.myworkdayjobs.com/StrykerCareers"),
    ("GE HealthCare", "https://gehc.wd5.myworkdayjobs.com/GEHC_ExternalSite"),
    ("BD", "https://bdx.wd1.myworkdayjobs.com/EXTERNAL_CAREER_SITE"),
    ("Align Technology", "https://aligntech.wd5.myworkdayjobs.com/aligncareers"),
    ("Chevron", "https://chevron.wd5.myworkdayjobs.com/jobs"),
    ("Philip Morris", "https://pmi.wd3.myworkdayjobs.com/PMI"),
    ("Teva", "https://teva.wd3.myworkdayjobs.com/TEVA"),
    ("Teva", "https://teva.wd3.myworkdayjobs.com/Teva_Careers"),
    ("Philips", "https://philips.wd3.myworkdayjobs.com/jobs-and-careers"),
    ("Dell", "https://dell.wd1.myworkdayjobs.com/External"),
    ("Broadcom", "https://broadcom.wd1.myworkdayjobs.com/External_Career"),
    ("Analog Devices", "https://analogdevices.wd1.myworkdayjobs.com/External"),
    ("Pfizer", "https://pfizer.wd1.myworkdayjobs.com/PfizerCareers"),
    ("Mobileye", "https://mobileye.wd1.myworkdayjobs.com/Mobileye"),
    ("CyberArk", "https://cyberark.wd1.myworkdayjobs.com/CyberArk"),
    ("Amdocs", "https://amdocs.wd3.myworkdayjobs.com/Amdocs"),
    ("Check Point", "https://checkpoint.wd3.myworkdayjobs.com/CheckPoint"),
    ("Visa", "https://visa.wd5.myworkdayjobs.com/Visa"),
    ("Siemens Healthineers", "https://siemenshealthineers.wd3.myworkdayjobs.com/Careers"),
    ("Sanofi", "https://sanofi.wd3.myworkdayjobs.com/SanofiCareers"),
    ("Roche", "https://roche.wd3.myworkdayjobs.com/roche-ext"),
    ("Boston Scientific", "https://bostonscientific.wd1.myworkdayjobs.com/BSCI"),
    ("Zimmer Biomet", "https://zimmerbiomet.wd1.myworkdayjobs.com/External"),
]

COMEET = [
    ("monday.com", "https://www.comeet.com/jobs/monday/41.00B"),
    ("Riverside", "https://careers.riverside.fm/careers"),
    ("Check Point", "https://careers.checkpoint.com/"),
    ("HiBob", "https://www.hibob.com/careers/"),
    ("Papaya Global", "https://www.papayaglobal.com/careers/"),
    ("Lemonade", "https://makers.lemonade.com/"),
    ("Fiverr", "https://www.fiverr.com/jobs"),
    ("Redis", "https://redis.io/careers/"),
    ("Global-e", "https://www.global-e.com/careers/"),
    ("Elementor", "https://elementor.com/careers/"),
    ("Buildots", "https://buildots.com/careers/"),
    ("Pagaya", "https://pagaya.com/careers/"),
    ("Sisense", "https://www.sisense.com/careers/"),
    ("Lusha", "https://www.lusha.com/careers/"),
    ("Nayax", "https://www.nayax.com/careers/"),
    ("Tipalti", "https://tipalti.com/careers/"),
]

BOARDS = [("greenhouse", fetch_greenhouse, GREENHOUSE_BOARDS),
          ("lever", fetch_lever, LEVER_COMPANIES),
          ("ashby", fetch_ashby, ASHBY_BOARDS),
          ("smartrecruiters", fetch_smartrecruiters, SMARTRECRUITERS_COMPANIES)]


def summarize(jobs):
    israel = [j for j in jobs if any(l in j["location"].lower() for l in LOCATIONS)]
    relevant = [j for j in jobs if is_relevant(j)]
    return len(jobs), len(israel), relevant


def attempt(label, fetch):
    try:
        jobs = fetch()
    except Exception:
        return None
    if not jobs:
        return None
    total, israel, relevant = summarize(jobs)
    return label, total, israel, relevant


if __name__ == "__main__":
    tasks = []
    for slug in dict.fromkeys(SLUGS):
        for kind, fetch, existing in BOARDS:
            if slug not in existing:
                tasks.append((f"{kind}:{slug}", lambda f=fetch, s=slug: f(s)))
    known = {u for _, u in WORKDAY_SITES}
    tasks += [(f"workday:{n}|{u}", lambda n=n, u=u: fetch_workday(n, u, max_jobs=200))
              for n, u in WORKDAY if u not in known]
    known = {u for _, u in COMEET_PAGES}
    tasks += [(f"comeet:{n}|{u}", lambda n=n, u=u: fetch_comeet(n, u))
              for n, u in COMEET if u not in known]

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = [r for r in pool.map(lambda t: attempt(*t), tasks) if r]

    results.sort(key=lambda r: (-len(r[3]), -r[2]))
    print(f"\nTried {len(tasks)} combinations, {len(results)} answered.\n")
    print("FOUND (label | all jobs | in Israel | pass the agent's filter)")
    for label, total, israel, relevant in results:
        print(f"FOUND {label} | {total} | {israel} | {len(relevant)}")
        for j in relevant[:4]:
            print(f"      - {j['title']} | {j['location']}")
