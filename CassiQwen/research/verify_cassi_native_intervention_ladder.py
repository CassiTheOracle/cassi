#!/usr/bin/env python3
"""Independently verify a native 27B IQ1_S intervention ladder receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_llama_capture import NativeCaptureError, load_graph_trial
from cassi_universal_interpreter import receipt_digest


EXPECTED_MODEL_SHA256 = "3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887"
EXPECTED_QUANTIZATION = "IQ1_S"
EXPECTED_LAYER = 32
EXPECTED_DECODE_STEPS = 2
EXPECTED_ARM_CONFIGS: dict[str, dict[str, Any]] = {
    "additive_identity": {"placement": "output_norm_additive", "displacement": 0, "injection_scale": 0.0, "substitute": 0.0},
    "additive_dose_025": {"placement": "output_norm_additive", "displacement": 0, "injection_scale": 0.25, "substitute": 0.0},
    "additive_dose_050": {"placement": "output_norm_additive", "displacement": 0, "injection_scale": 0.5, "substitute": 0.0},
    "additive_dose_100": {"placement": "output_norm_additive", "displacement": 0, "injection_scale": 1.0, "substitute": 0.0},
    "recurrent_lesion": {"placement": "recurrent_state_row_lesion", "displacement": 3, "injection_scale": 0.0, "substitute": 0.0},
    "recurrent_dose_025": {"placement": "recurrent_state_row", "displacement": 3, "injection_scale": 0.0, "substitute": 0.25},
    "recurrent_dose_050": {"placement": "recurrent_state_row", "displacement": 3, "injection_scale": 0.0, "substitute": 0.5},
    "recurrent_dose_100": {"placement": "recurrent_state_row", "displacement": 3, "injection_scale": 0.0, "substitute": 1.0},
    "head_field": {"placement": "lm_head_field_owned", "displacement": 6, "injection_scale": 0.0, "substitute": 0.0},
}


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NativeCaptureError(f"expected JSON object: {path}")
    return value


def _array(trial_dir: Path, descriptor: Mapping[str, Any]) -> np.ndarray:
    path = trial_dir / str(descriptor["path"])
    values = np.fromfile(path, dtype=np.float32)
    expected = int(descriptor["elements"])
    if values.size != expected or not np.isfinite(values).all():
        raise NativeCaptureError(f"invalid raw float32 artifact: {path}")
    if _sha256_path(path) != descriptor.get("sha256"):
        raise NativeCaptureError(f"raw artifact digest mismatch: {path}")
    return values


def _metric(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    if reference.shape != candidate.shape:
        raise NativeCaptureError(f"metric shape mismatch: {reference.shape} != {candidate.shape}")
    reference64 = reference.astype(np.float64)
    candidate64 = candidate.astype(np.float64)
    delta = candidate64 - reference64
    ref_norm = float(np.linalg.norm(reference64))
    candidate_norm = float(np.linalg.norm(candidate64))
    ref_order = np.argsort(reference64)[-2:][::-1]
    candidate_order = np.argsort(candidate64)[-2:][::-1]
    cosine = None
    if ref_norm > 0.0 and candidate_norm > 0.0:
        cosine = float(np.dot(reference64, candidate64) / (ref_norm * candidate_norm))
    return {
        "l2": float(np.linalg.norm(delta)),
        "max_abs": float(np.max(np.abs(delta))) if delta.size else 0.0,
        "mean_abs": float(np.mean(np.abs(delta))) if delta.size else 0.0,
        "cosine": cosine,
        "reference_top1": int(ref_order[0]),
        "candidate_top1": int(candidate_order[0]),
        "reference_gap": float(reference64[ref_order[0]] - reference64[ref_order[1]]),
        "candidate_gap": float(candidate64[candidate_order[0]] - candidate64[candidate_order[1]]),
    }


def _assert_tree(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(expected) != set(actual):
            raise NativeCaptureError(f"derived field mismatch at {path}")
        for key in expected:
            _assert_tree(expected[key], actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise NativeCaptureError(f"derived list mismatch at {path}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _assert_tree(left, right, f"{path}[{index}]")
        return
    if isinstance(expected, float):
        if not isinstance(actual, (float, int)) or not math.isclose(expected, float(actual), rel_tol=0.0, abs_tol=1e-10):
            raise NativeCaptureError(f"derived number mismatch at {path}: {actual!r} != {expected!r}")
        return
    if expected != actual:
        raise NativeCaptureError(f"derived value mismatch at {path}: {actual!r} != {expected!r}")


def _analysis(raw: Mapping[str, tuple[Path, Mapping[str, Any]]]) -> dict[str, Any]:
    identity_path, identity = raw["additive_identity"]
    identity_step_0 = _array(identity_path, identity["logit_steps"][0])
    identity_final = _array(identity_path, identity["logits"])
    identity_state = _array(identity_path, identity["state_successor"])
    comparisons: dict[str, Any] = {}
    state_comparisons: dict[str, Any] = {}
    for name in EXPECTED_ARM_CONFIGS:
        trial_path, receipt = raw[name]
        step_0 = _array(trial_path, receipt["logit_steps"][0])
        final = _array(trial_path, receipt["logits"])
        state = _array(trial_path, receipt["state_successor"])
        comparisons[name] = {
            "identity_step_0": _metric(identity_step_0, step_0),
            "identity_final": _metric(identity_final, final),
        }
        state_comparisons[name] = _metric(identity_state, state)

    lesion_path, lesion = raw["recurrent_lesion"]
    lesion_step_0 = _array(lesion_path, lesion["logit_steps"][0])
    lesion_final = _array(lesion_path, lesion["logits"])
    lesion_state = _array(lesion_path, lesion["state_successor"])
    recurrent_pairs: dict[str, Any] = {}
    for name in ("recurrent_dose_025", "recurrent_dose_050", "recurrent_dose_100"):
        trial_path, receipt = raw[name]
        recurrent_pairs[name] = {
            "lesion_step_0": _metric(lesion_step_0, _array(trial_path, receipt["logit_steps"][0])),
            "lesion_final": _metric(lesion_final, _array(trial_path, receipt["logits"])),
            "lesion_state": _metric(lesion_state, _array(trial_path, receipt["state_successor"])),
        }
    return {
        "identity_arm": "additive_identity",
        "comparisons_to_additive_identity": comparisons,
        "state_comparisons_to_additive_identity": state_comparisons,
        "recurrent_pairs_to_lesion": recurrent_pairs,
        "placement_pairs": {
            "head_vs_additive_identity": {
                "step_0": comparisons["head_field"]["identity_step_0"],
                "final": comparisons["head_field"]["identity_final"],
            },
            "recurrent_field_vs_lesion": recurrent_pairs["recurrent_dose_100"],
        },
        "live_signals": {
            "additive_dose_100_final_l2": comparisons["additive_dose_100"]["identity_final"]["l2"],
            "recurrent_dose_100_vs_lesion_final_l2": recurrent_pairs["recurrent_dose_100"]["lesion_final"]["l2"],
            "head_field_final_l2": comparisons["head_field"]["identity_final"]["l2"],
            "head_field_output_owner": raw["head_field"][1]["graph"]["output_owner"],
        },
    }


def _within(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise NativeCaptureError(f"{label} escapes ladder root: {path}") from error
    return resolved


def verify_ladder(root: Path) -> dict[str, Any]:
    receipt_path = root / "intervention-ladder-receipt.json"
    if not receipt_path.is_file():
        raise NativeCaptureError(f"missing ladder receipt: {receipt_path}")
    receipt = _load_json(receipt_path)
    if receipt.get("schema") != "cassi.qwen.native-intervention-ladder.v1":
        raise NativeCaptureError("ladder receipt schema mismatch")
    if receipt.get("content_sha256") != receipt_digest(receipt):
        raise NativeCaptureError("ladder content digest mismatch")

    model = receipt.get("model")
    source = receipt.get("source")
    fixed = receipt.get("fixed_controls")
    rows = receipt.get("arms")
    if not isinstance(model, Mapping) or not isinstance(source, Mapping) or not isinstance(fixed, Mapping) or not isinstance(rows, list):
        raise NativeCaptureError("ladder receipt omits required sections")
    if model.get("sha256") != EXPECTED_MODEL_SHA256 or model.get("quantization") != EXPECTED_QUANTIZATION:
        raise NativeCaptureError("ladder model identity is not the downloaded IQ1_S model")
    if model.get("filename") != "Qwen3.8-27B-UD-IQ1_S.gguf":
        raise NativeCaptureError("ladder model filename is not the downloaded IQ1_S model")
    if fixed.get("layer") != EXPECTED_LAYER or fixed.get("decode_steps") != EXPECTED_DECODE_STEPS:
        raise NativeCaptureError("ladder fixed controls changed")
    if fixed.get("state_predecessor") != "state-donor.f32":
        raise NativeCaptureError("ladder state predecessor name changed")

    state_path = _within(root, root / "state-donor.f32", "state donor")
    if _sha256_path(state_path) != source.get("state_sha256"):
        raise NativeCaptureError("ladder state donor digest mismatch")
    if state_path.stat().st_size // 4 != int(source.get("state_elements", -1)):
        raise NativeCaptureError("ladder state donor element count mismatch")
    prompt_path = _within(root, root / "prompt.utf8", "prompt")
    if _sha256_path(prompt_path) != source.get("prompt_sha256"):
        raise NativeCaptureError("ladder prompt digest mismatch")
    source_run_name = str(source.get("run_name", ""))
    source_run = _within(root.parent, root.parent / source_run_name, "source run")
    source_program_path = _within(source_run, source_run / "native-program-receipt.json", "source program receipt")
    source_capture_path = _within(source_run, source_run / "native-capture" / "capture-receipt.json", "source capture receipt")
    source_graph_path = _within(
        source_run,
        source_run / "graph-native" / "recurrent-field" / "graph-trial-receipt.json",
        "source graph receipt",
    )
    source_state_path = _within(source_run, source_run / "state-donor.f32", "source state donor")
    if _sha256_path(source_program_path) != source.get("program_receipt_sha256"):
        raise NativeCaptureError("source program receipt digest mismatch")
    if _sha256_path(source_capture_path) != source.get("capture_receipt_sha256"):
        raise NativeCaptureError("source capture receipt digest mismatch")
    if _sha256_path(source_graph_path) != source.get("graph_receipt_sha256"):
        raise NativeCaptureError("source graph receipt digest mismatch")
    if _sha256_path(source_state_path) != source.get("state_sha256"):
        raise NativeCaptureError("source state donor digest mismatch")
    source_program = _load_json(source_program_path)
    if source_program.get("content_sha256") != source.get("program_content_sha256"):
        raise NativeCaptureError("source program content digest mismatch")
    source_capture = _load_json(source_capture_path)
    source_prompt = source_capture.get("prompt", {})
    if source_prompt.get("sha256") != source.get("prompt_sha256") or source_prompt.get("token_count") != source.get("prompt_tokens"):
        raise NativeCaptureError("source prompt control differs from ladder receipt")
    source_graph = load_graph_trial(source_graph_path)
    if source_graph.get("configuration", {}).get("continuation_tokens") != source.get("continuation_tokens"):
        raise NativeCaptureError("source continuation control differs from ladder receipt")

    rows_by_name = {str(row.get("name")): row for row in rows if isinstance(row, Mapping)}
    if set(rows_by_name) != set(EXPECTED_ARM_CONFIGS):
        raise NativeCaptureError("ladder arm inventory mismatch")
    raw: dict[str, tuple[Path, Mapping[str, Any]]] = {}
    fingerprints: set[str] = set()
    for name, expected in EXPECTED_ARM_CONFIGS.items():
        row = rows_by_name[name]
        for key, value in expected.items():
            if row.get(key) != value:
                raise NativeCaptureError(f"arm row {name} mismatch for {key}")
        receipt_rel = Path(str(row.get("receipt_path", "")))
        trial_receipt_path = _within(root, root / receipt_rel, f"arm {name} receipt")
        if trial_receipt_path.name != "graph-trial-receipt.json":
            raise NativeCaptureError(f"arm {name} receipt name is not graph-trial-receipt.json")
        if _sha256_path(trial_receipt_path) != row.get("receipt_sha256"):
            raise NativeCaptureError(f"arm {name} graph receipt digest mismatch")
        trial_dir = trial_receipt_path.parent
        graph = load_graph_trial(trial_receipt_path)
        if row.get("configuration") != graph.get("configuration") or row.get("graph") != graph.get("graph"):
            raise NativeCaptureError(f"arm {name} copied graph metadata differs from raw receipt")
        if row.get("logit_steps") != graph.get("logit_steps") or row.get("logits") != graph.get("logits") or row.get("state_successor") != graph.get("state_successor"):
            raise NativeCaptureError(f"arm {name} copied artifact metadata differs from raw receipt")
        configuration = graph["configuration"]
        if configuration.get("layer") != EXPECTED_LAYER or configuration.get("decode_steps") != EXPECTED_DECODE_STEPS:
            raise NativeCaptureError(f"arm {name} configuration does not preserve fixed controls")
        if configuration.get("prompt_sha256") != source.get("prompt_sha256"):
            raise NativeCaptureError(f"arm {name} prompt digest differs from source")
        if configuration.get("prompt_tokens") != source.get("prompt_tokens") or configuration.get("continuation_tokens") != source.get("continuation_tokens"):
            raise NativeCaptureError(f"arm {name} token control differs from source")
        predecessor = graph.get("state_predecessor")
        if not isinstance(predecessor, Mapping):
            raise NativeCaptureError(f"arm {name} omits state predecessor")
        predecessor_path = _within(root, trial_dir / str(predecessor["path"]), f"arm {name} predecessor")
        if predecessor_path != state_path or predecessor.get("sha256") != source.get("state_sha256"):
            raise NativeCaptureError(f"arm {name} does not use the shared state predecessor")
        model_data = graph.get("model")
        fingerprint = str(graph.get("model_fingerprint"))
        if (
            not isinstance(model_data, Mapping)
            or model_data.get("model_sha256") != EXPECTED_MODEL_SHA256
            or model_data.get("model_id") != "Qwen3.8-27B-UD-IQ1_S.gguf"
        ):
            raise NativeCaptureError(f"arm {name} model identity mismatch")
        fingerprints.add(fingerprint)
        ownership = graph["graph"]
        displacement = int(expected["displacement"])
        substitute = float(expected["substitute"])
        if not ownership.get("executed") or ownership.get("decode_steps") != EXPECTED_DECODE_STEPS:
            raise NativeCaptureError(f"arm {name} graph did not execute the declared decode")
        if displacement == 6:
            required = {"output_owner": "field", "logit_owner": "field", "lm_head_owner": "field", "model_logits_read": 0, "field_logits_read": EXPECTED_DECODE_STEPS, "qi_state_write_owner": "suppressed-model"}
        elif displacement == 3 and substitute > 0.0:
            required = {"output_owner": "model", "logit_owner": "model", "lm_head_owner": "model", "model_logits_read": EXPECTED_DECODE_STEPS, "field_logits_read": 0, "qi_state_write_owner": "field"}
            if int(ownership.get("qi_state_field_width", 0)) <= 0:
                raise NativeCaptureError(f"arm {name} field substitution has zero field width")
        elif displacement == 3:
            required = {"output_owner": "model", "logit_owner": "model", "lm_head_owner": "model", "model_logits_read": EXPECTED_DECODE_STEPS, "field_logits_read": 0, "qi_state_write_owner": "suppressed-model"}
            if int(ownership.get("qi_state_field_width", -1)) != 0:
                raise NativeCaptureError(f"arm {name} lesion unexpectedly owns field state")
        else:
            required = {"output_owner": "model", "logit_owner": "model", "lm_head_owner": "model", "model_logits_read": EXPECTED_DECODE_STEPS, "field_logits_read": 0, "qi_state_write_owner": "model"}
        for key, value in required.items():
            if ownership.get(key) != value:
                raise NativeCaptureError(f"arm {name} ownership mismatch for {key}: {ownership.get(key)!r} != {value!r}")
        raw[name] = (trial_dir, graph)
    if len(fingerprints) != 1:
        raise NativeCaptureError("ladder arms do not share one model fingerprint")

    recomputed = _analysis(raw)
    _assert_tree(recomputed, receipt.get("analysis"), "analysis")
    return {
        "verdict": "PASS",
        "receipt": str(receipt_path),
        "content_sha256": receipt["content_sha256"],
        "arms": len(raw),
        "model_sha256": model["sha256"],
        "model_fingerprint": next(iter(fingerprints)),
        "signals": recomputed["live_signals"],
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = verify_ladder(args.run_dir.resolve())
    except (NativeCaptureError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
