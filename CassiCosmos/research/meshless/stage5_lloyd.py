"""Stage 5: density-weighted Lloyd on the steered mesh (MESHLESS_PLAN.md §10
— the "density-weighted Lloyd on the adaptive+steered mesh" remaining item).

The GPU modes 3/4 (compute/cassi_voronoi_cells.glsl) implement:

  Mode 3  — MASS-weighted centroid: per grid cell w = rho_mass + FLOOR
            (FLOOR = ML_LLOYD_FLOOR = 1e-3); cen[lab] = Σ w·center / Σ w.
            At rho_mass == 0 the floor cancels → the exact geometric
            centroid (the flat-noise / rho=0 regression must hold).
  Mode 4  — Qi-gated steer: κ_eff = κ·(1−q)^p with q = ρ²/(ρ²+φ⁻²+ε²),
            ρ = EY+EI, ε = EY−φ·EI (v2_moving3d.q_coh, p = ML_LLOYD_P = 4).
            The blended target (momentum ride + κ_eff·mass centroid) has its
            TOTAL displacement guarded to ML_MAX_DRIFT before the wrap.

This prototype validates the three gates in numpy BEFORE the GPU run:
  G19  a deposited mass blob makes sites concentrate — the mean site→blob
       distance after a steer with the mass-weighted centroid is SMALLER
       than with the plain geometric centroid (same mesh + seed).
  G20  uniform rho_mass ⇒ the weighted centroid == the geometric centroid
       to <= 1e-9 (the floor-cancellation identity).
  G21  Qi-gate endpoints: ε=0 & ρ→∞ ⇒ κ_eff→0 (coherent cells ride momentum
       only); q→0 ⇒ κ_eff=κ (unstructured cells relax fully).

Run:  python stage5_lloyd.py
"""
import numpy as np
from stage1b_aniso import aniso_bcc_seeds, aniso_jfa_full, _ax_h
import stage1b_aniso as _sa

PHI = (1.0 + 5.0 ** 0.5) / 2.0
FLOOR = 1e-3
KAPPA = 0.5
LLOYD_P = 4.0
DRIFT_CAP = 2.0
LAM = 8.0
T_STEER = 0.005 * 25.0


# ─────────────────────────────────────────────────────────────────────────
# Mesh + the GPU mode 3/4 operators in numpy
# ─────────────────────────────────────────────────────────────────────────
class LloydAniso3D:
    """Mirror of the GPU modes 3/4 on the anisotropic JFA mesh."""

    def __init__(self, sites, N, L, aspect, rho_mass_cells):
        self.N = N
        self.L = L
        self.aspect = aspect
        self.sites = sites.copy()
        self.n = len(sites)
        self.hx, self.hy, self.hz = _ax_h(N, L, aspect)
        self.Lx, self.Ly, self.Lz = L * aspect[0], L * aspect[1], L * aspect[2]
        self.labels = aniso_jfa_full(sites, N, L, aspect)
        # per-cell deposited density on the N³ accelerator grid
        self.rho = np.asarray(rho_mass_cells, dtype=np.float64)
        # per-site cell count for the volume-free centroid denominator
        self.cell_count = np.bincount(self.labels.ravel(), minlength=self.n)

    def centers(self):
        ii, jj, kk = np.mgrid[0:self.N, 0:self.N, 0:self.N]
        return np.stack([(ii + 0.5) * self.hx, (jj + 0.5) * self.hy,
                         (kk + 0.5) * self.hz], axis=-1).reshape(-1, 3)

    def mass_centroid(self):
        """Mode 3: weighted centroid per site. w = rho_cell + FLOOR."""
        cc = self.centers()
        lab = self.labels.ravel()
        w = self.rho.ravel() + FLOOR
        num = np.zeros((self.n, 3))
        den = np.zeros(self.n)
        wx = w * cc[:, 0]
        wy = w * cc[:, 1]
        wz = w * cc[:, 2]
        for a, wv in enumerate((wx, wy, wz)):
            np.add.at(num[:, a], lab, wv)
        np.add.at(den, lab, w)
        return num / np.maximum(den, 1e-12)[:, None]

    def geo_centroid(self):
        """The plain geometric centroid (rho == 0; floor cancels)."""
        cc = self.centers()
        lab = self.labels.ravel()
        num = np.zeros((self.n, 3))
        for a in range(3):
            np.add.at(num[:, a], lab, cc[:, a])
        den = self.cell_count.astype(np.float64)
        return num / np.maximum(den, 1e-12)[:, None]

    @staticmethod
    def qi_gate(rho, eps, p=LLOYD_P):
        """κ_eff = κ·(1 − q)^p with q = ρ²/(ρ²+φ⁻²+ε²)."""
        rsq = rho * rho
        q = rsq / (rsq + 1.0 / (PHI * PHI) + eps * eps)
        return KAPPA * (1.0 - q) ** p, q

    def steer(self, psiY, psiI, piY, piI, centroid):
        """Mode 4: Qi-gated relaxation with the total-displacement guard."""
        rho = np.maximum(psiY + psiI, 1e-5)
        eps = psiY - PHI * psiI
        keff, _ = self.qi_gate(rho, eps)
        drift = LAM * (piY + piI) / rho * T_STEER
        blended = (1.0 - keff)[:, None] * (self.sites + drift[:, None]) \
            + keff[:, None] * centroid
        disp = blended - self.sites
        # GUARD: clamp the TOTAL displacement vector length to ML_MAX_DRIFT
        dlen = np.linalg.norm(disp, axis=1)
        over = dlen > DRIFT_CAP
        if over.any():
            scale = np.where(over, DRIFT_CAP / np.maximum(dlen, 1e-12), 1.0)
            disp *= scale[:, None]
        newp = self.sites + disp
        newp[:, 0] = np.mod(newp[:, 0], self.Lx)
        newp[:, 1] = np.mod(newp[:, 1], self.Ly)
        newp[:, 2] = np.mod(newp[:, 2], self.Lz)
        return newp


