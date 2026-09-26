#!/usr/bin/env python3
"""Visualize the microcascade coordinate and its current physical boundary.

Run: python visual-explainers/coherence_transmission.py
Out: visual-explainers/coherence_transmission.png
"""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PHI = (1 + np.sqrt(5)) / 2
DELTA = 3

BG = "#060612"
PANEL = "#0d0d1d"
TEXT = "#e0e0f0"
SUB = "#a0a0c0"
GOLD = "#daa520"
YIN = "#7c5cff"
GREEN = "#2ecc71"
RED = "#ff6b6b"
GRID = "#303050"

plt.rcParams.update(
    {
        "figure.facecolor": BG,
        "axes.facecolor": PANEL,
        "savefig.facecolor": BG,
        "text.color": TEXT,
        "axes.labelcolor": TEXT,
        "axes.edgecolor": GRID,
        "xtick.color": SUB,
        "ytick.color": SUB,
        "font.family": "DejaVu Sans",
        "mathtext.default": "regular",
    }
)

fig, axes = plt.subplots(2, 2, figsize=(15, 9))
fig.subplots_adjust(left=0.07, right=0.97, bottom=0.08, top=0.88, hspace=0.36, wspace=0.24)

# A. The exact statement is a geometric coordinate continuation.
ax = axes[0, 0]
n_coord = np.arange(-20, 21)
log_ratio = n_coord * np.log10(PHI)
ax.plot(n_coord, log_ratio, color=GOLD, lw=2.4)
ax.axvline(0, color=RED, ls="--", lw=1.2)
ax.axhline(0, color=GRID, lw=0.8)
ax.fill_between(n_coord, log_ratio, 0, where=n_coord < 0, color=YIN, alpha=0.12)
ax.set_xlabel("integer scale label $n$")
ax.set_ylabel(r"$\log_{10}(\ell_n/\ell_{\rm Pl})$")
ax.set_title("A. What extends exactly?", color=GOLD, fontweight="bold")
ax.text(-18, -2.9, "formal microcascade labels", color=YIN, fontsize=9)
ax.text(1, 0.2, "Planck anchor", color=RED, fontsize=9)
ax.grid(alpha=0.18)

# B. The registered positive-step q profile has a finite physical domain.
ax = axes[0, 1]
n_q = np.arange(-7, 21)
q_formal = 1 - PHI ** (-n_q.astype(float) - DELTA)
valid_declared = n_q >= 0
bounded_extension = (n_q >= -DELTA) & (n_q < 0)
invalid = n_q < -DELTA
ax.axhspan(0, 1, color=GREEN, alpha=0.07)
ax.plot(n_q[valid_declared], q_formal[valid_declared], color=GOLD, lw=2.4, label=r"declared $n\geq0$ profile")
ax.plot(n_q[bounded_extension], q_formal[bounded_extension], color=YIN, lw=2, ls="--", label="formal, unselected extension")
ax.plot(n_q[invalid], q_formal[invalid], color=RED, lw=2, ls=":", label=r"outside $0\leq q\leq1$")
ax.scatter([0, -DELTA], [1 - PHI ** -3, 0], color=[GOLD, YIN], zorder=4)
ax.axvline(-DELTA, color=YIN, lw=1, ls="--")
ax.axhline(0, color=GRID, lw=0.8)
ax.set_xlim(-7, 20)
ax.set_ylim(-7.5, 1.08)
ax.set_xlabel("scale label $n$")
ax.set_ylabel("coherence $q_n$")
ax.set_title("B. Where does the $q_n$ profile stop?", color=GOLD, fontweight="bold")
ax.legend(loc="lower right", fontsize=8, framealpha=0.85, facecolor=PANEL, edgecolor=GRID)
ax.grid(alpha=0.18)

# C. Keep the canonical q semantics fixed.
ax = axes[1, 0]
ax.axis("off")
ax.set_title("C. What does $1-q$ mean?", color=GOLD, fontweight="bold", pad=12)
semantic_lines = [
    (r"$q\to1$", "high coherence; gate closed", GREEN),
    (r"$q\to0$", "low coherence; gate open", RED),
    (r"$1-q$", "openness or coherence deficit", YIN),
    (r"$\sum_n(1-q_n)$", "dimensionless without an energy measure", TEXT),
]
for row, (symbol, meaning, color) in enumerate(semantic_lines):
    y = 0.83 - row * 0.19
    ax.text(0.06, y, symbol, transform=ax.transAxes, color=color, fontsize=16, fontweight="bold")
    ax.text(0.34, y, meaning, transform=ax.transAxes, color=TEXT, fontsize=12)
ax.text(
    0.06,
    0.08,
    "Equal energy per negative step is an added assumption.\nThe coordinate sequence supplies no reservoir or passive power source.",
    transform=ax.transAxes,
    color=SUB,
    fontsize=10,
)

# D. A physical scale sector needs its own state and conservation law.
ax = axes[1, 1]
ax.axis("off")
ax.set_title("D. What turns scale labels into dynamics?", color=GOLD, fontweight="bold", pad=12)
requirements = [
    r"state: $\Psi(\mathbf{x},\mathfrak{s},t)$",
    r"measure and normalization over $\mathfrak{s}$",
    r"Hamiltonian and boundary conditions",
    r"distinct current: $J_{\mathfrak{s}}$",
]
for row, line in enumerate(requirements):
    ax.text(0.07, 0.83 - row * 0.14, f"{row + 1}.  {line}", transform=ax.transAxes, color=TEXT, fontsize=12)
ax.text(
    0.5,
    0.19,
    r"$\partial_t\rho+\nabla\!\cdot\!\mathbf{j}+\partial_{\mathfrak{s}}J_{\mathfrak{s}}=0$",
    transform=ax.transAxes,
    ha="center",
    color=GREEN,
    fontsize=15,
)
ax.text(
    0.5,
    0.07,
    r"$\mathbf{J}_d$ is a spatial density-plane diagnostic; it is not $J_{\mathfrak{s}}$.",
    transform=ax.transAxes,
    ha="center",
    color=SUB,
    fontsize=9.5,
)

fig.suptitle("MICROCASCADE: COORDINATE, COHERENCE, AND DYNAMICS BOUNDARY", fontsize=17, color=GOLD, fontweight="bold")
fig.text(
    0.5,
    0.925,
    r"Exact: $\ell_n=\ell_{\rm Pl}\varphi^n$ for integer $n$   ·   Hypothesized: physical states, energy, and transport for $n<0$",
    ha="center",
    color=SUB,
    fontsize=10,
)
fig.text(
    0.5,
    0.025,
    "Sources: foundations/microcascade-mirror.md · foundations/interscale-current-soliton.md",
    ha="center",
    color=SUB,
    fontsize=8,
)

OUT = "visual-explainers/coherence_transmission.png"
fig.savefig(OUT, dpi=160, facecolor=BG)
print(f"wrote {OUT}")

# Small executable consistency check for the displayed boundaries.
assert np.isclose((PHI - 1) / (PHI + 1), PHI ** -3)
assert np.isclose(1 - PHI ** -3, 0.7639320225002103)
assert np.isclose(1 - PHI ** (-(-DELTA) - DELTA), 0.0)
assert 1 - PHI ** (-(-DELTA - 1) - DELTA) < 0
print(f"phi={PHI:.12f}")
print(f"q_0={1 - PHI ** -3:.12f}")
print("q_-3=0; formal q_n is negative for n<-3")
print("negative-step energy/current: unselected")
