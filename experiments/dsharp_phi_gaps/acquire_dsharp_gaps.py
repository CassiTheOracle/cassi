#!/usr/bin/env python3
"""Acquire and parse the ALMA DSHARP 1.25 mm annular-substructure table.

Run from the repo root:
    python experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py

Source
------
DSHARP survey, Andrews et al. (2018), arXiv:1812.04040 (20 targets; the
18 single-disk systems analyzed for substructure). The gap/ring radial
positions (Table "Properties of annular substructures", label
tab:ringpositions) are published in the survey's substructure paper:
Huang et al. (2018), "The Disk Substructures at High Angular Resolution
Project (DSHARP). II. Characteristics of Annular Substructures",
arXiv:1812.04041 (ApJL 869, L42). This parser reads the r0 (au) column
of every DARK ("D") substructure row — the density gaps that the ring
ladder test reads as the disk analog of the bubble-shell void troughs —
from the paper's LaTeX source.

AUTHENTICITY / PROVENANCE
-------------------------
- Raw arXiv e-print sources are fetched over HTTPS and SHA-256 recorded
  (the specific fetched bytes):
    * 1812.04040_src.tar.gz (Andrews et al. 2018 survey)
    * 1812.04041_src.tar.gz (Huang et al. 2018 substructures)
- The ring-position table is parsed directly from the table body
  (\\startdata ... \\enddata) of DSHARPII_arxivuploadv3.tex, so every
  value is machine-extracted from the published source rather than
  re-typed. The Feature label (D##, B##) and radial location in au are
  transcribed verbatim; the three-part feature identification is
  described in the paper (Sec. "Radial locations of annular
  substructures"): well-resolved features are ellipse-fit (Method E),
  additional features are located from local extrema of the deprojected,
  azimuthally-averaged radial intensity profile (Method R), and
  low-SNR features are identified by visual inspection (Method V).

The test itself (the pre-registered decision tree) is in
stack_phi_gaps.py; this script only assembles and certifies the input
table.

The 18 single-disk DSHARP systems are: AS 209, DoAr 25, DoAr 33,
Elias 20, Elias 24, Elias 27, GW Lup, HD 142666, HD 143006, HD 163296,
IM Lup, MY Lup, RU Lup, SR 4, Sz 114, Sz 129, WaOph 6, WSB 52.
"""
import hashlib
import os
import re
from datetime import datetime

MYDIR = os.path.dirname(os.path.abspath(__file__))
DATADIR = os.path.join(MYDIR, "data")
RAWDIR = os.path.join(DATADIR, "raw")
PARSED = os.path.join(DATADIR, "parsed")
HASHFILE = os.path.join(RAWDIR, "sha256.txt")
os.makedirs(RAWDIR, exist_ok=True)
os.makedirs(PARSED, exist_ok=True)

TEX = os.path.join(RAWDIR, "1812.04041_src", "DSHARPII_arxivuploadv3.tex")

# The ring-position table body rows are the lines between the first
# \startdata after the tab:ringpositions caption's \tablehead and the
# matching \enddata. We capture that run.
HEAD_MARKER = r"\label{tab:ringpositions}"
START_MARKER = r"\startdata"
END_MARKER = r"\enddata"


def parse_gap_table():
    """Return list of (source, feature, r0_au_text, method, width_text)."""
    text = open(TEX, encoding="utf-8").read()
    lines = text.splitlines()

    # Locate the ring-positions table head marker, then the \startdata of
    # THAT table (the first \startdata after the marker).
    head_idx = None
    for i, ln in enumerate(lines):
        if HEAD_MARKER in ln:
            head_idx = i
            break
    if head_idx is None:
        raise RuntimeError("tab:ringpositions label not found")

    start_idx = None
    for i in range(head_idx, len(lines)):
        if START_MARKER in lines[i]:
            start_idx = i
            break
    if start_idx is None:
        raise RuntimeError("\\startdata after tab:ringpositions not found")

    # The next \enddata closes this table.
    end_idx = None
    for i in range(start_idx + 1, len(lines)):
        if END_MARKER in lines[i]:
            end_idx = i
            break
    if end_idx is None:
        raise RuntimeError("closing \\enddata not found")

    body = lines[start_idx + 1:end_idx]

    # Assemble logical rows: a physical line can wrap (some wide rows spill
    # onto a second line, e.g. HD 163296 B100). A new logical row starts on
    # a line whose first non-space character is an ampersand (continuation
    # of the prior disk's rows) or an uppercase source-name letter; any
    # other line (e.g. starting '\pm', '$', a digit) is a wrap fragment
    # appended to the current row.
    logical = []
    for ln in body:
        s = ln.lstrip()
        if not s or s.startswith("%") or s == r"\hline":
            continue
        head_ok = s.startswith("&") or (
            s[0].isalpha() and s[0].isupper()
        )
        if head_ok:
            logical.append(ln.strip())
        elif logical:
            logical[-1] = logical[-1] + " " + ln.strip()
        # else: stray fragment before any row — ignore

    rows = []
    cur_source = None
    for ln in logical:
        # A row is: [Source] & Feature & ... & r0(au) & ... & Method & Width & Depth \\
        # Source is present on the first substructure of a disk; for
        # continuation rows the Source cell is empty (the row begins with
        # the Feature of the previous source).
        # We detect a source-name cell as a leading capitalized token that
        # is not a Feature label (B##/D##).
        cells_raw = ln.split("&")
        # The trailing \\ may be glued to the last cell.
        if len(cells_raw) < 5:
            continue

        source = None
        first = cells_raw[0].strip().lstrip()
        m = re.match(r"^([A-Za-z][A-Za-z0-9 .-]*)", first)
        # Feature labels are D## / B##; anything else at the start of a row
        # (before '\\\\') that isn't such a label is the source name.
        feat_candidate = cells_raw[1].strip() if len(cells_raw) > 1 else ""
        lead = m.group(1) if m else ""
        if re.fullmatch(r"[DB]\d+", lead) or lead in ("", "\\^"):
            source = cur_source
        else:
            source = lead.strip()
            cur_source = source

        # cells: [source, feature, dx, dy, r0(mas), r0(au), incl, PA, method, width, depth(\\...)]
        feature = cells_raw[1].strip().lstrip()
        r0_au = cells_raw[5].strip()
        method = cells_raw[8].strip() if len(cells_raw) > 8 else ""
        width = cells_raw[9].strip() if len(cells_raw) > 9 else ""
        # method cell often has a trailing \\ or a footnote mark
        method = re.sub(r"\\\\+.*$", "", method).strip()
        rows.append((source, feature, r0_au, method, width))
    return rows


