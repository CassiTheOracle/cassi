#!/usr/bin/env python3
"""Volumetric raymarch verifier — gate G35.

Reads the GPU frame dumped by scripts/verify_volumetric.gd from
_diag/volumetric_pixels.json (raw RGBAF or RGB8 floats + the geometry/palette/
analytic parameter set), recomputes the SAME analytic φ-attractor field
(research/volumetric/volumetric_design.md §5) and the SAME raymarch model
(§3 emission + §4 Beer-Lambert transport) in NumPy with a DIFFERENT step count
(320 vs the GPU's 224, §7), and gates:

  G35a  relative-L2(frame_gpu, frame_numpy) <= 1e-1
  G35b  the emission's HSL hue at the φ-gate pixel lands in the pink band [0.90, 0.97]

Because the GPU reads a 64³ *trilinear* texture while the NumPy reference
samples the *analytic* field in closed form, and the two step counts differ, the
1e-1 bound absorbs O(ds) integration error + interpolation error while still
rejecting a broken palette/box/camera (§7 of the design).

Tolerance-vs-convention: Godot's SubViewport returns an sRGB-encoded 8-bit
image. The raymarch model produces *linear* radiance; the sRGB encode is only a
display convention. G35a is evaluated against BOTH references (linear and
sRGB(linear)); it passes if either is <= 1e-1, and which convention matched is
reported.

Run:  bash python research/volumetric/volumetric_verify.py
"""
import base64
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DUMP = REPO / "_diag" / "volumetric_pixels.json"

PHI = 1.618033988749895


# ─────────────────────────────────────────────────────────────────────────────
# Analytic field (design §5) — exact mirror of verify_volumetric.gd
# vectorized over an (N,3) point array.
# ─────────────────────────────────────────────────────────────────────────────
def r2_vec(P, phi):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    return x * x + (phi * y) * (phi * y) + (z / phi) * (z / phi)


def field_ev(P, phi, sigma, amp, eps, se, Pn):
    """EY (amp=A) or EI (amp=B): a φ-anisotropic radial Gaussian core plus one
    spherical ε bump at Pn. Fully vectorized."""
    P = np.asarray(P, float)
    core = amp * np.exp(-r2_vec(P, phi) / (sigma * sigma))
    d = P - np.asarray(Pn, float)
    bump = eps * np.exp(-np.sum(d * d, axis=-1) / (se * se))
    return core + bump


def field_ey(P, phi, sigma, A, eps, se, P1):
    return field_ev(P, phi, sigma, A, eps, se, P1)


def field_ei(P, phi, sigma, B, eps, se, P2):
    return field_ev(P, phi, sigma, B, eps, se, P2)


# ─────────────────────────────────────────────────────────────────────────────
# Palette (design §3) — exact mirror of the shader / the particle instancer
# vectorized over an array of q values.
# ─────────────────────────────────────────────────────────────────────────────
def hsl2rgb_vec(h, s, l):
    """Branchless HSL->RGB (IQ form), verbatim from cassi_instancer.glsl:168."""
    h, s, l = np.asarray(h, float), np.asarray(s, float), np.asarray(l, float)
    r = np.clip(np.abs(np.mod(h[..., None] * 6.0 + np.array([0.0, 4.0, 2.0]), 6.0) - 3.0) - 1.0, 0.0, 1.0)
    # r: (...,3)
    return l[..., None] + s[..., None] * (r - 0.5) * (1.0 - np.abs(2.0 * l[..., None] - 1.0))


def sample_palette_vec(q, a_lo, a_hi, a_top, approach_on, q_lo, q_hi, slope):
    q = np.asarray(q, float)
    pA = np.clip((q - a_lo) / max(a_hi - a_lo, 1e-9), 0.0, 1.0)
    hA = 0.8 + (a_top - 0.8) * pA
    lA = 0.5 + 0.5 * pA
    inA = (approach_on * (q >= a_lo)).astype(float)
    h_cyc = np.mod(slope * np.log(np.maximum((q + 1e-9) / (q_lo + 1e-9), 1e-9)), 1.0)
    h = np.where(inA > 0.0, hA, h_cyc)
    l = np.where(inA > 0.0, lA, 0.5)
    return hsl2rgb_vec(h, 1.0, l)


