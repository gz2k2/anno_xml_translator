"""Build Anno XML Translator as a Windows one-file executable with PyInstaller."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Import der Version aus dem Unterordner anno_translator
from anno_translator.version import APP_VERSION

BASE_APP_NAME = "Anno_XML_Translator"

# Säubert die Version für den Dateinamen (z. B. "v0.11 beta" -> "v0.11_beta")
version_suffix = re.sub(r"[^\w\.-]", "_", APP_VERSION.strip())
APP_NAME = f"{BASE_APP_NAME}_{version_suffix}"

SOURCE_FILE = "Anno_XML_Translator.py"
ICON_FILE = "icon.ico"  # Optional. The build also works without this file.

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_PATH = PROJECT_DIR / SOURCE_FILE
ASSETS_DIR = PROJECT_DIR / "assets"
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


def check_assets() -> None:
    """Verify that the bundled resources exist before starting the build.

    PyInstaller would otherwise abort with a cryptic --add-data error, or the
    executable would silently ship without the Ko-fi banner.
    """
    if not ASSETS_DIR.is_dir():
        raise SystemExit(
            f"Assets folder not found: {ASSETS_DIR}\n"
            "Create it and place kofi5.webp inside before building."
        )
    banner = ASSETS_DIR / "kofi5.webp"
    if not banner.is_file():
        print(f"WARNING: {banner} is missing. The Ko-fi button will fall back to text.")
    else:
        print(f"Bundling asset: {banner.relative_to(PROJECT_DIR)}")


def build() -> Path:
    """Run PyInstaller and return the path to the generated executable."""
    if not SOURCE_PATH.is_file():
        raise SystemExit(f"Source file not found: {SOURCE_FILE}")
    check_assets()

    ensure_pyinstaller()
    clean_previous_build()

    add_data_sep = ";" if os.name == "nt" else ":"

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
        # Absolute source path, so the build does not depend on the current
        # working directory. Target "assets" is the folder inside sys._MEIPASS.
        "--add-data",
        f"{ASSETS_DIR}{add_data_sep}assets",
        # Pillow's WebP codec is loaded dynamically and is not always detected
        # by the PIL hook, which would break the kofi5.webp banner.
        "--hidden-import",
        "PIL._webp",
        "--hidden-import",
        "PIL.WebPImagePlugin",
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