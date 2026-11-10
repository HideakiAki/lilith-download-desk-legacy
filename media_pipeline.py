"""Small, independently testable media helpers for Lilith Download Desk.

This module never downloads private URLs or changes user files unless explicitly
asked to merge a selected pair of local video/audio files.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from media_runtime import managed_media_engine, prepare_media_engine


def ffmpeg_executable(configured: str = "", app_folder: str | Path = "") -> str | None:
    """Find a working FFmpeg, favoring custom overrides then Lilith-managed FFmpeg."""
    candidates = []
    if configured:
        path = Path(configured).expanduser()
        candidates.append(path / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg") if path.is_dir() else path)
    if app_folder:
        base = Path(app_folder)
        exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        candidates += [base / "tools" / exe, base / exe, base / "bin" / exe]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    # The installer uses imageio-ffmpeg to keep a private copy. This also
    # self-heals when an update changes the packaged executable location.
    managed = managed_media_engine()
    if managed:
        return managed
    return shutil.which("ffmpeg")


def ffprobe_executable(ffmpeg: str | None) -> str | None:
    if not ffmpeg:
        return None
    binary = "ffprobe.exe" if Path(ffmpeg).suffix.lower() == ".exe" else "ffprobe"
    beside = Path(ffmpeg).with_name(binary)
    if beside.is_file():
        return str(beside.resolve())
    return shutil.which("ffprobe")


def selection_for(quality: str = "Best", explicit_id: str = "", *, is_audio: bool = False, has_audio: bool = False) -> str:
    """Prefer MP4 + M4A streams, use a compatible combined format next.

    When a specific video-only format is selected, require an audio stream;
    never silently download that video without its audio.
    """
    if explicit_id:
        if is_audio or has_audio:
            return explicit_id
        return f"{explicit_id}+ba[ext=m4a]/{explicit_id}+ba"
    if quality == "1080p max":
        filt = "[height<=1080]"
    elif quality == "720p max":
        filt = "[height<=720]"
    else:
        filt = ""
    return (f"bv{filt}[ext=mp4]+ba[ext=m4a]/"
            f"b{filt}[ext=mp4]/"
            f"bv{filt}+ba/"
            f"b{filt}")


def probe_media(path: str | Path, *, ffprobe: str | None = None, timeout: int = 30) -> set[str] | None:
    """Read stream types using ffprobe, or FFmpeg itself if only it is bundled.

    imageio-ffmpeg includes ffmpeg but not ffprobe. Its ordinary `-i` stream
    listing still identifies whether the final file has both streams.
    """
    binary = ffprobe or shutil.which("ffprobe")
    if binary:
        proc = subprocess.run([binary, "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode:
            raise RuntimeError("Could not inspect the resulting media: " + (proc.stderr or "unknown error")[-500:])
        return {str(s.get("codec_type", "")) for s in json.loads(proc.stdout).get("streams", [])}
    # This fallback requires no ffprobe dependency and does not modify media.
    import re
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise RuntimeError("Lilith's media engine is unavailable, so the output cannot be verified.")
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    info = proc.stderr + "\n" + proc.stdout
    streams = set()
    if re.search(r"Stream #\d+:\d+.*?Video:", info):
        streams.add("video")
    if re.search(r"Stream #\d+:\d+.*?Audio:", info):
        streams.add("audio")
    if not streams:
        raise RuntimeError("The merged media could not be inspected: " + info[-700:])
    return streams


def verify_combined(path: str | Path, *, ffprobe: str | None = None, audio_only: bool = False) -> None:
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        raise RuntimeError("The downloader finished without producing a playable output file.")
    kinds = probe_media(p, ffprobe=ffprobe)
    if kinds is None:
        return
    if audio_only:
        if "audio" not in kinds:
            raise RuntimeError("The downloaded audio file contains no audio stream.")
    elif not {"video", "audio"}.issubset(kinds):
        raise RuntimeError("The downloaded video is missing its audio track. Please check the log; the files have been preserved.")


def merge_existing(video: str | Path, audio: str | Path, output: str | Path, ffmpeg: str, *, timeout: int = 3600) -> str:
    """Merge user-selected already-downloaded tracks into MP4 without replacing originals.

    Video is copied losslessly when MP4-compatible; audio is converted to AAC
    to support e.g. an Opus track from a WebM download.
    """
    video, audio, output = map(Path, (video, audio, output))
    if not video.is_file() or not audio.is_file():
        raise ValueError("Select an existing video and audio file.")
    if output.exists() or output.resolve() in (video.resolve(), audio.resolve()):
        raise ValueError("Choose a new output name. The source tracks will not be overwritten.")
    if output.suffix.lower() != ".mp4":
        raise ValueError("The repaired output must use the .mp4 extension.")
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-n", "-i", str(video), "-i", str(audio),
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(output)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode:
            raise RuntimeError("FFmpeg merge failed: " + (proc.stderr or proc.stdout)[-1400:])
        verify_combined(output, ffprobe=ffprobe_executable(ffmpeg))
        return str(output)
    except Exception:
        # Never leave a corrupt file where an apparently finished MP4 should be.
        try:
            if output.exists():
                output.unlink()
        except OSError:
            pass
        raise
