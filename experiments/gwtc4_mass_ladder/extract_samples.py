#!/usr/bin/env python3
"""Extract mass_1_source posterior samples from LVK PE release HDF5 files.

Covers the full GWTC-4.0 catalog (218 events):
- GWTC-4.0 O4a release (zenodo 17602505): `*-combined_PEDataRelease.hdf5`,
  samples under `C00:Mixed`.
- GWTC-2.1 v2 (zenodo 6513631): O1+O2+O3a re-analyses, `*_mixed_cosmo.h5`,
  samples under `C01:Mixed` (cosmo = standard cosmology distance prior).
- GWTC-3 (zenodo 8177023): O3b, `*_mixed_cosmo.h5`, samples under `C01:Mixed`.

For each event the equal-weight waveform-model mixture ("Mixed") is used, and
the source-frame primary mass `mass_1_source` is saved to a compact .npz.

Usage:
  python experiments/gwtc4_mass_ladder/extract_samples.py [data_dir]

Output: data/samples_m1.npz  {events: [...], m1: [array per event], n_samples: [...]}
"""

import os
import sys
import glob
import re

import h5py
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# group labels that hold the equal-weight mixture, newest first
MIXED_LABELS = ["C00:Mixed", "C01:Mixed", "C02:Mixed"]


def find_mixed(f):
    """First Mixed group present in the file."""
    for label in MIXED_LABELS:
        key = f"{label}/posterior_samples"
        if key in f:
            return key
    # fall back: any group whose path ends with Mixed/posterior_samples
    for path in f:
        if path.endswith(":Mixed/posterior_samples") or path.endswith(
                "/Mixed/posterior_samples"):
            return path
    return None


def main():
    ddir = sys.argv[1] if len(sys.argv) > 1 else DATA_DIR
    files = sorted(glob.glob(os.path.join(ddir, "done", "*.h5")))
    files += sorted(glob.glob(os.path.join(ddir, "old_gwtc3", "*")))
    files += sorted(glob.glob(os.path.join(ddir, "old_gwtc2p1", "*")))
    files = sorted(set(files))
    files = [p for p in files if os.path.isfile(p)]
    if not files:
        print("no PE release files found under", ddir)
        sys.exit(1)

    events, m1s, ns, seen = [], [], [], set()
    for path in files:
        name = os.path.basename(path)
        try:
            with h5py.File(path, "r") as f:
                key = find_mixed(f)
                if key is None:
                    print(f"  skip {name}: no Mixed posterior group "
                          f"({[str(k) for k in f.keys()][:5]})")
                    continue
                ps = f[key][:]
            m1 = np.asarray(ps["mass_1_source"], dtype=np.float64)
            m1 = m1[np.isfinite(m1)]
            if len(m1) == 0:
                print(f"  skip {name}: no finite mass_1_source")
                continue
        except (KeyError, OSError, ValueError) as exc:
            print(f"  skip {name}: {exc}")
            continue
        m = re.search(r"GW\d{6}_\d{6}", name)
        ev = m.group(0) if m else name.rsplit(".", 1)[0]
        if ev in seen:
            print(f"  skip {name}: duplicate event {ev}")
            continue
        seen.add(ev)
        events.append(ev)
        m1s.append(m1)
        ns.append(len(m1))
        print(f"  {ev}: {len(m1)} samples, median m1 = {np.median(m1):.2f} Msun")

    out = os.path.join(ddir, "samples_m1.npz")
    np.savez(out, events=np.array(events), m1=np.array(m1s, dtype=object),
             n_samples=np.array(ns))
    print(f"wrote {out}: {len(events)} events, {sum(ns)} samples total")


if __name__ == "__main__":
    main()
