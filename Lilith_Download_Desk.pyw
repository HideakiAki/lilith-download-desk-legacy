"""Console-free Windows entry point for Lilith Download Desk."""
from pathlib import Path
import os
import traceback

if __name__ == "__main__":
    try:
        from Lilith_Download_Desk import main
        main()
    except Exception:
        # pythonw has no command prompt. Keep diagnostics in an ordinary local file.
        folder = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "LilithDownloadDesk"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0, f"Lilith encountered an error. Please see {folder}\\crash.log",
                    "Lilith Download Desk", 0x10)
            except Exception:
                pass
