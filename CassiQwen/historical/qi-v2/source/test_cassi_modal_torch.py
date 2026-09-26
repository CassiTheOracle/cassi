"""Focused tests for the differentiable native-parity modal mirror."""

from __future__ import annotations

import math

import numpy as np
import torch

from cassi_modal_torch import (
    CassiFieldAdapter,
    CassiModalConfig,
    cassi_modal_forward,
    cassi_modal_forward_parallel,
    native_mode_params,
    pack_native_output,
)


def _numpy_native_oracle(
    layer_modes: np.ndarray,
    state: np.ndarray,
    mode_params: np.ndarray,
    seq_ids: np.ndarray,
    config: CassiModalConfig,
) -> tuple[np.ndarray, np.ndarray]:
    mode_count = layer_modes.shape[0] // 2
    layer_count = layer_modes.shape[1]
    token_count = layer_modes.shape[2]
    sequence_count = state.shape[1]
    work = state.T.reshape(sequence_count, mode_count, 8).copy()
    correction = np.zeros((2 * mode_count, token_count), dtype=layer_modes.dtype)
    retained = config.retained_weight
    incoming = 1.0 - retained

    for token in range(token_count):
        sequence = int(seq_ids[token])
        for layer in range(layer_count):
            for mode in range(mode_count):
                signal_re = layer_modes[2 * mode + 0, layer, token]
                signal_im = layer_modes[2 * mode + 1, layer, token]
                values = work[sequence, mode]
                values[0] = retained * values[0] + incoming * 0.5 * signal_re
                values[1] = retained * values[1] + incoming * 0.5 * signal_im
                values[2] = retained * values[2] - incoming * 0.5 / config.phi * signal_re
                values[3] = retained * values[3] - incoming * 0.5 / config.phi * signal_im

                for _ in range(config.steps_per_layer):
                    diff_re = values[0] - config.phi * values[2]
                    diff_im = values[1] - config.phi * values[3]
                    acc_y_re = (mode_params[mode] - config.omega2) * values[0] + config.omega2 * config.phi * values[2]
                    acc_y_im = (mode_params[mode] - config.omega2) * values[1] + config.omega2 * config.phi * values[3]
                    acc_i_re = mode_params[mode] * values[2] + config.omega2 * diff_re
                    acc_i_im = mode_params[mode] * values[3] + config.omega2 * diff_im
                    values[4] += acc_y_re * config.dt
                    values[5] += acc_y_im * config.dt
                    values[6] += acc_i_re * config.dt
                    values[7] += acc_i_im * config.dt
                    values[0] += values[4] * config.dt
                    values[1] += values[5] * config.dt
                    values[2] += values[6] * config.dt
                    values[3] += values[7] * config.dt

        correction[2 * np.arange(mode_count), token] = config.coupling * (
            work[sequence, :, 0] - config.phi * work[sequence, :, 2]
        )
        correction[2 * np.arange(mode_count) + 1, token] = -config.coupling * (
            work[sequence, :, 1] - config.phi * work[sequence, :, 3]
        )

    return correction, work.reshape(sequence_count, 8 * mode_count).T.copy()


def test_native_mode_symbols_are_reproducible() -> None:
    symbols = native_mode_params(6, dtype=torch.float64)
    expected = np.array([0.0, -0.0320245326613, -0.1268674458145, -0.2808839794958, -0.4881553646891, -0.7407162783007])
    np.testing.assert_allclose(symbols.detach().numpy(), expected, atol=2.0e-9, rtol=0.0)

def test_interleaved_sequence_forward_matches_native_oracle() -> None:
    torch.manual_seed(11)
    config = CassiModalConfig(retained_weight=0.87, phi=1.61803398875, dt=0.003, omega2=11.0, coupling=0.75, steps_per_layer=3)
    mode_count, layer_count, token_count, sequence_count = 3, 2, 7, 3
    layer_modes = torch.randn(2 * mode_count, layer_count, token_count, dtype=torch.float64)
    state = torch.randn(8 * mode_count, sequence_count, dtype=torch.float64)
    mode_params = native_mode_params(mode_count, dtype=torch.float64)
    seq_ids = torch.tensor([0, 2, 1, 0, 2, 1, 0], dtype=torch.int64)

    actual = cassi_modal_forward(layer_modes, state, mode_params, seq_ids, config)
    expected_correction, expected_state = _numpy_native_oracle(
        layer_modes.detach().numpy(), state.detach().numpy(), mode_params.detach().numpy(), seq_ids.numpy(), config
    )

    np.testing.assert_allclose(actual.correction.detach().numpy(), expected_correction, atol=2.0e-12, rtol=0.0)
    np.testing.assert_allclose(actual.state.detach().numpy(), expected_state, atol=2.0e-12, rtol=0.0)
    packed = pack_native_output(actual).detach().numpy()
    expected_packed = np.concatenate((expected_correction.T.reshape(-1), expected_state.T.reshape(-1)))
    np.testing.assert_allclose(packed, expected_packed, atol=2.0e-12, rtol=0.0)
