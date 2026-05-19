# Run It On The Cloud, For Free, Forever

End state: every day at 3 AM your time, GitHub builds 5 cartoon shorts and uploads them to your YouTube channel. You don't touch your laptop. You don't pay anything.

Total one-time setup: ~30 minutes. After that, zero work.

---

## What runs where

**Your laptop (once, ~20 minutes):**
1. Create a Google Cloud project to get YouTube upload permission
2. Run `setup_cloud_credentials.py` to do the OAuth login
3. Create a GitHub repo and upload these files
4. Paste two secrets into GitHub
5. Hit "run" once to verify it works

**GitHub's servers (forever, free):**
- Daily at the scheduled time: generate scripts, build videos, upload to YouTube
- Save logs you can check on your phone
- Never bothers your laptop

---

## Step 1 — Get Google Cloud / YouTube API access (10 min)

This is the most painful step but it's a one-time thing.

1. Open https://console.cloud.google.com/
2. Click the project dropdown at the top → **New Project**. Name it whatever.
3. In the top search bar, type **YouTube Data API v3** → click it → click **Enable**
4. Left sidebar: **APIs & Services** → **OAuth consent screen**
   - User type: **External** → Create
   - App name: anything (e.g. "cartoon-shorts")
   - User support email: your email
   - Developer contact: your email
   - Save and continue. Skip scopes. Save and continue.
   - On the **Test users** page: click **+ Add Users** → add your own Google account email → Save
5. Left sidebar: **APIs & Services** → **Credentials**
   - **Create Credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Name: anything → Create
   - Download the JSON file
6. Rename the downloaded file to exactly `client_secret.json` and put it in your `cartoon_shorts` folder

---

## Step 2 — Run the OAuth dance locally (2 min)

Open PowerShell in the `cartoon_shorts` folder and run:

```powershell
python setup_cloud_credentials.py
```

A browser will pop open. Log in with the Google account you added as a test user. You'll see a "Google hasn't verified this app" warning — that's normal because it's your own app, click **Advanced** → **Go to [your app name] (unsafe)** → Allow.

When it finishes you'll have a new file called `CLOUD_SECRETS_PASTE_INTO_GITHUB.txt`. Open it in Notepad. Keep it open — you'll need it in step 4.

---

## Step 3 — Create your GitHub repo (5 min)

If you don't have a GitHub account, make one at https://github.com (free, takes 30 seconds).

1. Top right → **+** → **New repository**
2. Repository name: anything (e.g. `cartoon-shorts`)
3. **Public** ← important. Public repos get unlimited Actions minutes. Private ones cap at 2000/month which isn't enough.
4. Skip the README/gitignore options
5. **Create repository**

You'll see a page with upload instructions. The easiest path:
- Click **uploading an existing file** (it's a link in the middle of the page)
- Drag your entire `cartoon_shorts` folder contents into the browser window
- Wait for upload to finish
- Scroll down, click **Commit changes**

**Important: do NOT upload `client_secret.json` or `token.json`** — those should stay only on your laptop. The `.gitignore` file already excludes them, but double-check the file list before committing. If you accidentally upload them, delete the repo and start over.

---

## Step 4 — Paste your secrets into GitHub (3 min)

In your new repo:
1. Click **Settings** (top menu)
2. Left sidebar: **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `YOUTUBE_CLIENT_SECRET`
5. Value: paste the JSON from secret #1 in your `CLOUD_SECRETS_PASTE_INTO_GITHUB.txt` file
6. **Add secret**
7. Repeat for `YOUTUBE_TOKEN` with the JSON from secret #2

**Delete `CLOUD_SECRETS_PASTE_INTO_GITHUB.txt` from your laptop now.** It contains live credentials.

---

## Step 5 — Test it manually (15 min)

1. Go to your repo's **Actions** tab
2. If GitHub asks "Workflows aren't being run on this forked repository", click **I understand my workflows, go ahead and enable them**
3. Left sidebar: click **Daily Cartoon Shorts**
4. On the right: **Run workflow** dropdown → set count to **2** (small test) → keep upload unchecked for safety → **Run workflow**
5. Wait ~15 min. Refresh the page. Watch the run live.

If green ✓, success. Two videos got built. Logs are in the artifacts at the bottom of the run page.

If red ✗, click into the failed step to see the error. Common ones:
- "Missing client_secret.json" → secrets weren't pasted right; paste them again
- "LLM call failed" → Pollinations was throttling; just rerun
- "ffmpeg not found" → very rare; rerun usually fixes it

---

## Step 6 — Enable real daily runs

Once the test passes:

1. Go to **Actions** → **Run workflow**
2. Count: **5** → upload: **checked** → Run
3. After it finishes, check your YouTube channel. Videos should appear (set to private by default in `upload.py` — change `--privacy` flag if you want them public).

The schedule (`cron: '30 21 * * *'` in `.github/workflows/daily.yml`) means it runs every day at 21:30 UTC = 3:00 AM IST. To change the time, edit that file in your repo and commit. Use https://crontab.guru/ to convert your desired local time to UTC.

---

## Daily life after setup

- **Where do videos go?** Straight to your YouTube channel, scheduled by `upload.py` to space out by 3 hours.
- **How do I see what happened?** Repo → **Actions** tab on your phone. Each daily run is logged. Click any run → **autopilot-log** artifact → download for full details.
- **Can I change topics?** Yes. Edit `topics.txt` in your repo (browser is fine — click the file, click the pencil icon, edit, commit). Takes effect from the next day.
- **Can I trigger a run on demand?** Actions tab → Run workflow → done.
- **Will my credentials expire?** Google refresh tokens last indefinitely as long as the project stays in "Testing" mode. If a year passes and uploads start failing, repeat step 2 to refresh.

---

## YouTube quota reality

Google gives each Cloud project 10,000 quota units per day. Each YouTube upload costs ~1,600 units. **Maximum ~6 uploads/day per project**, which is why we target 5. If you ever want more, create a second Cloud project and rotate.

---

## What I'd do if I were you

1. Run the test with count=2, upload=off. Watch the videos. Are they at the quality you can live with?
2. If yes — enable daily, count=5, upload=on with `--privacy unlisted` (edit `upload.py` line that says `privacy_status="public"` to `"unlisted"`). Let it run for a week. Check YouTube daily but don't make them public yet.
3. After a week of acceptable quality and no policy warnings, flip privacy to public.
4. If at any point you stop being happy with quality, that's when you reconsider the $5/month upgrade to a better image API. The whole pipeline swap takes 10 minutes when that day comes.
