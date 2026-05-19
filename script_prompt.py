"""
Script Writer Helper
====================
Generates the prompt you paste into ChatGPT / Claude / Gemini to mass-produce
scripts for a week's worth of Shorts in one go.

USAGE:
    python script_prompt.py --topic "unsolved mysteries" --count 7
    python script_prompt.py --topic "wild west outlaws" --count 5 --length 60

Output is printed to terminal — copy it into any free LLM, paste the reply
back into scripts/ as separate .txt files (one per script), then run
batch_generate.py.
"""

import argparse


TEMPLATE = """You are a viral YouTube Shorts scriptwriter. Write {count} short narration scripts about: {topic}.

REQUIREMENTS for each script:
- Length: aim for roughly {length} seconds when narrated (about {words} words)
- Hook in the first sentence — make people stop scrolling
- Use simple, punchy sentences, present tense where possible
- Build tension or curiosity — don't reveal the payoff until the end
- End on a question or unsettling statement that drives comments
- Plain spoken English only — no markdown, no stage directions, no [SFX] cues
- Spell out numbers as words (nineteen forty seven, not 1947) — TTS reads better

FORMAT (extremely important):
Separate each script with exactly this line on its own:
===

For each script, write a title on the first line, then the script body. Like:

The Lighthouse That Vanished
She lit the lamp for thirty years...
===
The Roswell Cover-Up
In nineteen forty seven, something fell from the sky...
===

Now write {count} scripts about: {topic}
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=True, help="e.g. 'true crime', 'cold cases', 'haunted places'")
    p.add_argument("--count", type=int, default=7)
    p.add_argument("--length", type=int, default=45, help="Target seconds per video")
    args = p.parse_args()

    words = int(args.length * 2.4)  # ~2.4 words/sec at TTS rate
    prompt = TEMPLATE.format(
        topic=args.topic, count=args.count, length=args.length, words=words
    )
    print(prompt)
    print("\n" + "─" * 60)
    print("⬆️  Copy everything above and paste it into any free LLM chat.")
    print("Then save each script to scripts/NNN_slug.txt (numbered, lowercase).")
    print("─" * 60)


if __name__ == "__main__":
    main()
