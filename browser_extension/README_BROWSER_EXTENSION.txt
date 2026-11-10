LILITH DOWNLOAD COMPANION v1.3 — CHROME / EDGE

INSTALL
1. In Lilith tray menu, select Quit. Install / launch the new v1.3 app.
2. Open chrome://extensions or edge://extensions.
3. Remove the old Lilith companion (avoids duplicate floating buttons).
4. Turn on Developer mode -> Load unpacked -> choose this browser_extension folder.
5. Open the desktop app -> Copy browser pairing key.
6. Open the extension toolbar popup -> paste pairing key -> Save pairing key.
7. Optional: check "Automatically catch Chrome file downloads".
   This is OFF by default. Chrome will request the 'downloads' permission.
8. Test with an ordinary public ZIP or .safetensors file.

USE
- If auto-capture is ON, clicking a file link that triggers a Chrome download
  will make Chrome pause. Lilith checks if its local downloader can reach the
  file without Chrome cookies. If yes, Lilith queues the download and Chrome
  cancels its own transfer. If not, Chrome resumes its download.
- Floating button over HTML5 videos offers download or video quality inspection.
- Right click a file link -> Download link with Lilith (direct file).
- Toolbar popup offers Send current tab or Inspect video qualities.

LIMITATIONS
- Chrome downloads API is not a deep network sniffer. Browser-only authenticated
  sessions, protected sites, POST downloads, DRM and blob: media may stay in Chrome.
- Chrome can finish tiny files before the extension can pause them. Such files
  remain Chrome downloads and are not incorrectly marked as Lilith downloads.
- Very rare failures can happen after Chrome has already handed off a file.
- The extension does not read browsing cookies or secret request headers.
- The Windows desktop application must be running (including in the tray).
- Never share your pairing key or private download links.
