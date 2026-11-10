# Publish Lilith Legacy using the GitHub website only

No desktop app or command line is required.

1. Sign in to https://github.com/new.
2. Repository name: `lilith-download-desk-legacy`.
3. Description: `Historical Python prototypes of Lilith Download Desk (v1.0–v1.3.2)`.
4. Visibility: Public when you are ready to share it, or Private while you review.
5. Leave **Add a README**, **Add .gitignore**, and **Choose a license** set to None/off. The upload already contains README and .gitignore. No source license has been chosen yet.
6. Click **Create repository**.
7. On the new empty repository page click **uploading an existing file**; or select **Add file > Upload files** if shown.
8. Open this ZIP's extracted folder `UPLOAD_THE_CONTENTS_OF_THIS_FOLDER` on Windows.
9. Select **everything inside** the folder with Ctrl+A (not the outer folder and not the original Git-ready ZIP), then drag those selected files and folders into the GitHub web upload page.
10. Check that README.md, Lilith_Download_Desk.py, browser_extension/, and release-archives/ are in the upload list. GitHub can accept up to 100 files per upload and 25 MiB per file; this package is under those limits.
11. Enter a commit message such as `Add historical Lilith Download Desk prototypes v1.0-v1.3.2`.
12. Click **Commit changes** (or **Propose changes** if that is the label shown) and confirm repository root contents.
13. When ready, share https://github.com/YOUR_USERNAME/lilith-download-desk-legacy.

**Important**: Website-only upload creates a single initial commit, not historic version tags. All six historical ZIP files are included and clearly indexed in RELEASES.md. Version tags can be created later if desired. No binary release or professional security audit is claimed here.

**License status**: A public repository without a license is viewable, but it is not automatically licensed for reuse. Decide on an open-source license before advertising it as FOSS or inviting contributions.
