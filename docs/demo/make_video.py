"""Build the 30-second demo video (docs/demo/trend_detective_demo.mp4) from live-site screenshots.

Usage (from the repo root):
    backend/.venv/bin/python docs/demo/make_video.py           # captions only (silent)
    backend/.venv/bin/python docs/demo/make_video.py --voice   # + ElevenLabs voice-over

The voice-over needs ELEVENLABS_API_KEY in the environment or in backend/.env (git-ignored). It is never printed.
Optional: ELEVENLABS_VOICE_ID to pick another voice. Generated clips are cached in
docs/demo/audio/ so re-rendering costs nothing; delete them to regenerate.

The whole video is kept under 30.0 s (Space Apps rule for global judging). Scenes are
timed to the narration; captions are burnt in so it also works muted.

AI-use note: drafted with Claude (Anthropic) during the hackathon. The voice is
synthetic (ElevenLabs text-to-speech) and is disclosed in the end card.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMG, AUDIO = HERE / "img", HERE / "audio"
OUT = HERE / "trend_detective_demo.mp4"
W, H, FPS = 1280, 720, 30
MAX_LEN = 29.6  # seconds; the rule is <= 30.0
CAP_H = 118  # caption bar height
TEAM = "Paani Ke Batashe"
NAMES = "Akshita Srivastava · Kanishk K. Sachan"
CHALLENGE = "Be An Earth System Trend Detective!"
SITE = "kaakserver.tail042e87.ts.net/trend-detective"

BG, BLUE, RED, INK, MUTED = (247, 239, 223), (27, 63, 176), (196, 42, 18), (29, 36, 51), (91, 97, 112)
SUP = Path("/System/Library/Fonts/Supplemental")


def font(name: str, size: int):
    p = SUP / name
    try:
        return ImageFont.truetype(str(p) if p.exists() else "DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


DISPLAY = lambda s: font("DIN Condensed Bold.ttf", s)  # noqa: E731
BODY = lambda s: font("Arial Narrow.ttf", s)  # noqa: E731
BODY_B = lambda s: font("Arial Narrow Bold.ttf", s)  # noqa: E731
MONO = lambda s: font("Courier New Bold.ttf", s)  # noqa: E731

# (id, picture or card, focus_y, caption on screen, words spoken, minimum seconds)
SCENES = [
    ("title", "card:title", 0, None,
     "Is it really changing where you live, or does it just look that way?", 3.0),
    ("hero", "hero2.jpg", 0.45, "Pick any place on Earth and a NASA variable.",
     "Trend Detective tests NASA data the honest way.", 2.4),
    ("chance", "chance2.jpg", 0.55, "On pure noise, a typical test finds a “trend” 28% of the time. Ours: 6%.",
     "On pure noise, a typical test finds a trend twenty-eight percent of the time. Ours: six.", 4.0),
    ("alibi", "alibi_wisc.jpg", 0.5, "Cross-examination: was it a satellite switch? For cloud, 42 of 88 trends could be.",
     "Then we cross-examine it. Was it just a satellite switch?", 3.0),
    ("delhi", "delhi_wit_left.jpg", 0.4, "Delhi: NASA's own thermometers say warming. The model doesn't.",
     "Independent witnesses must agree. In Delhi, they don't.", 3.0),
    ("globe", "globe_luck.jpg", 0.5, "Shuffled records, no trend possible: a typical test is fooled 22%, ours 7%.",
     "Worldwide, on pure luck, a typical test is fooled twenty-two percent of the time. Ours: seven.", 4.2),
    ("y2050", "y2050.jpg", 0.5, "Around 2050: your trend, 7 climate models, 3 emission paths.",
     "And around twenty fifty: your trend, climate models, and three emission paths.", 3.3),
    ("end", "card:end", 0, None, "Check any place yourself.", 2.4),
]


# ---------- voice-over (ElevenLabs)
def _api_key() -> str | None:
    sys.path.insert(0, str(ROOT / "backend" / "src"))
    from trend_detective import creds  # loads backend/.env into os.environ, prints nothing

    creds._load()
    return os.environ.get("ELEVENLABS_API_KEY") or None


def voice_clips(speed: float) -> None:
    key = _api_key()
    if not key:
        sys.exit("No ELEVENLABS_API_KEY in backend/.env: add the line ELEVENLABS_API_KEY=... and run again.")
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # "George", a premade voice
    AUDIO.mkdir(exist_ok=True)
    prev = ""
    for sid, _, _, _, words, _ in SCENES:
        path = AUDIO / f"{sid}.mp3"
        meta = AUDIO / f"{sid}.json"
        want = {"text": words, "voice": voice, "speed": speed}
        if path.exists() and meta.exists() and json.loads(meta.read_text()) == want:
            prev = words
            continue
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                       params={"output_format": "mp3_44100_128"},
                       headers={"xi-api-key": key, "accept": "audio/mpeg"},
                       json={"text": words, "model_id": "eleven_multilingual_v2", "previous_text": prev or None,
                             "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "speed": speed}},
                       timeout=90)
        if r.status_code != 200:
            sys.exit(f"ElevenLabs error {r.status_code}: {r.text[:200]}")
        path.write_bytes(r.content)
        meta.write_text(json.dumps(want))
        print("voice:", sid)
        prev = words


TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse")


def trimmed(sid: str) -> Path | None:
    """The clip with ElevenLabs' leading/trailing silence removed (cached as .wav)."""
    src, out = AUDIO / f"{sid}.mp3", AUDIO / f"{sid}.wav"
    if not src.exists():
        return None
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", TRIM, str(out)], check=True)
    return out


