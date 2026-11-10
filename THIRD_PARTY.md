# Third-Party Dependencies and Attributions

The original code uses common packages/tools and platform interfaces. It **does not vendor** the Python packages or the FFmpeg executable into this source archive; the v1.3.2 setup downloads dependencies separately.

| Dependency | Purpose | Notes |
|---|---|---|
| Python, including Tkinter and standard library | Desktop GUI and local logic | Python and platform components have their own licenses |
| `yt-dlp` | Website/video metadata extraction and downloads | Separate open-source project; current upstream license applies |
| `Pillow` | Image/thumbnail handling | Separate open-source project; current upstream license applies |
| `pystray` | Windows system tray support | Separate open-source project; current upstream license applies |
| `imageio-ffmpeg` | Obtain FFmpeg executable without manual PATH configuration | Separate package with its own license |
| FFmpeg executable | Merge audio/video and convert media | Check the **actual binary build** and its licensing obligations when distributing binaries |
| Chrome/Chromium extension APIs | Browser popup, context menu, capture and downloads | Browser-provided APIs |

Refer to upstream packages and their included license documents for the exact version-specific terms. No blanket statement is made that all dependencies use the same license. **Before publishing an installer containing bundled executables, audit the specific versions and distribute all required license notices and source offers.**

The user requested an independent downloader, not a fork of Mister Download Manager. No Mister Download Manager or IDM source is intentionally included.
