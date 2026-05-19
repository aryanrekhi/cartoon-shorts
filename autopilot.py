"""
AUTOPILOT — the full daily pipeline.
====================================
One command. Runs unattended. Schedule it daily via Windows Task Scheduler.

It does:
  1. Picks today's topic from topics.txt (rotates by date)
  2. Generates N fresh scripts on that topic (free LLM)
  3. Builds N videos with LLM-enhanced visual prompts
  4. Optionally uploads them to YouTube, spaced out through the day

USAGE:
    python autopilot.py                      # generate + build only (recommended at first)
    python autopilot.py --upload             # also upload to YouTube
    python autopilot.py --count 3            # change number of videos
    python autopilot.py --style adult_scifi  # change style for today
    python autopilot.py --topic "deep sea mysteries"  # override topic
    python autopilot.py --no-llm-scripts     # use scripts already in scripts/ folder

SAFETY:
    Until you've watched at least 5 generated videos and are happy with the quality,
    DO NOT use --upload. YouTube terminates channels that mass-upload low-quality AI
    content. The safer pattern is: autopilot generates, you spend 5 minutes reviewing
    them on your phone before bed, then run upload.py the next morning.
"""

import argparse
import asyncio
import datetime
import json
import logging
import subprocess
import sys
from pathlib import Path

from make_video import build_video, CARTOON_STYLES, VOICES
from pollinations_llm import generate_script


def setup_logging():
    log_path = Path("autopilot.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("autopilot")


def get_todays_topic(topics_file="topics.txt", override=""):
    if override:
        return override
    p = Path(topics_file)
    if not p.exists():
        return "unexplained mysteries"
    topics = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if not topics:
        return "unexplained mysteries"
    day_index = datetime.date.today().toordinal()
    return topics[day_index % len(topics)]


async def run_autopilot(args, log):
    topic = get_todays_topic(override=args.topic)
    today_str = datetime.date.today().isoformat()

    log.info(f"=== Autopilot starting — date={today_str} topic='{topic}' count={args.count} style={args.style} ===")

    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    output_dir = Path("output")
    temp_dir = Path("temp")

    # ─── Step 1: scripts ──────────────────────────────────────────────────────
    scripts_to_use = []
    if args.no_llm_scripts:
        log.info("Using existing scripts in scripts/ folder")
        for f in sorted(scripts_dir.glob("*.txt"))[: args.count]:
            scripts_to_use.append((f.stem, f.read_text(encoding="utf-8").strip()))
    else:
        log.info(f"Generating {args.count} scripts via free LLM...")
        for i in range(args.count):
            log.info(f"  Script {i + 1}/{args.count}...")
            attempts = 0
            script = None
            while attempts < 3 and script is None:
                attempts += 1
                script = generate_script(
                    topic, length_seconds=args.length,
                    attempt_label=f"(variant {i + 1}, attempt {attempts})"
                )
                if not script:
                    log.warning(f"  attempt {attempts} failed, retrying...")
            if not script:
                log.error(f"  Script {i + 1} failed after 3 attempts. Skipping.")
                continue
            slug = f"{today_str}_{i + 1:02d}"
            (scripts_dir / f"{slug}.txt").write_text(script, encoding="utf-8")
            scripts_to_use.append((slug, script))
            log.info(f"  ✓ saved {slug}.txt ({len(script)} chars)")

    if not scripts_to_use:
        log.error("No scripts available. Aborting.")
        return

    # ─── Step 2: videos ───────────────────────────────────────────────────────
    log.info(f"Building {len(scripts_to_use)} videos...")
    built = []
    for slug, script in scripts_to_use:
        out_file = output_dir / f"{slug}.mp4"
        if out_file.exists() and not args.overwrite:
            log.info(f"  {slug}.mp4 already exists, skipping (use --overwrite to force)")
            built.append(out_file)
            continue
        log.info(f"  Building {slug}...")
        try:
            result = await build_video(
                script=script, name=slug, style=args.style, voice=args.voice,
                output_dir=output_dir, temp_dir=temp_dir, topic_hint=topic,
                use_llm_prompts=True,
            )
            if result:
                built.append(result)
                # Write sidecar metadata for upload.py
                meta = {
                    "title": _make_title(script, topic),
                    "description": _make_description(script, topic),
                    "tags": _make_tags(topic),
                }
                out_file.with_suffix(".json").write_text(
                    json.dumps(meta, indent=2), encoding="utf-8"
                )
        except Exception as exc:
            log.exception(f"  ❌  {slug} failed: {exc}")

    log.info(f"Built {len(built)}/{len(scripts_to_use)} videos")

    # ─── Step 3: upload (optional) ────────────────────────────────────────────
    if args.upload and built:
        log.info("Uploading to YouTube...")
        try:
            subprocess.run(
                [sys.executable, "upload.py", "--batch",
                 "--schedule", args.schedule, "--move-uploaded"],
                check=True
            )
        except subprocess.CalledProcessError as exc:
            log.error(f"Upload failed: {exc}")
    elif built:
        log.info("Skipping upload (use --upload to enable).")
        log.info("To upload manually:  python upload.py --batch --schedule 3hours --move-uploaded")

    log.info("=== Autopilot done ===\n")


def _make_title(script, topic):
    first_sentence = script.split(".")[0].strip()
    if len(first_sentence) > 70:
        first_sentence = first_sentence[:70].rsplit(" ", 1)[0]
    return f"{first_sentence} #shorts"[:100]


def _make_description(script, topic):
    first = script.split(".")[0].strip()
    return f"{first}.\n\n#shorts #{topic.replace(' ', '')} #story #mystery #viral"


def _make_tags(topic):
    base = ["shorts", "youtubeshorts", "story", "mystery", "viral", "fyp"]
    base += [w.strip() for w in topic.split() if len(w) > 2]
    return base[:15]


def main():
    p = argparse.ArgumentParser(description="Cartoon Shorts AUTOPILOT")
    p.add_argument("--count", type=int, default=5, help="How many videos to build")
    p.add_argument("--length", type=int, default=40, help="Target seconds per script")
    p.add_argument("--style", default="adult_cartoon", choices=list(CARTOON_STYLES))
    p.add_argument("--voice", default="narrator", choices=list(VOICES))
    p.add_argument("--topic", default="", help="Override today's topic")
    p.add_argument("--upload", action="store_true", help="Auto-upload after building (DANGEROUS — read warning)")
    p.add_argument("--schedule", default="3hours", help="Spacing between uploads")
    p.add_argument("--overwrite", action="store_true", help="Rebuild even if .mp4 exists")
    p.add_argument("--no-llm-scripts", action="store_true", help="Use existing scripts/ files instead of generating fresh")
    args = p.parse_args()

    log = setup_logging()
    try:
        asyncio.run(run_autopilot(args, log))
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
    except Exception:
        log.exception("Autopilot crashed")


if __name__ == "__main__":
    main()
