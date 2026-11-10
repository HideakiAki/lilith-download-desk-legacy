# Security & Privacy Notes

This repository contains old prototype code. **It is not certified secure.**

- Do not commit the local settings directory, actual downloads, logs, authentication cookies, browser pairing keys, or job history to a public repository. In the legacy app, local data is generally in `%LOCALAPPDATA%\LilithDownloadDesk`.
- URLs saved in download history may embed temporary tokens, so do not upload a real `jobs.json` or logs.
- The extension uses a local communication endpoint and a locally stored pairing key. Never publish your actual key.
- The extension injects a floating toolbar on a broad set of HTTP(S) pages, including frames. Review its permissions and avoid using it with sensitive sites if you are uncomfortable with that access.
- The old app/extension can download remote files. Test with files from trusted sources and scan unexpected downloads.
- Installer scripts download Python packages from the internet. Review scripts before running them.

## Archival review performed

The original six ZIP packages passed archive-integrity checks. An automated string check on their source found no recognizable private keys, typical API-key patterns, or hardcoded machine-specific `C:\Users\...` paths. This limited inspection **does not prove** the absence of vulnerabilities or all sensitive information. Python syntax was also checked without executing code. No public release environment or Windows/browser integration tests were performed here.

Please report security findings privately to the owner once a security contact is added to the GitHub repository. Do not paste credentials, signed download links, or personal paths into public issues.
