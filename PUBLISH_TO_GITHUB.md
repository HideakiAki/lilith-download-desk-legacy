# Lilith Legacy: GitHub publishing and archive notes

**Current status:** Public historical source archive with a GitHub pre-release containing the six original ZIP packages.

- Repository: https://github.com/HideakiAki/lilith-download-desk-legacy
- Release: https://github.com/HideakiAki/lilith-download-desk-legacy/releases/tag/legacy-archive-v1.3.2
- Release tag: `legacy-archive-v1.3.2`
- License: Custom free-to-use license with restricted modification and redistribution; see [LICENSE](LICENSE) and [LICENSE_STATUS.md](LICENSE_STATUS.md).

## How the archive was published

The legacy source and ZIPs were originally uploaded using GitHub's website. Subsequently, all six ZIPs were attached to one GitHub **pre-release**, and the download links in [README.md](README.md) and [RELEASES.md](RELEASES.md) were updated to refer directly to those Release assets.

The duplicate ZIPs were then deleted from the tip of the `main` branch. **Deleting committed files does not erase them from Git history.** No history rewrite was attempted. The original version-specific histories were not recreated.

## Future maintenance

1. Keep ordinary source code, documentation, and small interface images in the repository.
2. Attach new installable ZIPs or binaries to **GitHub Releases**, rather than committing them to `main`.
3. Ensure the release is published and all assets are visible before changing any download links.
4. After updating links, verify that every asset name and version is correct.
5. Do not accidentally describe these legacy builds as stable or professionally security-audited.
6. Keep license notices for third-party software and avoid committing local settings, cookies, pairing keys, or download histories.

The separate planned Lilith Download Desk v2.0 rebuild is not part of this legacy archive.
