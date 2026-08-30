"""Horizon Wheel TUI — the Textual UI layer.

Screens: Welcome → Step1 device roles → Step2 paths+mode → Step3 live 26-step capture →
Step4 FFB/base-model/tuning + generate/install → Done. Plus a standalone SilenceScreen for
enabling/disabling HID devices. Blocking work (device scan, autodetect, joystick capture,
install, device control) runs in @work(thread=True) methods that marshal back to the UI
thread via self.app.call_from_thread.

Round-2 features wired here: Quick mode (clone a supported wheel), preset save/load, restore
backup from Welcome, device silencing, per-control re-capture, and the two OPTIONAL knobs
(smarter FFB auto-pick + steering/axis tuning) which default to the faithful behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, Select, Static,
)

from . import ffb_presets, presets, quickmode, silence
from .devices import DeviceInfo, get_controller_devices
from .ffb import pick_template, pick_template_for_model
from .ffb_presets import find_official_preset
from .forza import INPUT_ZIP, WHEEL_ZIP, find_media_folders, list_ffb_templates
from .install import OFFICIAL_FFB_PREFIX, InstallResult, WizardState, generate_and_install
from .listener import JoystickListener
from .pack import restore_backup
from .profile import MappedInput, ProfileOptions, suggest_profile_name
from .steps import STEPS, category, control_hint
from .vidpid import VidPid

CORE_KEYS = {"STEER", "GAS", "BRAKE"}  # minimum required before install is meaningful

# A Moza wheel enumerates with this VID/PID only while Pit House's "Base Forza Horizon Compatibility"
# is ON — which breaks FH6 (and the official-preset match). The Welcome banner warns about it.
MOZA_FH_COMPAT_VIDPID = "346E0015"


def compat_mode_warning(devices: list[DeviceInfo]) -> tuple[str, bool]:
    """(banner text, is_red) for the Welcome screen. Red + specific when a connected wheel is in
    Moza's Forza-compat mode (0x346E0015); otherwise a muted general reminder."""
    if any(d.vid_pid.compact == MOZA_FH_COMPAT_VIDPID for d in devices):
        return ("⚠  Forza Horizon Compatibility is ON (0x346E0015). Turn it OFF in Moza Pit House "
                "for FH6, then restart this tool.", True)
    return ("Moza users: turn OFF “Base Forza Horizon Compatibility” in Pit House before "
            "using this for FH6.", False)

CSS = """
Screen { background: $surface; }
.step-banner { background: $primary-darken-2; color: $text; height: 5; padding: 1 3; text-style: bold; }
.step-title  { text-style: bold; color: $accent; }
.step-sub    { color: $text-muted; }
.card { border: solid $primary-darken-1; padding: 1 2; margin: 0 0 1 0; height: auto; }
.card-title { color: $accent; text-style: bold; margin-bottom: 1; }
.row { layout: horizontal; height: auto; margin-bottom: 1; align: left middle; }
.lbl { width: 22; color: $text-muted; text-align: right; padding-right: 1; }
.field { width: 1fr; }
Button { margin: 0 1 0 0; }
/* Bottom button bars are direct Screen children. Textual's Horizontal defaults to height:1fr,
   which would split the screen with the scroll area and leave a dead gap; pin them to their
   content height so the scroll area above absorbs all slack. (#binding-split keeps its own
   height:1fr via the higher-specificity id rule below.) */
Screen > Horizontal { height: auto; }
.btn-next  { background: $accent; color: $text; }
.btn-back  { background: $primary-darken-1; }
.btn-skip  { background: $warning-darken-1; }
.btn-danger { background: $error; }
DataTable { height: 12; border: solid $primary-darken-1; }
#binding-split { layout: horizontal; height: 1fr; }
#bind-list  { width: 36; border-right: solid $primary-darken-1; padding: 0 1; }
#bind-prompt { width: 1fr; padding: 2 4; align: center middle; }
.bind-current { color: $accent; text-style: bold; }
.bind-done { color: $success; }
.bind-skip { color: $text-muted; }
.bind-waiting { color: $warning; }
.pulse { text-style: bold; color: $warning; }
.ok { color: $success; } .warn { color: $warning; } .err { color: $error; } .muted { color: $text-muted; }
Log { height: 1fr; border: solid $primary-darken-1; }
#welcome-box { align: center middle; height: 1fr; }
.welcome-art { text-align: center; color: $accent; text-style: bold; margin-bottom: 2; }
.welcome-body { text-align: center; color: $text-muted; margin-bottom: 1; }
#bind-progress { color: $text-muted; margin-bottom: 1; }
"""


def _step_banner(n: int, title: str, sub: str = "") -> ComposeResult:
    with Static(classes="step-banner"):
        yield Static(f"Step {n} of 4", classes="step-sub")
        yield Static(title, classes="step-title")
        if sub:
            yield Static(sub, classes="step-sub")


