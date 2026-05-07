#!/usr/bin/env python3
"""
generate_feed.py — Monday Morning Motivator feed generator.

Reads the campaign calendar from Google Sheets, finds the row whose send_date
matches the upcoming Monday (or today if today is Monday), and writes
mmm-feed.xml with that single item.

Design principles:
- The Google Sheet is the canonical source of truth. This script is a pure function:
  (sheet contents, current date) -> feed file. No state is kept anywhere else.
- Forward-looking date logic: on Sunday, the script picks tomorrow's Monday so the
  Sunday preview email shows the upcoming send. On Monday, it picks today.
  Tuesday-Saturday it picks the next Monday (immaterial — feed isn't polled
  during those days anyway).
- Writes to stdout for the GitHub Action log (auditable: each run prints which week
  was selected and why).
- Exits non-zero on any error so the Action shows a failure (which emails the repo
  owner).

Environment variables required:
- GOOGLE_SHEETS_CREDENTIALS: JSON service account credentials (set via GitHub Secret)
- GOOGLE_SHEET_ID: the Sheet's ID from its URL
- GOOGLE_SHEET_TAB: optional, the tab name (defaults to first tab)

Output: writes mmm-feed.xml to the repo root.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime

import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Date logic
# ---------------------------------------------------------------------------

def central_today():
    """Return today's date in Central Time."""
    # Use UTC-6 (CST) to be conservative — at worst this means during a DST overlap
    # we'd consider it "still yesterday" in Texas, which is fine because the date
    # we care about (this week's Monday) doesn't change.
    utc_now = datetime.now(timezone.utc)
    central_offset = timezone(timedelta(hours=-6))  # CST
    return utc_now.astimezone(central_offset).date()


def upcoming_monday_on_or_after(d):
    """Return the next Monday from date d, or d itself if d is already a Monday.

    Examples:
      Sunday   2026-05-10 -> Monday 2026-05-11
      Monday   2026-05-11 -> Monday 2026-05-11  (today)
      Tuesday  2026-05-12 -> Monday 2026-05-18  (next week)
      Saturday 2026-05-16 -> Monday 2026-05-18  (next week)
    """
    days_ahead = (0 - d.weekday()) % 7  # Mon=0, ..., Sun=6
    return d + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# Google Sheets reader
# ---------------------------------------------------------------------------

def load_calendar_from_sheets():
    """Read all rows from the Google Sheet. Returns a list of dicts."""
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
    sheet_id = os.environ.get('GOOGLE_SHEET_ID')
    tab_name = os.environ.get('GOOGLE_SHEET_TAB', '').strip()

    if not creds_json:
        sys.exit("ERROR: GOOGLE_SHEETS_CREDENTIALS env var is empty. Did you set the GitHub Secret?")
    if not sheet_id:
        sys.exit("ERROR: GOOGLE_SHEET_ID env var is empty.")

    try:
        creds_dict = json.loads(creds_json)
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: GOOGLE_SHEETS_CREDENTIALS is not valid JSON: {e}")

    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(tab_name) if tab_name else sh.sheet1

    rows = ws.get_all_records()
    if not rows:
        sys.exit("ERROR: Sheet is empty or could not be read.")

    return rows


# ---------------------------------------------------------------------------
# Find the current week's row
# ---------------------------------------------------------------------------

def find_current_row(rows, target_date):
    """Find the row whose send_date matches target_date (a date object)."""
    target_str = target_date.strftime('%Y-%m-%d')
    for row in rows:
        if str(row.get('send_date', '')).strip() == target_str:
            return row
    return None


# ---------------------------------------------------------------------------
# Build the RSS feed XML
# ---------------------------------------------------------------------------