def clip_seconds(sid: str) -> float | None:
    p = trimmed(sid)
    if p is None:
        return None
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else None


def timings(use_voice: bool) -> list[float]:
    d = []
    for sid, *_, minimum in SCENES:
        c = clip_seconds(sid) if use_voice else None
        d.append(max(minimum, c + 0.22) if c else minimum)
    total = sum(d)
    if total > MAX_LEN:
        raise SystemExit(f"Scenes add up to {total:.1f} s (> {MAX_LEN}); rerun with a faster --speed.")
    if not use_voice:  # silent version: stretch every scene to fill the time
        d = [x * (MAX_LEN - 0.1) / total for x in d]
    return d


# ---------- pictures
def cover(im: Image.Image, fy: float, zoom: float, box=(W, H - CAP_H)) -> Image.Image:
    bw, bh = box
    s = max(bw / im.width, bh / im.height) * zoom
    big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x0 = (big.width - bw) // 2
    y0 = int(np.clip(fy * big.height - bh / 2, 0, big.height - bh))
    return big.crop((x0, y0, x0 + bw, y0 + bh))


def caption_bar(frame: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(frame)
    d.rectangle([0, H - CAP_H, W, H], fill=BLUE)
    lines = textwrap.wrap(text, 62)
    f = BODY_B(40 if len(lines) == 1 else 34)
    y = H - CAP_H + (CAP_H - len(lines) * f.size * 1.15) / 2
    for line in lines:
        d.text((48, y), line, font=f, fill=(255, 255, 255))
        y += f.size * 1.15
    d.text((W - 48, H - 16), f"TREND DETECTIVE · TEAM {TEAM.upper()}", font=MONO(13), fill=(200, 210, 245),
           anchor="rs")


def card(kind: str, voiced: bool) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.line([48, 64, W - 48, 64], fill=(207, 196, 173), width=2)
    d.text((48, 30), "NASA SPACE APPS CHALLENGE 2026", font=MONO(18), fill=BLUE)
    if kind == "title":
        d.text((48, 110), "TREND DETECTIVE", font=DISPLAY(150), fill=BLUE)
        d.text((52, 275), "IS IT REALLY CHANGING?", font=DISPLAY(72), fill=RED)
        d.text((52, 400), f"Team {TEAM}", font=BODY_B(46), fill=INK)
        d.text((52, 462), NAMES, font=BODY(40), fill=INK)
        d.text((52, 560), f"Challenge: “{CHALLENGE}”", font=BODY(32), fill=MUTED)
        d.text((52, 605), "Lincoln, UK", font=BODY(32), fill=MUTED)
    else:
        d.text((48, 110), "CHECK ANY PLACE", font=DISPLAY(120), fill=BLUE)
        d.text((48, 235), "YOURSELF.", font=DISPLAY(120), fill=RED)
        d.text((52, 375), SITE, font=MONO(38), fill=BLUE)
        d.text((52, 432), "Instrument check · false alarms measured · witnesses counted · 4 ocean cycles · "
                          "world luck test · 2050 what-ifs", font=BODY_B(27), fill=RED)
        d.text((52, 490), f"Team {TEAM}  ·  {NAMES}", font=BODY_B(34), fill=INK)
        d.text((52, 538), f"NASA Space Apps 2026  ·  “{CHALLENGE}”", font=BODY(30), fill=MUTED)
        credit = ("Data: NASA POWER, MERRA-2, MODIS, GPM IMERG, GPCP, GISTEMP, GLDAS, GRACE, Blue Marble; "
                  "ESA CCI; Met Office; NOAA; CMIP6.")
        d.text((52, 625), credit, font=BODY(22), fill=MUTED)
        if voiced:
            d.text((52, 658), "Voice: AI text-to-speech (ElevenLabs). Pictures: screenshots of our own site.",
                   font=BODY(22), fill=MUTED)
    return im


def frames(durations: list[float], voiced: bool):
    prev_last = None
    for (sid, src, fy, cap, _, _), dur in zip(SCENES, durations):
        n = round(dur * FPS)
        base = card(src[5:], voiced) if src.startswith("card:") else Image.open(IMG / src).convert("RGB")
        for i in range(n):
            t = i / max(n - 1, 1)
            if src.startswith("card:"):
                f = base.copy()
            else:
                f = Image.new("RGB", (W, H), BG)
                f.paste(cover(base, fy, 1.0 + 0.05 * t), (0, 0))
                caption_bar(f, cap)
            if prev_last is not None and i < 6:  # 0.2 s cross-fade
                f = Image.blend(prev_last, f, (i + 1) / 7)
            yield f
        prev_last = f


def render(durations: list[float], use_voice: bool) -> None:
    starts = np.cumsum([0] + durations[:-1])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    clips = [(trimmed(s[0]), st) for s, st in zip(SCENES, starts)] if use_voice else []
    for p, _ in clips:
        cmd += ["-i", str(p)]
    if clips:
        parts = [f"[{k + 1}:a]adelay={int((st + 0.08) * 1000)}|{int((st + 0.08) * 1000)}[a{k}]"
                 for k, (_, st) in enumerate(clips)]
        mix = "".join(f"[a{k}]" for k in range(len(clips)))
        cmd += ["-filter_complex", ";".join(parts) + f";{mix}amix=inputs={len(clips)}:normalize=0[aout]",
                "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
    meta = ("Trend Detective: Is It Really Changing? Team Paani Ke Batashe (Akshita Srivastava, Kanishk K. Sachan), "
            "NASA Space Apps 2026. Pictures: screenshots of our own site. "
            + ("Voice-over: AI-generated text-to-speech (ElevenLabs)." if use_voice else "No voice-over."))
    cmd += ["-metadata", f"title=Trend Detective: Is It Really Changing?", "-metadata", f"comment={meta}",
            "-metadata", f"description={meta}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart",
            "-t", f"{sum(durations):.2f}", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames(durations, use_voice):
        p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", action="store_true", help="add an ElevenLabs voice-over")
    ap.add_argument("--speed", type=float, default=1.08, help="ElevenLabs speaking speed (0.7–1.2)")
    a = ap.parse_args()
    if a.voice:
        voice_clips(a.speed)
    d = timings(a.voice)
    render(d, a.voice)
    print(f"wrote {OUT.relative_to(ROOT)}  ({sum(d):.1f} s, {'with' if a.voice else 'no'} voice-over)")
