"""The 26 logical inputs captured by the wizard.

Verbatim port of `WheelMapWizard.Steps` (WheelMapWizard.cs:47-82). `kind` is the
expected raw input type during live capture: "Axis" for the four analog controls,
"Button" for everything else. Each step is skippable; only captured steps are emitted.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MappingStep:
    key: str           # logical key, e.g. "STEER" (NOT the INPUTCMD_* key)
    label: str         # shown in the wizard
    instructions: str  # capture prompt
    kind: str          # "Axis" | "Button"


STEPS: list[MappingStep] = [
    # --- Driving ---
    MappingStep("STEER",      "Steering",        "Turn the wheel fully to one side.",                         "Axis"),
    MappingStep("GAS",        "Gas / Throttle",  "Press the throttle pedal all the way down.",                "Axis"),
    MappingStep("BRAKE",      "Brake",           "Press the brake pedal all the way down.",                   "Axis"),
    MappingStep("CLUTCH",     "Clutch",          "Press the clutch pedal all the way down. Skip if none.",    "Axis"),
    MappingStep("SHIFT_UP",   "Shift Up",        "Pull the right (upshift) paddle.",                          "Button"),
    MappingStep("SHIFT_DOWN", "Shift Down",      "Pull the left (downshift) paddle.",                         "Button"),
    MappingStep("HANDBRAKE",  "Handbrake",       "Pull the handbrake lever or press the button.",             "Button"),
    MappingStep("HORN",       "Horn",            "Press your horn button.",                                   "Button"),

    # --- Menu / UI ---
    MappingStep("CONFIRM",    "Confirm / A",     "Press the button used to confirm/select in menus (A equivalent).", "Button"),
    MappingStep("CANCEL",     "Cancel / B",      "Press the button used to cancel/go-back in menus (B equivalent).", "Button"),
    MappingStep("PAUSE",      "Pause / Menu",    "Press the pause or menu button.",                           "Button"),
    MappingStep("BACK",       "Back",            "Press the back/options button (if separate from Cancel).",  "Button"),
    MappingStep("BTN_X",      "X Button",        "Press the face button mapped to X (if your wheel has one).", "Button"),
    MappingStep("BTN_Y",      "Y Button",        "Press the face button mapped to Y (if your wheel has one).", "Button"),

    # --- Navigation ---
    MappingStep("NAV_UP",     "Navigate Up",     "Press D-Pad Up or your up navigation control.",             "Button"),
    MappingStep("NAV_DOWN",   "Navigate Down",   "Press D-Pad Down or your down navigation control.",         "Button"),
    MappingStep("NAV_LEFT",   "Navigate Left",   "Press D-Pad Left or your left navigation control.",         "Button"),
    MappingStep("NAV_RIGHT",  "Navigate Right",  "Press D-Pad Right or your right navigation control.",       "Button"),

    # --- Actions ---
    MappingStep("REWIND",     "Rewind",          "Press the rewind button.",                                  "Button"),
    MappingStep("CAMERA",     "Switch Camera",   "Press the camera toggle button.",                           "Button"),
    MappingStep("ANNA",       "Anna / AI Assist", "Press the Anna/assistant button.",                         "Button"),
    MappingStep("RADIO",      "Radio Next",      "Press the next-radio-station button.",                       "Button"),
    MappingStep("PHOTO",      "Photo Mode",      "Press the photo mode toggle button.",                       "Button"),
    MappingStep("QUICKCHAT",  "Quickchat",       "Press the quickchat button.",                               "Button"),
    MappingStep("TELEMETRY",  "Telemetry Toggle", "Press the telemetry HUD toggle button.",                   "Button"),
    MappingStep("MAP",        "Open Map / View", "Press the button you want to use to open the world map.",   "Button"),

    # --- H-pattern shifter gears (optional; skip all if you don't have an H-shifter) ---
    # These are only emitted when the "wider mappings" option is enabled at generate time.
    MappingStep("GEAR_R",     "Reverse Gear",    "Engage reverse on your H-pattern shifter. Skip if none.",   "Button"),
    MappingStep("GEAR_1",     "1st Gear",        "Engage 1st gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_2",     "2nd Gear",        "Engage 2nd gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_3",     "3rd Gear",        "Engage 3rd gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_4",     "4th Gear",        "Engage 4th gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_5",     "5th Gear",        "Engage 5th gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_6",     "6th Gear",        "Engage 6th gear on your H-pattern shifter. Skip if none.",  "Button"),
    MappingStep("GEAR_7",     "7th Gear",        "Engage 7th gear on your H-pattern shifter. Skip if none.",  "Button"),
]

# H-pattern shifter gear logical keys (the optional trailing block of STEPS).
GEAR_KEYS = ("GEAR_R", "GEAR_1", "GEAR_2", "GEAR_3", "GEAR_4", "GEAR_5", "GEAR_6", "GEAR_7")


# Where each logical control sits on Forza Horizon 6's DEFAULT Xbox-controller layout, shown as
# a dim hint during capture so the user knows what they're binding. A missing key renders no hint.
#
# These are FH6 "Default Layout 1" (the game ships several selectable layouts; Game8/TechWiser
# document Layout 1). Verified Aug 2026 against Game8, TechWiser and SCUF control guides:
#   - Shift Up = B; Shift Down ships UNBOUND (manual drivers must bind it) — confirmed by all three.
#   - Quickchat = Forza LINK = D-pad ← (context-shared with Telemetry Previous).
#   - Telemetry toggle has no default button.
#   - Map vs Pause: guides disagree on View (⧉) vs Menu (☰); we follow docs/fh6-xbox-controls.svg
#     (View = map, Menu = pause). The adjacent icons let the user find either regardless.
XBOX_HINTS: dict[str, str] = {
    # Driving
    "STEER":      "Left stick",
    "GAS":        "RT · right trigger",
    "BRAKE":      "LT · left trigger",
    "CLUTCH":     "LB · left bumper",
    "SHIFT_UP":   "B",
    "SHIFT_DOWN": "unbound by default",
    "HANDBRAKE":  "A",
    "HORN":       "Right stick (click)",
    # Menu / UI
    "CONFIRM":    "A",
    "CANCEL":     "B",
    "PAUSE":      "Menu (☰)",
    "BACK":       "B",
    "BTN_X":      "X",
    "BTN_Y":      "Y",
    # Navigation
    "NAV_UP":     "D-pad ↑",
    "NAV_DOWN":   "D-pad ↓",
    "NAV_LEFT":   "D-pad ←",
    "NAV_RIGHT":  "D-pad →",
    "MAP":        "View (⧉) · open map",
    # Actions
    "REWIND":     "Y",
    "CAMERA":     "RB · right bumper",
    "ANNA":       "D-pad ↓ · ANNA",
    "RADIO":      "D-pad → · radio next",
    "PHOTO":      "D-pad ↑ · photo mode",
    "QUICKCHAT":  "D-pad ← · Forza LINK",
    "TELEMETRY":  "no default binding",
}


# H-pattern shifter GATE, as a tiny ASCII diagram drawn during gear capture with the current gear
# highlighted in (parens). Two layouts users pick between, generalised from the 5-speed reference
# diagrams (docs/Manual_Layout.svg.webp standard, docs/Manual_Dogleg.svg.webp dogleg) to the full
# 7-speed + R gate. Top/bottom rows across four columns:
#   Standard: 1 3 5 7 / 2 4 6 R      Dogleg: R 2 4 6 / 1 3 5 7
_GATE_STD = (["1", "3", "5", "7"], ["2", "4", "6", "R"])   # (top row, bottom row)
_GATE_DOG = (["R", "2", "4", "6"], ["1", "3", "5", "7"])


def xbox_hint(key: str) -> str:
    """Default FH6 Xbox-layout location for a logical key (see XBOX_HINTS), '' if none."""
    return XBOX_HINTS.get(key, "")


def _gate_diagram(active: str) -> str:
    """Small side-by-side ASCII gate for both layouts, `active` gear label wrapped in (parens).
    Fixed 3-char cells keep the columns aligned whether or not a cell is highlighted."""
    def cell(lbl: str) -> str:
        return f"({lbl})" if lbl == active else f" {lbl} "
    def row(cells: list[str]) -> str:
        return "".join(cell(c) for c in cells)
    return (
        "🔧 H-shifter gate — ( ) = this gear\n"
        "   standard        dogleg\n"
        f"  {row(_GATE_STD[0])}    {row(_GATE_DOG[0])}\n"
        f"  {row(_GATE_STD[1])}    {row(_GATE_DOG[1])}"
    )


def control_hint(key: str) -> str:
    """Full capture-prompt hint for a logical key ('' when there's none).

    Gears render an ASCII shifter gate (standard + dogleg) with the current gear highlighted;
    everything else is a one-line default FH6 Xbox-button hint.
    """
    if key in GEAR_KEYS:
        return _gate_diagram(key.split("_", 1)[1])  # "GEAR_R"->"R", "GEAR_3"->"3"
    h = XBOX_HINTS.get(key, "")
    return f"🎮 Xbox default: {h}" if h else ""


def category(key: str) -> str:
    """Group label for a logical key (WheelMapWizard.cs:302-310)."""
    if key in ("STEER", "GAS", "BRAKE", "CLUTCH", "SHIFT_UP", "SHIFT_DOWN", "HANDBRAKE", "HORN"):
        return "Driving"
    if key in ("CONFIRM", "CANCEL", "PAUSE", "BACK", "BTN_X", "BTN_Y"):
        return "Menu / UI"
    if key in ("NAV_UP", "NAV_DOWN", "NAV_LEFT", "NAV_RIGHT", "MAP"):
        return "Navigation"
    if key in GEAR_KEYS:
        return "Gears (H-pattern shifter)"
    return "Actions"
