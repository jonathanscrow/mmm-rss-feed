# SETUP — Google Cloud Service Account + GitHub Secrets

This is a one-time setup. Total time: about 15 minutes.

You'll create a "service account" — a robot Google identity that the GitHub Action
will use to read the Sheet on its own schedule, without needing your password.

## Part 1 — Google Cloud Console (10 min)

### Step 1: Pick or create a project

1. Go to https://console.cloud.google.com/
2. At the top of the page, click the project dropdown (next to "Google Cloud" logo)
3. Either:
   - **Pick an existing project** if you already have one for TexInspec, OR
   - Click **New Project**, name it `texinspec-automation` (or whatever), click Create

### Step 2: Enable the Google Sheets API

1. In the left sidebar (or via the search bar at top), find **APIs & Services → Library**
2. Search for **"Google Sheets API"**
3. Click on the result, then click **Enable**
4. Wait ~10 seconds for it to enable

### Step 3: Create the service account

1. Sidebar: **APIs & Services → Credentials**
2. Top of page: **+ Create Credentials → Service account**
3. Service account name: `mmm-rss-reader`
4. Service account ID: will auto-fill — leave it
5. Description: `Reads MMM calendar Sheet for GitHub Action`
6. Click **Create and Continue**
7. **Grant this service account access to project** — leave blank, click **Continue**
8. **Grant users access to this service account** — leave blank, click **Done**

### Step 4: Generate the JSON key

1. You should now see your new service account in the list. Click on its email
   (something like `mmm-rss-reader@texinspec-automation.iam.gserviceaccount.com`)
2. Click the **Keys** tab
3. **Add Key → Create new key**
4. Select **JSON**, click **Create**
5. A JSON file downloads to your computer. **Keep this file safe** — it's the
   "password" the Action uses. Don't email it, don't paste it in chats, don't
   commit it to a repo.

### Step 5: Share the Sheet with the service account

1. Open the JSON file in a text editor and copy the value of `client_email`
   (it'll look like `mmm-rss-reader@texinspec-automation.iam.gserviceaccount.com`)
2. Open your Google Sheet
3. Click **Share** (top right)
4. Paste the service account email
5. **Set permission to Viewer** (read-only — that's all the Action needs)
6. **Uncheck "Notify people"** (the service account doesn't have an inbox)
7. Click **Share**

The service account can now read the Sheet.

## Part 2 — GitHub repo secrets (5 min)

### Step 6: Add the credentials to GitHub

1. Open your GitHub repo: https://github.com/jonathanscrow/mmm-rss-feed
2. **Settings** tab (top right of the repo page)
3. Left sidebar: **Secrets and variables → Actions**
4. Click **New repository secret**
5. Name: `GOOGLE_SHEETS_CREDENTIALS`
6. Value: open the JSON file you downloaded in Step 4, **copy its entire contents**
   (the whole `{ ... }` block), paste it into the value field
7. Click **Add secret**

### Step 7: Add the Sheet ID

1. Open your Google Sheet, look at the URL. It looks like:
   `https://docs.google.com/spreadsheets/d/1EXab7khmunvJvOwwZF21iThLohDVTH70fvifpZAbdWs/edit`
2. The Sheet ID is the long string between `/d/` and `/edit`. In the example
   above it's `1EXab7khmunvJvOwwZF21iThLohDVTH70fvifpZAbdWs`
3. Back in GitHub Secrets: **New repository secret**
4. Name: `GOOGLE_SHEET_ID`
5. Value: paste the Sheet ID
6. Click **Add secret**

## Part 3 — Test it

### Step 8: Manually run the rotation Action

1. In GitHub: **Actions** tab
2. Left sidebar: **Sunday Feed Rotation**
3. Right side: **Run workflow → Run workflow**
4. Wait ~30 seconds, refresh the page
5. You should see a green checkmark
6. Click into the run, then into the "Generate feed from Google Sheet" step,
   to see what week it picked

### What success looks like

The Action should print something like:

```
Today (Central): 2026-05-07 (Thursday)
Target Monday:   2026-05-04
ERROR: No row in the Sheet has send_date=2026-05-04...
```

(Wait — that's actually expected for **today**, May 7 2026. Our calendar starts
May 11. Once we're past May 11, the Action will succeed and produce a real feed.
For testing, see the "Sanity check" step below.)

### Sanity check before May 11

Edit the script temporarily to force a specific week, OR just wait until Sunday
May 10 when the natural rotation will pick up Wk1 (Lewis, May 11). Either works.

## What's already done

- ✅ `scripts/generate_feed.py` — the script
- ✅ `.github/workflows/sunday-rotate.yml` — Sunday 6 AM CT
- ✅ `.github/workflows/monday-rotate.yml` — Monday 7 AM CT
- ✅ `README.md` — operating manual

## What's left after Setup

- Build the **Preview campaign** in GHL (sends to you only, polls `mmm-feed.xml`,
  Sunday 7 AM CT)
- Build the **Production campaign** in GHL (sends to 28k list, polls `mmm-feed.xml`,
  Monday 8 AM CT, batch 1250/5min)
- Wait for the first natural Sunday rotation (May 10) and Monday send (May 11)
- Verify the preview email looks right Sunday morning
- Verify the production email lands Monday morning
- If both work: pause the manually-built Wk2 and Wk3 campaigns (they'd send
  duplicates otherwise), let the production system take over from Wk2 onward
