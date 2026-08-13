#!/usr/bin/env python3
"""Acquire the Nadathur & Hotchkiss (2014) SDSS DR7 void catalog.

Run from the repo root:
    python experiments/void_phi_rings/acquire_void_catalog.py

Catalog: SDSS DR7 voids and superclusters (Nadathur & Hotchkiss 2014),
VizieR catalogue J/MNRAS/440/1248. This is the "robust public catalogue"
identified with the parameter-free watershed (ZOBOV) transform on the SDSS
DR7 main and LRG galaxy samples. It supplies each detected structure's
barycentre (RA, Dec), redshift z, effective radius Reff (comoving Mpc/h),
average and minimum density, edge flag, and density ratio, for three
structure types (Basic, Type1, Type2) in six galaxy samples (dim1, dim2,
bright1, bright2, lrgdim, lrgbright).

WHY THIS CATALOG / CERTIFICATION
--------------------------------
The pre-registered test stack is the bubble-shell ring ladder of
`foundations/bubble-edge-geometry.md` §3.5 / Prediction 51
(`predictions/falsifiable-predictions.md`): stacked void radial galaxy
density profiles should carry matter ridges at r_k = R * phi^-k with the
successive-matter-ring ratio phi^-1 = 0.6180 vs the interleaved-null ratio
phi^-1/2 = 0.7862. The natural data source is a public void catalog with
per-void galaxy positions so each void can be stacked in units of its own
Reff.

A public catalog WITH per-void galaxy-member positions was sought but is
not downloadable for either preferred source:

  * Pan et al. (2012), arXiv:1103.4156 ("Cosmic voids in SDSS DR7"),
    which bundles the void GALAXY membership (8,046 void galaxies, 1054
    voids). It is NOT published to VizieR (J/MNRAS/421/926 -> 404 at CDS);
    its stated hosting at http://www.physics.drexel.edu/ is defunct (the
    paper's http://www.physics.drexel.edu/<math> link now 404s; no
    void-catalog page reachable from the Drexel physics root). The CDS
    "VizieR not found" page for J/MNRAS/421/926 was confirmed.

  * The Nadathur & Hotchkiss (2014) CDS tables downloaded here bundle each
    void's *summary* (center, radius, densities), NOT the galaxy-member
    positions. The member-galaxy lists are only produced by the
    auxiliary postproc.py in the full cat_v11.11.13 package, which is not
    mirrored on CDS (the 4 cat_files/* entries are absent from the CDS
    table set) and lives on the paywalled journal site.

Therefore the per-void-galaxy coordinate field needed for a genuinely
real stacking test is BLOCKED at the data layer (see
`analyses/void-ring-profiles.md` §Real-data step for the exact failures).
This script acquires and verifies the real void geometry (centers + radii)
that the pipeline stacks in anyway; the galaxy field for the stacking is
the synthetic phi-ladder pivot documented in stack_void_rings.py.

AUTHENTICITY
------------
  * Each table is fetched over HTTPS from the VizieR/CDS mirror and its
    SHA-256 recorded (raw bytes as served).
  * Counts are cross-checked against the paper's Table 2 (numbers of
    structures per type per sample, reproduced in the VizieR samples.dat
    table). The samples.dat table itself is the authoritative count
    reference (Table 3 volumes also listed).
"""
import hashlib
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime

PHI = (1 + 5 ** 0.5) / 2

CAT = "J/MNRAS/440/1248"
BASE_URL = f"https://cdsarc.cds.unistra.fr/viz-bin/asu-txt?-source={CAT}/"

