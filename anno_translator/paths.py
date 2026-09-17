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
