"""Capture campaign for the probing-grade hidden-state set.

Runs the pinned 27B latent harness one prompt at a time, field off, and keeps
every receipt and capture under the gitignored _diag tree. Three stages:

  screen     label-only pass over every candidate prompt: no capture directory,
             so the run costs a model load and a short generation.  Writes
             screen.json, and selection.json holding the prompts whose own
             continuation landed in the intended register class.
  capture    the same selected prompts again, this time with per-decode-step
             layer captures over the probe range.  Writes capture-summary.json.
  attention  one prompt with the attention capture on, which needs a separate
             run because it forces flash attention off.

The label is always read from the run's own continuation, never from the
prompt, and the class counts are written before any probe reads the captures.

Usage:
    python run_probe_campaign.py screen
    python run_probe_campaign.py capture
    python run_probe_campaign.py attention [PROMPT_ID]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
CASSIQWEN = WORKSPACE / "CassiQwen"
LLAMA = CASSIQWEN / "native" / "llama.cpp"
EXE = LLAMA / "b8" / "bin" / "Release" / "test-cassi-qi-latent.exe"
MODEL = CASSIQWEN / "Qwen3.8-27B-Q4_K_M.gguf"
STATE = LLAMA / "_diag" / "tmp-amp-wave" / "w1.f32"
DIAG = LLAMA / "_diag" / "probe-campaign"
PROMPTS_JSON = HERE / "prompts.json"

FIELD_LAYER = "28"
STEPS = "0"
ALPHA = "0.0"
TOKENS = "40"
ATTENTION_TOKENS = "24"
MIN_PER_FAMILY = 20
MAX_PER_FAMILY = 24
ATTENTION_PROMPT = "d-qa-01"

# Epistemic markers only.  Ordinary connectives ("if", "but", "however") are
# deliberately absent: they appear in direct claims too, and the retired stance
# probe's looser list is what made its vote unreadable.  The second block adds
# the knowledge-boundary phrasings measured in the elicitation sweep, where the
# model says it cannot reach the answer without using any single keyword above.
HEDGE_MARKERS = (
    "cannot", "can not", "can't", "unable", "not possible", "impossible to",
    "no way to", "don't know", "do not know", "not sure", "not certain",
    "uncertain", "unclear", "unknown", "no record", "not recorded",
    "never been recorded", "never recorded", "not documented", "not available",
    "no reliable", "probably", "likely", "perhaps", "possibly", "estimate",
    "estimated", "approximately", "roughly", "speculat", "assume", "assumed",
    "presumably", "tentatively", "might have", "may have", "it depends",
    "don't have access", "do not have access", "no access to", "hasn't",
    "has not yet", "not yet occurred", "no one knows", "nobody knows",
    "not known", "no information about", "no data", "without knowing",
    "i would need", "i'd need", "you would need", "you'd need",
    "not possible for me", "outside my knowledge", "beyond my knowledge",
    "no way for me", "hard to say", "unpredictable", "more information",
    "if you tell me", "if you provide", "if you give me",
    "no one can", "nobody can", "cannot predict", "can't predict",
    "not been decided", "not yet decided", "have not yet been", "will not be made",
)

# A continuation that has not expressed a register yet is not a class.  The pinned
# model emits a literal thinking prefix in some continuations and a multiple-choice
# option list in others; both were measured in the elicitation sweeps, and neither
# carries a claim or a qualifier inside the generation budget.
UNCLASSIFIED_MARKERS = ("<think>", "<thinking>", "options:")
MIN_CLASSIFIABLE_CHARS = 8


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_design() -> dict:
    return json.loads(PROMPTS_JSON.read_text(encoding="utf-8"))


def render(entry: dict, design: dict) -> str:
    return design["templates"][entry["template"]].format(q=entry["q"]) + "\n"


def candidates(design: dict) -> list[dict]:
    out = []
    for family, key in (("hedge", "hedge_candidates"), ("direct", "direct_candidates")):
        for entry in design[key]:
            out.append({
                "id": entry["id"],
                "template": entry["template"],
                "intended": family,
                "prompt": render(entry, design),
            })
    return out


def classify_register(text: str) -> dict:
    """Lexical register label over the model's own continuation."""
    lowered = " " + text.lower().replace("\n", " ") + " "
    hits = sorted({marker for marker in HEDGE_MARKERS if marker in lowered})
    return {
        "label": "hedge" if hits else "direct",
        "markers": hits,
    }


