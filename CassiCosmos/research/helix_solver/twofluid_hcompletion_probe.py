#!/usr/bin/env python3
"""
twofluid_hcompletion_probe.py -- wave 13 (U1): the Hamiltonian phi-completion of the two-fluid
coupling.

Tests whether symmetrizing the engine's asymmetric coupling matrix M_eng = [[1,-phi],[-1,phi]]
into the symmetric rank-1 projector M_ham = [[1,-phi],[-phi,phi^2]] (SAME null mode EY=phi*EI,
anti-phase frequency w0*sqrt(1+phi) -> w0*sqrt(1+phi^2)) (a) preserves the phi-attractor null mode,
and (b) restores energy conservation while shifting the splay frequency by sqrt(1+phi^2)/sqrt(1+phi)
~= 1.176.

Arms (per twofluid_hcompletion_prereg.md):
  A  engine form (two_fluid_shell.TwoFluidLine, aei = c^2 A ei + w0^2 d) -- the calibration anchor
     (reproduces wave-5 g2 anti-phase SHO period within its dispersion band).
  B  completed form (TwoFluidLineH, aei = c^2 A ei + phi*w0^2 d) -- identical spatial operator and
     parameters, only M changed.

Statistics (same spatial setup as wave-5: make_reference(phi^7, 160) + make_ic Gaussian, w0^2=20,
c=1): (i) null-mode stationarity (EY=phi*EI -> d=EY-phi*EI stays 0 in BOTH arms); (ii) anti-phase
SHO frequency from FFT of the d time series in both arms (ratio ~1.176); (iii) energy drift of the
Hamiltonian E over the same window in both arms.

Run from repo root:  python research/helix_solver/twofluid_hcompletion_probe.py
"""

import numpy as np

from phi_grid import PHI
from two_fluid_shell import TwoFluidLine, make_ic, make_reference

OMEGA2 = 20.0
C = 1.0
SPAN = PHI ** 7
K = 160
NSTEPS = 1200
FFT_STEPS = 12000
FREQ_RATIO_PRED = np.sqrt(1 + PHI ** 2) / np.sqrt(1 + PHI)   # ~1.176
FREQ_RATIO_LO, FREQ_RATIO_HI = FREQ_RATIO_PRED * 0.97, FREQ_RATIO_PRED * 1.03


# ─── The completed form (only the EI-row coupling changes: x phi) ────────────
class TwoFluidLineH(TwoFluidLine):
    """Hamiltonian-completed two-fluid line: aei = c^2 A ei + phi*w0^2 (EY - phi EI)."""

    def kick(self, ey, ei, vey, vei):
        dt = self.dt
        diff = ey - PHI * ei
        aey = self.c * self.c * (self.A @ ey) - self.w0_2 * diff
        aei = self.c * self.c * (self.A @ ei) + PHI * self.w0_2 * diff
        return vey + 0.5 * dt * aey, vei + 0.5 * dt * aei

    def step(self, ey, ei, vey, vei):
        dt = self.dt
        if not self._kicked:
            vey, vei = self.kick(ey, ei, vey, vei)
            self._kicked = True
        diff = ey - PHI * ei
        aey = self.c * self.c * (self.A @ ey) - self.w0_2 * diff
        aei = self.c * self.c * (self.A @ ei) + PHI * self.w0_2 * diff
        vey_n = vey + dt * aey
        vei_n = vei + dt * aei
        ey_n = ey + dt * vey_n
        ei_n = ei + dt * vei_n
        ey_n[0] = ey_n[-1] = 0.0
        ei_n[0] = ei_n[-1] = 0.0
        vey_n[0] = vey_n[-1] = 0.0
        vei_n[0] = vei_n[-1] = 0.0
        return ey_n, ei_n, vey_n, vei_n


def tf_energy(ey, ei, vey, vei, A, w0_2):
    """The Hamiltonian E (wave-5 tf_energy): KE + FV-potential + 1/2 w0^2 (EY-phi EI)^2."""
    ke = 0.5 * (np.sum(vey * vey) + np.sum(vei * vei))
    pe = 0.5 * (-(ey @ (A @ ey) + ei @ (A @ ei)))
    cp = 0.5 * w0_2 * np.sum((ey - PHI * ei) ** 2)
    return float(ke + pe + cp)


