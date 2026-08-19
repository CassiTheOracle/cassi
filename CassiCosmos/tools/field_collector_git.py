#!/usr/bin/env python3
"""field_collector_git.py — Phase-1 minimal git-commits collector.

Digests ONE digital stream — git commits — and encodes each new commit as a
`decision`-type engram deposition per field_desktop_spec.md §1.4, mirroring
the landed collector pattern of tools/engine_cache_writer.py (self-contained,
argparse, BridgeClient over the 7599 line-JSON bridge, gate checks).

This is the Phase 1 artifact of §4.2, implementing (NOT re-specifying) the
pre-registration fixed in field_desktop_spec.md:
  - Prediction: a commit deposited at deterministic cell (x,y,z) from its
    content hash is a *precondition* for the field-as-memory claim, not the
    claim; the measurable target is the §19 Stage-4 statistic z > 2 in
    >= 2/3 weekly sessions (K >= 3), with the epoch-to-cell JSONL journal as
    the immutable pairing record.
  - Decision tree: ADOPT placement (z > 2 in >= 2/3), NULL placement
    (z <= 2 in >= 2/3), INCONCLUSIVE (journal missing/corrupt, or engine
    down > 50% of a session). The verdict is "is the deterministic placement
    spatially retrievable in the field" — NOT "memory is a galaxy."
  - Discipline: passive ingestion (G34 — never per-step pointwise injection,
    no read-then-inject steering loop); pre-registration before any run.

Deposit encoding (spec §1.4, git-commit row) — deterministic forever:
  - nodeType     = "decision" (existing)
  - charge (cy,ci) = TYPE_CHARGE.decision [1.618, 0.618] * power 0.8
                     = [1.2944, 0.4944]  (field-encoder/index.ts lines 26,82)
  - sigma        = 2.0  (existing decision envelope)
  - r            = commit durability weight (SemVer-ish: root commits inner,
                   chore commits outer) -> a fixed radial shell band
  - theta        = hash(branch)  -> [0, 2pi)
  - z            = hash(message) -> [-1, 1]
  - (x,y,z)      = (r*cos theta, r*sin theta, z) in [-1,1]^3  (spec §1.2)

The same commit MUST yield the same (x,y,z,cy,ci,sigma) forever — every
hash/classifier is pure-SHA-256 structural, no randomness, no system state.

Read-only over git (git log / git show); never mutates the repo. Deposits to
the engine ONLY with --live; the DEFAULT --dry-run is encode + journal only
(no engine, no network, no deposit). --live is implemented but NOT executed
here (see acceptance: no live deposits performed).

Gates (mirroring the writer's gate culture):
  G1 journal integrity: re-encoding the same commit yields an identical
     journal row (tested twice).
  G2 position bounds:   x,y,z in [-1,1]^3 and r in [0,1).
  G3 charge sanity:     (cy,ci) == the decision charge table [1.2944, 0.4944].
  --self-test runs all gates offline (no engine, no network).

Usage:
  python tools/field_collector_git.py --self-test
  python tools/field_collector_git.py --dry-run --limit 20 \
      --journal .tmp_field_collector/scratch_journal.jsonl
  python tools/field_collector_git.py --live --journal ...   # NOT used here
"""

import argparse
import hashlib
import json
import math
import os
import socket
import subprocess
import sys
from pathlib import Path

# ── spec-grounded constants ---------------------------------------------
PHI = 1.618033988749895
TYPE_CHARGE_DECISION = (PHI, 0.618033988749895)   # [cy, ci] base (field-encoder)
DECISION_POWER = 0.8                               # powerFor("decision")
DECISION_SIGMA = 2.0                               # existing decision envelope
# Charge scaled by power: (1.618*0.8, 0.618*0.8) = (1.2944, 0.4944)
CHARGE_CY = TYPE_CHARGE_DECISION[0] * DECISION_POWER
CHARGE_CI = TYPE_CHARGE_DECISION[1] * DECISION_POWER

