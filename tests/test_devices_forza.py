"""Windows-only environment smoke tests; skipped where the device/install isn't present."""
import sys
from pathlib import Path

import pytest

from hwt import devices, forza
from hwt.vidpid import VidPid

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_enumerate_returns_device_infos():
    ds = devices.get_controller_devices()
    # Don't require a specific wheel; just that enumeration works and parses VID/PID.
    for d in ds:
        assert isinstance(d.vid_pid, VidPid)
        assert len(d.vid_pid.compact) == 8


def test_list_ffb_templates_from_real_zip():
    entries = forza.list_ffb_templates(ROOT / "wheeltunablesettingspc.zip")
    assert entries and all(e.lower().endswith(".ini") for e in entries)
