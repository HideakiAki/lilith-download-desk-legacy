"""Install a private, automatically managed FFmpeg executable for Lilith.

The installed imageio-ffmpeg wheel ships a platform-specific executable.  We
copy it once, as ffmpeg.exe on Windows, so yt-dlp can recognize it.  No system
PATH changes, administrator rights, or separate FFmpeg setup are needed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path


APP_DATA = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local")) / "LilithDownloadDesk"
MANAGED_DIR = APP_DATA / "tools"
BINARY_NAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _check_binary(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        proc = subprocess.run([str(path), "-hide_banner", "-version"],
                              capture_output=True, text=True, timeout=12,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return proc.returncode == 0 and "ffmpeg version" in proc.stdout.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def prepare_media_engine(*, repair: bool = False, directory: Path | None = None) -> str:
    """Copy the FFmpeg executable from imageio-ffmpeg to Lilith's app data.

    Raises a useful error when imageio-ffmpeg hasn't yet been installed or the
    wheel doesn't contain a usable executable. Repairs are explicit to avoid
    replacing ffmpeg.exe during an active download on Windows.
    """
    target_dir = Path(directory) if directory is not None else MANAGED_DIR
    target = target_dir / BINARY_NAME
    if not repair and _check_binary(target):
        return str(target)
    try:
        import imageio_ffmpeg
        packaged = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError) as exc:
        raise RuntimeError(
            "Lilith's automatic media engine is missing. "
            "Close Lilith and run Install_and_Launch.bat to install it automatically."
        ) from exc
    if not _check_binary(packaged):
        raise RuntimeError("The packaged media engine failed its health check. Run Install_and_Launch.bat again.")
    if target.resolve() == packaged.resolve():
        return str(target)
    target_dir.mkdir(parents=True, exist_ok=True)
    staging = target_dir / (".ffmpeg-" + uuid.uuid4().hex + (".exe" if os.name == "nt" else ".tmp"))
    try:
        shutil.copy2(packaged, staging)
        # The wheel binary is executable on Unix; preserve that bit as well.
        if os.name != "nt":
            staging.chmod(staging.stat().st_mode | 0o111)
        if not _check_binary(staging):
            raise RuntimeError("Copied media engine failed validation.")
        os.replace(staging, target)
    except PermissionError as exc:
        raise RuntimeError("The media engine is in use. Finish downloads and close Lilith before repairing it.") from exc
    finally:
        try:
            staging.unlink(missing_ok=True)
        except OSError:
            pass
    return str(target)


def managed_media_engine() -> str | None:
    """Return a ready-to-use private FFmpeg, or None if not yet installed."""
    try:
        return prepare_media_engine()
    except (RuntimeError, OSError):
        return None
