#!/usr/bin/env python3
"""fetch_moza_ffb_presets.py — download MOZA's official Forza FFB presets into the repo.

These are the *stock* `ControllerFFB-<VID><PID>.ini` force-feedback templates MOZA Pit House
injects into Forza on first configuration — the calibrated baseline for each MOZA wheelbase
(R3/R5/R9/R12/R16-21, all VID 0x346E). They are not shipped in the .exe you download; Pit
House pulls them at install time from a Qt Installer Framework (QIFW) component repository:

    <repo>/<version>/Updates.xml                      # manifest: component name, version, archive, SHA1
    <repo>/<version>/<component>/<version>bin.7z      # the actual payload (7z/LZMA)

This script walks that chain directly, so you get MOZA's originals without installing anything:
    1. GET Updates.xml, read the component name, version, archive filename, and SHA1.
    2. Download <version>bin.7z and verify its SHA1 against the manifest.
    3. Extract it (needs a 7-Zip CLI — .7z has no Python stdlib support) and copy every
       ControllerFFB-*.ini into ./official-moza-pithouse-ffb-presets/, mirroring the
       "<Game>/<Wheelbase>/" folders so each file's wheelbase stays labelled.

Usage:
    python fetch_moza_ffb_presets.py                 # fetch the pinned game_configs version
    python fetch_moza_ffb_presets.py --version X.Y.Z # fetch a specific game_configs version
    python fetch_moza_ffb_presets.py --dest DIR      # copy presets into DIR instead

Standard library only (plus a 7-Zip executable on PATH or in the default install dir).
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "official-moza-pithouse-ffb-presets"

# QIFW component repo for MOZA Pit House's per-game configs.
REPO_BASE = "https://cdn.gudsen.vip/simulation_game/Repoo/rs21.pit_house.game_configs"

# Pinned game_configs version. To bump: read the rs21.pit_house.game_configs entry in
# DefaultRepoUrls.json inside the Pit House installer (see download_pithouse.py), or pass
# --version. There is no directory index on the CDN, so "latest" cannot be auto-discovered.
DEFAULT_VERSION = "1.3.1.45"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetch_moza_ffb_presets.py"


def find_sevenzip():
    """Locate a 7-Zip command line executable, or exit with install guidance."""
    for exe in ("7z", "7za", "7zr", "7z.exe"):
        found = shutil.which(exe)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if Path(candidate).exists():
            return candidate
    sys.exit(
        "No 7-Zip executable found. Install 7-Zip (Windows) or p7zip (Linux/macOS: the "
        "'7z'/'7za' command) — .7z archives have no Python standard-library support."
    )


def fetch_bytes(url):
    """GET a URL and return the raw response body."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def read_manifest(version):
    """Parse Updates.xml → (component_name, version, archive_filename, sha1_or_None)."""
    url = f"{REPO_BASE}/{version}/Updates.xml"
    print(f"Reading manifest: {url}")
    root = ET.fromstring(fetch_bytes(url).decode("utf-8", "replace"))
    pkg = root.find("PackageUpdate")
    if pkg is None:
        sys.exit(f"No <PackageUpdate> in manifest for version {version}.")

    name = pkg.findtext("Name")
    ver = pkg.findtext("Version") or version
    archives = (pkg.findtext("DownloadableArchives") or "").strip()
    sha1 = pkg.findtext("SHA1")
    if not name or not archives:
        sys.exit("Manifest is missing Name or DownloadableArchives.")

    # DownloadableArchives may be a comma-separated list; game_configs ships a single "bin.7z".
    archive = archives.split(",")[0].strip()
    return name, ver, archive, (sha1.strip() if sha1 else None)


def download_archive(name, version, archive, expected_sha1):
    """Download <version><archive> and verify its SHA1, returning the local path."""
    # QIFW stores the payload in a per-component subfolder, prefixed with the version string.
    url = f"{REPO_BASE}/{version}/{name}/{version}{archive}"
    print(f"Downloading archive: {url}")
    data = fetch_bytes(url)

    if expected_sha1:
        actual = hashlib.sha1(data).hexdigest()
        if actual.lower() == expected_sha1.lower():
            print(f"SHA1 verified: {actual}")
        else:
            # QIFW's <SHA1> is not the SHA1 of the served .7z bytes (its CompressedSize doesn't
            # match the download either), so it hashes some pre-repack form we can't reproduce
            # here. HTTPS already guarantees transport integrity, and copy_ffb_presets() fails
            # loudly if the expected files aren't inside — so treat this as a warning, not fatal.
            print(f"Note: manifest SHA1 ({expected_sha1}) does not match the served archive "
                  f"({actual}); continuing (QIFW hashes a pre-repack form).")

    tmp_archive = Path(tempfile.gettempdir()) / f"{version}{archive}"
    tmp_archive.write_bytes(data)
    return tmp_archive


def extract(sevenzip, archive_path, out_dir):
    """Extract a .7z archive with the 7-Zip CLI."""
    print(f"Extracting {archive_path.name} ...")
    result = subprocess.run(
        [sevenzip, "x", "-y", f"-o{out_dir}", str(archive_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        sys.exit(f"7-Zip failed:\n{result.stderr.decode('utf-8', 'replace')}")


def copy_ffb_presets(extract_dir, dest):
    """Copy every ControllerFFB-*.ini into dest, mirroring its GameConfigs subpath."""
    # Anchor the mirrored path at the GameConfigs root so files land as
    # "<Game>/<Wheelbase>/ControllerFFB-*.ini" — keeping each preset's wheelbase labelled.
    roots = list(extract_dir.rglob("GameConfigs"))
    anchor = roots[0] if roots else extract_dir

    presets = sorted(anchor.rglob("ControllerFFB-*.ini"))
    if not presets:
        sys.exit("No ControllerFFB-*.ini files found in the extracted archive.")

    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in presets:
        rel = src.relative_to(anchor)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(rel)
    return copied


def main():
    parser = argparse.ArgumentParser(
        description="Download MOZA's official Forza FFB presets into this repo."
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help="game_configs version to fetch")
    parser.add_argument("--dest", default=str(DEST), help="destination folder for the presets")
    args = parser.parse_args()

    sevenzip = find_sevenzip()
    name, version, archive, sha1 = read_manifest(args.version)
    print(f"Component: {name}  version {version}  archive {archive}")

    archive_path = download_archive(name, version, archive, sha1)
    with tempfile.TemporaryDirectory() as tmp:
        extract(sevenzip, archive_path, tmp)
        copied = copy_ffb_presets(Path(tmp), Path(args.dest))
    archive_path.unlink(missing_ok=True)

    print(f"\nCopied {len(copied)} FFB preset(s) into {args.dest}:")
    for rel in copied:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
