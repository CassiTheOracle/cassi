"""Focused executable contracts for the deterministic Qi associative KV reference."""

from __future__ import annotations

import tempfile
from pathlib import Path

import torch

from cassi_qi_kv import (
    QiKVConfig,
    QiKVError,
    QiKVMemory,
    load_field_checkpoint,
    save_field_checkpoint,
)


def _config(**kwargs):
    defaults = {
        "mode": "compress",
        "scale_count": 2,
        "head_count": 2,
        "mode_count": 32,
        "key_dim": 4,
        "value_dim": 2,
        "local_window": 2,
        "read_threshold": 0.01,
    }
    defaults.update(kwargs)
    return QiKVConfig(**defaults)


def test_exact_local_window_retrieval_and_position_abstention() -> None:
    memory = QiKVMemory(_config(head_count=1))
    state = memory.initial_state()
    state = memory.deposit(state, 7, [1.0, 2.0], position=4)
    exact = memory.query(state, 7, position=5)
    assert exact.available and exact.exact and exact.local_available
    torch.testing.assert_close(exact.value, torch.tensor([1.0, 2.0]))
    too_old = memory.query(state, 7, position=6)
    assert not too_old.exact
    assert torch.isfinite(too_old.value).all()


def test_repeated_key_and_gap_do_not_return_wrong_local_entry() -> None:
    memory = QiKVMemory(_config(head_count=1, local_window=3))
    state = memory.initial_state()
    state = memory.deposit(state, 9, [1.0, 0.0], position=0)
    state = memory.deposit(state, 4, [0.0, 1.0], position=1)
    state = memory.deposit(state, 9, [3.0, 0.0], position=2)
    latest = memory.query(state, 9, position=2)
    assert latest.exact
    torch.testing.assert_close(latest.value, torch.tensor([3.0, 0.0]))
    old_position = memory.query(state, 9, position=1)
    assert old_position.exact
    torch.testing.assert_close(old_position.value, torch.tensor([1.0, 0.0]))
    far_gap = memory.query(state, 9, position=6)
    assert not far_gap.exact


def test_batch_identity_prevents_local_cross_talk() -> None:
    memory = QiKVMemory(_config(head_count=1, local_window=2))
    state = memory.initial_state(batch_size=2)
    state = memory.deposit(state, 5, [1.0, 0.0], position=0, batch=0)
    state = memory.deposit(state, 5, [0.0, 1.0], position=0, batch=1)
    left = memory.query(state, 5, position=0, batch=0)
    right = memory.query(state, 5, position=0, batch=1)
    torch.testing.assert_close(left.value, torch.tensor([1.0, 0.0]))
    torch.testing.assert_close(right.value, torch.tensor([0.0, 1.0]))
    assert left.exact and right.exact


def test_old_memory_uses_finite_field_retrieval_after_ring_eviction() -> None:
    memory = QiKVMemory(_config(mode="compress", head_count=1, local_window=2))
    state = memory.initial_state()
    for position in range(6):
        state = memory.deposit(state, position, [float(position + 1), float((position + 1) ** 2)], position)
    result = memory.query(state, 0, position=5)
    assert result.available
    assert not result.exact
    assert result.field_available
    assert torch.isfinite(result.value).all()
    assert 0.0 <= result.read_gate <= 1.0


def test_replace_mode_abstains_without_field_signal_and_ignores_external_candidates() -> None:
    memory = QiKVMemory(_config(mode="replace", head_count=1))
    state = memory.initial_state()
    result = memory.query(state, 3, position=0, external_full=[9.0, 9.0], external_local=[8.0, 8.0])
    assert not result.available
    assert result.zero
    torch.testing.assert_close(result.value, torch.zeros(2))


def test_assist_adds_only_qi_gated_field_to_external_candidate() -> None:
    memory = QiKVMemory(_config(mode="assist", scale_count=1, head_count=1))
    state = memory.initial_state()
    state = memory.deposit(state, 3, [1.0, 2.0], position=0)
    result = memory.query(state, 3, position=0, external_full={"value": [4.0, 5.0], "weight": 0.75})
    assert result.available
    assert result.local_weight == 0.75
    assert result.field_weight > 0.0
    assert torch.isfinite(result.value).all()


