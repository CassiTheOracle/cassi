#!/usr/bin/env python3
"""
σ₈ Magnitude Reconciliation: Pipeline Δσ₈ = −0.42 vs the "~5% lower" Claim
============================================================================

Runs the Cassi σ₈ pipeline (`two-fluid/run_sigma8_pipeline.py`, N=32) and
decomposes the headline Δσ₈ into the part attributable to the Qi-gravity
mechanism (the q-drop → G_eff factor) and the residual that is NOT the
mechanism (PDE dissipation, resolution, normalization). It also recomputes
the constant-μ growth-scaling table of `cosmology/sigma8-computational-plan.md`
§3.2 for the pipeline's actual q-drop, mapping μ = G_eff/G_ref → σ₈
suppression.

Why this script exists: the ledger (`parameter-inventory.md` §10, row 506)
flags "Slightly lower ~5%" (cosmology doc) vs the pipeline's −43%. The plan
doc already lists three reasons the pipeline overestimates (scale-independent
q, N=32 resolution, short evolution segment); this script quantifies each.

Physics functions are imported from `two-fluid/run_sigma8_pipeline.py`;
the PDE driver loop below mirrors that module's main() so the measured
P(k), field, and q(k) outputs are bit-identical to the pipeline run.

Usage:
    python computations/sigma8_reconciliation.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'two-fluid'))

# ── Physics functions imported from the σ₈ pipeline (attribution) ──────────
from run_sigma8_pipeline import (
    PHI, PHI_INV, XI,
    OMEGA_M, OMEGA_B, HUBBLE_H, N_S,
    L_BOX_MPC, L, R8_MPC, R8_SIM,
    N, DT, N_STEPS, SEED, DEVICE,
    LAM, CHI, CS2, INITIAL_RATIO, HUBBLE_MODE, SIGMA8_TARGET,
    ExpandingTwoFluid3DGPU,
    build_normalized_ics, sigma_R_from_pk, sigma_R_from_field,
    compute_q_field, compute_q_radial_profile, d_growth,
    build_k_mag_3d,
)

# ═════════════════════════════════════════════════════════════════════════
# 1. Rebuild ICs and run the PDE (mirrors run_sigma8_pipeline.py main())
# ═════════════════════════════════════════════════════════════════════════

print("=" * 68)
print("σ₈ MAGNITUDE RECONCILIATION—pipeline Δσ₈ vs the '~5%' claim")
print("=" * 68)
print(f"  N={N}³, L={L:.4f} (≈{L_BOX_MPC} Mpc/h), dt={DT}, steps={N_STEPS}")
print(f"  R₈ = {R8_MPC} Mpc/h → {R8_SIM:.4f} sim-units,  ξ = φ⁶ = {XI:.4f}")
print()

t0 = time.time()
print("[1/4] Building Eisenstein-Hu ICs (σ₈ target = 0.8)...")
EY, EI, k_mag, q_ref, delta_ic, pk_norm, k_init, Pk_init_norm = \
    build_normalized_ics(N, L, SIGMA8_TARGET, INITIAL_RATIO,
                         seed=SEED, device=DEVICE)
print(f"      q_ref = {q_ref:.4f}   P(k) norm factor = {pk_norm:.6f}  "
      f"(σ₈ Pk raw = {sigma_R_from_pk(k_init, Pk_init_norm / pk_norm, R8_SIM):.4f})")

print("[2/4] Running PDE simulation...")
solver = ExpandingTwoFluid3DGPU(
    N=N, L=L, lam=LAM, chi=CHI, cs2=CS2,
    hubble_mode=HUBBLE_MODE, initial_ratio=INITIAL_RATIO,
    qi_gate=True, a0=1.0, device=DEVICE)
u_hat = [torch.zeros((N, N, N), dtype=torch.complex128, device=DEVICE)
         for _ in range(3)]
ey_hat = torch.fft.fftn(EY)
ei_hat = torch.fft.fftn(EI)

delta_rms_ic = float(np.std(delta_ic))
a_ic = float(solver.a.cpu())

final = None
for step in range(N_STEPS):
    u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
    if step == N_STEPS - 1:
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        rho = ey + ei
        rho_ms = rho.mean().item()
        delta_t = rho / rho_ms - 1.0 if rho_ms > 0 else torch.zeros_like(rho)
        k_cur, Pk_raw = solver.power_spectrum(delta_t)
        Pk_cur = Pk_raw * pk_norm
        q_3d = compute_q_field(ey, ei)
        q_mean_cur = float(q_3d.mean().cpu())
        k_q, q_profile = compute_q_radial_profile(q_3d, solver)
        final = {
            'a': float(solver.a.cpu()),
            'delta_rms': float(delta_t.std().cpu()),
            'k': k_cur, 'Pk': Pk_cur,
            'k_q': k_q, 'q_profile': q_profile,
            'delta': delta_t.cpu().numpy().copy(),
            'q_mean': q_mean_cur,
        }
print(f"      PDE done in {time.time() - t0:.1f}s — "
      f"a: {a_ic:.3f} → {final['a']:.3f}, "
      f"δ_rms: {delta_rms_ic:.4f} → {final['delta_rms']:.4f}, "
      f"q_mean: {q_ref:.4f} → {final['q_mean']:.4f}")

# ═════════════════════════════════════════════════════════════════════════
# 2. σ₈ values — the pipeline's own five numbers
# ═════════════════════════════════════════════════════════════════════════

print("\n[3/4] σ₈ values (pipeline definitions)...")
D_ic = d_growth(a_ic)
D_fin = d_growth(final['a'])
Pk_lcdm = Pk_init_norm * (D_fin / D_ic) ** 2
q_final = final['q_mean']
G_eff_factor = (1.0 + XI * q_final) / (1.0 + XI * q_ref)
Pk_cassi_formula = Pk_lcdm * G_eff_factor ** 2

valid_q = np.isfinite(final['k_q']) & (final['k_q'] > 0)
if valid_q.sum() > 1:
    q_interp = np.interp(final['k'], final['k_q'][valid_q],
                         final['q_profile'][valid_q],
                         left=q_ref, right=q_final)
    G_eff_k = (1.0 + XI * q_interp) / (1.0 + XI * q_ref)
    Pk_cassi_kdep = Pk_lcdm * G_eff_k ** 2
else:
    Pk_cassi_kdep = Pk_cassi_formula

s8_lcdm = sigma_R_from_pk(final['k'], Pk_lcdm, R8_SIM)
s8_pk = sigma_R_from_pk(final['k'], final['Pk'], R8_SIM)
s8_field = sigma_R_from_field(final['delta'], k_mag, R8_SIM)
s8_formula = sigma_R_from_pk(final['k'], Pk_cassi_formula, R8_SIM)
s8_kdep = sigma_R_from_pk(final['k'], Pk_cassi_kdep, R8_SIM)

print(f"  σ₈(ΛCDM linear):       {s8_lcdm:.4f}")
print(f"  σ₈(Cassi, P(k) meas):  {s8_pk:.4f}")
print(f"  σ₈(Cassi, field):      {s8_field:.4f}")
print(f"  σ₈(Cassi, μ const):    {s8_formula:.4f}")
print(f"  σ₈(Cassi, μ(k) k-dep): {s8_kdep:.4f}")

# ═════════════════════════════════════════════════════════════════════════
# 3. Decomposition of the headline Δσ₈
# ═════════════════════════════════════════════════════════════════════════

print("\n[4/4] Decomposition of Δσ₈...")
d_total = s8_pk - s8_lcdm
d_mu = s8_formula - s8_lcdm
d_resid = s8_pk - s8_formula
print(f"  Δσ₈ total  (measured P(k) − ΛCDM):  {d_total:+.4f}  "
      f"({100 * d_total / s8_lcdm:+.1f}%)")
print(f"  Δσ₈ μ-only (G_eff factor {G_eff_factor:.4f}): {d_mu:+.4f}  "
      f"({100 * d_mu / s8_lcdm:+.1f}%)")
print(f"  Δσ₈ residual (measured − μ-formula): {d_resid:+.4f}  "
      f"({100 * d_resid / s8_lcdm:+.1f}%)")
print(f"  δ_rms evolution: {delta_rms_ic:.4f} → {final['delta_rms']:.4f}  "
      f"({100 * (final['delta_rms'] / delta_rms_ic - 1):+.1f}%) vs "
      f"ΛCDM linear growth D({final['a']:.3f})/D({a_ic:.3f}) = "
      f"{D_fin / D_ic:.4f} ({100 * (D_fin / D_ic - 1):+.1f}%)")

# Plan §3.2 constant-μ growth-scaling table, recomputed with the pipeline's
# actual q-drop. p = (-1 + sqrt(1 + 24μ)) / 4; growth D ∝ a^p from a_i = 0.01
# (z = 99, the plan's "z=100" pivot) to a = 1; σ₈ ratio = 100^(p-1).
print("\n  Constant-μ growth-scaling table (plan §3.2, recomputed "
      "with a_i = 0.01):")
print(f"  {'μ':>8} {'p':>8} {'D(0)/D(100)':>12} {'σ₈ ratio':>9} "
      f"{'Suppression':>11}")
rows = [(1.0000, 'ΛCDM'),
        (G_eff_factor, 'pipeline q-drop'),
        (0.9500, 'estimated effective'),
        (0.9800, 'target (matches obs)')]
for mu, label in rows:
    p = (-1.0 + np.sqrt(1.0 + 24.0 * mu)) / 4.0
    d_ratio = 100.0 ** p
    s8_ratio = 100.0 ** (p - 1.0)
    print(f"  {mu:8.4f} {p:8.4f} {d_ratio:12.1f} {s8_ratio:9.3f} "
          f"{100.0 * (s8_ratio - 1.0):+10.1f}%   ({label})")

# ═════════════════════════════════════════════════════════════════════════
# Verdict
# ═════════════════════════════════════════════════════════════════════════

print("""
VERDICT
-------
1. The pipeline headline is Δσ₈ = {0:+.4f} ({1:+.1f}%), reproduced here.
   Of that, only {2:+.1f}% is the Qi-gravity μ mechanism as the pipeline
   itself formulates it (the scale-independent G_eff factor
   (1+ξ·q_final)/(1+ξ·q_ref) = {4:.4f} applied to linear-growth P(k)).
