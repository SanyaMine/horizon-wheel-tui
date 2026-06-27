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
