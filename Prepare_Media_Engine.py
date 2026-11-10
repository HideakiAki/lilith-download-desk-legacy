"""Called once by the installer. Does not require admin access or PATH edits."""
import sys

from media_runtime import prepare_media_engine

if __name__ == "__main__":
    try:
        location = prepare_media_engine()
        print("Lilith's media engine is ready:", location)
    except Exception as exc:
        print("Media engine setup failed:", exc, file=sys.stderr)
        raise SystemExit(1)