# ════════════════════════════════════════════════════════════════════════════════════
class WelcomeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="welcome-box"):
            yield Static("🏎   HORIZON WHEEL WIZARD", classes="welcome-art")
            yield Static("Set up your sim racing wheel for Forza Horizon — no XML editing required.",
                         classes="welcome-body")
            yield Static("", classes="welcome-body")
            yield Static("  Step 1  →  Select your wheel & devices", classes="welcome-body")
            yield Static("  Step 2  →  Find your Forza install & pick a mode", classes="welcome-body")
            yield Static("  Step 3  →  Map 26 controls (or skip via Quick mode)", classes="welcome-body")
            yield Static("  Step 4  →  Pick FFB & install", classes="welcome-body")
            yield Static("", classes="welcome-body")
            yield Static("", id="welcome-warn", classes="muted")
            with Horizontal():
                yield Button("Start Setup  →", id="start", classes="btn-next")
                if presets.has_preset():
                    yield Button("📂 Load Preset", id="load-preset")
                    yield Button("✎ Remap Bindings", id="remap")
                yield Button("⟲ Restore Backup", id="restore", classes="btn-skip")
                yield Button("🔇 Device Silencing", id="silence")
            yield Static("", id="welcome-status", classes="welcome-body")
        yield Footer()

    def on_mount(self) -> None:
        self._check_compat_mode()

    @work(thread=True)
    def _check_compat_mode(self) -> None:
        """Scan devices off the UI thread and show the Moza compat-mode banner (red if active)."""
        devs = get_controller_devices()
        self.app.call_from_thread(self._apply_compat_banner, devs)

    def _apply_compat_banner(self, devs: list[DeviceInfo]) -> None:
        text, is_red = compat_mode_warning(devs)
        warn = self.query_one("#welcome-warn", Static)
        warn.update(text)
        warn.set_classes("err" if is_red else "muted")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "start":
            self.app.push_screen(Step1Screen())
        elif bid == "load-preset":
            self.query_one("#welcome-status", Static).update("Loading preset…")
            self._load_preset()
        elif bid == "remap":
            self.query_one("#welcome-status", Static).update("Loading saved bindings…")
            self._remap_bindings()
        elif bid == "restore":
            self.query_one("#welcome-status", Static).update("Restoring backup…")
            self._restore()
        elif bid == "silence":
            self.app.push_screen(SilenceScreen())

    @work(thread=True)
    def _load_preset(self) -> None:
        try:
            devs = get_controller_devices()
            state = presets.load_preset(devices=devs)
        except Exception as exc:
            self.app.call_from_thread(self.query_one("#welcome-status", Static).update,
                                      f"✘  Could not load preset: {exc}")
            return
        self.app.call_from_thread(self._apply_preset, state)

    def _apply_preset(self, state: WizardState) -> None:
        self.app.state = state
        self.app.push_screen(Step1Screen())

    @work(thread=True)
    def _remap_bindings(self) -> None:
        """Load the saved preset and jump straight to the capture screen in review mode, so
        the user can re-record just the control(s) they pick without redoing all 26."""
        try:
            devs = get_controller_devices()
            state = presets.load_preset(devices=devs)
        except Exception as exc:
            self.app.call_from_thread(self.query_one("#welcome-status", Static).update,
                                      f"✘  Could not load preset: {exc}")
            return
        if not state.bindings:
            self.app.call_from_thread(self.query_one("#welcome-status", Static).update,
                                      "✘  Saved preset has no captured bindings to remap "
                                      "(it was saved in Quick mode). Use Start Setup instead.")
            return
        self.app.call_from_thread(self._apply_remap, state)

    def _apply_remap(self, state: WizardState) -> None:
        self.app.state = state
        self.app.push_screen(Step3Screen(remap=True))

    @work(thread=True)
    def _restore(self) -> None:
        mf = self.app.state.media_folder
        if not mf:
            folders = find_media_folders()
            mf = str(folders[0]) if folders else ""
        if not mf:
            self.app.call_from_thread(self.query_one("#welcome-status", Static).update,
                                      "✘  No Forza media folder found to restore.")
            return
        try:
            bf = restore_backup(mf)
            msg = f"✔  Restored originals from {bf}"
        except Exception as exc:
            msg = f"✘  Restore failed: {exc}"
        self.app.call_from_thread(self.query_one("#welcome-status", Static).update, msg)


# ════════════════════════════════════════════════════════════════════════════════════
class Step1Screen(Screen):
    _devices: list[DeviceInfo] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield from _step_banner(1, "Select Your Devices",
                                "Pick your wheelbase and any separate pedals/shifter/handbrake.")
        with ScrollableContainer():
            with Container(classes="card"):
                yield Static("Detected controllers", classes="card-title")
                yield DataTable(id="dev-table", cursor_type="row")
                with Horizontal():
                    yield Button("↻ Refresh", id="refresh")
            with Container(classes="card"):
                yield Static("Role assignment", classes="card-title")
                for role_id, role_label in [
                    ("wb-sel", "Wheelbase / FFB *"), ("ped-sel", "Pedals"),
                    ("sh-sel", "Shifter"), ("hb-sel", "Handbrake"),
                ]:
                    with Horizontal(classes="row"):
                        yield Label(role_label, classes="lbl")
                        yield Select([], id=role_id, classes="field", prompt="— select device —")
            yield Label("", id="step1-err", classes="err")
        with Horizontal():
            yield Button("← Back", id="back", classes="btn-back")
            yield Button("Next →", id="next", classes="btn-next")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#dev-table", DataTable).add_columns("#", "Name", "VID", "PID")
        self._load_devices()

    @work(thread=True)
    def _load_devices(self) -> None:
        devices = get_controller_devices()
        self._devices = devices
        self.app.call_from_thread(self._populate, devices)

    def _populate(self, devices: list[DeviceInfo]) -> None:
        t = self.query_one("#dev-table", DataTable)
        t.clear()
        options = [("— none —", "")]
        for i, d in enumerate(devices, 1):
            t.add_row(str(i), d.name, d.vid_pid.vid, d.vid_pid.pid)
            options.append((d.label(), d.vid_pid.compact))
        for sel_id in ("#wb-sel", "#ped-sel", "#sh-sel", "#hb-sel"):
            try:
                self.query_one(sel_id, Select).set_options(options)
            except NoMatches:
                pass
        # Pre-select roles already present in state (e.g. after a preset load).
        s = self.app.state
        for sel_id, role in (("#wb-sel", s.wheelbase), ("#ped-sel", s.pedals),
                             ("#sh-sel", s.shifter), ("#hb-sel", s.handbrake)):
            if role and any(d.vid_pid.compact == role.vid_pid.compact for d in devices):
                try:
                    self.query_one(sel_id, Select).value = role.vid_pid.compact
                except Exception:
                    pass
        # Convenience: if no wheelbase is chosen yet, default it to the most likely wheel
        # so "Next" works out of the box (the user can still change it).
        if devices and self.query_one("#wb-sel", Select).value not in {d.vid_pid.compact for d in devices}:
            guess = self._guess_wheelbase(devices)
            try:
                self.query_one("#wb-sel", Select).value = guess.vid_pid.compact
                self.query_one("#step1-err", Label).update(
                    f"Auto-selected wheelbase: {guess.name} — change it above if that's wrong.")
            except Exception:
                pass

    _WHEEL_SIGS = ("wheel", "moza", "fanatec", "simagic", "simucube", "thrustmaster",
                   "logitech g", "cammus", "asetek", "vrs")

    def _guess_wheelbase(self, devices: list[DeviceInfo]) -> DeviceInfo:
        for d in devices:
            if any(sig in d.name.lower() for sig in self._WHEEL_SIGS):
                return d
        return devices[0]

    def _find(self, compact: str) -> Optional[DeviceInfo]:
        return next((d for d in self._devices if d.vid_pid.compact == compact), None)

    def _picked(self, sel_id: str) -> Optional[DeviceInfo]:
        """Resolve a role Select to a real device, or None. Keyed off the actual device
        lookup so it's immune to Textual's BLANK/NULL sentinel differences across versions."""
        val = self.query_one(sel_id, Select).value
        return self._find(val) if isinstance(val, str) and val else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self._load_devices()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "next":
            wb = self._picked("#wb-sel")
            if wb is None:
                msg = ("⚠  Select your Wheelbase / FFB device."
                       if self._devices else
                       "⚠  No controllers detected — plug in / power on your wheel, then ↻ Refresh.")
                self.query_one("#step1-err", Label).update(msg)
                return
            s = self.app.state
            s.wheelbase = wb
            s.pedals    = self._picked("#ped-sel")
            s.shifter   = self._picked("#sh-sel")
            s.handbrake = self._picked("#hb-sel")
            self.app.push_screen(Step2Screen())


