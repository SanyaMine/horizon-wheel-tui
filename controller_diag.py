"""Live controller input monitor — press each control on your wheel to see how it reports.

Run:  python controller_diag.py
Press Ctrl+C (or close the window) to quit.

Watch especially: push the D-PAD. If it prints HAT events, your d-pad is a hat (POV) and
must be captured as a Switch. If it prints BUTTON events, note the indices.
"""
import os, time
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

pygame.init()
pygame.joystick.init()
n = pygame.joystick.get_count()
print(f"Joysticks detected: {n}")
sticks = []
for i in range(n):
    js = pygame.joystick.Joystick(i)
    js.init()
    sticks.append(js)
    print(f"  [{i}] {js.get_name()} — axes={js.get_numaxes()} buttons={js.get_numbuttons()} hats={js.get_numhats()}")

print("\nNow press controls. (axes only printed when moved past 0.5)\n")
last_axis = {}
try:
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.JOYBUTTONDOWN:
                print(f"  BUTTON down  js={ev.joy}  index={ev.button}")
            elif ev.type == pygame.JOYHATMOTION:
                if ev.value != (0, 0):
                    print(f"  HAT move     js={ev.joy}  hat={ev.hat}  value={ev.value}  "
                          f"(d-pad -> this is a Switch)")
            elif ev.type == pygame.JOYAXISMOTION:
                key = (ev.joy, ev.axis)
                if abs(ev.value) > 0.5 and abs(ev.value - last_axis.get(key, 0)) > 0.4:
                    print(f"  AXIS move    js={ev.joy}  axis={ev.axis}  value={ev.value:+.2f}")
                    last_axis[key] = ev.value
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\nDone.")
