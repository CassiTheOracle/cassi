"""Diagnose which channel of the (KC1) identity breaks on the retained families.

Runs a short trajectory of one family and compares, interval by interval, the
finite difference of each frame quantity against the integral of the rate term the
identity assigns to it.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


budget = load("budget", "computations/navier_stokes_curvature_budget.py")
clock = budget.load_module(budget.CLOCK_SCRIPT)
long_trajectory = budget.load_module(budget.LONG_TRAJECTORY_SCRIPT)
depletion = budget.load_module(budget.DEPLETION_SCRIPT)

torch = __import__("torch")
NU = 0.1
STEPS = 256
HORIZON = 2.0
CASE = sys.argv[1] if len(sys.argv) > 1 else "helix_wide"

box = long_trajectory.TorchGalerkinBox(clock.CUTOFF, clock.GRID_FACTOR * clock.CUTOFF + 1)
case = next(c for c in depletion.CASES if c["name"] == CASE)
state, _ = depletion.initial_state(case, box)
probe = budget.PointProbe(box)
size = int(box.grid_size)
dt = HORIZON / float(STEPS)

omega_grid = box.grid(box.curl(state))
flat = int(torch.argmax(torch.sum(omega_grid * omega_grid, dim=-1)).item())
core_cell = np.unravel_index(flat, tuple(int(v) for v in omega_grid.shape[:3]))
tracer = np.array([2.0 * math.pi * float(i) / size for i in core_cell])

samples = []


def record(time, position):
    frame = budget.local_frame(probe, state, position, NU)
    samples.append((time, frame))


record(0.0, tracer.copy())
first_rhs = box.right_hand_side(state)
for index in range(STEPS):
    second_rhs = box.right_hand_side(state + 0.5 * dt * first_rhs)
    third_rhs = box.right_hand_side(state + 0.5 * dt * second_rhs)
    fourth_rhs = box.right_hand_side(state + dt * third_rhs)
    updated = state + (dt / 6.0) * (first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs)
    carried = tracer.copy()
    stage_1 = probe.velocity(state, tracer)
    stage_2 = probe.velocity(state + 0.5 * dt * first_rhs, tracer + 0.5 * dt * stage_1)
    stage_3 = probe.velocity(state + 0.5 * dt * second_rhs, tracer + 0.5 * dt * stage_2)
    stage_4 = probe.velocity(state + dt * third_rhs, tracer + dt * stage_3)
    tracer = (tracer + (dt / 6.0) * (stage_1 + 2.0 * stage_2 + 2.0 * stage_3 + stage_4)) % (2.0 * math.pi)
    state = updated.masked_fill(~box.shell[..., None], 0.0)
    first_rhs = box.right_hand_side(state)
    if (index + 1) % 4 == 0:
        record((index + 1) * dt, carried)

times = np.array([t for t, _ in samples])
print(f"{CASE}: {len(samples)} samples, dt={dt:.6f}, |omega| {samples[0][1]['magnitude']:.5f} -> {samples[-1][1]['magnitude']:.5f}")
print(f"  margins: kappa {samples[0][1]['kappa']:.5f}->{samples[-1][1]['kappa']:.5f}  "
      f"width {samples[0][1]['width']:.5f}->{samples[-1][1]['width']:.5f}  "
      f"margin {samples[0][1]['margin']:.5f}->{samples[-1][1]['margin']:.5f}")


def series(key):
    return np.array([frame[key] for _, frame in samples])


def dlog(key):
    values = series(key)
    return np.diff(np.log(np.abs(values))) * np.sign(values[1:])


def integrand(name):
    ell, transverse, binormal = series("stretch"), series("transverse"), series("binormal_strain")
    magnitude, production = series("magnitude"), series("production")
    if name == "kappa":
        return series("bend_rate")
    if name == "width":
        return transverse - ell
    if name == "magnitude":
        return ell + NU * production / magnitude**2
    if name == "margin":
        return series("assembled_rate")
    raise KeyError(name)


def integral(name):
    values = integrand(name)
    return 0.5 * (values[1:] + values[:-1]) * np.diff(times)


print(f"  {'channel':<10}{'dlog(finite diff)':>20}{'integral of rate':>20}{'gap':>12}{'worst interval':>16}")
for key, name in (("kappa", "kappa"), ("width", "width"), ("magnitude", "magnitude"), ("margin", "margin")):
    total = dlog(key).sum()
    pred = integral(name)
    print(f"  {key:<10}{total:>20.6f}{pred.sum():>20.6f}{total - pred.sum():>12.2e}"
          f"{np.max(np.abs(dlog(key) - pred)):>16.2e}")

print("  identity check: dlog margin - (dlog kappa + dlog width) =",
      f"{dlog('margin').sum() - (dlog('kappa').sum() + dlog('width').sum()):.2e}")
