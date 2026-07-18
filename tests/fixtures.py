"""Shared deterministic fixtures for the test suite."""
from __future__ import annotations

import re
from pathlib import Path

from hwt import forza
from hwt.profile import MappedInput, WheelMapResult
from hwt.steps import STEPS
from hwt.vidpid import VidPid

# Real game-data ZIPs are copyrighted, so they can't be committed. tests/conftest.py copies
# them here from a detected Forza install at session start; the game-data tests skip
# themselves when the copy is absent (e.g. CI, or no Forza installed).
GAMEDATA_DIR = Path(__file__).resolve().parent / "gamedata"
INPUTMAPPING_ZIP = GAMEDATA_DIR / forza.INPUT_ZIP
WHEELTUNABLE_ZIP = GAMEDATA_DIR / forza.WHEEL_ZIP

WHEEL = VidPid("346E", "0015")

_AXIS_IDX = {"STEER": 0, "GAS": 1, "BRAKE": 2, "CLUTCH": 3}
_NAV_POS = {"NAV_UP": "Up", "NAV_DOWN": "Down", "NAV_LEFT": "Left", "NAV_RIGHT": "Right"}


def full_capture_result() -> WheelMapResult:
    """A complete, deterministic 26-input capture for the Moza R3.

    Axes 0-3 for the pedals/wheel; nav captured as a hat (Switch); the rest as
    sequential buttons. No randomness so output is reproducible.
    """
    r = WheelMapResult(device_vidpid=WHEEL, device_name="MOZA Windows Driver",
                       profile_name="DefaultRawGameControllerMappingProfileMOZACustom")
    raw = WHEEL.compact
    btn = 0
    for s in STEPS:
        if s.kind == "Axis":
            r.inputs[s.key] = MappedInput("Axis", _AXIS_IDX[s.key],
                                          invert_axis=(s.key != "STEER"), device_vidpid=raw)
        elif s.key in _NAV_POS:
            r.inputs[s.key] = MappedInput("Switch", 0, switch_position=_NAV_POS[s.key],
                                          device_vidpid=raw)
        else:
            r.inputs[s.key] = MappedInput("Button", btn, device_vidpid=raw)
            btn += 1
    return r


def normalize_id(xml_bytes: bytes) -> bytes:
    """Replace the non-deterministic profile GUID with a fixed token for comparison."""
    return re.sub(rb'Id="[^"]*"', b'Id="GOLDEN-ID"', xml_bytes, count=1)