# ════════════════════════════════════════════════════════════════════════════════════
class Step2Screen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield from _step_banner(2, "Find Your Forza Install",
                                "Point the wizard at your game folder, output location, and setup mode.")
        with ScrollableContainer():
            with Container(classes="card"):
                yield Static("Game location", classes="card-title")
                for fid, flbl, fph in [
                    ("media-dir", "Media folder *", r"…\ForzaHorizon6\media"),
                    ("input-zip", "Input mapping ZIP", INPUT_ZIP),
                    ("wheel-zip", "Wheel tune ZIP", WHEEL_ZIP),
                ]:
                    with Horizontal(classes="row"):
                        yield Label(flbl, classes="lbl")
                        yield Input(placeholder=fph, id=fid, classes="field")
                yield Button("🔍 Auto-detect", id="autodetect", variant="primary")
                yield Label("", id="detect-status", classes="muted")
            with Container(classes="card"):
                yield Static("Output folder", classes="card-title")
                with Horizontal(classes="row"):
                    yield Label("Output folder *", classes="lbl")
                    yield Input(placeholder="Where generated files are saved", id="out-dir", classes="field")
            with Container(classes="card"):
                yield Static("Setup mode", classes="card-title")
                with Horizontal(classes="row"):
                    yield Label("Mode", classes="lbl")
                    yield Select(
                        [("Full capture — map all 26 controls live", "capture"),
                         ("Quick — clone a supported wheel's profile", "quick")],
                        id="mode-sel", classes="field", allow_blank=False, value="capture")
                yield Label("Quick mode skips live capture and re-VID/PIDs a shipped profile "
                            "(you'll pick the base wheel on the next screen).", classes="muted")
            yield Label("", id="step2-err", classes="err")
        with Horizontal():
            yield Button("← Back", id="back", classes="btn-back")
            yield Button("Next →", id="next", classes="btn-next")
        yield Footer()

    def on_mount(self) -> None:
        s = self.app.state
        if s.media_folder:
            self.query_one("#media-dir", Input).value = s.media_folder
            self.query_one("#input-zip", Input).value = s.input_zip
            self.query_one("#wheel-zip", Input).value = s.wheel_zip
            self.query_one("#out-dir", Input).value = s.output_folder
        else:
            self._autodetect()
        try:
            self.query_one("#mode-sel", Select).value = s.mode or "capture"
        except Exception:
            pass

    @work(thread=True)
    def _autodetect(self) -> None:
        folders = find_media_folders()
        if not folders:
            self.app.call_from_thread(self.query_one("#detect-status", Label).update,
                                      "No Forza install found — enter paths manually.")
            return
        self.app.call_from_thread(self._apply_folder, folders[0])

    def _apply_folder(self, mf: Path) -> None:
        self.query_one("#media-dir", Input).value = str(mf)
        iz, wz = mf / INPUT_ZIP, mf / WHEEL_ZIP
        if iz.exists():
            self.query_one("#input-zip", Input).value = str(iz)
        if wz.exists():
            self.query_one("#wheel-zip", Input).value = str(wz)
        self.query_one("#out-dir", Input).value = str(mf.parent / "HorizonWheelTUI-output")
        self.query_one("#detect-status", Label).update(f"✔  Found: {mf}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "autodetect":
            self._autodetect()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "next":
            mf  = self.query_one("#media-dir", Input).value.strip()
            iz  = self.query_one("#input-zip", Input).value.strip()
            wz  = self.query_one("#wheel-zip", Input).value.strip()
            out = self.query_one("#out-dir", Input).value.strip()
            if not (mf and iz and wz and out):
                self.query_one("#step2-err", Label).update("⚠  All fields are required.")
                return
            for path, lbl in ((iz, INPUT_ZIP), (wz, WHEEL_ZIP)):
                if not Path(path).exists():
                    self.query_one("#step2-err", Label).update(f"⚠  Not found: {path}")
                    return
            s = self.app.state
            s.media_folder, s.input_zip, s.wheel_zip, s.output_folder = mf, iz, wz, out
            mode = self.query_one("#mode-sel", Select).value
            s.mode = str(mode) if mode and mode is not Select.BLANK else "capture"
            if s.mode == "quick":
                self.app.push_screen(Step4Screen())   # skip live capture
            else:
                self.app.push_screen(Step3Screen())


# ════════════════════════════════════════════════════════════════════════════════════
class Step3Screen(Screen):
    _cursor: int = 0
    _waiting: bool = False
    _skipped: set[str]

    def __init__(self, remap: bool = False) -> None:
        """remap=True starts in the review state showing already-captured bindings (loaded
        from a preset) so the user can click just the control(s) they want to re-record,
        instead of walking all 26 steps again."""
        super().__init__()
        self._remap = remap

    def compose(self) -> ComposeResult:
        self._skipped = set()
        yield Header()
        yield from _step_banner(3, "Map Your Controls",
                                "Press each control when prompted. Click any control on the left to re-capture it.")
        with Horizontal(id="binding-split"):
            with ScrollableContainer(id="bind-list"):
                last_cat = None
                for s in STEPS:
                    cat = category(s.key)
                    if cat != last_cat:
                        yield Static(cat, classes="card-title")
                        last_cat = cat
                    yield Label("○ " + s.label, id=f"sl-{s.key}", classes="bind-waiting")
            with Container(id="bind-prompt"):
                yield Static("", id="bind-progress")
                yield Static("", id="prompt-cmd", classes="bind-current")
                yield Static("", id="prompt-hint", classes="muted")
                yield Static("", id="prompt-xbox", classes="muted")
                yield Static("", id="prompt-status", classes="pulse")
                yield Static("", id="prompt-result", classes="bind-done")
                yield Static("", id="prompt-joy", classes="muted")
                yield Static("", id="prompt-warn", classes="warn")
                yield Static("")
                with Horizontal():
                    yield Button("Accept ✔", id="btn-accept", variant="primary", disabled=True)
                    yield Button("Retry ↺", id="btn-retry", disabled=True)
                    yield Button("Skip →", id="btn-skip", classes="btn-skip")
        with Horizontal():
            yield Button("← Back", id="back", classes="btn-back")
            yield Button("Next →", id="next", classes="btn-next", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        if self._remap and self.app.state.bindings:
            self._enter_review()
        else:
            self._advance_to(0)

    def _enter_review(self) -> None:
        """Show every control with its current binding state and stop capturing — the user
        clicks the one(s) to re-record. Used for remap and after finishing a full run."""
        self._waiting = False
        for s in STEPS:
            self._restore_label(s.key)
        self._cursor = len(STEPS)
        self._all_done()

    # ── progress / next-gate ──
    def _update_progress(self) -> None:
        s = self.app.state
        n = len(s.bindings)
        missing = sorted(CORE_KEYS - set(s.bindings))
        core_ok = not missing
        self.query_one("#bind-progress", Static).update(
            f"{n} / {len(STEPS)} captured"
            + ("" if core_ok else f"  ·  need: {', '.join(missing)}"))
        self.query_one("#next", Button).disabled = not core_ok

    def _label_state(self, key: str) -> tuple[str, str]:
        step = next(s for s in STEPS if s.key == key)
        if key in self.app.state.bindings:
            return "✓ " + step.label, "bind-done"
        if key in self._skipped:
            return "— " + step.label + " (skipped)", "bind-skip"
        return "○ " + step.label, "bind-waiting"

    def _restore_label(self, key: str) -> None:
        text, cls = self._label_state(key)
        self._mark(key, text, cls)

    # ── capture flow ──
    def _advance_to(self, idx: int) -> None:
        self._cursor = idx
        self._waiting = False
        if idx >= len(STEPS):
            self._all_done()
            return
        step = STEPS[idx]
        self.query_one("#prompt-cmd", Static).update(step.label)
        self.query_one("#prompt-hint", Static).update(step.instructions)
        self.query_one("#prompt-xbox", Static).update(control_hint(step.key))
        self.query_one("#prompt-status", Static).update("⏳  Waiting for input…")
        self.query_one("#prompt-result", Static).update("")
        self.query_one("#prompt-joy", Static).update("")
        self.query_one("#prompt-warn", Static).update("")
        self.query_one("#btn-accept", Button).disabled = True
        self.query_one("#btn-retry", Button).disabled = True
        self.query_one("#btn-skip", Button).disabled = False
        self._mark(step.key, "◉ " + step.label, "bind-current")
        self._update_progress()
        self._start_capture(step)

    def _jump_to(self, key: str) -> None:
        """Re-capture a single control the user clicked (works mid-run or after completion)."""
        idx = next((i for i, s in enumerate(STEPS) if s.key == key), None)
        if idx is None or idx == self._cursor and self._waiting:
            return
        self._waiting = False
        self.app.listener.cancel()
        if 0 <= self._cursor < len(STEPS):
            self._restore_label(STEPS[self._cursor].key)  # un-highlight the old current
        self._skipped.discard(key)
        self.app.state.bindings.pop(key, None)
        self._advance_to(idx)

    @work(thread=True)
    def _start_capture(self, step) -> None:
        self._waiting = True
        self.app.listener.arm(expected=step.kind)
        event = self.app.listener.wait(timeout=120)
        if not self._waiting:
            return
        self._waiting = False
        if event is None:
            self.app.call_from_thread(self._on_timeout)
        else:
            self.app.call_from_thread(self._on_captured, step, event)

    def _on_captured(self, step, event) -> None:
        # Prefer the VID/PID of the device that actually produced the input (from its SDL GUID);
        # only fall back to fuzzy name→role matching when the GUID had no usable VID/PID. This is
        # what keeps a second device (button hub / shifter) from being mis-attributed to the
        # wheelbase — the cause of the "2nd device not in profile" bug (issue #1).
        dev_vp = event.device_vidpid
        if not dev_vp:
            role = self.app.state.role_for_joystick(event.joystick_name)
            dev_vp = role.vid_pid.compact if role else ""
        self.app.state.bindings[step.key] = MappedInput(
            input_type=event.input_type, index=event.index,
            invert_axis=event.invert_axis, switch_position=event.switch_position,
            device_vidpid=dev_vp,
        )
        self.query_one("#prompt-status", Static).update("✔  Input detected:")
        self.query_one("#prompt-result", Static).update(event.human_label())
        self.query_one("#prompt-joy", Static).update(
            f"Device: {event.joystick_name}" if event.joystick_name else "")
        self._warn_if_hat_nav(step, event)
        self.query_one("#btn-accept", Button).disabled = False
        self.query_one("#btn-retry", Button).disabled = False

    def _warn_if_hat_nav(self, step, event) -> None:
        """FH6's front-end menus won't navigate from a d-pad reported as a hat/POV (Switch).
        If a NAV_* control was captured that way, steer the user to button mode."""
        warn = self.query_one("#prompt-warn", Static)
        if step.key.startswith("NAV_") and event.input_type == "Switch":
            warn.update("⚠  Captured as a POV-hat (Switch). FH6 menus often won't navigate "
                        "from a hat — set your wheel's d-pad to BUTTON mode (e.g. Moza Pit "
                        "House) and re-capture if menu nav doesn't work.")
        else:
            warn.update("")

    def _on_timeout(self) -> None:
        self.query_one("#prompt-status", Static).update("⏱  Timed out — press Retry or Skip.")
        self.query_one("#btn-retry", Button).disabled = False

    def _mark(self, key: str, text: str, cls: str) -> None:
        try:
            lbl = self.query_one(f"#sl-{key}", Label)
            lbl.update(text)
            lbl.set_classes(cls)
        except NoMatches:
            pass

    def _all_done(self) -> None:
        n = len(self.app.state.bindings)
        self.query_one("#prompt-cmd", Static).update("All controls visited!")
        self.query_one("#prompt-hint", Static).update(
            "Click any control on the left to re-capture it, or press Next.")
        self.query_one("#prompt-xbox", Static).update("")
        self.query_one("#prompt-status", Static).update(
            f"✔  {n} controls captured. Press Next to choose FFB and install.")
        self.query_one("#prompt-result", Static).update("")
        self.query_one("#btn-accept", Button).disabled = True
        self.query_one("#btn-retry", Button).disabled = True
        self.query_one("#btn-skip", Button).disabled = True
        self._update_progress()

    def on_click(self, event) -> None:
        try:
            widget, _ = self.get_widget_at(event.screen_x, event.screen_y)
        except Exception:
            return
        wid = getattr(widget, "id", None) or ""
        if wid.startswith("sl-"):
            self._jump_to(wid[3:])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-accept":
            step = STEPS[self._cursor]
            self._mark(step.key, "✓ " + step.label, "bind-done")
            if self._remap:
                self._enter_review()   # re-record one control, then back to the overview
            else:
                self._advance_to(self._cursor + 1)
        elif bid == "btn-retry":
            self._waiting = False
            self.app.listener.cancel()
            step = STEPS[self._cursor]
            self.app.state.bindings.pop(step.key, None)
            self.query_one("#prompt-result", Static).update("")
            self.query_one("#prompt-status", Static).update("⏳  Waiting for input…")
            self.query_one("#btn-accept", Button).disabled = True
            self.query_one("#btn-retry", Button).disabled = True
            self._start_capture(step)
        elif bid == "btn-skip":
            step = STEPS[self._cursor]
            self._waiting = False
            self.app.listener.cancel()
            self.app.state.bindings.pop(step.key, None)
            self._skipped.add(step.key)
            self._mark(step.key, "— " + step.label + " (skipped)", "bind-skip")
            if self._remap:
                self._enter_review()
            else:
                self._advance_to(self._cursor + 1)
        elif bid == "back":
            self._waiting = False
            self.app.listener.cancel()
            self.app.pop_screen()
        elif bid == "next":
            self.app.push_screen(Step4Screen())


# ════════════════════════════════════════════════════════════════════════════════════
class Step4Screen(Screen):
    _ffb_entries: list[str]
    _base_profiles: list

    def compose(self) -> ComposeResult:
        self._ffb_entries = []
        self._base_profiles = []
        yield Header()
        yield from _step_banner(4, "Generate & Install",
                                "Name the profile, pick a base model / FFB template, then install.")
        with ScrollableContainer():
            with Container(classes="card"):
                yield Static("Summary", classes="card-title")
                yield Static("", id="binding-summary", classes="muted")
            with Container(classes="card"):
                yield Static("Profile", classes="card-title")
                with Horizontal(classes="row"):
                    yield Label("Profile name", classes="lbl")
                    yield Input(id="profile-name", classes="field")
                yield Checkbox("Set as default profile (auto-apply) — required for wheels Forza "
                               "doesn't natively support, e.g. Moza", id="default-profile", value=True)
                with Container(id="wider-group"):
                    yield Static("Wider mappings (capture mode only) — extra coverage the "
                                 "faithful build omits. Enable any independently:", classes="muted")
                    yield Checkbox("H-pattern gears (RACING) — only emitted if you captured gear inputs",
                                   id="wider-gears", value=False)
                    yield Checkbox("Brake-as-menu-trigger (left trigger in menus, WARNING: may BREAK map navigation on some pedals/wheels, use with CAUTION!)",
                                   id="wider-ltrigger", value=False)
                    yield Checkbox("EventLab prop-placement controls",
                                   id="wider-prop", value=False)
            with Container(classes="card", id="base-card"):
                yield Static("Base wheel model", id="base-title", classes="card-title")
                yield Label("", id="base-help", classes="muted")
                with Horizontal(classes="row"):
                    yield Label("Base model", classes="lbl")
                    yield Select([], id="base-sel", classes="field", prompt="— loading… —")
                yield Label("", id="base-status", classes="muted")
            with Container(classes="card"):
                yield Static("Force Feedback template", classes="card-title")
                yield Label("No native Moza template ships with the game — a direct-drive Fanatec "
                            "template is a good starting point for unsupported wheels.", classes="muted")
                with Horizontal(classes="row", id="ffb-model-row"):
                    yield Label("Borrow FFB from", classes="lbl")
                    yield Select([], id="ffb-model-sel", classes="field",
                                 prompt="— optional: a supported wheel to auto-fill the template —")
                with Horizontal(classes="row"):
                    yield Label("FFB INI template", classes="lbl")
                    yield Select([], id="ffb-sel", classes="field", prompt="— loading… —")
                yield Label("", id="ffb-status", classes="muted")
                with Horizontal(classes="row"):
                    yield Label("Custom .ini (optional)", classes="lbl")
                    yield Input(placeholder="Path to a custom ControllerFFB-*.ini — overrides the dropdown",
                                id="ffb-custom", classes="field")
                yield Label("", id="ffb-custom-status", classes="muted")
            with Container(classes="card", id="tuning-card"):
                yield Static("Advanced axis tuning (optional)", classes="card-title")
                yield Label("Off by default → faithful output. Enable to add steering deadzones "
                            "and custom axis ranges.", classes="muted")
                yield Checkbox("Enable advanced tuning", id="tune-enable", value=False)
                yield Checkbox("Add steering deadzones around center", id="tune-dz", value=False)
                with Horizontal(classes="row"):
                    yield Label("Steer inner / outer", classes="lbl")
                    yield Input(value="0.0", id="steer-inner", classes="field")
                    yield Input(value="1.0", id="steer-outer", classes="field")
                with Horizontal(classes="row"):
                    yield Label("Pedal inner / outer", classes="lbl")
                    yield Input(value="0.0", id="pedal-inner", classes="field")
                    yield Input(value="1.0", id="pedal-outer", classes="field")
            with Container(classes="card"):
                yield Static("Install log", classes="card-title")
                yield Log(id="install-log", highlight=True)
            yield Label("", id="step4-err", classes="err")
        with Horizontal():
            yield Button("← Back", id="back", classes="btn-back")
            yield Button("💾 Save Preset", id="save-preset")
            yield Button("⚡ Generate & Install", id="install", classes="btn-next")
        yield Footer()

    def on_mount(self) -> None:
        s = self.app.state
        self.query_one("#profile-name", Input).value = s.profile_name or suggest_profile_name(
            s.wheelbase.name if s.wheelbase else "My Wheel")
        if s.mode == "quick":
            self.query_one("#base-help", Label).update(
                "Quick mode: pick the wheel whose shipped profile to clone and re-VID/PID. *required")
            self.query_one("#tuning-card").display = False  # tuning applies to captured profiles only
            self.query_one("#wider-group").display = False  # capture-mode only
            # Quick mode already picks a clone-source wheel above; the FFB borrow dropdown would
            # be a confusing second model selector, so hide it — FFB stays auto/manual/custom.
            self.query_one("#ffb-model-row").display = False
        else:
            # Capture mode: mappings came from Step 3, so the base-model card has no job here.
            # Its only leftover use (auto-pick an FFB template) now lives inside the FFB card.
            self.query_one("#base-card").display = False
        # A saved custom template is a filesystem path (has a separator / is absolute), unlike
        # a bare ZIP entry name — prefill the field so presets round-trip visibly. Setting the
        # value fires on_input_changed, which restores the status + state.ffb_template_entry.
        saved = s.ffb_template_entry
        if saved and ("\\" in saved or "/" in saved or Path(saved).is_absolute()):
            self.query_one("#ffb-custom", Input).value = saved
        self._show_summary()
        self._load_base_models()
        self._load_templates()

    def _show_summary(self) -> None:
        s = self.app.state
        lines = [f"Mode:       {'Quick clone' if s.mode == 'quick' else 'Full capture'}",
                 f"Wheelbase:  {s.wheelbase.name if s.wheelbase else '?'} ({s.wheelbase_vidpid()})"]
        for role, name in ((s.pedals, "Pedals"), (s.shifter, "Shifter"), (s.handbrake, "Handbrake")):
            if role:
                lines.append(f"{name+':':11} {role.name}")
        lines.append("")
        if s.mode == "quick":
            lines.append("Quick mode — profile is cloned from the chosen base model below.")
        else:
            captured = len(s.bindings)
            lines.append(f"{captured} of {len(STEPS)} controls captured "
                         f"({len(STEPS) - captured} skipped).")
        self.query_one("#binding-summary", Static).update("\n".join(lines))

    # ── base models ──
    @work(thread=True)
    def _load_base_models(self) -> None:
        try:
            profs = quickmode.list_profiles(self.app.state.input_zip)
        except Exception as exc:
            self.app.call_from_thread(self.query_one("#base-status", Label).update,
                                      f"⚠  Could not list base profiles: {exc}")
            return
        self.app.call_from_thread(self._apply_base_models, profs)

    def _apply_base_models(self, profs: list) -> None:
        self._base_profiles = profs
        s = self.app.state
        # Capture mode's FFB-borrow dropdown lists the same wheels, with a "none" default so the
        # generic pick stays in force until the user opts in. (Only shown in capture mode.)
        model_opts = [("— none / generic FFB —", "")]
        model_opts += [(b.user_facing_name or b.entry, b.entry) for b in profs]
        self.query_one("#ffb-model-sel", Select).set_options(model_opts)
        options = ([] if s.mode == "quick" else [("— none / generic FFB —", "")])
        options += [(b.user_facing_name or b.entry, b.entry) for b in profs]
        sel = self.query_one("#base-sel", Select)
        sel.set_options(options)
        chosen = ""
        if s.base_profile_entry and any(b.entry == s.base_profile_entry for b in profs):
            chosen = s.base_profile_entry
        elif s.mode == "quick":
            wb = s.wheelbase_vidpid().compact
            match = next((b for b in profs if b.primary_vidpid == wb), None)
            chosen = match.entry if match else (profs[0].entry if profs else "")
        if chosen:
            try:
                sel.value = chosen
            except Exception:
                pass
            s.base_profile_entry = chosen

    # ── ffb templates ──
    @work(thread=True)
    def _load_templates(self) -> None:
        try:
            entries = list_ffb_templates(self.app.state.wheel_zip)
        except Exception as exc:
            self.app.call_from_thread(self.query_one("#ffb-status", Label).update,
                                      f"⚠  Could not load templates: {exc}")
            return
        self.app.call_from_thread(self._apply_templates, entries)

    def _apply_templates(self, entries: list[str]) -> None:
        self._ffb_entries = entries  # game-ZIP templates only; pick_template ranges over these
        s = self.app.state
        # Bundled official Moza presets are offered FIRST (selectable by any wheel — the installer
        # re-patches VendorProduct), each keyed by an `official:<compact>` sentinel value.
        self._official = ffb_presets.list_official_presets()
        official_opts = [(p.label(), OFFICIAL_FFB_PREFIX + p.compact) for p in self._official]
        sel = self.query_one("#ffb-sel", Select)
        sel.set_options(official_opts + [(e, e) for e in entries])

        valid = {OFFICIAL_FFB_PREFIX + p.compact for p in self._official} | set(entries)
        auto = find_official_preset(s.wheelbase_vidpid())
        if s.ffb_template_entry and s.ffb_template_entry in valid:
            best = s.ffb_template_entry
            note = f"Using saved: {best}"
        elif auto is not None:  # wheel VID/PID matches a bundled preset → auto-select it
            best = OFFICIAL_FFB_PREFIX + auto.compact
            note = f"✨ Official Moza {auto.model} FFB preset auto-selected"
        else:
            best = pick_template(entries, s.wheelbase_vidpid())
            note = f"Auto-selected closest: {best}" if best else ""
        if best:
            sel.value = best
            self.query_one("#ffb-status", Label).update(note)
            if not self._custom_ffb():  # a custom path, if set, owns ffb_template_entry
                s.ffb_template_entry = best

    def _selected_ffb_model(self):
        """The wheel model chosen in the capture-mode FFB-borrow dropdown, or None."""
        val = str(self.query_one("#ffb-model-sel", Select).value or "")
        return next((b for b in self._base_profiles if b.entry == val), None)

    def _custom_ffb(self) -> str:
        """Trimmed custom-template path, or "" if the field is empty/absent. A non-empty
        value takes precedence over the ZIP dropdown everywhere below."""
        try:
            return self.query_one("#ffb-custom", Input).value.strip()
        except NoMatches:
            return ""

    def _recompute_ffb(self) -> None:
        """Auto-fill the FFB template from the optionally chosen wheel model; a blank/no match
        falls back to the faithful generic pick. Skipped when a custom path is active."""
        if not self._ffb_entries or self._custom_ffb():  # custom path overrides auto-pick
            return
        sel = self.query_one("#ffb-sel", Select)
        status = self.query_one("#ffb-status", Label)
        model = self._selected_ffb_model()
        if model and len(model.primary_vidpid) == 8:
            vp = VidPid(model.primary_vidpid[:4], model.primary_vidpid[4:])
            cand = pick_template_for_model(self._ffb_entries, vp)
            if cand:
                sel.value = cand
                self.app.state.ffb_template_entry = cand
                status.update(f"Using {model.user_facing_name} FFB: {cand}")
                return
            status.update(f"No FFB template matches {model.user_facing_name}; using generic.")
        best = pick_template(self._ffb_entries, self.app.state.wheelbase_vidpid())
        if best:
            sel.value = best
            self.app.state.ffb_template_entry = best

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        if event.select.id == "ffb-sel":
            if not self._custom_ffb():  # don't let the dropdown clobber an active custom path
                self.app.state.ffb_template_entry = str(event.value)
        elif event.select.id == "ffb-model-sel":
            self._recompute_ffb()  # borrow FFB from the chosen wheel model (or revert to generic)
        elif event.select.id == "base-sel":
            self.app.state.base_profile_entry = str(event.value)  # quick-mode clone source

    def on_input_changed(self, event: Input.Changed) -> None:
        """Custom FFB path field: non-empty wins over the dropdown; empty reverts to it.
        We store even a not-yet-existing path so install-time validation can block on it."""
        if event.input.id != "ffb-custom":
            return
        status = self.query_one("#ffb-custom-status", Label)
        val = event.value.strip()
        if not val:  # cleared → hand control back to the auto-picked dropdown entry
            status.set_classes("muted")
            status.update("")
            sel_val = self.query_one("#ffb-sel", Select).value
            if sel_val is not Select.BLANK:
                self.app.state.ffb_template_entry = str(sel_val)
            return
        self.app.state.ffb_template_entry = val
        if Path(val).is_file():
            status.set_classes("ok")
            status.update(f"✔  Using custom template: {Path(val).name}")
        else:
            status.set_classes("err")
            status.update("✘  File not found — fix the path or clear it to use the dropdown.")

    def _build_options(self) -> Optional[ProfileOptions]:
        """Assemble ProfileOptions from the UI. Returns None only when nothing is enabled
        (preserving faithful output). The 'default profile' flag applies in both modes;
        'wider mappings' only affects the capture-mode build."""
        def _checked(sel: str) -> bool:
            try:
                return bool(self.query_one(sel, Checkbox).value)
            except NoMatches:
                return False
        default_on = _checked("#default-profile")
        if self.app.state.mode == "quick":
            return ProfileOptions(is_default_profile=default_on) if default_on else None
        gears = _checked("#wider-gears")
        left_trigger = _checked("#wider-ltrigger")
        prop = _checked("#wider-prop")
        tune_on = _checked("#tune-enable")
        if not (default_on or gears or left_trigger or prop or tune_on):
            return None
        opts = ProfileOptions(is_default_profile=default_on, wider_gears=gears,
                              wider_left_trigger=left_trigger, wider_prop_placement=prop)
        if tune_on:
            try:
                opts.steer_deadzones_around_center = _checked("#tune-dz")
                opts.steer_inner_deadzone = self.query_one("#steer-inner", Input).value.strip() or "0.0"
                opts.steer_outer_deadzone = self.query_one("#steer-outer", Input).value.strip() or "1.0"
                opts.pedal_inner_deadzone = self.query_one("#pedal-inner", Input).value.strip() or "0.0"
                opts.pedal_outer_deadzone = self.query_one("#pedal-outer", Input).value.strip() or "1.0"
            except NoMatches:
                pass
        return opts

    def _sync_state(self) -> None:
        s = self.app.state
        s.profile_name = self.query_one("#profile-name", Input).value.strip()
        s.profile_options = self._build_options()

    @work(thread=True)
    def _run_install(self) -> None:
        log = self.query_one("#install-log", Log)
        _log = lambda msg: self.app.call_from_thread(log.write_line, msg)
        try:
            self.app.call_from_thread(self.query_one("#install", Button).__setattr__, "disabled", True)
            result = generate_and_install(self.app.state, _log)
            self.app.call_from_thread(self.app.push_screen, DoneScreen(result))
        except Exception as exc:
            _log(f"✘  Error: {exc}")
            self.app.call_from_thread(self.query_one("#step4-err", Label).update, f"✘  {exc}")
            self.app.call_from_thread(self.query_one("#install", Button).__setattr__, "disabled", False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "back":
            self.app.pop_screen()
        elif bid == "save-preset":
            self._sync_state()
            try:
                p = presets.save_preset(self.app.state)
                self.query_one("#step4-err", Label).set_classes("ok")
                self.query_one("#step4-err", Label).update(f"✔  Preset saved to {p}")
            except Exception as exc:
                self.query_one("#step4-err", Label).set_classes("err")
                self.query_one("#step4-err", Label).update(f"✘  Could not save preset: {exc}")
        elif bid == "install":
            self._sync_state()
            self.query_one("#step4-err", Label).set_classes("err")
            if self.app.state.mode == "quick" and not self.app.state.base_profile_entry:
                self.query_one("#step4-err", Label).update("⚠  Quick mode needs a base wheel model.")
                return
            if not self.app.state.ffb_template_entry:
                self.query_one("#step4-err", Label).update("⚠  Select an FFB template first.")
                return
            custom = self._custom_ffb()
            if custom and not Path(custom).is_file():
                self.query_one("#step4-err", Label).update("⚠  Custom FFB file not found.")
                return
            self._run_install()


# ════════════════════════════════════════════════════════════════════════════════════
class SilenceScreen(Screen):
    """Enable/disable HID controllers so Forza doesn't bind a phantom/duplicate device."""
    _devices: list[DeviceInfo] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield from _step_banner(0, "Device Silencing",
                                "Disable controllers you don't want Forza to see (requires admin).")
        with ScrollableContainer():
            with Container(classes="card"):
                yield Static("Connected controllers", classes="card-title")
                yield DataTable(id="sil-table", cursor_type="row")
                yield Label("", id="sil-elev", classes="warn")
                yield Label("", id="sil-status", classes="muted")
        with Horizontal():
            yield Button("← Back", id="back", classes="btn-back")
            yield Button("↻ Refresh", id="sil-refresh")
            yield Button("🔇 Disable", id="sil-disable", classes="btn-danger")
            yield Button("🔊 Enable", id="sil-enable")
            yield Button("🛡 Relaunch as Admin", id="sil-admin", classes="btn-skip")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#sil-table", DataTable).add_columns("Name", "VID", "PID", "Status")
        elevated = silence.is_elevated()
        if not elevated:
            self.query_one("#sil-elev", Label).update(
                "⚠  Not running as admin — enable/disable will fail. Use “Relaunch as Admin”.")
        self.query_one("#sil-disable", Button).disabled = not elevated
        self.query_one("#sil-enable", Button).disabled = not elevated
        self.query_one("#sil-admin", Button).display = not elevated
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        devs = get_controller_devices()
        statuses = {d.instance_id: silence.get_status(d.instance_id) for d in devs}
        self.app.call_from_thread(self._populate, devs, statuses)

    def _populate(self, devs: list[DeviceInfo], statuses: dict[str, str]) -> None:
        self._devices = devs
        t = self.query_one("#sil-table", DataTable)
        t.clear()
        for d in devs:
            t.add_row(d.name, d.vid_pid.vid, d.vid_pid.pid, statuses.get(d.instance_id, "?"))

    def _selected(self) -> Optional[DeviceInfo]:
        t = self.query_one("#sil-table", DataTable)
        row = t.cursor_row
        if row is None or not (0 <= row < len(self._devices)):
            return None
        return self._devices[row]

    @work(thread=True)
    def _toggle(self, instance_id: str, enable: bool) -> None:
        try:
            if enable:
                silence.enable_device(instance_id)
            else:
                silence.disable_device(instance_id)
            ids = silence.load_silenced_ids()
            low = {i.lower() for i in ids}
            if enable:
                ids = [i for i in ids if i.lower() != instance_id.lower()]
            elif instance_id.lower() not in low:
                ids.append(instance_id)
            silence.save_silenced_ids(ids)
            self.app.state.silenced_ids = ids
            msg = f"✔  {'Enabled' if enable else 'Disabled'} {instance_id}"
        except Exception as exc:
            msg = f"✘  {exc}"
        self.app.call_from_thread(self.query_one("#sil-status", Label).update, msg)
        self.app.call_from_thread(self._load)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "back":
            self.app.pop_screen()
        elif bid == "sil-refresh":
            self._load()
        elif bid in ("sil-disable", "sil-enable"):
            dev = self._selected()
            if dev is None:
                self.query_one("#sil-status", Label).update("⚠  Select a device row first.")
                return
            if not dev.instance_id:
                self.query_one("#sil-status", Label).update("⚠  Device has no instance id.")
                return
            self.query_one("#sil-status", Label).update("Working…")
            self._toggle(dev.instance_id, enable=(bid == "sil-enable"))
        elif bid == "sil-admin":
            if silence.relaunch_as_admin():
                self.app.exit()
            else:
                self.query_one("#sil-status", Label).update("✘  Could not relaunch as admin.")


# ════════════════════════════════════════════════════════════════════════════════════
class DoneScreen(Screen):
    def __init__(self, result: Optional[InstallResult] = None) -> None:
        super().__init__()
        self._result = result

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="welcome-box"):
            yield Static("🏁   Setup Complete!", classes="welcome-art")
            yield Static("Your wheel profile and FFB files have been installed.\n"
                         "Launch Forza Horizon and select your profile in Controls.",
                         classes="welcome-body")
            yield Static("")
            yield Static(self._files_report(), classes="welcome-body")
            yield Static("", id="restore-status", classes="welcome-body")
            yield Static("")
            with Horizontal():
                yield Button("↺  Run Wizard Again", id="restart")
                yield Button("💾  Save Preset", id="save-preset")
                yield Button("⟲  Restore Backup", id="restore", classes="btn-skip")
                yield Button("Quit", id="quit", classes="btn-danger")
        yield Footer()

    def _files_report(self) -> str:
        """Human-readable list of exactly what the install wrote: the two archives replaced in
        the media folder and the entry ADDED inside each (alongside the stock defaults)."""
        r = self._result
        if r is None:  # defensive — DoneScreen is always constructed with a result today
            s = self.app.state
            return f"Media folder:  {s.media_folder}\nBackup:        {s.media_folder}\\HST-BACKUP\\"
        return (
            f"Installed into:  {r.media_folder}\n"
            f"Originals backed up to:  {r.backup_dir}\n"
            f"\nArchives updated (entry added alongside the stock defaults):\n"
            f"  {r.input_zip}\n"
            f"      + {r.profile_entry}   (your mapping profile)\n"
            f"  {r.wheel_zip}\n"
            f"      + {r.ini_entry}   (your FFB template)"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "restart":
            self.app.state = WizardState()
            while len(self.app.screen_stack) > 1:
                self.app.pop_screen()
        elif bid == "save-preset":
            try:
                p = presets.save_preset(self.app.state)
                self.query_one("#restore-status", Static).update(f"✔  Preset saved to {p}")
            except Exception as exc:
                self.query_one("#restore-status", Static).update(f"✘  {exc}")
        elif bid == "restore":
            try:
                bf = restore_backup(self.app.state.media_folder)
                self.query_one("#restore-status", Static).update(f"✔  Restored originals from {bf}")
            except Exception as exc:
                self.query_one("#restore-status", Static).update(f"✘  {exc}")
        elif bid == "quit":
            self.app.exit()


# ════════════════════════════════════════════════════════════════════════════════════
class WizardApp(App):
    TITLE = "Horizon Wheel TUI"
    CSS = CSS
    BINDINGS = [Binding("q", "quit", "Quit")]

    state: WizardState = WizardState()
    listener: JoystickListener = JoystickListener()

    def on_mount(self) -> None:
        self.listener.start()
        self.push_screen(WelcomeScreen())

    def on_unmount(self) -> None:
        self.listener.stop()