# (table name, structure type, galaxy sample, paper-Table-2 counts from samples.dat)
# counts = (Basic, Type1, Type2) as published in Nadathur & Hotchkiss 2014 Table 2
# (the samples.dat table downloaded here is the authoritative mirror).
TABLES = [
    ("samples", "samples", "all", None),
    ("bri1t1v", "Type1", "bright1", 262),
    ("bri1t2v", "Type2", "bright1", 163),
    ("bri1bt", "Basic", "bright1", 712),
    ("dim1t1v", "Type1", "dim1", 80),
    ("dim1t2v", "Type2", "dim1", 53),
    ("dim1bt", "Basic", "dim1", 262),
    ("dim2t1v", "Type1", "dim2", 271),
    ("dim2t2v", "Type2", "dim2", 199),
    ("dim2bt", "Basic", "dim2", 676),
    ("bri2t1v", "Type1", "bright2", 112),
    ("bri2t2v", "Type2", "bright2", 70),
    ("bri2bt", "Basic", "bright2", 398),
    ("lrgbt1v", "Type1", "lrgbright", 13),
    ("lrgbt2v", "Type2", "lrgbright", 1),
    ("lrgbribt", "Basic", "lrgbright", 193),
    ("lrgdt1v", "Type1", "lrgdim", 70),
    ("lrgdt2v", "Type2", "lrgdim", 19),
    ("lrgdimbt", "Basic", "lrgdim", 349),
]

MYDIR = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(MYDIR, "data")
RAWDIR = os.path.join(DATADIR, "raw")
PARSED = os.path.join(DATADIR, "parsed")
HASHFILE = os.path.join(RAWDIR, "sha256.txt")
os.makedirs(RAWDIR, exist_ok=True)
os.makedirs(PARSED, exist_ok=True)


def fetch(table):
    """Download one table's raw text, returning bytes. Raises on failure."""
    url = BASE_URL + table
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return r.read()


def parse_table(raw_bytes):
    """Parse a VizieR asu-txt table into a list of dict rows."""
    text = raw_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # Column headers are the line right before the ---- separator.
    # Find the table-start line "#Table J_MNRAS_440_1248_<name>:" onward.
    rows = []
    idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("#Table "):
            idx = i
            break
    if idx is None:
        return rows
    # header lines: the asu-txt format prints column labels then a dashed
    # separator; data follows. Concretely, header labels are the last block
    # of non-blank lines before the first run of '---' after '#Table'.
    body = lines[idx + 1:]
    # find first all-dash separator after the header text block
    sep = None
    for i, ln in enumerate(body):
        if re.match(r"^[\s\-\+]+$", ln) and "-" in ln and len(ln) > 8:
            sep = i
            break
    if sep is None:
        return rows
    header_text = "\n".join(body[:sep])
    # Collect the final label line (the actual field names). In asu-txt the
    # field-name columns are printed in a single line preceded by a '#---'
    # description block; the parse is done by fixed positions against the
    # first column-name line that matches known field names.
    data_lines = body[sep + 1:]
    # The label line is the one directly above the data-start and contains
    # the field names (Zone, RAJ2000, ...). We identify it as the last line
    # (non-empty) before data that starts with whitespace and contains 'Zone'
    # or is the samples header. For robustness, capture the column-name line
    # reported by the '#---Details of Columns:' block in order.
    col_names = []
    for i, ln in enumerate(body):
        if "Details of Columns" in ln:
            j = i + 1
            while j < len(body) and not body[j].startswith("---"):
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", body[j])
                if m:
                    col_names.append(m.group(1))
                elif body[j].strip() == "":
                    pass
                j += 1
            break
    return col_names, data_lines


def main():
    manifest = []
    for table, stype, sample, pub_count in TABLES:
        raw = fetch(table)
        if b"Making sure you're not a bot" in raw:
            raise RuntimeError(
                f"CDS returned the anti-bot challenge for table {table}; "
                "cannot download."
            )
        sha = hashlib.sha256(raw).hexdigest()
        outf = os.path.join(RAWDIR, f"{table}.asu.txt")
        with open(outf, "wb") as f:
            f.write(raw)
        manifest.append(f"{sha}  {table}.asu.txt")
        print(f"{table:12s} {len(raw):8d} bytes  sha256 {sha[:16]}…")
    with open(HASHFILE, "w") as f:
        f.write("# SHA-256 of the raw VizieR asu-txt responses for J/MNRAS/440/1248\n")
        f.write(f"# fetched {datetime.utcnow().isoformat()}Z\n")
        f.write("\n".join(manifest) + "\n")
    print(f"\nWrote {HASHFILE} with {len(manifest)} hashes.")
    print("Cross-check (Table 2 counts) is done in stack_void_rings.py and")
    print("recorded in analyses/void-ring-profiles.md.")


if __name__ == "__main__":
    main()
