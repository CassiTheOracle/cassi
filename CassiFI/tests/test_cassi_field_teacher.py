"""Focused contracts for the optional frozen-teacher boundary."""

from __future__ import annotations
import sys
from pathlib import Path

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from types import SimpleNamespace

import numpy as np

from cassi_field_teacher import (
    CaptureParityReceipt,
    FrozenFieldTeacher,
    FrozenTeacherError,
    PROFILE_ID,
    field_only_checkpoint_payload,
    validate_field_checkpoint_payload,
)
from l18_generated_token_trajectory import RuntimeConfig


def _expect_error(fn, phrase: str) -> None:
    try:
        fn()
    except FrozenTeacherError as error:
        assert phrase in str(error)
        return
    raise AssertionError("expected FrozenTeacherError")


def test_supplied_residual_has_explicit_norm_and_deterministic_wave() -> None:
    teacher = FrozenFieldTeacher(mode_count=32)
    residual = np.arange(64, dtype=np.float32) - 17.0
    first = teacher.from_residual(residual, sequence_id=3, event_index=4)
    second = teacher.from_residual(residual, sequence_id=3, event_index=4)

    assert first.wave.shape == (16, 2)
    assert first.wave.dtype == np.dtype(np.float32)
    assert first.wave.flags.c_contiguous
    assert np.isfinite(first.wave).all()
    np.testing.assert_array_equal(first.wave, second.wave)
    assert first.norm.dimension == 64
    assert first.norm.input_l2_norm > 0.0
    assert abs(first.norm.normalized_l2_norm - 1.0) <= 1.0e-6
    assert first.to_f3_command(session="s0") == {
        "cmd": "sense",
        "session": "s0",
        "wave": [first.wave.tolist()],
    }


def test_capture_reads_only_requested_l18_trunk_vector() -> None:
    teacher = FrozenFieldTeacher(mode_count=32, layer_index=2)
    residual = np.linspace(-2.0, 3.0, 64, dtype=np.float32)
    trunk = tuple(SimpleNamespace(values=np.full(64, index + 1, dtype=np.float32)) for index in range(3))
    record = SimpleNamespace(trunk=trunk)
    parity = CaptureParityReceipt.from_logits(
        np.array([0.0, 2.0, -1.0], dtype=np.float32),
        np.array([0.0, 2.0 + 1.0e-8, -1.0], dtype=np.float32),
        top_ids_off=[1, 0],
        top_ids_on=[1, 0],
    )
    event = teacher.capture(record=record, sequence_id=1, capture_parity=parity)

    assert event.layer_index == 2
    assert event.source == "l18_hidden_residual"
    assert event.capture_parity.parity_pass is True
    assert event.norm.dimension == 64
    assert not any(key in event.to_protocol_payload() for key in ("teacher_state", "teacher_kv", "teacher_logits"))
    assert residual.shape == (64,)


def test_pinned_runtime_config_is_accepted_without_loading_teacher() -> None:
    config = RuntimeConfig(model_path="missing.gguf", dll_dir="missing-runtime", expected_model_sha256="a" * 64)
    teacher = FrozenFieldTeacher(config, mode_count=32)
    assert teacher.runtime_config == config
    assert teacher.layer_index == 0


def test_field_checkpoint_is_teacher_free_and_rejects_forbidden_keys() -> None:
    payload = field_only_checkpoint_payload(np.zeros((256, 2), dtype=np.float32))
    assert payload["schema"].endswith("field-only-checkpoint.v1")
    assert payload["profile"] == PROFILE_ID
    assert payload["checkpoint"]["field_only"] is True
    assert payload["checkpoint"]["teacher_data_persisted"] is False
    validate_field_checkpoint_payload(payload)

    _expect_error(
        lambda: validate_field_checkpoint_payload(
            {"field": np.zeros(1), "teacher_state": np.zeros(1)}
        ),
        "excluded teacher data",
    )


def test_zero_or_undersized_residual_is_rejected() -> None:
    teacher = FrozenFieldTeacher(mode_count=32)
    _expect_error(
        lambda: teacher.from_residual(np.zeros(64, dtype=np.float32)),
        "L2 norm",
    )
    _expect_error(
        lambda: FrozenFieldTeacher(mode_count=128).from_residual(
            np.ones(64, dtype=np.float32)
        ),
        "available DFT bins",
    )

if __name__ == "__main__":
    test_supplied_residual_has_explicit_norm_and_deterministic_wave()
    test_capture_reads_only_requested_l18_trunk_vector()
    test_pinned_runtime_config_is_accepted_without_loading_teacher()
    test_field_checkpoint_is_teacher_free_and_rejects_forbidden_keys()
    test_zero_or_undersized_residual_is_rejected()
    print("Cassi frozen-teacher tests passed")
