#!/usr/bin/env python3
"""Lilith Download Desk: local Windows video/file download queue.

Requires Python 3.11+ and yt-dlp; a private FFmpeg is installed automatically.
Adds local browser companion receiver and video quality inspection.
"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import socket
import ctypes
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from transfer_engine import download_file, probe_direct, DIRECT_EXTENSIONS as FILE_EXTENSIONS, sanitize as sanitize_chrome_filename
from media_pipeline import ffmpeg_executable, ffprobe_executable, selection_for, verify_combined, merge_existing
from media_runtime import prepare_media_engine

APP_NAME = "Lilith Download Desk"
APP_VERSION = "1.3.2"
APP_DIR = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local")) / "LilithDownloadDesk"
JOBS_FILE = APP_DIR / "jobs.json"
SETTINGS_FILE = APP_DIR / "settings.json"
DEFAULT_DOWNLOADS = Path.home() / "Downloads" / "Lilith Downloads"
DIRECT_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".exe", ".msi", ".iso", ".pdf", ".apk",
    ".tar", ".gz", ".bz2", ".xz", ".bin", ".dmg", ".msix", ".deb",
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".mp3", ".flac",
    ".wav", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".srt",
    ".epub", ".csv", ".json", ".txt", ".blend", ".vrm", ".pptx",
}
BG = "#16131f"
PANEL = "#231b31"
FG = "#efe7fb"
MUTED = "#b8a8ca"
ACCENT = "#a86be3"
ACCENT_2 = "#7d4ac0"
HIGHLIGHT = "#f4d7ff"
ERROR = "#f1a5aa"
SERVER_PORT = 51234
MUTEX_HANDLE = None


def url_is_valid(value: str) -> bool:
    try:
        p = urllib.parse.urlsplit(value)
        return p.scheme.lower() in ("http", "https") and bool(p.netloc)
    except ValueError:
        return False


def detect_mode(url: str, requested: str) -> str:
    if requested in ("Video page", "Direct file"):
        return "video" if requested == "Video page" else "file"
    ext = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).suffix.lower()
    return "file" if ext in (DIRECT_EXTENSIONS | FILE_EXTENSIONS) else "video"


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(". ")
    if not name or name in {".", ".."}:
        name = "download.bin"
    root = name.split(".")[0].upper()
    if root in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "_" + name
    return name[:180]


def direct_filename(url: str) -> str:
    filename = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).name
    return safe_filename(filename or "download.bin")


def parse_percent(line: str) -> str | None:
    hits = re.findall(r"(?<!\d)(\d{1,3}(?:\.\d+)?)%", line)
    if hits:
        value = float(hits[-1])
        if 0 <= value <= 100:
            return f"{value:.1f}%"
    return None


def subprocess_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess_flags(), timeout=6,
            )
        else:
            proc.terminate()
        if proc.poll() is None:
            proc.terminate()
    except (OSError, subprocess.TimeoutExpired):
        try:
            proc.terminate()
        except OSError:
            pass


def human_bytes(num):
    try:
        amount = float(num)
    except (ValueError, TypeError):
        return "Unknown"
    if amount < 0:
        return "Unknown"
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or suffix == "TiB":
            return f"{amount:.1f} {suffix}" if suffix != "B" else f"{int(amount)} B"
        amount /= 1024


def human_eta(seconds):
    try:
        sec = int(float(seconds))
    except (ValueError, TypeError, OverflowError):
        return "Unknown"
    if sec < 0:
        return "Unknown"
    h, rem = divmod(sec, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sec:02d}s" if m else f"{sec}s"


def optional_float(value):
    try:
        f = float(value)
        return f if f >= 0 and f < float("inf") else None
    except (ValueError, TypeError):
        return None


def parse_yt_metrics(raw):
    if not raw.startswith("LL_PROGRESS:"):
        return None
    fields = raw[len("LL_PROGRESS:"):].split("|")
    if len(fields) != 5:
        return None
    got, total, estimate, speed, eta = map(optional_float, fields)
    total = total if total and total > 0 else estimate
    return {"bytes": got, "total": total, "speed": speed, "eta": eta}


def parse_aria_metrics(raw):
    # aria2 periodically prints: [#GID 24MiB/123MiB(19%) CN:8 DL:4.2MiB ETA:25s]
    pct = parse_percent(raw)
    if not pct:
        return None
    speed = None
    match = re.search(r"\bDL:([0-9.]+)([KMGTP]?i?B)", raw, re.I)
    if match:
        multiplier = {"B":1, "KIB":1024, "MIB":1024**2, "GIB":1024**3, "KB":1000, "MB":1000**2, "GB":1000**3}
        speed = float(match.group(1)) * multiplier.get(match.group(2).upper(), 1)
    eta = None
    match = re.search(r"\bETA:((?:(?:\d+h)?(?:\d+m)?(?:\d+s)?)|\d+)", raw)
    if match:
        phrase = match.group(1)
        sec = 0
        units = re.findall(r"(\d+)([hms])", phrase)
        if units:
            sec = sum(int(n) * {"h":3600,"m":60,"s":1}[u] for n,u in units)
        elif phrase.isdigit():
            sec = int(phrase)
        eta = sec
    return {"percent":pct, "speed":speed, "eta":eta}


class DownloadDesk:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        screen_w = max(1024, self.root.winfo_screenwidth())
        screen_h = max(650, self.root.winfo_screenheight())
        self.root.geometry(f"{min(1320, screen_w-50)}x{min(780, screen_h-105)}")
        self.root.minsize(min(1050, screen_w-60), min(640, screen_h-110))
        self.root.configure(background=BG)
        self.events: queue.Queue = queue.Queue()
        self.jobs: list[dict] = []
        self.active_job_id: str | None = None
        self.active_stop: threading.Event | None = None
        self.active_proc: subprocess.Popen | None = None
        self.conversion_proc: subprocess.Popen | None = None
        self.converting = False
        self.running = True
        self.auto_run = False
        self.progress_window = None
        self.progress_for_id = None
        self.progress_title_var = None
        self.progress_state_var = None
        self.progress_speed_var = None
        self.progress_bytes_var = None
        self.progress_eta_var = None
        self.progress_pct_var = None
        self.progress_bar = None
        self.tray_icon = None
        self.initial_tray = '--tray' in sys.argv
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.settings = {
            "receiver_enabled": True,
            "receiver_port": SERVER_PORT,
            "last_format_id": "",
            "last_format_label": "Auto / best available",
            "last_format_url": "",
            "receiver_token": "",
            "show_progress_on_start": True,
            "start_with_windows": False,
            "capture_direct_default": True,
            "ffmpeg_path": "",
        }
        self.format_map: dict[str, str] = {}
        self.format_details = {}
        self.trim_start = tk.StringVar()
        self.trim_duration = tk.StringVar()
        self.ffmpeg_status = tk.StringVar(value="Media engine: checking...")
        self.video_tools_window = None
        self.log_view_window = None
        self.log_view_text = None
        self.status_var = tk.StringVar(value="Ready")
        self._restore_settings()
        if not self.settings.get("receiver_token"):
            self.settings["receiver_token"] = secrets.token_urlsafe(32)
            self._save_settings()
        self._restore()
        self._style()
        self._create_ui()
        self._refresh_tree()
        self._bind_shortcuts()
        self.root.after(120, self._pump)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._init_tray()
        if self.initial_tray and self.tray_icon is not None:
            self.root.after(180, self._hide_main)
        self._log("Welcome home, Master. Lilith is ready to catch downloads for you. ♡")
        if self.tray_icon is None:
            self._log("Tray is unavailable: install Pillow and pystray to enable background mode.")
        self._log("yt-dlp handles videos; native direct-file engine reports progress and resumes partial files.")
        if self._find_ffmpeg() is None:
            self._log("Automatic media engine is missing. Quit Lilith and run Install_and_Launch.bat; no separate FFmpeg installation is needed.")
        self._log("New Chrome interception is opt-in from the extension popup; browser fallback stays available.")
        if self.receiver_enabled_var.get():
            self._start_receiver(initial=True)

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Card.TLabel", background=PANEL, foreground=FG)
        s.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground=HIGHLIGHT)
        s.configure("Secondary.TLabel", foreground=MUTED)
        s.configure("PanelTitle.TLabel", background=PANEL, foreground=HIGHLIGHT, font=("Segoe UI Semibold", 11))
        s.configure("TButton", padding=(11, 7), background=PANEL, foreground=FG, borderwidth=1)
        s.map("TButton", background=[("active", "#413051")])
        s.configure("Accent.TButton", background=ACCENT_2, foreground="white")
        s.map("Accent.TButton", background=[("active", ACCENT)])
        s.configure("TEntry", fieldbackground="#2a2238", foreground=FG, insertcolor=FG)
        s.configure("TCombobox", fieldbackground="#2a2238", background=PANEL, foreground=FG)
        s.map("TCombobox", fieldbackground=[("readonly", "#2a2238")], foreground=[("readonly", FG)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=28, borderwidth=0)
        s.map("Treeview", background=[("selected", "#68468a")], foreground=[("selected", "white")])
        s.configure("Treeview.Heading", background="#332a43", foreground=FG, relief="flat")
        s.configure("TCheckbutton", background=BG, foreground=FG)

    def _create_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Lilith Download Desk ♡", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Background download manager • Chrome interception • AI-ready videos", style="Secondary.TLabel").pack(anchor="w")
        ttk.Label(header, textvariable=self.status_var, style="Secondary.TLabel").pack(anchor="w", pady=(3,0))

        top = ttk.Frame(main)
        top.pack(fill="both", expand=True)
        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(top, width=300)
        right.pack(side="left", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        entry = ttk.Frame(left)
        entry.pack(fill="x")
        ttk.Label(entry, text="Download URL").pack(side="left", padx=(0, 9))
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(entry, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(entry, text="Paste", command=self._paste).pack(side="left", padx=(8, 0))

        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=(8, 6))
        ttk.Label(controls, text="Type").pack(side="left")
        self.mode_var = tk.StringVar(value="Auto detect")
        ttk.Combobox(controls, textvariable=self.mode_var, state="readonly", width=14,
                     values=["Auto detect", "Video page", "Direct file"]).pack(side="left", padx=(7, 16))
        ttk.Label(controls, text="Quick quality").pack(side="left")
        self.quality_var = tk.StringVar(value="Best")
        ttk.Combobox(controls, textvariable=self.quality_var, state="readonly", width=12,
                     values=["Best", "1080p max", "720p max"]).pack(side="left", padx=(7, 16))
        ttk.Label(controls, text="Browser login").pack(side="left")
        self.cookie_var = tk.StringVar(value="None")
        ttk.Combobox(controls, textvariable=self.cookie_var, state="readonly", width=11,
                     values=["None", "Chrome", "Edge", "Firefox", "Brave"]).pack(side="left", padx=(7, 16))
        ttk.Button(controls, text="Inspect qualities", command=self._inspect_qualities).pack(side="left")

        self.selected_format_label = tk.StringVar(value=self.settings.get("last_format_label", "Auto / best available"))
        ttk.Label(left, textvariable=self.selected_format_label, style="Secondary.TLabel").pack(anchor="w", pady=(0, 8))

        folder_line = ttk.Frame(left)
        folder_line.pack(fill="x", pady=(0, 10))
        ttk.Label(folder_line, text="Save to").pack(side="left", padx=(0, 11))
        self.folder_var = tk.StringVar(value=str(DEFAULT_DOWNLOADS))
        ttk.Entry(folder_line, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_line, text="Browse", command=self._browse_folder).pack(side="left", padx=(8, 0))
        ttk.Button(folder_line, text="Open folder", command=self._open_folder).pack(side="left", padx=(7, 0))

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(0, 12))
        ttk.Button(buttons, text="+ Add download", style="Accent.TButton", command=self._add).pack(side="left", padx=(0, 9))
        ttk.Button(buttons, text="▶ Start queue", command=self._start).pack(side="left", padx=(0, 9))
        ttk.Button(buttons, text="Ⅱ Pause selected", command=self._pause_selected).pack(side="left", padx=(0, 9))
        ttk.Button(buttons, text="↻ Resume selected", command=self._resume_selected).pack(side="left", padx=(0, 9))
        ttk.Button(buttons, text="Remove", command=self._remove_selected).pack(side="left")
        ttk.Button(buttons, text="Error details", command=self._show_selected_error).pack(side="left", padx=(9,0))
        file_actions = ttk.Frame(left)
        file_actions.pack(fill="x", pady=(0, 8))
        ttk.Button(file_actions, text="📂 Show in folder", command=self._show_selected_file_in_folder).pack(side="left", padx=(0, 8))
        ttk.Button(file_actions, text="▶ Open selected file", command=self._open_selected_file).pack(side="left")
        ttk.Button(file_actions, text="Video Tools", command=self._show_video_tools).pack(side="left", padx=(0,8))
        ttk.Button(file_actions, text="View log", command=self._show_log).pack(side="left")

        self.tree = ttk.Treeview(left, columns=("mode", "status", "progress", "speed", "folder"), show="tree headings", height=10)
        self.tree.heading("#0", text="Link / File")
        self.tree.heading("mode", text="Type")
        self.tree.heading("status", text="Status")
        self.tree.heading("progress", text="Progress")
        self.tree.heading("speed", text="Speed")
        self.tree.heading("folder", text="Destination")
        self.tree.column("#0", width=320, stretch=True)
        self.tree.column("mode", width=85, stretch=False)
        self.tree.column("status", width=105, stretch=False)
        self.tree.column("progress", width=90, stretch=False)
        self.tree.column("speed", width=110, stretch=False)
        self.tree.column("folder", width=230, stretch=True)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._update_selection)
        self.tree.bind("<Double-1>", self._double_click_job)
        self.tree.bind("<Button-3>", self._tree_context_menu)
        self.tree.bind("<Delete>", self._delete_shortcut)
        self.tree.bind("<Return>", self._enter_shortcut)

        self.main_progress_bar = ttk.Progressbar(left, mode="determinate", maximum=100)
        self.main_progress_bar.pack(fill="x", pady=(7, 2))
        self.main_progress_info = tk.StringVar(value="Select a download to see bytes, speed and ETA")
        ttk.Label(left, textvariable=self.main_progress_info, style="Secondary.TLabel").pack(anchor="w", pady=(0, 4))

        # Persistent hidden log buffer. View log opens a readable separate window.
        self.log_box = tk.Text(left, height=1, bg="#15121d", fg="#d3c5e4", insertbackground=FG,
                               font=("Consolas", 9), wrap="word", state="disabled", relief="flat")

        info = tk.Frame(right, bg=PANEL, bd=0, highlightthickness=1, highlightbackground="#312544")
        info.pack(fill="y", expand=True)
        info.grid_columnconfigure(0, weight=1)
        tk.Label(info, text="Lilith Companion", bg=PANEL, fg=HIGHLIGHT, font=("Segoe UI Semibold", 12)).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 2))
        tk.Label(info, text="Browser handoff and download formats ♡", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=250, justify="left").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self.receiver_enabled_var = tk.BooleanVar(value=bool(self.settings.get("receiver_enabled", True)))
        ttk.Checkbutton(info, text="Listen for browser extension links", variable=self.receiver_enabled_var,
                        command=self._toggle_receiver).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 6))
        self.receiver_status_var = tk.StringVar(value="Receiver idle")
        tk.Label(info, textvariable=self.receiver_status_var, bg=PANEL, fg=FG, justify="left", wraplength=280,
                 font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))
        ttk.Button(info, text="Copy browser pairing key", command=self._copy_pairing_key).grid(row=4, column=0, sticky="w", padx=12, pady=(0, 10))
        self.autostart_var = tk.BooleanVar(value=self._start_with_windows_enabled())
        ttk.Checkbutton(info, text="Start hidden with Windows", variable=self.autostart_var,
                        command=self._toggle_autostart).grid(row=9, column=0, sticky="w", padx=12, pady=(4, 2))
        self.auto_progress_var = tk.BooleanVar(value=bool(self.settings.get("show_progress_on_start", True)))
        ttk.Checkbutton(info, text="Show separate progress window", variable=self.auto_progress_var,
                        command=self._toggle_progress_pref).grid(row=10, column=0, sticky="w", padx=12, pady=(0, 10))
        ttk.Button(info, text="Open download progress", command=self._open_progress_window).grid(row=11, column=0, sticky="w", padx=12, pady=(0, 10))

        tk.Label(info, text="Inspected video formats", bg=PANEL, fg=HIGHLIGHT, font=("Segoe UI Semibold", 11), wraplength=250).grid(row=5, column=0, sticky="w", padx=12, pady=(8, 6))
        self.format_list = tk.Listbox(info, height=16, bg="#1a1424", fg=FG, selectbackground="#69408a", selectforeground="white",
                                      relief="flat", highlightthickness=1, highlightbackground="#312544")
        self.format_list.grid(row=6, column=0, sticky="nsew", padx=12)
        info.grid_rowconfigure(6, weight=1)
        btns = ttk.Frame(info)
        btns.grid(row=7, column=0, sticky="ew", padx=12, pady=10)
        ttk.Button(btns, text="Use selected quality", command=self._use_selected_format).pack(fill="x", pady=(0,4))
        ttk.Button(btns, text="Clear quality override", command=self._clear_selected_format).pack(fill="x")

        tip = (
            "Tip:\n"
            "• For supported video pages, click Inspect qualities first.\n"
            "• The browser companion can send the current tab directly to Lilith.\n"
            "• For private sites, use Browser login when yt-dlp supports it."
        )
        tk.Label(info, text=tip, bg=PANEL, fg=MUTED, justify="left", wraplength=280, font=("Segoe UI", 9)).grid(row=8, column=0, sticky="w", padx=12, pady=(0, 12))

        ttk.Label(left, text="Shortcuts: Enter add/start  •  Delete remove  •  Ctrl+J progress  •  Ctrl+R resume  •  F5 start",
                  style="Secondary.TLabel").pack(anchor="w", pady=(4,0))
        self._create_menu()
        self.url_entry.focus_set()

    def _bind_shortcuts(self):
        self.root.bind("<F5>", lambda _e: self._start())
        self.root.bind("<Control-j>", lambda _e: self._open_progress_window())
        self.root.bind("<Control-r>", lambda _e: self._resume_selected())
        self.root.bind("<Control-p>", lambda _e: self._pause_selected())
        self.root.bind("<Control-o>", lambda _e: self._open_selected_file())
        self.root.bind("<Control-Shift-O>", lambda _e: self._show_selected_file_in_folder())
        self.url_entry.bind("<Return>", lambda _e: self._add())
        # Do not steal Delete or Enter from focused text fields.

    def _delete_shortcut(self, _event=None):
        if self._selected():
            self._remove_selected()
        return "break"

    def _enter_shortcut(self, _event=None):
        job = self._selected()
        if job and job.get("status") in ("Failed", "Paused"):
            self._resume_selected()
        elif job and job.get("status") == "Queued":
            self._start()
        elif job and job.get("status") == "Completed":
            self._open_selected_file()
        elif job:
            self._open_progress_window(job)
        return "break"

    def _show_selected_error(self):
        job = self._selected()
        if not job:
            messagebox.showinfo("Error details", "Select a download first.")
            return
        detail = job.get("last_error") or "No error recorded for this download."
        messagebox.showinfo("Download details", f"{job.get('title') or job.get('filename') or job.get('url')}\n\nStatus: {job.get('status')}\n\n{detail}")

    def _create_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Open selected file", command=self._open_selected_file)
        file_menu.add_command(label="Show selected in folder", command=self._show_selected_file_in_folder)
        file_menu.add_command(label="Open downloads folder", command=self._open_folder)
        menu.add_cascade(label="File", menu=file_menu)
        download_menu = tk.Menu(menu, tearoff=0)
        download_menu.add_command(label="Start queue     F5", command=self._start)
        download_menu.add_command(label="Pause selected     Ctrl+P", command=self._pause_selected)
        download_menu.add_command(label="Resume selected     Ctrl+R", command=self._resume_selected)
        menu.add_cascade(label="Downloads", menu=download_menu)
        tools_menu = tk.Menu(menu, tearoff=0)
        tools_menu.add_command(label="Video Tools / Merge split tracks...", command=self._show_video_tools)
        tools_menu.add_command(label="Download progress     Ctrl+J", command=self._open_progress_window)
        tools_menu.add_command(label="View diagnostic log", command=self._show_log)
        menu.add_cascade(label="Tools", menu=tools_menu)
        self.root.configure(menu=menu)

    def _show_log(self):
        win = self.log_view_window
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = tk.Toplevel(self.root)
        self.log_view_window = win
        win.title("Lilith ♡ Download Log")
        win.geometry("820x420")
        win.configure(background=BG)
        box = tk.Text(win, bg="#15121d", fg="#d3c5e4", insertbackground=FG,
                      font=("Consolas", 10), wrap="word", relief="flat")
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", self.log_box.get("1.0", "end-1c"))
        box.configure(state="disabled")
        self.log_view_text = box
        def closed():
            self.log_view_text = None
            self.log_view_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", closed)

    def _show_video_tools(self):
        win = self.video_tools_window
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return
        win = tk.Toplevel(self.root)
        self.video_tools_window = win
        win.title("Lilith ♡ Video Tools")
        win.geometry("620x310")
        win.minsize(520, 290)
        win.configure(background=BG)
        frame = ttk.Frame(win, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Video Tools", style="Title.TLabel").pack(anchor="w", pady=(0,4))
        ttk.Label(frame, text="Recover split audio/video streams or prepare MP4 clips for AI sharing.",
                  style="Secondary.TLabel").pack(anchor="w", pady=(0,14))
        ff_row = ttk.Frame(frame)
        ff_row.pack(fill="x", pady=(0, 12))
        self.ffmpeg_status.set("Media engine: ready" if self._find_ffmpeg() else "Media engine: needs setup")
        ttk.Label(ff_row, textvariable=self.ffmpeg_status).pack(side="left", padx=(0, 12))
        ttk.Button(ff_row, text="Check / repair media engine", command=self._repair_media_engine).pack(side="left")
        ttk.Button(ff_row, text="Custom FFmpeg (optional)", command=self._choose_ffmpeg).pack(side="left", padx=(8,0))
        ttk.Button(frame, text="Merge existing video + audio into MP4", command=self._merge_existing_dialog).pack(anchor="w", pady=(0, 15))
        trim_row = ttk.Frame(frame)
        trim_row.pack(fill="x", pady=(0,8))
        ttk.Label(trim_row, text="Trim start (sec)").pack(side="left")
        ttk.Entry(trim_row, width=10, textvariable=self.trim_start).pack(side="left", padx=(8, 16))
        ttk.Label(trim_row, text="Duration (sec)").pack(side="left")
        ttk.Entry(trim_row, width=10, textvariable=self.trim_duration).pack(side="left", padx=(8,0))
        ttk.Button(frame, text="Convert / compress selected video to MP4 (H.264, 720p)",
                   command=self._convert_dialog).pack(anchor="w", pady=(6,0))

    def _paste(self):
        try:
            self.url_var.set(self.root.clipboard_get().strip())
        except tk.TclError:
            messagebox.showinfo("Clipboard", "No text URL is available on the clipboard.")

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def _open_folder(self):
        folder = Path(self.folder_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror("Open folder", str(exc))

    def _find_ffmpeg(self) -> str | None:
        return ffmpeg_executable(self.settings.get("ffmpeg_path", ""), Path(__file__).parent)

    def _repair_media_engine(self):
        self.ffmpeg_status.set("Media engine: checking...")
        self._log("Checking Lilith's private media engine...")
        threading.Thread(target=self._repair_media_worker, daemon=True).start()

    def _repair_media_worker(self):
        try:
            target = prepare_media_engine(repair=True)
            self.events.put(("media_engine_ready", target))
        except Exception as exc:
            self.events.put(("media_engine_error", str(exc)))

    def _choose_ffmpeg(self):
        picked = filedialog.askopenfilename(title="Locate FFmpeg executable", filetypes=[("FFmpeg", "ffmpeg.exe ffmpeg"), ("All files", "*.*")])
        if not picked:
            return
        try:
            proc = subprocess.run([picked, "-version"], capture_output=True, text=True, timeout=8,
                                  creationflags=subprocess_flags())
            if proc.returncode != 0 or "ffmpeg version" not in proc.stdout.lower():
                raise RuntimeError("This file is not a working FFmpeg executable.")
            self.settings["ffmpeg_path"] = picked
            self._save_settings()
            self.ffmpeg_status.set("Media engine: ready")
            self._log("FFmpeg location saved: " + picked)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            messagebox.showerror("FFmpeg check failed", str(exc))

    def _selected_output(self):
        job = self._selected()
        if not job:
            messagebox.showinfo("Select download", "Select a download in the list first.")
            return None
        output = job.get("output") or ""
        if output and Path(output).is_file():
            return Path(output)
        if job.get("status") == "Completed":
            messagebox.showerror("File missing", "This job is completed but the output file was moved or deleted.\n\n" + output)
        else:
            messagebox.showinfo("File not ready", "The selected download has not completed yet.")
        return None

    def _open_selected_file(self):
        path = self._selected_output()
        if path is None:
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Open file", str(exc))

    def _show_selected_file_in_folder(self):
        path = self._selected_output()
        if path is None:
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except OSError as exc:
            messagebox.showerror("Show in folder", str(exc))

    def _double_click_job(self, _event=None):
        job = self._selected()
        if job and job.get("status") == "Completed":
            self._open_selected_file()
        else:
            self._open_progress_window(job)

    def _tree_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        self._update_selection()
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label="Open file", command=self._open_selected_file)
        menu.add_command(label="Show in folder", command=self._show_selected_file_in_folder)
        menu.add_separator()
        menu.add_command(label="Download details", command=self._show_selected_error)
        menu.add_command(label="Resume", command=self._resume_selected)
        menu.add_command(label="Pause", command=self._pause_selected)
        menu.add_command(label="Remove from list", command=self._remove_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _current_format_id(self) -> str:
        return str(self.settings.get("last_format_id", "") or "")

    def _add(self, external_url: str | None = None, external_title: str | None = None):
        url = (external_url or self.url_var.get()).strip()
        if not url_is_valid(url):
            messagebox.showerror("Invalid URL", "Paste a full http:// or https:// URL.")
            return
        folder = str(Path(self.folder_var.get()).expanduser())
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Folder error", str(exc))
            return
        mode = detect_mode(url, self.mode_var.get())
        selected_fid = self._current_format_id() if mode == "video" and url == self.settings.get("last_format_url") else ""
        job = {
            "id": str(uuid.uuid4()), "url": url, "mode": mode, "folder": folder,
            "quality": self.quality_var.get(), "cookies": self.cookie_var.get(),
            "status": "Queued", "progress": "0%", "output": "", "title": external_title or "",
            "format_id": selected_fid,
            "format_has_audio": bool(self.settings.get("last_format_has_audio", False)) if selected_fid else False,
            "format_audio_only": bool(self.settings.get("last_format_audio_only", False)) if selected_fid else False,
            "format_label": self.settings.get("last_format_label", "Auto / best available") if selected_fid else "Auto / best available",
            "speed": None, "eta": None, "bytes": None, "total": None,
            "filename": "", "referer": "", "last_error": "",
        }
        self.jobs.append(job)
        self._save()
        self._refresh_tree()
        self.tree.selection_set(job["id"])
        self.tree.see(job["id"])
        self.url_var.set("")
        host = urllib.parse.urlsplit(url).netloc
        self._log(f"Added {mode} download: {external_title or host}")
        if external_url is None and self.auto_run:
            self._maybe_start_next()

    def _selected(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return next((x for x in self.jobs if x["id"] == selected[0]), None)

    def _update_selection(self, _event=None):
        job = self._selected()
        if job:
            extra = f" [{job.get('format_label')}]" if job.get("format_id") else ""
            self.status_var.set(f"{job['status']}: {job['url'][:110]}{extra}")
        self._update_main_progress(job)

    def _update_main_progress(self, job=None):
        if not hasattr(self, "main_progress_bar"):
            return
        job = job or self._selected()
        if job is None:
            self.main_progress_info.set("Select a download to see bytes, speed and ETA")
            return
        percent = str(job.get("progress", "0%"))
        match = re.match(r"^([0-9]+(?:\.[0-9]+)?)%$", percent)
        if job.get("status") == "Downloading" and not match:
            self.main_progress_bar.configure(mode="indeterminate")
            self.main_progress_bar.start(20)
        else:
            self.main_progress_bar.stop()
            self.main_progress_bar.configure(mode="determinate")
            self.main_progress_bar["value"] = float(match.group(1)) if match else 0
        speed = human_bytes(job.get("speed")) + "/s" if job.get("speed") is not None else "—"
        self.main_progress_info.set(
            f"{job.get('status','Queued')}  •  {percent}  •  {human_bytes(job.get('bytes'))} / {human_bytes(job.get('total'))}"
            f"  •  {speed}  •  ETA {human_eta(job.get('eta'))}")

    def _refresh_tree(self):
        old = self.tree.selection() if hasattr(self, "tree") else ()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for job in self.jobs:
            display = job.get("title") or (Path(job["output"]).name if job.get("output") else job["url"].split("?")[0])
            if len(display) > 110:
                display = display[:107] + "..."
            self.tree.insert("", "end", iid=job["id"], text=display, values=(
                job["mode"], job["status"], job["progress"], (human_bytes(job.get("speed")) + "/s" if job.get("speed") is not None else "—"), job["folder"]
            ))
        for iid in old:
            if self.tree.exists(iid):
                self.tree.selection_add(iid)
        if hasattr(self, "main_progress_bar"):
            self._update_main_progress()

    def _refresh_row(self, job: dict):
        if self.tree.exists(job["id"]):
            display = job.get("title") or (Path(job["output"]).name if job.get("output") else job["url"].split("?")[0])
            if len(display) > 110:
                display = display[:107] + "..."
            self.tree.item(job["id"], text=display, values=(job["mode"], job["status"], job["progress"], (human_bytes(job.get("speed")) + "/s" if job.get("speed") is not None else "—"), job["folder"]))
        if self.tree.selection() and job["id"] in self.tree.selection():
            self._update_main_progress(job)

    def _start(self):
        self.auto_run = True
        self._maybe_start_next()

    def _maybe_start_next(self):
        if not self.running or not self.auto_run or self.active_job_id:
            return
        job = next((x for x in self.jobs if x["status"] == "Queued"), None)
        if job is None:
            self.auto_run = False
            self.status_var.set("Queue finished with errors; select a failed job → Error details" if any(j.get("status") == "Failed" for j in self.jobs) else "Queue complete")
            return
        self.active_job_id = job["id"]
        self.active_stop = threading.Event()
        job["status"] = "Downloading"
        self._refresh_row(job)
        self._save()
        self._open_progress_window(job, automatic=True)
        self.status_var.set(f"Downloading: {urllib.parse.urlsplit(job['url']).netloc}")
        threading.Thread(target=self._download_worker, args=(job.copy(), self.active_stop), daemon=True).start()

    def _pause_selected(self):
        job = self._selected()
        if not job:
            return
        if job["status"] == "Downloading" and job["id"] == self.active_job_id:
            job["status"] = "Pausing"
            if self.active_stop:
                self.active_stop.set()
            stop_process(self.active_proc)
        elif job["status"] == "Queued":
            job["status"] = "Paused"
        self._refresh_row(job)
        self._save()

    def _resume_selected(self):
        job = self._selected()
        if not job or job["status"] not in ("Paused", "Failed"):
            return
        job["status"] = "Queued"
        self._refresh_row(job)
        self._save()
        self.auto_run = True
        self._maybe_start_next()

    def _remove_selected(self):
        job = self._selected()
        if not job:
            return
        if job["id"] == self.active_job_id:
            messagebox.showinfo("Pause first", "Pause this download, then remove it. Partial files are never deleted automatically.")
            return
        self.jobs = [x for x in self.jobs if x["id"] != job["id"]]
        self._refresh_tree()
        self._save()
        self._maybe_start_next()

    def _inspect_qualities(self):
        url = self.url_var.get().strip()
        if not url_is_valid(url):
            messagebox.showerror("Invalid URL", "Paste a supported video page URL first.")
            return
        self.format_list.delete(0, "end")
        self.format_map = {}
        self.format_details = {}
        self.format_list.insert("end", "Inspecting… please wait")
        threading.Thread(target=self._inspect_worker, args=(url, self.cookie_var.get()), daemon=True).start()

    def _inspect_worker(self, url: str, cookie_mode: str):
        try:
            try:
                import yt_dlp  # noqa: F401
            except ImportError as exc:
                raise RuntimeError("yt-dlp is missing. Run Install_and_Launch.bat first.") from exc
            cmd = [sys.executable, "-m", "yt_dlp", "--dump-single-json", "--no-warnings", "--no-playlist", "--", url]
            if cookie_mode != "None":
                cmd[3:3] = ["--cookies-from-browser", cookie_mode.lower()]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  creationflags=subprocess_flags(), timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Unable to inspect formats.")
            info = json.loads(proc.stdout)
            formats = info.get("formats") or []
            title = info.get("title") or urllib.parse.urlsplit(url).netloc
            rows = []
            details = {}
            seen = set()
            for f in formats:
                fid = str(f.get("format_id", ""))
                ext = f.get("ext") or "?"
                height = f.get("height")
                width = f.get("width")
                vcodec = f.get("vcodec") or "?"
                acodec = f.get("acodec") or "?"
                proto = f.get("protocol") or "?"
                approx = f.get("filesize") or f.get("filesize_approx")
                note = f.get("format_note") or ""
                fps = f.get("fps")
                if not fid or fid in seen:
                    continue
                seen.add(fid)
                details[fid] = {"has_audio": acodec != "none", "audio_only": vcodec == "none"}
                if vcodec == "none":
                    kind = "audio"
                    res = "audio only"
                else:
                    kind = "video"
                    res = f"{width or '?'}x{height or '?'}"
                size = f"{approx / (1024*1024):.1f} MiB" if isinstance(approx, (int, float)) else "?"
                fps_txt = f" {int(fps)}fps" if fps else ""
                label = f"{fid} — {res}{fps_txt} — {ext} — {kind} — {size} — {note or proto}"
                rows.append((0 if kind == 'video' else 1, -(height or 0), label, fid))
            rows.sort()
            items = [r[2:] for r in rows[:120]]
            self.events.put(("formats", title, items, details))
        except Exception as exc:
            self.events.put(("formats_error", str(exc)))

    def _use_selected_format(self):
        sel = self.format_list.curselection()
        if not sel:
            return
        label = self.format_list.get(sel[0])
        fid = self.format_map.get(label)
        if not fid:
            return
        self.settings["last_format_id"] = fid
        self.settings["last_format_has_audio"] = bool(self.format_details.get(fid, {}).get("has_audio", False))
        self.settings["last_format_audio_only"] = bool(self.format_details.get(fid, {}).get("audio_only", False))
        self.settings["last_format_label"] = label
        self.settings["last_format_url"] = self.url_var.get().strip()
        self.selected_format_label.set(f"Selected format override: {label}")
        self._save_settings()
        self._log(f"Selected format override set: {label}")

    def _clear_selected_format(self):
        self.settings["last_format_id"] = ""
        self.settings["last_format_has_audio"] = False
        self.settings["last_format_audio_only"] = False
        self.settings["last_format_label"] = "Auto / best available"
        self.settings["last_format_url"] = ""
        self.selected_format_label.set("Selected format override: Auto / best available")
        self._save_settings()
        self._log("Format override cleared. New video jobs will use the quick quality selector again.")

    def _download_worker(self, job: dict, stop: threading.Event):
        try:
            if job["mode"] == "video":
                output = self._download_video(job, stop)
            else:
                output = self._download_python(job, stop)
            self.events.put(("done", job["id"], bool(not stop.is_set()), output or ""))
        except Exception as exc:
            self.events.put(("error", job["id"], str(exc)))

    def _run_command(self, cmd: list[str], job: dict, stop: threading.Event) -> str:
        output = ""
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                bufsize=1, creationflags=subprocess_flags())
        self.active_proc = proc
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                if stop.is_set():
                    stop_process(proc)
                    break
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("OUTPUT_FILE:"):
                    output = line.split(":", 1)[1].strip()
                if job["mode"] == "video" and ("[Merger]" in line or "Merging formats into" in line):
                    self.events.put(("progress", job["id"], "Merging audio + video..."))
                    self.events.put(("metrics", job["id"], {"speed": None, "eta": None}))
                percent = parse_percent(line)
                if percent and ("[download]" in line or "%" in line):
                    self.events.put(("progress", job["id"], percent))
                yt_metrics = parse_yt_metrics(line)
                if yt_metrics is not None:
                    self.events.put(("metrics", job["id"], yt_metrics))
                    continue
                aria_metrics = parse_aria_metrics(line) if job["mode"] == "file" else None
                if aria_metrics is not None:
                    self.events.put(("metrics", job["id"], aria_metrics))
                if not (line.startswith("[download]") and percent):
                    self.events.put(("log", line[:320]))
            try:
                code = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                stop_process(proc)
                code = proc.wait(timeout=4)
            if code != 0 and not stop.is_set():
                raise RuntimeError(f"Downloader exited with error code {code}. See the log for details.")
            return output
        finally:
            self.active_proc = None
            try:
                if proc.stdout:
                    proc.stdout.close()
            except OSError:
                pass

    def _download_video(self, job: dict, stop: threading.Event) -> str:
        try:
            import yt_dlp  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("yt-dlp is missing. Run Install_and_Launch.bat to install it.") from exc
        ffmpeg = self._find_ffmpeg()
        label = str(job.get("format_label") or "")
        audio_only = bool(job.get("format_audio_only", "audio only" in label.lower()))
        if not ffmpeg and not audio_only:
            raise RuntimeError(
                "Lilith needs its bundled media engine to merge video and audio. "
                "Quit Lilith and run Install_and_Launch.bat to set it up automatically. Original partial downloads are preserved."
            )
        explicit = str(job.get("format_id") or "")
        # For old jobs, a selected quality was usually a video-only stream.
        has_audio = bool(job.get("format_has_audio", False))
        selector = selection_for(job.get("quality", "Best"), explicit,
                                 is_audio=audio_only, has_audio=has_audio)
        cmd = [sys.executable, "-m", "yt_dlp", "--newline", "--progress", "--continue", "--no-overwrites",
               "--no-playlist", "--windows-filenames", "--retries", "10", "--fragment-retries", "10",
               "--socket-timeout", "30", "--concurrent-fragments", "4",
               "--merge-output-format", "mp4", "--progress-delta", "0.4", "--progress-template",
               "download:LL_PROGRESS:%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
               "--print", "after_move:OUTPUT_FILE:%(filepath)s",
               "-o", str(Path(job["folder"]) / "%(title).150s [%(id)s].%(ext)s"),
               "-f", selector]
        if ffmpeg:
            cmd.extend(["--ffmpeg-location", str(Path(ffmpeg).parent)])
        if job["cookies"] != "None":
            cmd.extend(["--cookies-from-browser", job["cookies"].lower()])
        cmd.extend(["--", job["url"]])
        self.events.put(("log", "Video downloader started. Quality: " + label[:160] + ". Joining audio and video when needed."))
        output = self._run_command(cmd, job, stop)
        if stop.is_set():
            return ""
        if not output:
            raise RuntimeError("yt-dlp finished without reporting a finalized output file. Check the log. Separate video/audio files were preserved.")
        verify_combined(output, ffprobe=ffprobe_executable(ffmpeg), audio_only=audio_only)
        return output

    def _download_aria2(self, job: dict, stop: threading.Event) -> str:
        cmd = ["aria2c", "--continue=true", "--always-resume=true", "--split=8",
               "--max-connection-per-server=8", "--min-split-size=1M", "--max-tries=10",
               "--retry-wait=4", "--timeout=30", "--connect-timeout=25",
               "--file-allocation=none", "--summary-interval=1", "--console-log-level=notice",
               "--dir", job["folder"], "--", job["url"]]
        self.events.put(("log", "aria2c started (8 connections max; resume requested)."))
        return self._run_command(cmd, job, stop)

    def _download_python(self, job: dict, stop: threading.Event) -> str:
        self.events.put(("log", "Direct HTTP transfer started. Measuring received bytes and speed."))
        def report(metrics):
            self.events.put(("metrics", job["id"], metrics))
        return download_file(job["url"], job["folder"], preferred_filename=job.get("filename", ""),
                             referer=job.get("referer", ""), stop=stop, report=report)

    def _merge_existing_dialog(self):
        if self.converting:
            messagebox.showinfo("Video tools", "A video operation is already running.")
            return
        ffmpeg = self._find_ffmpeg()
        if ffmpeg is None:
            messagebox.showerror("Media engine missing", "Run Install_and_Launch.bat to install the media engine automatically.")
            return
        video = filedialog.askopenfilename(title="Choose the video-only file", filetypes=[("Video", "*.mp4 *.webm *.mkv *.mov"), ("All files", "*.*")])
        if not video:
            return
        audio = filedialog.askopenfilename(title="Choose the audio-only file", filetypes=[("Audio", "*.webm *.m4a *.mp3 *.aac *.opus"), ("All files", "*.*")])
        if not audio:
            return
        output = filedialog.asksaveasfilename(title="Save merged MP4", initialfile=Path(video).stem + "_with_audio.mp4",
                                              initialdir=str(Path(video).parent), defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if not output:
            return
        if Path(output).exists():
            messagebox.showerror("File exists", "Choose an unused output filename; originals will be preserved.")
            return
        self.converting = True
        self._log("Merging video and audio with FFmpeg; the original tracks will not be modified.")
        self.status_var.set("Merging existing video + audio...")
        threading.Thread(target=self._merge_worker, args=(video, audio, output, ffmpeg), daemon=True).start()

    def _merge_worker(self, video, audio, output, ffmpeg):
        try:
            result = merge_existing(video, audio, output, ffmpeg)
            self.events.put(("merge_done", result))
        except Exception as exc:
            self.events.put(("merge_error", str(exc)))

    def _convert_dialog(self):
        if self.converting:
            messagebox.showinfo("Conversion", "A video is already being converted.")
            return
        if not self._find_ffmpeg():
            messagebox.showerror("Media engine missing", "Run Install_and_Launch.bat to install the media engine automatically.")
            return
        src = filedialog.askopenfilename(title="Choose a video to prepare for AI",
                                         filetypes=[("Video files", "*.mp4 *.mkv *.mov *.webm *.avi *.ts *.m4v"), ("All files", "*.*")])
        if not src:
            return
        try:
            start = self._parse_positive(self.trim_start.get(), "Start time", zero_ok=True)
            duration = self._parse_positive(self.trim_duration.get(), "Duration", zero_ok=False)
        except ValueError as exc:
            messagebox.showerror("Clip settings", str(exc))
            return
        initial = str(Path(src).with_name(Path(src).stem + "_AI_720p.mp4"))
        output = filedialog.asksaveasfilename(title="Save AI-friendly MP4", defaultextension=".mp4",
                                              initialdir=str(Path(src).parent), initialfile=Path(initial).name,
                                              filetypes=[("MP4 video", "*.mp4")])
        if not output:
            return
        if Path(src).resolve() == Path(output).resolve():
            messagebox.showerror("Output", "Choose a different filename from the source video.")
            return
        if Path(output).exists():
            messagebox.showerror("Output", "The output file already exists. Choose a new filename.")
            return
        self.converting = True
        self.status_var.set("Converting video for AI sharing...")
        threading.Thread(target=self._convert_worker, args=(src, output, start, duration), daemon=True).start()

    @staticmethod
    def _parse_positive(value: str, label: str, zero_ok: bool) -> float | None:
        value = value.strip()
        if not value:
            return None
        try:
            result = float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number of seconds.") from exc
        if not (result < float("inf")) or result < 0 or (not zero_ok and result == 0):
            raise ValueError(f"{label} must be {'nonnegative' if zero_ok else 'positive' }.")
        return result

    def _convert_worker(self, src: str, output: str, start: float | None, duration: float | None):
        filter_expr = "scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
        cmd = [self._find_ffmpeg() or "ffmpeg", "-hide_banner", "-nostdin", "-n"]
        if start is not None:
            cmd.extend(["-ss", str(start)])
        cmd.extend(["-i", src])
        if duration is not None:
            cmd.extend(["-t", str(duration)])
        cmd.extend(["-map", "0:v:0", "-map", "0:a:0?", "-vf", filter_expr,
                    "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-sn",
                    "-movflags", "+faststart", output])
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace", text=True,
                                    creationflags=subprocess_flags())
            self.conversion_proc = proc
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if line and ("time=" in line or "Error" in line or "Invalid" in line):
                    self.events.put(("log", "Convert: " + line[:250]))
            code = proc.wait()
            if code:
                self.events.put(("convert_error", f"FFmpeg failed (exit {code}). Check log."))
            else:
                self.events.put(("convert_done", output))
        except Exception as exc:
            self.events.put(("convert_error", str(exc)))
        finally:
            self.conversion_proc = None

    def _start_receiver(self, initial: bool = False):
        port = int(self.settings.get("receiver_port", SERVER_PORT))
        if self.server:
            return
        app = self

        class Handler(BaseHTTPRequestHandler):
            def _cors(self):
                origin = self.headers.get("Origin", "")
                if origin.startswith("chrome-extension://") or origin.startswith("moz-extension://"):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Lilith-Token")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_POST(self):
                if self.path not in ("/add", "/inspect", "/show", "/handoff"):
                    self.send_error(404)
                    return
                token = self.headers.get("X-Lilith-Token", "")
                if not secrets.compare_digest(token, str(app.settings["receiver_token"])):
                    self.send_error(403, "Pairing key required")
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size > 8192 or size < 0:
                        raise ValueError("Invalid request size")
                    body = self.rfile.read(size)
                    data = json.loads(body.decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("Expected JSON object")
                    url = str(data.get("url", "")).strip()
                    title = str(data.get("title", ""))[:180]
                    mode = str(data.get("mode", "Video page"))
                    filename = sanitize_chrome_filename(data.get("filename", "")) if data.get("filename") else ""
                    referer = str(data.get("referer", ""))[:2048]
                    if self.path != "/show" and not url_is_valid(url):
                        raise ValueError("Invalid URL")
                except (ValueError, UnicodeDecodeError):
                    self.send_error(400, "Invalid JSON body")
                    return
                if self.path == "/handoff":
                    # Only acknowledge interception when a direct GET succeeds without
                    # Chrome cookies. If not, Chrome resumes its original download.
                    ok, detail = probe_direct(url, referer, timeout=6)
                    if not ok:
                        self.send_response(409)
                        self._cors()
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"ok": False, "error": detail}).encode("utf-8"))
                        return
                    app.events.put(("external_add", url, title, "Direct file", filename, referer, True))
                elif self.path == "/show":
                    app.events.put(("show_main",))
                elif self.path == "/inspect":
                    app.events.put(("external_inspect", url))
                else:
                    app.events.put(("external_add", url, title, mode, filename, referer, False))
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, format, *args):
                return

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.receiver_status_var.set(f"Listening locally on port {port}\nPair Chrome using your private key below.")
            if not initial:
                self._log(f"Browser receiver started on port {port}.")
        except OSError as exc:
            self.server = None
            self.receiver_enabled_var.set(False)
            self.receiver_status_var.set(f"Receiver failed: {exc}")
            self._log(f"Receiver failed to start: {exc}")

    def _stop_receiver(self):
        if self.server:
            server = self.server
            self.server = None
            threading.Thread(target=lambda: (server.shutdown(), server.server_close()), daemon=True).start()
            self.server_thread = None
            self.receiver_status_var.set("Receiver disabled")
            if self.running:
                self._log("Browser receiver stopped.")

    def _toggle_receiver(self):
        enabled = bool(self.receiver_enabled_var.get())
        self.settings["receiver_enabled"] = enabled
        self._save_settings()
        if enabled:
            self._start_receiver()
        else:
            self._stop_receiver()

    def _toggle_progress_pref(self):
        self.settings["show_progress_on_start"] = bool(self.auto_progress_var.get())
        self._save_settings()

    def _copy_pairing_key(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.settings["receiver_token"])
        self._log("Pairing key copied. Paste it in your browser extension once, then clear the clipboard.")

    def _copy_receiver_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(f"http://127.0.0.1:{int(self.settings.get('receiver_port', SERVER_PORT))}/add")
        self._log("Local receiver URL copied.")

    def _pause_by_id(self, job_id):
        if self.tree.exists(job_id):
            self.tree.selection_set(job_id)
            self._pause_selected()

    def _resume_by_id(self, job_id):
        if self.tree.exists(job_id):
            self.tree.selection_set(job_id)
            self._resume_selected()

    def _init_tray(self):
        if os.name != "nt":
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            icon_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            painter = ImageDraw.Draw(icon_image)
            painter.rounded_rectangle((4, 4, 60, 60), radius=19, fill="#5b2b88", outline="#d9a5ff", width=3)
            painter.arc((13, 9, 55, 55), start=35, end=285, fill="#f5d7ff", width=6)
            painter.ellipse((18, 18, 35, 35), fill="#ffdcfb")
            menu = pystray.Menu(
                pystray.MenuItem("Open Lilith", lambda icon, item: self.events.put(("show_main",)), default=True),
                pystray.MenuItem("Show download progress", lambda icon, item: self.events.put(("show_progress",))),
                pystray.MenuItem("Pause active download", lambda icon, item: self.events.put(("tray_pause",))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Lilith completely", lambda icon, item: self.events.put(("tray_quit",))),
            )
            self.tray_icon = pystray.Icon("LilithDownloadDesk", icon_image, "Lilith Download Desk", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as exc:
            self.tray_icon = None
            self.tray_error = str(exc)

    def _hide_main(self):
        if self.tray_icon is not None:
            self.root.withdraw()
        else:
            self.root.iconify()

    def _show_main(self):
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def _open_progress_window(self, job=None, automatic=False):
        if automatic and not self.settings.get("show_progress_on_start", True):
            return
        if job is None:
            job = next((j for j in self.jobs if j["id"] == self.active_job_id), None)
            if job is None and self.progress_for_id:
                job = next((j for j in self.jobs if j["id"] == self.progress_for_id), None)
            if job is None:
                if not automatic:
                    self._show_main()
                return
        if self.progress_window is not None and self.progress_window.winfo_exists():
            self.progress_for_id = job["id"]
            self.progress_window.deiconify()
            self.progress_window.lift()
            self._update_progress_window(job)
            return
        win = tk.Toplevel(self.root)
        self.progress_window = win
        self.progress_for_id = job["id"]
        win.title("Lilith ♡ Active Download")
        win.geometry("680x290")
        win.minsize(550, 280)
        win.configure(background=BG)
        win.protocol("WM_DELETE_WINDOW", self._hide_progress_window)
        outer = ttk.Frame(win, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="♡  Your download is on its way", style="Title.TLabel").pack(anchor="w")
        self.progress_title_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.progress_title_var).pack(anchor="w", pady=(8, 0))
        self.progress_state_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.progress_state_var, style="Secondary.TLabel").pack(anchor="w", pady=(2, 8))
        self.progress_pct_var = tk.StringVar()
        self.progress_bar = ttk.Progressbar(outer, mode="determinate", maximum=100, length=520)
        self.progress_bar.pack(fill="x", pady=(2, 6))
        ttk.Label(outer, textvariable=self.progress_pct_var, style="Secondary.TLabel").pack(anchor="w")
        metrics = ttk.Frame(outer)
        metrics.pack(fill="x", pady=(8, 5))
        self.progress_speed_var = tk.StringVar()
        self.progress_bytes_var = tk.StringVar()
        self.progress_eta_var = tk.StringVar()
        ttk.Label(metrics, textvariable=self.progress_speed_var).pack(side="left")
        ttk.Label(metrics, textvariable=self.progress_eta_var).pack(side="right")
        ttk.Label(outer, textvariable=self.progress_bytes_var, style="Secondary.TLabel").pack(anchor="w")
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Pause", command=lambda: self._pause_by_id(self.progress_for_id)).pack(side="left")
        ttk.Button(actions, text="Resume", command=lambda: self._resume_by_id(self.progress_for_id)).pack(side="left", padx=7)
        ttk.Button(actions, text="Open file", command=self._open_selected_file).pack(side="left")
        ttk.Button(actions, text="Show in folder", command=self._show_selected_file_in_folder).pack(side="left", padx=7)
        ttk.Button(actions, text="Hide", command=self._hide_progress_window).pack(side="right")
        self._update_progress_window(job)

    def _hide_progress_window(self):
        if self.progress_window is not None and self.progress_window.winfo_exists():
            self.progress_window.withdraw()

    def _update_progress_window(self, job):
        if self.progress_window is None or not self.progress_window.winfo_exists() or job["id"] != self.progress_for_id:
            return
        title = job.get("title") or job.get("url") or "Downloading"
        self.progress_title_var.set(title[:80])
        self.progress_state_var.set(("Error: " + job.get("last_error", ""))[:95] if job.get("status") == "Failed" else job.get("status", "Queued"))
        percent = job.get("progress", "0%")
        match = re.match(r"^([0-9]+(?:\.[0-9]+)?)%$", percent)
        if not match and job.get("status") == "Downloading":
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(20)
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar["value"] = float(match.group(1)) if match else 0
        self.progress_pct_var.set(percent)
        self.progress_speed_var.set("Speed: " + (human_bytes(job["speed"]) + "/s" if job.get("speed") is not None else "Waiting"))
        self.progress_eta_var.set("ETA: " + human_eta(job.get("eta")))
        self.progress_bytes_var.set("Downloaded: " + human_bytes(job.get("bytes")) + " / " + human_bytes(job.get("total")))
        if job.get("status") in ("Completed", "Paused", "Failed"):
            self.progress_eta_var.set(job["status"])

    def _start_with_windows_enabled(self):
        if os.name != "nt":
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "LilithDownloadDesk")
                return True
        except OSError:
            return False

    def _toggle_autostart(self):
        if os.name != "nt":
            messagebox.showinfo("Windows startup", "Available on Windows only.")
            self.autostart_var.set(False)
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if self.autostart_var.get():
                    python_bin = Path(sys.executable)
                    if python_bin.name.lower() in ("python.exe", "python3.exe"):
                        maybe = python_bin.with_name("pythonw.exe")
                        if maybe.exists():
                            python_bin = maybe
                    script = str(Path(__file__).resolve())
                    value = subprocess.list2cmdline([str(python_bin), script, "--tray"])
                    winreg.SetValueEx(key, "LilithDownloadDesk", 0, winreg.REG_SZ, value)
                    self._log("Lilith will launch hidden in the tray when you sign into Windows.")
                else:
                    try:
                        winreg.DeleteValue(key, "LilithDownloadDesk")
                    except FileNotFoundError:
                        pass
                    self._log("Windows startup disabled.")
        except OSError as exc:
            messagebox.showerror("Startup setting", str(exc))
        self.autostart_var.set(self._start_with_windows_enabled())

    def _log(self, message: str):
        if not self.running:
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        if line_count > 350:
            self.log_box.delete("1.0", "90.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        if self.log_view_text is not None and self.log_view_text.winfo_exists():
            self.log_view_text.configure(state="normal")
            self.log_view_text.insert("end", message + "\n")
            self.log_view_text.see("end")
            self.log_view_text.configure(state="disabled")

    def _pump(self):
        if not self.running:
            return
        dirty = False
        try:
            while True:
                item = self.events.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "media_engine_ready":
                    self.ffmpeg_status.set("Media engine: ready")
                    self._log("Managed media engine ready: " + item[1])
                elif kind == "media_engine_error":
                    self.ffmpeg_status.set("Media engine: needs setup")
                    self._log("Media engine issue: " + item[1])
                    messagebox.showerror("Media engine setup", item[1])
                elif kind == "merge_done":
                    self.converting = False
                    self.status_var.set("Merged MP4 ready: " + item[1])
                    self._log("Merged audio + video into: " + item[1])
                    messagebox.showinfo("Merge completed", "A playable MP4 was created:\n" + item[1])
                elif kind == "merge_error":
                    self.converting = False
                    self.status_var.set("Merge failed")
                    self._log("Merge failed: " + item[1])
                    messagebox.showerror("Merge failed", item[1])
                elif kind == "metrics":
                    job = next((x for x in self.jobs if x["id"] == item[1]), None)
                    if job:
                        metrics = item[2]
                        for key in ("speed", "eta", "bytes", "total"):
                            if key in metrics:
                                job[key] = metrics[key]
                        if metrics.get("percent"):
                            job["progress"] = metrics["percent"]
                        elif job.get("bytes") is not None and not job.get("total"):
                            job["progress"] = human_bytes(job["bytes"]) + " received"
                        elif job.get("bytes") is not None and job.get("total"):
                            job["progress"] = f"{min(100, 100 * job['bytes']/job['total']):.1f}%"
                        self._refresh_row(job)
                        self._update_progress_window(job)
                elif kind == "progress":
                    job = next((x for x in self.jobs if x["id"] == item[1]), None)
                    if job:
                        job["progress"] = item[2]
                        self._refresh_row(job)
                        self._update_progress_window(job)
                elif kind == "formats":
                    title, items = item[1], item[2]
                    self.format_list.delete(0, "end")
                    self.format_map = {}
                    self.format_details = item[3] if len(item) > 3 else {}
                    if not items:
                        self.format_list.insert("end", "No explicit formats found")
                    else:
                        for label, fid in items:
                            self.format_list.insert("end", label)
                            self.format_map[label] = fid
                    self._log(f"Loaded {len(items)} formats for: {title}")
                elif kind == "formats_error":
                    self.format_list.delete(0, "end")
                    self.format_map = {}
                    self.format_details = {}
                    self.format_list.insert("end", "Inspection failed")
                    self._log("Format inspection failed: " + str(item[1]))
                    messagebox.showerror("Inspect qualities", str(item[1]))
                elif kind == "external_inspect":
                    self._show_main()
                    self.url_var.set(item[1])
                    self.mode_var.set("Video page")
                    self._clear_selected_format()
                    self._inspect_qualities()
                elif kind == "show_main":
                    self._show_main()
                elif kind == "show_progress":
                    self._open_progress_window()
                elif kind == "tray_quit":
                    self._really_quit()
                    return
                elif kind == "tray_pause":
                    if self.active_job_id:
                        self._pause_by_id(self.active_job_id)
                elif kind == "external_add":
                    url, title, mode = item[1], item[2], item[3]
                    filename, referer, automatic = item[4], item[5], item[6]
                    old_mode = self.mode_var.get()
                    try:
                        if mode in ("Video page", "Direct file", "Auto detect"):
                            self.mode_var.set(mode)
                        self._add(external_url=url, external_title=title)
                        added = self._selected()
                        if added:
                            added["filename"] = filename
                            added["referer"] = referer
                            if filename:
                                added["title"] = filename
                                self._refresh_row(added)
                            self._save()
                    finally:
                        self.mode_var.set(old_mode)
                    self._log(f"Received from browser: {filename or title or url}")
                    self.auto_run = True
                    self._maybe_start_next()
                elif kind in ("done", "error"):
                    job = next((x for x in self.jobs if x["id"] == item[1]), None)
                    if job:
                        stopped = self.active_stop.is_set() if self.active_stop else False
                        if stopped:
                            job["status"] = "Paused"
                            self._log("Paused. Partial download files were preserved.")
                        elif kind == "done" and item[2]:
                            job["status"] = "Completed"
                            job["last_error"] = ""
                            job["progress"] = "100%"
                            if item[3]:
                                job["output"] = item[3]
                            self._log("Download completed.")
                        else:
                            job["status"] = "Failed"
                            job["last_error"] = str(item[2] if kind == "error" else "Download interrupted unexpectedly.")
                            self._log("Error: " + job["last_error"])
                            self.status_var.set("Failed: " + job["last_error"][:180])
                        job["speed"] = None
                        job["eta"] = None
                        self._refresh_row(job)
                        self._update_progress_window(job)
                        dirty = True
                    self.active_job_id = None
                    self.active_stop = None
                    self._maybe_start_next()
                elif kind == "convert_done":
                    self.converting = False
                    self.status_var.set("AI-friendly MP4 ready: " + str(item[1]))
                    self._log("Converted MP4: " + str(item[1]))
                    messagebox.showinfo("Conversion finished", "Saved AI-friendly MP4:\n" + str(item[1]))
                elif kind == "convert_error":
                    self.converting = False
                    self.status_var.set("Conversion failed")
                    self._log("Conversion failed: " + str(item[1]))
                    messagebox.showerror("Conversion failed", str(item[1]))
        except queue.Empty:
            pass
        if dirty:
            self._save()
        self.root.after(120, self._pump)

    def _restore(self):
        try:
            records = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                return
            for job in records:
                if not isinstance(job, dict) or not url_is_valid(str(job.get("url", ""))):
                    continue
                if job.get("status") in ("Downloading", "Pausing", "Queued"):
                    job["status"] = "Paused"
                # Upgrade failed v1.2 model-file links that were incorrectly
                # classified as video pages. Preserve the rest of the job.
                if (job.get("mode") == "video"
                        and detect_mode(job["url"], "Auto detect") == "file"):
                    job["mode"] = "file"
                    job["format_id"] = ""
                    job["format_label"] = "Auto / best available"
                job.setdefault("last_error", "")
                job.setdefault("filename", "")
                job.setdefault("referer", "")
                self.jobs.append(job)
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            temp = JOBS_FILE.with_suffix(".tmp")
            temp.write_text(json.dumps(self.jobs, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, JOBS_FILE)
        except OSError as exc:
            self._log(f"Warning: unable to save job list: {exc}") if hasattr(self, "log_box") else None

    def _restore_settings(self):
        try:
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.settings.update(loaded)
        except (OSError, ValueError):
            pass

    def _save_settings(self):
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _close(self):
        if self.tray_icon is not None:
            self._hide_main()
            return
        self._really_quit()

    def _really_quit(self):
        self.running = False
        if self.active_stop:
            self.active_stop.set()
        stop_process(self.active_proc)
        stop_process(self.conversion_proc)
        self._stop_receiver()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        for job in self.jobs:
            if job["status"] in ("Downloading", "Pausing", "Queued"):
                job["status"] = "Paused"
        self._save()
        self._save_settings()
        self.root.destroy()


def main():
    global MUTEX_HANDLE
    if os.name == "nt":
        try:
            MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, True, "Local\\Lilith_Download_Desk_v12")
            if ctypes.windll.kernel32.GetLastError() == 183:
                try:
                    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                    port = int(settings.get("receiver_port", SERVER_PORT))
                    token = str(settings.get("receiver_token", ""))
                    if not token:
                        raise RuntimeError("Unpaired")
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{port}/show", data=b"{}",
                        headers={"Content-Type":"application/json", "X-Lilith-Token":token}, method="POST")
                    urllib.request.urlopen(request, timeout=2).close()
                except Exception:
                    ctypes.windll.user32.MessageBoxW(0, "Lilith is already running. Open her from the system tray near the clock.",
                                                     "Lilith Download Desk", 0x40)
                return
        except Exception:
            pass
    root = tk.Tk()
    DownloadDesk(root)
    root.mainloop()


if __name__ == "__main__":
    main()
