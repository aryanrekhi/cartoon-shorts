"""
Cartoon YouTube Shorts Generator (Quality Edition)
===================================================
Now with:
  • LLM-enhanced visual prompts (free, via Pollinations text API) — biggest quality jump
  • Best-of-2 image selection per scene
  • Auto-shrinking captions that never get cut off
  • Adult-animation styles tuned for "Family Guy / Rick and Morty" vibe
  • Quality threshold — re-generates if image looks broken
  • Smooth crossfades, varied Ken Burns motion, pop-in captions, vignette
"""

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import edge_tts
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, ImageClip, VideoClip,
)

from pollinations_llm import enhance_visual_prompt

WIDTH, HEIGHT = 1080, 1920

VOICES = {
    "narrator":   "en-US-ChristopherNeural",
    "male_us":    "en-US-GuyNeural",
    "female_us":  "en-US-AriaNeural",
    "male_uk":    "en-GB-RyanNeural",
    "female_uk":  "en-GB-SoniaNeural",
    "energetic":  "en-US-JennyNeural",
    "deep_male":  "en-US-DavisNeural",
    "warm_male":  "en-US-TonyNeural",
    "young_male": "en-US-BrandonNeural",
}

CARTOON_STYLES = {
    # The two you asked for — adult animation styles, no copyrighted characters
    "adult_cartoon": (
        "adult animated sitcom art style, bold thick black outlines, flat vibrant saturated colors, "
        "2D digital animation, exaggerated character designs with rounded shapes, suburban or domestic setting, "
        "sharp clean line work, modern adult cartoon television aesthetic, dynamic composition, "
        "professional cel animation quality, comedic exaggerated expressions"
    ),
    "adult_scifi": (
        "adult animated sci-fi cartoon art style, bold black outlines, flat vibrant colors, 2D animation, "
        "surreal sci-fi setting, dimension-hopping aesthetic, exaggerated cartoon character proportions, "
        "vibrant alien color palette, dynamic angles, comedic sci-fi style, retro-future vibes, "
        "sharp graphic shapes, adult swim animation feel"
    ),
    # The earlier ones, kept
    "pixar":       "3D Pixar animation style, vibrant colors, expressive characters, soft cinematic lighting, highly detailed, professional render",
    "anime":       "anime style, Studio Ghibli inspired, vibrant colors, detailed backgrounds, painterly",
    "cartoon":     "modern 2D cartoon style, bold clean outlines, vibrant flat colors, expressive, fun",
    "disney":      "Disney animation style, magical atmosphere, vibrant colors, painterly, cinematic lighting",
    "comic":       "comic book illustration style, bold ink lines, dynamic composition, vibrant colors, cel shaded",
    "noir":        "stylized noir illustration, dramatic shadows, moody atmosphere, painted cartoon style",
    "claymation":  "stop motion claymation style, soft clay textures, charming and warm, handcrafted look",
}

QUALITY_SUFFIX = "highly detailed, sharp focus, professional, masterpiece quality, vivid colors, dramatic composition"

POLLINATIONS_URL = (
    "https://image.pollinations.ai/prompt/{prompt}"
    "?model=flux&width={w}&height={h}&nologo=true&enhance=true&seed={seed}"
)


# ─── Script parsing ───────────────────────────────────────────────────────────

def split_script_into_scenes(script, target_chars=100):
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    scenes, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) < target_chars:
            current = (current + " " + sent).strip()
        else:
            if current:
                scenes.append(current)
            current = sent
    if current:
        scenes.append(current)
    return scenes


# ─── TTS ──────────────────────────────────────────────────────────────────────

async def generate_tts(text, output_path, voice, rate="+6%"):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output_path))


# ─── Image generation with LLM-enhanced prompts + best-of-2 ───────────────────

def _request_image(full_prompt, seed, width, height, timeout=120):
    url = POLLINATIONS_URL.format(
        prompt=quote_plus(full_prompt), w=width, h=height, seed=seed
    )
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and len(r.content) > 30000:  # quality floor
            return r.content
    except Exception as exc:
        print(f"      (attempt failed: {exc})")
    return None


def generate_image_best_of_n(visual_prompt, style, output_path,
                              base_seed, width=1080, height=1920, n=2):
    """Generate N candidates, save the best one (largest file = most detail)."""
    style_suffix = CARTOON_STYLES.get(style, CARTOON_STYLES["adult_cartoon"])
    full_prompt = f"{visual_prompt}. Style: {style_suffix}. {QUALITY_SUFFIX}"

    best_bytes = None
    best_size = 0
    for i in range(n):
        seed = (base_seed + i * 91) % 1_000_000
        for retry in range(2):
            data = _request_image(full_prompt, seed, width, height)
            if data:
                if len(data) > best_size:
                    best_bytes = data
                    best_size = len(data)
                break
            time.sleep(2)

    if best_bytes is None:
        return False
    with open(output_path, "wb") as f:
        f.write(best_bytes)
    return True


