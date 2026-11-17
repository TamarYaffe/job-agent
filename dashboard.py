"""
Job Search Agent - Stage 6: a dashboard tab in the Google Sheet.

Every run it:
  1. saves today's snapshot to the "history" tab (open jobs per role family) and to
     "history_companies" (open jobs per company) - running twice a day just overwrites
     today's numbers, so the history stays clean;
  2. rewrites the "dashboard" tab: today's numbers, my application pipeline,
     open jobs by role and by company;
  3. adds 3 charts the first time (trend over time, by company, my applications).
"""
from collections import Counter
from datetime import date

import gspread

from sheets import HEADERS, STATUS_OPTIONS, get_worksheet

# A title goes to the first family whose words appear in it (order matters:
# "Supply Chain Project Manager" is a project role, "Product Analyst" a data role).
ROLE_FAMILIES = [
    ("Project / Program", ["project", "program", "pmo"]),
    ("Data / Analytics", ["analyst", "analytics", "data", "bi ", "insight"]),
    ("Product", ["product"]),
    ("Operations / Supply chain", ["operation", "supply", "planner", "buyer", "purchas",
                                   "logistic", "material", "sourcing", "inventory",
                                   "demand", "scheduler", "order"]),
]
OTHER = "Other"
FAMILIES = [name for name, _ in ROLE_FAMILIES] + [OTHER]

HISTORY_HEADERS = ["date", "jobs_scanned", "open_relevant"] + FAMILIES
COMPANY_HISTORY_HEADERS = ["date", "company", "open_jobs"]

# Fixed layout of the dashboard tab (the charts point at these rows)
STATUS_ROW = 13            # header row of "My applications"
ROLE_ROW = 24              # header row of "Open jobs by role"
COMPANY_ROW = 33           # header row of "Open jobs by company"
MAX_COMPANIES = 30
CHART_TREND = "Open jobs by role over time"
CHART_COMPANY = "Open jobs by company"
CHART_STATUS = "My applications"


def role_family(title):
    t = title.lower() + " "
    for name, words in ROLE_FAMILIES:
        if any(w in t for w in words):
            return name
    return OTHER


def _score(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tab(sh, title, rows=1000, cols=12):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _read_jobs(ws):
    jobs = []
    for row in ws.get_all_values()[1:]:
        row = row + [""] * (len(HEADERS) - len(row))
        job = dict(zip(HEADERS, row))
        if job["url"]:
            jobs.append(job)
    return jobs


def build_tables(jobs):
    """Everything the dashboard shows, computed from the rows of the jobs tab."""
    open_jobs = [j for j in jobs if not j["closed_on"]]
    by_role = Counter(role_family(j["title"]) for j in open_jobs)
    by_company = Counter(j["company"] for j in open_jobs)
    best = {}
    for j in open_jobs:
        s = _score(j["score"])
        if s is not None:
            best[j["company"]] = max(best.get(j["company"], 0), int(s) if s == int(s) else s)
    statuses = Counter((j["status"] or "new").strip().lower() for j in jobs)
    scores = [s for s in (_score(j["score"]) for j in open_jobs) if s is not None]
    return {
        "open": len(open_jobs),
        "strong": sum(1 for s in scores if s >= 8),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else "",
        "favorite_companies": len({j["company"] for j in open_jobs if j["favorite"]}),
        "by_role": [[f, by_role.get(f, 0)] for f in FAMILIES],
        "by_company": [[c, n, best.get(c, "")] for c, n in
                       sorted(by_company.items(), key=lambda x: (-x[1], x[0]))][:MAX_COMPANIES],
        "statuses": [[s, statuses.get(s, 0)] for s in STATUS_OPTIONS],
    }


def _save_history(sh, today, scanned, t):
    ws = _tab(sh, "history", cols=len(HISTORY_HEADERS))
    rows = ws.get_all_values()
    if not rows or rows[0] != HISTORY_HEADERS:
        ws.update(range_name="A1", values=[HISTORY_HEADERS])
        rows = [HISTORY_HEADERS] + rows[1:]
    line = [today, scanned, t["open"]] + [n for _, n in t["by_role"]]
    dates = [r[0] if r else "" for r in rows]
    if today in dates:                              # second run today: overwrite
        ws.update(range_name=f"A{dates.index(today) + 1}", values=[line],
                  value_input_option="USER_ENTERED")
    else:
        ws.append_rows([line], value_input_option="USER_ENTERED")
    return ws

def _save_company_history(sh, today, t):
    ws = _tab(sh, "history_companies", cols=len(COMPANY_HISTORY_HEADERS))
    old = [r for r in ws.get_all_values()[1:] if r and r[0] != today]
    new = [[today, c, n] for c, n, _ in t["by_company"]]
    ws.clear()
    ws.update(range_name="A1", values=[COMPANY_HISTORY_HEADERS] + old + new,
              value_input_option="USER_ENTERED")


def _write_dashboard(ws, today, scanned, new_today, t):
    pad = lambda rows, n: rows + [["", "", ""]] * (n - len(rows))
    ws.batch_clear(["A1:C100"])
    ws.batch_update([
        {"range": "A1", "values": [["Job search dashboard"], [f"Updated {today}"]]},
        {"range": "A4", "values": [
            ["Today", ""],
            ["Jobs scanned", scanned],
            ["Relevant jobs open", t["open"]],
            ["New today", new_today],
            ["Strong matches open (score 8+)", t["strong"]],
            ["Average score of open jobs", t["avg_score"]],
            ["Favorite companies hiring", t["favorite_companies"]],
        ]},
        {"range": f"A{STATUS_ROW - 1}", "values": [["My applications"], ["Status", "Jobs"]]
                                                   + t["statuses"]},
        {"range": f"A{ROLE_ROW - 1}", "values": [["Open jobs by role"], ["Role", "Jobs"]]
                                                 + t["by_role"]},
        {"range": f"A{COMPANY_ROW - 1}", "values": [["Open jobs by company"],
                                                    ["Company", "Jobs", "Best score"]]
                                                   + pad(t["by_company"], MAX_COMPANIES)},
    ], value_input_option="USER_ENTERED")


def _grid(sheet_id, r0, r1, c0, c1):
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}


