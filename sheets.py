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
           "score", "reason", "status", "favorite", "closed_on"]

# Options in the status dropdown. The agent sets "new" and "closed";
# the rest are for you to track your applications. You can also type anything else.
STATUS_OPTIONS = ["new", "interested", "applied", "interview", "offer",
                  "rejected", "not interested", "closed"]
CLOSED_COLOR = {"red": 0.96, "green": 0.78, "blue": 0.78}   # light red

_formatted = False


def _col_letter(col):
    return "".join(c for c in gspread.utils.rowcol_to_a1(1, col) if c.isalpha())


def ensure_formatting(ws):
    """Once per run: status dropdown + 'closed rows are red' rule (added only if missing)."""
    global _formatted
    if _formatted:
        return
    _formatted = True
    try:
        sh = ws.spreadsheet
        closed_letter = _col_letter(HEADERS.index("closed_on") + 1)
        formula = f'=${closed_letter}2<>""'
        meta = sh.fetch_sheet_metadata({"fields": "sheets(properties(sheetId),conditionalFormats)"})
        rules = next((s.get("conditionalFormats", []) for s in meta.get("sheets", [])
                      if s["properties"]["sheetId"] == ws.id), [])
        has_rule = any(v.get("userEnteredValue") == formula
                       for r in rules
                       for v in r.get("booleanRule", {}).get("condition", {}).get("values", []))
        requests = []
        if not has_rule:
            requests.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [{"sheetId": ws.id, "startRowIndex": 1,
                            "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA",
                                  "values": [{"userEnteredValue": formula}]},
                    "format": {"backgroundColor": CLOSED_COLOR}}}}})
        status_idx = HEADERS.index("status")
        requests.append({"setDataValidation": {
            "range": {"sheetId": ws.id, "startRowIndex": 1,
                      "startColumnIndex": status_idx, "endColumnIndex": status_idx + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST",
                                   "values": [{"userEnteredValue": v} for v in STATUS_OPTIONS]},
                     "showCustomUi": True, "strict": False}}})
        sh.batch_update({"requests": requests})
    except Exception as e:   # formatting is nice-to-have; never break the run
        print(f"(sheet formatting skipped: {e})")


def get_worksheet():
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    ws = gc.open_by_key(SHEET_ID).sheet1
    if ws.row_values(1) != HEADERS:          # first run: add header row
        ws.update(range_name="A1", values=[HEADERS])
    ensure_formatting(ws)
    return ws


def update_closed_jobs(open_urls_by_company):
    """Mark jobs that disappeared from their company's site as closed (and reopen
    ones that came back). Only companies whose source answered this run are checked.
    Statuses you set yourself (applied, interview...) are kept; the row still turns red."""
    ws = get_worksheet()
    status_col = HEADERS.index("status") + 1
    closed_col = HEADERS.index("closed_on") + 1
    today = date.today().isoformat()
    updates, closed, reopened = [], 0, 0

    def cell(row, col, value):
        updates.append({"range": gspread.utils.rowcol_to_a1(row, col), "values": [[value]]})

    for row_number, row in enumerate(ws.get_all_values()[1:], start=2):
        row = row + [""] * (len(HEADERS) - len(row))
        job = dict(zip(HEADERS, row))
        open_urls = open_urls_by_company.get(job["company"])
        if not open_urls or not job["url"]:
            continue                      # source failed / unknown company: don't touch
        still_open = job["url"] in open_urls
        if not still_open and not job["closed_on"]:
            cell(row_number, closed_col, today)
            if job["status"] in ("", "new"):
                cell(row_number, status_col, "closed")
            closed += 1
        elif still_open and job["closed_on"]:
            cell(row_number, closed_col, "")
            if job["status"] == "closed":
                cell(row_number, status_col, "new")
            reopened += 1
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    return closed, reopened


def save_new_jobs(jobs):
    """Append only jobs whose URL isn't already in the sheet.
    Returns the list of jobs that were actually new."""
    ws = get_worksheet()
    url_col = HEADERS.index("url") + 1
    existing_urls = set(ws.col_values(url_col)[1:])   # skip header

    new_jobs = [j for j in jobs if j["url"] not in existing_urls]
    today = date.today().isoformat()
    rows = [[today, j["company"], j["title"], j["location"], j["url"],
             "", "", "new", j.get("favorite", ""), ""] for j in new_jobs]
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
