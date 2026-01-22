#!/usr/bin/env python3
"""
top_hat_wave_animation.py
=========================
Creates an animation that shows a single‑period triangle wave
(“top‑hat”) whose amplitude (scale factor) grows from 0 to 10.
The scale=1 wave stays visible for the whole animation.

Dependencies:
    - numpy
    - matplotlib
    - pillow (for saving GIFs)

Install them with:
    pip install numpy matplotlib pillow
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ------------------------------------------------------------------
# 1.  Geometry of a single‑period triangle wave
# ------------------------------------------------------------------
def triangle_wave(t: np.ndarray) -> np.ndarray:
    """
    Return the *unit* triangle wave over one period (t ∈ [0, 1]).
    The wave goes from 0 → 1 → 0, so its maximum is 1 at t = 0.5.
    """
    return 1 - np.abs(2 * t - 1)

# Discretise the period (200 points is plenty)
t = np.linspace(0, 1, 200)

# ------------------------------------------------------------------
# 2.  Prepare the figure
# ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.set_xlim(0, 1)
ax.set_ylim(-0.5, 11.5)
ax.set_xlabel("t (period)")
ax.set_ylabel("Amplitude")
ax.set_title("Scale = 0")
ax.grid(True, which="both", ls=":", lw=0.5)

# Static reference line – scale = 1 (red)
static_line, = ax.plot(t, triangle_wave(t),
                       color="red", lw=2, label="scale = 1")
ax.legend(loc="upper left")

# Variable that will hold the currently displayed dynamic line
dynamic_line = None

# ------------------------------------------------------------------
# 3.  Animation function
# ------------------------------------------------------------------
def update(scale: int):
    """
    Update the frame for a given integer scale (0 … 10).
    The dynamic line is redrawn each time, while the static line
    (scale = 1) stays on the plot.
    """
    global dynamic_line

    # Remove the previous dynamic line (if any)
    if dynamic_line is not None:
        dynamic_line.remove()

    # Compute the new amplitude and plot it
    y = scale * triangle_wave(t)
    dynamic_line, = ax.plot(t, y,
                            color="blue", lw=1, alpha=0.7,
                            label=f"scale = {scale}")

    # Update the title to reflect the current scale
    ax.set_title(f"Scale = {scale}")

    return dynamic_line,

# ------------------------------------------------------------------
# 4.  Build the animation object
# ------------------------------------------------------------------
ani = FuncAnimation(fig,
                    update,
                    frames=range(0, 11),   # 0 … 10 inclusive
                    interval=200,          # 200 ms per frame (≈5 fps)
                    blit=True,
                    repeat=False)

# ------------------------------------------------------------------
# 5.  Show or save
# ------------------------------------------------------------------
# Show the animation in an interactive window
# plt.show()

# OR: save as a GIF (takes a few seconds)
ani.save("top_hat_wave.gif", writer="pillow", fps=5)
print("GIF saved as top_hat_wave.gif")
