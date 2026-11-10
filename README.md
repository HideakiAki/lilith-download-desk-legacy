<p align="center">
  <img src="./Lilith Neon Blink Animation Grid.gif" alt="Animated Lilith Download Desk Legacy banner" width="100%">
</p>

<h1 align="center">Lilith Download Desk Legacy</h1>

<p align="center">
  An archive of the original AI-assisted Windows downloader prototypes.<br>
  <strong>v1.0 through v1.3.2</strong> · Python desktop app · Chrome/Edge browser extension
</p>

<p align="center">
  <a href="#downloads">Downloads</a> ·
  <a href="#getting-started">Getting started</a> ·
  <a href="#known-limitations">Known limitations</a> ·
  <a href="#license-and-permissions">License</a>
</p>

> [!IMPORTANT]
> **Historical prototype archive, not a stable release.** The final legacy snapshot is **v1.3.2**. The upcoming **v2.0** is a separate project and is **not** included here.

## Overview

**Lilith Download Desk** is an experimental Windows download manager built with Python, a desktop interface, and a Chrome/Edge-compatible browser extension. This repository preserves the original versions, **including their unfinished features and known bugs**. It is not presented as a polished replacement for Internet Download Manager.

The **repository root contains the latest legacy source (v1.3.2)**. All six original ZIP packages are downloadable as assets attached to the [legacy archive pre-release](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/tag/legacy-archive-v1.3.2). The original version-by-version Git histories were not reconstructed; the archive tag identifies this single collection.

## Downloads

| Version | Archived package | Historical milestone |
| :--- | :--- | :--- |
| **v1.0** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1.zip) | Initial Windows/Tkinter download queue |
| **v1.1** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_1.zip) | Early browser extension and video quality controls |
| **v1.2** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_2.zip) | System tray, floating video button, and separate progress window |
| **v1.3** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_3.zip) | Direct-file transfer engine and opt-in browser interception |
| **v1.3.1** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_3_1.zip) | Media merging, file actions, and interface fixes |
| **v1.3.2** | [Download ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_3_2_No_Manual_FFmpeg.zip) | Automatic local FFmpeg preparation |

**Latest legacy package:** [Lilith Download Desk v1.3.2](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_3_2_No_Manual_FFmpeg.zip)

See [RELEASES.md](RELEASES.md) for the full version history. The six archived ZIPs are hosted as **GitHub Release assets**, outside the current source tree. Earlier commits can still contain the original ZIPs.

## Getting started

1. Download the [v1.3.2 ZIP](https://github.com/HideakiAki/lilith-download-desk-legacy/releases/download/legacy-archive-v1.3.2/Lilith_Download_Desk_v1_3_2_No_Manual_FFmpeg.zip) and extract it on **Windows**.
2. Read **`START_HERE_v1_3_2.txt`** inside the extracted folder.
3. With **Python and Tkinter** available, run **`01_Install_and_Launch.bat`**. Initial setup requires an internet connection to install Python packages and prepare a local FFmpeg executable.
4. For browser integration, read [the extension instructions](browser_extension/README_BROWSER_EXTENSION.txt) before loading the extension or granting its webpage permissions.

Older versions have their own setup instructions inside their corresponding ZIPs. No Windows/browser integration regression test has been performed for this archival publication.

## Known limitations

> [!WARNING]
> **The final browser overlay bug remains unfixed.** The floating **Download with Lilith** control may cover website navigation or login/signup buttons. It has no built-in close, minimize, or drag control.

Other limitations include:

- **Broad browser access:** the old extension runs on ordinary HTTP(S) pages, including frames. Review its permissions before using it on sensitive sites.
- **Site compatibility:** browser-authenticated downloads, expiring URLs, cookies, non-GET requests, and some media formats may not work.
- **Transfer performance:** the later direct HTTP engine uses **one connection**, not IDM-style multi-connection acceleration.
- **Unfinished workflows:** image capture, category-specific folders, download confirmation, some shortcuts, and media postprocessing are not consistently implemented.

For fuller details, read [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [SECURITY.md](SECURITY.md). Test only with non-sensitive downloads from trusted sources.

## License and permissions

**Free to use, but modification and redistribution are restricted.**

You may **view the code** and **download, install, and run unmodified copies for free**. Modifying or redistributing the covered Lilith code or original project assets requires the owner's **prior written permission**, subject to GitHub's platform rights and applicable law.

This is **source-available software, not OSI-approved open source**. Third-party libraries and tools retain their own licenses.

Read the full [LICENSE](LICENSE), [license explanation](LICENSE_STATUS.md), and [third-party dependency notes](THIRD_PARTY.md) before reusing any material.

## Project background and feedback

Lilith Download Desk was developed with **AI assistance under the project owner's direction**. It is not a fork of Internet Download Manager or Mister Download Manager; neither project's source code is intentionally included.

This archive exists so testers can inspect the earlier work and share reproducible bug reports, security observations, and suggestions. Please **do not post credentials, private URLs, or pairing keys** in public issues.

The planned **Lilith Download Desk v2.0** frontend and backend are separate future work, not features delivered by these legacy releases.
