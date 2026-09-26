"""vk_qi_telemetry.py — M1 additive telemetry for the VkQiCube Vulkan trainer.

Zero behavior change: host-side reads of existing buffers only (plus two
additive uint clamp-fire counters in norm_constants, populated by
qi_accum.comp / nonlinear_step.comp). Hooked at vk_qi.py:786 (per ingest
window) and at the _ingest generation site.

Per-window log (CSV, logs/vkqi_telemetry_<ts>.csv):
  step, qi_val, q_M, q_ratio_mean, water_q, qbar_win, s, s_eff,
  chakra_q[13], clamp counters/fractions, J_z/F_c (every K=16),
  shell energies E_m + phase order R_m (every K=16), pinch stats.

Naming (58 §0): q_M = M/(M+φ⁻²+|ε|²) — qi_accum.comp:200, recomputed
host-side from the accum buffer (exactly what the shader computes).
q_ratio = (EY−φEI)/(EY+φEI) — two_fluid_diag.comp:60, mean of
ratio_field[v*3+1]. NOTE: qi_accum.comp:293 mislabels ratio_field[1] as
q_M; the column header here is corrected to q_ratio_mean.
water_q: qi_output byte 1068 (wood 1052, fire 1056, metal 1060, earth
1064, water_q 1068, eps_memory 1072).
chakra_q[13]: training_data buffer, float offset 13*128+13 = 1677.
"""

import math
import os
import time
from pathlib import Path

import numpy as np

PHI = 0.5 * (1.0 + math.sqrt(5.0))
PHI_INV = 1.0 / PHI
PHI_INV2 = PHI_INV * PHI_INV
W = 128          # q-history window for q̄_win / slope s
K = 16           # psi / byte_embed read cadence (windows)

# Clamp bounds (58 §0)
L2_CLAMP = 5.0
AMP_CAP = 2.0
FLOOR_AMP = 1e-3
QNEW_LO, QNEW_HI = 0.0, 10.0
STRIDE_LO, STRIDE_HI = 512, 4096
GATE_LO, GATE_HI = 0.01, 2.0
Q_RATIO_BOUND = 1.0
ATT_LO, ATT_HI = 0.1, 1.0
CHAKRA_LO, CHAKRA_HI = 0.1, 5.0
QI_TARGET_FLOOR = 0.05

# φ-radius DFT shells on the 16³ grid: [φ^m, φ^{m+1}) for m=0..5,
# excluding DC. Counts verified: 18/62/224/1052/2517/222 = 4095 (58 §3).
_K1 = np.fft.fftfreq(16) * 16.0
_KX, _KY, _KZ = np.meshgrid(_K1, _K1, _K1, indexing='ij')
_N_SHELLS = 6

def _shell_counts():
    KR = np.sqrt(_KX ** 2 + _KY ** 2 + _KZ ** 2).ravel()
    return [int(((KR >= PHI ** m) & (KR < PHI ** (m + 1))).sum()) for m in range(_N_SHELLS)]


