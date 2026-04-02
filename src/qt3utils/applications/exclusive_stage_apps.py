"""
Exclusive lock so only one of qt3scan or qt3move runs at a time.

Both applications talk to the same microstage / DAQ stack; running them
concurrently risks conflicting hardware access.
"""
from __future__ import annotations

import atexit
import os
import sys
import tempfile

_LOCK_HELD = False
_win_mutex_handle = None
_unix_lock_fp = None

_SUITE_DESCRIPTION = "qt3scan or qt3move"
_MUTEX_NAME = "Local\\QT3Utils_Qt3Scan_Qt3Move_Exclusive"
_UNIX_LOCK_BASENAME = "qt3utils_qt3scan_qt3move.lock"


def _release_windows_mutex() -> None:
    global _win_mutex_handle
    if _win_mutex_handle is not None:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(_win_mutex_handle)
        _win_mutex_handle = None


def _release_unix_lock() -> None:
    global _unix_lock_fp
    if _unix_lock_fp is not None:
        import fcntl

        try:
            fcntl.flock(_unix_lock_fp.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            _unix_lock_fp.close()
        except OSError:
            pass
        _unix_lock_fp = None


def try_acquire_exclusive_stage_apps_lock() -> bool:
    """
    Acquire the suite-wide lock for this process.

    Returns True if this process now holds the lock (or already held it).
    Returns False if another process is holding it.
    """
    global _LOCK_HELD, _win_mutex_handle, _unix_lock_fp

    if _LOCK_HELD:
        return True

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ERROR_ALREADY_EXISTS = 183

        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            return False
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        _win_mutex_handle = handle
        atexit.register(_release_windows_mutex)
    else:
        import fcntl

        path = os.path.join(tempfile.gettempdir(), _UNIX_LOCK_BASENAME)
        fp = None
        try:
            fp = open(path, "w")
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if fp is not None:
                try:
                    fp.close()
                except OSError:
                    pass
            return False
        except OSError:
            if fp is not None:
                try:
                    fp.close()
                except OSError:
                    pass
            return False

        _unix_lock_fp = fp
        atexit.register(_release_unix_lock)

    _LOCK_HELD = True
    return True


def exit_if_exclusive_lock_held_by_other(app_display_name: str) -> None:
    """
    If another qt3scan/qt3move is already running, show an error and exit.

    Call before initializing hardware or GUIs that use shared devices.
    """
    if try_acquire_exclusive_stage_apps_lock():
        return

    msg = (
        f"Another {_SUITE_DESCRIPTION} session is already open.\n\n"
        "Close it before starting this application to avoid conflicting "
        "control of the microstage and other hardware."
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(f"{app_display_name} — already running", msg)
        root.destroy()
    except Exception:
        print(f"{app_display_name}: {msg}", file=sys.stderr)
    raise SystemExit(1)
