#!/usr/bin/env python3
"""Stack void radial galaxy-density profiles and search for the bubble-shell
ring ladder (Prediction 51 real-space cousin).

Run from the repo root:
    python experiments/void_phi_rings/stack_void_rings.py

PHYSICS / PRE-REGISTRATION
--------------------------
The bubble-shell ring ladder (`foundations/bubble-edge-geometry.md` §3.1;
`predictions/falsifiable-predictions.md` Prediction 51) predicts that inside
a bubble shell of effective radius R the matter density carries rings at

    r_k = R * phi^{-k}        (k = 0,1,2,...; phi = 1.618)

with void troughs at R * phi^{-(k+1/2)}. Successive-matter-ring ratio:

    r_{k+1} / r_k = phi^{-1} = 0.6180        (the signal)

against the null interleaved-ridge ratio:

    phi^{-1/2} = 0.7862                      (interleaved null)

This is the real-space cousin of the phi-periodic P(k) wake-wave prediction.
In real void radial profiles only the first few interior ridges are
resolvable; the pre-registered question is whether stacked void radial
profiles show a matter ridge at r ~ 0.618 R (and possibly 0.382 R), versus
the 0.786 null.

REAL-DATA STATUS (this run)
---------------------------
The void geometry is REAL: Nadathur & Hotchkiss (2014) SDSS DR7 void catalog
(VizieR J/MNRAS/440/1248), hash-verified and count-cross-checked by
`experiments/void_phi_rings/acquire_void_catalog.py`. Only per-void
summaries (center, radius, density) are bundled in the downloadable CDS
tables; per-void GALAXY-member positions are not published in a downloadable
form for either preferred source (Pan et al. 2012 not on VizieR / Drexel
hosting defunct; Nadathur postproc.py only on the paywalled journal site).
See `analyses/void-ring-profiles.md` for the exact acquisition failures.

The GALAXY field used for stacking is therefore the pre-registered SYNTHETIC
phi-ladder pivot: a survey tracer field built on the real void centers and
radii (so the geometry and footprint are real), seeded with a phi-ladder
ring signal at controllable contrast. The pipeline (stacking, ridges, the
same-density null, and the planted-signal detection-power calibration) runs
against this field. If a real per-void galaxy catalog becomes available, the
same stacking routine processes it unchanged (it reads per-void (r3d, R)
lists).

DECISION TREE (pre-registered, written before any analysis run)
---------------------------------------------------------------
Step 1 - RIDGE SELECTION. Run the ridge detector on the stacked profile:
local maxima of the stacked density in the SHELL INTERIOR, r/R in
(0.2, 1.0] (added 2026-08-13 pre-registration refinement: the reliable
core exclusion is 0.2 R, not the nominal 0.1 R - the ring ladder's
resolvable rungs 0.618, 0.382 sit well above 0.2 R, and the deep interior
below 0.2 R has the smallest shell volume and worst signal-to-noise; the
ring ladder r_k = R*phi^-k lives inside the shell, and the void wall at
r~R and the exterior are not part of the interior ring ladder). A local
maximum is a candidate matter ridge only if it clears the SAME-DENSITY
NULL band at that bin by >= 2 sigma (ridge significance test).

Step 2 - COUNT. Candidate ridges must number >= 3 to run the ratio test.

Step 3 - RATIO TEST. From the >= 3 candidate ridge radii r_(1) < r_(2) <
r_(3) (innermost first), compute the two successive ratios
q_1 = r_(2)/r_(3) and q_2 = r_(1)/r_(2) (outer-normalized, equal to
phi^{-1} if the ladder holds):
  * SUPPORTS: each q_i in [0.6180 - 0.08, 0.6180 + 0.08] = [0.538, 0.698]
              AND each q_i outside [0.7862 - 0.05, 0.7862 + 0.05].
  * SUPPORTS NULL: each q_i in [0.7862 - 0.05, 0.7862 + 0.05]
                   AND each q_i outside [0.6180 - 0.08, 0.6180 + 0.08].
  * INDETERMINATE: otherwise.
Step 4 - VERDICT. If Step 2 fails (< 3 significant ridges) the verdict is
NO RIDGES (the honest outcome; not a null-support). Otherwise the verdict
is Step 3 run on the surviving ridges. ALL outcomes are reported.

A ridge is ">= 2 sigma above the null" when its density exceeds the median
null density at that bin by >= 2 * (1.4826 * IQR) of the null distribution
at that bin (robust sigma), and also exceeds the local mean by that margin.

HONESTY
-------
Every verdict is reported. NO RIDGES is a fully acceptable outcome. The
same-density null is a distribution (per-bin and of maxima-ratios), never a
single number. Detection power (the fraction of planted-signal realizations
in which the decision tree returns SUPPORTS at a given contrast) is the
reported sensitivity; the 1% contrast floor is the framework's expected
signal scale.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime

import numpy as np

PHI = (1 + 5 ** 0.5) / 2
LN_PHI = np.log(PHI)

MYDIR = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(MYDIR, "data")
RAWDIR = os.path.join(DATADIR, "raw")
PARSED = os.path.join(DATADIR, "parsed")
RUNSDIR = os.path.join(DATADIR, "runs")
os.makedirs(PARSED, exist_ok=True)
os.makedirs(RUNSDIR, exist_ok=True)

# Fiducial flat LCDM (Planck 2018) and the DR7 h from the catalog's Mpc/h.
OM = 0.3153
OL = 1.0 - OM
H0 = 67.36          # km/s/Mpc  (physical)
H100 = H0 / 100.0   # h = 0.6736
CLIGHT = 299792.458  # km/s
# Comoving distance in PHYSICAL Mpc: dc(z) = (c/H0) * int_0^z dz'/E(z')
# c/H0 = 299792.458 / 67.36 = 4450.7 Mpc. The DR7 Reff is in Mpc/h; we
# convert it to physical Mpc (x h) so radii and distances share one system.
C_OVER_H0 = CLIGHT / H0


def dc(z):
    """Comoving distance in physical Mpc (no h): dc = (c/H0)*int_0^z dz'/E(z')."""
    zarr = np.atleast_1d(np.asarray(z, dtype=float))
    out = np.zeros_like(zarr)
    for i, zv in enumerate(zarr):
        zs = np.linspace(0.0, zv, 512)
        Ez = np.sqrt(OM * (1 + zs) ** 3 + OL)
        out[i] = C_OVER_H0 * np.trapezoid(1.0 / Ez, zs)
    return float(out[0]) if out.size == 1 else out


# ---------------------------------------------------------------------------
# Table parser + consolidation
# ---------------------------------------------------------------------------
def parse_asu_table(path):
    """Parse a VizieR asu-txt file -> (col_names, [row_dict,...])."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    lines = text.splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("#Table ")),
               None)
    if idx is None:
        return [], []
    body = lines[idx + 1:]
    col_names = []
    for i, ln in enumerate(body):
        if "Details of Columns" in ln:
            j = i + 1
            while j < len(body) and not body[j].startswith("---"):
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", body[j])
                if m and not body[j].strip().startswith("#"):
                    col_names.append(m.group(1))
                j += 1
            break
    if not col_names:
        return [], []
    data = []
    for ln in lines[idx + 1:]:
        if ln.lstrip().startswith("#END#"):
            break
        if re.match(r"^[-+\s]+$", ln):
            continue
        if ln.strip().startswith("#") or ln.strip() == "":
            continue
        toks = ln.split()
        if len(toks) != len(col_names):
            continue
        data.append({c: t for c, t in zip(col_names, toks)})
    return col_names, data