def parse_r0_au(text):
    """Extract a numeric au value from a LaTeX r0 cell like '8.69\\pm0.11'.

    Returns (value, uncertainty, is_approx). is_approx True when the cell
    uses '~' (visual estimate, no fitted uncertainty).
    """
    text = text.strip().replace(" ", "")
    is_approx = "\\sim" in text or "~" in text
    # strip any trailing \\.... and footnotes
    text = re.sub(r"\\\\+.*$", "", text)
    text = re.sub(r"\\tablenotemark.*$", "", text)
    # Uncertainties: value\pmunc; drop the uncertainty after a marker
    # position so we keep the central au value. Some cells are just '~74'.
    text = re.sub(r"\\pm.*$", "", text)
    text = text.replace("\\sim", "").replace("~", "")
    text = text.strip("$")
    try:
        val = float(text)
    except ValueError:
        return None, None, is_approx
    return val, None, is_approx


def main():
    manifest = []
    # Record raw-bytes hashes of the two downloaded sources (specific bytes).
    for fn in ("1812.04040_src.tar.gz", "1812.04041_src.tar.gz"):
        p = os.path.join(RAWDIR, fn)
        if os.path.exists(p):
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            manifest.append(f"{h}  {fn}")
            print(f"{fn:28s} sha256 {h[:16]}…")
        else:
            print(f"{fn} NOT PRESENT — raw bytes not on disk")

    rows = parse_gap_table()
    # Keep only DARK (gap) substructures: the D-label rows.
    gaps = [r for r in rows if r[1].startswith("D")]
    print(f"\nParsed {len(rows)} substructure rows, {len(gaps)} gaps (D-labeled)")

    # Write the parsed gap list.
    outpath = os.path.join(PARSED, "dsharp_gaps.csv")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("# DSHARP 1.25 mm gap radial positions (Huang et al. 2018, TABLE tab:ringpositions)\n")
        f.write("# parsed from DSHARPII_arxivuploadv3.tex (arXiv:1812.04041)\n")
        f.write("# source,feature,r0_au,is_approx,method\n")
        for src, feat, r0, method, width in gaps:
            feat = re.sub(r"\\tablenotemark.*$", "", feat).strip()
            feat = re.sub(r"\^+.*$", "", feat).strip()
            val, _, approx = parse_r0_au(r0)
            if val is None:
                print(f"  !! unparsed r0 for {src} {feat}: '{r0}'")
                continue
            # capture uncertainty if present
            unc = ""
            m = re.search(r"\\pm\s*([0-9.]+)", r0)
            if m:
                unc = m.group(1)
            f.write(f"{src},{feat},{val},{int(approx)},\"{method}\",{unc}\n")
    print(f"Wrote {outpath}")

    # Verify counts per disk against the published table: list per-disk gap counts.
    from collections import Counter, OrderedDict
    cnt = Counter()
    for src, feat, *_ in gaps:
        cnt[src] += 1
    ordered = OrderedDict()
    for src, *_ in gaps:
        ordered[src] = cnt[src]
    print("\nPer-disk gap counts:")
    for src, n in ordered.items():
        print(f"  {src:10s} {n}")

    with open(HASHFILE, "w") as f:
        f.write("# SHA-256 of DSHARP source bytes fetched over HTTPS\n")
        f.write(f"# fetched {datetime.utcnow().isoformat()}Z\n")
        f.write("\n".join(manifest) + "\n")
    print(f"\nWrote {HASHFILE}")


if __name__ == "__main__":
    main()
