"""
Job Search Agent - Stage 4: score each job against the candidate profile with Gemini.

Run on its own:  python3 scorer.py   (scores every sheet row that has no score yet)
It also runs automatically at the end of fetch_jobs.py.
"""
import html
import json
import os
import re
import time
from urllib.parse import urlparse

import requests

from sheets import get_unscored_jobs, write_scores

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")  # fast model, bigger free quota
BATCH_SIZE = 4        # jobs per request - fewer requests = stays inside the free tier
PAUSE_SECONDS = 8     # free tier allows only a few requests per minute


PROMPT = """You are a practical career advisor helping a job seeker in Israel.

CANDIDATE PROFILE:
{profile}

Rate how well each job below fits this candidate, on a 1-10 scale:
- 9-10: strong fit - she should apply today
- 6-8: reasonable fit - worth applying
- 3-5: weak fit
- 1-2: not relevant (different field, far too senior, or not located in Israel)

Be realistic: compare the seniority and years of experience the job requires
with what the profile actually shows. Use the "Locations" line when present.

Return ONLY a JSON array, one object per job, in this exact shape:
[{{"id": 0, "score": 7, "reason": "one short sentence explaining the score"}}]

JOBS:
{jobs}
"""


def load_env(path=".env"):
    """Read KEY=VALUE lines from .env into environment variables."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def clean_html(raw):
    text = html.unescape(raw or "")
    text = re.sub(r"<(script|style).*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_description(url):
    """Get the full job description (and real locations for Workday jobs)."""
    try:
        parsed = urlparse(url)
        if parsed.netloc.endswith("myworkdayjobs.com"):
            # https://<tenant>.wdN.myworkdayjobs.com/<site>/job/...  ->  JSON API
            tenant = parsed.netloc.split(".")[0]
            site, _, rest = parsed.path.strip("/").partition("/")
            api = f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}/{rest}"
            r = requests.get(api, headers={"Accept": "application/json"}, timeout=30)
            r.raise_for_status()
            info = r.json().get("jobPostingInfo", {})
            locations = [info.get("location", "")] + info.get("additionalLocations", [])
            text = ("Locations: " + ", ".join(l for l in locations if l) + "\n"
                    + clean_html(info.get("jobDescription", "")))
        else:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            text = clean_html(r.text)
        return text[:3000]   # keep prompts small = faster answers
    except Exception as e:
        return f"(could not load description: {e})"


def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "temperature": 0.2}}
    for attempt in range(3):
        try:
            r = requests.post(url, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                              json=body, timeout=180)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            print(f"  Gemini didn't answer in time, retrying ({attempt + 1}/3)...")
            time.sleep(10)
            continue
        if r.status_code in (429, 500, 503):   # rate limit / overloaded - wait and retry
            wait = 30 * (attempt + 1)
            print(f"  Gemini busy ({r.status_code}), waiting {wait}s...")
            time.sleep(wait)
            continue
        if not r.ok:
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:400]}")
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    raise RuntimeError("Gemini unavailable after 3 tries - run again later")


def build_prompt(profile, batch):
    jobs_text = "\n\n".join(
        f"### Job id={i}\nTitle: {j['title']}\nCompany: {j['company']}\n"
        f"Location: {j['location']}\nDescription: {j['description']}"
        for i, j in enumerate(batch))
    return PROMPT.format(profile=profile, jobs=jobs_text)


def score_pending(profile_path="profile.txt"):
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        print("AI scoring skipped: no GEMINI_API_KEY in .env")
        return
    with open(profile_path, encoding="utf-8") as f:
        profile = f.read()

    ws, pending = get_unscored_jobs()
    print(f"\nAI scoring: {len(pending)} jobs to score")

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        for job in batch:
            job["description"] = fetch_description(job["url"])
        try:
            results = call_gemini(build_prompt(profile, batch))
        except Exception as e:
            print(f"[error] {e}")
            break   # unscored rows stay empty and get scored next run

        by_id = {int(r["id"]): r for r in results if "id" in r}
        updates = []
        for i, job in enumerate(batch):
            r = by_id.get(i)
            if r:
                updates.append((job["row"], int(r["score"]), r.get("reason", "")))
                print(f"  {int(r['score']):>2}/10  {job['title']}")
        write_scores(ws, updates)   # save after every batch

        if start + BATCH_SIZE < len(pending):
            time.sleep(PAUSE_SECONDS)


if __name__ == "__main__":
    score_pending()
