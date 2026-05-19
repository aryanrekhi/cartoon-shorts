"""
Interactive quickstart — no command-line flags needed.
Run:    python quickstart.py
"""

import asyncio
from pathlib import Path

from make_video import build_video, CARTOON_STYLES, VOICES


def menu(title, options, default):
    print(f"\n{title}")
    for i, opt in enumerate(options, 1):
        marker = "←" if opt == default else " "
        print(f"  {i:2}. {opt:<14} {marker}")
    raw = input(f"Pick a number (or Enter for {default}): ").strip()
    if not raw:
        return default
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    except ValueError:
        pass
    return default


def get_script():
    print("\n" + "─" * 60)
    print("📝  SCRIPT")
    print("─" * 60)
    print("Options:")
    print("  1. Use the included Roswell sample")
    print("  2. Use a file from scripts/ folder")
    print("  3. Paste a new script here")
    print("  4. Auto-generate ONE fresh script via free LLM")
    choice = input("Pick 1 / 2 / 3 / 4 [1]: ").strip() or "1"

    if choice == "1":
        return Path("scripts/001_roswell.txt").read_text(encoding="utf-8").strip(), "roswell_demo"

    if choice == "2":
        files = sorted(Path("scripts").glob("*.txt"))
        if not files:
            print("  (No scripts found, using sample)")
            return Path("scripts/001_roswell.txt").read_text(encoding="utf-8").strip(), "roswell_demo"
        print()
        for i, f in enumerate(files, 1):
            print(f"  {i}. {f.name}")
        raw = input("Pick a number [1]: ").strip() or "1"
        try:
            file = files[int(raw) - 1]
        except (ValueError, IndexError):
            file = files[0]
        return file.read_text(encoding="utf-8").strip(), file.stem

    if choice == "4":
        from pollinations_llm import generate_script
        topic = input("\nWhat topic? (e.g. 'haunted lighthouses'): ").strip() or "unexplained mysteries"
        print("Generating script via free LLM... (about 20s)")
        script = generate_script(topic, length_seconds=40)
        if not script:
            print("LLM failed, falling back to Roswell sample.")
            return Path("scripts/001_roswell.txt").read_text(encoding="utf-8").strip(), "roswell_demo"
        slug = topic.replace(" ", "_").lower()[:30]
        return script, slug

    # paste mode
    print("\nPaste your script. When done, type a single dot '.' on a new line and Enter.")
    print("─" * 60)
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    script = " ".join(lines).strip()
    if not script:
        print("Empty script — using sample.")
        return Path("scripts/001_roswell.txt").read_text(encoding="utf-8").strip(), "roswell_demo"
    name = input("Filename for this video (no extension): ").strip() or "my_video"
    return script, name


def main():
    print("\n" + "=" * 60)
    print("   🎬   CARTOON SHORTS — QUICKSTART")
    print("=" * 60)

    script, name = get_script()
    print(f"\n✓  Loaded script ({len(script)} chars), output name: {name}.mp4")

    style = menu("🎨  STYLE", list(CARTOON_STYLES.keys()), "adult_cartoon")
    voice = menu("🎙️   VOICE",  list(VOICES.keys()),         "narrator")
    topic = input("\n💡 Optional topic hint (helps the AI; press Enter to skip): ").strip()

    print("\n" + "─" * 60)
    print(f"Building:  {name}.mp4   |   style={style}   |   voice={voice}")
    print("This takes 4–10 minutes (best-of-2 image gen takes a bit longer).")
    print("─" * 60 + "\n")

    asyncio.run(build_video(
        script=script, name=name, style=style, voice=voice,
        output_dir=Path("output"), temp_dir=Path("temp"),
        topic_hint=topic,
    ))

    print("\n" + "=" * 60)
    print(f"  Open it:  output\\{name}.mp4")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
