#!/usr/bin/env python3
"""Calibrate a void-ring ridge detector on synthetic radial count profiles.

Run from the repo root:
    python experiments/void_phi_rings/stack_void_rings.py

The target from `foundations/bubble-edge-geometry.md` §3.1 and Prediction 51
is a matter-ring ladder

    r_k / R = phi^-k,          r_(k+1) / r_k = phi^-1 = 0.6180,

with the interleaved comparison ratio phi^-1/2 = 0.7862.

SCOPE
-----
This script is a synthetic detector and power calibration, not a real-data
stack. It parses the Nadathur & Hotchkiss (2014) SDSS DR7 void-summary tables
to cross-check published Type1 counts and uses that count as the number of
independent synthetic profiles. The simulation does not consume catalog sky
positions, effective radii, survey-mask geometry, or member-galaxy positions.
The downloadable catalog has no per-void member-galaxy coordinates, so the
real stacking test remains blocked at the data layer.

The planted model is

    ln n(u) = ln n0 + c cos(2 pi log_phi(u)),       u = r / R,

sampled with independent Poisson shell counts. The null sets c=0 with the
same profile count, binning, and mean count. The resulting power curve tests
this detector under that toy model only.

DECISION TREE
-------------
Candidate ridges are maxima of contiguous bins whose stacked density exceeds
the per-bin null median by at least two robust null sigmas, restricted to
0.2 < r/R <= 1.0. At least three ridges are required. With ascending radii,
the two outer-normalized successive ratios are compared against:

  * SUPPORTS: both in [0.538, 0.698] and outside [0.736, 0.836];
  * SUPPORTS NULL: both in [0.736, 0.836] and outside [0.538, 0.698];
  * INDETERMINATE: otherwise;
  * NO RIDGES: fewer than three significant ridges.

Every simulated outcome is retained. None is observational evidence for or
against Prediction 51.
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
# c/H0 = 299792.458 / 67.36 = 4450.7 Mpc. The DR7 Reff is in h^-1 Mpc;
# divide by h to convert it to physical Mpc so radii and distances share one system.
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
                    "z": float(r["z"]), "Reff": float(r["Reff"]) / H100,
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
# Synthetic catalog-sized count profiles. Only n_profiles enters: catalog
# centers, radii, and footprint are deliberately not used.
# ---------------------------------------------------------------------------
def simulate_count_stack(n_profiles, rng, bins, contrast=0.0,
                         n_mean=50000.0, ladder=True, seed=None):
    """Simulate and stack independent radial count profiles.

    The planted log-density modulation is
    exp(c*cos(2*pi*log_phi(u))); the null uses unity. ``n_mean`` is the mean
    count per profile over the simulated sphere.
    """
    if seed is not None:
        rng = np.random.default_rng(seed)
    nbin = len(bins) - 1
    vol = (4.0 / 3.0) * np.pi * (bins[1:] ** 3 - bins[:-1] ** 3)
    if n_profiles <= 0:
        return (bins[:-1] + bins[1:]) / 2.0, np.zeros(nbin), 0
    frac_per_profile = vol / vol.sum()
    lam = n_profiles * n_mean * frac_per_profile
    u_center = (bins[:-1] + bins[1:]) / 2.0
    if ladder:
        mod = np.exp(
            contrast * np.cos(2 * np.pi * np.log(u_center) / LN_PHI)
        )
        mod /= np.sum(frac_per_profile * mod)
        lam = lam * mod
    counts = rng.poisson(lam)
    dens = counts / vol / n_profiles
    return u_center, dens, n_profiles


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




def null_stacks(n_profiles, bins, nreal, n_mean, seed0):
    """Uniform synthetic nulls with the same profile count and binning."""
    null_all = np.zeros((nreal, len(bins) - 1))
    for k in range(nreal):
        rng = np.random.default_rng(seed0 + 1000 + k)
        _, nd, _ = simulate_count_stack(
            n_profiles, rng, bins, contrast=0.0, n_mean=n_mean, ladder=False
        )
        null_all[k] = nd
    null_med = np.median(null_all, axis=0)
    null_sig = np.array([
        robust_sigma(null_all[:, i]) for i in range(null_all.shape[1])
    ])
    null_lo = np.percentile(null_all, 16, axis=0)
    null_hi = np.percentile(null_all, 84, axis=0)
    return null_all, null_med, null_sig, null_lo, null_hi


# ---------------------------------------------------------------------------
# Detection power
# ---------------------------------------------------------------------------
def run_one(n_profiles, bins, seed, contrast, n_mean, nnull=16):
    rng = np.random.default_rng(seed)
    r_c, dens, nv = simulate_count_stack(
        n_profiles, rng, bins, contrast=contrast, n_mean=n_mean, ladder=True
    )
    _, null_med, null_sig, null_lo, null_hi = null_stacks(
        n_profiles, bins, nnull, n_mean, seed
    )
    radii, qs = ridge_analysis(r_c, dens, null_med, null_sig)
    verdict = decide(qs)
    return {
        "seed": seed, "contrast": contrast, "n_profiles": nv,
        "r_c": r_c.tolist(), "dens": dens.tolist(),
        "null_med": null_med.tolist(), "null_lo": null_lo.tolist(),
        "null_hi": null_hi.tolist(), "null_sig": null_sig.tolist(),
        "sig_ridge_radii": radii, "successive_ratios": qs,
        "verdict": verdict,
    }


def detection_power(n_profiles, bins, contrasts, nreal, n_mean, seed0):
    power = {}
    for c in contrasts:
        succ = 0
        for k in range(nreal):
            r = run_one(n_profiles, bins, seed0 + 7 * k, c, n_mean)
            if r["verdict"] == "SUPPORTS":
                succ += 1
        power[f"{c:.3f}"] = {
            "n_realizations": nreal,
            "n_supports": succ,
            "power": succ / nreal,
        }
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
        raise RuntimeError(
            "Catalog integrity check failed; synthetic calibration requires "
            "the complete 808-entry Type1 count receipt")

    bins = np.linspace(0.12, 3.0, 29)  # r/R in (0.12, 3.0), ~0.1-R bins
    r_c = (bins[:-1] + bins[1:]) / 2.0
    # This count scale belongs only to the synthetic Poisson model.
    N_MEAN = 50000.0

    # Catalog count sizes the simulation; no center or radius enters it.
    n_profiles = len(voids)
    print("\n  SYNTHETIC FIDUCIAL: 1% log-density ladder contrast")
    print(f"    independent synthetic profiles: {n_profiles}")
    res = run_one(n_profiles, bins, 20260813, 0.01, N_MEAN)
    print(f"    significant ridge radii (r/R): "
          f"{[round(x,3) for x in res['sig_ridge_radii']]}")
    print(f"    successive ratios: {[round(q,3) for q in res['successive_ratios']]}"
          f"  (signal 0.618, null 0.786)")
    print(f"    verdict: {res['verdict']}")

    print("\n  SYNTHETIC DETECTION-POWER CALIBRATION")
    contrasts = [0.003, 0.005, 0.01, 0.02, 0.05]
    power = detection_power(n_profiles, bins, contrasts, nreal=8,
                            n_mean=N_MEAN, seed0=20260813)
    for c, p in power.items():
        flag = "high toy power" if p["power"] >= 0.95 else (
            "moderate toy power" if p["power"] >= 0.68 else (
                "low toy power" if p["power"] >= 0.30 else "minimal toy power"))
        print(f"    contrast {c:>5}: power = {p['power']:.2f} "
              f"({p['n_supports']}/{p['n_realizations']})  {flag}")

    # Maxima ratios under the same catalog-sized toy with no planted ladder.
    # No survey mask or random sky center enters this synthetic null.
    print("\n  SYNTHETIC NULL MAXIMA-RATIO DISTRIBUTION (no ladder)")
    null_ratios = []
    null_nridge = []
    for k in range(40):
        rng = np.random.default_rng(5000 + k)
        _, nd, _ = simulate_count_stack(
            n_profiles, rng, bins, contrast=0.0, n_mean=N_MEAN, ladder=False
        )
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
        "scope": "synthetic catalog-sized count-profile calibration",
        "catalog_count_source": (
            "J/MNRAS/440/1248 (Nadathur & Hotchkiss 2014, DR7)"
        ),
        "catalog_fields_consumed_by_simulation": ["Type1 count"],
        "vtypes": "Type1",
        "n_profiles": n_profiles,
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
