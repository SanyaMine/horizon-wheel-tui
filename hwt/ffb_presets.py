"""Bundled official Moza Pit House FFB presets.

Moza publishes per-model force-feedback tunes as `ControllerFFB-0X<VIDPID>.ini` files. We ship
them under `official-moza-pithouse-ffb-presets/Forza Horizon 5/<model>/…` and offer them in Step 4
as selectable FFB templates: auto-selected when the connected wheel's VID/PID matches, or pickable
manually by any wheel (the installer re-patches `VendorProduct` to whatever wheel is installed).

Matching is strict VID/PID equality — verified against real hardware: with Moza Pit House's "Base
Forza Horizon Compatibility" OFF, an R3 enumerates as 0x346E0005, exactly the preset filename. (With
that mode ON it reports 0x346E0015 and won't match — the Welcome screen warns about this.)

The presets are packaged into the PyInstaller build via `--add-data` (see build.py), so at runtime
they live under `sys._MEIPASS` when frozen and under the repo root in a source checkout.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .vidpid import VidPid

_BUNDLE_SUBDIR = ("official-moza-pithouse-ffb-presets", "Forza Horizon 5")


def _resource_root() -> Path:
    """Directory that holds bundled data files. PyInstaller extracts `--add-data` payloads to
    `sys._MEIPASS` at runtime; in a source checkout the data sits next to the `hwt/` package
    (repo root = this file's parent's parent)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def _preset_root() -> Path:
    return _resource_root().joinpath(*_BUNDLE_SUBDIR)


@dataclass(frozen=True)
class OfficialPreset:
    vidpid: VidPid
    model: str      # parent folder name, e.g. "R3", "R16-21"
    path: Path

    @property
    def compact(self) -> str:
        return self.vidpid.compact

    def label(self) -> str:
        return f"★ Official Moza {self.model} ({self.vidpid.to_xml_string()})"


def list_official_presets() -> list[OfficialPreset]:
    """Every bundled preset, sorted by model. Files whose name has no parseable VID/PID are skipped."""
    root = _preset_root()
    out: list[OfficialPreset] = []
    for p in sorted(root.glob("*/ControllerFFB-*.ini")):
        vp = VidPid.try_parse(p.name)  # the 0x+8-hex branch matches "...0X346E0005.ini" (IGNORECASE)
        if vp is None:
            continue
        out.append(OfficialPreset(vidpid=vp, model=p.parent.name, path=p))
    out.sort(key=lambda o: o.model)
    return out


def find_official_preset(vidpid: VidPid) -> Optional[OfficialPreset]:
    """The bundled preset whose VID/PID equals `vidpid`, or None (used for autodetect)."""
    for preset in list_official_presets():
        if preset.vidpid == vidpid:
            return preset
    return None


def get_official_preset(compact: str) -> Optional[OfficialPreset]:
    """Look a preset up by its compact 'VVVVPPPP' string — resolves an `official:<compact>` template
    selection back to its bundled file at install time."""
    key = (compact or "").upper()
    for preset in list_official_presets():
        if preset.compact == key:
            return preset
    return None