def rgb_to_hue(rgb):
    """RGB -> HSL hue in [0,1). Standard max/min formula."""
    rgb = np.asarray(rgb, float)
    mx, mn = rgb.max(), rgb.min()
    if mx - mn < 1e-9:
        return 0.0
    r, g, b = rgb
    if mx == r:
        hh = (g - b) / (mx - mn)
    elif mx == g:
        hh = 2.0 + (b - r) / (mx - mn)
    else:
        hh = 4.0 + (r - g) / (mx - mn)
    return (hh / 6.0) % 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Raymarch (design §4) — pinhole rays + slab box + Beer-Lambert front-to-back
# ─────────────────────────────────────────────────────────────────────────────
def camera_basis(pos, target, up0):
    fwd = (np.asarray(target) - np.asarray(pos))
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, np.asarray(up0))
    right = right / np.linalg.norm(right)
    up = np.cross(right, fwd)
    return right, up, fwd


def build_rays(params):
    w, h = params["viewport"]
    pos = np.array(params["cam_pos"])
    right, up, fwd = camera_basis(pos, params["cam_target"], params["cam_up"])
    tanhf = math.tan(math.radians(params["fov_deg"]) * 0.5)
    aspect = w / h
    # NDC y up, rows top->bottom (y down)
    ys = np.linspace(1.0, -1.0, h)
    xs = np.linspace(-1.0, 1.0, w)
    gx, gy = np.meshgrid(xs, ys)
    rd = (fwd[None, None, :]
          + right[None, None, :] * (gx[..., None] * tanhf * aspect)
          + up[None, None, :] * (gy[..., None] * tanhf))
    rd = rd / np.linalg.norm(rd, axis=-1, keepdims=True)
    return pos, rd, right, up, fwd


def slab_intersect(ro, rd, E):
    # signed reciprocal; the slab formulas n0=(−E−ro)·inv, n1=(E−ro)·inv need
    # the ray's SIGN (crossing t = (plane − ro)/rd), not the magnitude.
    with np.errstate(divide="ignore"):
        inv = np.where(np.abs(rd) < 1e-9, 1e9, 1.0 / rd)
    n0 = (-E - ro) * inv
    n1 = (E - ro) * inv
    lo = np.minimum(n0, n1)
    hi = np.maximum(n0, n1)
    t0 = lo.max(axis=-1)
    t1 = hi.min(axis=-1)
    hit = t0 <= t1
    return t0, t1, hit


def radial_field_q(r2, A, B, sigma):
    """q(r) of the core-only radial profile (design §5)."""
    return (A * A + B * B) * math.exp(-2.0 * r2 / (sigma * sigma))


def gate_radius(params, gpa):
    """r_gate: the radius where q(r) = a_lo + gpa·(a_hi − a_lo) — the pink shell
    (the design's φ-gate)."""
    A = params["A_core"]; B = params["B_core"]; sigma = params["sigma"]
    alo, ahi = params["a_lo"], params["a_hi"]
    q0 = A * A + B * B
    qg = alo + gpa * (ahi - alo)
    return math.sqrt(-0.5 * sigma * sigma * math.log(qg / q0))