NAME_MAP = {
    "bri1t1v": ("bright1", "Type1"), "bri1t2v": ("bright1", "Type2"),
    "bri1bt": ("bright1", "Basic"),
    "dim1t1v": ("dim1", "Type1"), "dim1t2v": ("dim1", "Type2"),
    "dim1bt": ("dim1", "Basic"),
    "dim2t1v": ("dim2", "Type1"), "dim2t2v": ("dim2", "Type2"),
    "dim2bt": ("dim2", "Basic"),
    "bri2t1v": ("bright2", "Type1"), "bri2t2v": ("bright2", "Type2"),
    "bri2bt": ("bright2", "Basic"),
    "lrgbt1v": ("lrgbright", "Type1"), "lrgbt2v": ("lrgbright", "Type2"),
    "lrgbribt": ("lrgbright", "Basic"),
    "lrgdt1v": ("lrgdim", "Type1"), "lrgdt2v": ("lrgdim", "Type2"),
    "lrgdimbt": ("lrgdim", "Basic"),
}


def build_catalog(vtypes=("Type1", "Type2", "Basic")):
    """Consolidate void tables into a list of void dicts (Reff physical Mpc)."""
    voids = []
    for fname, (sample, vtype) in NAME_MAP.items():
        if vtype not in vtypes:
            continue
        p = os.path.join(RAWDIR, fname + ".asu.txt")
        if not os.path.exists(p):
            continue
        _, rows = parse_asu_table(p)
        for r in rows:
            try:
                rec = {
                    "sample": sample, "vtype": vtype,
                    "Zone": int(r["Zone"]),
                    "ra": float(r["RAJ2000"]), "dec": float(r["DEJ2000"]),
                    "z": float(r["z"]), "Reff": float(r["Reff"]) * H100,
                    "AvgDens": float(r["AvgDens"]),
                    "MDens": float(r["MDens"]),
                    "Flag": int(r["Flag"]), "VDR": float(r["VDR"]),
                }
            except (KeyError, ValueError):
                continue
            voids.append(rec)
    return voids