# ─── Statistics ──────────────────────────────────────────────────────────────
def anti_phase_period(cls, warmup=NSTEPS, extra=2000):
    """Wave-5 g2 reproduction: zero-crossing period of d at the peak cell."""
    g = cls(make_reference(SPAN, K))
    ey, ei = make_ic(g.z)
    vey = vei = np.zeros_like(ey)
    for _ in range(warmup):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
    peak = int(np.argmax(np.abs(ey) + np.abs(ei)))
    series = np.zeros(extra)
    for i in range(extra):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
        series[i] = ey[peak] - PHI * ei[peak]
    zc = np.where(series[1:] * series[:-1] < 0)[0]
    per = np.diff(zc)
    full_per = float(np.mean(per) * 2) if len(per) >= 4 else float("nan")
    pred = (2 * np.pi / np.sqrt(g.w0_2 * (1 + PHI))) / g.dt
    return full_per, pred


def measure_frequency(cls, n_steps=FFT_STEPS, warmup=200):
    """FFT the d time series at the center probe; return the dominant frequency (Hz)."""
    g = cls(make_reference(SPAN, K))
    ey, ei = make_ic(g.z)
    vey = vei = np.zeros_like(ey)
    center = len(ey) // 2
    for _ in range(warmup):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
    series = np.zeros(n_steps)
    for i in range(n_steps):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
        series[i] = ey[center] - PHI * ei[center]
    w = np.hanning(n_steps)
    spec = np.abs(np.fft.rfft(series * w))
    freqs = np.fft.rfftfreq(n_steps, d=g.dt)
    lo = int(np.searchsorted(freqs, 0.3))
    hi = int(np.searchsorted(freqs, 5.0))
    idx = lo + int(np.argmax(spec[lo:hi]))
    f = freqs[idx]
    if 0 < idx < len(spec) - 1:
        a, b, c = spec[idx - 1], spec[idx], spec[idx + 1]
        denom = a - 2.0 * b + c
        if abs(denom) > 1e-15:
            delta = 0.5 * (a - c) / denom
            f = freqs[idx] + delta * (freqs[1] - freqs[0])
    return float(f)


def null_mode_max_d(cls, n_steps=NSTEPS):
    """EY=phi*EI IC -> d = EY - phi*EI must stay 0 (null-mode invariance)."""
    g = cls(make_reference(SPAN, K))
    ey, ei = make_ic(g.z)
    ey = PHI * ei                 # pure null mode (d = 0)
    vey = vei = np.zeros_like(ey)
    max_d = 0.0
    for _ in range(n_steps):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
        max_d = max(max_d, float(np.max(np.abs(ey - PHI * ei))))
    return max_d


def energy_drift(cls, n_steps=NSTEPS):
    g = cls(make_reference(SPAN, K))
    ey, ei = make_ic(g.z)
    ey0, ei0 = ey.copy(), ei.copy()
    vey = vei = np.zeros_like(ey)
    e0 = tf_energy(ey0, ei0, np.zeros_like(ey), np.zeros_like(ei), g.A, g.w0_2)
    for _ in range(n_steps):
        ey, ei, vey, vei = g.step(ey, ei, vey, vei)
    e1 = tf_energy(ey, ei, vey, vei, g.A, g.w0_2)
    return float(abs(e1 - e0) / max(abs(e0), 1e-12))


def energy_drift_windows(cls, windows=(1200, 2400, 4800, 9600)):
    """REPORTED diagnostic: drift of E over increasing windows -- secular (grows) vs
    bounded shadow (saturates). Distinguishes the engine's secular drift from the
    completed form's leapfrog shadow drift."""
    g = cls(make_reference(SPAN, K))
    ey, ei = make_ic(g.z)
    ey0, ei0 = ey.copy(), ei.copy()
    vey = vei = np.zeros_like(ey)
    e0 = tf_energy(ey0, ei0, np.zeros_like(ey), np.zeros_like(ei), g.A, g.w0_2)
    out = []
    last = 0
    for w in windows:
        for _ in range(w - last):
            ey, ei, vey, vei = g.step(ey, ei, vey, vei)
        last = w
        e1 = tf_energy(ey, ei, vey, vei, g.A, g.w0_2)
        out.append((w, float(abs(e1 - e0) / max(abs(e0), 1e-12))))
    return out


