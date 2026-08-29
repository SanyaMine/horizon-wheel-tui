"""VID/PID parsing and formatting.

Mirrors the C# `VidPid` record struct (Program.cs:703-765):
  - Vid / Pid are stored as 4-hex-digit UPPERCASE strings.
  - Compact      -> "VVVVPPPP" (uppercase, no prefix) — used for FFB ini names and
                    the per-<Value> VidPid attribute the wizard emits.
  - to_xml_string -> "0x" + Compact — used for the profile header attributes.
"""
from __future__ import annotations

import re
from typing import Optional

# Same alternation as the C# VidPidRegex (Program.cs:705-707). Greedy ".*" between
# VID and PID matches the C# behaviour.
_VID_PID_RE = re.compile(
    r"VID[_=:\- ]?([0-9a-fA-F]{4}).*PID[_=:\- ]?([0-9a-fA-F]{4})"
    r"|0x([0-9a-fA-F]{4})([0-9a-fA-F]{4})"
    r"|^([0-9a-fA-F]{4})[:;\- ]([0-9a-fA-F]{4})$"
    r"|^([0-9a-fA-F]{8})$",
    re.IGNORECASE,
)


class VidPid:
    __slots__ = ("vid", "pid")

    def __init__(self, vid: str, pid: str) -> None:
        self.vid = _normalize_half(vid)
        self.pid = _normalize_half(pid)

    @property
    def compact(self) -> str:
        """Uppercase 'VVVVPPPP' (no 0x prefix)."""
        return self.vid + self.pid

    def to_xml_string(self) -> str:
        """'0x' + uppercase compact, e.g. '0x346E0015'."""
        return "0x" + self.compact

    @classmethod
    def from_sdl_guid(cls, guid: Optional[str]) -> Optional["VidPid"]:
        """Parse the USB vendor/product out of an SDL joystick GUID (pygame `get_guid()`).

        The GUID is 32 hex chars; for USB HID devices the vendor is stored little-endian at
        hex offset 8:12 and the product at 16:20 (each a byte-swapped u16). Example:
        '030000005e0400008e02000010010000' -> vendor 045E, product 028E.

        Returns None when the string isn't a usable 32-hex GUID, or when vendor+product are
        both 0000 (Bluetooth / drivers that don't populate them) — the caller then falls back
        to name matching. This is the authoritative "which device produced this input", the
        pygame analogue of the C# `RawGameController` VendorId/ProductId."""
        g = (guid or "").strip().lower()
        if len(g) < 20 or any(c not in "0123456789abcdef" for c in g[:20]):
            return None
        vid = g[10:12] + g[8:10]   # LE u16 at bytes 4-5 -> big-endian VID
        pid = g[18:20] + g[16:18]  # LE u16 at bytes 8-9 -> big-endian PID
        if vid == "0000" and pid == "0000":
            return None
        return cls(vid, pid)

    @classmethod
    def try_parse(cls, value: Optional[str]) -> Optional["VidPid"]:
        if not value or not value.strip():
            return None
        m = _VID_PID_RE.search(value.strip())
        if not m:
            return None
        if m.group(1):
            return cls(m.group(1), m.group(2))
        if m.group(3):
            return cls(m.group(3), m.group(4))
        if m.group(5):
            return cls(m.group(5), m.group(6))
        if m.group(7):
            c = m.group(7)
            return cls(c[:4], c[4:])
        return None

    def __str__(self) -> str:
        return self.to_xml_string()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VidPid) and self.compact == other.compact

    def __hash__(self) -> int:
        return hash(self.compact)


def _normalize_half(value: str) -> str:
    value = (value or "").strip()
    if len(value) != 4 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("VID and PID values must be four hex characters.")
    return value.upper()
