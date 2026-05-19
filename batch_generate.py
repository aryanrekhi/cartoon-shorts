"""
Batch Video Generator
=====================
Reads all scripts from scripts/ folder and builds a video for each.
Run this once a day (or via cron / Windows Task Scheduler) to produce
multiple Shorts in one go.

USAGE:
    python batch_generate.py --style pixar --voice narrator
    python batch_generate.py --count 5            # only build first 5 scripts
    python batch_generate.py --delete-after       # delete scripts after building

Folder layout expected:
    scripts/
        001_roswell_mystery.txt
        002_haunted_lighthouse.txt
        ...
"""

import argparse
import asyncio
from pathlib import Path

from make_video import build_video, CARTOON_STYLES, VOICES


async def run_batch(args):
    scripts_dir = Path(args.scripts_dir)
    output_dir = Path(args.output_dir)
    temp_dir = Path(args.temp_dir)

    files = sorted(scripts_dir.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {scripts_dir}")
        return

    if args.count:
        files = files[: args.count]

    print(f"Found {len(files)} scripts to process.\n")

    for i, file in enumerate(files, 1):
        name = file.stem
        out_file = output_dir / f"{name}.mp4"
        if out_file.exists() and not args.overwrite:
            print(f"[{i}/{len(files)}] {name} — already exists, skipping")
            continue

        print(f"\n{'─' * 60}\n[{i}/{len(files)}] Building: {name}\n{'─' * 60}")
        script_text = file.read_text(encoding="utf-8").strip()
        if not script_text:
            print("  empty file, skipping")
            continue

        try:
            await build_video(
                script=script_text,
                name=name,
                style=args.style,
                voice=args.voice,
                topic_hint=args.topic,
                output_dir=output_dir,
                temp_dir=temp_dir,
                whisper_size=args.whisper,
            )
            if args.delete_after:
                file.unlink()
                print(f"  ✓ deleted source script {file.name}")
        except Exception as exc:
            print(f"  ❌ failed: {exc}")
            continue

    print(f"\n🎉  Batch complete.")


def main():
    p = argparse.ArgumentParser(description="Batch generate Shorts from a scripts folder")
    p.add_argument("--scripts-dir", default="scripts")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--temp-dir", default="temp")
    p.add_argument("--style", default="pixar", choices=list(CARTOON_STYLES))
    p.add_argument("--voice", default="narrator", choices=list(VOICES))
    p.add_argument("--topic", default="")
    p.add_argument("--count", type=int, default=0, help="Only process N scripts (0 = all)")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--delete-after", action="store_true", help="Delete script after building")
    p.add_argument("--whisper", default="base", choices=["tiny", "base", "small", "medium"])
    args = p.parse_args()

    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