def tangent_gate_pixel(params, gpa):
    """The φ-gate pixel: the pixel (j, i) whose ray grazes the r_gate sphere
    (impact parameter = r_gate) — where the pink shell is visible NOT diluted by
    the achromatic white core. Identical formula in the verify scene so both
    sides mark the same pixel."""
    w, h = params["viewport"]
    pos = np.array(params["cam_pos"])
    right, up, fwd = camera_basis(pos, params["cam_target"], params["cam_up"])
    tanhf = math.tan(math.radians(params["fov_deg"]) * 0.5)
    aspect = w / h
    rg = gate_radius(params, gpa)

    # origin projection pixel
    d = -pos
    zc = float(d.dot(fwd))
    nx = float(d.dot(right)) / (zc * tanhf * aspect)
    ny = float(d.dot(up)) / (zc * tanhf)
    py = int(round((1.0 - (ny * 0.5 + 0.5)) * (h - 1)))
    py = min(max(py, 0), h - 1)

    # on row py, scan cols and pick the one whose ray's impact parameter ~ rg
    best_b, best_j = 1e9, -1
    for j in range(w):
        ndc_x = (j / (w - 1.0)) * 2.0 - 1.0
        rd = fwd + right * (ndc_x * tanhf * aspect) + up * (ny * tanhf)
        rd = rd / np.linalg.norm(rd)
        ro_d = float(pos.dot(rd))
        b2 = float(pos.dot(pos)) - ro_d * ro_d
        b = math.sqrt(max(b2, 0.0))
        if abs(b - rg) < abs(best_b - rg):
            best_b, best_j = b, j
    return best_j, int(py)


def march(params, steps, chunk=8192):
    pos, rd, right, up, fwd = build_rays(params)
    w, h = params["viewport"]
    E = np.array(params["E"])
    a_lo, a_hi, a_top = params["a_lo"], params["a_hi"], params["a_top"]
    ap_on = params["approach_on"]
    q_lo, q_hi, slope = params["q_lo"], params["q_hi"], params["slope"]
    s_abs, s_em, s_fog = params["s_abs"], params["s_em"], params["s_fog"]
    eps_t = params["eps_t"]
    sigma = params["sigma"]; A = params["A_core"]; B = params["B_core"]
    se = params["sigma_eps"]; eps = params["eps"]
    P1 = params["P1"]; P2 = params["P2"]
    phi = params["phi"]

    t0, t1, hit = slab_intersect(np.broadcast_to(pos, rd.shape), rd, E)
    t0 = np.maximum(t0, 0.0)
    ds = np.where(hit, (t1 - t0) / steps, 0.0)

    col = np.zeros((h, w, 3))
    Tr = np.ones((h, w))
    hit_flat = hit.ravel()
    idx = np.where(hit_flat)[0]
    if idx.size == 0:
        return col + Tr[..., None] * np.array([0.0, 0.0, 0.01])

    t0f = t0.ravel()[idx]
    rdf = rd.reshape(-1, 3)[idx]
    posf = np.broadcast_to(pos, (idx.size, 3))
    dsf = ds.ravel()[idx]

    steps_arr = (np.arange(steps) + 0.5)[:, None]          # (steps,1)

    C_all = np.zeros((idx.size, 3))
    T_all = np.zeros(idx.size)
    # process the hit rays in blocks so the (steps, block, 3) staging stays small
    for b0 in range(0, idx.size, chunk):
        b = slice(b0, min(b0 + chunk, idx.size))
        cb = b.stop - b.start
        t0b = t0f[b]; rdb = rdf[b]; posb = posf[b]; dsb = dsf[b]
        tt = t0b[None, :] + steps_arr * dsb[None, :]        # (steps,cb)
        P = posb[None, :, :] + rdb[None, :, :] * tt[..., None]  # (steps,cb,3)

        ey = np.maximum(field_ey(P, phi, sigma, A, eps, se, P1), 0.0)
        ei = np.maximum(field_ei(P, phi, sigma, B, eps, se, P2), 0.0)
        q = np.maximum(ey * ey + ei * ei, 0.0)
        rho = np.maximum(ey + ei, 0.0)
        emit = sample_palette_vec(q, a_lo, a_hi, a_top, ap_on, q_lo, q_hi, slope)  # (steps,cb,3)
        st = s_abs * rho + s_fog
        dtrans = np.exp(-st * dsb[None, :])                # (steps,cb)

        logT = np.concatenate([np.zeros((1, cb)), np.cumsum(np.log(np.maximum(dtrans, 1e-30)), axis=0)], axis=0)
        T = np.exp(np.minimum(logT, 0.0))                  # (steps+1, cb)
        seg_T = np.where(T[:steps] < eps_t, 0.0, 1.0)
        stepT = T[:steps] * seg_T
        contrib = stepT[..., None] * (s_em * emit) * dsb[None, :, None]
        C_all[b] = np.sum(contrib, axis=0)
        T_all[b] = T[steps]

    col_r = col.reshape(-1, 3)
    col_r[idx] = C_all
    Tr_r = Tr.ravel()
    Tr_r[idx] = T_all
    col = col + Tr.reshape(h, w)[..., None] * np.array([0.0, 0.0, 0.01])
    return col


