#!/usr/bin/env python3
"""
Model downloader for Kokoro TTS weights (kokoro-v1.0.onnx and voices-v1.0.bin).
Downloads into the `models/` directory if not already present.
"""

import os
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

FILES = [
    {
        "name": "kokoro-v1.0.onnx",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
        "size_mb": 325
    },
    {
        "name": "voices-v1.0.bin",
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
        "size_mb": 28
    }
]

def download_file(url: str, dest_path: str, label: str):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024 * 1024:
        print(f"[✓] {label} already exists at {dest_path}")
        return

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"Downloading {label} from {url} ...")

    def progress(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            downloaded_mb = (count * block_size) / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  Progress: {percent}% ({downloaded_mb:.1f} / {total_mb:.1f} MB)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest_path, reporthook=progress)
    print("\n[✓] Done!")

def main():
    print(f"Setting up Kokoro TTS models in: {MODELS_DIR}\n")
    for item in FILES:
        dest = os.path.join(MODELS_DIR, item["name"])
        download_file(item["url"], dest, f"{item['name']} (~{item['size_mb']}MB)")
    print("\nAll model weights ready for speech generation!")

if __name__ == "__main__":
    main()

