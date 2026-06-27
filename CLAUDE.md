# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Textual TUI that configures a sim racing wheel for **Forza Horizon 6** without hand-editing
XML — a faithful Python port of the C# tool [irpina/HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard)
(WinForms/WebView2). The wizard captures **26 logical inputs** from the wheel and **builds a
complete input-mapping profile from scratch**, expanding each captured input into many
`INPUTCMD_*` keys across **10 contexts**, then patches a force-feedback INI and repacks the
game's two media ZIPs (with a backup).

The active package is `hwt/`. The four wizard steps: select devices → locate Forza → live-capture
26 controls → pick FFB template + generate/install. There is also a **Quick mode** (clone a
shipped profile and re-VID/PID it, skipping capture) and a standalone **Device Silencing** screen.

## Commands

```powershell
pip install -r requirements.txt       # runtime: textual + pygame
pip install -r requirements-dev.txt   # + pytest (test suite)
python main.py                        # launch the wizard TUI
python -m pytest -q                   # run the test suite (31 tests)
```

`tests/` is a real pytest suite (schema/golden regression, ffb, pack+verify, quickmode, presets,
silence, plus Windows-only device/forza smoke tests skipped off-Windows). Device enumeration,
device silencing, and install only work on Windows; profile/INI/ZIP generation is portable.

## Architecture (`hwt/`)

`main.py` → `hwt.app.WizardApp().run()`. Modules, in dependency order:

- **`vidpid.py`** — `VidPid` parse/format. `compact` = `"VVVVPPPP"` uppercase (no prefix);
  `to_xml_string()` = `"0x"+compact`. Mirrors the C# `VidPid` struct.
- **`steps.py`** — `STEPS`: the canonical 26 `MappingStep`s (logical key, label, instructions,
  `kind` = "Axis"/"Button"), verbatim from `WheelMapWizard.cs`, **plus** 8 optional trailing
  `GEAR_*` steps (`GEAR_KEYS`) for H-pattern shifters — emitted only under `wider_mappings`. The
  logical keys (`STEER`, `GAS`, `NAV_UP`…) are **not** the XML keys — they are expanded in `profile.py`.
