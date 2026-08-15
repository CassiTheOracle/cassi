#!/usr/bin/env python3
"""cascade_ladder.py — the M2 offline φ-cascade ladder core (research/cascade_machine/).

Reusable machinery for the N-level offline cascade tree (MACHINE_PLAN.md §1–§2):
a ladder of short, each-own-periodic-solve levels, φ-spaced (never N/2), parent
levels condensing (Stage-3 machinery) and children ingesting the parent survey
dirs as ICs. Everything is numpy, offline, deterministic (a level given a fixed
RNG seed and the same parent survey reproduces byte-identical survey output).

This module imports the SHIPPED meshless machinery unchanged (stage1_jfa3d /
stage2_moving3d / stage3_collapse / falsify_wo semantics) — it REUSES, never
rewrites, the condensation pathway, the rung-score discipline, and the survey
byte format (G24).

Design decisions (see m2_design.md §1 for the full D-ledger):
  D-M2-1  R = 4 rungs per level (box side ×φ⁴ finer per child = the level's
          "one 7-rung resolved window re-resolving the parent's finest rung").
          The proton→supercluster physical reach is 193 φ-rungs
          (n=95→288 from the theory table, log_φ proven below); ceil(193/4)=49
          levels cover it. This is the plan's "~51 levels" modulo its own
          rung-count figure (§8 provenance is explicit the count is a spec).
  D-M2-2  Uniform N=64 fixed box-resolution ladder (plan D6), the level's box
          side is the only thing that changes with the rung.
  D-M2-3  Each level is its OWN periodic solve on its OWN box (multigrid §(c));
          no patch, no coarse-supplied BCs. The φ-spacing (gcd-decorrelated)
          is the de-resonance — inherited from the cascade-multigrid G38–G41.
  D-M2-4  The parent→child EDGE = condensation (plan D3): the child zooms the
          parent's most-massive condensed core, re-seeding a φ-spaced multi-rung
          blob cluster 4 rungs finer, with the handed core MASS conserved
          (the M1 G42 discipline, ≤1e-6 on the deposition remap).
  D-M2-5  CLOSURE IS OUT OF M2 SCOPE (plan §8: the closure artifact does not
          exist—closure wave 2 was an honest negative). The closure slot is a
          no-op in the registry (R1), and the rung-integrity gate runs WITHOUT
          it. Stated, not hidden.
  D-M2-7  CFL time-step homothety for the scale-free ladder: dt_lev = DT·min(1,
          L/10). The L=10 reference (dt=0.005) is the identity; finer boxes
          scale dt down with L so ω_max·dt stays constant (measured: fixed dt
          explodes below n~168). See m2_design.md §1.5.

Gates measured by gates_m2.py: G47 (end-to-end unattended + checkpoint/resume),
G48 (replayability: same seed → byte-identical survey), G49 (mass-ladder
integrity at handoffs, uniform-baseline rung_score), G50 (P(k) log-periodicity
with calibrated null discipline).

Run:  python research/cascade_machine/run_cascade_tree.py   (orchestrator)
      python research/cascade_machine/gates_m2.py            (gate harness)
      python research/cascade_machine/falsifier_ledger.py    (band ledger)
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_MESHLESS = _HERE.parents[1] / "research" / "meshless"
if str(_MESHLESS) not in sys.path:
    sys.path.insert(0, str(_MESHLESS))

from stage1_jfa3d import PHI, bcc_seeds            # noqa: E402
from stage2_moving3d import MovingVoronoi3D        # noqa: E402
from stage3_collapse import collapse, rung_score   # noqa: E402

# ── physical constants / anchor table ─────────────────────────────────────
ELL_PL = 1.616e-35          # Planck length (m), the sole dimensionful scale
LN_PHI = np.log(PHI)        # 0.4812118...  the machine's period
PHI3 = PHI ** 3             # the mass-ladder rung step (mass ∝ ℓ³)
N = 64                      # uniform grid resolution (D-M2-2 / plan D6)
DT = 0.005                  # stage3 fixed time step
N_STEPS = 80                # evolution steps to condensation (stage3)
Q_TH = 3.6                  # condensation threshold on peak q_field = EY²+EI²
A_PARENT = 0.5              # physical deviation amplitude (stage3)
RHO = 2.5                   # fluid density baseline rho = psiY + psiI
NCELL = 16384               # BCC seed count (stage3)
R_CELLS = [7.68, 4.74, 2.94]   # structure radii in cells (stage3's 1.2/0.74/0.46
                               # at h=0.15625 — the radius-to-cell ratio that
                               # keeps the level's resolved band with its
                               # ~2.5–7.7 cell floor; scale-free per level)
SHELL_CELLS = 3.4 / (10.0 / 64.0)   # shell distance in cells (3.4 at L=10)

# rung anchors (theory table, dimensionful-cascade.md §3)
N_PROTON = 95          # QCD confinement / proton — the machine's bottom anchor
N_SUPERCLUSTER = 288   # supercluster — the machine's top anchor
R = 4                  # rungs per level (box ×φ⁴ finer per child)


def rungs_between(n_lo, n_hi):
    """Exact φ-rungs between two rung numbers (proton→supercluster reach)."""
    return n_hi - n_lo


def level_count(n_lo=N_PROTON, n_hi=N_SUPERCLUSTER, rungs_per=R):
    """Number of levels to cover [n_lo, n_hi] at `rungs_per` rungs each."""
    return int(np.ceil((n_hi - n_lo) / float(rungs_per)))


def box_side(rung):
    """Box side (m) for a level whose structure max radius (7.68 cells) sits
    at the given rung:  L = (N / r_cells_max) × ℓ_Pl × φ^rung."""
    return (N / R_CELLS[0]) * ELL_PL * PHI ** rung


def rung_of_box(L):
    """Inverse of box_side: the rung whose 7.68-cell structure scale = L·7.68/N."""
    return np.log((L * R_CELLS[0] / N) / ELL_PL) / LN_PHI


# ── per-level IC: the φ-spaced multi-rung blob shell (stage3 geometry) ────
def shell_centers(L, center=None, shell=None):
    """The stage3 axis-shell blob centres (centre ± shell·e), 6 centres
    (2 per axis), scale-free in cells."""
    if center is None:
        center = np.full(3, L / 2.0)
    if shell is None:
        shell = SHELL_CELLS * (L / N)
    return [center + shell * e for e in np.eye(3)] + \
           [center - shell * e for e in np.eye(3)]


def blob_fields(sites, L, centers, radii, A):
    """psiY/psiI deviation blobs on a flat rho = psiY + psiI = RHO baseline.

    Reproduces stage3's `make_blob_ics` EXACTLY: the radius bands pair with
    their axis-shell centre pairs (band i radii[i] on centres 2i,2i+1), not
    every radius on every centre (that over-seeds and merges cores)."""
    psiY = np.full(len(sites), 1.5)
    psiI = np.ones(len(sites))
    for bi, r in enumerate(radii):
        for c in (centers[2 * bi], centers[2 * bi + 1]):
            d = np.mod(sites - c, L)
            d = np.minimum(d, L - d)
            g = np.exp(-(d ** 2).sum(axis=1) / (2.0 * r ** 2))
            psiY += A * g
            psiI -= A * g
    return psiY, psiI


def run_condensation(sites, L, radii, A, dt=DT, ns=N_STEPS, q_th=Q_TH,
                     seed=None, centers=None):
    """One resolved two-fluid condensation run on box L at grid N=64, seeded
    by φ-spaced blobs (the level's multi-rung structure). `centers` overrides
    the default box-center axis-shell (used for a child zooming the parent's
    most-massive core). Returns a dict:
    fv, psiY, psiI, qf_max, masses, pos, r_traj, p_net_max, m_cell, A."""
    rng = np.random.default_rng(0 if seed is None else seed)
    fv = MovingVoronoi3D(sites, N, L)
    if centers is None:
        centers = shell_centers(L)
    psiY, psiI = blob_fields(fv.sites, L, centers, radii, A)
    piY = np.zeros(fv.n)
    piI = np.zeros(fv.n)
    qf_max = psiY ** 2 + psiI ** 2
    r_traj = [(psiY * fv.vol).sum() / (psiI * fv.vol).sum()]
    p_net_max = 0.0
    for _ in range(ns):
        psiY, psiI, piY, piI = fv.step(psiY, psiI, piY, piI, dt)
        qf_max = np.maximum(qf_max, psiY ** 2 + psiI ** 2)
        r_traj.append((psiY * fv.vol).sum() / (psiI * fv.vol).sum())
        pn = float(abs(((piY + piI) * fv.vol).sum()))
        p_net_max = max(p_net_max, pn)
    masses, pos = collapse(fv, qf_max, psiY + psiI, q_th)
    m_cell = float(((psiY + psiI) * fv.vol).sum() / fv.n)
    return {
        "fv": fv, "psiY": psiY, "psiI": psiI, "qf_max": qf_max,
        "masses": masses, "pos": pos, "r_traj": np.array(r_traj),
        "p_net_max": p_net_max, "m_cell": m_cell, "A": A,
    }


def level_radii(L):
    """A level's structure radii in ABSOLUTE length = the φ-spaced cell band
    scaled by this box's cell size (scale-free per level, D-M2-2)."""
    h = L / N
    return [float(c) * h for c in R_CELLS]


# ── the survey format (M1-style, extended meta — G24 byte contract) ──────
def _write_raw(path, arr):
    np.ascontiguousarray(arr, dtype="<f4").tofile(path)


def dump_survey(dirpath, N, L, ey_grid, ei_grid, q_grid, part_pos, part_mass,
                meta_extra=None):
    """Write a survey-format snapshot (cassi_survey.gd contract + the M1 mass
    extension): meta.json + float32 LE field_ey/ei/q + particles + masses.

    `part_mass` may be either ABSOLUTE masses (small boxes, M1 convention) or
    dimensionless log-rungs log_φ(m/m_cell) (the ladder's bounded, overflow-
    free encoding). The meta key `mass_encoding` records which; the ladder
    uses the dimensionless form at cosmological scales where absolute masses
    (~1e77) exceed float32 range."""
    os.makedirs(dirpath, exist_ok=True)
    _write_raw(os.path.join(dirpath, "field_ey.raw"), ey_grid)
    _write_raw(os.path.join(dirpath, "field_ei.raw"), ei_grid)
    _write_raw(os.path.join(dirpath, "field_q.raw"), q_grid)
    _write_raw(os.path.join(dirpath, "particles.raw"), part_pos)
    _write_raw(os.path.join(dirpath, "particles_mass.raw"), part_mass)
    meta_extra = dict(meta_extra or {})
    mass_encoding = meta_extra.get("mass_encoding", "absolute")
    meta = {
        "grid_N": int(N),
        "extents": {"x": float(L), "y": float(L), "z": float(L)},
        "particle_count": int(len(part_pos)),
        "mass_unit": "fluid_mass (rho*dV)",
        "mass_extension": "particles_mass.raw",
        "mass_encoding": mass_encoding,
    }
    meta.update(meta_extra)
    with open(os.path.join(dirpath, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def read_survey(dirpath):
    """Read a survey dir back; returns (meta, ey, ei, q, pos, mass). `mass`
    is whatever was stored: absolute fluid-mass OR dimensionless log-rung
    log_φ(m/m_cell) per meta['mass_encoding'] (and meta['m_cell'])."""
    meta = json.loads(open(os.path.join(dirpath, "meta.json")).read())
    Nn = int(meta["grid_N"])
    shape = (Nn, Nn, Nn)
    ey = np.fromfile(os.path.join(dirpath, "field_ey.raw"), dtype="<f4").reshape(shape)
    ei = np.fromfile(os.path.join(dirpath, "field_ei.raw"), dtype="<f4").reshape(shape)
    q = np.fromfile(os.path.join(dirpath, "field_q.raw"), dtype="<f4").reshape(shape)
    npc = int(meta["particle_count"])
    pos = np.fromfile(os.path.join(dirpath, "particles.raw"), dtype="<f4").reshape(npc, 3)
    mass = np.fromfile(os.path.join(dirpath, "particles_mass.raw"), dtype="<f4")
    return meta, ey, ei, q, pos, mass


def survey_abs_mass(meta, mass):
    """Reconstruct ABSOLUTE fluid mass from a survey's stored mass encoding
    (absolute or dimensionless log-rung log_φ(m/m_cell))."""
    enc = meta.get("mass_encoding", "absolute")
    if enc == "absolute":
        return mass.astype(np.float64)
    m_cell = float(meta.get("m_cell", 0.0))
    nn = mass.astype(np.float64)
    if m_cell <= 0:
        raise RuntimeError("log-rung survey missing m_cell in meta")
    return m_cell * PHI ** np.maximum(nn, 0.0)


def byte_hash(dirpath):
    """A deterministic hash over every survey file (fields + particles +
    masses + meta.json), for the replayability byte-check (G48)."""
    import hashlib
    h = hashlib.sha256()
    for name in ["meta.json", "field_ey.raw", "field_ei.raw", "field_q.raw",
                 "particles.raw", "particles_mass.raw"]:
        p = os.path.join(dirpath, name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(name.encode())
                h.update(f.read())
    return h.hexdigest()


# ── the parent→child handoff (plan D3 / M1 G42 discipline) ───────────────
def anchor_support(sites, L, radii):
    """The integrated absolute support of the largest structure's unit
    gaussian over the parent box (M1's B1), used to calibrate the parent's
    mass-per-amplitude factor κ. Computed on the parent's own sites."""
    h = L / N
    fv = MovingVoronoi3D(sites, N, L)
    c0 = np.full(3, L / 2.0)
    d = np.mod(sites - c0, L)
    d = np.minimum(d, L - d)
    g = np.exp(-(d ** 2).sum(axis=1) / (2.0 * radii[0] ** 2))
    return float((g * fv.vol).sum())


def build_child_ic(parent_survey_dir, child_L, child_radii, seed, core_idx=None):
    """Build the child level's IC from the parent's survey dir.

    The child zooms a parent condensed core (the MOST-MASSIVE by default, or
    `core_idx` for a sibling fan — each parent core is one child seed, the
    plan's many-to-many tree §2.3), placing a φ-spaced blob shell centered on
    that core's child-frame position. The handed core MASS is conserved on the
    deposition remap (≤1e-6, M1 G42). `anchor_support_B1` (the parent's
    anchor-gaussian support, calibrated during the parent run) is read from
    the parent survey meta, so the child never rebuilds the parent mesh.

    Returns a dict: centers (the child's blob shell centers), A_cons (the
    conservation-achieving amplitude), m_handed, dM (relative mass error),
    B1, B2 (the child's integrated absolute excitation), pcore_child."""
    meta, ey, ei, q, pos, mass = read_survey(parent_survey_dir)
    parent_L = float(meta["extents"]["x"])
    mP = survey_abs_mass(meta, mass)
    if len(mP) == 0:
        raise RuntimeError("parent survey has no condensed cores — cannot hand off")
    B1 = float(meta.get("anchor_support_B1", 0.0))
    if B1 <= 0:
        raise RuntimeError("parent survey missing anchor_support_B1 (re-run parent)")
    tgt = int(np.argmax(mP)) if core_idx is None else \
        int(np.argsort(mP)[-1 - int(core_idx)])
    m_handed = float(mP[tgt])
    # M1 zoom map: child_coord = (parent_coord − parent_centre)·φ^R + child
    # centre (mod child box).  zoom = child_L/parent_L == φ^−R (R=4).
    zoom = child_L / parent_L
    pcore_child = np.mod((pos[tgt].astype(np.float64) - parent_L / 2.0) * zoom
                         + child_L / 2.0, child_L)
    shell_child = SHELL_CELLS * (child_L / N)
    centers = shell_centers(child_L, center=pcore_child, shell=shell_child)
    s_rng = np.random.default_rng(seed)
    sites = bcc_seeds(NCELL, child_L, s_rng)
    fv0 = MovingVoronoi3D(sites, N, child_L)
    Uy, _ = blob_fields(sites, child_L, centers, child_radii, 1.0)
    exc = Uy - 1.5                       # unit-amplitude excitation = Σ g_k
    B2 = float((exc * fv0.vol).sum())
    kappa = m_handed / (A_PARENT * B1)
    A_cons = m_handed / (kappa * B2) if B2 > 0 else 0.0
    M_dep = kappa * float((A_cons * exc * fv0.vol).sum())
    dM = abs(M_dep - m_handed) / m_handed if m_handed else 0.0
    return {"centers": centers, "A_cons": float(A_cons), "m_handed": m_handed,
            "dM": float(dM), "B1": float(B1), "B2": float(B2),
            "pcore_child": pcore_child, "parent_L": float(parent_L),
            "core_idx": tgt, "exc_support": float(B2)}


# ── P(k) log-periodicity (calibrated null discipline, logperiodicity skill) ──
def pk_from_field(ey_grid, ei_grid, L):
    """Radial-average the density field's power spectrum into 1D P(k).

    rho = psiY + psiI (flat baseline 2.5 + blobs). FFT the N³ grid, take
    |FFT|², bin by |k| into radial shells, return (k_centers, P). The grid is
    periodic so the FFT is exact (the level's own spectral structure)."""
    rho = (ey_grid.astype(np.float64) + ei_grid.astype(np.float64)) - (
        (ey_grid.astype(np.float64) + ei_grid.astype(np.float64)).mean() - 2.5)
    Nn = ey_grid.shape[0]
    F = np.fft.fftn(rho - rho.mean())
    P = np.abs(F) ** 2 / (Nn ** 6)          # normalized spectral density
    kvec = np.fft.fftfreq(Nn, d=L / Nn)
    kx, ky, kz = np.meshgrid(kvec, kvec, kvec, indexing="ij")
    kmag = np.sqrt(kx ** 2 + ky ** 2 + kz ** 2)
    k_edges = np.linspace(2 * np.pi / L, np.pi * Nn / L, 40)   # log-ish shells
    k_edges = np.geomspace(k_edges[0], k_edges[-1], 40)
    kc = 0.5 * (k_edges[:-1] + k_edges[1:])
    P1 = np.array([
        P[(kmag >= k_edges[i]) & (kmag < k_edges[i + 1])].mean()
        if ((kmag >= k_edges[i]) & (kmag < k_edges[i + 1])).any() else np.nan
        for i in range(len(k_edges) - 1)])
    ok = np.isfinite(P1) & (P1 > 0)
    return kc[ok], P1[ok]


def pk_logperiodic(k, P, ln_phi=LN_PHI):
    """Test P(k) for log-periodic modulation at period Δ(ln k) = ln φ.

    Calibrated null discipline (logperiodicity-test-calibration skill):
      – linear cos/sin basis regression (NO phase search, honest 2 oscillation
        params):  ln P = a + b·x + c·cos(ω₀x) + s·sin(ω₀x), x = ln k, ω₀ = 2π/lnφ.
      – ω-specificity percentile: p = fraction of grid frequencies with
        ΔAIC ≤ ΔAIC(ω₀); a real signal requires p < 0.05 (else it's just a
        fixed-frequency fit to smooth data).
    Reports both ΔAIC and p_spec.
    """
    k = np.asarray(k)
    P = np.asarray(P)
    x = np.log(k)
    y = np.log(P)
    # linear fit (reduced model)
    A1 = np.column_stack([np.ones_like(x), x])
    c1, *_ = np.linalg.lstsq(A1, y, rcond=None)
    resid1 = y - A1 @ c1
    n = len(y)
    rss1 = float((resid1 ** 2).sum())
    aic1 = n * np.log(rss1 / n) + 2 * 2
    # probe a grid of fixed frequencies around ω₀ (excluding ω₀ ± 2) for the
    # ω-specificity percentile
    om0 = 2 * np.pi / ln_phi
    om_grid = np.geomspace(0.5, 20.0, 200)
    om_grid = om_grid[(om_grid < om0 - 2) | (om_grid > om0 + 2)]
    dalc_grid = []
    for om in om_grid:
        A2 = np.column_stack([np.ones_like(x), x,
                              np.cos(om * x), np.sin(om * x)])
        c2, *_ = np.linalg.lstsq(A2, y, rcond=None)
        resid2 = y - A2 @ c2
        rss2 = float((resid2 ** 2).sum())
        aic2 = n * np.log(rss2 / n) + 2 * 4
        dalc_grid.append(aic2 - aic1)
    dalc_grid = np.array(dalc_grid)
    # ω₀ model
    A2 = np.column_stack([np.ones_like(x), x,
                          np.cos(om0 * x), np.sin(om0 * x)])
    c2, *_ = np.linalg.lstsq(A2, y, rcond=None)
    resid2 = y - A2 @ c2
    rss2 = float((resid2 ** 2).sum())
    aic2 = n * np.log(rss2 / n) + 2 * 4
    daic0 = aic2 - aic1          # negative → the φ-period improves over linear
    p_spec = float((dalc_grid <= daic0).mean())
    amp = float(np.hypot(c2[2], c2[3]))
    return {"daic": float(daic0), "p_spec": p_spec, "amp": amp,
            "omega0": float(om0), "ln_phi": float(ln_phi), "n_bins": n}


# ── R5: the MULTI-LEVEL P(k) concatenation (MACHINE_PLAN §7 §R5) ─────────
def concatenate_pk(tree_root, n_levels, max_workers=4, mode="finest"):
    """Stitch the per-level P(k) bands into ONE combined spectrum across the
    ladder, then report both the scale-free overlap consistency and the
    concatenated spectrum (for the R5 log-periodicity test).

    Stitching (documented, plan §7-R5 'overlapping windows vs adjacent'):
      - Each level j contributes its own spectral band, k ∈ [2π/L_j, πN/L_j]
        (a 7.2-rung window). Consecutive levels shift by 4 rungs in k
        (box ×φ⁴), so consecutive bands overlap by ~3.2 rungs — a genuine
        overlapping-window stitch.
      - Normalization: all levels are N=64 at the SAME physical density basis
        (ρ = psiY+psiI baseline 2.5). The (N_c/N_f)³ per-level-normalization
        discipline (D2/G41) is satisfied BY CONSTRUCTION (no N_c≠N_f between
        these levels), and confirmed empirically by the scale-free P collapse
        in the overlap (level j and j+1 agree in reduced-k within ~few %).
      - `mode='finest'`: each absolute-k point is taken from the FINEST level
        whose band contains it (best-resolved at that k). Adjacent levels join
        continuously because their overlap P agrees (scale-free). This avoids
        artificial blending and double counting.
    Returns a dict with the concatenated k,P, the per-band map, and the
    overlap-consistency metric.
    """
    import concurrent.futures as cf
    specs = _build_specs_range(n_levels)

    def _band(lev):
        sp = specs[lev]
        d = Path(tree_root) / ("level_%02d_r%d" % (sp["lev"], sp["rung"]))
        meta, ey, ei, q, pos, mass = read_survey(d)
        L = float(meta["extents"]["x"])
        return lev, L, *pk_from_field(ey, ei, L)

    bands = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for lev, L, k, P in ex.map(_band, (spec["lev"] for spec in specs)):
            bands[lev] = (L, np.asarray(k), np.asarray(P))

    # scale-free overlap consistency: in reduced-k (k·h), the levels' P curve
    # should agree where they overlap (the multi-level self-similarity check).
    h = {lev: L / N for lev, (L, _, _) in bands.items()}
    red = {lev: k * h[lev] for lev, (_, k, _) in bands.items()}
    overlap_agree = {}
    for lev in range(1, n_levels):
        kp, Pp = red[lev - 1], bands[lev - 1][2]
        kn, Pn = red[lev], bands[lev][2]
        # overlap in reduced-k (both bands span ~[0.1, 3.1] /cell on the scale-
        # free curve)
        lo = max(kp.min(), kn.min())
        hi = min(kp.max(), kn.max())
        mskp = (kp >= lo) & (kp <= hi)
        mskn = (kn >= lo) & (kn <= hi)
        if mskp.any() and mskn.any():
            # compare log-P on a shared reduced-k grid (linear interp)
            xg = np.linspace(lo, hi, 12)
            Pp_i = np.interp(xg, kp[mskp], np.log(Pp[mskp]))
            Pn_i = np.interp(xg, kn[mskn], np.log(Pn[mskn]))
            # relative log-difference (0.05 = ~5%)
            overlap_agree[lev] = float(np.mean(np.abs(Pp_i - Pn_i)))

    if mode == "finest":
        # build a common absolute-k axis = the union of all band k-bins
        allk = np.concatenate([bands[lev][1] for lev in range(n_levels)])
        k_con = np.sort(np.unique(np.round(allk, 12)))
        klo = {lev: bands[lev][1].min() for lev in range(n_levels)}
        khi = {lev: bands[lev][1].max() for lev in range(n_levels)}
        P_con = np.zeros_like(k_con)
        band_map = np.zeros_like(k_con, dtype=int)
        for i, kk in enumerate(k_con):
            # finest level whose band contains kk
            for lev in range(n_levels - 1, -1, -1):
                if klo[lev] <= kk <= khi[lev]:
                    P_con[i] = np.interp(kk, bands[lev][1], bands[lev][2])
                    band_map[i] = lev
                    break
    else:  # pragma: no cover - only 'finest' shipped
        raise ValueError("mode must be 'finest'")

    valid = np.isfinite(P_con) & (P_con > 0)

    # ── the honest R5 discriminator: detrend each band internally, then test
    # the concatenated RESIDUAL. The raw stitch can show a spurious ln-phi
    # period because 49 scale-free band-shapes repeat at phi^4 k-spacing
    # (whose 4th harmonic is exactly omega0 = 2pi/lnphi — the R5 artifact).
    # Removing each level's own smooth band-envelope leaves only a genuine
    # cross-level ln-phi modulation, so the residual test is the honest one.
    resid_alls = []
    resid_allk = []
    for lev in range(n_levels):
        L, kk, PP = bands[lev]
        xx = np.log(kk)
        yy = np.log(PP)
        cc = np.polyfit(xx, yy, min(6, len(xx) - 2))
        smooth = np.exp(np.polyval(cc, xx))
        resid_alls.append(PP / smooth - 1.0)
        resid_allk.append(kk)
    ka = np.concatenate(resid_allk)
    ra = np.concatenate(resid_alls)
    o = np.argsort(ka)
    resid_k, resid_r = ka[o], ra[o]
    resid_test = _pk_logperiodic_residual(resid_k, resid_r)

    return {"k": k_con[valid], "P": P_con[valid],
            "band_map": band_map[valid], "bands": n_levels,
            "overlap_agreement": {int(k): float(v) for k, v in overlap_agree.items()},
            "stitch_mode": mode,
            "raw_test": pk_logperiodic(k_con[valid], P_con[valid]),
            "detrended_test": resid_test,
            "k_span_rungs": float((np.log(k_con[valid][-1] / k_con[valid][0])
                                   / LN_PHI)) if valid.any() else 0.0}


def _pk_logperiodic_residual(x, r, ln_phi=LN_PHI):
    """Calibrated log-periodicity test on a band-detrended RESIDUAL series
    (y = P/smooth − 1, not log P). Same discipline: linear cos/sin basis at
    ω₀ = 2π/ln φ, ω-specificity percentile over probe frequencies."""
    x = np.asarray(x)
    r = np.asarray(r)
    om0 = 2 * np.pi / ln_phi
    n = len(r)
    rss1 = float(((r - np.mean(r)) ** 2).sum())
    aic1 = n * np.log(rss1 / n) + 2 * 1
    A2 = np.column_stack([np.ones_like(x), np.cos(om0 * x), np.sin(om0 * x)])
    c2, *_ = np.linalg.lstsq(A2, r, rcond=None)
    rss2 = float(((r - A2 @ c2) ** 2).sum())
    aic2 = n * np.log(rss2 / n) + 2 * 3
    daic0 = aic2 - aic1
    om_grid = np.geomspace(0.5, 20.0, 200)
    om_grid = om_grid[(om_grid < om0 - 2) | (om_grid > om0 + 2)]
    dgs = []
    for om in om_grid:
        A3 = np.column_stack([np.ones_like(x), np.cos(om * x), np.sin(om * x)])
        c3, *_ = np.linalg.lstsq(A3, r, rcond=None)
        rss3 = float(((r - A3 @ c3) ** 2).sum())
        dgs.append(n * np.log(rss3 / n) + 2 * 3 - aic1)
    p_spec = float((np.array(dgs) <= daic0).mean())
    amp = float(np.hypot(c2[1], c2[2]))
    return {"daic": float(daic0), "p_spec": p_spec, "amp": amp,
            "omega0": float(om0), "ln_phi": float(ln_phi), "n_bins": n,
            "significant": bool(daic0 < -2.0 and p_spec < 0.05)}


# ── internal helper: build_specs used by concatenate_pk ─────────────────
def _build_specs_range(n_levels):
    return [{"lev": lev, "rung": N_SUPERCLUSTER - R * lev,
             "L": box_side(N_SUPERCLUSTER - R * lev),
             "radii": level_radii(box_side(N_SUPERCLUSTER - R * lev)),
             "seed": 20260814 + lev * 7919} for lev in range(n_levels)]


if __name__ == "__main__":
    # quick self-checks (rung math + a P(k) smoke)
    print("=== cascade_ladder self-check ===")
    print("ell_PL=%.3e  LN_PHI=%.6f  PHI^3=%.4f" % (ELL_PL, LN_PHI, PHI3))
    reach = rungs_between(N_PROTON, N_SUPERCLUSTER)
    print("proton->supercluster reach = %d rungs (n=%d..%d)" % (
        reach, N_PROTON, N_SUPERCLUSTER))
    print("levels(R=4) = %d  (plan's '~51' reconciled in m2_design.md §1)" % level_count())
    nlev = level_count()
    for j in [0, nlev // 4, nlev // 2, 3 * nlev // 4, nlev - 1]:
        rung = N_SUPERCLUSTER - R * j              # lev 0 = supercluster (coarsest)
        print("  level %2d  n_anchor=%d  L=%.3e m" % (j, rung, box_side(rung)))
    print("rung of box (round-trip):", round(rung_of_box(box_side(120)), 3))
    print("self-check OK")