def _gaussian_blob(N, L, aspect, center_frac, sig_frac, amp):
    """Deposited density blob on the accelerator grid (Gaussian)."""
    hx, hy, hz = _ax_h(N, L, aspect)
    ii, jj, kk = np.mgrid[0:N, 0:N, 0:N]
    cc = np.stack([(ii + 0.5) * hx, (jj + 0.5) * hy, (kk + 0.5) * hz], axis=-1)
    C = np.array(center_frac, dtype=np.float64) * np.array(
        [L * aspect[0], L * aspect[1], L * aspect[2]])
    d2 = ((cc - C) ** 2).sum(axis=-1)
    g = np.exp(-d2 / (2.0 * (sig_frac[0] * L * aspect[0]) ** 2))
    return amp * g


def _mean_site_to_blob(sites, blob_center, aspect):
    C = np.array(blob_center, dtype=np.float64)
    d2 = ((sites - C) ** 2).sum(axis=1)
    return float(np.sqrt(d2).mean())


def lg_geo_steer(sites, N, L, aspect, psiY, psiI, piY, piI, rho_mass):
    """One mode-4 steer: mass-weighted centroid when rho_mass != 0 present,
    geometric (floor-only) centroid when the deposit is all zeros — the two
    G19 arms on identical mesh/seed/state."""
    la = LloydAniso3D(sites, N, L, aspect, rho_mass)
    if np.any(rho_mass > 0):
        c = la.mass_centroid()
    else:
        c = la.geo_centroid()
    return la.steer(psiY, psiI, piY, piI, c)