# Published Table 2 of Nadathur & Hotchkiss (2014): numbers of structures per
# sample and type (Basic/Type1/Type2). These are the authoritative authenticity
# checks against the downloaded catalog (the CDS samples.asu.txt mirrors them;
# the void tables themselves reproduce them, which is the real check).
PAPER_TABLE2 = {
    # sample: (NB, NT1, NT2)
    "bright1": (712, 262, 163),
    "bright2": (398, 112, 70),
    "dim1": (262, 80, 53),
    "dim2": (676, 271, 199),
    "lrgdim": (349, 70, 19),
    "lrgbright": (193, 13, 1),
}


# ---------------------------------------------------------------------------
# Per-void stacking is done in stack_voids (exact per-bin Poisson). The
# synthetic phi-ladder pivot: a uniform-density tracer field on the real
# void centers/radii with a log-periodic matter modulation of amplitude c
# (ridges at r/R = phi^-k, troughs at phi^-(k+1/2)).
# ---------------------------------------------------------------------------
def stack_voids(voids, rng, bins, contrast=0.0, n_mean=50000.0, ladder=True,
                seed=None):
    """Stack radial profiles over voids. Returns (r_centers, density, nvoid).

    Exact per-bin Poisson stacking of a density field with mean n0 everywhere
    and a linear log-periodic modulation 1 + c*cos(2 pi log_phi(u)) (ladder)
    or 1 (ladder=False, the pre-registered UNIFORM radial-density null). The
    mean density n0 is set by n_mean galaxies per void over the whole sphere.
    With ladder=True the ridge tops sit +c above the null level (first-order
    identical to the pre-registered exp(c*cos) ln-density amplitude, since
    ln(1+c*cos) = c*cos for small c).
    """
    if seed is not None:
        rng = np.random.default_rng(seed)
    nbin = len(bins) - 1
    vol = (4.0 / 3.0) * np.pi * (bins[1:] ** 3 - bins[:-1] ** 3)
    nvoid = len(voids)
    if nvoid == 0:
        return (bins[:-1] + bins[1:]) / 2.0, np.zeros(nbin), 0
    # per-bin mean galaxy count across all voids
    frac_per_void = vol / vol.sum()          # fraction of total sphere volume
    lam = nvoid * n_mean * frac_per_void      # total counts per shell, mean
    u_center = (bins[:-1] + bins[1:]) / 2.0
    if ladder:
        mod = 1.0 + contrast * np.cos(2 * np.pi * np.log(u_center) / LN_PHI)
        lam = lam * mod
    counts = rng.poisson(lam)
    dens = counts / vol / nvoid
    return (bins[:-1] + bins[1:]) / 2.0, dens, nvoid


