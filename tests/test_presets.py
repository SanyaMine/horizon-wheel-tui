from hwt.devices import DeviceInfo
from hwt.install import WizardState
from hwt.presets import load_preset, save_preset
from hwt.profile import MappedInput, ProfileOptions
from hwt.vidpid import VidPid


def _state():
    moza = DeviceInfo(name="MOZA Windows Driver", vid_pid=VidPid("346E", "0015"),
                      instance_id="HID\\VID_346E&PID_0015")
    s = WizardState(wheelbase=moza, media_folder="M", input_zip="I", wheel_zip="W",
                    output_folder="O", profile_name="P", ffb_template_entry="T",
                    mode="quick", base_profile_entry="Base.xml",
                    profile_options=ProfileOptions(steer_deadzones_around_center=True,
                                                   steer_inner_deadzone="0.02",
                                                   is_default_profile=True,
                                                   profile_id="PINNED-ID",
                                                   wider_mappings=True),
                    silenced_ids=["HID\\X"])
    s.bindings["STEER"] = MappedInput("Axis", 0, invert_axis=False, device_vidpid="346E0015")
    s.bindings["NAV_UP"] = MappedInput("Switch", 0, switch_position="Up", device_vidpid="346E0015")
    s.bindings["CONFIRM"] = MappedInput("Button", 3, device_vidpid="346E0015")
    return s


def test_preset_roundtrip(tmp_path):
    p = tmp_path / "preset.json"
    s = _state()
    save_preset(s, p)
    # reload with the device present in the live list -> resolves to live DeviceInfo
    live = [s.wheelbase]
    r = load_preset(p, live)

    assert r.media_folder == "M" and r.output_folder == "O"
    assert r.mode == "quick" and r.base_profile_entry == "Base.xml"
    assert r.profile_options.steer_deadzones_around_center is True
    assert r.profile_options.steer_inner_deadzone == "0.02"
    assert r.profile_options.is_default_profile is True
    assert r.profile_options.profile_id == "PINNED-ID"
    assert r.profile_options.wider_mappings is True
    assert r.silenced_ids == ["HID\\X"]
    assert r.wheelbase is s.wheelbase  # re-resolved to the live device object
    assert set(r.bindings) == {"STEER", "NAV_UP", "CONFIRM"}
    assert r.bindings["NAV_UP"].switch_position == "Up"
    assert r.bindings["STEER"].device_vidpid == "346E0015"


def test_preset_reconstructs_absent_device(tmp_path):
    p = tmp_path / "preset.json"
    save_preset(_state(), p)
    r = load_preset(p, devices=[])  # device not present
    assert r.wheelbase is not None
    assert r.wheelbase.vid_pid == VidPid("346E", "0015")
    assert r.wheelbase.name == "MOZA Windows Driver"
