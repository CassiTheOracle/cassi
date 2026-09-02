"""Independent scalar oracle for the native canonical Qi field step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class NativeQiParameters:
    scale_count: int
    steps: int
    phi: float
    dt: float
    coupling: float
    damping_min: float
    damping_max: float
    epsilon_tau: float
    scale_ratio: float
    energy_floor: float
    read_floor: float

def _f(value: Any) -> np.float32:
    return np.float32(value)

def _clamp(value: Any, low: Any, high: Any) -> np.float32:
    return _f(min(max(_f(value), _f(low)), _f(high)))


def _state_value(value: np.float32) -> np.float32:
    return _clamp(value, -64.0, 64.0) if np.isfinite(value) else _f(0.0)


def _chirp(scale: int, mode: int) -> tuple[np.float32, np.float32]:
    primes = (4093, 4099, 4127, 4133)
    cosine = (
        1.0, 0.9238795325, 0.7071067812, 0.3826834324,
        0.0, -0.3826834324, -0.7071067812, -0.9238795325,
        -1.0, -0.9238795325, -0.7071067812, -0.3826834324,
        0.0, 0.3826834324, 0.7071067812, 0.9238795325,
    )
    sine = (
        0.0, 0.3826834324, 0.7071067812, 0.9238795325,
        1.0, 0.9238795325, 0.7071067812, 0.3826834324,
        0.0, -0.3826834324, -0.7071067812, -0.9238795325,
        -1.0, -0.9238795325, -0.7071067812, -0.3826834324,
    )
    index = (mode * mode + mode * primes[scale & 3] + 17 * scale) & 15
    return _f(cosine[index]), _f(sine[index])


def _metrics(
    ey_re: np.float32,
    ey_im: np.float32,
    ei_re: np.float32,
    ei_im: np.float32,
    epsilon2_ema: np.float32,
    phi: np.float32,
    energy_floor: np.float32,
) -> tuple[np.float32, np.float32, np.float32, bool]:
    e_y = _f(ey_re * ey_re + ey_im * ey_im)
    e_i = _f(ei_re * ei_re + ei_im * ei_im)
    rho = _clamp(_f(e_y + e_i), 0.0, 64.0)
    inv_phi2 = _f(_f(1.0) / _f(phi * phi))
    rho2 = _f(rho * rho)
    denominator = _f(rho2 + inv_phi2 + max(epsilon2_ema, _f(0.0)))
    q = _clamp(_f(rho2 / denominator), 0.0, 1.0) if denominator > 0.0 else _f(0.0)
    q_max = _f(rho2 / _f(rho2 + inv_phi2))
    available = bool(rho > energy_floor)
    chi = _clamp(_f(q / q_max), 0.0, 1.0) if available and q_max > 0.0 else _f(0.0)
    return rho, q, chi, available



def _row_metrics(
    row: np.ndarray,
    phi: np.float32,
    energy_floor: np.float32,
) -> tuple[np.float32, np.float32, np.float32, bool]:
    return _metrics(
        row[0],
        row[1],
        row[2],
        row[3],
        max(row[8], _f(0.0)),
        phi,
        energy_floor,
    )
def native_qi_step(
    sense: np.ndarray,
    state: np.ndarray,
    mode_params: np.ndarray,
    sequence_ids: np.ndarray,
    parameters: NativeQiParameters,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply the native contract without importing production implementation.

    ``sense`` has shape ``[T,W,2]`` and native state has shape ``[B,S,M,9]``.
    Modes ``W..M-1`` receive zero external source and do not emit boundary flux.
    """

    sense = np.ascontiguousarray(sense, dtype=np.float32)
    state = np.ascontiguousarray(state, dtype=np.float32)
    mode_params = np.ascontiguousarray(mode_params, dtype=np.float32)
    sequence_ids = np.ascontiguousarray(sequence_ids, dtype=np.int32)
    if sense.ndim != 3 or sense.shape[2] != 2:
        raise ValueError("sense must have shape [T,W,2]")
    if state.ndim != 4 or state.shape[3] != 9:
        raise ValueError("state must have shape [B,S,M,9]")
    batch_count, scale_count, state_mode_count, _ = state.shape
    token_count, wave_mode_count, _ = sense.shape
    if scale_count != parameters.scale_count:
        raise ValueError("state scale count does not match parameters")
    if not 0 < wave_mode_count <= state_mode_count:
        raise ValueError("wave mode count must be within the state mode count")
    if mode_params.shape != (state_mode_count,):
        raise ValueError("mode_params shape does not match state mode count")
    if sequence_ids.shape != (token_count,):
        raise ValueError("sequence_ids shape does not match token count")

    phi = _f(parameters.phi)
    dt_base = _clamp(_f(parameters.dt), 1.0e-6, 0.25)
    coupling = _f(parameters.coupling)
    damping_min = _f(parameters.damping_min)
    damping_max = _f(parameters.damping_max)
    epsilon_tau = _f(parameters.epsilon_tau)
    alpha = _clamp(_f(dt_base / epsilon_tau), 0.0, 1.0)
    scale_ratio = _f(parameters.scale_ratio)
    energy_floor = _f(parameters.energy_floor)
    read_floor = _f(parameters.read_floor)

    flux = np.zeros((token_count, wave_mode_count, 2), dtype=np.float32)
    state_out = np.empty_like(state)
    diagnostics = np.zeros((batch_count, scale_count, 10), dtype=np.float32)

    for sequence in range(batch_count):
        diag_sum = np.zeros((scale_count, 10), dtype=np.float32)
        for mode in range(state_mode_count):
            work = np.empty((scale_count, 9), dtype=np.float32)
            last_write = np.zeros(scale_count, dtype=np.float32)
            last_consolidation = np.zeros(scale_count, dtype=np.float32)
            for scale in range(scale_count):
                for component in range(9):
                    work[scale, component] = _state_value(state[sequence, scale, mode, component])

            for token in range(token_count):
                if int(sequence_ids[token]) != sequence:
                    if sequence == 0 and mode < wave_mode_count:
                        flux[token, mode] = 0.0
                    continue

                rho_local = np.zeros(scale_count, dtype=np.float32)
                q_local = np.zeros(scale_count, dtype=np.float32)
                chi_local = np.zeros(scale_count, dtype=np.float32)
                available_local = np.zeros(scale_count, dtype=np.bool_)
                read_re = _f(0.0)
                read_im = _f(0.0)
                chi_sum = _f(0.0)
                available_count = 0
                for scale in range(scale_count):
                    rho, q, chi, available = _row_metrics(
                        work[scale], phi, energy_floor
                    )
                    rho_local[scale] = rho
                    q_local[scale] = q
                    chi_local[scale] = chi
                    available_local[scale] = available
                    if available:
                        d_re = _f(work[scale, 0] - phi * work[scale, 2])
                        d_im = _f(work[scale, 1] - phi * work[scale, 3])
                        norm = _f(_f(1.0) / np.sqrt(max(rho, _f(1.0e-12))))
                        read_re = _f(read_re + chi * d_re * norm)
                        read_im = _f(read_im + chi * d_im * norm)
                        chi_sum = _f(chi_sum + chi)
                        available_count += 1

                phase_sum = _f(0.0)
                phase_count = 0
                for scale in range(1, scale_count):
                    if available_local[scale - 1] and available_local[scale]:
                        d0_re = _f(work[scale - 1, 0] - phi * work[scale - 1, 2])
                        d0_im = _f(work[scale - 1, 1] - phi * work[scale - 1, 3])
                        d1_re = _f(work[scale, 0] - phi * work[scale, 2])
                        d1_im = _f(work[scale, 1] - phi * work[scale, 3])
                        denom = np.sqrt(max(_f(rho_local[scale - 1] * rho_local[scale]), _f(1.0e-12)))
                        phase_sum = _f(
                            phase_sum
                            + _clamp(_f(_f(0.5) + _f(0.5) * _f(d0_re * d1_re + d0_im * d1_im) / denom), 0.0, 1.0)
                        )
                        phase_count += 1
                cross = (
                    _f(phase_sum / _f(phase_count))
                    if phase_count > 0
                    else (_f(1.0) if available_local[0] else _f(0.0))
                )
                read_gate = (
                    _clamp(_f(_f(chi_sum / _f(available_count)) * cross), 0.0, 1.0)
                    if available_count > 0
                    else _f(0.0)
                )
                if mode < wave_mode_count:
                    if read_gate >= read_floor and available_count > 0:
                        flux[token, mode, 0] = _f(coupling * read_gate * read_re / _f(available_count))
                        flux[token, mode, 1] = _f(coupling * read_gate * read_im / _f(available_count))
                    else:
                        flux[token, mode] = 0.0

                signal_re = sense[token, mode, 0] if mode < wave_mode_count else _f(0.0)
                signal_im = sense[token, mode, 1] if mode < wave_mode_count else _f(0.0)
                chirp_re, chirp_im = _chirp(0, mode)
                source_re = _f(chirp_re * signal_re - chirp_im * signal_im)
                source_im = _f(chirp_re * signal_im + chirp_im * signal_re)
                source_energy = _f(source_re * source_re + source_im * source_im)
                structured_source = _clamp(_f(source_energy / _f(_f(1.0) + source_energy)), 0.0, 1.0)
                write_gate = _f(1.0) if not available_local[0] else _f(structured_source * _f(_f(1.0) - q_local[0]))
                write_gain = _clamp(_f(dt_base * write_gate), 0.0, 0.5)
                last_write[0] = write_gate
                work[0, 0] = _state_value(_f(_f(_f(1.0) - write_gain) * work[0, 0] + _f(0.5) * write_gain * source_re))
                work[0, 1] = _state_value(_f(_f(_f(1.0) - write_gain) * work[0, 1] + _f(0.5) * write_gain * source_im))
                work[0, 2] = _state_value(_f(_f(_f(1.0) - write_gain) * work[0, 2] - _f(0.5) * write_gain * source_re / phi))
                work[0, 3] = _state_value(_f(_f(_f(1.0) - write_gain) * work[0, 3] - _f(0.5) * write_gain * source_im / phi))

                for _ in range(parameters.steps):
                    damping = _clamp(abs(mode_params[mode]), damping_min, damping_max)
                    diff_re = _f(work[0, 0] - phi * work[0, 2])
                    diff_im = _f(work[0, 1] - phi * work[0, 3])
                    ay_re = _f(diff_re - damping * work[0, 4])
                    ay_im = _f(diff_im - damping * work[0, 5])
                    ai_re = _f(-diff_re / phi - damping * work[0, 6])
                    ai_im = _f(-diff_im / phi - damping * work[0, 7])
                    work[0, 4] = _state_value(_f(work[0, 4] + ay_re * dt_base))
                    work[0, 5] = _state_value(_f(work[0, 5] + ay_im * dt_base))
                    work[0, 6] = _state_value(_f(work[0, 6] + ai_re * dt_base))
                    work[0, 7] = _state_value(_f(work[0, 7] + ai_im * dt_base))
                    work[0, 0] = _state_value(_f(work[0, 0] + work[0, 4] * dt_base))
                    work[0, 1] = _state_value(_f(work[0, 1] + work[0, 5] * dt_base))
                    work[0, 2] = _state_value(_f(work[0, 2] + work[0, 6] * dt_base))
                    work[0, 3] = _state_value(_f(work[0, 3] + work[0, 7] * dt_base))
                e_y = _f(work[0, 0] * work[0, 0] + work[0, 1] * work[0, 1])
                e_i = _f(work[0, 2] * work[0, 2] + work[0, 3] * work[0, 3])
                epsilon = _f(e_y - phi * e_i)
                work[0, 8] = _state_value(
                    _f(_f(_f(1.0) - alpha) * max(work[0, 8], _f(0.0)) + alpha * _clamp(_f(epsilon * epsilon), 0.0, 64.0))
                )

                scale_dt = dt_base
                for scale in range(1, scale_count):
                    scale_dt = _clamp(_f(scale_dt / max(scale_ratio, _f(1.0e-6))), 1.0e-6, 0.25)
                    source_rho, _, source_chi, source_available = _row_metrics(
                        work[scale - 1], phi, energy_floor
                    )
                    target_rho, target_q, _, target_available = _row_metrics(
                        work[scale], phi, energy_floor
                    )
                    sd_re = _f(work[scale - 1, 0] - phi * work[scale - 1, 2])
                    sd_im = _f(work[scale - 1, 1] - phi * work[scale - 1, 3])
                    td_re = _f(work[scale, 0] - phi * work[scale, 2])
                    td_im = _f(work[scale, 1] - phi * work[scale, 3])
                    j_scale = _f(sd_re * td_im - sd_im * td_re)
                    denom = np.sqrt(max(_f(source_rho * target_rho), _f(1.0e-12)))
                    phase = _clamp(_f(_f(0.5) + _f(0.5) * _f(sd_re * td_re + sd_im * td_im) / denom), 0.0, 1.0)
                    gain = _f(0.0)
                    if source_available:
                        target_open = _f(_f(1.0) - target_q)
                        if not target_available:
                            gain = _f(scale_dt * source_chi)
                        elif phase >= _f(0.5) and j_scale >= _f(0.0):
                            gain = _f(scale_dt * source_chi * phase * _clamp(_f(j_scale / denom), 0.0, 1.0) * target_open)
                    gain = _clamp(gain, 0.0, 0.5)
                    last_consolidation[scale] = gain
                    for component in range(9):
                        work[scale, component] = _state_value(
                            _f(_f(_f(1.0) - gain) * work[scale, component] + gain * work[scale - 1, component])
                        )

                final_read_re = _f(0.0)
                final_read_im = _f(0.0)
                final_chi_sum = _f(0.0)
                final_available = 0
                for scale in range(scale_count):
                    rho, _, chi, available = _row_metrics(
                        work[scale], phi, energy_floor
                    )
                    if available:
                        d_re = _f(work[scale, 0] - phi * work[scale, 2])
                        d_im = _f(work[scale, 1] - phi * work[scale, 3])
                        norm = _f(_f(1.0) / np.sqrt(max(rho, _f(1.0e-12))))
                        final_read_re = _f(final_read_re + chi * d_re * norm)
                        final_read_im = _f(final_read_im + chi * d_im * norm)
                        final_chi_sum = _f(final_chi_sum + chi)
                        final_available += 1
                final_gate = _clamp(_f(final_chi_sum / _f(final_available)), 0.0, 1.0) if final_available else _f(0.0)
                if mode < wave_mode_count:
                    if final_available and final_gate >= read_floor:
                        flux[token, mode, 0] = _f(coupling * final_gate * final_read_re / _f(final_available))
                        flux[token, mode, 1] = _f(coupling * final_gate * final_read_im / _f(final_available))
                    else:
                        flux[token, mode] = 0.0

            rho_final = np.zeros(scale_count, dtype=np.float32)
            available_final = np.zeros(scale_count, dtype=np.bool_)
            for scale in range(scale_count):
                rho, _, _, available = _row_metrics(
                    work[scale], phi, energy_floor
                )
                rho_final[scale] = rho
                available_final[scale] = available
            final_phase_sum = _f(0.0)
            final_phase_count = 0
            for scale in range(1, scale_count):
                if available_final[scale - 1] and available_final[scale]:
                    d0_re = _f(work[scale - 1, 0] - phi * work[scale - 1, 2])
                    d0_im = _f(work[scale - 1, 1] - phi * work[scale - 1, 3])
                    d1_re = _f(work[scale, 0] - phi * work[scale, 2])
                    d1_im = _f(work[scale, 1] - phi * work[scale, 3])
                    denom = np.sqrt(max(_f(rho_final[scale - 1] * rho_final[scale]), _f(1.0e-12)))
                    final_phase_sum = _f(
                        final_phase_sum
                        + _clamp(_f(_f(0.5) + _f(0.5) * _f(d0_re * d1_re + d0_im * d1_im) / denom), 0.0, 1.0)
                    )
                    final_phase_count += 1
            final_cross = (
                _f(final_phase_sum / _f(final_phase_count))
                if final_phase_count
                else (_f(1.0) if available_final[0] else _f(0.0))
            )
            for scale in range(scale_count):
                rho, q, chi, available = _row_metrics(
                    work[scale], phi, energy_floor
                )
                d_re = _f(work[scale, 0] - phi * work[scale, 2])
                d_im = _f(work[scale, 1] - phi * work[scale, 3])
                dd_re = _f(work[scale, 4] - phi * work[scale, 6])
                dd_im = _f(work[scale, 5] - phi * work[scale, 7])
                j_temporal = _clamp(_f(d_re * dd_im - d_im * dd_re), -64.0, 64.0)
                j_scale = _f(0.0)
                if scale + 1 < scale_count:
                    nd_re = _f(work[scale + 1, 0] - phi * work[scale + 1, 2])
                    nd_im = _f(work[scale + 1, 1] - phi * work[scale + 1, 3])
                    j_scale = _clamp(_f(d_re * nd_im - d_im * nd_re), -64.0, 64.0)
                read_gate = _clamp(_f(chi * final_cross), 0.0, 1.0) if available else _f(0.0)
                values = (
                    rho,
                    q,
                    chi,
                    j_temporal,
                    j_scale,
                    read_gate,
                    final_cross if available else _f(0.0),
                    _clamp(last_write[scale], 0.0, 1.0) if available else _f(0.0),
                    _clamp(last_consolidation[scale], 0.0, 1.0) if scale > 0 else _f(0.0),
                    _f(1.0) if available else _f(0.0),
                )
                for component, value in enumerate(values):
                    diag_sum[scale, component] = _f(diag_sum[scale, component] + value)
                state_out[sequence, scale, mode] = work[scale]

        diagnostics[sequence] = diag_sum / _f(state_mode_count)

    return flux, state_out, diagnostics
