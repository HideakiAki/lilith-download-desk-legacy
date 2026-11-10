# Known Issues (Legacy Versions)

**This list is intentionally frank. Issues are not fixed by publishing the archive.**

## Browser extension and capture

1. **Floating download control cannot be hidden or moved.** The injected `Download with Lilith` button lacks a close, minimize, drag, or per-site-disable control. It can cover site navigation, login/signup buttons, or embedded-player controls. Confirmed as the user-reported final legacy issue; observed in extension source (`browser_extension/video_button.js`).
2. **Video-focused detection.** The floating overlay is designed around HTML5 `<video>` elements. It does not provide equivalent hover/download controls for arbitrary images and page files.
3. **Interception is opt-in but imperfect.** Some files require browser cookies/session data or non-GET requests, or use ephemeral links. In these cases Lilith may fail or Chrome may need to handle the transfer.
4. **Broad content-script scope.** The extension is configured to run on ordinary HTTP(S) pages, including frames. Users should assess permissions and disable/unload it if unwanted.
5. **A successful handoff is not a guarantee of final download success.** A link may expire after the initial connectivity test.

## Downloads, queue and media

6. **Download Now / Later confirmation not implemented consistently.** Browser handoffs can create queue items without a full IDM-style dialog that confirms folder and mode.
7. **Category-based destination folders are not fully implemented.** Different file types may use the same output folder.
8. **Media merging varies by source.** v1.3.1 and v1.3.2 attempt to fix separate video/audio outputs but live-site results have not been verified in this archival review.
9. **Direct HTTP uses one connection** in the later legacy engine. Performance and resumability depend on the server; this is not a claim of IDM-equivalent acceleration.
10. **Download speed/ETA can be unknown or imperfect.** Unknown content size, interrupted transfers, and media postprocessing complicate reporting.
11. **Some UI actions and keyboard shortcuts may still misbehave.** These snapshots are not regression-tested on Windows in the archival build.

## Scope

The following are **v2.0 planning goals**, not completed legacy features: reliably dismissible overlays, broader file/image capture, category-specific folder confirmation, polished queue dialogs, minimalist crystal-violet frontend, and the planned Lilith character animations.
