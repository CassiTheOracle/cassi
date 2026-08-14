#!/usr/bin/env python3
"""Acquire the Kepler confirmed multi-planet catalog from the NASA Exoplanet
Archive and build the adjacent-period-ratio sample for the phi-spacing test.

Run from the repo root:
    python experiments/kepler_phi_ratios/acquire_kepler_catalog.py

WHAT THIS PROVIDES
------------------
The Cassi phi-spacing prediction (hypotheses/exoplanet-phi-spacing.md §3) says
the distribution of ADJACENT-planet PERIOD ratios P_out/P_in in the
Kepler/TESS multi-planet catalog is enhanced at phi (and its Fibonacci
convergents) and at the headline ratio phi^(3/2) = 2.058. This script pulls
the confirmed multi-planet systems and writes a parsed sample of adjacent
period ratios to data/parsed/kepler_ratios.csv. The statistical decision tree
that consumes this catalog is in run_phi_ratios.py (written before any run).

AUTHENTICITY / PROVENANCE
-------------------------
- Primary source: NASA Exoplanet Archive, exoplanetarchive.ipac.caltech.edu,
  Table Access Protocol (TAP) endpoint /TAP/sync. The `ps` (Planetary Systems)
  table carries one, confirmed default row per planet (default_flag=1) with
  the discovery/facility and orbital period.
- The query is issued over HTTPS; the raw returned CSV bytes are SHA-256
  recorded (the specific fetched bytes) in data/raw/sha256.txt.
- Confirmed planets are selected by the archive's own disposition
  (pl_pnum >= ... via counting confirmed rows per host) and discoverymethod.
- Sample filter (pre-registered): confirmed, transit-discovered planets in
  multi-planet systems -- a hostname must have >= 2 confirmed planets -- whose
  discovery facility is the Kepler space telescope (disc_facility
  CONTAINS 'Kepler', i.e. the original Kepler mission). Each host's planets
  are ordered by orbital period and the ADJACENT period ratios
  P_outer/P_inner are formed for every adjacent pair. This is the
  KEPLER-TRANSIT multi-planet sample.
- The K2 and TESS transit samples are pulled alongside (same query pattern)
  for a cross-check / detection-power note, but the primary headline sample
  is the Kepler one.

Only the scripts are tracked; the downloaded CSV and parsed ratios live in
data/ (gitignored). The decision tree is in run_phi_ratios.py.
"""
import hashlib
import io
import os
from datetime import datetime, timezone

import requests

BASE = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
MYDIR = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(MYDIR, "data")
RAWDIR = os.path.join(DATADIR, "raw")
PARSEDDIR = os.path.join(DATADIR, "parsed")
HASHFILE = os.path.join(RAWDIR, "sha256.txt")
os.makedirs(RAWDIR, exist_ok=True)
os.makedirs(PARSEDDIR, exist_ok=True)

# Columns we need from the ps table. pl_bmassprov distinguishes confirmed vs
# candidate in some legacy rows, but default_flag=1 already selects the best
# confirmed default row per planet.
COLUMNS = (
    "hostname,pl_name,pl_orbper,pl_orbpererr1,pl_orbpererr2,"
    "disc_facility,discoverymethod"
)

# Pre-registered samples: (tag, where-clause, description)
SAMPLES = [
    (
        "kepler",
        "disc_facility like '%Kepler%' and discoverymethod='Transit'",
        "Kepler confirmed transit multi-planet systems (primary)",
    ),
    (
        "k2_tess",
        "(disc_facility like '%K2%' or disc_facility like '%TESS%') "
        "and discoverymethod='Transit'",
        "K2/TESS confirmed transit multi-planet systems (cross-check)",
    ),
]


def fetch(tag, where):
    """Issue the TAP query over HTTPS; return raw bytes + decoded text."""
    query = (
        f"select {COLUMNS} from ps where default_flag=1 and {where} "
        f"order by hostname, pl_orbper"
    )
    r = requests.get(BASE, params={"query": query, "format": "csv"}, timeout=120)
    r.raise_for_status()
    raw = r.content
    return raw, r.text


def parse_rows(text):
    """Parse the CSV into a dict {host: [(pl_name, period), ...]} keeping only
    systems with >= 2 confirmed planets."""
    import csv

    hosts = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        host = row["hostname"].strip()
        try:
            per = float(row["pl_orbper"])
        except (TypeError, ValueError):
            continue
        if per <= 0:
            continue
        hosts.setdefault(host, []).append((row["pl_name"].strip(), per))
    # only multi-planet systems
    return {h: sorted(v, key=lambda x: x[1]) for h, v in hosts.items() if len(v) >= 2}


def adjacent_ratios(planets):
    """P_outer/P_inner for each adjacent pair ordered by period."""
    out = []
    for i in range(len(planets) - 1):
        p_in, p_out = planets[i][1], planets[i + 1][1]
        out.append((planets[i][0], planets[i + 1][0], p_in, p_out, p_out / p_in))
    return out


def main():
    manifest = []
    per_sample = {}
    for tag, where, desc in SAMPLES:
        raw, text = fetch(tag, where)
        h = hashlib.sha256(raw).hexdigest()
        manifest.append(f"{h}  {tag}_ps.csv")
        print(f"{tag:12s} sha256 {h[:16]}…  bytes={len(raw)}")

        rawname = os.path.join(RAWDIR, f"{tag}_ps.csv")
        with open(rawname, "wb") as f:
            f.write(raw)

        hosts = parse_rows(text)
        n_sys = len(hosts)
        n_planets = sum(len(v) for v in hosts.values())
        tot_ratios = sum(len(v) - 1 for v in hosts.values())
        per_sample[tag] = {
            "systems": n_sys, "planets": n_planets, "adjacent_ratios": tot_ratios,
        }
        print(
            f"  {tag}: {n_sys} multi-planet systems, {n_planets} planets, "
            f"{tot_ratios} adjacent period ratios"
        )

        # write parsed ratios
        outpath = os.path.join(PARSEDDIR, f"{tag}_ratios.csv")
        with open(outpath, "w", encoding="utf-8") as f:
            f.write("# Adjacent-planet period ratios P_outer/P_inner (NASA Exoplanet ")
            f.write("Archive ps, default_flag=1)\n")
            f.write("# host,pl_in,pl_out,period_in_d,period_out_d,ratio\n")
            for host in sorted(hosts):
                for pin, pout, p_in_d, p_out_d, ratio in adjacent_ratios(hosts[host]):
                    f.write(
                        f"{host},{pin},{pout},{p_in_d:.6f},{p_out_d:.6f},{ratio:.6f}\n"
                    )
        print(f"  wrote {outpath}")

    with open(HASHFILE, "w", encoding="utf-8") as f:
        f.write("# SHA-256 of NASA Exoplanet Archive ps TAP CSV bytes ")
        f.write(f"(fetched {datetime.now(timezone.utc).isoformat()}Z)\n")
        f.write("# endpoint https://exoplanetarchive.ipac.caltech.edu/TAP/sync\n")
        f.write("\n".join(manifest) + "\n")
    print(f"\nWrote {HASHFILE}")
    print("Sample summary:")
    for tag, d in per_sample.items():
        print(f"  {tag}: {d}")


if __name__ == "__main__":
    main()