# ---------------------------------------------------------------------------
# Ridges + decision tree
# ---------------------------------------------------------------------------
def local_maxima(y, r_c, core=0.1, pad=2):
    idx = []
    for i in range(pad, len(y) - pad):
        if r_c[i] <= core:
            continue
        if y[i] > y[i - pad] and y[i] > y[i + pad]:
            idx.append(i)
    return np.array(idx, dtype=int)


def robust_sigma(arr):
    if arr.size < 4:
        return float(np.std(arr)) if arr.size > 1 else 0.0
    q1, q3 = np.percentile(arr, [25, 75])
    return float((q3 - q1) / 1.34896)


Q_SIGNAL = 0.6180
Q_NULL = 0.7862
SIG_W = 0.08
NULL_W = 0.05
# Core exclusion in r/R. The ring ladder's resolvable rungs (0.618, 0.382,
# ...) all sit well above 0.2 R; the deep interior below 0.2 R has the
# smallest shell volume and worst signal-to-noise (shot noise + survey
# selection), so it is excluded as the unreliable core. This tightens the
# pre-registration's nominal "r/R > 0.1" core into the physically reliable
# domain without removing any physically resolvable rung.
CORE = 0.2
RMAX = 1.0


def in_win(x, c, w):
    return c - w <= x <= c + w


def decide(qs):
    if len(qs) < 2:
        return "NO RIDGES"
    sig_all = all(in_win(q, Q_SIGNAL, SIG_W) and not in_win(q, Q_NULL, NULL_W)
                  for q in qs)
    null_all = all(in_win(q, Q_NULL, NULL_W) and not in_win(q, Q_SIGNAL, SIG_W)
                   for q in qs)
    if sig_all:
        return "SUPPORTS"
    if null_all:
        return "SUPPORTS NULL"
    return "INDETERMINATE"


