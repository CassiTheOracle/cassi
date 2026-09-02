"""Export the canonical language checkpoint and an independent native-op oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import sys

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from canonical_native_qi_oracle import NativeQiParameters, native_qi_step

from cassi_field_language import CassiQiTextEngine
from cassi_qi_field import QiFieldConfig, QiFieldController

DEFAULT_CONFIG = ROOT / "configs" / "cassi-qi-corpus-language.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts" / "cassi-qi-corpus-language" / "field-state.pt"
DEFAULT_OUTPUT = WORKSPACE / "CassiQwen" / "_diag" / "canonical-native-qi-v1"
SCHEMA = "cassi.qi.native-contract.v1"
STATE_MODE_COUNT = 6144
WAVE_MODE_COUNT = 3072
QWEN_HIDDEN_DIMENSION = 5120
HORIZONS = (0, 1, 4)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_array(path: Path, value: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(value)
    path.write_bytes(contiguous.tobytes())
    return {
        "path": path.name,
        "dtype": str(contiguous.dtype),
        "shape": list(contiguous.shape),
        "bytes": int(contiguous.nbytes),
        "sha256": _sha256(path),
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def export_fixture(config_path: Path, checkpoint_path: Path, output_dir: Path) -> dict[str, Any]:
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    config = QiFieldConfig.from_dict(config_payload)
    if (
        config.scale_count != 4
        or config.mode_count != STATE_MODE_COUNT
        or config.wave_mode_count != WAVE_MODE_COUNT
    ):
        raise ValueError("the native contract requires canonical S=4, M=6144, W=3072")
    controller = QiFieldController(config)
    engine = CassiQiTextEngine(controller, checkpoint_path=checkpoint_path)
    state = engine.initial_state(device="cpu", dtype=torch.float32)
    source = state.field.reshape(config.scale_count, 9, config.mode_count, 1)
    native_state = np.ascontiguousarray(
        source.permute(3, 0, 2, 1).numpy(),
        dtype=np.float32,
    )

    hidden_index = np.arange(QWEN_HIDDEN_DIMENSION, dtype=np.float32)
    hidden = np.sin(hidden_index * np.float32(0.017)) + np.cos(hidden_index * np.float32(0.031))
    norm = np.linalg.norm(hidden.astype(np.float64))
    if not np.isfinite(norm) or norm <= 0.0:
        raise ValueError("deterministic hidden fixture has an invalid norm")
    hidden = np.asarray(hidden.astype(np.float64) / norm, dtype=np.float32)
    sense = np.zeros((1, WAVE_MODE_COUNT, 2), dtype=np.float32)
    sense[0, : QWEN_HIDDEN_DIMENSION // 2] = hidden.reshape(-1, 2)
    recovered = sense[0, : QWEN_HIDDEN_DIMENSION // 2].reshape(-1)
    boundary_error = float(np.max(np.abs(recovered.astype(np.float64) - hidden.astype(np.float64))))

    mode_params = np.linspace(
        config.physics.slow_damping,
        config.physics.fast_damping,
        config.mode_count,
        dtype=np.float32,
    )
    sequence_ids = np.asarray((0,), dtype=np.int32)
    parameters = NativeQiParameters(
        scale_count=config.scale_count,
        steps=config.settle_steps,
        phi=config.phi,
        dt=config.physics.dt,
        coupling=config.correction_gain,
        damping_min=config.physics.slow_damping,
        damping_max=config.physics.fast_damping,
        epsilon_tau=config.epsilon_tau,
        scale_ratio=float(config.scale_ratio),
        energy_floor=config.energy_floor,
        read_floor=config.read_floor,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {
        "state_h0": _write_array(output_dir / "state-h0.f32", native_state),
        "sense": _write_array(output_dir / "sense.f32", sense),
        "mode_params": _write_array(output_dir / "mode-params.f32", mode_params),
        "sequence_ids": _write_array(output_dir / "sequence-ids.i32", sequence_ids),
    }
    for horizon in HORIZONS[1:]:
        working = native_state.copy()
        flux = np.empty((0,), dtype=np.float32)
        diagnostics = np.empty((0,), dtype=np.float32)
        for _ in range(horizon):
            flux, working, diagnostics = native_qi_step(
                sense,
                working,
                mode_params,
                sequence_ids,
                parameters,
            )
        arrays[f"flux_h{horizon}"] = _write_array(output_dir / f"flux-h{horizon}.f32", flux)
        arrays[f"state_h{horizon}"] = _write_array(output_dir / f"state-h{horizon}.f32", working)
        arrays[f"diagnostics_h{horizon}"] = _write_array(
            output_dir / f"diagnostics-h{horizon}.f32",
            diagnostics,
        )

    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "config": {
            "path": str(config_path.resolve()),
            "sha256": _sha256(config_path),
            "fingerprint": config.fingerprint,
        },
        "checkpoint": {
            "path": str(checkpoint_path.resolve()),
            "sha256": _sha256(checkpoint_path),
            "state_sha256": engine.state_sha256(state),
            "trained_memory_sha256": engine.corpus_memory_sha256,
        },
        "layout": {
            "python": "scale-component-mode-batch",
            "native": "batch-scale-mode-component",
            "component_order": [
                "Y_re",
                "Y_im",
                "I_re",
                "I_im",
                "VY_re",
                "VY_im",
                "VI_re",
                "VI_im",
                "epsilon2_ema",
            ],
            "state_shape_python": list(state.field.shape),
            "state_shape_native": list(native_state.shape),
            "state_mode_count": STATE_MODE_COUNT,
            "wave_mode_count": WAVE_MODE_COUNT,
        },
        "boundary": {
            "qwen_hidden_dimension": QWEN_HIDDEN_DIMENSION,
            "normalization": "float64-l2-then-float32",
            "packing": "adjacent-real-pairs-to-complex",
            "occupied_complex_modes": QWEN_HIDDEN_DIMENSION // 2,
            "zero_padded_complex_modes": WAVE_MODE_COUNT - QWEN_HIDDEN_DIMENSION // 2,
            "unobserved_state_modes": STATE_MODE_COUNT - WAVE_MODE_COUNT,
            "unobserved_state_mode_source": "zero",
            "emitted_flux_modes": WAVE_MODE_COUNT,
            "roundtrip_max_abs": boundary_error,
        },
        "transition": {
            "operator": "ggml_cassi_qi_field_step.v2",
            "one_observation_per_step": True,
            "state_out_is_next_state_in": True,
            "parameters": parameters.__dict__,
            "horizons": list(HORIZONS),
        },
        "arrays": arrays,
    }
    contract["contract_sha256"] = hashlib.sha256(_canonical_json(contract)).hexdigest()
    contract_path = output_dir / "contract.json"
    contract_path.write_bytes(_canonical_json(contract) + b"\n")
    summary = {
        "schema": SCHEMA,
        "contract": str(contract_path.resolve()),
        "contract_sha256": contract["contract_sha256"],
        "checkpoint_sha256": contract["checkpoint"]["sha256"],
        "state_sha256": contract["checkpoint"]["state_sha256"],
        "boundary_roundtrip_max_abs": boundary_error,
        "verdict": "PASS",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export_fixture(args.config.resolve(), args.checkpoint.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
