"""Bundled official Moza FFB presets: discovery, VID/PID matching, install-time resolution, and the
Welcome-screen compat-mode banner."""
import pytest

from hwt import ffb
from hwt.app import compat_mode_warning
from hwt.devices import DeviceInfo
from hwt.ffb_presets import (
    find_official_preset, get_official_preset, list_official_presets,
)
from hwt.install import WizardState, _read_ffb_template
from hwt.vidpid import VidPid

EXPECTED = {"R3": "346E0005", "R5": "346E0004", "R9": "346E0002",
            "R12": "346E0006", "R16-21": "346E0000"}


def test_lists_all_five_presets():
    presets = list_official_presets()
    assert {p.model: p.compact for p in presets} == EXPECTED
    for p in presets:
        # the VID/PID is parsed from the filename, and the file really exists
        assert p.compact in p.path.name.upper()
        assert p.path.is_file()


def test_find_by_wheel_vidpid():
    assert find_official_preset(VidPid("346E", "0005")).model == "R3"
    assert find_official_preset(VidPid("346E", "0000")).model == "R16-21"
    assert find_official_preset(VidPid("046D", "C24F")) is None   # a Logitech, not Moza


def test_get_by_compact():
    assert get_official_preset("346E0002").model == "R9"
    assert get_official_preset("346e0002").model == "R9"          # case-insensitive
    assert get_official_preset("DEADBEEF") is None


def test_install_reads_and_repatches_official_preset():
    """`official:<compact>` resolves to the bundled file; any wheel can borrow it and the installer
    re-patches VendorProduct to the wheel actually being installed."""
    state = WizardState(ffb_template_entry="official:346E0005")
    text = _read_ffb_template(state, lambda _msg: None)
    assert "FriendlyName MOZA R3" in text                          # it's genuinely the R3 preset

    # Borrow the Moza tune onto a Logitech G29 — VendorProduct must become the G29's.
    patched = ffb.set_vendor_product(text, VidPid("046D", "C24F"))
    assert "VendorProduct 0x046DC24F" in patched
    assert "VendorProduct 0x346E0005" not in patched              # old vendor line replaced, not kept


def test_install_unknown_official_sentinel_raises():
    state = WizardState(ffb_template_entry="official:FFFFFFFF")
    with pytest.raises(FileNotFoundError):
        _read_ffb_template(state, lambda _msg: None)


def _dev(compact: str) -> DeviceInfo:
    return DeviceInfo(name="wheel", vid_pid=VidPid(compact[:4], compact[4:]), instance_id="x")


def test_compat_banner_red_only_when_compat_pid_present():
    msg_off, red_off = compat_mode_warning([_dev("346E0005")])   # normal Moza mode
    assert red_off is False and "turn OFF" in msg_off

    msg_on, red_on = compat_mode_warning([_dev("346E0015"), _dev("046DC24F")])
    assert red_on is True and "0x346E0015" in msg_on
