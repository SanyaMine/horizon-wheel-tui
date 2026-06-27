from pathlib import Path
from xml.etree import ElementTree as ET

from hwt.profile import ProfileOptions, build_profile_xml, stable_profile_id
from hwt.vidpid import VidPid
from tests.fixtures import full_capture_result, normalize_id

GOLDEN = Path(__file__).parent / "data" / "golden_profile.xml"


def test_default_output_matches_golden():
    """With no options, generation must stay byte-identical to the captured baseline."""
    out = normalize_id(build_profile_xml(full_capture_result()))
    assert out == GOLDEN.read_bytes()


def test_structure():
    root = ET.fromstring(build_profile_xml(full_capture_result()))
    assert root.tag == "Profiles"
    prof = root[0]
    assert prof.tag == "RawGameControllerInputMappingProfile"
    assert prof.get("PrimaryDeviceVidPid") == "0x346E0015"        # header: 0x + UPPER
    assert prof.get("Id") == prof.get("Id").upper()
    contexts = [c for c in prof if c.tag == "Context"]
    assert [c.get("Context") for c in contexts] == [
        "INPUTCONTEXT_RACING", "INPUTCONTEXT_UI", "INPUTCONTEXT_RACING_UI",
        "INPUTCONTEXT_ANNA", "INPUTCONTEXT_COPTER", "INPUTCONTEXT_RACING_CAMERA_ONLY",
        "INPUTCONTEXT_FREECAM", "INPUTCONTEXT_HIDE_SEEK", "INPUTCONTEXT_ELIMINATOR_UI",
        "INPUTCONTEXT_CAR_MEETS",
    ]


def _find(prof, ctx_name, key):
    for c in prof:
        if c.tag == "Context" and c.get("Context") == ctx_name:
            for v in c.iter("Value"):
                if v.get("Key") == key:
                    return v
    return None


def test_value_encoding():
    prof = ET.fromstring(build_profile_xml(full_capture_result()))[0]
    steer = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_STEERING")
    # per-Value VidPid carries the 0x prefix (shipped game format; required to bind)
    assert steer.get("InputType") == "Axis" and steer.get("VidPid") == "0x346E0015"
    assert steer.get("InvertAxis") == "false" and steer.get("InnerDeadzone") == "0.0"
    gas = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GAS")
    assert gas.get("InvertAxis") == "true"
    dpad = _find(prof, "INPUTCONTEXT_UI", "INPUTCMD_UI_DPAD_UP_PRESS")
    assert dpad.get("InputType") == "Switch" and dpad.get("SwitchPosition") == "Up"
    rtrig = _find(prof, "INPUTCONTEXT_UI", "INPUTCMD_UI_RTRIGGER_PRESS")
    assert rtrig.get("InnerDeadzone") == "0.05" and rtrig.get("OuterDeadzone") == "0.95"
    mapmove = _find(prof, "INPUTCONTEXT_UI", "INPUTCMD_UI_MAP_MOVE_LEFTRIGHT")
    assert [k.tag for k in mapmove] == ["InputCmdLow", "InputCmdHigh"]


def test_profile_id_is_stable_for_same_wheel():
    """Re-running yields the SAME id (so re-installs overwrite, not duplicate); different
    wheels get different ids; an explicit profile_id overrides."""
    a = ET.fromstring(build_profile_xml(full_capture_result()))[0].get("Id")
    b = ET.fromstring(build_profile_xml(full_capture_result()))[0].get("Id")
    assert a == b == stable_profile_id(VidPid("346E", "0015"))
    assert a == a.upper()
    assert stable_profile_id(VidPid("046D", "C24F")) != a
    pinned = ET.fromstring(
        build_profile_xml(full_capture_result(), ProfileOptions(profile_id="FIXED-ID")))[0]
    assert pinned.get("Id") == "FIXED-ID"


def test_wider_mappings_adds_gears_pp_ltrigger():
    prof = ET.fromstring(build_profile_xml(full_capture_result(),
                                           ProfileOptions(wider_mappings=True)))[0]
    # H-pattern gears in RACING
    assert _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GEAR_FIRST") is not None
    assert _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GEAR_REVERSE") is not None
    assert _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GEAR_SEVENTH") is not None
    # brake-as-left-trigger in UI
    assert _find(prof, "INPUTCONTEXT_UI", "INPUTCMD_UI_LTRIGGER_PRESS") is not None
    # whole prop-placement context, transforms driven by the d-pad (Switch)
    names = [c.get("Context") for c in prof if c.tag == "Context"]
    assert "INPUTCONTEXT_PROP_PLACEMENT_UI" in names
    pp = _find(prof, "INPUTCONTEXT_PROP_PLACEMENT_UI", "INPUTCMD_PP_TRANSFORM_UP")
    assert pp is not None and pp.get("InputType") == "Switch"


def test_wider_mappings_off_is_faithful():
    prof = ET.fromstring(build_profile_xml(full_capture_result(), ProfileOptions()))[0]
    assert _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GEAR_FIRST") is None
    assert _find(prof, "INPUTCONTEXT_UI", "INPUTCMD_UI_LTRIGGER_PRESS") is None
    names = [c.get("Context") for c in prof if c.tag == "Context"]
    assert "INPUTCONTEXT_PROP_PLACEMENT_UI" not in names


def test_options_are_optional_and_effective():
    opts = ProfileOptions(steer_deadzones_around_center=True, steer_inner_deadzone="0.02",
                          pedal_inner_deadzone="0.03")
    prof = ET.fromstring(build_profile_xml(full_capture_result(), opts))[0]
    steer = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_STEERING")
    assert steer.get("DeadzonesAroundCenter") == "true"
    assert steer.get("InnerDeadzone") == "0.02"
    gas = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_GAS")
    assert gas.get("InnerDeadzone") == "0.03"
