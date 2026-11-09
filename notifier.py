"""
Job Search Agent - Stage 5: email digest via Gmail.

Needs in .env:
  EMAIL_ADDRESS=you@gmail.com
  EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   (Gmail App Password, not your normal password)
  EMAIL_TO=you@gmail.com                   (optional - defaults to EMAIL_ADDRESS)
"""
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from html import escape
from zoneinfo import ZoneInfo

from scorer import load_env
from sheets import SHEET_ID

GOOD_SCORE = 6   # jobs at or above this are highlighted


def _score(job):
    try:
        return int(job.get("score") or -1)
    except ValueError:
        return -1


def build_email(jobs, now):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    if not jobs:
        subject = f"Job Agent {now} - no new jobs"
        body = (f"<p>No new relevant jobs in this run.</p>"
                f'<p><a href="{sheet_url}">Open the jobs sheet</a></p>')
        return subject, body

    jobs = sorted(jobs, key=_score, reverse=True)
    good = [j for j in jobs if _score(j) >= GOOD_SCORE]
    subject = f"Job Agent {now} - {len(jobs)} new jobs, {len(good)} worth a look"
    if good:
        best = good[0]
        subject += f" (top: {best['score']}/10 {best['title']} @ {best['company']})"

    rows = []
    for j in jobs:
        s = _score(j)
        style = "background:#e8f5e9;font-weight:bold;" if s >= GOOD_SCORE else "color:#777;"
        rows.append(
            f'<tr style="{style}">'
            f'<td style="padding:6px;text-align:center">{s if s >= 0 else "?"}/10</td>'
            f'<td style="padding:6px"><a href="{escape(j["url"])}">{escape(j["title"])}</a></td>'
            f'<td style="padding:6px">{escape(j["company"])}</td>'
            f'<td style="padding:6px">{escape(j["location"])}</td>'
            f'<td style="padding:6px;font-weight:normal">{escape(j["reason"])}</td></tr>')
    body = (f"<p><b>{len(jobs)}</b> new jobs, <b>{len(good)}</b> scored "
            f"{GOOD_SCORE}+ out of 10.</p>"
            '<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px">'
            '<tr style="background:#333;color:#fff"><th style="padding:6px">Score</th>'
            '<th style="padding:6px">Job</th><th style="padding:6px">Company</th>'
            '<th style="padding:6px">Location</th><th style="padding:6px">Why</th></tr>'
            + "".join(rows) +
            f'</table><p><a href="{sheet_url}">Open the full jobs sheet</a></p>')
    return subject, body


def send_digest(jobs):
    load_env()
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    to = os.environ.get("EMAIL_TO") or sender
    if not sender or not password:
        print("Email skipped: add EMAIL_ADDRESS and EMAIL_APP_PASSWORD to .env")
        return

    now = datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%d/%m %H:%M")
    subject, body = build_email(jobs, now)
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password.replace(" ", ""))
        server.send_message(msg)
    print(f"Email sent to {to}: {subject}")


if __name__ == "__main__":
    # Test: sends a "no new jobs" email so you can check the setup
    send_digest([])
