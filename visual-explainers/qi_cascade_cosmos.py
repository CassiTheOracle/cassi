#!/usr/bin/env python3
"""
Qi Cascade Cosmos—the megacascade bubble lattice with Qi coherence interiors.

A large image centered on our universe bubble, surrounded by neighbors in
the staggered checkerboard lattice. Each bubble is filled with Qi coherence
textures derived analytically from the golden-ratio standing wave form.
Our universe contains a Fibonacci fractal spiral representing the 292-step
cascade from Planck to Hubble.

Staggered checkerboard: m+n even = bubble, m+n odd = void.
Center + 4 diagonal neighbors = 5 bubbles, 4 void sites.

Run:  python visual-explainers/qi_cascade_cosmos.py
Out:  visual-explainers/qi_cascade_cosmos.png
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patheffects as pe

# ═══════════════════════════════════════════════════════════════════════════
# Framework constants
# ═══════════════════════════════════════════════════════════════════════════
PHI = (1 + np.sqrt(5)) / 2
N_CASCADE = 292  # φ-steps from Planck to Hubble

# ═══════════════════════════════════════════════════════════════════════════
# Color palette—cosmic dark
# ═══════════════════════════════════════════════════════════════════════════
BG = "#030308"

QI_CMAP = LinearSegmentedColormap.from_list("qi", [
    "#010104", "#040e0a", "#082018", "#0e3a2a", "#166048",
    "#20a078", "#30d0a0", "#60ffc0", "#c0ffe0"])
CASCADE_CMAP = LinearSegmentedColormap.from_list("cascade", [
    "#0a0620", "#1a1050", "#3020a0", "#6040d0", "#a060f0",
    "#e080ff", "#ffa0c0", "#ffe060", "#fffbe0"])

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": "#e0e0f0", "font.family": "DejaVu Sans",
    "mathtext.default": "regular",
})

# ═══════════════════════════════════════════════════════════════════════════
# Analytical Qi texture—golden-ratio standing wave with multi-scale detail
# ═══════════════════════════════════════════════════════════════════════════
print("Generating analytical Qi texture...")
N_TEX = 512
x = np.linspace(0, 6, N_TEX, endpoint=False)
y = np.linspace(0, 6, N_TEX, endpoint=False)
XX, YY = np.meshgrid(x, y)

# Base standing waves at φ-scaled wavelengths
ey = (1.0 + 0.35 * np.cos(2*np.pi*XX/PHI)
         + 0.12 * np.cos(2*np.pi*XX/(PHI**2))
         + 0.06 * np.cos(2*np.pi*XX/(PHI**3)))
ei = (1.0 + 0.35 * np.cos(2*np.pi*YY)
         + 0.12 * np.cos(2*np.pi*YY/PHI)
         + 0.06 * np.cos(2*np.pi*YY/(PHI**2)))

# Qi = coherence from interference
qi_raw = np.abs(ey) * np.abs(ei)
# Checkerboard modulation (anti-phase structure)
checker = np.cos(2*np.pi*XX/PHI) * np.cos(2*np.pi*YY)
qi_mod = qi_raw * (0.7 + 0.3 * (checker + 1) / 2)
# Fine golden-ratio filaments
filament = np.cos(2*np.pi*(XX/PHI + YY*PHI))**2
qi_final = qi_mod * (0.85 + 0.15 * filament)
qi_texture = (qi_final - qi_final.min()) / (qi_final.max() - qi_final.min())
print(f"  Qi texture: {qi_texture.shape}")

# ═══════════════════════════════════════════════════════════════════════════
# Bubble geometry—staggered checkerboard
# m+n even = bubble (5 sites), m+n odd = void (4 sites)
# ═══════════════════════════════════════════════════════════════════════════
BUBBLE_R = 0.26
SPACING_X = BUBBLE_R * 2.15
SPACING_Y = BUBBLE_R * 1.95

centers = []
for row in range(-1, 2):
    for col in range(-1, 2):
        cx = col * SPACING_X
        cy = row * SPACING_Y
        if row % 2 != 0:
            cx += SPACING_X * 0.5
        has_bubble = ((row + col) % 2 == 0)
        centers.append((cx, cy, row, col, has_bubble))

# ═══════════════════════════════════════════════════════════════════════════
# Compose the image
# ═══════════════════════════════════════════════════════════════════════════
print("Composing bubble lattice...")
RES = 2048
y_arr = np.linspace(-1, 1, RES)
x_arr = np.linspace(-1, 1, RES)
XX_img, YY_img = np.meshgrid(x_arr, y_arr)

# Dark void background
img_rgb = np.full((RES, RES, 3), 0.008)

# Subtle string lattice glow at every site
for row in range(-2, 3):
    for col in range(-2, 3):
        cx_s = col * SPACING_X
        cy_s = row * SPACING_Y
        if row % 2 != 0:
            cx_s += SPACING_X * 0.5
        dist = np.sqrt((XX_img - cx_s)**2 + (YY_img - cy_s)**2)
        glow = 0.015 * np.exp(-dist**2 / 0.04**2)
        img_rgb[:, :, 0] += glow * 0.3
        img_rgb[:, :, 1] += glow * 0.3
        img_rgb[:, :, 2] += glow * 0.7

# Connect neighboring sites with faint strings
for cx, cy, row, col, _ in centers:
    for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nc, nr = col + dc, row + dr
        if -1 <= nc <= 1 and -1 <= nr <= 1:
            nx = nc * SPACING_X
            ny = nr * SPACING_Y
            if nr % 2 != 0:
                nx += SPACING_X * 0.5
            t = np.linspace(0, 1, 100)
            for ti in t:
                px = cx + (nx - cx) * ti
                py = cy + (ny - cy) * ti
                dist = np.sqrt((XX_img - px)**2 + (YY_img - py)**2)
                line_glow = 0.004 * np.exp(-dist**2 / 0.015**2)
                img_rgb[:, :, 2] += line_glow * 0.5

def tile_texture(cx, cy, R, texture):
    dx = (XX_img - cx) / R
    dy = (YY_img - cy) / R
    tx = ((dx * 1.5 + 100) % 1.0 * (texture.shape[1] - 1)).astype(int)
    ty = ((dy * 1.5 + 100) % 1.0 * (texture.shape[0] - 1)).astype(int)
    return texture[np.clip(ty, 0, texture.shape[0]-1),
                   np.clip(tx, 0, texture.shape[1]-1)]

def bubble_mask(cx, cy, R):
    dx = XX_img - cx
    dy = YY_img - cy
    r = np.sqrt(dx**2 + dy**2)
    waist = 1.0 - 0.30 * np.exp(-dy**2 / (0.25 * R)**2)
    mask = np.clip(1.0 - (r / (R * waist))**3, 0, 1)
    void = np.exp(-dx**2 / (0.6*R)**2) * np.exp(-dy**2 / (0.08*R)**2)
    mask *= (1.0 - 0.5 * void)
    return np.clip(mask * 4, 0, 1)

# Draw bubbles
for cx, cy, row, col, has_bubble in centers:
    if not has_bubble:
        continue
    is_center = (row == 0 and col == 0)
    R = BUBBLE_R * (1.15 if is_center else 1.0)
    mask = bubble_mask(cx, cy, R)
    qi = tile_texture(cx, cy, R, qi_texture)
    if is_center:
        color = QI_CMAP(qi * 0.95)[:, :, :3]
        bright = 1.0
    else:
        color = QI_CMAP(qi * 0.60)[:, :, :3]
        bright = 0.7
    edge = np.clip(mask * 8, 0, 1) - np.clip(mask * 3, 0, 1)
    for c in range(3):
        img_rgb[:, :, c] = img_rgb[:, :, c] * (1 - mask) + color[:, :, c] * mask * bright
    img_rgb[:, :, 0] += edge * 0.04 * mask
    img_rgb[:, :, 1] += edge * 0.22 * mask
    img_rgb[:, :, 2] += edge * 0.16 * mask

# ═══════════════════════════════════════════════════════════════════════════
# Fibonacci cascade spiral inside center bubble
# ═══════════════════════════════════════════════════════════════════════════
print("Drawing Fibonacci cascade spiral...")

fig, ax = plt.subplots(figsize=(20, 20), dpi=120)
ax.set_facecolor(BG)
ax.imshow(np.clip(img_rgb, 0, 1), extent=[-1, 1, -1, 1],
          origin="lower", interpolation="bilinear")

b = np.log(PHI) / (np.pi / 2)
theta_max = 14 * np.pi
n_pts = 8000
theta = np.linspace(0.3, theta_max, n_pts)
r_spiral = 0.003 * np.exp(b * theta)
spiral_scale = BUBBLE_R * 1.05 * 1.15 / r_spiral.max()
r_spiral *= spiral_scale
sx = r_spiral * np.cos(theta)
sy = r_spiral * np.sin(theta)

# Draw spiral segments
seg_len = 6
for i in range(0, n_pts - seg_len, seg_len):
    frac = theta[i] / theta_max
    color = CASCADE_CMAP(frac)
    alpha = 0.35 + 0.55 * (1.0 - frac**0.5)
    lw = 0.4 + 2.0 * (1.0 - frac)
    ax.plot(sx[i:i+seg_len+1], sy[i:i+seg_len+1],
            color=color, alpha=alpha, linewidth=lw, solid_capstyle="round")

# Fibonacci rectangles—more visible
fib_n = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
rect_scale = BUBBLE_R * 0.008
for k, n in enumerate(fib_n):
    frac = k / len(fib_n)
    angle = k * np.pi / 2
    idx = min(int(frac * (n_pts - 1)), n_pts - 1)
    size = n * rect_scale * (1.0 + 0.3 * (1 - frac))
    rect_color = CASCADE_CMAP(frac * 0.8)
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    corners = np.array([[-size, -size], [size, -size], [size, size*PHI],
                        [-size, size*PHI], [-size, -size]])
    rot = corners @ np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    rot[:, 0] += sx[idx]
    rot[:, 1] += sy[idx]
    ax.plot(rot[:, 0], rot[:, 1], color=rect_color, alpha=0.5, linewidth=1.0)

# Cascade scale labels
text_fx = [pe.withStroke(linewidth=3, foreground=BG)]
scales = [
    (0.05, "Planck\n$10^{-35}$ m"),
    (0.18, "Proton\n$10^{-15}$ m"),
    (0.35, "Atom\n$10^{-10}$ m"),
    (0.55, "Cell\n$10^{-5}$ m"),
    (0.72, "Star\n$10^{9}$ m"),
    (0.88, "Galaxy\n$10^{21}$ m"),
    (0.97, "Hubble\n$10^{26}$ m"),
]
for frac, label in scales:
    idx = min(int(frac * (n_pts - 1)), n_pts - 1)
    a_out = np.arctan2(sy[idx], sx[idx])
    lx = sx[idx] + 0.025 * np.cos(a_out)
    ly = sy[idx] + 0.025 * np.sin(a_out)
    ax.text(lx, ly, label, ha="center", va="center", fontsize=6.5,
            color=CASCADE_CMAP(frac), alpha=0.9, path_effects=text_fx)

# φ-step markers
for step in range(0, N_CASCADE + 1, 50):
    frac = step / N_CASCADE
    idx = min(int(frac * (n_pts - 1)), n_pts - 1)
    ax.plot(sx[idx], sy[idx], 'o', color=CASCADE_CMAP(frac),
            markersize=1.5 + 2.0 * (1 - frac), alpha=0.6)
    if step % 100 == 0 and step > 0:
        a_out = np.arctan2(sy[idx], sx[idx])
        lx = sx[idx] + 0.015 * np.cos(a_out + np.pi/2)
        ly = sy[idx] + 0.015 * np.sin(a_out + np.pi/2)
        ax.text(lx, ly, f"n={step}", ha="center", va="center",
                fontsize=4.5, color=CASCADE_CMAP(frac), alpha=0.5,
                path_effects=text_fx)

# ── Labels ──
ax.text(0, 0.93, "MEGACASCADE—Qi Coherence Bubble Lattice",
        ha="center", va="top", fontsize=17, color="#ffe060", fontweight="bold",
        path_effects=text_fx)
ax.text(0, 0.885,
        "Checkerboard lattice: m+n even = bubble (universe), "
        "m+n odd = void  ·  Center: our universe with 292-step "
        "φ-cascade spiral (Planck → Hubble)  ·  Qi coherence (teal) "
        "self-reinforces standing waves",
        ha="center", va="top", fontsize=8, color="#a0a0c0",
        path_effects=text_fx, style="italic")

# Bubble/void labels
bubble_labels = {
    (-1, -1): ("anti-phase\nbubble", "#508070"),
    (-1, 1):  ("anti-phase\nbubble", "#508070"),
    (1, -1):  ("anti-phase\nbubble", "#508070"),
    (1, 1):   ("anti-phase\nbubble", "#508070"),
}
void_labels = {
    (-1, 0):  "void\n(string)",
    (0, -1):  "void\n(string)",
    (0, 1):   "void\n(string)",
    (1, 0):   "void\n(string)",
}

for cx, cy, row, col, has_bubble in centers:
    if row == 0 and col == 0:
        continue
    if has_bubble:
        label, color = bubble_labels.get((row, col), ("bubble", "#508070"))
        ax.text(cx, cy - BUBBLE_R * 1.15, label, ha="center", va="top",
                fontsize=6.5, color=color, alpha=0.7, path_effects=text_fx)
    else:
        label = void_labels.get((row, col), "void")
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=7, color="#303050", alpha=0.5, path_effects=text_fx)
        d = BUBBLE_R * 0.3
        ax.plot([cx-d, cx+d], [cy-d, cy+d], color="#201030", alpha=0.3, lw=0.8)
        ax.plot([cx-d, cx+d], [cy+d, cy-d], color="#201030", alpha=0.3, lw=0.8)

# "OUR UNIVERSE" label below the spiral, not overlapping it
ax.text(0, -BUBBLE_R * 1.25, "OUR UNIVERSE", ha="center", va="top",
        fontsize=8, color="#ffe060", fontweight="bold", alpha=0.6,
        path_effects=text_fx)

ax.text(0, -0.93,
        r"$\partial_t Q_i = \alpha_Q |E_Y||E_I| - \delta_Q Q_i$"
        "   ·   "
        r"$\gamma_{\rm eff} = \gamma_0 (1 - \beta \, Q_i / \bar{Q}_i)$"
        "   ·   "
        r"$c^2(r) = c_0^2 |r-\varphi|/(\alpha + |r-\varphi|)$"
        "   ·   "
        r"$\ell_n = \ell_{\rm Pl} \times \varphi^n$,  $n = 0 \ldots 292$",
        ha="center", va="bottom", fontsize=7.5, color="#506080",
        path_effects=text_fx)

ax.set_xlim(-1, 1)
ax.set_ylim(-1, 1)
ax.set_aspect("equal")
ax.axis("off")

OUT = "visual-explainers/qi_cascade_cosmos.png"
fig.savefig(OUT, dpi=150, facecolor=BG, bbox_inches="tight", pad_inches=0.1)
print(f"wrote {OUT}")
plt.close()