# ─── Captions (Whisper) ───────────────────────────────────────────────────────

def transcribe_with_whisper(audio_path, model_size="base"):
    import whisper
    print(f"  Loading Whisper model ({model_size})...")
    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), word_timestamps=True, verbose=False)
    words = []
    for segment in result["segments"]:
        for w in segment.get("words", []):
            words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})
    return words


def group_words(words, per_group=3):
    groups = []
    for i in range(0, len(words), per_group):
        chunk = words[i:i + per_group]
        if not chunk:
            continue
        groups.append({
            "text": " ".join(w["word"] for w in chunk),
            "start": chunk[0]["start"],
            "end": chunk[-1]["end"],
        })
    return groups


# ─── Caption rendering (auto-shrinks to fit, no more cutoff) ──────────────────

def find_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\impact.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_caption_text_tight(text, max_width=820, max_font=92, min_font=46):
    """Render caption on tight-cropped transparent canvas, auto-shrinking font
    to fit within max_width (so the pop animation stays inside the screen)."""
    text_up = text.upper().strip()
    if not text_up:
        return np.zeros((10, 10, 4), dtype=np.uint8)

    tmp = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(tmp)
    stroke_w = 7

    font_size = max_font
    font = find_font(font_size)
    bbox = draw.textbbox((0, 0), text_up, font=font, stroke_width=stroke_w)
    tw = bbox[2] - bbox[0]
    while tw > max_width and font_size > min_font:
        font_size -= 4
        font = find_font(font_size)
        bbox = draw.textbbox((0, 0), text_up, font=font, stroke_width=stroke_w)
        tw = bbox[2] - bbox[0]

    th = bbox[3] - bbox[1]
    pad = 25
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text(
        (pad - bbox[0], pad - bbox[1]),
        text_up, font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255),
    )
    return np.array(img)


def make_animated_caption(text, start, end, video_w, video_h):
    """Caption with snappy pop-in animation (kept slightly under-scaled so
    even at peak overshoot it stays inside the screen)."""
    frame_array = render_caption_text_tight(text)
    fh = frame_array.shape[0]
    duration = max(end - start, 0.01)

    pop_dur = min(0.18, duration * 0.4)
    overshoot_point = pop_dur * 0.6

    def scale_fn(t):
        if t < overshoot_point:
            return 0.60 + 0.55 * (t / overshoot_point)            # 0.60 → 1.15
        elif t < pop_dur:
            return 1.15 - 0.15 * ((t - overshoot_point) / (pop_dur - overshoot_point))
        return 1.0

    clip = ImageClip(frame_array, transparent=True).set_duration(duration)
    clip = clip.resize(scale_fn)

    target_center_y = int(video_h * 0.78)

    def pos_fn(t):
        s = scale_fn(t)
        return ("center", int(target_center_y - s * fh / 2))

    return clip.set_position(pos_fn).set_start(start)


# ─── Ken Burns motion ─────────────────────────────────────────────────────────

