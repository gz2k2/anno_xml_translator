"""Build Anno XML Translator as a Windows one-file executable with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "Anno_XML_Translator"
SOURCE_FILE = "Anno_XML_Translator.py"
ICON_FILE = "icon.ico"  # Optional. The build also works without this file.

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_PATH = PROJECT_DIR / SOURCE_FILE
ICON_PATH = PROJECT_DIR / ICON_FILE
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
SPEC_FILE = PROJECT_DIR / f"{APP_NAME}.spec"


def ensure_pyinstaller() -> None:
    """Stop with a clear message if PyInstaller is not installed."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit(
            "PyInstaller is not installed. Run:\n"
            f'  "{sys.executable}" -m pip install -r requirements.txt'
        )


def clean_previous_build() -> None:
    """Remove output from an earlier build."""
    for directory in (BUILD_DIR, DIST_DIR):
        if directory.exists():
            shutil.rmtree(directory)

    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def build() -> Path:
    """Run PyInstaller and return the path to the generated executable."""
    if not SOURCE_PATH.is_file():
        raise SystemExit(f"Source file not found: {SOURCE_PATH}")

    ensure_pyinstaller()
    clean_previous_build()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(PROJECT_DIR),
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "argostranslate",
        "--collect-submodules",
        "ctranslate2",
        "--collect-submodules",
        "stanza",
        str(SOURCE_PATH),
    ]

    if ICON_PATH.is_file():
        command[3:3] = ["--icon", str(ICON_PATH)]
        print(f"Using application icon: {ICON_PATH.name}")
    else:
        print(f"Optional icon not found: {ICON_PATH.name}. Building without custom icon.")

    print("\nStarting PyInstaller build:\n")
    print(subprocess.list2cmdline(command))
    print()

    subprocess.run(command, cwd=PROJECT_DIR, check=True)

    executable_name = f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME
    executable_path = DIST_DIR / executable_name

    if not executable_path.is_file():
        raise SystemExit(f"Build finished, but executable was not found: {executable_path}")

    print("\nBuild completed successfully.")
    print(f"Executable: {executable_path}")
    print(
        "At first start, the application creates config, argos_packages, "
        "and temp next to the executable."
    )
    return executable_path


if __name__ == "__main__":
    try:
        build()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"PyInstaller build failed with exit code {error.returncode}.") from error
