#!/usr/bin/env python3
"""
Timeline compiler and procedural audio generator.
Converts script.json into:
  - data.js (timeline and cues for page.html)
  - meta.json (frame count and duration)
  - vo.wav (Kokoro speech track)
  - sfx.wav (procedural SFX track: dings, whooshes, ticks)
  - music.wav (procedural lo-fi pad and arpeggio music)
  - post_metadata.txt (ready-to-post title, description, hashtags)
"""

import argparse
import json
import math
import os
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np

# Optional soundfile import with fallback message
try:
    import soundfile as sf
except ImportError:
    sf = None

# Optional kokoro_onnx import
try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None


def split_sentences_and_words(text: str):
    """Splits narration text into segments at punctuation marks."""
    pattern = r"[^.,;?!]+[.,;?!]?"
    segments = [s.strip() for s in re.findall(pattern, text) if s.strip()]
    if not segments:
        segments = [text.strip()]
    return segments


def create_procedural_sfx(sample_rate=44100):
    """Generates procedural sound effects using pure NumPy."""
    # 1. Whoosh (0.45s)
    dur_whoosh = int(sample_rate * 0.45)
    t_w = np.linspace(0, 0.45, dur_whoosh, endpoint=False)
    noise = np.random.uniform(-1, 1, dur_whoosh)
    # Sweeping low-pass envelope
    env = np.sin(np.pi * t_w / 0.45) ** 2
    f_sweep = np.linspace(400, 2400, dur_whoosh)
    carrier = np.sin(2 * np.pi * f_sweep * t_w)
    whoosh = (noise * 0.4 + carrier * 0.6) * env * 0.45

    # 2. Ding (harmonic chime: 1568 Hz + 3136 Hz)
    dur_ding = int(sample_rate * 0.35)
    t_d = np.linspace(0, 0.35, dur_ding, endpoint=False)
    ding = (np.sin(2 * np.pi * 1568 * t_d) * 0.65 + np.sin(2 * np.pi * 3136 * t_d) * 0.35) * np.exp(-12 * t_d) * 0.55

    # 3. Tick (fast mechanical click transient, 25ms)
    dur_tick = int(sample_rate * 0.025)
    t_k = np.linspace(0, 0.025, dur_tick, endpoint=False)
    tick = np.random.uniform(-1, 1, dur_tick) * np.exp(-350 * t_k) * 0.35

    return {
        "whoosh": whoosh.astype(np.float32),
        "ding": ding.astype(np.float32),
        "tick": tick.astype(np.float32),
    }


def synthesize_procedural_music(total_seconds: float, sample_rate=44100):
    """
    Synthesizes an ambient lo-fi pad progression (Am - F - C - G) at 90 BPM
    with soft pluck arpeggios using additive sine synthesis.
    """
    total_samples = int(total_seconds * sample_rate)
    music = np.zeros(total_samples, dtype=np.float32)

    bpm = 90.0
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4.0  # 4 beats per bar (~2.67s)

    # Chord roots and frequencies (Am, F, C, G)
    chords = [
        [220.00, 261.63, 329.63, 440.00],  # Am (A3, C4, E4, A4)
        [174.61, 220.00, 261.63, 349.23],  # F (F3, A3, C4, F4)
        [130.81, 164.81, 196.00, 261.63],  # C (C3, E3, G3, C4)
        [196.00, 246.94, 293.66, 392.00],  # G (G3, B3, D4, G4)
    ]

    num_bars = int(math.ceil(total_seconds / bar_dur)) + 1
    t = np.arange(total_samples) / sample_rate

    # Generate chord pads
    for bar_idx in range(num_bars):
        chord = chords[bar_idx % len(chords)]
        bar_start = int(bar_idx * bar_dur * sample_rate)
        bar_samples = int(bar_dur * sample_rate)
        if bar_start >= total_samples:
            break

        actual_len = min(bar_samples, total_samples - bar_start)
        t_bar = np.arange(actual_len) / sample_rate

        # Pad envelope (slow attack, smooth decay)
        attack_len = int(0.6 * sample_rate)
        env = np.ones(actual_len, dtype=np.float32)
        if actual_len > attack_len:
            env[:attack_len] = np.linspace(0, 1, attack_len)

        chord_audio = np.zeros(actual_len, dtype=np.float32)
        for freq in chord:
            # Fundamental + soft octave + slight detune for warmth
            tone = (
                np.sin(2 * np.pi * freq * t_bar) * 0.6
                + np.sin(2 * np.pi * (freq * 2) * t_bar) * 0.25
                + np.sin(2 * np.pi * (freq * 1.002) * t_bar) * 0.15
            )
            chord_audio += tone

        music[bar_start : bar_start + actual_len] += (chord_audio / len(chord)) * env * 0.22

        # Plucked arpeggio (eighth notes)
        arp_notes = [chord[i % len(chord)] * 2 for i in range(8)]
        sub_dur = bar_dur / 8.0
        for i, arp_freq in enumerate(arp_notes):
            arp_start = bar_start + int(i * sub_dur * sample_rate)
            arp_len = min(int(sub_dur * sample_rate * 1.5), total_samples - arp_start)
            if arp_start < total_samples and arp_len > 0:
                t_arp = np.arange(arp_len) / sample_rate
                pluck_env = np.exp(-8.0 * t_arp)
                pluck = (np.sin(2 * np.pi * arp_freq * t_arp) + 0.3 * np.sin(4 * np.pi * arp_freq * t_arp)) * pluck_env * 0.08
                music[arp_start : arp_start + arp_len] += pluck

    # Master volume envelope: 1.5s fade in, 2.0s fade out
    fade_in_len = min(int(1.5 * sample_rate), total_samples)
    fade_out_len = min(int(2.0 * sample_rate), total_samples)

    if fade_in_len > 0:
        music[:fade_in_len] *= np.linspace(0, 1, fade_in_len)
    if fade_out_len > 0:
        music[-fade_out_len:] *= np.linspace(1, 0, fade_out_len)

    # Normalize peak to 0.60
    peak = np.max(np.abs(music))
    if peak > 1e-4:
        music = (music / peak) * 0.60

    return music


