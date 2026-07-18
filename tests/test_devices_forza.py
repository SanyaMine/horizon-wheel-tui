"""Windows-only environment smoke tests; skipped where the device/install isn't present."""
import sys

import pytest

from hwt import devices, forza
from hwt.vidpid import VidPid
from tests.fixtures import WHEELTUNABLE_ZIP

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")


def test_enumerate_returns_device_infos():
    ds = devices.get_controller_devices()
    # Don't require a specific wheel; just that enumeration works and parses VID/PID.
    for d in ds:
        assert isinstance(d.vid_pid, VidPid)
        assert len(d.vid_pid.compact) == 8


@pytest.mark.skipif(
    not WHEELTUNABLE_ZIP.exists(),
    reason="wheeltunablesettingspc.zip not available (no Forza install detected)",
)
def test_list_ffb_templates_from_real_zip():
    entries = forza.list_ffb_templates(WHEELTUNABLE_ZIP)
    assert entries and all(e.lower().endswith(".ini") for e in entries)