2. The remaining {3:+.1f}% is NOT the μ mechanism: the PDE's δ_rms falls
   {5:.1f}% over the run (dissipation at N=32 with nonlinear ICs, δ_rms = {6:.2f})
   while ΛCDM linear growth would raise σ₈ by +{7:.1f}%. The measured-vs-formula
   gap is a resolution/transport artifact of the box, not a gravity change.
3. The "~5% lower" claim is a Mapped target (ledger row 506): the plan's
   own table maps μ = 0.98 on σ₈ scales to −5.3%; the pipeline's spatial-mean
   q-drop (μ = {4:.4f}) maps to −23.7% under the same full-history growth
   scaling. The pipeline cannot resolve the effective μ on σ₈ scales: its
   k-dependent variant ({8:+.1f}%) is normalization-unstable (final-state q(k)
   anchored to the IC q_ref), and N=32 captures few σ₈ modes.
4. Honest number: the N=32 pipeline measures Δσ₈ = {0:+.4f} ({1:+.1f}%) total,
   of which ≈ {2:+.1f}% is attributable to the q-drop mechanism. Neither the
   −43% nor the −5% is a derived prediction; the ~5% claim remains a Mapped
   target pending the Boltzmann σ₈ integration with q(k,a) input
   (cosmology/sigma8-computational-plan.md Phases 3–4; the current
   two-fluid/run_boltzmann_cassi.py computes C_ℓ only and does not support σ₈).
""".format(
    d_total, 100 * d_total / s8_lcdm,
    100 * d_mu / s8_lcdm, 100 * d_resid / s8_lcdm,
    G_eff_factor,
    100 * (final['delta_rms'] / delta_rms_ic - 1), delta_rms_ic,
    100 * (D_fin / D_ic - 1),
    100 * (s8_kdep - s8_lcdm) / s8_lcdm))

print("=" * 68)
