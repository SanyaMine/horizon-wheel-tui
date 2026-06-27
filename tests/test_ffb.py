from pathlib import Path

import pytest

from hwt import ffb, forza
from hwt.vidpid import VidPid

ROOT = Path(__file__).resolve().parent.parent
WHEEL = VidPid("346E", "0015")


@pytest.fixture(scope="module")
def templates():
    return forza.list_ffb_templates(ROOT / "wheeltunablesettingspc.zip")


@pytest.mark.parametrize("entry", ["ControllerFFB-0000000000.ini", "ControllerFFB-0x044FB653.ini"])
def test_set_vendor_product_single_line(entry):
    txt = forza.read_ffb_ini(ROOT / "wheeltunablesettingspc.zip", entry)
    patched = ffb.set_vendor_product(txt, WHEEL)
    vlines = [l for l in patched.splitlines() if l.lower().startswith("vendorproduct")]
    assert vlines == ["VendorProduct 0x346E0015"]


def test_output_ini_name():
    assert ffb.output_ini_name(WHEEL) == "ControllerFFB-0X346E0015.ini"


def test_pick_template_falls_back_to_generic(templates):
    # No native Moza template -> generic all-zero fallback
    assert ffb.pick_template(templates, WHEEL) == "ControllerFFB-0000000000.ini"


def test_pick_template_for_model(templates):
    # Logitech G29 = 046DC24F has a matching FFB template
    g29 = VidPid("046D", "C24F")
    picked = ffb.pick_template_for_model(templates, g29)
    assert picked and "046DC24F" in picked.upper()
    # unknown model -> "" so caller can fall back
    assert ffb.pick_template_for_model(templates, WHEEL) == ""
