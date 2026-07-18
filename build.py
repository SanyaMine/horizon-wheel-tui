#!/usr/bin/env python3
"""build.py — build the standalone executable(s) with PyInstaller (cross-platform).

Usage:
    python build.py                  # build both: standalone exe + portable .zip
    python build.py --target exe     # single-file dist/horizon-wheel-tui[.exe] only
    python build.py --target zip     # portable dist/horizon-wheel-tui-portable.zip only
    python build.py --clean          # remove build/ and dist/ first

Outputs (in dist/):
    horizon-wheel-tui[.exe]          — standalone single-file executable
                                       (".exe" suffix only on Windows)
    horizon-wheel-tui-portable.zip   — portable folder build (extract and run the exe inside)

Note: PyInstaller logs progress to stderr — that is normal, not an error.
Success/failure is determined by exit codes, not by stderr output.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Work relative to this script's own directory (replaces PowerShell's $PSScriptRoot), so the
# build is location-independent no matter where it is invoked from.
ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
NAME = "horizon-wheel-tui"

# PyInstaller appends ".exe" to the artifact name only on Windows; match that here so the
# post-build existence check looks for the right file on each platform.
EXE_NAME = f"{NAME}.exe" if os.name == "nt" else NAME


def run_pyinstaller(*args):
    """Invoke PyInstaller through the *current* interpreter (sys.executable -m PyInstaller).

    Using sys.executable guarantees the build uses the same Python/venv running this script,
    avoiding "python not found" or "wrong PyInstaller" mismatches from a bare `python` call.
    Returns the process exit code.
    """
    return subprocess.run([sys.executable, "-m", "PyInstaller", *args]).returncode


def ensure_pyinstaller():
    """Ensure PyInstaller is importable; install it on first use if missing."""
    probe = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode == 0:
        return
    print("PyInstaller not found - installing...")
    if subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"]).returncode != 0:
        print("Failed to install PyInstaller.")
        sys.exit(1)


def build_exe():
    """Standalone single-file executable → dist/horizon-wheel-tui[.exe]."""
    print("Building standalone executable (single file)...")
    code = run_pyinstaller(
        "--onefile",
        "--name", NAME,
        "--collect-all", "textual",
        "--console",
        "--noconfirm",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(ROOT / "main.py"),
    )
    exe_path = DIST_DIR / EXE_NAME
    if code != 0 or not exe_path.exists():
        print(f"Standalone build failed (exit code {code}).")
        sys.exit(1)
    return exe_path


def build_zip():
    """Portable folder build (--onedir), zipped with the top-level folder preserved."""
    print("Building portable folder build (zip)...")
    portable_root = DIST_DIR / "portable"
    code = run_pyinstaller(
        "--onedir",
        "--name", NAME,
        "--collect-all", "textual",
        "--console",
        "--noconfirm",
        "--distpath", str(portable_root),
        "--workpath", str(BUILD_DIR),
        str(ROOT / "main.py"),
    )
    portable_dir = portable_root / NAME
    if code != 0 or not portable_dir.exists():
        print(f"Portable build failed (exit code {code}).")
        sys.exit(1)

    zip_path = DIST_DIR / f"{NAME}-portable.zip"
    zip_path.unlink(missing_ok=True)

    # shutil.make_archive(base_name, "zip", root_dir, base_dir): base_dir="horizon-wheel-tui"
    # keeps the top-level folder inside the archive (matches the PowerShell build's
    # includeBaseDirectory=true). Short retry loop: antivirus may briefly lock freshly-written
    # files right after the build (a Windows quirk; harmless and cheap elsewhere).
    base_name = str(DIST_DIR / f"{NAME}-portable")
    for attempt in range(1, 6):
        try:
            shutil.make_archive(base_name, "zip", root_dir=str(portable_root), base_dir=NAME)
            return zip_path
        except OSError:
            print(f"  zip attempt {attempt} failed (file lock?), retrying...")
            time.sleep(2)
    print("Failed to create portable zip.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Build the horizon-wheel-tui executable(s).")
    parser.add_argument("--target", choices=["exe", "zip", "all"], default="all")
    parser.add_argument("--clean", action="store_true", help="remove build/ and dist/ first")
    args = parser.parse_args()

    ensure_pyinstaller()

    if args.clean:
        print("Cleaning build/ and dist/...")
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    artifacts = []
    if args.target in ("exe", "all"):
        artifacts.append(build_exe())
    if args.target in ("zip", "all"):
        artifacts.append(build_zip())

    print()
    print("Build complete:")
    for a in artifacts:
        size_mb = round(a.stat().st_size / (1024 * 1024), 1)
        print(f"  {a} ({size_mb} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
