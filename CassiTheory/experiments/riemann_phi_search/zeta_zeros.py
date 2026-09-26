#!/usr/bin/env python3
"""Shared loader for Odlyzko's first 100,000 Riemann zeta zeros.

Data: A. Odlyzko's table (imaginary parts of the nontrivial zeros, one per
line), cached at runs/odlyzko_zeros1.txt (gitignored). The table is ~1.8 MB;
re-downloaded only if the cache is missing or fails sanity checks.
"""

import os
import ssl
import urllib.request

import numpy as np

PHI = (1 + np.sqrt(5)) / 2
LN_PHI = np.log(PHI)
W0 = 2 * np.pi / LN_PHI          # Cassi fixed log-frequency, ~13.057
ZEROS_URL = "http://www.dtc.umn.edu/~odlyzko/zeta_tables/zeros1"
CACHE = "runs/odlyzko_zeros1.txt"
EXPECTED = 100_000
FIRST = 14.134725142              # gamma_1 (sanity anchor)


def load_zeros():
    if not (os.path.exists(CACHE) and os.path.getsize(CACHE) > 1_700_000):
        os.makedirs("runs", exist_ok=True)
        try:
            req = urllib.request.Request(ZEROS_URL, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
        except Exception:
            # Windows cert-store fallback (documented machine issue)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(ZEROS_URL, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90, context=ctx).read()
        with open(CACHE, "wb") as f:
            f.write(data)
    g = np.array([float(x) for x in open(CACHE)], dtype=float)
    if len(g) != EXPECTED or abs(g[0] - FIRST) > 1e-6 or not np.all(np.diff(g) > 0):
        raise RuntimeError("zero table failed sanity checks; delete runs/ and retry")
    return g
