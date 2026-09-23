#!/usr/bin/env python3
"""Run a reproducible 27B IQ1_S native field intervention ladder.

The ladder holds the prompt, predecessor field state, readout layer, and
continuation fixed while sweeping two independent axes:

* placement: additive output-norm, recurrent state-row, and LM-head ownership;
* dose: additive injection and recurrent state substitution.

Every arm is a fresh graph trial in one native llama.cpp session.  The raw
trial receipts and float32 outputs remain the evidence; the top-level receipt
only records derived comparisons and provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_llama_capture import NativeCaptureError, NativeLlamaSession, load_graph_trial
from cassi_universal_interpreter import receipt_digest


HERE = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = HERE.parent
DEFAULT_MODEL = _CASSIQWEN_ROOT / "Qwen3.8-27B-UD-IQ1_S.gguf"
DEFAULT_RUNTIME_DIR = _CASSIQWEN_ROOT / "native" / "llama.cpp" / "b8" / "bin" / "Release"
DEFAULT_SOURCE_RUN = (
    _CASSIQWEN_ROOT
    / "_diag"
    / "universal-interpreter-native-program-27b-iq1s-20260917-r2"
)
EXPECTED_MODEL_SHA256 = "3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887"
EXPECTED_QUANTIZATION = "IQ1_S"
EXPECTED_LAYER = 32
EXPECTED_DECODE_STEPS = 2

# Keep one layer/readout fixed.  Placement is represented by the existing
# graph seam's displacement: 0 = output-norm additive, 3 = recurrent state
# row, 6 = LM-head ownership.  The positive dose ladders are intentionally
# identical except for the single swept scalar.
ARM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "additive_identity",
        "placement": "output_norm_additive",
        "layer": EXPECTED_LAYER,
        "displacement": 0,
        "injection_scale": 0.0,
        "substitute": 0.0,
    },
    {
        "name": "additive_dose_025",
        "placement": "output_norm_additive",
        "layer": EXPECTED_LAYER,
        "displacement": 0,
        "injection_scale": 0.25,
        "substitute": 0.0,
    },
    {
        "name": "additive_dose_050",
        "placement": "output_norm_additive",
        "layer": EXPECTED_LAYER,
        "displacement": 0,
        "injection_scale": 0.5,
        "substitute": 0.0,
    },
    {
        "name": "additive_dose_100",
        "placement": "output_norm_additive",
        "layer": EXPECTED_LAYER,
        "displacement": 0,
        "injection_scale": 1.0,
        "substitute": 0.0,
    },
    {
        "name": "recurrent_lesion",
        "placement": "recurrent_state_row_lesion",
        "layer": EXPECTED_LAYER,
        "displacement": 3,
        "injection_scale": 0.0,
        "substitute": 0.0,
    },
    {
        "name": "recurrent_dose_025",
        "placement": "recurrent_state_row",
        "layer": EXPECTED_LAYER,
        "displacement": 3,
        "injection_scale": 0.0,
        "substitute": 0.25,
    },
    {
        "name": "recurrent_dose_050",
        "placement": "recurrent_state_row",
        "layer": EXPECTED_LAYER,
        "displacement": 3,
        "injection_scale": 0.0,
        "substitute": 0.5,
    },
    {
        "name": "recurrent_dose_100",
        "placement": "recurrent_state_row",
        "layer": EXPECTED_LAYER,
        "displacement": 3,
        "injection_scale": 0.0,
        "substitute": 1.0,
    },
    {
        "name": "head_field",
        "placement": "lm_head_field_owned",
        "layer": EXPECTED_LAYER,
        "displacement": 6,
        "injection_scale": 0.0,
        "substitute": 0.0,
    },
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NativeCaptureError(f"expected JSON object: {path}")
    return value


def _finite_array(path: Path, *, expected_elements: int | None = None) -> np.ndarray:
    values = np.fromfile(path, dtype=np.float32)
    if expected_elements is not None and values.size != expected_elements:
        raise NativeCaptureError(
            f"unexpected float32 length for {path}: {values.size} != {expected_elements}"
        )
    if not np.isfinite(values).all():
        raise NativeCaptureError(f"non-finite float32 artifact: {path}")
    return values


def _metric(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    if reference.shape != candidate.shape:
        raise NativeCaptureError(f"metric shape mismatch: {reference.shape} != {candidate.shape}")
    delta = candidate.astype(np.float64) - reference.astype(np.float64)
    reference64 = reference.astype(np.float64)
    candidate64 = candidate.astype(np.float64)
    ref_norm = float(np.linalg.norm(reference64))
    candidate_norm = float(np.linalg.norm(candidate64))
    delta_norm = float(np.linalg.norm(delta))
    cosine = None
    if ref_norm > 0.0 and candidate_norm > 0.0:
        cosine = float(np.dot(reference64, candidate64) / (ref_norm * candidate_norm))
    ref_order = np.argsort(reference64)[-2:][::-1]
    candidate_order = np.argsort(candidate64)[-2:][::-1]
    return {
        "l2": delta_norm,
        "max_abs": float(np.max(np.abs(delta))) if delta.size else 0.0,
        "mean_abs": float(np.mean(np.abs(delta))) if delta.size else 0.0,
        "cosine": cosine,
        "reference_top1": int(ref_order[0]),
        "candidate_top1": int(candidate_order[0]),
        "reference_gap": float(reference64[ref_order[0]] - reference64[ref_order[1]]),
        "candidate_gap": float(candidate64[candidate_order[0]] - candidate64[candidate_order[1]]),
    }


def _trial_logits(trial_dir: Path, receipt: Mapping[str, Any], step: int) -> np.ndarray:
    if step == 0:
        descriptor = receipt["logit_steps"][0]
    else:
        descriptor = receipt["logits"]
    path = trial_dir / str(descriptor["path"])
    return _finite_array(path, expected_elements=int(descriptor["elements"]))


def _trial_state(trial_dir: Path, receipt: Mapping[str, Any]) -> np.ndarray:
    descriptor = receipt["state_successor"]
    path = trial_dir / str(descriptor["path"])
    return _finite_array(path, expected_elements=int(descriptor["elements"]))


def _source_inputs(source_root: Path) -> dict[str, Any]:
    program_receipt_path = source_root / "native-program-receipt.json"
    capture_receipt_path = source_root / "native-capture" / "capture-receipt.json"
    graph_receipt_path = source_root / "graph-native" / "recurrent-field" / "graph-trial-receipt.json"
    state_path = source_root / "state-donor.f32"
    for path in (program_receipt_path, capture_receipt_path, graph_receipt_path, state_path):
        if not path.is_file():
            raise NativeCaptureError(f"missing source artifact: {path}")

    program = _load_json(program_receipt_path)
    capture = _load_json(capture_receipt_path)
    graph = load_graph_trial(graph_receipt_path)
    prompt_data = capture.get("prompt", {})
    prompt = prompt_data.get("utf8")
    if not isinstance(prompt, str) or not prompt:
        raise NativeCaptureError("source capture does not contain a prompt")
    prompt_sha = _sha256_bytes(prompt.encode("utf-8"))
    if prompt_sha != prompt_data.get("sha256"):
        raise NativeCaptureError("source prompt digest does not match its capture receipt")
    continuation = graph.get("configuration", {}).get("continuation_tokens")
    if not isinstance(continuation, list) or not continuation or not all(
        isinstance(token, int) for token in continuation
    ):
        raise NativeCaptureError("source graph trial does not contain integer continuation tokens")
    model = program.get("model", {})
    model_sha = model.get("model_sha256")
    quantization = model.get("quantization")
    if model_sha != EXPECTED_MODEL_SHA256:
        raise NativeCaptureError(f"source model sha mismatch: {model_sha} != {EXPECTED_MODEL_SHA256}")
    if quantization != EXPECTED_QUANTIZATION:
        raise NativeCaptureError(f"source quantization mismatch: {quantization} != {EXPECTED_QUANTIZATION}")
    state_size = state_path.stat().st_size
    if state_size % 4 != 0 or state_size == 0:
        raise NativeCaptureError(f"invalid source state byte length: {state_size}")
    return {
        "source_program_receipt_sha256": _sha256_path(program_receipt_path),
        "source_program_content_sha256": program.get("content_sha256"),
        "source_capture_receipt_sha256": _sha256_path(capture_receipt_path),
        "source_graph_receipt_sha256": _sha256_path(graph_receipt_path),
        "prompt": prompt,
        "prompt_sha256": prompt_sha,
        "prompt_tokens": int(prompt_data.get("token_count", 0)),
        "continuation_tokens": [int(token) for token in continuation],
        "state_sha256": _sha256_path(state_path),
        "state_elements": state_size // 4,
        "model_sha256": model_sha,
        "quantization": quantization,
    }


def _validate_arm_config(receipt: Mapping[str, Any], spec: Mapping[str, Any]) -> None:
    configuration = receipt.get("configuration")
    if not isinstance(configuration, Mapping):
        raise NativeCaptureError(f"missing graph configuration for {spec['name']}")
    expected = {
        "layer": spec["layer"],
        "displacement": spec["displacement"],
        "injection_scale": spec["injection_scale"],
        "substitute": spec["substitute"],
        "field_enabled": True,
        "decode_steps": EXPECTED_DECODE_STEPS,
    }
    for key, value in expected.items():
        if configuration.get(key) != value:
            raise NativeCaptureError(
                f"arm {spec['name']} configuration mismatch for {key}: "
                f"{configuration.get(key)!r} != {value!r}"
            )


def _analyze_arms(
    arm_receipts: Mapping[str, Mapping[str, Any]],
    arm_paths: Mapping[str, Path],
) -> dict[str, Any]:
    identity_name = "additive_identity"
    identity = arm_receipts[identity_name]
    identity_path = arm_paths[identity_name]
    identity_step_0 = _trial_logits(identity_path, identity, 0)
    identity_final = _trial_logits(identity_path, identity, 1)
    identity_state = _trial_state(identity_path, identity)
    comparisons: dict[str, Any] = {}
    state_comparisons: dict[str, Any] = {}
    for spec in ARM_SPECS:
        name = str(spec["name"])
        receipt = arm_receipts[name]
        trial_path = arm_paths[name]
        step_0 = _trial_logits(trial_path, receipt, 0)
        final = _trial_logits(trial_path, receipt, 1)
        state = _trial_state(trial_path, receipt)
        comparisons[name] = {
            "identity_step_0": _metric(identity_step_0, step_0),
            "identity_final": _metric(identity_final, final),
        }
        state_comparisons[name] = _metric(identity_state, state)

    recurrent_lesion = arm_receipts["recurrent_lesion"]
    recurrent_lesion_path = arm_paths["recurrent_lesion"]
    lesion_step_0 = _trial_logits(recurrent_lesion_path, recurrent_lesion, 0)
    lesion_final = _trial_logits(recurrent_lesion_path, recurrent_lesion, 1)
    lesion_state = _trial_state(recurrent_lesion_path, recurrent_lesion)
    recurrent_pairs: dict[str, Any] = {}
    for name in ("recurrent_dose_025", "recurrent_dose_050", "recurrent_dose_100"):
        receipt = arm_receipts[name]
        path = arm_paths[name]
        recurrent_pairs[name] = {
            "lesion_step_0": _metric(lesion_step_0, _trial_logits(path, receipt, 0)),
            "lesion_final": _metric(lesion_final, _trial_logits(path, receipt, 1)),
            "lesion_state": _metric(lesion_state, _trial_state(path, receipt)),
        }

    head = arm_receipts["head_field"]
    return {
        "identity_arm": identity_name,
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
            "head_field_output_owner": head["graph"]["output_owner"],
        },
    }


def run_ladder(
    *,
    model: Path,
    runtime_dir: Path,
    source_root: Path,
    output_root: Path,
    gpu_layers: int,
) -> dict[str, Any]:
    if output_root.exists():
        if any(output_root.iterdir()):
            raise NativeCaptureError(f"refusing non-empty output directory: {output_root}")
    else:
        output_root.mkdir(parents=True)
    source = _source_inputs(source_root)
    if not model.is_file():
        raise NativeCaptureError(f"model does not exist: {model}")
    model_sha = _sha256_path(model)
    if model_sha != EXPECTED_MODEL_SHA256:
        raise NativeCaptureError(f"model sha mismatch: {model_sha} != {EXPECTED_MODEL_SHA256}")

    state_copy = output_root / "state-donor.f32"
    shutil.copyfile(source_root / "state-donor.f32", state_copy)
    prompt_path = output_root / "prompt.utf8"
    prompt_path.write_text(source["prompt"], encoding="utf-8")
    if _sha256_path(prompt_path) != source["prompt_sha256"]:
        raise NativeCaptureError("prompt copy changed during setup")
    if _sha256_path(state_copy) != source["state_sha256"]:
        raise NativeCaptureError("state donor copy changed during setup")

    arms_root = output_root / "arms"
    arms_root.mkdir()
    arm_receipts: dict[str, Mapping[str, Any]] = {}
    arm_paths: dict[str, Path] = {}
    session_kwargs = {
        "runtime_dir": runtime_dir,
        "model_path": model,
        "gpu_layers": gpu_layers,
        "context_tokens": 256,
    }
    with NativeLlamaSession(**session_kwargs) as session:
        for spec in ARM_SPECS:
            name = str(spec["name"])
            trial_dir = arms_root / name
            trial_result = session.graph_trial(
                prompt=source["prompt"],
                output_dir=trial_dir,
                continuation_tokens=source["continuation_tokens"],
                layer=int(spec["layer"]),
                displacement=int(spec["displacement"]),
                injection_scale=float(spec["injection_scale"]),
                substitute=float(spec["substitute"]),
                state_path=state_copy,
                sequence_id=f"ladder-{name}",
            )
            receipt = trial_result["receipt"]
            _validate_arm_config(receipt, spec)
            loaded = load_graph_trial(trial_dir / "graph-trial-receipt.json")
            arm_receipts[name] = loaded
            arm_paths[name] = trial_dir
            print(
                json.dumps(
                    {
                        "arm": name,
                        "output_owner": loaded["graph"]["output_owner"],
                        "logit_owner": loaded["graph"]["logit_owner"],
                        "state_write_owner": loaded["graph"]["qi_state_write_owner"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    arm_rows: list[dict[str, Any]] = []
    for spec in ARM_SPECS:
        name = str(spec["name"])
        trial_dir = arm_paths[name]
        graph_receipt_path = trial_dir / "graph-trial-receipt.json"
        receipt = arm_receipts[name]
        arm_rows.append(
            {
                **spec,
                "receipt_path": f"arms/{name}/graph-trial-receipt.json",
                "receipt_sha256": _sha256_path(graph_receipt_path),
                "graph": receipt["graph"],
                "configuration": receipt["configuration"],
                "logit_steps": receipt["logit_steps"],
                "logits": receipt["logits"],
                "state_successor": receipt["state_successor"],
            }
        )

    body: dict[str, Any] = {
        "schema": "cassi.qwen.native-intervention-ladder.v1",
        "verdict": "MEASURED",
        "model": {
            "filename": model.name,
            "sha256": model_sha,
            "quantization": EXPECTED_QUANTIZATION,
            "gpu_layers": gpu_layers,
        },
        "runtime": {"directory_name": runtime_dir.name},
        "source": {
            "run_name": source_root.name,
            "program_receipt_sha256": source["source_program_receipt_sha256"],
            "program_content_sha256": source["source_program_content_sha256"],
            "capture_receipt_sha256": source["source_capture_receipt_sha256"],
            "graph_receipt_sha256": source["source_graph_receipt_sha256"],
            "prompt_sha256": source["prompt_sha256"],
            "prompt_tokens": source["prompt_tokens"],
            "continuation_tokens": source["continuation_tokens"],
            "state_sha256": source["state_sha256"],
            "state_elements": source["state_elements"],
        },
        "fixed_controls": {
            "layer": EXPECTED_LAYER,
            "decode_steps": EXPECTED_DECODE_STEPS,
            "field_scales": 4,
            "state_predecessor": "state-donor.f32",
            "same_prompt_across_arms": True,
            "same_state_predecessor_across_arms": True,
        },
        "arms": arm_rows,
    }
    analysis = _analyze_arms(arm_receipts, arm_paths)
    body["analysis"] = analysis
    body["content_sha256"] = receipt_digest(body)
    _atomic_json(output_root / "intervention-ladder-receipt.json", body)
    return body




def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=_CASSIQWEN_ROOT / "_diag" / "native-intervention-ladder-27b-iq1s-20260917",
    )
    parser.add_argument("--gpu-layers", type=int, default=99)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = run_ladder(
            model=args.model.resolve(),
            runtime_dir=args.runtime_dir.resolve(),
            source_root=args.source_run.resolve(),
            output_root=args.output_root.resolve(),
            gpu_layers=args.gpu_layers,
        )
    except (NativeCaptureError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "receipt": str((args.output_root.resolve() / "intervention-ladder-receipt.json")),
                "content_sha256": receipt["content_sha256"],
                "arms": len(receipt["arms"]),
                "additive_dose_100_final_l2": receipt["analysis"]["live_signals"]["additive_dose_100_final_l2"],
                "recurrent_dose_100_vs_lesion_final_l2": receipt["analysis"]["live_signals"]["recurrent_dose_100_vs_lesion_final_l2"],
                "head_field_final_l2": receipt["analysis"]["live_signals"]["head_field_final_l2"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