def build_timeline_and_audio(script_path: str, output_dir: str, models_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    voice_id = script.get("voice", "am_michael")
    speed = float(script.get("speed", 1.05))
    theme = script.get(
        "theme",
        {
            "accent": "#ff7a50",
            "accent2": "#5aa2ff",
            "glowA": "rgba(255,122,80,0.18)",
            "glowB": "rgba(90,162,255,0.15)",
        },
    )

    print("=" * 60)
    print(f"Building Short: {script.get('title', 'Untitled')}")
    print(f"Voice: {voice_id} (speed: {speed}x)")
    print("=" * 60)

    # Initialize Kokoro TTS if available
    kokoro = None
    onnx_path = os.path.join(models_dir, "kokoro-v1.0.onnx")
    voices_path = os.path.join(models_dir, "voices-v1.0.bin")

    if Kokoro is not None and os.path.exists(onnx_path) and os.path.exists(voices_path):
        try:
            print("Loading Kokoro ONNX TTS model...")
            kokoro = Kokoro(onnx_path, voices_path)
            print("[✓] Kokoro TTS initialized successfully.")
        except Exception as e:
            print(f"[!] Warning: Failed to initialize Kokoro: {e}. Using mock speech timing.")
    else:
        print("[i] Kokoro model files not found in models/ - using realistic procedural speech timing.")
        print("    (Run 'python scripts/download_models.py' to download the 82M voice weights.)")

    sr_tts = 24000
    voice_segments = []  # List of (start_sec, audio_array)
    processed_scenes = []
    all_captions = []
    sfx_cues = []  # List of (time_sec, sfx_type)

    current_time = 0.0

    for idx, sc in enumerate(script.get("scenes", [])):
        scene_type = sc.get("type", "hook")
        say_text = sc.get("say", "")
        segments = split_sentences_and_words(say_text)

        t0 = current_time
        cur = t0 + 0.35  # Scene narration starts 0.35s after scene entrance
        cues = []
        is_new_sentence = True

        # SFX: whoosh on scene transitions (after first scene)
        if idx > 0:
            sfx_cues.append((t0, "whoosh"))

        print(f"\n[Scene {idx+1}: {scene_type}] t0={t0:.2f}s")

        for s in segments:
            if is_new_sentence:
                cues.append(round(cur, 3))
                # Trigger SFX for cues in loop or cards scenes
                if scene_type in ["loop", "cards", "stats"]:
                    sfx_cues.append((cur, "ding"))
                is_new_sentence = False

            # Synthesize audio or mock duration
            if kokoro is not None:
                try:
                    audio, out_sr = kokoro.create(s, voice=voice_id, speed=speed, lang="en-us")
                    sr_tts = out_sr
                    duration = len(audio) / sr_tts
                except Exception as err:
                    print(f"  [!] Kokoro synthesis error on '{s}': {err}")
                    words = s.split()
                    duration = max(0.6, (len(words) / (2.5 * speed)))
                    audio = np.zeros(int(duration * sr_tts), dtype=np.float32)
            else:
                words = s.split()
                # Realistic speaking rate: ~2.5 words per second modified by speed
                duration = max(0.6, (len(words) / (2.5 * speed)))
                audio = np.zeros(int(duration * sr_tts), dtype=np.float32)

            voice_segments.append((cur, audio))

            # Distribute words for captions
            words = s.split()
            if words:
                # Weight words proportionally to character length
                char_weights = np.array([len(w) + 2 for w in words], dtype=float)
                cumulative = np.cumsum(char_weights) / np.sum(char_weights) * duration
                starts = np.r_[0, cumulative[:-1]]
                for j, w in enumerate(words):
                    all_captions.append(
                        [
                            round(cur + float(starts[j]), 3),
                            round(cur + float(cumulative[j]), 3),
                            w.strip(".,;:?!"),
                        ]
                    )

            is_sentence_end = s[-1] in ".?!" if len(s) > 0 else True
            cur += duration + (0.35 if is_sentence_end else 0.12)
            is_new_sentence = is_sentence_end

        t1 = cur + 0.25  # Hold scene for 0.25s after voice completes
        current_time = t1

        # Copy scene data and inject computed timeline windows and cues
        sc_data = dict(sc)
        sc_data["t0"] = round(t0, 3)
        sc_data["t1"] = round(t1, 3)
        sc_data["cues"] = cues
        processed_scenes.append(sc_data)
        print(f"  └─ Audio duration: {t1 - t0:.2f}s | cues: {cues}")

    total_duration = current_time + 0.5  # Tail buffer
    total_duration = round(total_duration, 2)
    print("\n" + "=" * 60)
    print(f"Total Video Duration: {total_duration}s ({int(math.ceil(total_duration * 30))} frames @ 30fps)")
    if total_duration > 55.0:
        print("[!] Warning: Total duration exceeds 55 seconds for Shorts/Reels! Consider raising speed or trimming text.")
    print("=" * 60)

    # 1. Export data.js
    data_payload = {
        "title": script.get("title", ""),
        "theme": theme,
        "scenes": processed_scenes,
        "caps": all_captions,
        "total": total_duration,
    }
    data_js_path = os.path.join(output_dir, "data.js")
    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write(f"const DATA = {json.dumps(data_payload, indent=2)};\n")
        f.write("if (typeof module !== 'undefined') module.exports = DATA;\n")
    print(f"[✓] Generated timeline: {data_js_path}")

    # 2. Export meta.json
    meta_payload = {
        "title": script.get("title", ""),
        "total": total_duration,
        "fps": 30,
        "frames": int(math.ceil(total_duration * 30)),
        "width": 720,
        "height": 1280,
    }
    meta_json_path = os.path.join(output_dir, "meta.json")
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)
    print(f"[✓] Generated metadata: {meta_json_path}")

    # 3. Export post_metadata.txt
    post_meta_path = os.path.join(output_dir, "post_metadata.txt")
    with open(post_meta_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{script.get('title', '')}\n\n")
        f.write(f"DESCRIPTION:\n{script.get('description', '')}\n\n")
        f.write(f"HASHTAGS:\n{' '.join(script.get('hashtags', []))}\n")
    print(f"[✓] Generated post info: {post_meta_path}")

    if sf is None:
        print("[!] soundfile package not installed - skipping WAV file exports.")
        print("    Run 'pip install soundfile' to produce vo.wav, sfx.wav, and music.wav.")
        return

    # 4. Generate & Save Voice Track (vo.wav)
    total_voice_samples = int(total_duration * sr_tts)
    vo_audio = np.zeros(total_voice_samples, dtype=np.float32)
    for start_t, seg_audio in voice_segments:
        start_idx = int(start_t * sr_tts)
        end_idx = min(start_idx + len(seg_audio), total_voice_samples)
        write_len = end_idx - start_idx
        if write_len > 0:
            vo_audio[start_idx:end_idx] += seg_audio[:write_len]

    vo_path = os.path.join(output_dir, "vo.wav")
    sf.write(vo_path, vo_audio, sr_tts)
    print(f"[✓] Saved Voice Audio: {vo_path}")

    # 5. Generate & Save SFX Track (sfx.wav) at 44.1 kHz
    sr_sfx = 44100
    sfx_samples = int(total_duration * sr_sfx)
    sfx_audio = np.zeros(sfx_samples, dtype=np.float32)
    sfx_bank = create_procedural_sfx(sr_sfx)

    for cue_t, sfx_name in sfx_cues:
        clip = sfx_bank.get(sfx_name)
        if clip is not None:
            st = int(cue_t * sr_sfx)
            en = min(st + len(clip), sfx_samples)
            if en > st:
                sfx_audio[st:en] += clip[: en - st]

    sfx_path = os.path.join(output_dir, "sfx.wav")
    sf.write(sfx_path, sfx_audio, sr_sfx)
    print(f"[✓] Saved SFX Audio: {sfx_path}")

    # 6. Generate & Save Music Track (music.wav) at 44.1 kHz
    music_audio = synthesize_procedural_music(total_duration, sample_rate=sr_sfx)
    music_path = os.path.join(output_dir, "music.wav")
    sf.write(music_path, music_audio, sr_sfx)
    print(f"[✓] Saved Music Audio: {music_path}")


def main():
    parser = argparse.ArgumentParser(description="Compile script.json into video timeline and audio assets.")
    parser.add_argument("--input", "-i", default="script.json", help="Path to script.json")
    parser.add_argument("--output-dir", "-o", default="dist", help="Output directory")
    parser.add_argument("--models-dir", "-m", default="models", help="Directory containing Kokoro ONNX model weights")

    args = parser.parse_args()

    # Fallback to example if script.json not present in current dir
    if not os.path.exists(args.input):
        example_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "demo_agent_loop", "script.json")
        if os.path.exists(example_path):
            print(f"'{args.input}' not found. Using default example at: {example_path}")
            args.input = example_path
        else:
            print(f"Error: Input file '{args.input}' not found.")
            sys.exit(1)

    build_timeline_and_audio(args.input, args.output_dir, args.models_dir)


if __name__ == "__main__":
    main()