# Radial durability weight (SemVer-ish): root/init commits inner (Shell 0),
# chore commits outer (Shell 3). Fixed mapping keyed on the conventional-
# commit type token; pure content-derivable, deterministic forever.
# Shell bands (spatial-index.ts): 0 r<0.1, 1 r<0.3, 2 r<0.6, 3 r>=0.6.
TYPE_R = {
    "init": 0.05,      # Shell 0 — foundational, innermost
    "root": 0.05,      # Shell 0
    "import": 0.08,    # Shell 0 — history import (root-ish)
    "feat": 0.25,      # Shell 1 — constructive (SemVer MINOR)
    "breaking": 0.15,  # Shell 1 inner — SemVer MAJOR
    "refactor": 0.35,  # Shell 2
    "perf": 0.50,      # Shell 2
    "fix": 0.45,       # Shell 2 (SemVer PATCH)
    "revert": 0.48,    # Shell 2
    "test": 0.55,      # Shell 2 outer
    "docs": 0.70,      # Shell 3 — documentation, outer
    "build": 0.75,     # Shell 3
    "style": 0.78,     # Shell 3
    "ci": 0.80,        # Shell 3
    "chore": 0.85,     # Shell 3 — outermost, least durable
    "merge": 0.40,     # Shell 2
    "default": 0.60,   # unclassified → Shell 3 boundary
}
R_MAX = 1.0  # exclusive upper bound; r in [0, 1)


# ── deterministic encoding ----------------------------------------------
def _sha_uniform(seed: str) -> float:
    """Deterministic 64-bit uniform in [0, 1) from SHA-256(seed). Pure."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def durability_r(subject: str) -> float:
    """r in [0,1): commit's durable weight by conventional-commit type.

    The message's leading word is the type token (`feat`, `fix(p7)`, ...);
    strip any scope suffix before `(`. Deterministic: identical subject →
    identical r.
    """
    first = subject.strip().lower()
    if not first:
        return TYPE_R["default"]
    if first.startswith("merge") or first.startswith("import"):
        return TYPE_R["merge"]
    token = first.split(":", 1)[0].split("(", 1)[0].strip()
    return TYPE_R.get(token, TYPE_R["default"])


def hash_theta(branch: str) -> float:
    """theta in [0, 2pi): hash(branch). Deterministic."""
    return 2.0 * 3.141592653589793 * _sha_uniform("branch:" + branch)


def hash_z(message: str) -> float:
    """z in [-1, 1]: hash(message). Deterministic; spreads across [-1,1]
    smoothly (spec §1.3 — the phiFromZ pole-compression expects this)."""
    return 2.0 * _sha_uniform("msg:" + message) - 1.0


def encode_commit(commit_id: str, timestamp: str, branch: str,
                  message: str, subject: str, salience: int) -> dict:
    """Deterministic spec §1.4 encoding of one commit → journal row.

    Returns the full immutable pairing record. The same inputs always
    produce the byte-identical row (G1). Never touches the engine.
    """
    r = durability_r(subject)
    theta = hash_theta(branch)
    z = hash_z(message)
    x = r * math.cos(theta)
    y = r * math.sin(theta)
    return {
        "commit_id": commit_id,
        "timestamp": timestamp,
        "branch": branch,
        "r": r, "theta": theta, "z": z,
        "x": x, "y": y,
        "cy": CHARGE_CY, "ci": CHARGE_CI, "sigma": DECISION_SIGMA,
        "salience": salience,
        "message": message,
    }


def journal_row(enc: dict) -> str:
    """Stable JSONL row string for the epoch-to-cell journal."""
    return json.dumps(enc, ensure_ascii=False)


# ── git read (read-only, never mutates) ----------------------------------
def _git(repo: str, args: list) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout


def resolve_branch(repo: str, commit_id: str) -> str:
    """Deterministic branch for a commit: containing refs sorted, else HEAD."""
    try:
        refs = _git(repo, ["for-each-ref", "--contains", commit_id,
                           "--format=%(refname:short)"]).splitlines()
        if refs:
            return sorted(r for r in refs if r)[0]
    except subprocess.CalledProcessError:
        pass
    try:
        head = _git(repo, ["symbolic-ref", "--short", "HEAD"]).strip()
        if head:
            return head
    except subprocess.CalledProcessError:
        pass
    return "HEAD"


def collect_commits(repo: str, limit: int) -> list[dict]:
    """Poll git log (newest-first) for up to `limit` commits and encode each.

    Returns journal rows INCREASING by time (oldest→newest) so a journal is
    an ordered epoch ledger. Read-only over git.
    """
    lines = _git(repo, [
        "log", "-n", str(limit),
        "--format=%H%x1f%aI%x1f%s%x1f%B%x1e", "HEAD",
    ]).split("\x1e")
    commits = []
    for entry in lines:
        entry = entry.strip()
        if not entry:
            continue
        commit_id, timestamp, subject, message = entry.split("\x1f", 3)
        commit_id = commit_id.strip()
        timestamp = timestamp.strip()
        message = message.rstrip("\n").strip()
        branch = resolve_branch(repo, commit_id)
        salience = commit_delta(repo, commit_id)
        commits.append({
            "commit_id": commit_id, "branch": branch, "subject": subject,
            "message": message, "salience": salience, "timestamp": timestamp,
        })
    commits.reverse()  # oldest → newest
    return commits


def commit_delta(repo: str, commit_id: str) -> int:
    """Lines changed (added+deleted) for a commit — the salience, clamped."""
    try:
        out = _git(repo, [
            "show", "--numstat", "--format=", commit_id,
        ])
    except subprocess.CalledProcessError:
        return 1
    added = deleted = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] != "-" and parts[1] != "-":
            try:
                added += int(parts[0])
                deleted += int(parts[1])
            except ValueError:
                pass
    # clamp salience to keep it a bounded, deterministic brightness
    return max(1, min(10000, added + deleted))


# ── bridge (deposit path; used ONLY with --live) -------------------------
class BridgeClient:
    """Minimal line-delimited JSON client for the 7599 mind-engine bridge."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7599,
                 timeout: float = 10.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._rf = self._sock.makefile("rb")

    def request(self, obj: dict) -> dict:
        self._sock.sendall(json.dumps(obj).encode() + b"\n")
        resp = self._rf.readline()
        if not resp:
            raise ConnectionError("engine closed the connection")
        return json.loads(resp.decode())

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def deposit_rows(client: BridgeClient, rows: list[dict]) -> None:
    """Fire-and-forget deposits (shadow-bridge semantics, spec §2.2).

    Deposit failures degrade to bounded warnings; never crash the collector.
    """
    for row in rows:
        try:
            client.request({
                "cmd": "deposit",
                "x": row["x"], "y": row["y"], "z": row["z"],
                "cy": row["cy"], "ci": row["ci"], "sigma": row["sigma"],
            })
        except (OSError, ConnectionError, ValueError) as e:
            print(f"[collector] WARN deposit {row['commit_id']} dropped: {e}",
                  file=sys.stderr)


