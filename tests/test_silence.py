"""Non-destructive tests for device silencing — never touches real hardware."""
from hwt import silence


def test_state_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert silence.load_silenced_ids() == []
    silence.save_silenced_ids(["HID\\A", "HID\\B", "HID\\a"])  # dup (case-insensitive)
    assert silence.load_silenced_ids() == ["HID\\A", "HID\\B"]
    silence.clear_silenced_ids()
    assert silence.load_silenced_ids() == []


def test_is_elevated_returns_bool():
    assert isinstance(silence.is_elevated(), bool)


def test_status_unknown_for_bogus_device():
    assert silence.get_status("HID\\VID_FFFF&PID_FFFF\\definitely-not-real") == silence.STATUS_UNKNOWN


def test_disable_bogus_device_raises():
    # _locate fails before any privileged call, so this raises regardless of elevation.
    import pytest
    with pytest.raises(Exception):
        silence.disable_device("HID\\VID_FFFF&PID_FFFF\\definitely-not-real")