def main():
    rng = np.random.default_rng(20260813)
    N = 64
    L = 6.283185307179586
    aspect = (1.0, 1.0, 1.0)   # the cube — the G20/G21 regression geometry
    blob_frac = (0.75, 0.5, 0.5)   # off-center blob so the pull is measurable
    blob_center = np.array(blob_frac, dtype=np.float64) * L

    sites = aniso_bcc_seeds(4096, L, aspect, rng)
    rho_blob = _gaussian_blob(N, L, aspect, blob_frac, (0.12, 0.12, 0.12), 2.0)

    # ── G19: mass weighting concentrates sites toward the blob ──────────
    # Use an INCOHERENT state (rho → 0, q → 0, κ_eff ≈ κ) so the centroid
    # relaxation is actually exercised — with the coherent generic field the
    # Qi gate (q≈0.78) mutes κ_eff to ~0.001 and nothing moves. One full
    # steer: the MASS-weighted centroid (Voronoi regions overlapping the
    # deposit pull toward it) moves sites closer to the blob than the plain
    # geometric centroid (uniform Lloyd keeps the spread).
    # lowest-q state: rho ~ 0, eps finite → κ_eff ≈ κ for every site
    psiI_lo = 1e-4 * np.ones(len(sites))
    psiY_lo = psiI_lo.copy()
    piY_lo = np.zeros(len(sites))
    piI_lo = np.zeros(len(sites))
    rho_lo = np.maximum(psiY_lo + psiI_lo, 1e-5)
    eps_lo = psiY_lo - PHI * psiI_lo
    keff_lo, q_lo = LloydAniso3D.qi_gate(rho_lo, eps_lo)
    print("      (G19 steering at κ_eff=%.3f, q=%.3f)" % (keff_lo.mean(), q_lo.mean()))

    sites_geo = lg_geo_steer(sites, N, L, aspect, psiY_lo, psiI_lo, piY_lo,
                             piI_lo, np.zeros((N, N, N)))
    d_geo = _mean_site_to_blob(sites_geo, blob_center, aspect)
    sites_mass = lg_geo_steer(sites, N, L, aspect, psiY_lo, psiI_lo, piY_lo,
                              piI_lo, rho_blob)
    d_mass = _mean_site_to_blob(sites_mass, blob_center, aspect)
    # concentration: sites within the blob's radius R = 3·sigma of the center
    R = 3.0 * (0.12 * L)
    n_geo = int((np.linalg.norm(sites_geo - blob_center, axis=1) < R).sum())
    n_mass = int((np.linalg.norm(sites_mass - blob_center, axis=1) < R).sum())
    print("[G19] mean site→blob dist: plain-center %.4f  mass-weighted %.4f ; "
          "sites within blob R: plain %d  mass %d" % (d_geo, d_mass, n_geo, n_mass))
    g19 = n_mass > n_geo and (d_mass < d_geo)
    print("[G19] mass weighting concentrates sites on the blob (Δ sites = %d)" % (n_mass - n_geo))

    # ── G20: uniform rho ⇒ weighted centroid == geometric centroid ──────
    rho_uniform = 0.7 * np.ones((N, N, N))
    lu = LloydAniso3D(sites, N, L, aspect, rho_uniform)
    diff = float(np.abs(lu.mass_centroid() - lu.geo_centroid()).max())
    g20 = diff <= 1e-9
    print("[G20] |weighted − geometric| centroid max = %.3e" % diff)

    # ── G21: Qi-gate endpoints ──────────────────────────────────────────
    # eps = 0, rho → ∞ : q → 1 ⇒ κ_eff → 0
    rho_big = np.array([1.0, 1e3, 1e9, 1e15], dtype=np.float64)
    keff_big, q_big = LloydAniso3D.qi_gate(rho_big, np.zeros_like(rho_big))
    endpoint_a = float(keff_big[-1])
    # q → 0 (rho → 0, eps finite): κ_eff → κ
    rho_zero_q = np.array([1e-6, 1e-9], dtype=np.float64)
    keff_lo, q_lo = LloydAniso3D.qi_gate(rho_zero_q, np.ones_like(rho_zero_q) * 1.0)
    endpoint_b = float(keff_lo[-1])
    print("[G21] ε=0,ρ→∞: q→%.6f κ_eff→%.4e ; ρ→0: q→%.4e κ_eff→%.6f (κ=%.2f)"
          % (q_big[-1], endpoint_a, q_lo[-1], endpoint_b, KAPPA))
    g21 = endpoint_a < 1e-3 and abs(endpoint_b - KAPPA) < 1e-9

    print("---- gate ----")
    for name, ok in [("G19 mass blob concentrates sites", g19),
                     ("G20 uniform rho → weighted==geometric", g20),
                     ("G21 Qi-gate endpoints", g21)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g19 and g20 and g21)
                          else "FAILURES PRESENT"))
    return 0 if (g19 and g20 and g21) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