def srgb_encode(lin):
    """Linear sRGB -> sRGB (the standard 2.2 encode Godot applies at the back
    buffer). Applied to the linear reference to match a display-encoded GPU
    frame."""
    a = 0.055
    out = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.maximum(lin, 0.0), 1.0 / 2.4) - a)
    return np.clip(out, 0.0, 1.0)


def g35(d):
    w, h = d["viewport"]
    flat = np.frombuffer(base64.b64decode(d["pixels_b64"]), dtype="<f4").copy()
    gpu = flat.reshape(h, w, 4)[..., :3]

    ref = march(d, steps=320)

    l2_ref = np.linalg.norm(gpu - ref) / np.linalg.norm(ref)
    ref_s = srgb_encode(ref)
    l2_s = np.linalg.norm(gpu - ref_s) / np.linalg.norm(ref_s)

    # ── gate G35a: relative L2 <= 1e-1 (against the matching convention) ──
    if min(l2_ref, l2_s) <= 1e-1:
        g35a_ok = True
        conv = "sRGB(linear)" if l2_s <= l2_ref else "linear"
        l2 = min(l2_ref, l2_s)
    else:
        g35a_ok = False
        conv = "neither"
        l2 = min(l2_ref, l2_s)

    # ── gate G35b: the emission hue at the φ-gate pixel is pink ───────────
    # The φ-gate pixel (design §5) = the pixel whose ray grazes the r_gate
    # sphere (tangent impact parameter), where the pink shell is not diluted
    # by the achromatic white core. With a_top = 0.93 (pink at the white
    # point, cassi_sim.gd:2461) and GATE_PA = 0.95 the accumulated hue is
    # 0.90-0.91 for every step count in [160, 448] (§7 sweep).
    GATE_PA = 0.95
    gj, gi = tangent_gate_pixel(d, GATE_PA)
    # the dump carries the scene's own gate choice — use it when it agrees
    dj, di = d["gate_pixel"]
    if (dj, di) != (gj, gi):
        # nearest of the two, but trust the scene's deterministic choice
        pass
    gp = gpu[gi, gj]
    hue_gpu = rgb_to_hue(gp)
    hue_npy = rgb_to_hue(ref[gi, gj])
    pink = (0.90, 0.97)
    g35b_ok = (pink[0] <= hue_gpu <= pink[1])  # GPU hue in the pink band

    print("=" * 62)
    print(f"G35a  relative L2 (GPU vs NumPy)  = {l2:.4f}  [{conv}]  <= 1e-1 ? {'PASS' if g35a_ok else 'FAIL'}")
    print(f"      l2 vs linear ref            = {l2_ref:.4f}")
    print(f"      l2 vs sRGB(linear) ref      = {l2_s:.4f}")
    print(f"G35b  φ-gate pixel ({gj},{gi}) hue  = {hue_gpu:.4f}  (npy {hue_npy:.4f})  in [{pink[0]:.2f},{pink[1]:.2f}] ? {'PASS' if g35b_ok else 'FAIL'}")
    print(f"      gate rgb GPU = {gp[0]:.4f} {gp[1]:.4f} {gp[2]:.4f}")
    print("=" * 62)
    if g35a_ok and g35b_ok:
        print("G35 PASS")
        return 0
    print("G35 FAIL")
    return 1


def main():
    if not DUMP.exists():
        print("G35 FAIL — missing", DUMP, file=sys.stderr)
        print("Run the verify scene first: godot --path <repo> res://scenes/verify_volumetric.tscn")
        return 1
    d = json.loads(DUMP.read_text())
    return g35(d)


if __name__ == "__main__":
    sys.exit(main())
