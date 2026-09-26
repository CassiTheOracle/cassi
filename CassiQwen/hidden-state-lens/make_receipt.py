"""Build RECEIPT.json: what was read, what was produced, and what the reading rests on.

The receipt is generated, never hand-written.  Its own content digest is stable across
runs: the clock, the host, and everything derived from them are declared in `strip` and
excluded from the digested body, so two runs of this script on the same inputs produce
the same `content_digest`.

Usage:
    python make_receipt.py [--skip-captures]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lens_common import WORKSPACE  # noqa: E402

STRIP = ["generated_at", "host", "content_digest", "strip", "self_check"]

# files this analysis actually reads out of a capture directory
CAPTURE_GLOBS = ("layer-*.f32", "decode-logits-*.f32", "logits.f32", "state-after.f32", "qi-flux-*.f32")

ARTIFACTS = (
    "logit_lens.py", "lens_common.py", "probe_decode.py", "readout_preflight.py",
    "inventory_captures.py", "make_receipt.py", "verify_report.py",
    "lens-states.json", "lens-results.json", "probe-results.json",
    "capture-inventory.json", "readout-preflight.json",
    "lens-curves-w5120.npz", "lens-curves-w1024.npz", "readout-cells.npz",
    "commitment-curve-w5120.png", "commitment-curve-w1024.png",
    "commitment-curve-arms-named-w5120.png",
    "commitment-curve-arms-carryp0-w5120.png",
    "lens-fidelity-w5120.png", "lens-fidelity-w1024.png",
    "REPORT.md", "FIELD_READOUT_DESIGN.md",
)

MEASURED_VS_INFERRED = {
    "measured": [
        "per-layer lens top-1/top-5/median rank/median p(answer)/median entropy, and the "
        "readable vs unreadable layer sets, for both widths and every captured kind",
        "commitment layer, stable run and sharpness per kind and per arm, including the "
        "on/off pairs and the 0.8B control",
        "instrument validation: 256 decode rows at layer 63, top-1 0.977, median rank 1",
        "on/off agreement in the controlled pairs (same commit layer and run; p within 0.006)",
        "the trajectory census per width and kind, and the per-fold class disjointness that "
        "makes the probe control degenerate",
        "probe accuracies, balanced accuracies, majority baselines and shuffled controls, "
        "with the strict per-kind mapper and the trajectory gate",
        "continuation-stance counts (250/280 and 39/49 all direct claim, 0 hedges)",
        "readout pre-flight: availability, rho saturation, cell-weight and top-cell "
        "concentration, zero share, cell-energy vs confidence, field score vs model "
        "probability, and the readout-cell probes with both controls",
        "the absolute-read A/B comparison at 12 tokens (cosine +0.553, top-cell agreement 0.0)",
    ],
    "inferred": [
        "that the prompt position's low top-1 rate comes from a mismatch between the stored "
        "logits and the captured residual position (no receipt states each logits file's "
        "position, so this is not established)",
        "that the L61-63 collapse is a property of the end of a deep stack rather than of "
        "this particular model (the 0.8B control is consistent, n=1)",
        "that the mid-stack residual is empty rather than weakly informative (uniform "
        "entropy supports it; a nonlinear read is not excluded)",
        "the (a)-(d) mechanism in FIELD_READOUT_DESIGN.md section 3 that would make a cell "
        "legible, and that attention heads would carry more legible content than the readout",
        "that a steering signal must arrive before roughly L55 to change the next token",
    ],
    "not_claimed": [
        "that the field's presence alters where or how sharply the model commits (the "
        "controlled pairs show identical commit layers and runs)",
        "any probe result as a property of the model: every probe is recorded as "
        "not_supported, and the two that carry a number sit within one standard deviation "
        "of their own shuffled control",
        "any claim about the model beyond the captures read here (nothing was re-run, "
        "rebuilt, or re-generated for this analysis)",
    ],
}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def capture_dirs() -> list[Path]:
    """Every capture directory this analysis read a number out of."""
    dirs: set[Path] = set()
    for name in ("lens-states.json", "capture-inventory.json"):
        path = HERE / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("states") or payload.get("records") or []
        for record in records:
            raw = record.get("capture_dir")
            if not raw:
                continue
            candidate = Path(raw)
            dirs.add(candidate if candidate.is_absolute() else WORKSPACE / candidate)
    family = WORKSPACE / "CassiQwen/native/llama.cpp/_diag/aim-profile-floor-flag-canonical"
    for arm in ("abs_on", "abs_off", "lesion", "off"):
        candidate = family / arm / "captures"
        if candidate.exists():
            dirs.add(candidate)
    return sorted(dirs)


def capture_rows(skip: bool) -> list[dict]:
    rows = []
    for directory in capture_dirs():
        if not directory.exists():
            rows.append({"capture_dir": str(directory), "missing": True})
            continue
        files = sorted(path for pattern in CAPTURE_GLOBS for path in directory.glob(pattern))
        files = sorted(set(files))
        entry = {
            "capture_dir": str(directory.relative_to(WORKSPACE)),
            "n_files": len(files),
            "bytes": sum(path.stat().st_size for path in files),
        }
        if skip:
            entry["digest"] = "skipped (--skip-captures)"
        else:
            digest = hashlib.sha256()
            for path in files:
                digest.update(f"{path.name} {path.stat().st_size} ".encode())
                digest.update(sha256_file(path).encode())
            entry["digest"] = digest.hexdigest()
        rows.append(entry)
    return rows


def gguf_identity() -> dict:
    """The unembedding source.  The file is 16 GB, so identity is path/size/mtime plus the
    tensor that was actually read, not a whole-file hash."""
    candidates = []
    for profile in (WORKSPACE / "CassiQwen/native/llama.cpp/_diag").glob("aim-profile-*/profile.json"):
        try:
            payload = json.loads(profile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        text = json.dumps(payload)
        for token in text.replace('"', " ").replace(",", " ").split():
            if token.endswith(".gguf") and "27" in token:
                candidates.append(Path(token.replace("\\\\", "\\")))
    rows = []
    for path in sorted(set(candidates)):
        if not path.is_absolute():
            path = WORKSPACE / path
        exists = path.exists()
        stat = path.stat() if exists else None
        rows.append({
            "path": str(path),
            "exists": exists,
            "bytes": stat.st_size if stat else None,
            "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else None,
            "hash": "not computed: 16 GB inference-time weight file; identity is path/size/mtime "
                    "plus the tensor the lens reads (output.weight / token_embd.weight, 248320 rows)",
        })
    return {"gguf_files_referenced": rows}


def build(skip_captures: bool) -> dict:
    artifacts = []
    for name in ARTIFACTS:
        path = HERE / name
        if not path.exists():
            artifacts.append({"name": name, "missing": True})
            continue
        artifacts.append({
            "name": name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return {
        "what": "layer-by-layer decoding of the captured hidden states: logit lens, probes, "
                "and the field readout design note",
        "scope": "analysis of captures already on disk; no model run, no llama.cpp change, no rebuild",
        "mapper": "strict per-kind classes (labels with fewer than --min-class states are dropped, "
                  "never folded into a catch-all class)",
        "probe_gate": "a per-layer probe is reported only with >= 20 independent trajectories; "
                      "blocked probes keep their measurement under rows_measured_but_not_supported",
        "artifacts": artifacts,
        "captures": {
            "roots": [
                "CassiQwen/native/llama.cpp/_diag/steps32-{on,off}",
                "CassiQwen/native/llama.cpp/_diag/carry-forward/runs2/epoch-0/{off,on}-p0",
                "CassiQwen/native/llama.cpp/_diag/carry-forward/runs/epoch-*/{A,B}-on-p{0,1}",
                "CassiQwen/native/llama.cpp/_diag/aim-profile-floor-flag-canonical/{abs_on,abs_off,lesion,off}",
                "CassiQwen/native/llama.cpp/_diag/ (0.8B width-1024 captures)",
            ],
            "files_hashed": list(CAPTURE_GLOBS),
            "rows": capture_rows(skip_captures),
        },
        "weights": gguf_identity(),
        "measured_vs_inferred": MEASURED_VS_INFERRED,
        "verdicts": {
            "logit_lens": "readable from layer ~55 onward; commit layer 61 (decode row of token 1), "
                          "63 (last decode row), 62 (prompt row); 0.8B control not committed in its tail",
            "on_vs_off": "commit layer, stable run and sharpness unchanged within the controlled pairs",
            "probes": "not supported by this capture set: 4-8 independent trajectories, and the "
                      "next-token target is constant within a trajectory",
            "stance_probe": "0 hedges in 289 classifiable continuations; one class, no probe",
            "readout_as_decoder": "readout cells do not name the model's next token (0.215 vs "
                                  "majority 0.262 and shuffled 0.231+-0.081; balanced 0.500 on "
                                  "both binary targets)",
        },
        "strip": STRIP,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "node": socket.gethostname(), "python": sys.version.split()[0]},
    }


def digest_of(receipt: dict) -> str:
    body = {key: value for key, value in receipt.items() if key not in STRIP}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-captures", action="store_true",
                        help="skip hashing the capture files (fast, receipt is not provenance-complete)")
    args = parser.parse_args()
    receipt = build(args.skip_captures)
    receipt["content_digest"] = digest_of(receipt)
    receipt["self_check"] = {
        "digest_rule": "sha256 of the receipt body with the keys in `strip` removed, json-serialized "
                       "with sorted keys and no spaces.  Stripped: this run's clock and host, and the "
                       "rule's own text.  Kept, because they are evidence rather than clock: input "
                       "sizes, input content digests, and input mtimes (a change to a weight file or a "
                       "capture must change the digest).",
        "reproduce": "python make_receipt.py   # compare content_digest across runs",
    }
    (HERE / "RECEIPT.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    total = sum(row.get("bytes", 0) for row in receipt["captures"]["rows"])
    print(f"wrote RECEIPT.json: {len(receipt['artifacts'])} artifacts, "
          f"{len(receipt['captures']['rows'])} capture dirs, {total / 1e6:.1f} MB hashed")
    print(f"content_digest {receipt['content_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