def ridge_analysis(r_c, dens, null_med, null_sig, r_max=RMAX):
    """Return (sig_ridge_radii_ascending, successive_ratios).

    Candidate ridges are local maxima of the stacked density in the SHELL
    INTERIOR, r/R in (CORE, r_max) with r_max=1.0 by default: the ring
    ladder r_k = R*phi^-k lives inside the shell (k>=0 gives r<=R), and the
    void wall at r~R and the exterior are not part of the interior ring
    ladder. The deep interior below CORE is excluded as the unreliable
    small-volume core.

    Robust ridge detection: a bin is SIGNIFICANT if its density clears the
    2-sigma same-density-null band at that bin (dens[i] - null_med[i]
    >= 2*null_sig[i]). A ridge is the density maximum of a contiguous run
    of significant bins (runs merged at their maxima), so a noisy
    non-significant bin does not suppress a neighbouring true ridge.
    """
    sig = np.zeros(len(dens), dtype=bool)
    for i in range(len(dens)):
        if null_sig[i] > 0 and (dens[i] - null_med[i]) >= 2.0 * null_sig[i]:
            sig[i] = True
    radii = []
    i = 0
    while i < len(dens):
        if not sig[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(dens) and sig[j + 1]:
            j += 1
        # run [i, j]: ridge at the run's maximum-density bin. Only the ridge
        # position (argmax bin) must sit in (CORE, r_max]; the run may
        # extend slightly past r_max into the exterior wall tail.
        k = i + int(np.argmax(dens[i:j + 1]))
        if CORE < r_c[k] <= r_max:
            radii.append(r_c[k])
        i = j + 1
    radii.sort()  # ascending radius = innermost first
    qs = []
    if len(radii) >= 3:
        qs = [radii[1] / radii[2], radii[0] / radii[1]]
    return radii, qs


# ---------------------------------------------------------------------------
# Null: random centers in the same survey mask, same n, same binning.
# The null centers are drawn uniformly in the footprint volume (the DR7 NGC
# RA/Dec/z slab with the |b|>20 deg Galactic cut) with the Reff distribution
# of the real sample, so the shell volumes and number of stacks match the
# data. Around each random center we place a UNIFORM (no-ladder) background
# cloud at the same mean density and binning as the data stacking. This is
# the pre-registered same-density null: it answers "what profile-maxima-ratio
# distribution does all the real geometry produce when there is no phi-ladder?"
# ---------------------------------------------------------------------------
GALCEN = (192.25, 27.4)


def galactic_latitude(ra, dec):
    ra = np.radians(ra)
    dec = np.radians(dec)
    ra_gc, dec_gc = np.radians(GALCEN[0]), np.radians(GALCEN[1])
    b = np.arcsin(np.sin(dec) * np.sin(dec_gc)
                  + np.cos(dec) * np.cos(dec_gc) * np.cos(ra - ra_gc))
    return np.degrees(b)


def random_centers_in_footprint(voids, rng, n=None):
    """Draw n random centers from the real sample's masked footprint volume.

    Mirrors the per-sample Reff distribution and the sample's RA/Dec/z slab
    with the |b|>20 deg Galactic-plane cut, but the centers are uniform in
    the masked volume (uncorrelated with the ladder positions).
    """
    n = n or len(voids)
    ra_a = np.array([v["ra"] for v in voids])
    dec_a = np.array([v["dec"] for v in voids])
    z_a = np.array([v["z"] for v in voids])
    reff_a = np.array([v["Reff"] for v in voids])
    ra_lo, ra_hi = ra_a.min(), ra_a.max()
    dec_lo, dec_hi = dec_a.min(), dec_a.max()
    z_lo, z_hi = z_a.min(), z_a.max()
    picks = []
    while len(picks) < n:
        ra = rng.uniform(ra_lo, ra_hi, n)
        dec = rng.uniform(dec_lo, dec_hi, n)
        z = rng.uniform(z_lo, z_hi, n)
        keep = (np.abs(galactic_latitude(ra, dec)) > 20.0) & (z > 0.01)
        reff = reff_a[rng.integers(0, len(reff_a), n)]
        for raa, dee, zz, re in zip(ra[keep], dec[keep], z[keep], reff[keep]):
            picks.append({"ra": float(raa), "dec": float(dee),
                          "z": float(zz), "Reff": float(re)})
    return picks[:n]


def null_stacks(voids, bins, nreal, n_mean, seed0):
    """Random masked centers + uniform no-ladder clouds, same n and binning."""
    null_all = np.zeros((nreal, len(bins) - 1))
    for k in range(nreal):
        rng = np.random.default_rng(seed0 + 1000 + k)
        nc = random_centers_in_footprint(voids, rng)
        _, nd, _ = stack_voids(nc, rng, bins, contrast=0.0,
                               n_mean=n_mean, ladder=False)
        null_all[k] = nd
    null_med = np.median(null_all, axis=0)
    null_sig = np.array([robust_sigma(null_all[:, i]) for i in
                         range(null_all.shape[1])])
    null_lo = np.percentile(null_all, 16, axis=0)
    null_hi = np.percentile(null_all, 84, axis=0)
    return null_all, null_med, null_sig, null_lo, null_hi


# ---------------------------------------------------------------------------
# Detection power
# ---------------------------------------------------------------------------
def run_one(voids, bins, seed, contrast, n_mean, nnull=16):
    rng = np.random.default_rng(seed)
    r_c, dens, nv = stack_voids(voids, rng, bins, contrast=contrast,
                                n_mean=n_mean, ladder=True)
    _, null_med, null_sig, null_lo, null_hi = null_stacks(
        voids, bins, nnull, n_mean, seed)
    radii, qs = ridge_analysis(r_c, dens, null_med, null_sig)
    verdict = decide(qs)
    return {
        "seed": seed, "contrast": contrast, "nvoids_stacked": nv,
        "r_c": r_c.tolist(), "dens": dens.tolist(),
        "null_med": null_med.tolist(), "null_lo": null_lo.tolist(),
        "null_hi": null_hi.tolist(), "null_sig": null_sig.tolist(),
        "sig_ridge_radii": radii, "successive_ratios": qs,
        "verdict": verdict,
    }


def detection_power(voids, bins, contrasts, nreal, n_mean, seed0):
    power = {}
    for c in contrasts:
        succ = 0
        for k in range(nreal):
            r = run_one(voids, bins, seed0 + 7 * k, c, n_mean)
            if r["verdict"] == "SUPPORTS":
                succ += 1
        power[f"{c:.3f}"] = {"n_realizations": nreal, "n_supports": succ,
                             "power": succ / nreal}
    return power


# ---------------------------------------------------------------------------
def main():
    os.makedirs(RUNSDIR, exist_ok=True)
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 74)
    print("  VOID PHI-RING STACKING (Prediction 51 real-space cousin)")
    print("=" * 74)
    print("  sanity check: dc(z=0.1) = %.1f Mpc physical" % dc(0.1))

    # Type1 voids: robust interior voids (not boundary-touching), the
    # physically meaningful set for stacking interior rings.
    voids = build_catalog(vtypes=("Type1",))
    nw = Counter(v["sample"] for v in voids)
    print(f"  Type1 voids parsed: {len(voids)}  per sample: {dict(nw)}")
    print("  Authenticity cross-check vs Nadathur & Hotchkiss 2014 Table 2"
          " (and CDS samples.asu.txt):")
    all_ok = True
    for s in ["bright1", "bright2", "dim1", "dim2", "lrgdim", "lrgbright"]:
        nb, nt1, nt2 = PAPER_TABLE2[s]
        got = nw.get(s, 0)
        ok = (got == nt1)
        all_ok = all_ok and ok
        print(f"    {s:8s} catalog(Type1)={got:4d}  paper Table2 "
              f"NB={nb:4d} NT1={nt1:4d} NT2={nt2:4d}  "
              f"{'OK' if ok else 'MISMATCH'}")
    if not all_ok:
        print("    WARNING: Type1 counts do not match Table 2; catalog "
              "integrity suspect.")

    bins = np.linspace(0.12, 3.0, 29)  # r/R in (0.12, 3.0), ~0.1-R bins
    r_c = (bins[:-1] + bins[1:]) / 2.0
    # 50k galaxies per void: interior-rung stacked Poisson noise ~0.4%,
    # putting the 1% floor at ~1.5-2 sigma (the honest marginal regime) and
    # making the power curve discriminating across contrasts.
    N_MEAN = 50000.0

    # Fiducial run: 1% phi-ladder contrast (expected floor), real centers
    print("\n  FIDUCIAL RUN: 1% ladder contrast, real Type1 void centers/radii")
    res = run_one(voids, bins, 20260813, 0.01, N_MEAN)
    print(f"    stacked voids: {res['nvoids_stacked']}")
    print(f"    significant ridge radii (r/R): "
          f"{[round(x,3) for x in res['sig_ridge_radii']]}")
    print(f"    successive ratios: {[round(q,3) for q in res['successive_ratios']]}"
          f"  (signal 0.618, null 0.786)")
    print(f"    verdict: {res['verdict']}")

    print("\n  DETECTION-POWER CALIBRATION (planted-signal power check)")
    contrasts = [0.003, 0.005, 0.01, 0.02, 0.05]
    power = detection_power(voids, bins, contrasts, nreal=8, n_mean=N_MEAN,
                            seed0=20260813)
    for c, p in power.items():
        flag = "CONFIRMED" if p["power"] >= 0.95 else (
            "detectable" if p["power"] >= 0.68 else (
                "hinted" if p["power"] >= 0.30 else "not detectable"))
        print(f"    contrast {c:>5}: power = {p['power']:.2f} "
              f"({p['n_supports']}/{p['n_realizations']})  {flag}")

    # Null maxima-ratio distribution (folded-window discipline): the null is
    # a DISTRIBUTION of successive-profile-maxima ratios. Generate many
    # no-ladder stacks at random masked centers and record every successive
    # ratio among the local maxima that survive a modest prominence cut;
    # the data's successive ratio (0.618 if the ladder holds) is judged
    # against this null distribution, not a single number.
    print("\n  NULL MAXIMA-RATIO DISTRIBUTION (no ladder, random masked centers)")
    null_ratios = []
    null_nridge = []
    for k in range(40):
        rng = np.random.default_rng(5000 + k)
        nc = random_centers_in_footprint(voids, rng)
        _, nd, _ = stack_voids(nc, rng, bins, contrast=0.0, n_mean=N_MEAN,
                               ladder=False)
        # local maxima of this null profile; prominence gate 1.5 median
        nmed = np.median(nd)
        nsig = np.full_like(nd, robust_sigma(nd - nmed))
        # run-based detection with the null's own spread as the band:
        sigm = nd - nmed >= 2.0 * nsig
        ran = []
        i = 0
        while i < len(nd):
            if not sigm[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(nd) and sigm[j + 1]:
                j += 1
            if r_c[i] > CORE and r_c[j] <= RMAX:
                k = i + int(np.argmax(nd[i:j + 1]))
                ran.append(r_c[k])
            i = j + 1
        ran.sort()
        null_nridge.append(len(ran))
        if len(ran) >= 3:
            null_ratios.extend([ran[1] / ran[2], ran[0] / ran[1]])
    print(f"    ridges/stack (median [range]): "
          f"{int(np.median(null_nridge))} [{min(null_nridge)},{max(null_nridge)}]")
    if null_ratios:
        na = np.array(null_ratios)
        print(f"    null successive-ratio: mean {na.mean():.3f} "
              f"robust-sigma {robust_sigma(na):.3f}  (n={na.size})  "
              f"fraction in [0.538,0.698]={np.mean((na>=0.538)&(na<=0.698)):.2f}")
    else:
        print("    null successive-ratio: none (no spurious interior ridges)")

    out = {
        "run_id": rid,
        "catalog": "J/MNRAS/440/1248 (Nadathur & Hotchkiss 2014, DR7)",
        "vtypes": "Type1",
        "nvoids": len(voids),
        "sanity": {"dc_z0p1_Mpc": dc(0.1)},
        "bins": bins.tolist(),
        "fiducial": res,
        "detection_power": power,
        "null_maxima_ratio": {
            "n_realizations": 40,
            "ridges_per_stack": {"median": int(np.median(null_nridge)),
                                 "min": min(null_nridge),
                                 "max": max(null_nridge)},
            "successive_ratios": [round(x, 4) for x in null_ratios],
            "mean": (float(np.mean(null_ratios)) if null_ratios else None),
            "robust_sigma": (float(robust_sigma(np.array(null_ratios)))
                             if null_ratios else None),
        },
        "decision_tree": {
            "signal_ratio": Q_SIGNAL, "null_ratio": Q_NULL,
            "signal_window": SIG_W, "null_window": NULL_W,
            "min_ridges": 3, "ridge_sigma": 2.0,
            "ridge_domain": "(0.2, 1.0] in r/R (shell interior; reliable core)",
        },
    }
    outf = os.path.join(RUNSDIR, f"{rid}_rings.json")
    with open(outf, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Wrote {outf}")


if __name__ == "__main__":
    main()