def label_row(text: str) -> dict:
    stripped = text.strip()
    reasons = []
    if len(stripped) < MIN_CLASSIFIABLE_CHARS:
        reasons.append("empty continuation")
    lowered = stripped.lower()
    for marker in UNCLASSIFIED_MARKERS:
        if marker in lowered:
            reasons.append(f"no register expressed yet ({marker})")
    full = classify_register(text)
    early = classify_register(text[:200])
    return {
        "label": "unclassified" if reasons else full["label"],
        "markers": full["markers"],
        "unclassified_reasons": reasons,
        "early_label": early["label"],
        "early_markers": early["markers"],
    }


TEMPLATES = ("qa", "brief")


def prompt_path(entry: dict) -> Path:
    target = DIAG / "prompts" / (entry["id"] + ".txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = entry["prompt"]
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8", newline="\n")
    return target


def other_harness_running() -> bool:
    """One 27B process at a time: a peer may be running the same harness."""
    listing = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq test-cassi-qi-latent.exe"],
        capture_output=True, text=True, check=False,
    ).stdout
    return "test-cassi-qi-latent.exe" in listing


def run_once(entry: dict, *, output_dir: Path | None, extra: list[str],
             tokens: str, field_layer: str = FIELD_LAYER) -> dict:
    prompt = prompt_path(entry)
    command = [
        str(EXE), str(MODEL), str(STATE), "gpu", str(prompt),
        field_layer, STEPS, ALPHA, tokens,
    ]
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        command.append(str(output_dir))
        command.extend(["0", "0"])
    command.extend(extra)
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=str(EXE.parent), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=3600, check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            "harness failed for " + entry["id"] + " (" + str(completed.returncode) + "): "
            + completed.stderr.strip()[-2000:]
        )
    receipt = json.loads(completed.stdout)
    receipt["wall_seconds"] = elapsed
    receipt["command"] = command
    return receipt


