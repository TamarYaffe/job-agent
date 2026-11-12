"""
Job Search Agent - source discovery (round 2).

Tries each candidate company on Greenhouse, Lever, Ashby and SmartRecruiters,
plus a list of Workday career sites, counts open jobs in Israel, and prints
updated lists to paste into fetch_jobs.py (existing sources are kept).

Run:  python3 discover_sources.py      (takes several minutes)
"""
from fetch_jobs import (ASHBY_BOARDS, GREENHOUSE_BOARDS, LEVER_COMPANIES, LOCATIONS,
                        SMARTRECRUITERS_COMPANIES, WORKDAY_SITES, fetch_ashby,
                        fetch_greenhouse, fetch_lever, fetch_smartrecruiters,
                        fetch_workday)

# Guessed IDs - most will fail, that's expected. The script keeps the ones that work.
CANDIDATES = {
    "israeli tech": [
        "monday", "mondaycom", "wix", "fiverr", "lemonade", "melio", "hibob", "papayaglobal",
        "papaya", "tipalti", "rapyd", "nayax", "gong", "gongio", "fireblocks", "pagaya",
        "snyk", "armis", "armissecurity", "cyera", "orca", "orcasecurity", "lightricks",
        "honeybook", "atbay", "sentinelone", "cyberark", "checkpoint", "playtika",
        "moonactive", "wscsports", "via", "viatransportation", "innovid", "verbit",
        "hunters", "explorium", "coralogix", "komodor", "hailo", "nextsilicon", "etoro",
        "plus500", "lusha", "bringg", "sisense", "port", "portio", "apiiro", "oligo",
        "aquasec", "unity", "tabnine", "duda", "elementor", "guesty", "zesty", "upwind",
        "noname", "salt", "pecan", "pecanai", "superwise", "dataloop", "anecdotes",
        "torq", "silverfort", "catoneworks", "nanit", "deel", "bluevine", "lili",
        "obligo", "unit", "justt", "sunbit", "melio-payments", "trullion", "chargeflow",
        "buildots", "cloudzone", "wilco", "hirepeople", "yalo", "alta", "tailor",
    ],
    "biotech & health": [
        "immunai", "cytoreason", "nucleai", "quris", "quris-ai", "aidoc", "tytocare",
        "biolinerx", "evogene", "compugen", "pluri", "ultrasight", "dreamed",
        "dreamedd", "itamar", "novocure", "enlivex", "emendo", "scopio", "scopiolabs",
        "ibex", "ibexmedical", "nanox", "nanoxvision", "sanara", "eyecarrot", "healthy",
        "healthyio", "sweetch", "diagnostic-robotics", "diagnosticrobotics", "k-health",
        "khealth", "viz", "vizai", "medint", "brainsway", "essentim", "ceribell",
        "biosight", "kamada", "protalix", "gamida", "gamidacell", "teva", "phinergy",
    ],
    "global companies": [
        "visa", "bosch", "mcdonalds", "ikea", "abbvie", "checkpointsoftware",
        "CheckPointSoftwareTechnologies", "amdocs", "nice", "elbit", "elbitsystems",
        "philips", "medtronic", "siemens", "sapient", "servicenow", "palantir",
    ],
}

WORKDAY_CANDIDATES = [
    ("Medtronic", "https://medtronic.wd1.myworkdayjobs.com/MedtronicCareers"),
    ("Philips", "https://philips.wd3.myworkdayjobs.com/jobs-and-careers"),
    ("Motorola Solutions", "https://motorolasolutions.wd5.myworkdayjobs.com/Careers"),
    ("HP", "https://hp.wd5.myworkdayjobs.com/ExternalCareerSite"),
    ("Marvell", "https://marvell.wd1.myworkdayjobs.com/MarvellCareers"),
    ("Broadcom", "https://broadcom.wd1.myworkdayjobs.com/External_Career"),
    ("Analog Devices", "https://analogdevices.wd1.myworkdayjobs.com/External"),
    ("KLA", "https://kla.wd1.myworkdayjobs.com/Search"),
    ("Abbott", "https://abbott.wd5.myworkdayjobs.com/abbottcareers"),
    ("Thermo Fisher", "https://thermofisher.wd5.myworkdayjobs.com/ThermoFisherCareers"),
    ("Pfizer", "https://pfizer.wd1.myworkdayjobs.com/PfizerCareers"),
    ("PayPal", "https://paypal.wd1.myworkdayjobs.com/jobs"),
    ("Dell", "https://dell.wd1.myworkdayjobs.com/External"),
    ("Teva", "https://teva.wd3.myworkdayjobs.com/TevaCareers"),
    ("Teva", "https://teva.wd5.myworkdayjobs.com/TevaCareers"),
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

ATS = [("greenhouse", fetch_greenhouse, GREENHOUSE_BOARDS),
       ("lever", fetch_lever, LEVER_COMPANIES),
       ("ashby", fetch_ashby, ASHBY_BOARDS),
       ("smartrecruiters", fetch_smartrecruiters, SMARTRECRUITERS_COMPANIES)]


def israel_count(jobs):
    return sum(any(loc in j["location"].lower() for loc in LOCATIONS) for j in jobs)


def try_source(fetch):
    try:
        return fetch()
    except Exception:
        return None


if __name__ == "__main__":
    found = {kind: list(existing) for kind, _, existing in ATS}

    for group, slugs in CANDIDATES.items():
        print(f"\n== {group} ==")
        for slug in slugs:
            for kind, fetch, _ in ATS:
                if slug in found[kind]:
                    continue
                jobs = try_source(lambda: fetch(slug))
                if jobs:
                    n = israel_count(jobs)
                    print(f"  {slug:<26} {kind:<16} {len(jobs):>4} jobs, {n:>3} in Israel")
                    if n:
                        found[kind].append(slug)

    print("\n== workday ==")
    known_urls = {url for _, url in WORKDAY_SITES}
    workday = list(WORKDAY_SITES)
    for name, url in WORKDAY_CANDIDATES:
        if url in known_urls or any(n == name for n, _ in workday):
            continue
        jobs = try_source(lambda: fetch_workday(name, url, max_jobs=100))
        if jobs:
            n = israel_count(jobs)
            print(f"  {name:<26} workday          {len(jobs):>4} jobs matching 'Israel', {n} located in Israel")
            if n:
                workday.append((name, url))
        else:
            print(f"  {name:<26} workday          not found")

    print("\n\n######## Paste into fetch_jobs.py (replace the old lists) ########")
    print(f"GREENHOUSE_BOARDS = {found['greenhouse']}")
    print(f"LEVER_COMPANIES = {found['lever']}")
    print(f"ASHBY_BOARDS = {found['ashby']}")
    print(f"SMARTRECRUITERS_COMPANIES = {found['smartrecruiters']}")
    print("WORKDAY_SITES = [")
    for name, url in workday:
        print(f'    ("{name}", "{url}"),')
    print("]")
