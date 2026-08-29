"""External custom FFB template support: read_ffb_ini reading a file on disk instead of a
ZIP entry, and the VendorProduct re-stamp that follows. Intentionally independent of a Forza
install (the disk branch never opens the wheel ZIP), so it runs everywhere — unlike test_ffb.py
which is gated on wheeltunablesettingspc.zip being present."""
from hwt import ffb, forza
from hwt.vidpid import VidPid

WHEEL = VidPid("346E", "0015")

# A Moza R3 preset body: its VendorProduct is a *different* device than WHEEL, so a correct
# re-stamp must overwrite it (the "re-stamp to my connected wheel" behavior).
CUSTOM_INI = (
    "[General]\r\n"
    "VendorProduct 0x346E0005\r\n"
    "MaxForce 1.0\r\n"
)


def test_read_ffb_ini_reads_external_file(tmp_path):
    # A bogus ZIP path proves the disk branch wins and the ZIP is never opened.
    f = tmp_path / "ControllerFFB-0X346E0005.ini"
    f.write_text(CUSTOM_INI, encoding="utf-8")
    txt = forza.read_ffb_ini(tmp_path / "does-not-exist.zip", str(f))
    assert "MaxForce 1.0" in txt
    assert "0x346E0005" in txt  # original body preserved verbatim before patching


def test_external_file_vendorproduct_restamped_to_wheel(tmp_path):
    f = tmp_path / "custom.ini"
    f.write_text(CUSTOM_INI, encoding="utf-8")
    patched = ffb.set_vendor_product(forza.read_ffb_ini("ignored.zip", str(f)), WHEEL)
    vlines = [l for l in patched.splitlines() if l.lower().startswith("vendorproduct")]
    assert vlines == ["VendorProduct 0x346E0015"]  # single line, re-stamped to WHEEL


def test_utf8_bom_stripped_from_external_file(tmp_path):
    # Templates in the game ZIP are utf-8-sig; a custom file may carry a BOM too. read_ffb_ini
    # decodes utf-8-sig for parity, so the first key isn't polluted with a BOM.
    f = tmp_path / "bom.ini"
    f.write_bytes(b"\xef\xbb\xbfVendorProduct 0x346E0005\r\n")
    txt = forza.read_ffb_ini("ignored.zip", str(f))
    assert txt.startswith("VendorProduct")