# ─── Verdict printing ────────────────────────────────────────────────────────
def main() -> None:
    print("== wave 13 (U1): Hamiltonian phi-completion of the two-fluid coupling ==")
    print(f"  M_eng=[[1,-phi],[-1,phi]] -> M_ham=[[1,-phi],[-phi,phi^2]] (same null mode EY=phi*EI)")
    print(f"  anti-phase freq: w0*sqrt(1+phi)={np.sqrt(OMEGA2*(1+PHI)):.4f} rad/s -> "
          f"w0*sqrt(1+phi^2)={np.sqrt(OMEGA2*(1+PHI**2)):.4f} rad/s")
    print(f"  predicted freq ratio B/A = {FREQ_RATIO_PRED:.4f} (band [{FREQ_RATIO_LO:.4f},{FREQ_RATIO_HI:.4f}])")

    # (i) null-mode stationarity
    da = null_mode_max_d(TwoFluidLine)
    db = null_mode_max_d(TwoFluidLineH)
    print(f"\n  (null-mode) EY=phi*EI -> max|d| over {NSTEPS} steps:  A={da:.2e}  B={db:.2e}")
    null_ok = da < 1e-12 and db < 1e-12

    # arm-A anchor (wave-5 g2)
    per_a, pred = anti_phase_period(TwoFluidLine)
    print(f"\n  (arm-A anchor) anti-phase SHO period = {per_a:.1f} steps vs k=0 prediction {pred:.1f} "
          f"(wave-5 band +-30%)")
    anchor_ok = abs(per_a - pred) < 0.30 * pred

    # (ii) anti-phase frequency (FFT)
    f_a = measure_frequency(TwoFluidLine)
    f_b = measure_frequency(TwoFluidLineH)
    ratio = f_b / f_a
    print(f"\n  (frequency) FFT of d=EY-phi*EI at center probe:")
    print(f"    f_A = {f_a:.4f} Hz   f_B = {f_b:.4f} Hz   ratio = {ratio:.4f} (pred {FREQ_RATIO_PRED:.4f})")
    freq_ok = FREQ_RATIO_LO <= ratio <= FREQ_RATIO_HI

    # (iii) energy drift
    drift_a = energy_drift(TwoFluidLine)
    drift_b = energy_drift(TwoFluidLineH)
    print(f"\n  (energy) Hamiltonian E drift over {NSTEPS} steps:  A={drift_a:.3e}  B={drift_b:.3e}")
    wa = energy_drift_windows(TwoFluidLine)
    wb = energy_drift_windows(TwoFluidLineH)
    print("  (energy-windows, REPORTED) drift vs window (secular grows / shadow saturates):")
    for (wa_w, wa_d), (wb_w, wb_d) in zip(wa, wb):
        print(f"    window {wa_w:>5}:  A={wa_d:.3e}  B={wb_d:.3e}  ratio B/A={wb_d/max(wa_d,1e-12):.3f}")
    energy_ok = drift_b < 0.1 * drift_a

    print()
    print("== frozen verdicts ==")
    print(f"  (i)   null-mode invariant: A={da:.2e} B={db:.2e} -> {'PASS' if null_ok else 'FAIL'}")
    print(f"  (armA anchor) period {per_a:.1f} vs {pred:.1f} -> {'REPRODUCED wave-5' if anchor_ok else 'ANCHOR MISMATCH'}")
    print(f"  (ii)  freq ratio {ratio:.4f} in [{FREQ_RATIO_LO:.4f},{FREQ_RATIO_HI:.4f}] -> "
          f"{'PASS (shifts per prediction)' if freq_ok else 'FAIL'}")
    print(f"  (iii) drift_B < 0.1*drift_A: {drift_b:.3e} < {0.1*drift_a:.3e} -> "
          f"{'PASS (conservation restored)' if energy_ok else 'FAIL'}")

    if not (np.isfinite(f_a) and np.isfinite(f_b) and np.isfinite(drift_a) and np.isfinite(drift_b)):
        verdict = "INCONCLUSIVE (non-finite measurement)"
    elif not anchor_ok:
        verdict = "INCONCLUSIVE (arm-A anchor did not reproduce wave-5)"
    elif null_ok and freq_ok and energy_ok:
        verdict = "SUPPORTS (null mode preserved, freq shifts per prediction, conservation restored)"
    elif not null_ok:
        verdict = "CONTRADICTS (the completion does NOT preserve the null mode)"
    else:
        parts = []
        if not freq_ok:
            parts.append(f"frequency ratio {ratio:.4f} outside [{FREQ_RATIO_LO:.4f},{FREQ_RATIO_HI:.4f}]")
        if not energy_ok:
            parts.append(f"drift_B={drift_b:.3e} not < 0.1*drift_A={0.1*drift_a:.3e}")
        verdict = "CONTRADICTS (" + "; ".join(parts) + ")"
    print(f"  OVERALL: {verdict}")
    print("done")


if __name__ == "__main__":
    main()