def xml_escape(s):
    """Escape XML special characters in attribute values and text."""
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def build_feed(row, generated_at_utc):
    """
    Build the RSS 2.0 feed with a single <item>.

    Channel-level metadata is set to match the item's content because GHL's RSS
    Schedule subject-line field only supports {{rss_feed.*}} (channel) variables,
    not {{rss_item.*}}. By making channel.title == item.subject, the email subject
    line stays dynamic per week.
    """
    week = row['week_num']
    quote = row['quote']
    author = row['author']
    subject = row['subject_line']
    image_url = row['image_url']
    send_date = row['send_date']

    # GUID must be stable per week. Using week_num + send_date makes it
    # impossible for two weeks to ever have the same GUID.
    guid = f"mmm-wk{int(week):03d}-{send_date}"

    # pubDate at noon CT on the send_date. Doesn't really matter for delivery
    # since GHL ignores pubDate for filtering, but it should be a real date
    # for any RSS reader that consumes the feed directly.
    pub_dt = datetime.strptime(send_date, '%Y-%m-%d')
    pub_dt = pub_dt.replace(hour=12, tzinfo=timezone(timedelta(hours=-6)))

    # The HTML body of the email. This is what {{rss_item.content_full}}
    # renders inside the RSS Items block in GHL.
    description_html = f'''<![CDATA[
<div style="text-align:center;font-family:Georgia,serif;">
  <img src="{image_url}" alt="Monday Motivator Week {week}" style="max-width:600px;width:100%;height:auto;display:block;margin:0 auto;" />
  <blockquote style="font-size:20px;font-style:italic;margin:24px auto;max-width:540px;line-height:1.5;">
    &ldquo;{xml_escape(quote)}&rdquo;
  </blockquote>
  <p style="font-size:16px;color:#555;margin-top:16px;">— {xml_escape(author)}</p>
</div>
]]>'''

    feed = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{xml_escape(subject)}</title>
    <link>https://www.texinspec.com/monday-motivator</link>
    <description>Weekly motivation from TexInspec</description>
    <language>en-us</language>
    <lastBuildDate>{format_datetime(generated_at_utc)}</lastBuildDate>
    <atom:link href="https://raw.githubusercontent.com/jonathanscrow/mmm-rss-feed/refs/heads/main/mmm-feed.xml" rel="self" type="application/rss+xml" />
    <item>
      <title>{xml_escape(subject)}</title>
      <link>https://www.texinspec.com/monday-motivator/wk{int(week):03d}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{format_datetime(pub_dt)}</pubDate>
      <author>clientcare@texinspec.com (TexInspec)</author>
      <description>{description_html}</description>
      <enclosure url="{xml_escape(image_url)}" type="image/png" length="0" />
      <media:content url="{xml_escape(image_url)}" medium="image" type="image/png" />
    </item>
  </channel>
</rss>
'''
    return feed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    today_ct = central_today()
    target_monday = upcoming_monday_on_or_after(today_ct)

    print(f"Today (Central): {today_ct} ({today_ct.strftime('%A')})")
    print(f"Target Monday:   {target_monday}")

    print("Loading calendar from Google Sheets...")
    rows = load_calendar_from_sheets()
    print(f"Loaded {len(rows)} rows.")

    row = find_current_row(rows, target_monday)
    if row is None:
        sys.exit(
            f"ERROR: No row in the Sheet has send_date={target_monday.strftime('%Y-%m-%d')}. "
            f"Either the calendar has run out of weeks (last entry was likely 2031-04-28), "
            f"or there's a date mismatch in the Sheet."
        )

    print(f"Selected: Week {row['week_num']} — {row['author']}")
    print(f"  Subject: {row['subject_line']}")
    print(f"  Image:   {row['image_url'][:80]}")

    feed_xml = build_feed(row, datetime.now(timezone.utc))

    output_path = 'mmm-feed.xml'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(feed_xml)

    print(f"Wrote {output_path} ({len(feed_xml)} bytes).")

    # Also write a per-week audit log entry. These accumulate over 5 years and
    # provide a forensic trail of "what was sent each week."
    os.makedirs('logs', exist_ok=True)
    log_path = f"logs/{target_monday.strftime('%Y-%m-%d')}-wk{int(row['week_num']):03d}.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Send date: {row['send_date']}\n")
        f.write(f"Week:      {row['week_num']}\n")
        f.write(f"Author:    {row['author']}\n")
        f.write(f"Subject:   {row['subject_line']}\n")
        f.write(f"Image:     {row['image_url']}\n")
        f.write(f"Quote:     {row['quote']}\n")
    print(f"Wrote audit log: {log_path}")


if __name__ == '__main__':
    main()
