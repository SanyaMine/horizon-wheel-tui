"""Repack the game ZIPs and install with a backup.

Mirrors C# `ZipWriter` (store-only, flat top-level entries, patched entry added
alongside the stock defaults) and `GameFileInstaller` (HST-BACKUP copy-if-missing, then
overwrite the media zips). Program.cs:1554-1810.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from .forza import BACKUP_DIR, INPUT_ZIP, WHEEL_ZIP


def _top(name: str) -> str:
    """Flatten to the top-level entry name (Forza reads flat, store-only archives)."""
    return name.replace("\\", "/").strip("/").split("/")[-1]


def write_input_zip(src: Path, dst: Path, profile_name: str, xml_bytes: bytes) -> None:
    """Copy every stock entry (flattened, stored) and add our profile alongside.

    If an entry with the same top-level name already exists it is replaced by ours.
    """
    _repack(src, dst, {_top(profile_name): xml_bytes})


def write_wheel_zip(src: Path, dst: Path, ini_name: str, ini_text: str) -> None:
    _repack(src, dst, {_top(ini_name): ini_text.encode("utf-8")})


def _repack(src: Path, dst: Path, extra: dict[str, bytes]) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    written: set[str] = set()
    extra_lower = {k.lower() for k in extra}
    with zipfile.ZipFile(src, "r") as s, zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as d:
        for info in s.infolist():
            if info.filename.endswith("/"):
                continue
            top = _top(info.filename)
            low = top.lower()
            if low in extra_lower or low in written:
                continue  # replaced by extra, or duplicate top-level name
            written.add(low)
            with d.open(top, "w") as out:
                out.write(s.read(info.filename))
        for name, data in extra.items():
            with d.open(_top(name), "w") as out:
                out.write(data)
    dst.unlink(missing_ok=True)
    tmp.rename(dst)


# ── Backup / install / restore (GameFileInstaller) ───────────────────────────────────
def ensure_backup(media: str | Path) -> Path:
    mf = Path(media)
    bf = mf / BACKUP_DIR
    for z in (INPUT_ZIP, WHEEL_ZIP):
        if not (mf / z).exists():
            raise FileNotFoundError(f"The media folder is missing {z}.")
    bf.mkdir(exist_ok=True)
    for z in (INPUT_ZIP, WHEEL_ZIP):
        src, dst = mf / z, bf / z
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    return bf


def install_zips(media: str | Path, out_input: Path, out_wheel: Path) -> Path:
    mf = Path(media)
    bf = ensure_backup(mf)
    _copy_unless_same(out_input, mf / INPUT_ZIP)
    _copy_unless_same(out_wheel, mf / WHEEL_ZIP)
    return bf


def restore_backup(media: str | Path) -> Path:
    mf = Path(media)
    bf = mf / BACKUP_DIR
    bi, bw = bf / INPUT_ZIP, bf / WHEEL_ZIP
    if not bi.exists() or not bw.exists():
        raise FileNotFoundError("HST-BACKUP does not contain both required game zips.")
    shutil.copy2(bi, mf / INPUT_ZIP)
    shutil.copy2(bw, mf / WHEEL_ZIP)
    return bf


def _copy_unless_same(src: Path, dst: Path) -> None:
    if Path(src).resolve() != Path(dst).resolve():
        shutil.copy2(src, dst)


def verify_store_only_top_level(zip_path: str | Path) -> tuple[bool, list[str]]:
    """Port of C# ZipVerifier.VerifyStoreOnlyTopLevel (Program.cs:1812-1832).

    Forza expects flat, uncompressed (STORED) archives. Returns (passed, bad_entries)
    where bad = any entry that is nested (has a path separator) or not stored.
    """
    bad: list[str] = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if ("/" in info.filename or "\\" in info.filename
                    or info.compress_type != zipfile.ZIP_STORED):
                bad.append(info.filename)
    return (not bad, bad)
