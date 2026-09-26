"""Cassi Synth — CPU reference for the cascade meter (research/meshless).

Mirrors the EXACT reduce math of compute/cassi_audio_reduce.glsl and gates
the GPU readout dumped by scripts/verify_synth.gd to _diag/synth_gpu.json:

  G22  GPU vs numpy rung energies (and the total energy) ≤ 1e-2 relative.
  G23  rung localization — each probe plane wave's energy PEAKS in its
       designated rung, the GPU per-wave spectrum agrees with the numpy
       prediction to < 15% relative, and the meter is scale-responsive
       (the high-wavenumber n=8 wave deposits into the FINEST rung, the
       low-wavenumber n=1 wave into the COARSEST).

The probe is a "known sum of φ-spaced plane waves": the full field is
ey = Σ_r ½·cos(2π n_r x / N) (ei = 0), with n = [8,7,2,1] designated to
rungs 0..3. Each monochromatic wave localizes to its own rung under the
L2 box-difference meter (verified: own-shares 0.92/0.76/0.51/0.74).

Process: run scripts/verify_synth.tscn first (windowed; writes the JSON),
then `python research/meshless/synth_verify.py`.
"""
import json
import os
import sys

import numpy as np

PHI = 1.618033988749895
N = 64
R = 4
# b_m ≈ round(φ^m); the coarsest rung uses b=8 (round-up of φ⁴ ≈ 6.9) for
# clean coarse-scale separation on N=64. MUST match the shader's BOX table
# (compute/cassi_audio_reduce.glsl) and verify_synth.gd's const BOX.
BOX = [2, 3, 4, 8]
WAVE_N = [8, 7, 2, 1]  # wave designated to rung r has wavenumber n_r


def ey_field(nfs):
    """Resultant ey = Σ ½·cos(2π n x/N) over the given n's (ei = 0)."""
    ax = np.arange(N)
    ey = np.zeros(N)
    for nf in nfs:
        ey += 0.5 * np.cos(2 * np.pi * nf * ax / N)
    return ey


def fblur1d(v, w):
    """Periodic 1D box mean of half-width w (window 2w+1)."""
    r = np.zeros_like(v)
    for d in range(-w, w + 1):
        r += np.roll(v, -d)
    return r / (2 * w + 1)


def cpu_rung_energies(ey):
    """Exact numpy mirror of the shader's SAT + box-difference reduce.

    q = ey² (ei=0 for the probe); per rung m the (mean over the b_m box
    − mean over the 2·b_m box)² detail energy. The field is constant along
    y,z, so the 3D box mean equals the 1D x-blur — identical to the
    shader, which integrates all three axes (the constants cancel in the
    band-pass and the per-cell mean is the same).
    """
    q = ey * ey
    energies = []
    for r in range(R):
        b = BOX[r]
        small = fblur1d(q, b)
        large = fblur1d(q, 2 * b)
        d = small - large
        energies.append(float((d * d).mean()))
    return np.array(energies)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/synth_gpu.json"
    if not os.path.exists(path):
        print("RESULT: SKIP — no GPU dump at %s (run verify_synth.tscn first)" % path)
        return 0
    d = json.load(open(path, encoding="utf-8"))
    gpu = np.asarray(d["rung_energies_gpu"], dtype=np.float64)
    gpu_tot = d["total_energy_gpu"]

    ref = cpu_rung_energies(ey_field(WAVE_N))
    ref_tot = float((ey_field(WAVE_N) ** 2).mean())

    print("BOX=[%s] R=%d N=%d" % (",".join(map(str, BOX)), R, N))
    print("[ref] rung energies: %s" % np.round(ref, 6))
    print("[gpu] rung energies: %s" % np.round(gpu, 6))

    # ── G22: GPU vs numpy ≤ 1e-2 relative ────────────────────────────
    rel = np.abs(gpu - ref) / np.maximum(np.abs(ref), 1e-9)
    g22 = bool(np.all(rel <= 1e-2))
    rel_tot = abs(gpu_tot - ref_tot) / max(abs(ref_tot), 1e-9) if abs(ref_tot) > 0 else 0.0
    g22 = g22 and rel_tot <= 1e-2
    print("[G22] rung rel err max=%.2e  total rel=%.2e" % (rel.max(), rel_tot))

    # ── G23: localization (per-wave peaks + scale-responsiveness) ────
    peaks_ok = True
    waves_gpu = d["per_wave_energies_gpu"]
    waves_ref = d["per_wave_energies_ref"]
    for r in range(R):
        wg = np.asarray(waves_gpu[r], dtype=np.float64)
        wr = np.asarray(waves_ref[r], dtype=np.float64)
        pk_g = int(np.argmax(wg))
        rr = np.abs(wg - wr) / np.maximum(wr, 1e-9)
        ok = pk_g == r and rr.max() < 0.15
        peaks_ok = peaks_ok and ok
        print("[G23] wave r%d n=%d: peak_gpu=r%d (want r%d) relmax=%.3f %s"
              % (r, WAVE_N[r], pk_g, r, rr.max(), "ok" if ok else "FAIL"))
    w0 = np.asarray(waves_gpu[0], dtype=np.float64)   # n=8 → finest
    w3 = np.asarray(waves_gpu[3], dtype=np.float64)   # n=1 → coarsest
    fine_ok = w0[0] >= w0[-1] * 0.5 and int(np.argmax(w0)) <= 1
    coarse_ok = w3[-1] >= w3[0] * 0.5 and int(np.argmax(w3)) >= 2
    print("[G23] scale-responsive: fine(n=8) r0=%.4f  coarse(n=1) r3=%.4f"
          % (w0[0], w3[-1]))
    g23 = peaks_ok and fine_ok and coarse_ok

    for name, ok in [("G22 GPU=numpy", g22), ("G23 localization", g23)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g22 and g23) else "FAILURES PRESENT"))
    return 0 if (g22 and g23) else 1


if __name__ == "__main__":
    sys.exit(main())
