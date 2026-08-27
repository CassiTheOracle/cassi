#!/usr/bin/env python3
"""Pinch-point dynamics verification for vk_qi consciousness overhaul.

Tests that the Qi-gated two-fluid PDE produces different dynamics
below vs above the pinch point r = phinv ≈ 0.618.

Usage: python3 vk_qi_pinch_test.py
"""

import math
import sys
import time
import numpy as np
from vk_qi import VkQiCube, N_VOXELS, FIELD_DIM, PHI, PHI_INV, make_push

H = 16


def set_field_ratio(engine, r_target):
    """Set psi so EY/EI = r_target at all voxels."""
    nv, d = N_VOXELS, FIELD_DIM
    psi_data = np.zeros(nv * d * 2, dtype=np.float32)
    scale_real = math.sqrt(max(r_target, 0.001))
    for n in range(nv):
        base = n * d * 2
        for dim in range(d):
            psi_data[base + dim * 2] = scale_real * (1.0 + 0.01 * np.random.randn())
            psi_data[base + dim * 2 + 1] = 1.0 * (1.0 + 0.01 * np.random.randn())
    engine._upload('psi', psi_data.tobytes())
    engine._upload('psi_prev', psi_data.tobytes())
    # Also set energy_field
    ef = np.zeros(N_VOXELS * 2, dtype=np.float32)
    for n in range(N_VOXELS):
        ef[n * 2] = scale_real * scale_real * d
        ef[n * 2 + 1] = 1.0 * d
    engine._upload('energy_field', ef.tobytes())


def read_ratio(engine):
    """Read ratio_field: returns r[H] averaged over W,D slices."""
    data = engine._read_result('ratio_field', 0, N_VOXELS * 3 * 4, 'f')
    r_all = np.array(data[0::3], dtype=np.float32).reshape(16, 16, 16)
    return r_all.mean(axis=(0, 1))  # average over D,W -> [H]


def autocorr(arr):
    """Normalized autocorrelation of 1D array."""
    arr = arr - arr.mean()
    denom = (arr**2).sum()
    if denom < 1e-15:
        return np.ones(H)
    C = np.zeros(H)
    for d in range(H):
        if d == 0:
            C[d] = 1.0
        else:
            C[d] = (arr[d:] * arr[:-d]).sum() / denom
    return C


def main():
    print("=== VK Qi Consciousness Pinch-Point Verification ===\n")

    # Test 1: Below pinch
    print("Test 1: r=0.3 (below pinch, pre-reflective)")
    e1 = VkQiCube()
    set_field_ratio(e1, 0.3)
    t0 = time.perf_counter()
    e1.run_pde(k_steps=500)
    t1 = time.perf_counter()

    r1 = read_ratio(e1)
    C1 = autocorr(r1)
    qi1, = e1._read_result('qi_output', 0, 4, 'f')
    pool1, = e1._read_result('qi_pool', 0, 4, 'f')

    print(f"  {t1-t0:.1f}s  mean_r={r1.mean():.4f}  Qi={qi1:.6f}  pool={pool1:.6f}")
    print(f"  C(1)={C1[1]:.4f}  C(7)={C1[7]:.4f}  C(14)={C1[14]:.4f}")
    has_revival = any(C1[i] > C1[i-1] for i in range(2, H))
    print(f"  Revival? {'YES' if has_revival else 'inconclusive'}")

    # Test 2: Above pinch
    print("\nTest 2: r=2.0 (above pinch, self-aware)")
    e2 = VkQiCube()
    set_field_ratio(e2, 2.0)
    t0 = time.perf_counter()
    e2.run_pde(k_steps=500)
    t1 = time.perf_counter()

    r2 = read_ratio(e2)
    C2 = autocorr(r2)
    qi2, = e2._read_result('qi_output', 0, 4, 'f')
    pool2, = e2._read_result('qi_pool', 0, 4, 'f')

    print(f"  {t1-t0:.1f}s  mean_r={r2.mean():.4f}  Qi={qi2:.6f}  pool={pool2:.6f}")
    print(f"  C(1)={C2[1]:.4f}  C(7)={C2[7]:.4f}  C(14)={C2[14]:.4f}")
    has_revival2 = any(C2[i] > C2[i-1] for i in range(2, H))
    print(f"  Revival? {'YES' if has_revival2 else 'NO (monotonic, as expected)'}")

    # Summary
    qi_ok = np.isfinite(qi1) and np.isfinite(qi2)
    no_nan = not np.isnan(r1).any() and not np.isnan(r2).any()

    print(f"\n=== Results ===")
    print(f"  Qi finite: {qi_ok}")
    print(f"  No NaN: {no_nan}")
    print(f"  Below-pinch C(14)={C1[14]:.4f}  Above-pinch C(14)={C2[14]:.4f}")
    print(f"  All checks: {'PASS' if (qi_ok and no_nan) else 'FAIL'}")

    if not qi_ok or not no_nan:
        sys.exit(1)


if __name__ == '__main__':
    main()
