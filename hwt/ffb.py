"""Force-feedback INI patching and template selection.

Mirrors C# `IniEditor.SetVendorProduct` (Program.cs:1535-1552) and the FFB output name
`ControllerFFB-0X{Compact}.ini` (Program.cs).
"""
from __future__ import annotations

import re

from .vidpid import VidPid

# Deviation from upstream (intentional): upstream's regex only matches a 0x-prefixed,
# 8-hex value (^\s*VendorProduct\s+0x[0-9a-fA-F]{8}\s*$). The generic template
# `ControllerFFB-0000000000.ini` — the one an unsupported wheel (e.g. Moza) falls back
# to — stores a bare "0000000000", so upstream APPENDS a second VendorProduct line
# instead of replacing it, leaving a stray conflicting entry. Matching any value fixes
# that real bug while still replacing the 0x form for supported wheels.
_VENDOR_PRODUCT_RE = re.compile(r"^\s*VendorProduct\s+\S+\s*$", re.IGNORECASE | re.MULTILINE)


def set_vendor_product(ini_text: str, vid_pid: VidPid) -> str:
    value = "VendorProduct " + vid_pid.to_xml_string()
    if _VENDOR_PRODUCT_RE.search(ini_text):
        return _VENDOR_PRODUCT_RE.sub(value, ini_text)
    newline = "\r\n" if "\r\n" in ini_text else "\n"
    return ini_text.rstrip() + newline + value + newline


def output_ini_name(vid_pid: VidPid) -> str:
    return f"ControllerFFB-0X{vid_pid.compact}.ini"


def pick_template(entries: list[str], vid_pid: VidPid) -> str:
    """Closest FFB template entry for a wheel.

    Mirrors the C# default-entry selection (Program.cs:510): prefer an entry whose name
    contains the wheel's compact VID/PID; otherwise fall back to the generic all-zero
    template, otherwise the first entry. Returns "" if there are no templates.
    """
    if not entries:
        return ""
    compact = vid_pid.compact.upper()
    for e in entries:
        if compact in e.upper():
            return e
    for e in entries:
        if "0000000000" in e:
            return e
    return entries[0]


def pick_template_for_model(entries: list[str], model_vid_pid: VidPid) -> str:
    """OPTIONAL smarter pick: the FFB template matching a chosen *base wheel model's*
    VID/PID (e.g. emulate a Fanatec DD on a Moza). Returns "" if none matches, so the
    caller can fall back to `pick_template` (the faithful generic default)."""
    compact = model_vid_pid.compact.upper()
    for e in entries:
        if compact in e.upper():
            return e
    return ""
