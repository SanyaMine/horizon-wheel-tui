"""Background joystick listener (pygame, headless) for live input capture.

Polls all connected joysticks. For an "Axis" step it reports the axis with the largest
deflection from its resting baseline; for a "Button" step it reports the first button
rising-edge OR a hat (D-pad) direction. Hats are reported as Switch positions so
hat-style D-pads (e.g. the Moza R3, which has no nav buttons) can bind UI navigation —
an enhancement over upstream, whose capture only saw buttons.

Poll/baseline behaviour follows WheelMapWizard.cs:312-441 (late axis re-baseline after a
grace period; axis threshold 0.15).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from .vidpid import VidPid

# Headless SDL — no window/audio (must be set before pygame imports SDL)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_AXIS_THRESHOLD = 0.15   # deflection from baseline to count (matches C#)
_POLL_HZ        = 50


@dataclass
class InputEvent:
    input_type: str                       # "Axis" | "Button" | "Switch"
    index: int
    value: float = 0.0                    # signed axis value at detection
    delta: float = 0.0                    # signed change from resting baseline at detection
    switch_position: Optional[str] = None  # "Up"|"Down"|"Left"|"Right" for hats
    joystick_name: str = ""
    device_vidpid: str = ""                # capturing device's compact "VVVVPPPP" (from SDL GUID)

    @property
    def invert_axis(self) -> bool:
        # Direction of travel from baseline (C# `bestInvert = delta < 0`), NOT the sign of
        # the instantaneous value — pedals rest at an axis extreme, so the value's sign at
        # the detection sample is the baseline's sign, not the press direction.
        return self.input_type == "Axis" and self.delta < 0

    def human_label(self) -> str:
        if self.input_type == "Axis":
            return f"Axis {self.index} ({'inverted' if self.invert_axis else 'normal'})"
        if self.input_type == "Button":
            return f"Button {self.index}"
        if self.input_type == "Switch":
            return f"D-Pad {self.switch_position}"
        return "?"


class JoystickListener:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop   = threading.Event()
        self._done   = threading.Event()
        self._cancel = threading.Event()
        self._active = False
        self._expected = "Button"            # "Axis" | "Button"
        self._captured: Optional[InputEvent] = None
        self._joysticks: list = []
        self._names: list[str] = []
        self._vidpids: dict[int, str] = {}   # instance_id -> compact "VVVVPPPP" (or "")
        self._baselines: dict[int, list[float]] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────────
    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="joy-listener")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.cancel()
        if self._thread:
            self._thread.join(timeout=3)

    # ── Capture API ───────────────────────────────────────────────────────────────
    def arm(self, expected: str = "Button") -> None:
        self._expected = expected
        self._captured = None
        self._cancel.clear()
        self._done.clear()
        # Re-snapshot axis baselines so any held pedal is treated as neutral.
        self._snapshot_baselines()
        self._active = True

    def cancel(self) -> None:
        self._active = False
        self._cancel.set()
        self._done.set()

    def wait(self, timeout: float = 120.0) -> Optional[InputEvent]:
        self._done.wait(timeout=timeout)
        if self._cancel.is_set() or not self._done.is_set():
            return None
        return self._captured

    @property
    def joystick_names(self) -> list[str]:
        return list(self._names)

    # ── Background thread ─────────────────────────────────────────────────────────
    def _run(self) -> None:
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return

        joysticks = []
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i)
            j.init()
            joysticks.append(j)
        self._joysticks = joysticks
        self._names = [j.get_name() for j in joysticks]
        self._vidpids = {j.get_instance_id(): _guid_vidpid(j) for j in joysticks}
        self._pygame = pygame
        self._snapshot_baselines()

        while not self._stop.is_set():
            pygame.event.pump()
            if self._active:
                self._poll()
            time.sleep(1.0 / _POLL_HZ)

        try:
            pygame.joystick.quit()
            pygame.quit()
        except Exception:
            pass

    def _snapshot_baselines(self) -> None:
        try:
            import pygame
            pygame.event.pump()
        except Exception:
            return
        self._baselines = {
            j.get_instance_id(): [j.get_axis(a) for a in range(j.get_numaxes())]
            for j in self._joysticks
        }

    def _poll(self) -> None:
        if self._expected == "Axis":
            self._poll_axes()
        else:
            self._poll_buttons_and_hats()

    def _poll_axes(self) -> None:
        best_delta = 0.0
        best = None  # (value, index, name, vidpid)
        for j in self._joysticks:
            bl = self._baselines.get(j.get_instance_id(), [])
            for i in range(j.get_numaxes()):
                val = j.get_axis(i)
                base = bl[i] if i < len(bl) else 0.0
                delta = val - base
                if abs(delta) > abs(best_delta):
                    best_delta = delta
                    best = (val, i, j.get_name(), self._vidpids.get(j.get_instance_id(), ""))
        if best is not None and abs(best_delta) > _AXIS_THRESHOLD:
            val, idx, name, vp = best
            self._emit(InputEvent("Axis", idx, value=val, delta=best_delta,
                                  joystick_name=name, device_vidpid=vp))

    def _poll_buttons_and_hats(self) -> None:
        for j in self._joysticks:
            name = j.get_name()
            vp = self._vidpids.get(j.get_instance_id(), "")
            for i in range(j.get_numbuttons()):
                if j.get_button(i):
                    self._emit(InputEvent("Button", i, joystick_name=name, device_vidpid=vp))
                    return
            for i in range(j.get_numhats()):
                hx, hy = j.get_hat(i)
                pos = ("Up" if hy > 0 else "Down" if hy < 0 else
                       "Right" if hx > 0 else "Left" if hx < 0 else None)
                if pos:
                    self._emit(InputEvent("Switch", 0, switch_position=pos,
                                          joystick_name=name, device_vidpid=vp))
                    return

    def _emit(self, event: InputEvent) -> None:
        if self._active and not self._cancel.is_set():
            self._captured = event
            self._active = False
            self._done.set()


def _guid_vidpid(joystick) -> str:
    """Compact 'VVVVPPPP' for a pygame joystick from its SDL GUID, or '' if unavailable.

    get_guid exists on pygame 2.x; wrapped defensively so a driver/edge case that raises (or a
    GUID without a usable VID/PID) degrades to name matching rather than crashing capture."""
    try:
        vp = VidPid.from_sdl_guid(joystick.get_guid())
    except Exception:
        return ""
    return vp.compact if vp else ""