# ── gates ----------------------------------------------------------------
def gate_g1(rows: list[dict]) -> None:
    """Journal integrity: same commit re-encoded → identical journal row."""
    assert rows, "G1: no rows to check"
    for r in rows:
        subj = r["message"].split("\n", 1)[0].strip()
        re1 = encode_commit(r["commit_id"], r["timestamp"], r["branch"],
                            r["message"], subj, r["salience"])
        re2 = encode_commit(r["commit_id"], r["timestamp"], r["branch"],
                            r["message"], subj, r["salience"])
        assert journal_row(re1) == journal_row(r), f"G1: row drift {r['commit_id']}"
        assert journal_row(re2) == journal_row(r), f"G1: row drift 2nd pass {r['commit_id']}"
    print(f"[gate] G1 PASS: {len(rows)} rows re-encode identically (tested twice)")


def gate_g2(rows: list[dict]) -> None:
    """Position bounds: x,y,z in [-1,1]^3; r in [0,1)."""
    for r in rows:
        for ax, v in (("x", r["x"]), ("y", r["y"]), ("z", r["z"])):
            assert -1.0 <= v <= 1.0, f"G2: {ax}={v} out of [-1,1] {r['commit_id']}"
        assert 0.0 <= r["r"] < R_MAX, f"G2: r={r['r']} out of [0,1) {r['commit_id']}"
    print(f"[gate] G2 PASS: {len(rows)} rows have (x,y,z) in [-1,1]^3, r in [0,1)")


def gate_g3(rows: list[dict]) -> None:
    """Charge sanity: (cy,ci) matches the decision charge table."""
    for r in rows:
        assert abs(r["cy"] - CHARGE_CY) < 1e-12, \
            f"G3: cy={r['cy']} != {CHARGE_CY} {r['commit_id']}"
        assert abs(r["ci"] - CHARGE_CI) < 1e-12, \
            f"G3: ci={r['ci']} != {CHARGE_CI} {r['commit_id']}"
        assert r["sigma"] == DECISION_SIGMA, \
            f"G3: sigma={r['sigma']} != {DECISION_SIGMA} {r['commit_id']}"
    print(f"[gate] G3 PASS: {len(rows)} rows match decision charge "
          f"[{CHARGE_CY:.4f}, {CHARGE_CI:.4f}] sigma {DECISION_SIGMA}")


