"""
Job Search Agent - Stage 3: save jobs to Google Sheets (no duplicates).
"""
import os
from datetime import date

import gspread

# The long ID from your sheet's URL:
# https://docs.google.com/spreadsheets/d/<THIS PART>/edit
SHEET_ID = os.environ.get("SHEET_ID", "1hiC8Ao8HjyXIVdFXZ-4yKj6OEq5o8JcINDSTQ2Gg-ZM")
CREDENTIALS_FILE = "credentials.json"   # never upload this file to GitHub!

HEADERS = ["date_found", "company", "title", "location", "url",
           "score", "reason", "status"]


def get_worksheet():
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    ws = gc.open_by_key(SHEET_ID).sheet1
    if ws.row_values(1) != HEADERS:          # first run: add header row
        ws.update(range_name="A1", values=[HEADERS])
    return ws


def save_new_jobs(jobs):
    """Append only jobs whose URL isn't already in the sheet.
    Returns the list of jobs that were actually new."""
    ws = get_worksheet()
    url_col = HEADERS.index("url") + 1
    existing_urls = set(ws.col_values(url_col)[1:])   # skip header

    new_jobs = [j for j in jobs if j["url"] not in existing_urls]
    today = date.today().isoformat()
    rows = [[today, j["company"], j["title"], j["location"], j["url"],
             "", "", "new"] for j in new_jobs]
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    return new_jobs


def get_unscored_jobs():
    """Return the worksheet and every row that has a URL but no score yet."""
    ws = get_worksheet()
    pending = []
    for row_number, row in enumerate(ws.get_all_values()[1:], start=2):
        row = row + [""] * (len(HEADERS) - len(row))
        job = dict(zip(HEADERS, row))
        if job["url"] and not job["score"]:
            job["row"] = row_number
            pending.append(job)
    return ws, pending


def get_jobs_by_urls(urls):
    """Read back rows (with their scores) for the given job URLs."""
    if not urls:
        return []
    ws = get_worksheet()
    jobs = []
    for row in ws.get_all_values()[1:]:
        row = row + [""] * (len(HEADERS) - len(row))
        job = dict(zip(HEADERS, row))
        if job["url"] in urls:
            jobs.append(job)
    return jobs


def write_scores(ws, results):
    """results: list of (row_number, score, reason)."""
    score_col = HEADERS.index("score") + 1
    data = [{"range": f"{gspread.utils.rowcol_to_a1(row, score_col)}:"
                      f"{gspread.utils.rowcol_to_a1(row, score_col + 1)}",
             "values": [[score, reason]]}
            for row, score, reason in results]
    if data:
        ws.batch_update(data, value_input_option="USER_ENTERED")