def _chart(title, chart_type, domain, series, value_axis, anchor_sheet, anchor_row, legend):
    return {"addChart": {"chart": {
        "spec": {"title": title, "basicChart": {
            "chartType": chart_type,
            "legendPosition": "BOTTOM_LEGEND" if legend else "NO_LEGEND",
            "headerCount": 1,
            "domains": [{"domain": {"sourceRange": {"sources": [domain]}}}],
            "series": [{"series": {"sourceRange": {"sources": [s]}}, "targetAxis": value_axis}
                       for s in series]}},
        "position": {"overlayPosition": {
            "anchorCell": {"sheetId": anchor_sheet, "rowIndex": anchor_row, "columnIndex": 4},
            "widthPixels": 640, "heightPixels": 340}}}}}


def _format_once(sh, dash, hist):
    """Bold headers, column widths and the 3 charts - only what's missing."""
    meta = sh.fetch_sheet_metadata(
        {"fields": "sheets(properties(sheetId),charts(spec(title)))"})
    titles = {c.get("spec", {}).get("title") for s in meta.get("sheets", [])
              for c in s.get("charts", [])}
    d, h = dash.id, hist.id
    bold = lambda r, size=10: {"repeatCell": {
        "range": _grid(d, r, r + 1, 0, 3),
        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": size}}},
        "fields": "userEnteredFormat.textFormat"}}
    requests = [bold(0, 16), bold(3, 12), bold(STATUS_ROW - 2, 12), bold(STATUS_ROW - 1),
                bold(ROLE_ROW - 2, 12), bold(ROLE_ROW - 1),
                bold(COMPANY_ROW - 2, 12), bold(COMPANY_ROW - 1),
                {"updateDimensionProperties": {
                    "range": {"sheetId": d, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                    "properties": {"pixelSize": 240}, "fields": "pixelSize"}}]
    first_family = HISTORY_HEADERS.index(FAMILIES[0])
    if CHART_TREND not in titles:
        requests.append(_chart(
            CHART_TREND, "LINE", _grid(h, 0, 1000, 0, 1),
            [_grid(h, 0, 1000, c, c + 1) for c in range(first_family, len(HISTORY_HEADERS))],
            "LEFT_AXIS", d, 0, legend=True))
    if CHART_COMPANY not in titles:
        r0 = COMPANY_ROW - 1
        requests.append(_chart(
            CHART_COMPANY, "BAR", _grid(d, r0, r0 + 1 + MAX_COMPANIES, 0, 1),
            [_grid(d, r0, r0 + 1 + MAX_COMPANIES, 1, 2)], "BOTTOM_AXIS", d, 18, legend=False))
    if CHART_STATUS not in titles:
        r0 = STATUS_ROW - 1
        requests.append(_chart(
            CHART_STATUS, "COLUMN", _grid(d, r0, r0 + 1 + len(STATUS_OPTIONS), 0, 1),
            [_grid(d, r0, r0 + 1 + len(STATUS_OPTIONS), 1, 2)], "LEFT_AXIS", d, 36,
            legend=False))
    sh.batch_update({"requests": requests})


def update_dashboard(scanned, new_today):
    jobs_ws = get_worksheet()
    sh = jobs_ws.spreadsheet
    today = date.today().isoformat()
    t = build_tables(_read_jobs(jobs_ws))
    hist = _save_history(sh, today, scanned, t)
    _save_company_history(sh, today, t)
    dash = _tab(sh, "dashboard", rows=100, cols=12)
    _write_dashboard(dash, today, scanned, new_today, t)
    try:
        _format_once(sh, dash, hist)
    except Exception as e:      # looks are nice-to-have; the numbers are already saved
        print(f"(dashboard formatting skipped: {e})")
    print(f"Dashboard: {t['open']} open jobs, {t['strong']} strong matches")