def fit_image_to_canvas(img_path, canvas_w, canvas_h):
    img = Image.open(img_path).convert("RGB")
    iw, ih = img.size
    target_ratio = canvas_w / canvas_h
    img_ratio = iw / ih
    if img_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        offset = (iw - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, ih))
    else:
        new_h = int(iw / target_ratio)
        offset = (ih - new_h) // 2
        img = img.crop((0, offset, iw, offset + new_h))
    img = img.resize((canvas_w, canvas_h), Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(1.18)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    return np.array(img)


def make_ken_burns_clip(img_path, duration, w, h, motion="zoom_in"):
    base = fit_image_to_canvas(img_path, w, h)
    base_img = Image.fromarray(base)

    def make_frame(t):
        progress = min(t / max(duration, 0.01), 1.0)
        if motion == "zoom_in":
            scale, off_x, off_y = 1.00 + 0.12 * progress, 0.0, 0.0
        elif motion == "zoom_out":
            scale, off_x, off_y = 1.12 - 0.12 * progress, 0.0, 0.0
        elif motion == "pan_right":
            scale, off_x, off_y = 1.10, -0.04 + 0.08 * progress, 0.0
        elif motion == "pan_left":
            scale, off_x, off_y = 1.10, 0.04 - 0.08 * progress, 0.0
        else:
            scale, off_x, off_y = 1.00 + 0.06 * progress, 0.0, 0.0
        new_w, new_h = int(w * scale), int(h * scale)
        scaled = base_img.resize((new_w, new_h), Image.LANCZOS)
        center_x = new_w // 2 + int(off_x * new_w * 0.5)
        center_y = new_h // 2 + int(off_y * new_h * 0.5)
        left = max(0, min(new_w - w, center_x - w // 2))
        top = max(0, min(new_h - h, center_y - h // 2))
        return np.array(scaled.crop((left, top, left + w, top + h)))

    return VideoClip(make_frame, duration=duration)


def make_vignette_clip(w, h, duration, strength=150):
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2, h / 2
    dx = (x - cx) / cx
    dy = (y - cy) / cy
    d = np.sqrt(dx * dx + dy * dy)
    t = np.clip((d - 0.55) / 0.5, 0, 1)
    alpha = (t * t * strength).astype(np.uint8)
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = alpha
    return ImageClip(img, transparent=True).set_duration(duration)


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def build_video(script, name, style, voice, output_dir, temp_dir,
                      topic_hint="", whisper_size="base", use_llm_prompts=True):
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("📝  Splitting script into scenes...")
    scenes = split_script_into_scenes(script)
    print(f"    → {len(scenes)} scenes")

    print("🎙️   Generating voiceover (Edge TTS, free)...")
    audio_path = temp_dir / f"{name}_audio.mp3"
    await generate_tts(script, audio_path, VOICES.get(voice, VOICES["narrator"]))
    audio_clip = AudioFileClip(str(audio_path))
    duration = audio_clip.duration
    print(f"    → {duration:.1f}s")

    # LLM-enhance visual prompts before image generation
    if use_llm_prompts:
        print(f"🧠  Building visual prompts via LLM (free)...")
        visual_prompts = []
        for i, scene in enumerate(scenes, 1):
            print(f"    [{i}/{len(scenes)}] enhancing...")
            vp = enhance_visual_prompt(scene, topic_hint=topic_hint)
            visual_prompts.append(vp)
    else:
        visual_prompts = scenes

    print(f"🎨  Generating {len(scenes)} images (best of 2 each, free)...")
    image_paths = []
    base_seed = int(time.time())
    for i, vp in enumerate(visual_prompts, 1):
        path = temp_dir / f"{name}_scene_{i:02d}.jpg"
        snippet = vp[:65] + ("..." if len(vp) > 65 else "")
        print(f"    [{i}/{len(visual_prompts)}] {snippet}")
        ok = generate_image_best_of_n(
            vp, style, path,
            base_seed=base_seed + i * 137,
            n=2
        )
        if ok:
            image_paths.append(path)
        else:
            print(f"    ⚠️  scene {i} image failed — skipping")

    if not image_paths:
        print("❌  No images generated. Aborting.")
        return None

    print("📋  Transcribing captions (Whisper)...")
    words = transcribe_with_whisper(audio_path, model_size=whisper_size)
    captions = group_words(words, per_group=3)
    print(f"    → {len(captions)} caption chunks")

    print("🎬  Assembling video...")
    per_scene = duration / len(image_paths)
    crossfade_dur = min(0.4, per_scene * 0.18)
    motions = ["zoom_in", "pan_right", "zoom_out", "pan_left"]

    image_clips = []
    for i, img_path in enumerate(image_paths):
        clip_dur = per_scene + (crossfade_dur if i < len(image_paths) - 1 else 0.0)
        clip = make_ken_burns_clip(img_path, clip_dur, WIDTH, HEIGHT, motion=motions[i % 4])
        clip = clip.set_start(i * per_scene)
        if i > 0:
            clip = clip.crossfadein(crossfade_dur)
        image_clips.append(clip)

    caption_clips = [
        make_animated_caption(c["text"], c["start"], c["end"], WIDTH, HEIGHT)
        for c in captions
    ]
    vignette = make_vignette_clip(WIDTH, HEIGHT, duration)

    final = CompositeVideoClip(
        image_clips + [vignette] + caption_clips, size=(WIDTH, HEIGHT)
    ).set_audio(audio_clip).set_duration(duration)

    out_path = output_dir / f"{name}.mp4"
    final.write_videofile(
        str(out_path), fps=30, codec="libx264", audio_codec="aac",
        threads=4, preset="medium", bitrate="6000k",
    )
    print(f"\n✅  Done!  →  {out_path}")
    return out_path


def main():
    p = argparse.ArgumentParser(description="Cartoon Shorts generator (quality edition)")
    p.add_argument("--script", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--style", default="adult_cartoon", choices=list(CARTOON_STYLES))
    p.add_argument("--voice", default="narrator", choices=list(VOICES))
    p.add_argument("--topic", default="")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--temp-dir", default="temp")
    p.add_argument("--whisper", default="base", choices=["tiny", "base", "small", "medium"])
    p.add_argument("--no-llm", action="store_true", help="Skip LLM prompt enhancement")
    args = p.parse_args()

    script_text = Path(args.script).read_text(encoding="utf-8").strip()
    if not script_text:
        print("Script file is empty.")
        sys.exit(1)

    asyncio.run(build_video(
        script=script_text, name=args.name, style=args.style, voice=args.voice,
        topic_hint=args.topic,
        output_dir=Path(args.output_dir), temp_dir=Path(args.temp_dir),
        whisper_size=args.whisper, use_llm_prompts=not args.no_llm,
    ))


if __name__ == "__main__":
    main()