- **`profile.py`** — **the core.** `build_profile_xml(result, options=None)` is a 1:1 port of C#
  `WheelMapWizard.BuildXmlDocument` + its ten `Build*Context` helpers. Each captured logical input
  fans out to multiple `INPUTCMD_*` keys across contexts (e.g. `CONFIRM` →
  `INPUTCMD_ACTIVATE` in RACING and `INPUTCMD_UI_OK_{PRESS,RELEASE,REPEAT,WHILEDOWN}` in UI). This
  expansion table is the heart of the tool — keep it in lockstep with the C# source if changing it.
  The optional `ProfileOptions` (steering `DeadzonesAroundCenter` + inner/outer deadzones, pedal
  deadzones, `is_default_profile`, `profile_id`) is applied **post-build** to the RACING axes;
  `options=None` is byte-identical to the faithful output (guarded by a golden-file test). The
  profile `Id` is now **deterministic** — `stable_profile_id(vidpid)` (a `uuid5` of the VID/PID)
  so re-installs overwrite the same profile instead of spawning a fresh random GUID each run;
  `ProfileOptions.profile_id` pins an explicit id (persisted in presets). `ProfileOptions.wider_mappings`
  (opt-in, off by default) adds the coverage shipped profiles have but the faithful build omits:
  H-pattern **gears** (RACING), brake-as-**left-trigger** (UI), and the whole **`PROP_PLACEMENT_UI`**
  context (`_build_prop_placement`, mapped semantically from already-captured inputs — not in upstream
  C#). Gears come from the optional trailing `GEAR_*` steps in `steps.py` (`GEAR_KEYS`).
- **`quickmode.py`** — Quick mode. Port of C# `XmlProfileEditor`: `list_profiles(input_zip)` lists
  shipped `RawGameController` profiles; `clone_profile_xml(base_xml, wheel, name, patch_in_place)`
  re-VID/PIDs **every** VidPid-bearing attribute to the wheel, sets Primary/FFB, and assigns a new
  uppercase `Id` (kept when patching in place).
- **`presets.py`** — JSON save/load of `WizardState` at `%LOCALAPPDATA%\HorizonWheelWizard\preset.json`
  (roles, paths, mode, base profile, options, bindings). Devices are re-resolved against the live
  device list on load, falling back to a reconstructed `DeviceInfo` if absent.
- **`silence.py`** — enable/disable HID devices via `cfgmgr32` (ctypes) so Forza won't bind a
  phantom/duplicate controller. Port of C# `DeviceSilencer`. All mutations require admin
  (`is_elevated()` / `relaunch_as_admin()`); silenced instance ids persist to a state file.
- **`devices.py`** — Windows SetupAPI HID enumeration (`get_controller_devices`). See the ctypes
  caveat below.
- **`forza.py`** — `find_media_folders` (Steam defaults + **Xbox Game Pass** scan of every fixed
  drive's `XboxGames\…\Content\media` + Steam registry + `libraryfolders.vdf`); FFB template
  list/read. Defines `INPUT_ZIP`/`WHEEL_ZIP`/`BACKUP_DIR`.
- **`ffb.py`** — `set_vendor_product` (INI patch), `output_ini_name`, `pick_template` (closest
  template by VID/PID, else generic) and the OPTIONAL `pick_template_for_model` (template matching a
  chosen base wheel model's VID/PID; returns `""` to fall back to the faithful generic pick).
- **`pack.py`** — store-only (`ZIP_STORED`) repack with flattened top-level entry names; our
  profile is added **alongside** the stock defaults (not replacing them). Backup
  (`HST-BACKUP/`, copy-if-missing), install, restore, and `verify_store_only_top_level` (port of
  C# `ZipVerifier`: fails if any entry is nested or not STORED — run before install).
- **`listener.py`** — headless pygame joystick capture. `arm(expected)` then `wait()`. "Axis"
  steps pick the largest axis deflection from baseline; "Button" steps take the first button OR
  hat direction.
- **`install.py`** — `WizardState` (the single source of truth across screens; carries `mode`
  `"capture"|"quick"`, `base_profile_entry`, `profile_options`, `silenced_ids`) and
  `generate_and_install` (branch capture vs quick → patch INI → repack → **verify** → backup →
  install → **post-install self-check**). `verify_installed_profile` re-opens the *installed* input
  zip and asserts our profile is present, `IsDefaultProfile="1"` (when requested), and every
  per-`Value` `VidPid` carries the `0x` prefix — catching the two historical binding bugs.
- **`app.py`** — the Textual UI: Welcome (Start / Load Preset / **Remap Bindings** / Restore Backup
  / Device Silencing), Step1 roles, Step2 paths + capture/quick mode select, Step3 live capture with
  click-to-re-capture + progress + core-gated Next + **hat/POV guardrail** (warns when a `NAV_*`
  control is captured as a `Switch`, which FH6 menus often won't navigate — directs to button mode),
  Step4 base-model + FFB + optional tuning + Save Preset + install, plus `SilenceScreen` and
  `DoneScreen`. **Remap mode** (`Step3Screen(remap=True)`) loads a preset and opens the capture
  screen in review state so only clicked controls are re-recorded — no full 26-step redo. All
  blocking work runs in `@work(thread=True)` methods that marshal back via
  **`self.app.call_from_thread`** (note: it's on `App`, not `Screen`).

## Canonical Forza profile format (must match exactly)

Verified against the game's own `inputmappingprofiles.zip` (e.g.
`DefaultRawGameControllerMappingProfileLogitechG29.xml`):

- Root `<Profiles>` wrapping one `<RawGameControllerInputMappingProfile Version="1" Id="{GUID-UPPER}"
  UserFacingName="…" IsDefaultProfile="0" PrimaryDeviceVidPid="0x…" FFBDeviceVidPid="0x…"
  FFBMotorIndex="0">`.
- `<Context Version="1" Context="INPUTCONTEXT_*">` (named contexts, not integers), with `<Value>`
  **directly inside** (there is no `<Mapping>` wrapper).
- `<Value Version="1" Key="INPUTCMD_*" VidPid="…" InputType="Axis|Button|Switch" Index="N" …/>`.
  Axis adds `InvertAxis="true|false"`, `InnerDeadzone`, `OuterDeadzone`. Switch (d-pad) uses
  `Index="0"` + `SwitchPosition="Up|Down|Left|Right"`. Map-move uses a composite
  `<Value Key="…"><InputCmdLow/><InputCmdHigh/></Value>`.
- **VID/PID format:** BOTH the header (`PrimaryDeviceVidPid`/`FFBDeviceVidPid`) and **every per-`Value`
  `VidPid` carry the `0x` prefix** (e.g. `VidPid="0x346E0015"`). Verified against the shipped
  `DefaultRawGameControllerMappingProfileLogitechG29.xml` (`VidPid="0x046dc24f"`) and a working
  community Moza mod. **The `0x` prefix is mandatory — without it Forza fails to match the binding to
  the device and NONE of the inputs work** (this was a real bug: earlier code/docs claimed per-`Value`
  used a bare no-`0x` form, which silently produced non-functional profiles). Case is not significant
  (`profile.py` emits `0x`+uppercase; shipped files use lowercase). See `_per_value_vidpid`.

## Deviations / enhancements over upstream (intentional)

1. **Hat → Switch for navigation.** Upstream only polls buttons, so wheels whose d-pad is a hat
   (e.g. the Moza R3 — 1 hat, no nav buttons) can't bind UI nav. The listener also reads hats and
   emits `InputType="Switch"` (the encoding the shipped profiles use).
2. **Broadened `VendorProduct` regex.** Upstream's regex only matches a `0x`-prefixed value, so the
   generic `ControllerFFB-0000000000.ini` (the fallback for unsupported wheels) gets a *duplicate*
   line appended. `ffb.py` matches any value and replaces it.
3. `profile.py` emits `INPUTCMD_OPEN_MAP` and `INPUTCMD_UI_VIEW_*` — present in the C# source but
   not in any shipped profile (likely inert). Kept for fidelity.
4. **Optional, off-by-default knobs.** Smarter FFB auto-pick (`pick_template_for_model`) and steering
   /axis tuning (`ProfileOptions`) are opt-in toggles. With them off, generated output is byte-for-
   byte identical to the faithful build — this invariant is enforced by the golden-file test.

## Gotchas

- **SetupAPI ctypes handle:** `HDEVINFO` is a pointer. `SetupDiGetClassDevsW.restype` and every
  function receiving the handle MUST be `c_void_p`, or ctypes truncates the 64-bit handle to 32
  bits and enumeration silently returns **zero devices** on 64-bit Windows. See `devices.py`.
- FriendlyName is usually empty for HID collections; `devices.py` falls back to the device
  description (e.g. "MOZA Windows Driver").

## Verification

There is no native Moza FFB template in the wheel ZIP, so Step 4 auto-selects the generic
`ControllerFFB-0000000000.ini` and patches its VendorProduct — pick a direct-drive Fanatec template
for better feel. `python -m pytest -q` is the primary gate; it covers:

1. Full 26-input profile re-parsed — 10 contexts, header `0x` VID/PID, per-Value `0x` VID/PID,
   Switch d-pad, axis deadzones, composite map-move pairs — **and** the golden-file regression that
   `options=None` / `ProfileOptions()` output is byte-identical (so the optional knobs — tuning, stable
   id, `wider_mappings` — can't silently drift the faithful default). Plus the `wider_mappings` add-ons
   (gears, left-trigger, prop-placement) and the post-install self-check.
2. `set_vendor_product` yields a single `VendorProduct 0x…` line for both `0x`-prefixed and the
   generic `0000000000` template.
3. Repack + reopen with `zipfile`: STORED, flat names, our profile alongside `…LogitechG29.xml`; and
   `verify_store_only_top_level` passes on ours / fails on a nested or deflated entry.
4. Quick-mode clone: every VidPid attribute → the wheel, new uppercase Id, header Primary/FFB set.
5. Preset round-trip (devices re-resolved); silence state-file round-trip + bogus-id `locate` failure.

Throwaway end-to-end checks (not in pytest — they touch the filesystem): run `generate_and_install`
against a **copy** of the media folder for both modes; assert `HST-BACKUP` holds pristine originals
and is not clobbered on re-install. **Never test installs against the real game folder.**

Final manual gate: run the TUI on the wheel, install, launch FH6, confirm the profile loads. Device
silencing must be tested manually while elevated, on a spare device.

## Repo notes

The root `inputmappingprofiles.zip` / `wheeltunablesettingspc.zip` are real FH6 game data used as
generation inputs and test fixtures.
