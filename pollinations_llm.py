"""
Multi-LLM failover client.

Tries providers in order: Groq -> Gemini -> Cerebras -> Pollinations (free fallback).
Each has independent rate limits, so combined effective limit is much higher.

Original name kept as 'pollinations_llm.py' to avoid changing imports elsewhere.
"""

import os
import time
import json
import random
import logging
import urllib.parse
import urllib.request
import urllib.error

log = logging.getLogger(__name__)

# ---------- Provider configurations ----------

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
]

CEREBRAS_MODELS = [
    "llama-3.3-70b",
    "llama3.1-8b",
]

POLLINATIONS_MODELS = ["openai", "mistral", "qwen-coder"]

# ---------- HTTP helper ----------

def _http_post_json(url, payload, headers, timeout=45):
    """POST JSON, return parsed response or raise."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _http_get(url, timeout=45):
    """GET text, return response text or raise."""
    req = urllib.request.Request(url, headers={"User-Agent": "cartoon-shorts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

# ---------- Provider implementations ----------

def _try_groq(prompt, system=None):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    for model in GROQ_MODELS:
        try:
            resp = _http_post_json(
                "https://api.groq.com/openai/v1/chat/completions",
                {"model": model, "messages": messages, "temperature": 0.8, "max_tokens": 800},
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )
            text = resp["choices"][0]["message"]["content"].strip()
            if text:
                log.debug(f"  groq/{model} ok ({len(text)} chars)")
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log.debug(f"  groq/{model} rate-limited")
                continue
            log.debug(f"  groq/{model} HTTP {e.code}")
        except Exception as e:
            log.debug(f"  groq/{model} {type(e).__name__}: {e}")
    return None

def _try_gemini(prompt, system=None):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    text_prompt = prompt if not system else f"{system}\n\n{prompt}"
    for model in GEMINI_MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": text_prompt}]}],
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 800},
            }
            resp = _http_post_json(
                url, payload, {"Content-Type": "application/json"}, timeout=30
            )
            text = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text:
                log.debug(f"  gemini/{model} ok ({len(text)} chars)")
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log.debug(f"  gemini/{model} rate-limited")
                continue
            log.debug(f"  gemini/{model} HTTP {e.code}")
        except Exception as e:
            log.debug(f"  gemini/{model} {type(e).__name__}: {e}")
    return None

def _try_cerebras(prompt, system=None):
    key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    for model in CEREBRAS_MODELS:
        try:
            resp = _http_post_json(
                "https://api.cerebras.ai/v1/chat/completions",
                {"model": model, "messages": messages, "temperature": 0.8, "max_tokens": 800},
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )
            text = resp["choices"][0]["message"]["content"].strip()
            if text:
                log.debug(f"  cerebras/{model} ok ({len(text)} chars)")
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log.debug(f"  cerebras/{model} rate-limited")
                continue
            log.debug(f"  cerebras/{model} HTTP {e.code}")
        except Exception as e:
            log.debug(f"  cerebras/{model} {type(e).__name__}: {e}")
    return None

def _try_pollinations(prompt, system=None):
    """Pollinations free text API - last resort fallback."""
    text_prompt = prompt if not system else f"{system}\n\n{prompt}"
    encoded = urllib.parse.quote(text_prompt[:1500])
    for model in POLLINATIONS_MODELS:
        for attempt in range(2):
            try:
                url = f"https://text.pollinations.ai/{encoded}?model={model}"
                text = _http_get(url, timeout=45).strip()
                if text and len(text) > 50:
                    log.debug(f"  pollinations/{model} ok ({len(text)} chars)")
                    return text
            except Exception as e:
                log.debug(f"  pollinations/{model} attempt {attempt+1} {type(e).__name__}")
                time.sleep(2 + random.random() * 2)
    return None

# ---------- Public API ----------

PROVIDERS = [
    ("groq", _try_groq),
    ("gemini", _try_gemini),
    ("cerebras", _try_cerebras),
    ("pollinations", _try_pollinations),
]

def ask(prompt, system=None, max_retries=2):
    """
    Try each LLM provider in sequence. Returns the first non-empty response.

    Args:
        prompt: user prompt
        system: optional system message
        max_retries: number of full passes through all providers

    Returns:
        response text, or None if all providers failed
    """
    for cycle in range(max_retries):
        if cycle > 0:
            wait = 2 + cycle * 3
            log.info(f"  retry cycle {cycle+1} in {wait}s...")
            time.sleep(wait)
        for name, fn in PROVIDERS:
            try:
                result = fn(prompt, system=system)
                if result:
                    log.debug(f"  [provider: {name}]")
                    return result
            except Exception as e:
                log.debug(f"  {name} crashed: {type(e).__name__}: {e}")
    log.warning("  All providers exhausted")
    return None


# ---------- Backward compatibility helpers ----------

def enhance_visual_prompt(narration_text, style_hint=""):
    """
    Convert narration text into a vivid visual prompt for image generation.
    Falls back to a clean version of the input if all LLMs fail.

    Args:
        narration_text: the text being narrated (one sentence usually)
        style_hint: optional cartoon style descriptor (e.g. "Family Guy style")

    Returns:
        a visual prompt string suitable for Flux/Pollinations image generation
    """
    if not narration_text or not narration_text.strip():
        return style_hint or "cinematic illustration"

    system = (
        "You are a visual prompt engineer for an AI image generator. "
        "Given a sentence of narration, write ONE concise visual prompt (max 30 words) "
        "describing what to SHOW on screen. Be vivid, specific, and visual. "
        "Focus on subject, action, setting, mood, lighting. No quotes or explanations - "
        "just the prompt itself."
    )
    user_prompt = f"Narration: {narration_text.strip()}\n\nStyle hint: {style_hint}\n\nVisual prompt:"

    result = ask(user_prompt, system=system, max_retries=1)
    if result:
        # Clean up: take first line only, strip quotes
        first_line = result.split("\n")[0].strip().strip('"').strip("'")
        if first_line:
            return first_line if not style_hint else f"{first_line}, {style_hint}"

    # Fallback: use the narration directly with style hint
    fallback = narration_text.strip()[:200]
    return f"{fallback}, {style_hint}" if style_hint else fallback


def generate_script(topic, max_seconds=55):
    """
    Generate a YouTube Short narration script for a given topic.
    Returns None if all providers fail.

    Args:
        topic: the topic to write about
        max_seconds: target video length

    Returns:
        a narration script string, or None if generation failed
    """
    word_target = int(max_seconds * 2.5)  # ~2.5 words/sec narration pace

    system = (
        "You are a viral short-form video scriptwriter. Write narration scripts that:\n"
        "- Hook the viewer in the first sentence\n"
        "- Use SHORT sentences (under 12 words each)\n"
        "- Have clear punctuation - period at end of every sentence\n"
        "- Build tension across the script\n"
        "- End with a memorable closing line\n"
        "- No emojis, no stage directions, no music cues - just spoken narration\n"
        "- Write ONLY what the narrator says aloud"
    )
    prompt = (
        f"Write a {word_target}-word narration script about: {topic}\n\n"
        f"Target length: {max_seconds} seconds of speech. "
        "Remember: short sentences with clear periods. One idea per sentence. "
        "Make it captivating from word one."
    )

    return ask(prompt, system=system, max_retries=2)


# ---------- Self-test ----------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    test_keys = {
        "GROQ_API_KEY": "present" if os.environ.get("GROQ_API_KEY") else "MISSING",
        "GEMINI_API_KEY": "present" if os.environ.get("GEMINI_API_KEY") else "MISSING",
        "CEREBRAS_API_KEY": "present" if os.environ.get("CEREBRAS_API_KEY") else "MISSING",
    }
    print("API keys:")
    for k, v in test_keys.items():
        print(f"  {k}: {v}")

    print("\n=== Test 1: generate_script ===")
    script = generate_script("a haunted vending machine in a Tokyo subway", max_seconds=45)
    print(f"\n{script}\n")

    print("\n=== Test 2: enhance_visual_prompt ===")
    vp = enhance_visual_prompt(
        "The vending machine glowed an unnatural blue at 3am.",
        style_hint="Family Guy adult cartoon style",
    )
    print(f"\n{vp}\n")