class VkQiTelemetry:
    """Per-window telemetry collector. Additive-only; never raises.

    M4 Phase 1 (58 §4): when env VKQI_KEYLOG=1, also logs the ready-made
    field-as-key — combined_state from qi_output bytes 1076-1588
    (qi_accum.comp:307-328, 128 floats) — per window to
    logs/vkqi_keys_<ts>.bin (130 f32 records: [step, data_offset, key[128]])
    and generation records to logs/vkqi_gen_<ts>.jsonl. The engine's
    _cur_offset attr (set by _ingest) records the training data offset of
    each window for the retrieval test. Env VKQI_HEAVY_EVERY overrides the
    K=16 psi-read cadence (0 = skip heavy reads; run-speed control only).
    """

    def __init__(self, engine, out_dir='logs'):
        self.eng = engine
        self.sizes = getattr(engine, '_buffer_sizes', {})
        self.steps = []
        self.qis = []
        self.waters = []
        self.qbar = float('nan')
        self.slope = float('nan')
        self.s_eff = float('nan')
        self._win = 0
        self._csv = None
        self._csv_path = None
        try:
            d = Path(out_dir)
            d.mkdir(parents=True, exist_ok=True)
            self._csv_path = d / f'vkqi_telemetry_{time.strftime("%Y%m%d_%H%M%S")}.csv'
            self._csv = open(self._csv_path, 'w', newline='')
            self._write_header()
        except Exception:
            self._csv = None
        # ── M4 key log (off unless VKQI_KEYLOG=1) ──
        self._keys = None
        self._gens = None
        if os.environ.get('VKQI_KEYLOG') == '1':
            try:
                ts = time.strftime('%Y%m%d_%H%M%S')
                self._keys = open(d / f'vkqi_keys_{ts}.bin', 'wb')
                self._gens = open(d / f'vkqi_gen_{ts}.jsonl', 'w')
            except Exception:
                self._keys = self._gens = None

    # ── helpers ──

    def _has(self, name):
        return name in self.sizes

    def _read(self, name, offset, size, fmt='f'):
        try:
            if not self._has(name):
                return None
            return self.eng._read_result(name, offset, size, fmt)
        except Exception:
            return None

    def _read_float(self, name, offset, size, fmt='f'):
        r = self._read(name, offset, size, fmt)
        return None if r is None else np.array(r, dtype=np.float32)

    def _write_header(self):
        cols = ['step', 'qi_val', 'q_M', 'q_ratio_mean', 'water_q',
                'qbar_win', 's', 's_eff']
        cols += [f'chakra_q_{c}' for c in range(13)]
        cols += ['sat_gate_weight', 'sat_att_mod',
                 'frac_l2_clamp', 'frac_amp_cap', 'frac_amp_floor',
                 'frac_qnew_lo', 'frac_qnew_hi', 'frac_stride_pin',
                 'frac_q_pin', 'frac_chakra_pin', 'qi_target_floor',
                 'jz_mean', 'fc_mean'] + [f'fc_h_{h}' for h in range(16)]
        cols += [f'E_m{m}' for m in range(_N_SHELLS)]
        cols += [f'R_m{m}' for m in range(_N_SHELLS)]
        cols += ['slope_logE', 'R_alt_pattern',
                 'f_pinch_lt_phiinv', 'chord_mean',
                 'gen_unique', 'gen_printable']
        self._csv.write(','.join(cols) + '\n')

    def _row(self, vals):
        if self._csv is None:
            return
        try:
            self._csv.write(','.join('' if v is None else
                                     (f'{v:.6e}' if isinstance(v, float) else str(v))
                                     for v in vals) + '\n')
            self._csv.flush()
        except Exception:
            pass

    # ── per-window hook (vk_qi.py:786) ──

    def on_window(self, engine, qi_val):
        try:
            self._on_window(engine, qi_val)
        except Exception:
            pass  # telemetry must never affect training (zero behavior change)

    def _on_window(self, engine, qi_val):
        self._win += 1
        eng = engine
        step = getattr(eng, 'step_count', self._win)

        # q-history state
        self.steps.append(step)
        self.qis.append(float(qi_val))
        if len(self.qis) > W:
            self.steps.pop(0)
            self.qis.pop(0)
        q = np.array(self.qis, dtype=np.float64)
        st = np.array(self.steps, dtype=np.float64)
        self.qbar = float(q.mean()) if q.size else float('nan')
        if q.size >= 2 and st[-1] != st[0]:
            self.slope = float(np.polyfit(st, q, 1)[0])
        else:
            self.slope = float('nan')

        # water_q (qi_output byte 1068)
        water_q = None
        w = self._read_float('qi_output', 1068, 4)
        if w is not None and w.size:
            water_q = float(w[0])
        self.waters.append(water_q)
        self.s_eff = float('nan')
        if water_q is not None and not math.isnan(self.slope):
            self.s_eff = self.slope * abs(water_q)

        # q_M: recompute exactly as qi_accum.comp:200 — M/(M+φ⁻²+|ε|²)
        # from accum (b12): [max_amp_bits u32, phase1_done u32,
        #                    accum_delta2 f, accum_psi_psi_prev f,
        #                    accum_psi2 f, accum_prev2 f, accum_epsilon2 f]
        q_M = None
        acc = self._read('accum', 0, 28, 'I')
        if acc is not None and len(acc) >= 7:
            try:
                accum_delta2 = float(np.array(acc[2:3], dtype=np.uint32).view(np.float32)[0])
                accum_psi2 = float(np.array(acc[4:5], dtype=np.uint32).view(np.float32)[0])
                total = float(4096 * 128)
                M = accum_psi2 / total
                eps2 = accum_delta2 / total
                q_M = M / (M + PHI_INV2 + eps2)
            except Exception:
                q_M = None

        # q_ratio_mean: ratio_field[v*3+1] (b25) — the value qi_accum.comp:293
        # mislabels as q_M; header corrected here.
        q_ratio_mean = None
        rf = self._read_float('ratio_field', 0, self.sizes.get('ratio_field', 0))
        if rf is not None and rf.size >= 3:
            q_ratio_mean = float(rf[1::3].mean())
            r_vals = rf[0::3]
            r_safe = r_vals[r_vals > 0]
            f_pinch = float((r_safe < PHI_INV).mean()) if r_safe.size else float('nan')
            chord = (r_safe - 1.0) / (r_safe + 1.0)
            chord_mean = float(chord.mean()) if chord.size else float('nan')
            q_pin = float((np.abs(rf[1::3]) >= Q_RATIO_BOUND - 1e-6).mean())
        else:
            f_pinch = chord_mean = q_pin = float('nan')

        # clamp counters (norm_constants bytes 8..15, additive uints)
        nc = self._read('norm_constants', 0, 16, 'I')
        sat_gw = sat_am = None
        if nc is not None and len(nc) >= 4:
            sat_gw, sat_am = int(nc[2]), int(nc[3])

        # host-side fractions
        qd = self._read_float('qi_density', 0, self.sizes.get('qi_density', 0))
        if qd is not None and qd.size:
            frac_qnew_lo = float((qd <= QNEW_LO + 1e-6).mean())
            frac_qnew_hi = float((qd >= QNEW_HI - 1e-6).mean())
        else:
            frac_qnew_lo = frac_qnew_hi = float('nan')

        cp = self._read_float('chakra_params', 0, self.sizes.get('chakra_params', 0))
        if cp is not None and cp.size:
            frac_chakra_pin = float(((cp <= CHAKRA_LO + 1e-6) | (cp >= CHAKRA_HI - 1e-6)).mean())
        else:
            frac_chakra_pin = float('nan')

        stride = getattr(eng, 'stride', None)
        smin = getattr(eng, 'stride_min', STRIDE_LO)
        smax = getattr(eng, 'stride_max', STRIDE_HI)
        if stride is not None:
            frac_stride_pin = float(stride in (smin, smax))
        else:
            frac_stride_pin = float('nan')
        qi_t = getattr(eng, 'qi_target', None)
        qi_target_floor = float(qi_t is not None and abs(qi_t - QI_TARGET_FLOOR) < 1e-9)

        # chakra_q[13] (training_data float offset 1677)
        chakra_q = [None] * 13
        td = self._read_float('training_data', 1677 * 4, 13 * 4)
        if td is not None and td.size == 13:
            chakra_q = [float(v) for v in td]

        # every-K heavy reads: psi (J_z/F_c, shells), byte_embed (L2 clamp)
        jz_mean = fc_mean = float('nan')
        fc_h = [float('nan')] * 16
        E_m = [float('nan')] * _N_SHELLS
        R_m = [float('nan')] * _N_SHELLS
        slope_logE = float('nan')
        R_alt = 'NA'
        frac_l2 = frac_amp_cap = frac_amp_floor = float('nan')
        try:
            k_eff = int(os.environ.get('VKQI_HEAVY_EVERY', str(K)))
        except Exception:
            k_eff = K
        if k_eff > 0 and self._win % k_eff == 0:
            (frac_l2, frac_amp_cap, frac_amp_floor, jz_mean, fc_mean,
             fc_h, E_m, R_m, slope_logE, R_alt) = self._heavy_reads(rf, q_ratio_mean)

        # ── M4 key log: combined_state (qi_output bytes 1076-1588) ──
        if self._keys is not None:
            try:
                key = self._read_float('qi_output', 1076, 128 * 4)
                if key is not None and key.size == 128:
                    off = float(getattr(eng, '_cur_offset', -1.0))
                    rec = np.concatenate([[float(step), off], key]).astype('<f4')
                    self._keys.write(rec.tobytes())
            except Exception:
                pass

        row = [step, float(qi_val), q_M, q_ratio_mean, water_q,
               self.qbar, self.slope, self.s_eff]
        row += chakra_q
        row += [sat_gw, sat_am, frac_l2, frac_amp_cap, frac_amp_floor,
                frac_qnew_lo, frac_qnew_hi, frac_stride_pin,
                q_pin, frac_chakra_pin, qi_target_floor,
                jz_mean, fc_mean] + fc_h
        row += E_m + R_m + [slope_logE, R_alt, f_pinch, chord_mean]
        row += [None, None]
        self._row(row)

    def _heavy_reads(self, rf, q_ratio_mean):
        """Every-K reads: byte_embed L2 clamp fraction; psi-based AMP_CAP /
        FLOOR fractions, J_z/F_c(h), shell energies + phase order."""
        frac_l2 = frac_amp_cap = frac_amp_floor = float('nan')
        be = self._read_float('byte_embed', 0, self.sizes.get('byte_embed', 0))
        if be is not None and be.size and be.size % 128 == 0:
            rows = be.reshape(-1, 128)
            norms = np.sqrt((rows ** 2).sum(axis=1))
            frac_l2 = float((norms >= L2_CLAMP - 1e-3).mean())

        psi = self._read_float('psi', 0, self.sizes.get('psi', 0))
        if psi is None or psi.size == 0:
            return (frac_l2, float('nan'), float('nan'), float('nan'),
                    float('nan'), float('nan'), float('nan'),
                    [float('nan')] * 16,
                    [float('nan')] * _N_SHELLS, [float('nan')] * _N_SHELLS,
                    float('nan'), 'NA')

        NV = 4096
        DIM = 128
        psi = psi[: NV * DIM * 2].reshape(NV, DIM, 2)
        amp = np.sqrt((psi ** 2).sum(axis=2))  # [NV, DIM]
        vox_max = amp.max(axis=1)
        frac_amp_cap = float((vox_max >= AMP_CAP - 1e-4).mean())
        frac_amp_floor = float(((amp > 0) & (amp <= FLOOR_AMP + 1e-6)).mean())

        # J_z = Im(ψ*·∂_hψ) along the spine (h = n % 16 fastest):
        # central diff (ψ[n+1]−ψ[n−1])/2 for 0<h<15; fwd/bwd at h=0/15.
        h = np.arange(NV) % 16
        idx = np.arange(NV)
        psi_c = psi[:, :, 0] + 1j * psi[:, :, 1]  # [NV, DIM]
        d_psi = np.zeros_like(psi_c)
        inner = (h > 0) & (h < 15)
        d_psi[inner] = (psi_c[idx[inner] + 1] - psi_c[idx[inner] - 1]) * 0.5
        d_psi[h == 0] = psi_c[idx[h == 0] + 1] - psi_c[idx[h == 0]]        # fwd at h=0
        d_psi[h == 15] = psi_c[idx[h == 15]] - psi_c[idx[h == 15] - 1]     # bwd at h=15
        Jz = np.imag(np.conj(psi_c) * d_psi).sum(axis=1)     # [NV]
        if rf is not None and rf.size >= 3:
            q_ratio_v = rf[1::3]
        else:
            q_ratio_v = np.full(NV, float('nan') if q_ratio_mean is None else q_ratio_mean)
        Fc = np.abs(Jz) * q_ratio_v
        jz_mean = float(np.abs(Jz).mean())
        fc_mean = float(Fc.mean())
        fc_h = [float(Fc[h == hh].mean()) if (h == hh).any() else float('nan')
                for hh in range(16)]

        # Shell energies + phase order (3D FFT per dim, φ-radius mask)
        # voxel n = z*256 + y*16 + h (h fastest) — FFT axes are
        # permutation-invariant for |k| shell sums.
        psi_cube = psi_c.reshape(16, 16, 16, DIM)  # [z, y, h, d]
        F = np.fft.fftn(psi_cube, axes=(0, 1, 2))  # [16,16,16,DIM]
        Ff = F.reshape(-1, DIM)                    # [4096, DIM]
        # DC row (|k|=0) is excluded by the shell mask (empty shell 0 band
        # starts at |k| ≥ 1 = φ⁰). Row k of Ff ↔ grid index k (meshgrid 'ij'
        # of fftfreq axes), so the 4096-long radius vector maps rows to shells:
        KR_full = np.sqrt(_KX ** 2 + _KY ** 2 + _KZ ** 2).ravel()
        shells = np.zeros(4096, dtype=np.int64)
        for m in range(_N_SHELLS):
            lo, hi = PHI ** m, PHI ** (m + 1)
            shells[(KR_full >= lo) & (KR_full < hi)] = m
        E_m = []
        R_m = []
        for m in range(_N_SHELLS):
            sel = shells == m
            if not sel.any():
                E_m.append(float('nan'))
                R_m.append(float('nan'))
                continue
            spec = Ff[sel]  # [N_m, DIM]
            E_m.append(float((np.abs(spec) ** 2).sum()))
            ph = np.exp(1j * np.angle(spec))       # unit-phase vectors
            R_m.append(float(np.abs(ph.sum(axis=0)).mean() / sel.sum()))
        E_arr = np.array(E_m, dtype=np.float64)
        valid = ~np.isnan(E_arr) & (E_arr > 0)
        if valid.sum() >= 3:
            slope_logE = float(np.polyfit(np.arange(_N_SHELLS)[valid],
                                          np.log(E_arr[valid]), 1)[0])
        # half-rung sign-alternation of the phase order (REPORTED check):
        # sign of Re(Σ e^{iφ})/N_m per shell, adjacent-shell flips.
        signs = []
        for m in range(_N_SHELLS):
            sel = shells == m
            if not sel.any():
                signs.append(float('nan'))
                continue
            spec = Ff[sel]
            signs.append(float(np.real(np.exp(1j * np.angle(spec)).sum()) / sel.sum()))
        flips = sum(1 for a, b in zip(signs[:-1], signs[1:])
                    if a == a and b == b and a * b < 0)
        R_alt = f'{flips}/{_N_SHELLS - 1}'
        return (frac_l2, frac_amp_cap, frac_amp_floor, jz_mean, fc_mean,
                fc_h, E_m, R_m, slope_logE, R_alt)

    # ── generation hook (_ingest gen site) ──

    def on_generation(self, gen_bytes, step):
        if self._csv is None and self._gens is None:
            return
        try:
            gen = bytes(gen_bytes)
            printable = sum(1 for b in gen if 32 <= b < 127)
            unique = len(set(gen))
            if self._gens is not None:
                import json as _json
                key = self._read_float('qi_output', 1076, 128 * 4)
                key_hex = None
                if key is not None and key.size == 128:
                    key_hex = key.astype('<f4').tobytes().hex()
                rec = {'step': int(step),
                       'offset': float(getattr(self.eng, '_cur_offset', -1.0)),
                       'key_hex': key_hex,
                       'text': gen.decode('latin1'),
                       'printable': int(printable),
                       'unique': int(unique)}
                self._gens.write(_json.dumps(rec) + '\n')
                self._gens.flush()
            q_M = self.qbar  # last window's q̄ as placeholder columns
            row = [step, self.qis[-1] if self.qis else None,
                   None, None, self.waters[-1] if self.waters else None,
                   self.qbar, self.slope, self.s_eff]
            row += [None] * 13
            row += [None] * 11
            row += [None] * 2 + [None] * 16
            row += [None] * _N_SHELLS + [None] * _N_SHELLS
            row += [None, None, None, None, unique, printable]
            self._row(row)
        except Exception:
            pass

    def close(self):
        if self._csv is not None:
            try:
                self._csv.close()
            except Exception:
                pass
            self._csv = None
        for attr in ('_keys', '_gens'):
            f = getattr(self, attr, None)
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
                setattr(self, attr, None)