def test_parallel_batch_matches_interleaved_routing() -> None:
    torch.manual_seed(17)
    mode_count, layer_count, batch_size, horizon = 2, 2, 3, 5
    layer_modes = torch.randn(2 * mode_count, layer_count, batch_size, horizon, dtype=torch.float64)
    state = torch.randn(8 * mode_count, batch_size, dtype=torch.float64)
    mode_params = native_mode_params(mode_count, dtype=torch.float64)
    config = CassiModalConfig(retained_weight=0.91, dt=0.004, omega2=13.0, coupling=0.8, steps_per_layer=2)

    parallel = cassi_modal_forward_parallel(layer_modes, state, mode_params, config)
    flattened = layer_modes.permute(0, 1, 3, 2).reshape(2 * mode_count, layer_count, horizon * batch_size)
    sequence_ids = torch.arange(batch_size, dtype=torch.int64).repeat(horizon)
    routed = cassi_modal_forward(flattened, state, mode_params, sequence_ids, config)
    expected_correction = routed.correction.reshape(2 * mode_count, horizon, batch_size).permute(0, 2, 1)

    torch.testing.assert_close(parallel.correction, expected_correction, atol=1.0e-12, rtol=0.0)
    torch.testing.assert_close(parallel.state, routed.state, atol=1.0e-12, rtol=0.0)

def test_parallel_batch_has_finite_gradients() -> None:
    torch.manual_seed(29)
    mode_count, layer_count, batch_size, horizon = 2, 1, 3, 4
    layer_modes = torch.randn(2 * mode_count, layer_count, batch_size, horizon, dtype=torch.float64, requires_grad=True)
    state = torch.randn(8 * mode_count, batch_size, dtype=torch.float64, requires_grad=True)
    mode_params = native_mode_params(mode_count, dtype=torch.float64).detach().requires_grad_()

    output = cassi_modal_forward_parallel(layer_modes, state, mode_params)
    (output.correction.square().mean() + output.state.square().mean()).backward()

    for tensor in (layer_modes, state, mode_params):
        assert tensor.grad is not None
        assert torch.isfinite(tensor.grad).all()
        assert float(tensor.grad.abs().sum()) > 0.0


def test_modal_recurrence_has_finite_nonzero_gradients() -> None:
    torch.manual_seed(19)
    mode_count, layer_count, token_count, sequence_count = 2, 2, 5, 2
    layer_modes = torch.randn(2 * mode_count, layer_count, token_count, dtype=torch.float64, requires_grad=True)
    state = torch.randn(8 * mode_count, sequence_count, dtype=torch.float64, requires_grad=True)
    mode_params = native_mode_params(mode_count, dtype=torch.float64).detach().requires_grad_()
    seq_ids = torch.tensor([0, 1, 0, 1, 0], dtype=torch.int64)

    output = cassi_modal_forward(layer_modes, state, mode_params, seq_ids)
    loss = output.correction.square().mean() + output.state.square().mean()
    loss.backward()

    for tensor in (layer_modes, state, mode_params):
        assert tensor.grad is not None
        assert torch.isfinite(tensor.grad).all()
        assert float(tensor.grad.abs().sum()) > 0.0


def test_adapter_starts_as_identity_and_learns_bounded_residual() -> None:
    torch.manual_seed(23)
    adapter = CassiFieldAdapter(8, bottleneck=3, max_scale=0.25)
    hidden = torch.randn(8, 4, dtype=torch.float64)
    field = torch.randn(8, 4, dtype=torch.float64)
    adapter = adapter.to(dtype=torch.float64)

    initial = adapter(hidden, field)
    torch.testing.assert_close(initial.hidden, hidden)
    assert torch.all(initial.gate == 0.125)

    initial.hidden.sum().backward()
    assert adapter.up.weight.grad is not None
    assert torch.isfinite(adapter.up.weight.grad).all()
    assert float(adapter.up.weight.grad.abs().sum()) > 0.0
    assert float(initial.gate.detach().abs().max()) <= 0.25


if __name__ == "__main__":
    test_native_mode_symbols_are_reproducible()
    test_interleaved_sequence_forward_matches_native_oracle()
    test_parallel_batch_matches_interleaved_routing()
    test_parallel_batch_has_finite_gradients()
    test_modal_recurrence_has_finite_nonzero_gradients()
    test_adapter_starts_as_identity_and_learns_bounded_residual()
    print("differentiable Cassi modal tests passed")