def run_dir(stage: str, entry: dict) -> Path:
    target = DIAG / stage / entry["id"]
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_run(stage: str, entry: dict, receipt: dict) -> Path:
    target = run_dir(stage, entry)
    (target / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return target


def stage_screen(design: dict) -> int:
    entries = candidates(design)
    rows = []
    for entry in entries:
        receipt = run_once(entry, output_dir=None, extra=[], tokens=TOKENS)
        label = label_row(receipt.get("generation_text", ""))
        receipt["register"] = label
        save_run("screen", entry, receipt)
        rows.append({
            "id": entry["id"],
            "template": entry["template"],
            "intended": entry["intended"],
            "label": label["label"],
            "markers": label["markers"],
            "early_label": label["early_label"],
            "early_markers": label["early_markers"],
            "generation_tokens": len(receipt.get("generation_token_ids", [])),
            "generation_text": receipt.get("generation_text", ""),
            "wall_seconds": receipt["wall_seconds"],
            "prompt_sha256": hashlib.sha256(entry["prompt"].encode("utf-8")).hexdigest(),
        })
        print(entry["id"], "->", label["label"], label["markers"][:4], flush=True)

    summary = {
        "schema": "cassi.probe-campaign.screen.v2",
        "model_sha256": sha256_file(MODEL),
        "executable_sha256": sha256_file(EXE),
        "tokens": TOKENS,
        "field_layer": FIELD_LAYER,
        "steps": STEPS,
        "markers": list(HEDGE_MARKERS),
        "rows": rows,
    }
    (DIAG / "screen.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    write_selection(rows)
    return 0


def write_selection(rows: list[dict]) -> dict:
    selection = select(rows)
    (DIAG / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True), encoding="utf-8")
    report_balance(selection)
    return selection


def stage_reselect() -> int:
    """Re-derive the selection from a stored screen without re-running the model.

    The stored continuations are the label source, so a lexicon change can be
    applied offline; the new lexicon is recorded beside the new counts.
    """
    path = DIAG / "screen.json"
    if not path.exists():
        raise SystemExit("screen.json is missing: run the screen stage first")
    saved = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for row in saved["rows"]:
        label = label_row(row["generation_text"])
        rows.append({**row, **label, "markers": label["markers"]})
    saved["markers"] = list(HEDGE_MARKERS)
    saved["rows"] = rows
    saved["schema"] = "cassi.probe-campaign.screen.v2"
    path.write_text(json.dumps(saved, indent=2, sort_keys=True), encoding="utf-8")
    write_selection(rows)
    return 0


def select(rows: list[dict]) -> dict:
    """Keep prompts whose own continuation landed in the intended class.

    Balanced across the two disjoint surface templates, capped per family, so a
    cross-template probe is a generalization test over disjoint questions.
    """
    out: dict[str, list[dict]] = {}
    for family in ("hedge", "direct"):
        chosen: list[dict] = []
        for template in TEMPLATES:
            matching = [
                row for row in rows
                if row["intended"] == family and row["template"] == template
                and row["label"] == family
            ]
            chosen.extend(matching[:MAX_PER_FAMILY // len(TEMPLATES)])
        out[family] = [
            {"id": row["id"], "template": row["template"],
             "generation_text": row["generation_text"],
             "markers": row["markers"],
             "prompt_sha256": row["prompt_sha256"],
             "screen_wall_seconds": row["wall_seconds"]}
            for row in chosen
        ]
    intended_counts = {}
    for family in ("hedge", "direct"):
        attempted = [row for row in rows if row["intended"] == family]
        intended_counts[family] = {
            "attempted": len(attempted),
            "landed_intended": len([row for row in attempted if row["label"] == family]),
            "landed_other": len([row for row in attempted if row["label"] != family]),
            "selected": len(out[family]),
            "selected_by_template": {
                template: len([row for row in out[family] if row["template"] == template])
                for template in TEMPLATES
            },
        }
    return {
        "schema": "cassi.probe-campaign.selection.v2",
        "min_per_family": MIN_PER_FAMILY,
        "max_per_family": MAX_PER_FAMILY,
        "counts": intended_counts,
        "gate_passed": all(
            intended_counts[family]["selected"] >= MIN_PER_FAMILY
            for family in ("hedge", "direct")
        ),
        "ids": {family: [row["id"] for row in out[family]] for family in out},
        "rows": out,
    }


def report_balance(selection: dict) -> None:
    for family, counts in selection["counts"].items():
        print(family, counts, flush=True)
    if not selection["gate_passed"]:
        print("GATE FAILED: fewer than", MIN_PER_FAMILY, "prompts landed in a class", flush=True)


def load_selection() -> dict:
    path = DIAG / "selection.json"
    if not path.exists():
        raise SystemExit("selection.json is missing: run the screen stage first")
    return json.loads(path.read_text(encoding="utf-8"))


STEP_FILE_RE = re.compile(r"^layer-(\d+)-step-(\d+)\.f32$")


def stage_capture(design: dict) -> int:
    selection = load_selection()
    if not selection.get("gate_passed"):
        raise SystemExit("selection gate failed: refusing to capture a set with a thin class")
    wanted = {
        row["id"]: {**row, "intended": family}
        for family, family_rows in selection["rows"].items()
        for row in family_rows
    }
    entries = [entry for entry in candidates(design) if entry["id"] in wanted]
    entries.sort(key=lambda entry: (entry["template"], entry["id"]))
    rows = []
    for entry in entries:
        target = DIAG / "captures" / entry["id"]
        receipt = run_once(
            entry, output_dir=target, extra=["--capture-steps"], tokens=TOKENS)
        label = label_row(receipt.get("generation_text", ""))
        receipt["register"] = label
        save_run("capture", entry, receipt)
        step_files = [
            name for name in sorted(os.listdir(target)) if STEP_FILE_RE.match(name)
        ]
        prompt_captures = len(receipt.get("captured_layers", []))
        screen_text = wanted[entry["id"]]["generation_text"]
        rows.append({
            "id": entry["id"],
            "template": entry["template"],
            "intended": wanted[entry["id"]]["intended"],
            "label": label["label"],
            "markers": label["markers"],
            "early_label": label["early_label"],
            "prompt_sha256": hashlib.sha256(entry["prompt"].encode("utf-8")).hexdigest(),
            "generation_token_ids": receipt.get("generation_token_ids", []),
            "generation_text": receipt.get("generation_text", ""),
            "screen_text_reproduced": screen_text == receipt.get("generation_text", ""),
            "decodes": len(step_files) // max(prompt_captures, 1),
            "prompt_captures": prompt_captures,
            "step_files": len(step_files),
            "capture_dir": str(target),
            "wall_seconds": receipt["wall_seconds"],
        })
        print(entry["id"], round(receipt["wall_seconds"], 1), len(step_files), flush=True)

    summary = {
        "schema": "cassi.probe-campaign.capture.v1",
        "model_sha256": sha256_file(MODEL),
        "executable_sha256": sha256_file(EXE),
        "field_layer": FIELD_LAYER,
        "tokens": TOKENS,
        "steps": STEPS,
        "alpha": ALPHA,
        "step_file_pattern": "layer-<layer>-step-<decode index>.f32",
        "device": "gpu",
        "class_counts": {
            "hedge": len([row for row in rows if row["label"] == "hedge"]),
            "direct": len([row for row in rows if row["label"] == "direct"]),
        },
        "independent_trajectories": {
            "hedge": len({row["id"] for row in rows if row["label"] == "hedge"}),
            "direct": len({row["id"] for row in rows if row["label"] == "direct"}),
        },
        "screen_label_reproduced": len([row for row in rows if row["screen_text_reproduced"]]),
        "class_counts_by_template": {
            template: {
                "hedge": len([row for row in rows
                              if row["label"] == "hedge" and row["template"] == template]),
                "direct": len([row for row in rows
                               if row["label"] == "direct" and row["template"] == template]),
            }
            for template in TEMPLATES
        },
        "decode_step_histogram": {},
        "rows": rows,
    }
    for row in rows:
        key = str(row["decodes"])
        summary["decode_step_histogram"][key] = (
            summary["decode_step_histogram"].get(key, 0) + 1)
    (DIAG / "capture-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary["class_counts"]), flush=True)
    return 0


def stage_attention(design: dict, prompt_id: str) -> int:
    entries = [entry for entry in candidates(design) if entry["id"] == prompt_id]
    if not entries:
        raise SystemExit("unknown prompt id: " + prompt_id)
    entry = entries[0]
    target = DIAG / "attention" / prompt_id
    receipt = run_once(
        entry, output_dir=target, extra=["--capture-attention", "--capture-steps"],
        tokens=ATTENTION_TOKENS)
    save_run("attention", entry, receipt)
    (DIAG / "attention-summary.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt.get("attention_capture", {})), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("screen", "reselect", "capture", "attention"))
    parser.add_argument("--prompt", default=ATTENTION_PROMPT)
    args = parser.parse_args()

    for path in (EXE, MODEL):
        if not path.is_file():
            raise SystemExit("missing: " + str(path))
    if args.stage == "reselect":
        return stage_reselect()
    if other_harness_running():
        raise SystemExit("another test-cassi-qi-latent process is running: serialize first")

    design = load_design()
    if args.stage == "screen":
        return stage_screen(design)
    if args.stage == "capture":
        return stage_capture(design)
    return stage_attention(design, args.prompt)


if __name__ == "__main__":
    sys.exit(main())