def test_fixed_bindings_separate_position_layer_head_and_are_reproducible() -> None:
    memory = QiKVMemory(_config(head_count=2, scale_count=2))
    same_left = memory.binding(11, 3, layer=2, head=1, scale=0)
    same_right = memory.binding(11, 3, layer=2, head=1, scale=0)
    assert torch.equal(same_left, same_right)
    for changed in (
        memory.binding(11, 4, layer=2, head=1, scale=0),
        memory.binding(11, 3, layer=3, head=1, scale=0),
        memory.binding(11, 3, layer=2, head=0, scale=0),
        memory.binding(11, 3, layer=2, head=1, scale=1),
    ):
        assert not torch.equal(same_left, changed)
        assert float(torch.linalg.vector_norm(same_left - changed)) > 1.0e-4


def _collision_error(memory: QiKVMemory) -> float:
    state = memory.initial_state()
    sequence = [(position, torch.tensor([float((position % 5) - 2)])) for position in range(20)]
    for position, value in sequence:
        state = memory.deposit(state, position, value, position)
    errors = []
    for position, value in sequence:
        result = memory.query(state, position, position)
        assert result.available
        errors.append(float(torch.mean((result.value - value) ** 2)))
    return sum(errors) / len(errors)


def test_multiscale_consensus_has_lower_or_equal_matched_budget_collision_error() -> None:
    common = {"mode": "replace", "head_count": 1, "key_dim": 4, "value_dim": 1, "read_threshold": 0.001}
    one_scale = QiKVMemory(QiKVConfig.matched_budget(64, scale_count=1, **common))
    multi_scale = QiKVMemory(QiKVConfig.matched_budget(64, scale_count=4, **common))
    assert one_scale.memory_bytes().field_bytes == multi_scale.memory_bytes().field_bytes
    assert _collision_error(multi_scale) <= _collision_error(one_scale) + 1.0e-5


def test_expanded_bank_capacity_accounting_is_explicit() -> None:
    matched = QiKVMemory(QiKVConfig.matched_budget(64, scale_count=4, mode="replace", key_dim=4, value_dim=1))
    expanded = QiKVMemory(QiKVConfig(scale_count=4, mode_count=64, mode="replace", key_dim=4, value_dim=1))
    assert matched.memory_bytes().field_modes == 64
    assert expanded.memory_bytes().field_modes == 256
    assert expanded.memory_bytes().field_bytes == matched.memory_bytes().field_bytes * 4


def test_field_only_checkpoint_restores_full_field_without_local_ring() -> None:
    memory = QiKVMemory(_config(mode="compress", head_count=1))
    state = memory.initial_state()
    state = memory.deposit(state, 3, [1.0, 2.0], position=0)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "qi-field.pt"
        digest = save_field_checkpoint(path, memory, state)
        assert len(digest) == 64
        payload = torch.load(path, map_location="cpu", weights_only=True)
        assert "field" in payload
        assert "binding_descriptor" in payload and "binding_fingerprint" in payload
        assert "local_ring" not in payload
        restored = load_field_checkpoint(path, memory)
        torch.testing.assert_close(restored.field, state.field, rtol=0.0, atol=0.0)
        # The field survives, but the exact ring is not part of the artifact.
        result = memory.query(restored, 3, position=0)
        assert result.available and not result.exact


def test_canonical_q_math_and_bounded_finite_updates() -> None:
    memory = QiKVMemory(_config(mode="replace", scale_count=1, head_count=1, mode_count=16, value_dim=1))
    state = memory.initial_state()
    modes = memory.config.mode_count
    state.field[0, :modes, 0] = 1.0
    state.field[0, 2 * modes : 3 * modes, 0] = memory.config.phi ** -0.5
    balanced = memory.query(state, 0, position=0)
    assert abs(balanced.q - 0.87267799) < 1.0e-5
    state = memory.initial_state()
    for position in range(1000):
        state = memory.deposit(state, position % 23, [1.0e9], position)
    assert torch.isfinite(state.field).all()
    assert float(state.field.abs().max()) <= memory.config.max_field_norm + 1.0e-5
    result = memory.query(state, 0, position=999)
    assert torch.isfinite(result.value).all()
    assert all(torch.isfinite(torch.tensor(value)) for value in (result.q, result.q_max, result.epsilon2_ema, result.chi, result.read_gate))


def test_invalid_configuration_and_nonfinite_updates_are_rejected() -> None:
    try:
        QiKVConfig(scale_primes=(4093, 4099, 4127, 5003))
    except QiKVError:
        pass
    else:
        raise AssertionError("custom codebook primes must be rejected")
    memory = QiKVMemory(_config(mode="replace", head_count=1))
    state = memory.initial_state()
    try:
        memory.deposit(state, 1, [float("nan"), 0.0], position=0)
    except QiKVError:
        pass
    else:
        raise AssertionError("non-finite values must be rejected")


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("Cassi QiKV tests passed")
