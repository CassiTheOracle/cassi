"""What is the Cassi qi field as a memory? A measurement against the pinned rule.

Ports `ggml_compute_forward_cassi_qi_field_step_f32` (CassiQwen/native/llama.cpp,
ggml/src/ggml-cpu/ops.cpp:11109) at production defaults and measures the four
properties that decide whether the field can stand in for a KV cache:

  1. the readout's weight against token age -- its implicit attention profile,
  2. the state's own decay per mode and scale -- its memory span in tokens,
  3. how many distinct items one mode can hold -- its capacity under the write rule,
  4. whether the mode bank can express a graded, local profile at all.

Read-only study: it imports nothing from the fork and changes nothing in it.
Writes _diag/field-memory-study/study.json and prints a report.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import nnls

PHI = 1.618033988749895
INV_PHI2 = 1.0 / (PHI * PHI)
STATE_CLAMP = 64.0
PRIMES = (4093, 4099, 4127, 4133)

_C = np.array([1.0, 0.9238795325, 0.7071067812, 0.3826834324,
               0.0, -0.3826834324, -0.7071067812, -0.9238795325,
               -1.0, -0.9238795325, -0.7071067812, -0.3826834324,
               0.0, 0.3826834324, 0.7071067812, 0.9238795325])
_S = np.array([0.0, 0.3826834324, 0.7071067812, 0.9238795325,
               1.0, 0.9238795325, 0.7071067812, 0.3826834324,
               0.0, -0.3826834324, -0.7071067812, -0.9238795325,
               -1.0, -0.9238795325, -0.7071067812, -0.3826834324])


def chirp(scale: int, modes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = modes.astype(np.uint64)
    index = (m * m + m * np.uint64(PRIMES[scale & 3]) + np.uint64(17 * scale)) & np.uint64(15)
    return _C[index.astype(np.int64)], _S[index.astype(np.int64)]


def state_value(x: np.ndarray) -> np.ndarray:
    return np.where(np.isfinite(x), np.clip(x, -STATE_CLAMP, STATE_CLAMP), 0.0)


@dataclass
class FieldConfig:
    scales: int = 4
    mode_count: int = 6144
    wave_mode_count: int = 3072
    steps: int = 1
    dt: float = 0.005
    coupling: float = 0.5
    damping_min: float = 0.01
    damping_max: float = 0.5
    epsilon_tau: float = 0.618033988749895
    scale_ratio: float = 4.2360679775
    energy_floor: float = 1.0e-6
    read_floor: float = 0.05
    read_absolute: bool = False
    memory_write: bool = False
    # Proposed variants, off by default so the pinned rule is the baseline.
    additive_write: bool = False
    unwritten_latch: bool = False
    # A mode's readout is a sum over scales, and the shared gate averages over them, so the
    # mode's own rate barely reaches the read. This weights each scale's contribution by how
    # much of the mode survives to reach it: `exp(-taper * s * damping * dt)`. Zero keeps the
    # pinned rule exactly.
    scale_read_taper: float = 0.0


class CassiField:
    """One sequence, `mode_count` modes, `scales` scales, 9 floats per slot."""

    def __init__(self, cfg: FieldConfig):
        self.cfg = cfg
        self.modes = np.arange(cfg.mode_count)
        # llama-context.cpp:240 maps the mode bank onto [damping_min, damping_max].
        denominator = cfg.mode_count - 1 if cfg.mode_count > 1 else 1
        alpha = self.modes / denominator
        self.mode_params = cfg.damping_min + alpha * (cfg.damping_max - cfg.damping_min)
        self.chirp0_re, self.chirp0_im = chirp(0, self.modes)
        self.state = np.zeros((cfg.scales, cfg.mode_count, 9), dtype=np.float64)

    @property
    def read_weight(self) -> np.ndarray:
        """Per-scale readout weight, `exp(-taper * s * damping * dt)`.

        A property rather than a cached array because the callers replace `mode_params`
        after construction, and a weight built from stale damping would silently measure a
        different field. At taper 0 it is 1.0 everywhere, so the pinned readout is exact.
        """
        cfg = self.cfg
        if cfg.scale_read_taper == 0.0:
            return np.ones((cfg.scales, cfg.mode_count), dtype=np.float64)
        damping = np.clip(np.abs(self.mode_params), cfg.damping_min, cfg.damping_max)
        scale = np.arange(cfg.scales, dtype=np.float64)[:, None]
        return np.exp(-cfg.scale_read_taper * scale * damping[None, :] * cfg.dt)

    # -- pinned rule -------------------------------------------------------
    def step(self, signal_re: np.ndarray, signal_im: np.ndarray):
        cfg = self.cfg
        st = self.state
        ey_re, ey_im = st[:, :, 0], st[:, :, 1]
        ei_re, ei_im = st[:, :, 2], st[:, :, 3]
        eps2 = np.maximum(st[:, :, 8], 0.0)

        e_y = ey_re ** 2 + ey_im ** 2
        e_i = ei_re ** 2 + ei_im ** 2
        rho = np.clip(e_y + e_i, 0.0, STATE_CLAMP)
        rho2 = rho * rho
        q = np.clip(rho2 / (rho2 + INV_PHI2 + eps2), 0.0, 1.0)
        q_max = rho2 / (rho2 + INV_PHI2)
        available = rho > cfg.energy_floor
        chi = np.where(available & (q_max > 0.0),
                       np.clip(np.divide(q, q_max, out=np.zeros_like(q), where=q_max > 0.0), 0.0, 1.0),
                       0.0)

        d_re = ey_re - PHI * ei_re
        d_im = ey_im - PHI * ei_im
        norm = np.ones_like(rho) if cfg.read_absolute else 1.0 / np.sqrt(np.maximum(rho, 1e-12))
        damping = np.clip(np.abs(self.mode_params), cfg.damping_min, cfg.damping_max)
        # Scale weights: 1.0 everywhere at taper 0, so the pinned readout is untouched.
        weight = self.read_weight
        read_re = np.sum(np.where(available, weight * chi * d_re * norm, 0.0), axis=0)
        read_im = np.sum(np.where(available, weight * chi * d_im * norm, 0.0), axis=0)
        chi_sum = np.sum(np.where(available, weight * chi, 0.0), axis=0)
        avail_count = np.sum(available, axis=0)
        weight_sum = np.sum(np.where(available, weight, 0.0), axis=0)

        phase_sum = np.zeros(cfg.mode_count)
        for s in range(1, cfg.scales):
            both = available[s - 1] & available[s]
            denom = np.sqrt(np.maximum(rho[s - 1] * rho[s], 1e-12))
            phase_sum += np.where(both,
                                  np.clip(0.5 + 0.5 * (d_re[s - 1] * d_re[s] + d_im[s - 1] * d_im[s]) / denom, 0.0, 1.0),
                                  0.0)
        cross = np.where(avail_count > 1,
                         np.clip(phase_sum / np.maximum(avail_count - 1, 1), 0.0, 1.0),
                         np.where(avail_count == 1, 1.0, 0.0))
        read_gate = np.where(avail_count > 0,
                             np.clip((chi_sum / np.maximum(weight_sum, 1e-30)) * cross, 0.0, 1.0),
                             0.0)
        live = (read_gate >= cfg.read_floor) & (avail_count > 0)
        divisor = np.maximum(weight_sum, 1e-30)
        cell_re = np.where(live, cfg.coupling * read_gate * read_re / divisor, 0.0)
        cell_im = np.where(live, cfg.coupling * read_gate * read_im / divisor, 0.0)

        src_re = self.chirp0_re * signal_re - self.chirp0_im * signal_im
        src_im = self.chirp0_re * signal_im + self.chirp0_im * signal_re
        src_energy = src_re ** 2 + src_im ** 2
        structured = np.clip(src_energy / (1.0 + src_energy), 0.0, 1.0)
        latch = (rho[0] == 0.0) if cfg.unwritten_latch else ~available[0]
        write_gate = np.where(latch, 1.0, structured * (1.0 - q[0]))
        gain = np.clip(cfg.dt * write_gate, 0.0, 0.5)

        keep = 1.0 if cfg.additive_write else (1.0 - gain)
        st[0, :, 0] = state_value(keep * st[0, :, 0] + 0.5 * gain * src_re)
        st[0, :, 1] = state_value(keep * st[0, :, 1] + 0.5 * gain * src_im)
        st[0, :, 2] = state_value(keep * st[0, :, 2] - 0.5 * gain * src_re / PHI)
        st[0, :, 3] = state_value(keep * st[0, :, 3] - 0.5 * gain * src_im / PHI)

        for _ in range(cfg.steps):
            diff_re = st[0, :, 0] - PHI * st[0, :, 2]
            diff_im = st[0, :, 1] - PHI * st[0, :, 3]
            ay_re = -diff_re - damping * st[0, :, 4]
            ay_im = -diff_im - damping * st[0, :, 5]
            ai_re = diff_re / PHI - damping * st[0, :, 6]
            ai_im = diff_im / PHI - damping * st[0, :, 7]
            st[0, :, 4] = state_value(st[0, :, 4] + ay_re * cfg.dt)
            st[0, :, 5] = state_value(st[0, :, 5] + ay_im * cfg.dt)
            st[0, :, 6] = state_value(st[0, :, 6] + ai_re * cfg.dt)
            st[0, :, 7] = state_value(st[0, :, 7] + ai_im * cfg.dt)
            st[0, :, 0] = state_value(st[0, :, 0] + st[0, :, 4] * cfg.dt)
            st[0, :, 1] = state_value(st[0, :, 1] + st[0, :, 5] * cfg.dt)
            st[0, :, 2] = state_value(st[0, :, 2] + st[0, :, 6] * cfg.dt)
            st[0, :, 3] = state_value(st[0, :, 3] + st[0, :, 7] * cfg.dt)

        e_y0 = st[0, :, 0] ** 2 + st[0, :, 1] ** 2
        e_i0 = st[0, :, 2] ** 2 + st[0, :, 3] ** 2
        epsilon = e_y0 - PHI * e_i0
        alpha = np.clip(cfg.epsilon_tau, 0.0, 1.0)
        st[0, :, 8] = state_value((1.0 - alpha) * np.maximum(st[0, :, 8], 0.0) +
                                  alpha * np.clip(epsilon ** 2, 0.0, STATE_CLAMP))

        scale_dt = cfg.dt
        for s in range(1, cfg.scales):
            scale_dt = float(np.clip(scale_dt / max(cfg.scale_ratio, 1e-6), 1e-6, 0.25))
            source_available, target_available = available[s - 1], available[s]
            source_chi, target_q = chi[s - 1], q[s]
            sd_re, sd_im = d_re[s - 1], d_im[s - 1]
            td_re, td_im = d_re[s], d_im[s]
            j_scale = sd_re * td_im - sd_im * td_re
            denom = np.sqrt(np.maximum(rho[s - 1] * rho[s], 1e-12))
            phase = np.clip(0.5 + 0.5 * (sd_re * td_re + sd_im * td_im) / denom, 0.0, 1.0)
            gain = np.where(
                source_available,
                np.where(~target_available,
                         scale_dt * source_chi,
                         np.where((phase >= 0.5) & (j_scale >= 0.0),
                                  scale_dt * source_chi * phase *
                                  np.clip(j_scale / denom, 0.0, 1.0) * (1.0 - target_q),
                                  0.0)),
                0.0)
            gain = np.clip(gain, 0.0, 0.5)
            st[s] = state_value((1.0 - gain)[:, None] * st[s] + gain[:, None] * st[s - 1])

        return cell_re, cell_im


def run(field_: CassiField, signals: list[tuple[np.ndarray, np.ndarray]], modes: np.ndarray):
    """Readout cells, the differential coordinate d, its velocity, and rho, for `modes`."""
    cells, differential, velocity, rho = [], [], [], []
    for sig_re, sig_im in signals:
        cell_re, cell_im = field_.step(sig_re, sig_im)
        st = field_.state
        cells.append(cell_re[modes] + 1j * cell_im[modes])
        differential.append((st[:, modes, 0] - PHI * st[:, modes, 2]) +
                            1j * (st[:, modes, 1] - PHI * st[:, modes, 3]))
        velocity.append((st[:, modes, 4] - PHI * st[:, modes, 6]) +
                        1j * (st[:, modes, 5] - PHI * st[:, modes, 7]))
        rho.append(st[:, modes, 0] ** 2 + st[:, modes, 1] ** 2 +
                   st[:, modes, 2] ** 2 + st[:, modes, 3] ** 2)
    return np.array(cells), np.array(differential), np.array(velocity), np.array(rho)


def silence(mode_count: int, count: int):
    zero = np.zeros(mode_count)
    return [(zero, zero) for _ in range(count)]


def log_slope(series: np.ndarray) -> float:
    index = np.arange(series.size, dtype=np.float64)
    return float(-np.polyfit(index, np.log(series), 1)[0])


def main() -> int:
    cfg = FieldConfig()
    horizon = 4097  # token 0 carries the impulse, so ages 1..4096 are readable
    probe_modes = [0, 768, 1536, 2304, 3071]  # spans the wave-mode damping ramp
    age_columns = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096]

    # -- 1. readout and oscillator energy against token age ---------------
    age_rows = []
    for index, mode in enumerate(probe_modes):
        f = CassiField(cfg)
        sig_re = np.zeros(cfg.mode_count)
        sig_re[mode] = 1.0
        signals = [(sig_re, np.zeros(cfg.mode_count))] + silence(cfg.mode_count, horizon - 1)
        cells, differential, velocity, rho = run(f, signals, np.array([mode]))
        readout = np.abs(cells[:, 0])
        energy = (np.abs(differential[:, 0, 0]) ** 2 + 0.5 * np.abs(velocity[:, 0, 0]) ** 2)[1:]
        damping = float(np.clip(abs(f.mode_params[mode]), cfg.damping_min, cfg.damping_max))
        # The same impulse in a single-scale field: no cascade can drain scale 0, so this
        # separates the mode's own damping from the multi-scale consolidation drain.
        single = CassiField(FieldConfig(scales=1))
        single.step(sig_re, np.zeros(cfg.mode_count))
        _, single_d, single_v, _ = run(single, silence(cfg.mode_count, horizon - 1), np.array([mode]))
        single_energy = (np.abs(single_d[:, 0, 0]) ** 2 + 0.5 * np.abs(single_v[:, 0, 0]) ** 2)
        # A field whose modes never fall below the availability floor: if the post-cliff drain
        # is the `!available -> write_gate = 1` latch acting on a silent input, removing the
        # floor must collapse the asymptotic rate back onto the mode's own damping.
        floorless = CassiField(FieldConfig(energy_floor=0.0))
        floorless.step(sig_re, np.zeros(cfg.mode_count))
        _, floor_d, floor_v, _ = run(floorless, silence(cfg.mode_count, horizon - 1), np.array([mode]))
        floor_energy = (np.abs(floor_d[:, 0, 0]) ** 2 + 0.5 * np.abs(floor_v[:, 0, 0]) ** 2)
        # |d| / sqrt(rho) is the readout's magnitude before the gates. The gates are constant
        # while the mode is available, so this number is what the readout hands the model.
        invariance = {str(age): round(float(np.abs(differential[age, 0, 0]) /
                                            math.sqrt(max(float(rho[age, 0, 0]), 1e-30))), 9)
                      for age in (1, 64, 512, 2048)}
        full = np.nonzero(readout[1:] >= 0.999 * readout[1])[0]
        live = np.nonzero(readout[1:] > 0.0)[0]
        age_rows.append({
            "mode": mode,
            "damping": round(damping, 6),
            "predicted_energy_rate_per_token": round(damping * cfg.dt, 9),
            "measured_early_rate": round(log_slope(energy[:256]), 9),
            "measured_asymptotic_rate": round(log_slope(energy[-1024:]), 9),
            "measured_asymptotic_rate_scales1": round(log_slope(single_energy[-1024:]), 9),
            "measured_asymptotic_rate_no_floor": round(log_slope(floor_energy[-1024:]), 9),
            "readout_magnitude_by_age": invariance,
            "predicted_amplitude_half_life_tokens": round(2.0 * math.log(2) / (damping * cfg.dt), 1),
            "last_age_at_full_readout": int(full[-1] + 1) if full.size else 0,
            "last_age_with_any_readout": int(live[-1] + 1) if live.size else 0,
            "readout_at_age": {str(a): round(float(readout[a]) / float(readout[1]), 6) for a in age_columns},
            "energy_at_age": {str(a): round(float(energy[a - 1]) / float(energy[0]), 6) for a in age_columns},
        })

    # -- 2. the rate span of the production bank --------------------------
    span_rows = []
    for scale in range(cfg.scales):
        scale_dt = cfg.dt / (cfg.scale_ratio ** scale)
        for damping in (cfg.damping_min, 0.05, 0.1, 0.25, cfg.damping_max):
            half_life = 2.0 * math.log(2) / (damping * scale_dt)
            span_rows.append({
                "scale": scale,
                "scale_dt": round(scale_dt, 8),
                "damping": damping,
                "amplitude_half_life_tokens": round(half_life, 1),
            })
    wave_damping = cfg.damping_min + (np.arange(cfg.wave_mode_count) / (cfg.mode_count - 1)) * \
        (cfg.damping_max - cfg.damping_min)
    fastest = float(np.max(wave_damping)) * cfg.dt / 2.0
    span_summary = {
        "wave_mode_amplitude_rate_min": round(float(np.min(wave_damping)) * cfg.dt / 2.0, 9),
        "wave_mode_amplitude_rate_max": round(fastest, 9),
        "fastest_mode_amplitude_half_life_tokens": round(math.log(2) / fastest, 1),
        "slowest_scale3_amplitude_half_life_tokens": round(
            2.0 * math.log(2) / (cfg.damping_min * cfg.dt / cfg.scale_ratio ** 3), 1),
        "rate_span_ratio": round(float(np.max(wave_damping)) / float(np.min(wave_damping)) * cfg.scale_ratio ** 3, 1),
    }

    # -- 3. capacity of the write rule ------------------------------------
    capacity_rows = []
    rng = np.random.default_rng(20260920)
    wave = cfg.wave_mode_count
    key_count = 2048
    # A real signal writes d = EY - phi*EI = gain*chirp*signal. The chirp is a unit-modulus
    # 16-point table with purely imaginary entries (chirp_re = 0 for four of sixteen indices),
    # so it must be undone by multiplication with its conjugate, never by dividing by its
    # real part. Rademacher keys keep the write's energy gate live (structured ~ 0.5).
    keys = rng.choice(np.array([-1.0, 1.0]), size=(key_count, wave))
    for additive in (False, True):
        for steps in (0, 1):
            arm = FieldConfig(additive_write=additive, steps=steps)
            f = CassiField(arm)
            chirp = f.chirp0_re[:wave] + 1j * f.chirp0_im[:wave]
            for i in range(key_count):
                sig = np.zeros(cfg.mode_count)
                sig[:wave] = keys[i]
                f.step(sig, np.zeros(cfg.mode_count))
                if (i + 1) in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048):
                    state = f.state
                    differential = ((state[0, :wave, 0] - PHI * state[0, :wave, 2]) +
                                    1j * (state[0, :wave, 1] - PHI * state[0, :wave, 3]))
                    decoded = (differential * np.conj(chirp)).real
                    retrieved = decoded / np.linalg.norm(decoded)
                    cosines = (keys[: i + 1] @ retrieved) / math.sqrt(wave)
                    others = np.delete(cosines, i)
                    capacity_rows.append({
                        "write": "additive" if additive else "pinned_blend",
                        "oscillator_steps": steps,
                        "items": i + 1,
                        "decoded_norm": round(float(np.linalg.norm(decoded)), 6),
                        "target_cosine": round(float(cosines[i]), 6),
                        "best_other_cosine": round(float(np.max(np.abs(others))), 6) if others.size else None,
                    })

    # -- 4. can the bank express a graded profile? ------------------------
    ages = np.arange(1, 4097, dtype=np.float64)
    targets = {
        "local_exp8": np.exp(-ages / 8.0),
        "power_law": 1.0 / (ages + 1.0),
        "mix_local_power": 0.5 * np.exp(-ages / 8.0) + 0.5 / (ages + 1.0),
    }
    production_rates = np.unique(wave_damping * cfg.dt / 2.0)
    design_rates = np.logspace(np.log10(1.0e-4), np.log10(4.0), 96)

    def fit_profile(rates: np.ndarray, target: np.ndarray):
        bank = np.exp(-np.outer(rates, ages))
        bank /= np.linalg.norm(bank, axis=1, keepdims=True)
        weights, _ = nnls(bank.T, target)
        fitted = weights @ bank
        denominator = float(np.sum(np.abs(target)))
        return (round(float(np.sum(np.abs(target - fitted)) / denominator), 6),
                round(float(np.corrcoef(fitted, target)[0, 1]), 6),
                int(np.count_nonzero(weights > 1.0e-9)))

    fit_rows = []
    for name, target in targets.items():
        for bank_name, rates in (("production_ramp", production_rates), ("designable_log_grid", design_rates)):
            for subset in (1, 2, 4, 8, 16, 32, 64, 96):
                if subset > rates.size:
                    continue
                picked = rates[np.linspace(0, rates.size - 1, subset).astype(int)]
                error, correlation, used = fit_profile(picked, target)
                fit_rows.append({"target": name, "bank": bank_name, "rates": subset,
                                 "relative_l1_error": error, "correlation": correlation,
                                 "nonzero_rates": used})

    report = {
        "config": asdict(cfg),
        "horizon": horizon,
        "readout_and_energy_by_age": age_rows,
        "rate_span": span_rows,
        "rate_span_summary": span_summary,
        "capacity": capacity_rows,
        "profile_fit": fit_rows,
    }
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_diag", "field-memory-study")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "study.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
