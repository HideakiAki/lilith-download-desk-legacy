LILITH DOWNLOAD DESK 1.3.2
Windows download manager with browser video button, opt-in Chrome auto-capture,
resumable direct-file transfers, downloadable video quality inspection, and a tray app.

UPGRADING FROM v1.2 / v1.3 / v1.3.1
1. In the Lilith system tray menu, select Quit (not just X; X hides the window).
2. Extract this v1.3.2 ZIP to a permanent folder such as Documents\LilithDownloadDesk_v1_3.
3. Double-click Install_and_Launch.bat once (installs yt-dlp, Pillow, pystray, imageio-ffmpeg and prepares private media engine).
4. If you want a new desktop shortcut, use Create_Shortcuts.bat in the extracted folder.
5. In Chrome: chrome://extensions -> remove old Lilith extension -> turn on Developer
   mode -> Load unpacked -> select the NEW browser_extension folder from this ZIP.
6. Pair the extension again if necessary: copy the browser pairing key from the
   desktop application's right sidebar into the extension popup, then Save.
7. In the extension popup, check "Automatically catch Chrome file downloads".
   This option is OFF by default so you can decide whether Lilith takes over.
8. For existing v1.2 failed .safetensors downloads, select the old job and click
   Resume. The app upgrades known model-file URLs from video to direct-file mode.

KEY FEATURES
- Chrome download interception (opt-in): Chrome pauses a new HTTP(S) download,
  Lilith checks whether it can fetch the file without browser cookies, then
  queues it. Only then does Chrome cancel its original download. If Lilith cannot
  access it at the handoff stage, Chrome resumes its own download.
- Floating "Download this video" button remains available for HTML5 players.
- Browser right-click -> "Download link with Lilith (direct file)".
- Video pages handled by yt-dlp; available formats from Inspect qualities.
- Direct files handled by built-in resumable HTTP engine (single connection).
- Dedicated progress window: live percentage, bytes, speed and estimated time.
- Unknown-size downloads use an animated progress indicator; percent and ETA may
  not be possible until a server reports the file size.
- Downloads stay in the queue, including errors and saved partial files.
- Closing main window hides it to the system tray where available.
- Optional startup with Windows, console-free launcher and desktop shortcut.
- AI-friendly MP4 conversion and trimming with Lilith-managed FFmpeg (no manual install).

KEYBOARD SHORTCUTS
- Enter in Download URL: add link.
- Enter on selected queue item: start, resume, or show progress.
- Delete on selected queue item: remove that job (does not erase file data).
- F5: start queue.
- Ctrl+J: open active download progress window.
- Ctrl+P: pause selected download. Ctrl+R: resume selected download.
- Ctrl+O: open download folder.
- Error details button: view exact reason for a failed job.

DIRECT DOWNLOAD LIMITATIONS
- Supported files include .safetensors, .ckpt, .pt, .onnx, .gguf, .zip, .mp4,
  .rar, .exe, and many others.
- Some browser downloads require cookies, temporary access tokens, POST requests,
  protected sessions or referer checks. Lilith does not extract or transmit
  browser cookies, and cannot always download those links. Chrome remains the
  fallback whenever Lilith's preflight check fails.
- Browser handoff can succeed initially then fail later if a link expires or
  the remote server changes permissions. In that case, use Chrome again.
- Only HTTP(S) files with working download links are eligible for auto-capture;
  blob:, data:, DRM and browser-internal links remain in Chrome.
- Resume depends on HTTP Range support and a stable URL/file. If unavailable,
  an existing partial file is preserved, not silently discarded.
- For download failures, select the job and click Error details; HTTP 403
  usually indicates authentication/expired URL, not a bug in the progress UI.
- Direct file transfers currently use one connection for reliable telemetry.
  yt-dlp can download multiple video fragments, but this is not an exact IDM
  replacement for every website and streaming protocol.
- Download only content you are permitted to save.

DEPENDENCIES
- Required: Python 3.11 or newer and tkinter.
- Automatically installed: yt-dlp, Pillow, pystray and imageio-ffmpeg (includes FFmpeg executable).
- No system-wide FFmpeg install or PATH editing needed. Setup creates a private copy in %LOCALAPPDATA%\LilithDownloadDesk\tools\.

DATA AND PRIVACY
- Local downloads and queue data stay on your Windows machine.
- Local app data: %LOCALAPPDATA%\LilithDownloadDesk
- Browser pairing key is stored locally; never share it publicly.
- Queue URLs may include private signed tokens; keep your jobs.json private.
- Receiver is bound to 127.0.0.1:51234 and requires a pairing key.
- The extension requests Chrome Downloads permission only for the explicitly
  opted-in interception workflow. You can disable auto-capture anytime.

MAIN WINDOW PROGRESS DISPLAY
v1.3 includes a live compact progress bar immediately below the download queue.
The standalone download progress window remains independently minimizable.
When there is no total file size, Lilith shows downloaded bytes and an animated
indicator instead of inventing a percentage or ETA.

v1.3.1 HOTFIX ADDENDUM
- Video conversion, clip trimming, FFmpeg settings and manual merging now live in a separate Video Tools dialog.
- Detailed logs open in a separate View log window.
- Explicit FFmpeg location and merge requirement for high-quality video.
- Prefer compatible MP4 + M4A streams where offered and verify merged output.
- Repair previously split .mp4 video + .webm audio using Merge existing video + audio.
- Open a completed file, reveal it in Explorer, context menu and shortcuts.
- See START_HERE_v1_3_1.txt for the update procedure and known limitations.
- See UI_V2_DESIGN_PLAN.txt for the recommended design-first animated UI approach.


v1.3.2 NO-MANUAL-FFMPEG HOTFIX
- Install_and_Launch.bat automatically installs a Windows FFmpeg binary via the
  reputable imageio-ffmpeg Python package and stores a private copy for Lilith.
- Video/audio merging and MP4 conversion use this private media engine.
- FFprobe is no longer required to verify combined output: the verification
  code falls back to FFmpeg's own stream inspection.
- Video Tools offers Check / repair media engine; custom paths remain optional.
- See START_HERE_v1_3_2.txt for exact upgrade steps.
