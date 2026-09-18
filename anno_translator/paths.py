"""Application path helpers for source and frozen executable builds."""

from __future__ import annotations

import os
import sys


def get_application_directory() -> str:
    """Return the directory used for persistent application data.

    When the application runs as a normal Python script, this is the project
    directory containing the main script. In a PyInstaller frozen build, it is
    the directory containing the executable. This deliberately avoids the
    temporary one-file extraction directory.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_directory() -> str:
    """Return the directory that contains read-only files bundled with the app.

    This is the counterpart to `get_application_directory`. In a PyInstaller
    one-file build, everything passed via `--add-data` is extracted into the
    temporary directory `sys._MEIPASS` at startup, NOT next to the executable.
    Bundled resources such as images must therefore be resolved from here,
    while writable data (config, models) stays next to the executable.
    """
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return bundle_dir
    return get_application_directory()


def find_resource(*relative_parts: str) -> str | None:
    """Locate a bundled resource and return its absolute path, or None.

    Several locations are tried so the same code works for a source checkout,
    a one-file build, and a one-folder build:

        1. The PyInstaller bundle directory (`sys._MEIPASS`).
        2. The application directory (next to the script or executable).
        3. The application directory without the leading sub-folder, which
           allows the user to simply drop the file next to the executable.
    """
    relative_path = os.path.join(*relative_parts)
    candidates = [
        os.path.join(get_resource_directory(), relative_path),
        os.path.join(get_application_directory(), relative_path),
        os.path.join(get_application_directory(), os.path.basename(relative_path)),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None
