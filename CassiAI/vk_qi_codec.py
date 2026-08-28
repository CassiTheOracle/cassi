"""vk_qi_codec.py — M3: the φ-shell checkpoint codec for the VkQiCube engine.

Implements 58 §5 / 51 C1 on psi = 4096 voxels (16³) × 128 complex dims:
per-dim 3D FFT, φ-radius shell masks m=0..5 (18/62/224/1052/2517/222 modes,
DC exact), the 38/48/50 allocation (LOW c64; HIGH shell 5: c64 if P_j >= 2.0,
b16 if C_j >= 0.10 and qbar >= 0.5, else pb{p+6}), p(τ) phase bits
p = clamp(ceil(log2(2π·sqrt(τ)/(sqrt(12)·1e-4))), 6, 16) with
τ = E_shell5/E_tot_metric per dim (50:13), the aggregate-gated certified drop
(HIGH shell only if E_5 <= 1e-8·E_tot AND |Δqbar| <= 1e-4, ΔF <= 1e-2 rel
(F = eps_memory proxy = ⟨|ψ|²⟩), jz_err <= 1e-2, fc_err <= 1e-2; any failure
refuses all drops — 50:65), the error-vector certificate (38 §6), zlib,
sha256+xor64. Decoder is a deterministic function of the stored bits.

Instantiations pre-registered in 65-vkqi-codec-keys-ic.md §2 (vk_qi mapping
of the two-fluid formulas; no number transfers — 51 §2).

API:
  encode(psi_flat, exact=False) -> (packet_bytes, certificate_dict)
      psi_flat: float32 array of length 4096*128*2 (engine order:
      [voxel, dim, real/imag]) or complex [4096,128].
  decode(packet_bytes) -> psi_flat (float32 [4096*128*2], engine order)
"""

import hashlib
import math
import struct
import zlib

import numpy as np

PHI = 0.5 * (1.0 + math.sqrt(5.0))
PHI_INV = 1.0 / PHI
N = 16
DIM = 128
NV = N ** 3                    # 4096
RAW_BYTES = NV * DIM * 2 * 4   # 4,194,304 B raw complex64
BUDGET = 1e-4
FLOOR_REL = 1e-12              # keep-bitmask relative magnitude floor (48)
J_LO = 4                       # LOW/HIGH split: LOW = shells 0..4 (39:217)
P_THRESH = 2.0                 # peakedness -> c64 (39:219)
C_THRESH = 0.10                # phase-current share -> b16 (39:220)
Q_THRESH = 0.5                 # q_mean regime (39:221)
TAU_DROP = 1e-8                # energy gate for the certified drop (50:14)
# Aggregate-gate criteria (39's PASS dict + 50:62-64)
DQ_MAX = 1e-4
DF_REL_MAX = 1e-2
DF_ABS_A1 = 1e-8               # A1 regime: F < 1e-6
JZ_MAX = 1e-2
FC_MAX = 1e-2
MAGIC = b'C2FC'
VERSION = 1

# ── φ-radius shell masks on the 16³ grid (grid-independent counts) ──
_K1 = np.fft.fftfreq(N) * N
_KX, _KY, _KZ = np.meshgrid(_K1, _K1, _K1, indexing='ij')
KR = np.sqrt(_KX ** 2 + _KY ** 2 + _KZ ** 2).ravel()      # [4096]
N_SHELLS = 6
SHELLS = np.zeros(NV, dtype=np.int64)                     # -1 for DC
for m in range(N_SHELLS):
    lo, hi = PHI ** m, PHI ** (m + 1)
    SHELLS[(KR >= lo) & (KR < hi)] = m
SHELLS[KR == 0.0] = -1
SHELL_COUNTS = [int((SHELLS == m).sum()) for m in range(N_SHELLS)]
LOW_MASK = SHELLS <= J_LO            # shells 0..4 (+ nothing else)
LOW_MASK = LOW_MASK & (SHELLS >= 0)  # exclude DC (handled separately)
DC_IDX = 0                           # k=(0,0,0) is index 0 of the ravel order


