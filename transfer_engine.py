"""Resumable direct-HTTP transfers used by Lilith Download Desk.

No third-party packages required. Chrome handoffs are probed without cookies before
Chrome is asked to stop its own transfer; inaccessible links stay in the browser.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHUNK = 128 * 1024
DIRECT_EXTENSIONS = {
    '.zip','.rar','.7z','.exe','.msi','.iso','.pdf','.apk','.tar','.gz','.bz2','.xz',
    '.bin','.dmg','.msix','.deb','.mp4','.webm','.mkv','.mov','.avi','.mp3','.flac',
    '.wav','.jpg','.jpeg','.png','.gif','.webp','.srt','.epub','.csv','.json','.txt',
    '.blend','.vrm','.pptx','.safetensors','.ckpt','.pt','.pth','.onnx','.gguf',
    '.ggml','.weights','.model','.tflite','.npz','.npy','.pth','.torrent','.parquet',
    '.sqlite','.db','.jar','.py','.psd','.kra','.mov','.flv','.heic','.otf','.ttf',
    '.docx','.xlsx','.ppt','.doc','.xls','.csv','.obj','.fbx','.glb','.gltf',
}


def sanitize(name: str) -> str:
    name = str(name or '').replace('\\', '/')
    name = name.rsplit('/', 1)[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip().rstrip('. ')
    name = name[:180] or 'download.bin'
    base = name.split('.')[0].upper()
    if base in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        name = '_' + name
    return name


def name_from_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return sanitize(urllib.parse.unquote(Path(parsed.path).name) or 'download.bin')


def is_html(content_type: str) -> bool:
    return 'text/html' in content_type.lower() or 'application/xhtml+xml' in content_type.lower()


def request_headers(referer: str = '') -> dict[str, str]:
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; LilithDownloadDesk/1.3)'}
    if referer and urllib.parse.urlsplit(referer).scheme in ('http', 'https'):
        headers['Referer'] = referer
    return headers


def probe_direct(url: str, referer: str = '', timeout: float = 7) -> tuple[bool, str]:
    """Probe a file GET with Range: bytes=0-0; never download its body.

    HEAD is deliberately not used: many file hosts reject HEAD.
    """
    if urllib.parse.urlsplit(url).scheme not in ('http', 'https'):
        return False, 'Only HTTP or HTTPS file links are supported.'
    headers = request_headers(referer)
    headers['Range'] = 'bytes=0-0'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            if is_html(content_type):
                return False, 'The link returned a webpage/login screen, not a downloadable file.'
            return True, f'Reachable ({response.status}, {content_type or "unknown type"})'
    except urllib.error.HTTPError as exc:
        return False, f'Server returned HTTP {exc.code}. It may require browser authentication or an unexpired link.'
    except (OSError, ValueError) as exc:
        return False, f'Could not reach file without browser authentication: {exc}'


def _safe_part_for(dest: Path, url: str) -> tuple[Path, Path]:
    """Pick a partial path that cannot accidentally resume another URL's bytes."""
    import hashlib
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
    return Path(str(dest) + f'.{digest}.part'), Path(str(dest) + f'.{digest}.part.json')


def download_file(url: str, folder: str | Path, preferred_filename: str = '', referer: str = '',
                  stop=None, report=None, timeout: int = 30) -> str:
    """Download file with safe HTTP Range resume and periodic UI metrics.

    report receives dict {bytes,total,speed,eta,percent}; stop is Event.
    Partial data remains on pause or failed download. Never overwrite existing files.
    """
    if urllib.parse.urlsplit(url).scheme not in ('http', 'https'):
        raise ValueError('Only HTTP and HTTPS URLs are supported.')
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    name = sanitize(preferred_filename) if preferred_filename else name_from_url(url)
    if name == 'download.bin':
        raise ValueError('No reliable filename detected. Use a direct link or Chrome capture.')
    dest = folder / name
    part, meta = _safe_part_for(dest, url)
    if dest.exists():
        raise FileExistsError(f'{name} already exists. It was not overwritten.')
    old = part.stat().st_size if part.exists() else 0
    headers = request_headers(referer)
    if old:
        headers['Range'] = f'bytes={old}-'
        if meta.exists():
            try:
                record = json.loads(meta.read_text(encoding='utf-8'))
                if record.get('url') == url and record.get('validator'):
                    headers['If-Range'] = record['validator']
            except (ValueError, OSError):
                pass
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(f'HTTP {exc.code}: This file may require a browser login, cookies or a fresh signed URL. Use Chrome to download it if needed.') from exc
        if exc.code == 416 and old:
            raise RuntimeError('Server rejected the saved resume offset (HTTP 416). Partial data was preserved.') from exc
        raise RuntimeError(f'HTTP {exc.code}: {exc.reason}') from exc
    with resp:
        if is_html(resp.headers.get('Content-Type', '')) and not name.lower().endswith(('.html', '.htm')):
            raise RuntimeError('Server returned an HTML page instead of file data (possibly a sign-in page). No invalid file was saved.')
        if old:
            if resp.status != 206:
                raise RuntimeError('This server did not honor Range resume. Partial data preserved; use a new filename for a fresh download.')
            c_range = resp.headers.get('Content-Range', '')
            match = re.fullmatch(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', c_range)
            if not match or int(match.group(1)) != old:
                raise RuntimeError('Mismatched server byte-range response. Partial data was preserved.')
            total = int(match.group(3)) if match.group(3) != '*' else None
        else:
            c_length = resp.headers.get('Content-Length')
            total = int(c_length) if c_length and c_length.isdigit() else None
            if resp.status == 206:
                c_range = resp.headers.get('Content-Range', '')
                match = re.fullmatch(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', c_range)
                if match and match.group(3) != '*':
                    total = int(match.group(3))
            validator = resp.headers.get('ETag') or resp.headers.get('Last-Modified')
            meta.write_text(json.dumps({'url': url, 'validator': validator}, ensure_ascii=False), encoding='utf-8')

        done = old
        started = time.monotonic()
        last_at = started
        last_bytes = old
        moving_speed = None

        def emit(force=False):
            nonlocal last_at, last_bytes, moving_speed
            now = time.monotonic()
            delta = now-last_at
            if not force and delta < 0.32:
                return
            instantaneous = max(0, (done-last_bytes) / max(delta, .001))
            moving_speed = instantaneous if moving_speed is None else .65 * moving_speed + .35 * instantaneous
            eta = ((total-done)/moving_speed) if total and moving_speed and moving_speed > 0 else None
            if report:
                report({'bytes':done, 'total':total, 'speed':moving_speed, 'eta':eta,
                        'percent':f'{min(100, 100*done/total):.1f}%' if total else None})
            last_bytes, last_at = done, now

        emit(force=True)
        with part.open('ab' if old else 'wb') as fout:
            while not (stop and stop.is_set()):
                block = resp.read(CHUNK)
                if not block:
                    break
                fout.write(block)
                done += len(block)
                emit()
        emit(force=True)
        if stop and stop.is_set():
            return ''
        if total is not None and done != total:
            raise RuntimeError(f'File incomplete ({done:,} of {total:,} bytes). Partial data was kept; choose Resume to try again.')
        os.replace(part, dest)
        try:
            meta.unlink(missing_ok=True)
        except OSError:
            pass
        if report:
            report({'bytes':done,'total':total or done,'speed':None,'eta':0,'percent':'100%'})
        return str(dest)