def self_test() -> int:
    """Offline (no engine, no network) run of all gates on synthetic rows.

    Builds rows from a small fixed corpus of real commit subjects seeded
    from this repo + a synthetic set, so every gate exercises the full
    deterministic encode path without touching git or the bridge.
    """
    corpus = [
        ("0000aaa1", "2026-08-14T20:56:54-07:00", "master",
         "feat(p7): add spine server", "feat(p7): add spine server", 120),
        ("0000aaa2", "2026-08-14T20:56:47-07:00", "master",
         "chore: bump workspace refs", "chore: bump workspace refs", 3),
        ("0000aaa3", "2026-08-14T18:51:34-07:00", "feature/phi",
         "fix(engine): repair scatter renorm",
         "fix(engine): repair scatter renorm", 47),
        ("0000aaa4", "2026-08-14T18:00:00-07:00", "master",
         "Merge branch 'x' into master", "Merge branch 'x' into master", 900),
    ]
    rows = [
        encode_commit(cid, ts, br, msg, subj, sal)
        for cid, ts, br, msg, subj, sal in corpus
    ]
    gate_g1(rows)
    gate_g2(rows)
    gate_g3(rows)
    # duplicate-subject determinism: identical message/branch → same theta/z
    a = encode_commit("x", "t", "master", "same msg", "same", 1)
    b = encode_commit("y", "t2", "master", "same msg", "same", 1)
    assert a["theta"] == b["theta"] and a["z"] == b["z"], "hash non-determinism"
    print("[self-test] PASS: all gates green offline (no engine, no network)")
    return 0


# ── main -----------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(
        description="Phase-1 git-commits collector — encodes commits to "
                    "decision deposits (spec §1.4) and journals the "
                    "epoch-to-cell pairing record.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--repo", default=r"C:/Users/Carina/workspaces/Cassi/CassiCore",
                   help="git repo to poll (read-only over git)")
    p.add_argument("--limit", type=int, default=20,
                   help="max commits to poll from git log (newest N)")
    p.add_argument("--journal", default=None,
                   help="epoch-to-cell JSONL journal path "
                        "(default: ./field_collector_{repo}.jsonl)")
    p.add_argument("--dry-run", action="store_true",
                   help="encode + journal only — no engine, no network, no deposit")
    p.add_argument("--live", action="store_true",
                   help="deposit to the engine via BridgeClient (127.0.0.1:7599); "
                        "requires the mind engine to be running.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7599)
    p.add_argument("--self-test", action="store_true",
                   help="offline run of all gates, no git/engine/network")
    args = p.parse_args()

    if args.self_test:
        return self_test()

    if not os.path.isdir(os.path.join(args.repo, ".git")):
        print(f"[collector] ERROR: not a git repo: {args.repo}", file=sys.stderr)
        return 2

    journal_path = Path(args.journal or
                        f"field_collector_{Path(args.repo).name}.jsonl")

    # Poll git log (read-only) and encode per spec §1.4.
    commits = collect_commits(args.repo, args.limit)
    rows = [
        encode_commit(c["commit_id"], c["timestamp"], c["branch"],
                      c["message"], c["subject"], c["salience"])
        for c in commits
    ]

    if not rows:
        print("[collector] no commits found")
        return 0

    # Gates are run before any journal write or deposit (pre-registration
    # control: journal integrity, bounds, charge — all must pass first).
    gate_g3(rows)   # charge sanity (cheap, no I/O)
    gate_g2(rows)   # position bounds
    gate_g1(rows)   # journal integrity (re-encode determinism)

    # epoch-to-cell journal: the immutable pairing record (§4.2).
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with open(journal_path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(journal_row(r) + "\n")
    print(f"[collector] journal: {len(rows)} rows -> {journal_path}")

    if args.live:
        # --live is implemented but NOT executed in this task ($19 discipline):
        # deposits require the mind engine on 127.0.0.1:7599 and would begin
        # §19 collection. We only reach here when the caller explicitly passes
        # --live (a real collection run is a separate, pre-registered event).
        client = BridgeClient(args.host, args.port)
        try:
            pong = client.request({"cmd": "ping"})
            if not pong.get("ok"):
                print(f"[collector] ERROR: engine ping failed: {pong}",
                      file=sys.stderr)
                return 1
            deposit_rows(client, rows)
            print(f"[collector] deposited {len(rows)} to {args.host}:{args.port}")
        finally:
            client.close()
    else:
        print("[collector] dry-run (no deposit; no engine; no network) — "
              "pass --live after idempotent journal confirmation")

    for r in rows[:3]:
        print(f"  sample  {r['commit_id'][:7]}  branch={r['branch']}  "
              f"pos=({r['x']:.4f}, {r['y']:.4f}, {r['z']:.4f})  "
              f"(r={r['r']:.2f})  q=({r['cy']:.4f},{r['ci']:.4f})  "
              f"sigma={r['sigma']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