def _packn(vals, width):
    """LSB-first variable-width bit packer (widths 6..22, per 50)."""
    vals = np.asarray(vals, dtype=np.uint32)
    out = bytearray(int((vals.size * width + 7) // 8))
    bit = 0
    for v in vals.tolist():
        for b in range(width):
            if (v >> b) & 1:
                out[bit >> 3] |= 1 << (bit & 7)
            bit += 1
    return bytes(out)


def _unpackn(data, n, width):
    vals = np.zeros(n, dtype=np.uint32)
    bit = 0
    for i in range(n):
        v = 0
        for b in range(width):
            if data[bit >> 3] & (1 << (bit & 7)):
                v |= 1 << b
            bit += 1
        vals[i] = v
    return vals


def _jz_of(field):
    """J_z = Im(ψ*·∂_hψ) along the spine (h = n%16 fastest), per my M1
    formula. Accepts a [NV] complex field or [NV, DIM]; returns [NV]
    (summed over dims for the full field)."""
    f2 = np.asarray(field)
    flat = f2.reshape(NV, -1)                  # [NV, rest]
    h = np.arange(NV) % N
    idx = np.arange(NV)
    d = np.zeros_like(flat)
    inner = (h > 0) & (h < 15)
    d[inner] = (flat[idx[inner] + 1] - flat[idx[inner] - 1]) * 0.5
    d[h == 0] = flat[idx[h == 0] + 1] - flat[idx[h == 0]]
    d[h == 15] = flat[idx[h == 15]] - flat[idx[h == 15] - 1]
    return np.imag(np.conj(flat) * d).sum(axis=1)   # [NV]


def _q_of(psi_c):
    """q(ψ) = M/(M+φ⁻²), M = per-voxel mean_d |ψ_d|² (pre-registered proxy;
    the shader's q includes |ε|², unavailable offline)."""
    M = (np.abs(psi_c) ** 2).mean(axis=1)          # [4096]
    return float((M / (M + PHI_INV ** 2)).mean())


def _F_of(psi_c):
    """F = eps_memory proxy = global mean |ψ|² (the |ε|² scale)."""
    return float((np.abs(psi_c) ** 2).mean())


def encode(psi_flat, exact=False):
    """Encode a psi state. Returns (packet_bytes, certificate_dict)."""
    a = np.asarray(psi_flat)
    if a.dtype == np.complex128 or a.dtype == np.complex64:
        psi_c = a.astype(np.complex128).reshape(NV, DIM)
    else:
        f = a.astype(np.float32).reshape(NV, DIM, 2)
        psi_c = f[:, :, 0] + 1j * f[:, :, 1]
    # Per-dim 3D FFT, vectorized over dims
    F = np.fft.fftn(psi_c.reshape(N, N, N, DIM), axes=(0, 1, 2)).reshape(NV, DIM)
    spec = F.T                    # [DIM, 4096] rows = dims
    E_tot = (np.abs(spec) ** 2).sum(axis=1)                    # [DIM]
    E_5 = (np.abs(spec[:, SHELLS == 5]) ** 2).sum(axis=1)      # [DIM]
    tau = np.where(E_tot > 0, E_5 / np.maximum(E_tot, 1e-300), 0.0)
    # p(τ) per dim (50:13), 1e-4 budget, N_HIGH=1
    with np.errstate(divide='ignore', invalid='ignore'):
        p = np.ceil(np.log2(2.0 * np.pi * np.sqrt(tau) / (math.sqrt(12.0) * BUDGET)))
    p = np.clip(np.nan_to_num(p, nan=6.0, posinf=16.0, neginf=6.0), 6.0, 16.0).astype(np.int64)

    # Aggregate gate: simulate dropping ALL candidate dims' shell 5 jointly.
    cand = np.where((tau <= TAU_DROP) & (E_tot > 0))[0]
    drop_ok = True
    gate = {}
    if cand.size:
        Fdrop = F.copy()
        row_mask = (SHELLS == 5)
        for dd in cand:
            Fdrop[row_mask, dd] = 0.0
        psi_drop = np.fft.ifftn(Fdrop.reshape(N, N, N, DIM), axes=(0, 1, 2)).reshape(NV, DIM)
        jz0 = _jz_of(psi_c)
        jz1 = _jz_of(psi_drop)
        n0, n1 = np.linalg.norm(jz0), np.linalg.norm(jz1)
        jz_err = float(np.linalg.norm(jz1 - jz0) / max(n0, 1e-12))
        fc0, fc1 = np.abs(jz0), np.abs(jz1)
        fc_err = float(np.linalg.norm(fc1 - fc0) / max(np.linalg.norm(fc0), 1e-12))
        q0, q1 = _q_of(psi_c), _q_of(psi_drop)
        dq = abs(q1 - q0)
        F0, F1 = _F_of(psi_c), _F_of(psi_drop)
        dF = abs(F1 - F0)
        dF_ok = (F0 >= 1e-6 and dF / max(F0, 1e-300) <= DF_REL_MAX) or \
                (F0 < 1e-6 and dF <= DF_ABS_A1)
        drop_ok = (dq <= DQ_MAX) and dF_ok and (jz_err <= JZ_MAX) and (fc_err <= FC_MAX)
        gate = {'dq': dq, 'dF': dF, 'dF_rel': float(dF / max(F0, 1e-300)),
                'F0': F0, 'jz_err': jz_err, 'fc_err': fc_err,
                'n_candidates': int(cand.size), 'accepted': bool(drop_ok)}
    if not drop_ok:
        cand = np.empty(0, dtype=np.int64)   # any failure refuses all drops

    # ── Per-dim allocation + payloads ──
    hdr = bytearray()
    low_payload = bytearray()
    hi_payload = bytearray()
    hi_meta = []
    J_FLOOR = 1e-4 * (E_tot / NV) * (2.0 * np.pi / N)   # per-dim (pre-registered)
    for dd in range(DIM):
        if dd in cand:
            mode = 0                                  # certified drop
            rec = struct.pack('<BBHHfffff', mode, 0, 0, 0,
                              0.0, 0.0, float(tau[dd]), 0.0, 0.0)
            hdr += rec
            continue
        # LOW (shells 0..4) + DC: exact c64
        low_vals = spec[dd, LOW_MASK].astype(np.complex64)
        dc_val = spec[dd, DC_IDX].astype(np.complex64)
        low_payload += dc_val.tobytes() + low_vals.tobytes()
        # shell 5
        s5 = spec[dd, SHELLS == 5]
        amp = np.abs(s5)
        keep = (amp >= FLOOR_REL) & (amp > 0.0)
        mask_bits = np.packbits(keep.astype(np.uint8))
        v = s5[keep]
        amp_k = amp[keep]
        P_j = float(amp_k.max() / amp_k.mean()) if amp_k.size else 0.0
        # C_j: band-pass shell 5 -> real space -> axial current (39:771-778)
        if amp_k.size:
            field5 = np.fft.ifftn(np.zeros((N, N, N, 1), dtype=np.complex128)).reshape(NV)
            fmask = np.zeros(NV, dtype=bool)
            fmask[SHELLS == 5] = True
            f5 = np.zeros(NV, dtype=np.complex128)
            f5[fmask] = s5
            field5 = np.fft.ifftn(f5.reshape(N, N, N), axes=(0, 1, 2)).reshape(NV)
            Jmean = float(np.abs(_jz_of(field5)).mean())
        else:
            Jmean = 0.0
        C_j = float(Jmean / max(Jmean, J_FLOOR[dd])) if Jmean > 0 else 0.0
        qbar = _q_of(psi_c)
        if P_j >= P_THRESH:
            mode = 1
        elif C_j >= C_THRESH and qbar >= Q_THRESH:
            mode = 2
        else:
            mode = 3
        n_kept = int(amp_k.size)
        A_min = float(np.log(amp_k.min())) if n_kept else 0.0
        A_max = float(np.log(amp_k.max())) if n_kept else 0.0
        rec = struct.pack('<BBHHfffff', mode, int(p[dd]), n_kept, len(mask_bits),
                          A_min, A_max, float(tau[dd]), C_j, P_j)
        hdr += rec
        hi_payload += bytes(mask_bits)
        if n_kept:
            if mode == 1:
                hi_payload += v.astype(np.complex64).tobytes()
            elif mode == 2:
                b_ph = b_am = 8
                ph_q = np.round(np.mod(np.angle(v), 2 * np.pi) / (2 * np.pi) * (2 ** b_ph - 1)).astype(np.uint32)
                uq = np.round((np.log(amp_k) - A_min) / (A_max - A_min) * (2 ** b_am - 1)).astype(np.uint32)
                hi_payload += _packn((ph_q << b_am) | uq, 16)
            else:
                b_ph, b_am = int(p[dd]), 6
                ph_q = np.round(np.mod(np.angle(v), 2 * np.pi) / (2 * np.pi) * (2 ** b_ph - 1)).astype(np.uint32)
                uq = np.round((np.log(amp_k) - A_min) / (A_max - A_min) * (2 ** b_am - 1)).astype(np.uint32)
                hi_payload += _packn((ph_q << b_am) | uq, b_ph + b_am)
        hi_meta.append((dd, mode, n_kept))

    body = (struct.pack('<4sHBBH', MAGIC, VERSION, N, DIM, DIM)
            + bytes(hdr) + bytes(low_payload) + bytes(hi_payload))
    comp = zlib.compress(bytes(body), 9)
    cert = _certificate(psi_c, comp, gate, tau, p, hi_meta, cand, exact)
    digest = hashlib.sha256(comp).digest()
    packet = comp + digest + _xor64(comp)
    cert['bytes'] = len(packet)
    cert['ratio_vs_raw'] = RAW_BYTES / len(packet)
    cert['exact_mode'] = bool(exact)
    if exact:
        psi_hat = decode(packet)
        e = psi_c - psi_hat.reshape(NV, DIM).astype(np.complex128)
        cert['error_vector_bytes'] = e.astype(np.complex64).nbytes
        cert['error_vector'] = e
    return bytes(packet), cert


def _certificate(psi_c, comp, gate, tau, p, hi_meta, cand, exact):
    psi_hat = decode(comp + hashlib.sha256(comp).digest() + _xor64(comp))
    f32 = psi_hat.reshape(NV, DIM, 2)
    f = f32[:, :, 0].astype(np.complex128) + 1j * f32[:, :, 1].astype(np.complex128)
    err = psi_c - f
    rel_l2 = float(np.linalg.norm(err) / max(np.linalg.norm(psi_c), 1e-300))
    per_dim = np.linalg.norm(err, axis=0) / np.maximum(np.linalg.norm(psi_c, axis=0), 1e-300)
    q0, q1 = _q_of(psi_c), _q_of(f)
    F0, F1 = _F_of(psi_c), _F_of(f)
    jz0, jz1 = _jz_of(psi_c), _jz_of(f)
    jz_err = float(np.linalg.norm(jz1 - jz0) / max(np.linalg.norm(jz0), 1e-12))
    fc_err = float(np.linalg.norm(np.abs(jz1) - np.abs(jz0)) /
                   max(np.linalg.norm(np.abs(jz0)), 1e-12))
    # per-shell energies
    Fs = np.fft.fftn(psi_c.reshape(N, N, N, DIM), axes=(0, 1, 2)).reshape(NV, DIM)
    Fh = np.fft.fftn(f.reshape(N, N, N, DIM), axes=(0, 1, 2)).reshape(NV, DIM)
    E0, E1 = {}, {}
    for m in range(N_SHELLS):
        E0[m] = float((np.abs(Fs[SHELLS == m]) ** 2).sum())
        E1[m] = float((np.abs(Fh[SHELLS == m]) ** 2).sum())
    dE = {m: (abs(E1[m] - E0[m]) / max(E0[m], 1e-300)) for m in range(N_SHELLS)}
    dc0 = Fs[DC_IDX].copy()
    dc1 = Fh[DC_IDX].copy()
    return {
        'rel_l2': float(rel_l2),
        'rel_l2_budget': BUDGET,
        'budget_pass': bool(rel_l2 <= BUDGET),
        'per_dim_max_rel_l2': float(per_dim.max()),
        'dqbar': float(abs(q1 - q0)),
        'dF': float(abs(F1 - F0)),
        'dF_rel': float(abs(F1 - F0) / max(F0, 1e-300)),
        'jz_err': float(jz_err),
        'fc_err': float(fc_err),
        'dE_shells': {str(m): dE[m] for m in range(N_SHELLS)},
        'dc_rel_err': float(np.linalg.norm(dc1 - dc0) / max(np.linalg.norm(dc0), 1e-300)),
        'shell_counts': SHELL_COUNTS,
        'per_dim_tau': tau.astype(np.float64).tolist(),
        'per_dim_p': p.astype(np.int64).tolist(),
        'hi_meta': [[int(dd), int(md), int(nk)] for dd, md, nk in hi_meta],
        'dropped_dims': [int(x) for x in cand],
        'aggregate_gate': gate,
        'compressed_bytes': len(comp),
        'p_candidates': int((tau <= TAU_DROP).sum()),
        'peaked_c64': int(sum(1 for _, m, _ in hi_meta if m == 1)),
        'b16': int(sum(1 for _, m, _ in hi_meta if m == 2)),
        'pb': int(sum(1 for _, m, _ in hi_meta if m == 3)),
        'checksum': hashlib.sha256(comp).hexdigest()[:16],
    }


def _xor64(data):
    x = bytearray(8)
    for i in range(0, len(data) - (len(data) % 8), 8):
        for j in range(8):
            x[j] ^= data[i + j]
    return bytes(x)


def decode(packet):
    """Decode a packet back to psi_flat (float32 [4096*128*2], engine order).
    Pure function of the stored bits (38 §5)."""
    comp = packet[:-40]
    digest = packet[-40:-8]
    xor64 = packet[-8:]
    assert hashlib.sha256(comp).digest() == digest, 'sha256 mismatch'
    assert _xor64(comp) == xor64, 'xor64 mismatch'
    body = zlib.decompress(comp)
    magic, version, n, dim, nd = struct.unpack_from('<4sHBBH', body, 0)
    assert magic == MAGIC, 'bad magic'
    assert n == N and dim == DIM
    off = 10
    hi_meta = []
    for dd in range(DIM):
        mode, p_ph, n_kept, mb = struct.unpack_from('<BBHH', body, off)
        A_min, A_max, tau, C_j, P_j = struct.unpack_from('<fffff', body, off + 6)
        hi_meta.append((dd, mode, p_ph, n_kept, mb, A_min, A_max))
        off += 26
    F = np.zeros((NV, DIM), dtype=np.complex128)
    # LOW + DC per dim (fixed order: DC then LOW modes)
    n_low = int(LOW_MASK.sum())
    for dd in range(DIM):
        raw = body[off:off + 8 * (n_low + 1)]
        vals = np.frombuffer(raw, dtype='<c8').astype(np.complex128)
        off += 8 * (n_low + 1)
        F[DC_IDX, dd] = vals[0]
        F[LOW_MASK, dd] = vals[1:]
    for dd, mode, p_ph, n_kept, mb, A_min, A_max in hi_meta:
        s5_idx = np.where(SHELLS == 5)[0]
        if mode == 0:
            continue                                   # certified drop
        mask = np.unpackbits(np.frombuffer(body[off:off + mb], dtype=np.uint8))
        off += mb
        mask = mask[:222].astype(bool)
        assert int(mask.sum()) == n_kept, 'mask/n mismatch'
        if n_kept == 0:
            continue
        if mode == 1:
            raw = body[off:off + 8 * n_kept]
            off += 8 * n_kept
            v = np.frombuffer(raw, dtype='<c8').astype(np.complex128)
        else:
            b_ph = 8 if mode == 2 else int(p_ph)
            b_am = 8 if mode == 2 else 6
            nb = (n_kept * (b_ph + b_am) + 7) // 8
            raw = body[off:off + nb]
            off += nb
            val = _unpackn(raw, n_kept, b_ph + b_am)
            ph_q = val >> b_am
            uq = val & ((1 << b_am) - 1)
            ph = ph_q / (2 ** b_ph - 1) * 2.0 * np.pi
            if A_max > A_min:
                loga = A_min + uq / (2 ** b_am - 1) * (A_max - A_min)
            else:
                loga = np.full(n_kept, A_min, dtype=np.float64)
            v = np.exp(loga.astype(np.float64)) * np.exp(1j * ph)
        F[s5_idx[mask], dd] = v
    psi_c = np.fft.ifftn(F.reshape(N, N, N, DIM), axes=(0, 1, 2)).reshape(NV, DIM)
    flat = np.empty((NV, DIM, 2), dtype=np.float32)
    flat[:, :, 0] = psi_c.real.astype(np.float32)
    flat[:, :, 1] = psi_c.imag.astype(np.float32)
    return flat
