"""
Free LLM helper using Pollinations text API.
Used to:
  • Convert narration scenes into proper visual prompts for image generation
  • Auto-generate fresh YouTube Shorts scripts on a topic

Includes polite rate-limiting so we don't get throttled by the free service.
"""

import re
import time
from urllib.parse import quote_plus

import requests

TEXT_URL = "https://text.pollinations.ai/{prompt}?model={model}&private=true"

# Rate limiting — wait at least this long between any two LLM calls
MIN_DELAY_BETWEEN_CALLS = 4.0  # seconds
_last_call_time = [0.0]  # mutable list so we can track across function calls


def _wait_for_rate_limit():
    """Make sure we don't hammer Pollinations faster than it tolerates."""
    elapsed = time.time() - _last_call_time[0]
    if elapsed < MIN_DELAY_BETWEEN_CALLS:
        sleep_for = MIN_DELAY_BETWEEN_CALLS - elapsed
        time.sleep(sleep_for)
    _last_call_time[0] = time.time()


def call_llm(prompt, model="openai", timeout=60, retries=4):
    """Call Pollinations free LLM. Returns response text or None on failure.
    Uses exponential backoff on retries to be polite to the free service."""
    encoded = quote_plus(prompt)
    url = TEXT_URL.format(prompt=encoded, model=model)
    for attempt in range(retries + 1):
        _wait_for_rate_limit()
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
            if r.status_code == 429:
                # Rate limited — wait longer
                wait = 10 * (attempt + 1)
                print(f"    (rate limited, waiting {wait}s)", flush=True)
                time.sleep(wait)
                continue
        except Exception as e:
            if attempt == retries:
                print(f"    (LLM call failed: {e})", flush=True)
        # Exponential backoff before next attempt
        wait = 3 * (2 ** attempt)
        time.sleep(min(wait, 30))
    return None


def enhance_visual_prompt(scene_text, topic_hint=""):
    """Convert narration into a vivid visual prompt for image generation."""
    instruction = (
        "You convert narration text into a single vivid visual scene description "
        "for an AI image generator. Output ONLY one sentence, max 35 words. "
        "Include: main subject, action, setting, mood, and lighting. "
        "Be concrete and visual. No style words, no quotes, no preamble.\n\n"
        f"Topic context: {topic_hint or 'general storytelling'}\n"
        f"Narration: {scene_text}\n\n"
        "Visual scene:"
    )
    result = call_llm(instruction)
    if not result:
        return scene_text
    result = result.strip().strip('"\'').strip()
    result = re.sub(
        r"^(visual scene|visual prompt|scene|prompt|description|image)[\s:]+",
        "", result, flags=re.IGNORECASE
    )
    result = result.split("\n")[0].strip()
    if len(result) > 220:
        result = result[:220]
    return result or scene_text


def generate_script(topic, length_seconds=40, attempt_label=""):
    """Generate one fresh YouTube Shorts narration script on a topic."""
    target_words = int(length_seconds * 2.4)
    instruction = (
        f"Write ONE original YouTube Shorts narration about: {topic}. "
        f"Length: roughly {target_words} words. "
        "Hook in first sentence. Build curiosity. End on a question. "
        "Spell out numbers as words. Output ONLY the narration body, "
        "no title, no markdown, no preamble, no quotation marks.\n"
        f"{attempt_label}"
    ).strip()
    result = call_llm(instruction, timeout=90)
    if not result:
        return None
    result = re.sub(
        r"^(here[\'s]+ (is|the|a)|sure[,!]?|narration[\s:]+|script[\s:]+|title[\s:]+[^\n]*\n)",
        "", result.strip(), flags=re.IGNORECASE
    ).strip()
    result = result.strip('"\'').strip()
    if len(result) < 100 or len(result) > 1500:
        return None
    return result
