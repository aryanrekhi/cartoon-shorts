"""
Free LLM helper using Pollinations text API.
Used to:
  • Convert narration scenes into proper visual prompts for image generation
  • Auto-generate fresh YouTube Shorts scripts on a topic
"""

import re
import time
from urllib.parse import quote_plus

import requests

TEXT_URL = "https://text.pollinations.ai/{prompt}?model={model}&private=true"


def call_llm(prompt: str, model: str = "openai", timeout: int = 60, retries: int = 2) -> str | None:
    """Call Pollinations free LLM. Returns response text or None on failure."""
    encoded = quote_plus(prompt)
    url = TEXT_URL.format(prompt=encoded, model=model)
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception as e:
            if attempt == retries:
                print(f"    (LLM call failed: {e})")
            time.sleep(2)
    return None


def enhance_visual_prompt(scene_text: str, topic_hint: str = "") -> str:
    """Convert narration into a vivid, concrete visual prompt for image generation.

    This is the single biggest quality lever in the pipeline — bad raw narration
    becomes specific 'wide shot of X doing Y in Z with mood W' which the image
    model can actually render.
    """
    instruction = (
        "You convert narration text into a single vivid visual scene description "
        "for an AI image generator. Output ONLY one sentence, max 35 words. "
        "Include: main subject, action, setting/location, mood, and lighting. "
        "Be concrete and visual — describe what we SEE, not what's said. "
        "Do not include style words, quotes, or preamble. Just the description.\n\n"
        f"Topic context: {topic_hint or 'general storytelling'}\n"
        f"Narration: {scene_text}\n\n"
        "Visual scene:"
    )
    result = call_llm(instruction)
    if not result:
        return scene_text  # fall back to raw narration
    # Cleanup: strip quotes, prefixes, multi-line junk
    result = result.strip().strip('"\'').strip()
    result = re.sub(
        r"^(visual scene|visual prompt|scene|prompt|description|image)[\s:]+",
        "", result, flags=re.IGNORECASE
    )
    # Keep only first sentence/paragraph
    result = result.split("\n")[0].strip()
    # Cap length so we don't blow up the URL
    if len(result) > 220:
        result = result[:220]
    return result or scene_text


def generate_script(topic: str, length_seconds: int = 40, attempt_label: str = "") -> str | None:
    """Generate one fresh YouTube Shorts narration script on a topic."""
    target_words = int(length_seconds * 2.4)
    instruction = (
        f"Write ONE original YouTube Shorts narration about: {topic}. "
        f"Length: roughly {target_words} words (about {length_seconds} seconds spoken). "
        "Style: hook in first sentence that makes people stop scrolling, build tension "
        "or curiosity, end on a question or unsettling statement that drives comments. "
        "Use simple punchy sentences. Spell out numbers as words (nineteen forty seven, "
        "not 1947). Output ONLY the narration body — no title, no markdown, no stage "
        "directions, no 'here is the script' preamble, no quotation marks. Just plain "
        "spoken narration text. Avoid generic openings like 'Did you know'.\n"
        f"{attempt_label}"
    ).strip()
    result = call_llm(instruction, timeout=90)
    if not result:
        return None
    # Strip common LLM preamble
    result = re.sub(
        r"^(here[\'s]+ (is|the|a)|sure[,!]?|narration[\s:]+|script[\s:]+|title[\s:]+[^\n]*\n)",
        "", result.strip(), flags=re.IGNORECASE
    ).strip()
    result = result.strip('"\'').strip()
    # Reject obvious garbage
    if len(result) < 100 or len(result) > 1500:
        return None
    return result
