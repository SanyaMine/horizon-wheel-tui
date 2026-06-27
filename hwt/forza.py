r"""Locate the Forza Horizon media folder and read FFB templates from the wheel ZIP.

`find_media_folders` mirrors C# `ForzaInstallFinder.FindMediaFolders`
(Program.cs:1238-1330): Steam defaults + Xbox Game Pass (scan every fixed drive's
`XboxGames\...\Content\media`) + Steam registry + libraryfolders.vdf. A candidate is
kept only if it contains inputmappingprofiles.zip.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

INPUT_ZIP  = "inputmappingprofiles.zip"
WHEEL_ZIP  = "wheeltunablesettingspc.zip"
BACKUP_DIR = "HST-BACKUP"


def find_media_folders() -> list[Path]:
    candidates: list[Path] = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\ForzaHorizon6\media"),
        Path(r"C:\Program Files\Steam\steamapps\common\ForzaHorizon6\media"),
    ]
    # Xbox Game Pass / Xbox app — scan all fixed drives (Program.cs:1247-1253)
    for root in _fixed_drive_roots():
        candidates.append(root / "XboxGames" / "Forza Horizon 6" / "Content" / "media")
        candidates.append(root / "XboxGames" / "Forza Horizon 5" / "Content" / "media")
        candidates.append(root / "XboxGames" / "ForzaHorizon6" / "Content" / "media")
    # Steam registry + libraries
    for sp in _steam_paths():
        candidates.append(sp / "steamapps" / "common" / "ForzaHorizon6" / "media")
        for lib in _steam_libraries(sp):
            candidates.append(lib / "steamapps" / "common" / "ForzaHorizon6" / "media")

    seen: set[str] = set()
    result: list[Path] = []
    for p in candidates:
        try:
            r = p.resolve()
            k = str(r).lower()
            if k not in seen and r.is_dir() and (r / INPUT_ZIP).exists():
                seen.add(k)
                result.append(r)
        except Exception:
            pass
    return result


def _fixed_drive_roots() -> list[Path]:
    if sys.platform != "win32":
        return []
    roots: list[Path] = []
    try:
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        DRIVE_FIXED = 3
        for i in range(26):
            if not (bitmask >> i) & 1:
                continue
            root = f"{chr(ord('A') + i)}:\\"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_FIXED:
                    roots.append(Path(root))
            except Exception:
                pass
    except Exception:
        return [Path(r"C:\\")]
    return roots


def _steam_paths() -> list[Path]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except Exception:
        return []
    paths: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for flag in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r"Software\Valve\Steam",
                                    access=winreg.KEY_READ | flag) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            v, _ = winreg.QueryValueEx(k, name)
                            p = Path(str(v).replace("/", "\\"))
                            if p.exists():
                                paths.append(p)
                        except FileNotFoundError:
                            pass
            except FileNotFoundError:
                pass
            except OSError:
                pass
    return paths


def _steam_libraries(steam: Path) -> list[Path]:
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if not vdf.exists():
        return []
    paths: list[Path] = []
    for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore"), re.I):
        p = Path(m.group(1).replace("\\\\", "\\"))
        if p.exists():
            paths.append(p)
    return paths


# ── FFB template ZIP access ──────────────────────────────────────────────────────────
def list_ffb_templates(wheel_zip: str | Path) -> list[str]:
    with zipfile.ZipFile(wheel_zip) as zf:
        return sorted(e.filename for e in zf.infolist()
                      if e.filename.lower().endswith(".ini"))


def read_ffb_ini(wheel_zip: str | Path, entry: str) -> str:
    with zipfile.ZipFile(wheel_zip) as zf:
        return zf.read(entry).decode("utf-8-sig")
