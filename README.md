# Cartoon YouTube Shorts Generator

A Python pipeline that builds faceless cartoon-style YouTube Shorts automatically — AI cartoon images, natural TTS narration, animated captions, all assembled into a finished vertical video ready to upload.

## What it actually does (and doesn't)

✅ **Does:** Generates polished vertical Shorts with AI cartoon imagery, professional TTS voiceover, word-by-word captions, and Ken Burns motion — all for free.

❌ **Doesn't:** Generate full Pixar-style character animation with lip-sync. That tech exists (Sora, Veo) but isn't free or unlimited. This tool produces high-quality *narrated* content with cartoon imagery — perfect for stories, true crime, mysteries, history, motivational content.

## What's free

- **TTS voiceover** — Microsoft Edge TTS, unlimited, no API key, very natural voices
- **Cartoon images** — Pollinations.ai (flux model), unlimited, no API key
- **Captions** — OpenAI Whisper running locally on your machine, free forever
- **Video assembly** — moviepy + ffmpeg, free
- **Upload** — YouTube Data API, free (10,000 quota units/day, an upload costs ~1,600 units → up to 6 uploads/day per project; create a 2nd Google Cloud project if you need more)

## One-time setup

### 1. Install Python 3.10+ and ffmpeg
- **Windows:** Install Python from python.org; install ffmpeg via `winget install ffmpeg` or download from ffmpeg.org and add to PATH
- **Mac:** `brew install python ffmpeg`
- **Linux:** `sudo apt install python3 python3-pip ffmpeg`

### 2. Install Python dependencies
```bash
cd cartoon_shorts
pip install -r requirements.txt
```

First run will also auto-download a ~150MB Whisper model.

### 3. Test with the included sample
```bash
python make_video.py --script scripts/001_roswell.txt --name test_video --style pixar --voice narrator
```

If everything works, you'll get `output/test_video.mp4` — a vertical Short ready to upload.

## Daily workflow (the actual automation)

### Step 1 — Generate a week of scripts in one sitting (5 minutes)
```bash
python script_prompt.py --topic "unsolved mysteries" --count 7
```
This prints a ready-made prompt. Paste it into ChatGPT, Claude, or Gemini (free tiers all work). It will give you 7 scripts separated by `===`. Split each into its own file under `scripts/` numbered like `003_*.txt`, `004_*.txt`, etc.

### Step 2 — Batch-build all videos (runs unattended)
```bash
python batch_generate.py --style pixar --voice narrator
```
This takes 3–8 minutes per video. Walk away. Come back to a folder of finished `.mp4` files in `output/`.

### Step 3 — Auto-upload to YouTube
First time only: set up OAuth credentials (see comments at top of `upload.py`). After that:
```bash
python upload.py --batch --schedule 4hours --move-uploaded
```
This schedules uploads 4 hours apart so they post throughout the day. You can also leave videos private/unlisted to review them first.

### Step 4 — Schedule it to run automatically
- **Windows:** Task Scheduler → run `batch_generate.py` once daily, then `upload.py --batch` after
- **Mac/Linux:** cron job, e.g. `0 6 * * * cd /path/to/cartoon_shorts && python batch_generate.py && python upload.py --batch`

## Styles available
`pixar` `anime` `cartoon` `disney` `comic` `fantasy` `noir`

## Voices available
`narrator` (deep dramatic), `male_us`, `female_us`, `male_uk`, `female_uk`, `energetic`, `deep_male`, `warm_male`, `young_male`

## Tuning quality

- For sharper images: edit `make_video.py` and lengthen the style suffix in `CARTOON_STYLES`
- For longer captions: change `per_group=3` to `per_group=4` in `build_video()`
- For different aspect (1920x1080 horizontal): change `WIDTH, HEIGHT` constants at top of `make_video.py`
- For higher quality Whisper captions: pass `--whisper small` or `--whisper medium` (slower, more accurate)

## Folder layout
```
cartoon_shorts/
├── make_video.py          # core: builds one video
├── batch_generate.py      # builds all scripts in scripts/
├── upload.py              # uploads all videos in output/
├── script_prompt.py       # generates the LLM prompt for bulk script writing
├── requirements.txt
├── scripts/               # put your .txt scripts here
│   ├── 001_roswell.txt
│   └── 002_lighthouse.txt
├── output/                # finished .mp4 files appear here
└── temp/                  # working files; safe to delete anytime
```

## Realistic expectations

- **Time per video:** 3–8 minutes on a normal laptop
- **Quality:** Good enough to monetize — but you need to put effort into hooks, niches, and thumbnails. The tool handles production; you handle strategy.
- **Channel growth:** YouTube needs 1,000 subs + 4,000 watch hours (long-form) or 10M Shorts views (90-day rolling) to monetize. Realistic timeline: 6–12 months of daily consistent uploads.
- **Faceless channel risks:** YouTube has tightened rules against "low-effort" or fully AI content. Pick niches where you add real value (good scripts, interesting topics, real research) — pure "AI slop" channels are being demonetized in waves. Treat AI as production help, not a replacement for thinking.

## Sidecar metadata (optional)
For each `output/video.mp4`, you can drop a `output/video.json` next to it:
```json
{
  "title": "The Lighthouse That Vanished",
  "description": "On a remote Scottish island...\n\n#shorts #mystery",
  "tags": ["shorts", "mystery", "haunted", "scotland"]
}
```
`upload.py` will use it automatically.
