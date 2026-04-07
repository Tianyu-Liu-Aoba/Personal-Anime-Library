from __future__ import annotations

import os
import subprocess
import threading
import webbrowser
from pathlib import Path


_DIALOG_LOCK = threading.Lock()


def choose_directory(title: str = "Choose an anime library folder") -> str | None:
    with _DIALOG_LOCK:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title, mustexist=True)
        root.destroy()
    return selected or None


def choose_image_file(title: str = "Choose a custom cover image") -> str | None:
    with _DIALOG_LOCK:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            return None
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("WebP", "*.webp"),
                ("Bitmap", "*.bmp"),
                ("GIF", "*.gif"),
                ("All Files", "*.*"),
            ],
        )
        root.destroy()
    return selected or None


def open_default_player(path: str) -> None:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(path)
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    subprocess.Popen([str(target)], shell=False)


def open_browser(url: str) -> None:
    webbrowser.open(url, new=1)
