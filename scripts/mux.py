#!/usr/bin/env python3
"""
Muxes video and audio tracks with automated sidechain audio ducking using ffmpeg.
Ducks background music under voice narration, mixes procedural SFX,
and extracts a video thumbnail.
"""

import argparse
import json
import os
import subprocess
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def find_ffmpeg():
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_ffmpeg = os.path.join(
        local_app_data,
        "Microsoft",
        "WinGet",
        "Packages",
        "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
        "ffmpeg-8.0.1-full_build",
        "bin",
        "ffmpeg.exe",
    )
    if os.path.exists(winget_ffmpeg):
        return winget_ffmpeg
    return "ffmpeg"

def run_cmd(cmd):
    ffmpeg_bin = find_ffmpeg()
    if cmd and cmd[0] == "ffmpeg":
        cmd[0] = ffmpeg_bin
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[!] Error running command:\n{res.stderr}")
        return False
    return True


def mux_video_audio(video_file: str, audio_dir: str, output_file: str):
    if not os.path.exists(video_file):
        print(f"Error: Video file not found at: {video_file}")
        sys.exit(1)

    vo_wav = os.path.join(audio_dir, "vo.wav")
    music_wav = os.path.join(audio_dir, "music.wav")
    sfx_wav = os.path.join(audio_dir, "sfx.wav")
    meta_json = os.path.join(audio_dir, "meta.json")

    total_duration = 30.0
    if os.path.exists(meta_json):
        try:
            with open(meta_json, "r", encoding="utf-8") as f:
                meta = json.load(f)
                total_duration = float(meta.get("total", 30.0))
        except Exception:
            pass

    print("=" * 60)
    print("Muxing Video + Multi-Track Audio with Sidechain Ducking")
    print(f"Video input:  {video_file}")
    print(f"Voice track:  {vo_wav} (exists: {os.path.exists(vo_wav)})")
    print(f"Music track:  {music_wav} (exists: {os.path.exists(music_wav)})")
    print(f"SFX track:    {sfx_wav} (exists: {os.path.exists(sfx_wav)})")
    print(f"Output file:  {output_file}")
    print("=" * 60)

    # Check which audio files are available
    has_vo = os.path.exists(vo_wav)
    has_music = os.path.exists(music_wav)
    has_sfx = os.path.exists(sfx_wav)

    cmd = ["ffmpeg", "-y", "-i", video_file]

    if has_vo and has_music and has_sfx:
        cmd.extend(["-i", vo_wav, "-i", music_wav, "-i", sfx_wav])
        filter_complex = (
            "[1:a]aresample=44100,loudnorm=I=-16:TP=-1.5,asplit=2[v1][v2];"
            "[2:a]volume=0.38[m0];[m0][v2]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[md];"
            "[3:a]volume=0.6[sx];"
            "[v1][md][sx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[a]"
        )
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(total_duration),
            output_file
        ])
    elif has_vo and has_music:
        cmd.extend(["-i", vo_wav, "-i", music_wav])
        filter_complex = (
            "[1:a]aresample=44100,loudnorm=I=-16:TP=-1.5,asplit=2[v1][v2];"
            "[2:a]volume=0.38[m0];[m0][v2]sidechaincompress=threshold=0.03:ratio=10:attack=15:release=350[md];"
            "[v1][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
        )
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(total_duration),
            output_file
        ])
    elif has_vo:
        cmd.extend([
            "-i", vo_wav,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(total_duration),
            output_file
        ])
    else:
        print("[!] No audio tracks found. Copying video stream only.")
        cmd.extend(["-c:v", "copy", "-t", str(total_duration), output_file])

    success = run_cmd(cmd)
    if not success:
        print("[!] Muxing failed. Check ffmpeg output above.")
        sys.exit(1)

    print(f"\n[✓] Final video created successfully: {output_file}")

    # Extract high-impact thumbnail from 25% into the video
    thumb_time = max(1.0, round(total_duration * 0.25, 2))
    thumb_path = os.path.splitext(output_file)[0] + "_thumbnail.jpg"
    thumb_cmd = [
        "ffmpeg", "-y",
        "-ss", str(thumb_time),
        "-i", output_file,
        "-frames:v", "1",
        "-q:v", "2",
        thumb_path
    ]
    if run_cmd(thumb_cmd):
        print(f"[✓] Extracted thumbnail: {thumb_path}")


def main():
    parser = argparse.ArgumentParser(description="Mux video with voice, SFX, and ducked music.")
    parser.add_argument("--video", "-v", default="dist/tmp_short.mp4", help="Path to raw video mp4")
    parser.add_argument("--audio-dir", "-a", default="dist", help="Directory containing audio tracks and meta.json")
    parser.add_argument("--output", "-o", default="final.mp4", help="Path for final output mp4")

    args = parser.parse_args()
    mux_video_audio(args.video, args.audio_dir, args.output)


if __name__ == "__main__":
    main()

