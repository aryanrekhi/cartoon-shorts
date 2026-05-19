# Hands-off Daily Automation — Setup Guide

This is what makes the whole thing run while you sleep.

## What you'll set up (one time, ~15 minutes)

1. Test the new pipeline on one video to make sure quality is good enough
2. Set up YouTube API access (so the script can upload for you)
3. Schedule the autopilot to run daily at a set time
4. Curate `topics.txt` with topics you actually want videos about

---

## Step 1 — Test the new quality first

Before anything automated, build ONE video with the new pipeline:

```powershell
python quickstart.py
```

Pick option **4** (auto-generate fresh script), give it a topic, choose **adult_cartoon** style. Watch the result.

The big improvement vs last time: an LLM converts each narration sentence into a proper visual prompt before image generation. Instead of asking the image AI to draw "in nineteen forty seven something fell from the sky," it now asks for "wide cinematic shot of a glowing UFO crashing into red desert at night with smoke and debris." That's where the quality comes from.

**If you're still not happy with the visuals,** stop here and tell me. We'll either tune the prompts further or have an honest conversation about whether $0 can get you what you actually want. Don't waste time setting up automation on a quality you don't like.

---

## Step 2 — YouTube API (skip if you'll upload manually)

1. Go to https://console.cloud.google.com/
2. Create a new project (call it whatever — "cartoon-shorts")
3. In the search bar, type **"YouTube Data API v3"** and click it → click **Enable**
4. Left sidebar: **APIs & Services → Credentials**
5. **Create Credentials → OAuth client ID**
   - If it asks you to configure consent screen: pick **External**, fill in name + your email, skip the optional fields, add yourself as a test user
6. Application type: **Desktop app** → Create
7. Download the JSON file → rename it to `client_secret.json` → place it in the `cartoon_shorts` folder (same folder as `upload.py`)
8. Test the connection:
   ```powershell
   python upload.py --file output\roswell_demo.mp4 --privacy private
   ```
   First run opens a browser for you to authorize. After that it remembers the token.

---

## Step 3 — Edit your topics list

Open `topics.txt` in Notepad. Each line is one topic. The autopilot picks a different one each day, rotating through. Add what fits your channel:

```
true crime cold cases that were never solved
weird animal behaviors that defy science
historical hoaxes that fooled everyone
strange laws still on the books today
```

More topics = more variety = healthier channel.

---

## Step 4 — Daily test (do this for 2–3 days BEFORE enabling auto-upload)

Run the autopilot manually first to see what it produces:

```powershell
python autopilot.py --count 5
```

This will:
- Pick today's topic from `topics.txt`
- Generate 5 fresh scripts via free LLM
- Build 5 videos (takes ~30–50 minutes total)
- Stop. Does NOT upload.

After it finishes, watch all 5 videos in the `output\` folder. Are they good enough to put on your channel? If yes, move to Step 5. If not, tell me what's wrong and we'll iterate.

---

## Step 5 — Auto-upload (only after you trust the quality)

Once you're happy:

```powershell
python autopilot.py --count 5 --upload
```

This builds the videos AND uploads them spaced 3 hours apart. They'll be set to **private** as a safety default — you can change that flag in `autopilot.py` to make them public.

**⚠️ Real talk:** I strongly recommend keeping `--privacy private` for the first week. Then "unlisted" for the second week. Only flip to "public" once you've watched what's being uploaded and you'd actually want it on your channel. YouTube's 2025–2026 enforcement actions have specifically targeted accounts that go from zero to 5 daily AI uploads with no human curation.

---

## Step 6 — Schedule it (Windows Task Scheduler)

So it runs daily without you doing anything:

1. Press **Windows key**, type **Task Scheduler**, open it
2. Right sidebar: **Create Basic Task**
3. Name: "Cartoon Shorts Daily"
4. Trigger: **Daily**, pick a time like **3:00 AM** (you don't want to be using your computer when it runs — video rendering is heavy)
5. Action: **Start a program**
6. Program/script: `python`
7. Add arguments: `autopilot.py --count 5 --upload`
8. Start in: `C:\Users\bethe\Downloads\cartoon_shorts (1)\cartoon_shorts` (the full path to your folder)
9. Finish. Right-click the task → Properties → check **"Run whether user is logged on or not"** and **"Wake the computer to run this task"**

Now it runs every day at 3 AM automatically. Wake up to 5 fresh videos uploaded throughout the day.

Logs go to `autopilot.log` in the same folder so you can see what happened overnight.

---

## Common issues & fixes

**"YouTube quota exceeded"** — YouTube API gives you 10,000 quota units/day. Each upload costs ~1,600 units, so the API caps you at ~6 uploads/day per Google Cloud project. If you hit this, create a second Cloud project and use a second `client_secret.json`.

**"All scripts failed to generate"** — Pollinations free LLM sometimes throttles. The autopilot retries each script 3 times. If it still fails, it skips. You'll just get fewer videos that day. Re-running an hour later usually works.

**"Images look the same / boring"** — Edit `CARTOON_STYLES` in `make_video.py`. Add more descriptive words. Try `--style adult_scifi` for a Rick-and-Morty-ish vibe vs `--style adult_cartoon` for the Family Guy vibe.

**"Captions still cut off"** — Open `make_video.py`, find `max_width=820` in `render_caption_text_tight`, lower it to 760 or 720. They'll auto-shrink further.

**"YouTube terminated my channel"** — I warned you. Don't auto-upload garbage. Curate. Review. Be a real person making AI-assisted content, not an AI-slop bot farmer.
