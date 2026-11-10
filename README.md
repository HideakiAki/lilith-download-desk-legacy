# Lilith Download Desk | Legacy Releases

> **Historical archive, not the upcoming v2.0 project.**

Lilith Download Desk is an experimental, AI-assisted Windows downloader with a Python desktop application and a Chrome/Edge-compatible browser extension. This repository preserves the original prototype releases **v1.0 through v1.3.2**, including their rough edges. The software is not presented as a polished IDM replacement.

## What is here?

- **Repository root**: source for the latest legacy snapshot, **v1.3.2**, plus repository documentation.
- **Previous versions**: six original ZIP packages in `release-archives/`. A website-only upload does not reproduce Git history or create version tags.
- **`release-archives/`**: the six original ZIP release packages, preserved **unchanged** for convenient download and inspection.
- **`RELEASES.md`**: release index and brief version history.
- **`KNOWN_ISSUES.md`**: important limitations, including the undismissible floating browser video button.
- **`PUBLISH_TO_GITHUB.md`**: simple website-only publishing instructions.

## Status and warnings

This is **prototype code**. Do not assume it has been professionally security audited or tested on every website. Test with non-sensitive downloads first. The latest version still has a browser-overlay bug: the floating **Download with Lilith** button can overlap website navigation or login/signup controls and has no built-in dismiss/minimize/drag setting. This issue remains **unfixed in this archive**.

The old extension also requests broad webpage access for its floating video button. Review permissions before loading it. Downloads requiring browser-only authentication, cookies, DRM, or short-lived links may not work. The built-in direct HTTP engine in later legacy versions is **single-connection**, not full IDM-style accelerated downloading.

For details, see [Known Issues](KNOWN_ISSUES.md) and [Security & Privacy](SECURITY.md).

## Quick start: latest old version

1. Obtain `release-archives/Lilith_Download_Desk_v1_3_2_No_Manual_FFmpeg.zip`.
2. Extract it; read `START_HERE_v1_3_2.txt` from inside the release.
3. Use `01_Install_and_Launch.bat` on Windows with Python and Tkinter available. Initial setup downloads Python dependencies and prepares a private FFmpeg executable; internet access is required.
4. If testing browser integration, read `browser_extension/README_BROWSER_EXTENSION.txt` and grant permissions only if you accept the risks.

For the original instructions for each historical version, extract that version's ZIP. The ZIPs are preserved as delivered; the source itself has not been repaired or modernized for this archival repository.

## Third-party tools and project origin

This project was developed with AI assistance under the project owner's direction. It is not a fork of Internet Download Manager or Mister Download Manager, and neither project's proprietary or project-specific source code is included. It uses standard Python modules and third-party packages listed in [Third-Party Dependencies](THIRD_PARTY.md). Those dependencies have their own terms.

**License decision pending.** This repository intentionally does **not** claim an open-source license until the owner chooses one. Public visibility alone does not grant permission for reuse. See [LICENSE_STATUS.md](LICENSE_STATUS.md). If you want community contributions, decide the license before inviting substantial code submissions.

## Feedback

If you are evaluating this archive to help with a future rebuild, please share reproducible bug reports, security findings, user-experience suggestions, and dependency/license observations. The **new v2.0 frontend/backend is a separate, future effort** and is not included here.
