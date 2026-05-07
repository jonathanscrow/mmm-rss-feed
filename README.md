# Monday Morning Motivator — RSS Feed System

This repo holds the production feed that drives TexInspec's Monday Morning Motivator
email, sent every Monday at 8 AM Central to the subscriber list via GHL/HelpMeEngage.

## How it works

1. **Source of truth** is a Google Sheet (260 rows, one per week, dated 2026-05-11
   through 2031-04-28).
2. **Sunday at 6 AM CT** a GitHub Action reads the Sheet, finds the row for the
   upcoming Monday, and writes `mmm-feed.xml` to this repo.
3. **Sunday at 7 AM CT** a "preview" campaign in GHL polls `mmm-feed.xml` and
   sends to a small test list (you).
4. **You review the preview** during Sunday and edit the Sheet if needed.
5. **Monday at 7 AM CT** the same Action runs again, picking up any edits.
6. **Monday at 8 AM CT** the production campaign in GHL polls `mmm-feed.xml` and
   sends to the full subscriber list.

The feed contains exactly **one item** at any time: whichever week's content is
"current" by the calendar. The channel `<title>` matches the item title, so GHL's
subject line (which only supports `{{rss_feed.title}}`) stays dynamic per week.

## Editing the calendar

**For weekly content edits** — wrong quote, better image, typo fix, etc.:

1. Open the Google Sheet
2. Find the row for the week you want to change
3. Edit the cell (`quote`, `subject_line`, `image_url`, etc.)
4. Save (Sheets auto-saves)
5. The next rotation (Sunday 6 AM or Monday 7 AM) will pick up your change

**For emergency same-day edits** (e.g., realized at 7:30 AM Monday that something
is wrong before the 8 AM send):

- Edit the Sheet, then **manually trigger the Monday rotation Action** (Actions
  tab → "Monday Feed Rotation" → "Run workflow" button). Takes ~30 seconds to
  run. Ensures the feed reflects your edit before GHL polls at 8 AM.
- OR edit `mmm-feed.xml` directly in the repo's web UI. **Caveat:** direct XML
  edits get overwritten by the next regen, so this is only good for "I need to
  fix something for THIS week's send and that's it."

## Stopping a Monday send

If the preview email reveals something so wrong it shouldn't go to the list at
all, you have three options, in order of speed:

1. **Pause the GHL production campaign** (HME → Marketing → Email → find the
   campaign → three-dot menu → Pause). Fastest, ~30 seconds. Email never sends.
2. **Replace the image_url in the Sheet** with a placeholder if you just want
   to swap the image. Trigger Monday rotation manually.
3. **Edit `mmm-feed.xml` directly** in the GitHub web UI to neuter the bad
   content. Last resort.

## Files

- `scripts/generate_feed.py` — the rotation script
- `.github/workflows/sunday-rotate.yml` — Sunday 6 AM CT cron
- `.github/workflows/monday-rotate.yml` — Monday 7 AM CT cron
- `mmm-feed.xml` — the live feed (regenerated each Sunday and Monday)
- `logs/` — audit trail; one text file per Monday with what was sent

## Setup (one-time, done at deploy time)

The Action needs two secrets configured in the repo:

- `GOOGLE_SHEETS_CREDENTIALS` — JSON service account credentials
- `GOOGLE_SHEET_ID` — the Sheet's ID (the long string in its URL)

The service account needs **Viewer** access to the Sheet (share the Sheet with
the service account's email).

## Failure modes & alerts

- **Action fails** — GitHub emails the repo owner automatically. Most common
  cause: someone revoked the service account's access to the Sheet, or rotated
  its credentials.
- **Calendar runs out** (after 2031-04-28) — the script exits with an error,
  Action fails, you get an email. ~5 years of warning.
- **Sheet has a malformed date** — script exits with an error explaining
  exactly which row.
- **GHL doesn't fire** — the Action commits aren't enough to detect this.
  Manual check Monday morning is the safety net.

## Why this architecture

We chose to "rotate one item" rather than "publish all 260 with future pubDates"
because GHL's RSS Schedule item-selection logic turned out to be unpredictable
(see the test results in the May 2026 setup conversation). A feed with exactly
one item gives GHL nothing to choose between, which makes delivery deterministic.
