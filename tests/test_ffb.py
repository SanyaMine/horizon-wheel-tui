import pytest

from hwt import ffb, forza
from hwt.vidpid import VidPid
from tests.fixtures import WHEELTUNABLE_ZIP

WHEEL = VidPid("346E", "0015")
# A device guaranteed absent from any FFB zip — used for the "unknown model -> fallback"
# assertions so they don't depend on which templates a tool may have injected locally.
NO_TEMPLATE = VidPid("FFFF", "FFFF")

pytestmark = pytest.mark.skipif(
    not WHEELTUNABLE_ZIP.exists(),
    reason="wheeltunablesettingspc.zip not available (no Forza install detected)",
)


@pytest.fixture(scope="module")
def templates():
    return forza.list_ffb_templates(WHEELTUNABLE_ZIP)


@pytest.mark.parametrize("entry", ["ControllerFFB-0000000000.ini", "ControllerFFB-0x044FB653.ini"])
def test_set_vendor_product_single_line(entry):
    txt = forza.read_ffb_ini(WHEELTUNABLE_ZIP, entry)
    patched = ffb.set_vendor_product(txt, WHEEL)
    vlines = [l for l in patched.splitlines() if l.lower().startswith("vendorproduct")]
    assert vlines == ["VendorProduct 0x346E0015"]


def test_output_ini_name():
    assert ffb.output_ini_name(WHEEL) == "ControllerFFB-0X346E0015.ini"


def test_pick_template_falls_back_to_generic(templates):
    # Unknown device -> generic all-zero fallback
    assert ffb.pick_template(templates, NO_TEMPLATE) == "ControllerFFB-0000000000.ini"


def test_pick_template_for_model(templates):
    # Logitech G29 = 046DC24F has a matching FFB template
    g29 = VidPid("046D", "C24F")
    picked = ffb.pick_template_for_model(templates, g29)
    assert picked and "046DC24F" in picked.upper()
    # unknown model -> "" so caller can fall back
    assert ffb.pick_template_for_model(templates, NO_TEMPLATE) == ""
