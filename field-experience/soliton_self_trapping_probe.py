# Soliton self-trapping Wave-0 probe.
# FROZEN in field-experience/soliton-self-trapping-pre-registration.md.
#
# Integrates the theory-declared L_TF RHS (phi^4 + Bohm QP included) on a real
# doublet Psi=(P0,P1)=(E_Y,E_I):
#
#   d_t P0 =  a lap(P0) - nu lap^2(P0) + b |Psi|^2 P0
#          + 2 lam (P0^2 - phi P1^2) P0 - Q_B0 + c B P0
#   d_t P1 =  a lap(P1) - nu lap^2(P1) + b |Psi|^2 P1
#          - 2 lam phi (P0^2 - phi P1^2) P1 - Q_B1 + c B P1
#
# The LINEAR part is carried in the integrating factor (spectral, exact): with
# symbol -lap = -k^2 (decaying) and -nu lap^2 = -nu k^4 (damping), the linear
# half-step is unconditionally stable for any dt. phi^4/attractor/QP are RK4
# in real space. (The EL derivation gives hyperdiffusion sign -nu lap^2; a +nu
# lap^2 is anti-diffusive and exploded in diagnostics.)
#
# Seed: theory standing wave (qi-flow-double-helix.md:275) - rho=EY+EI localized
# Gaussian (sigma0 << box, no wrap discontinuity), phase theta=atan2(EI,EY)
# single winding (charge Q=1), q>=phi^-2 in the core.
#
# Reports per-arm: R(t) localization width, Q(t) charge, M(t) rest-mass,
# eps_mid(t), rad_frac(t) -> frozen verdict (H-HOLDS/H-DISPERSES/H-COLLAPSES).
import numpy as np
import numpy.fft as fft
import json, math, os, time

PHI = (1.0 + math.sqrt(5)) / 2.0
PI_ = 1.0 / PHI
BETA = PI_ / 2.0
DIAG = os.environ.get("WAVE0_DIAG", "0") == "1"

# ---- frozen coefficients (pre-reg §5) ----
A_DISP, NU, B_F4, LAM, C_BREATHE, QB_SCALE = 1.0, 0.01, 1.0, 0.1, 0.0, 1.0
TAU = 1.0          # cascade-unit time (normalized)

# ---- spectral operators (3D periodic). Laplacian symbol = -k^2; biharmonic +k^4.
def make_lap_ops(N, dx):
    k = np.fft.fftfreq(N, dx) * 2.0 * math.pi
    kx, ky, kz = np.meshgrid(k, k, k, indexing='ij')
    k2 = kx*kx + ky*ky + kz*kz
    return k2, k2*k2

def lap_fft(u, k2):
    return fft.ifftn((-k2) * fft.fftn(u)).real

def lap2_fft(u, K4):
    return fft.ifftn(K4 * fft.fftn(u)).real

# ---- Bohm QP functional derivative (exact discrete, verified in soliton_el_verify) ----
def qp_term(P0, P1, k2):
    M = np.maximum(P0*P0 + P1*P1, 1e-4)    # floor relative to seed scale (0.5)
    Mb = M ** BETA
    lapMb = lap_fft(Mb, k2)
    dM0, dM1 = 2.0*P0, 2.0*P1
    dMb0 = BETA * M**(BETA-1.0) * dM0
    dMb1 = BETA * M**(BETA-1.0) * dM1
    lapdMb0 = lap_fft(dMb0, k2)
    lapdMb1 = lap_fft(dMb1, k2)
    inv_Mb = np.where(Mb > 1e-10, 1.0/(Mb + 1e-10), 0.0)   # clipped inverse
    Q0 = (lapdMb0*inv_Mb - lapMb*dMb0*inv_Mb*inv_Mb)*M + (lapMb*inv_Mb)*dM0
    Q1 = (lapdMb1*inv_Mb - lapMb*dMb1*inv_Mb*inv_Mb)*M + (lapMb*inv_Mb)*dM1
    return -QB_SCALE*Q0, -QB_SCALE*Q1   # -Q_Ba (EL contribution)

def rhs(P0, P1, k2, K4, use_f4, use_qp, use_attr, nu, bf, lam):
    d0 = A_DISP*lap_fft(P0, k2) - nu*lap2_fft(P0, K4)
    d1 = A_DISP*lap_fft(P1, k2) - nu*lap2_fft(P1, K4)
    Ps2 = P0*P0 + P1*P1
    if use_f4:
        d0 += bf*Ps2*P0; d1 += bf*Ps2*P1
    if use_attr:
        c = P0*P0 - PHI*P1*P1
        d0 += 2.0*lam*c*P0
        d1 -= 2.0*lam*PHI*c*P1
    if use_qp:
        q0, q1 = qp_term(P0, P1, k2)
        d0 += q0; d1 += q1
    return d0, d1

def stats(P0, P1, dx, box):
    N = P0.shape[0]
    M = P0*P0 + P1*P1
    total = np.sqrt(M).sum()
    X, Y, Z = np.meshgrid(np.arange(N)*dx, np.arange(N)*dx, np.arange(N)*dx, indexing='ij')
    Xc, Yc, Zc = X-box/2, Y-box/2, Z-box/2
    R2 = (Xc*Xc+Yc*Yc+Zc*Zc)*M
    R = math.sqrt(max(R2.sum()/max(total, 1e-12), 0.0))
    dx3 = dx**3
    theta = np.arctan2(P1, P0)
    g = np.zeros_like(theta)
    for a in range(3):
        g += abs(np.roll(theta,-1,a)-np.roll(theta,1,a))/(2*dx)
    Q = (g*dx3).sum()/(2*math.pi)
    Mtot = total*dx3
    im = np.unravel_index(np.argmax(M), M.shape)
    eps_mid = P0[im]-PHI*P1[im]
    r2v = Xc*Xc+Yc*Yc+Zc*Zc
    core = r2v <= (2.0*0.1)**2
    rad = M[~core].sum()/max(M.sum(), 1e-12)
    qm = M[im]/(M[im]+PI_**2+eps_mid*eps_mid)
    return R, Q, Mtot, eps_mid, rad, qm

def seed(N, box, sigma0=0.1, m=1, Qtarget=1.0):
    """Standing-wave seed with m self-turn winding inside the lump.

    m=1 is the frozen single-turn baseline (theta=atan2(Y,X), Q~1 over the box).
    m>1 closes the Qi twist m times *within* sigma0 (tight twist): the phase
    gradient scales ~ m/r, steepening the Bohm-QP term that can oppose
    dispersion (owner hypothesis 2026-08-16, Amendment 1). cos^2/sin^2 keeps
    both components nonnegative.
    """
    x = np.arange(N)*box/N
    X, Y, Z = np.meshgrid(x, x, x, indexing='ij')
    Xc, Yc, Zc = X-box/2, Y-box/2, Z-box/2
    r2 = Xc*Xc+Yc*Yc+Zc*Zc
    g = np.exp(-r2/(2*sigma0*sigma0))     # peak = 1 at core (O(1) amplitude)
    theta = m*np.arctan2(Yc, Xc)          # m self-turns in the lump
    EY = 0.5*g*np.cos(theta)**2     # rho = EY+EI ~ g ~ 1 in core (no bg floor)
    EI = 0.5*g*np.sin(theta)**2
    return EY, EI

def integrate(P0, P1, k2, K4, dx, box, dt, n_steps, cfg, log_every=1):
    use_f4, use_qp, use_attr = cfg["f4"], cfg["qp"], cfg["attr"]
    nu = cfg.get("nu", NU); bf = cfg.get("bf", B_F4); lam = cfg.get("lam", LAM)
    # Exact linear propagator (Strang-split exponential): L(k) = a*(-k^2) - nu*k^4
    # is real & <=0 -> the linear half-steps are unconditionally stable. The
    # nonlinear terms are integrated by RK4 in real space between the two
    # linear half-steps (they are O(1), non-stiff). This removes the biharmonic
    # stiffness that made plain explicit RK4 catastrophic.
    lin_sym = (A_DISP*(-k2)) - nu*K4
    E_half = np.exp(0.5*lin_sym*dt)          # linear half-step propagator (Fourier)
    E_full = np.exp(lin_sym*dt)
    h = dt
    p0, p1 = P0.copy(), P1.copy()
    rec = {"t":[], "R":[], "Q":[], "M":[], "eps":[], "rad":[], "q":[]}
    for s in range(n_steps):
        # linear half-step (exact, spectral)
        p0 = fft.ifftn(E_half * fft.fftn(p0)).real
        p1 = fft.ifftn(E_half * fft.fftn(p1)).real
        # nonlinear RK4 step (phi4 + attractor + QP) in real space
        def nl(a, b):
            da = np.zeros_like(a); db = np.zeros_like(b)
            Ps2 = a*a + b*b
            if use_f4:
                da -= bf*Ps2*a; db -= bf*Ps2*b   # EL: L=-g/4|Psi|^4 -> -b|Psi|^2 (defocusing)
            if use_attr:
                c = a*a - PHI*b*b
                da -= 2.0*lam*c*a      # EL: L=-lam/2(...)^2 -> -2lam c P0 (verified)
                db += 2.0*lam*PHI*c*b  # EL: +2lam phi c P1 (verified)
            if use_qp:
                q0, q1 = qp_term(a, b, k2)
                da += q0; db += q1
            return da, db
        k0 = nl(p0, p1)
        k1 = nl(p0+0.5*h*k0[0], p1+0.5*h*k0[1])
        k2f = nl(p0+0.5*h*k1[0], p1+0.5*h*k1[1])
        k3 = nl(p0+h*k2f[0], p1+h*k2f[1])
        p0 = p0 + (h/6.0)*(k0[0]+2*k1[0]+2*k2f[0]+k3[0])
        p1 = p1 + (h/6.0)*(k0[1]+2*k1[1]+2*k2f[1]+k3[1])
        # second linear half-step
        p0 = fft.ifftn(E_half * fft.fftn(p0)).real
        p1 = fft.ifftn(E_half * fft.fftn(p1)).real
        p0 = np.maximum(p0, 0.0); p1 = np.maximum(p1, 0.0)
        if DIAG:
            print(f"[diag] s={s+1} amax={max(p0.max(), p1.max()):.3e} sumM={(p0*p0+p1*p1).sum():.3e}", flush=True)
        if (s+1) % log_every == 0:
            R, Q, Mt, eps, rad, qm = stats(p0, p1, dx, box)
            rec["t"].append((s+1)*dt); rec["R"].append(R); rec["Q"].append(Q)
            rec["M"].append(Mt); rec["eps"].append(eps); rec["rad"].append(rad); rec["q"].append(qm)
    return p0, p1, rec

def verdict(rec, R0):
    if not rec["R"]: return "no-rec"
    dM = abs(rec["M"][-1]-rec["M"][0])/max(rec["M"][0], 1e-12)
    dQ = abs(rec["Q"][-1]-rec["Q"][0])/max(rec["Q"][0], 1e-12)
    radf = rec["rad"][-1]
    Rmax = rec["R"][-1]
    if Rmax <= 2.0*R0 and dM < 1e-3 and dQ < 0.01 and radf < 0.5:
        return "H-HOLDS"
    if Rmax > 4.0*R0 or radf > 0.95:
        return "H-DISPERSES"
    if Rmax < 0.1*R0:
        return "H-COLLAPSES"
    return "H-DISPERSES"

def main():
    N = int(os.environ.get("WAVE0_N", 48))
    box = 1.0; dx = box/N
    k2, K4 = make_lap_ops(N, dx)
    EY, EI = seed(N, box)
    P0, P1 = EY.astype(float), EI.astype(float)
    R0 = stats(P0, P1, dx, box)[0]
    dt = 0.0005
    tau_steps = float(os.environ.get("WAVE0_TAU", "1"))
    n_steps = int(TAU*tau_steps/dt)
    arms = {
        "A0_full":    dict(f4=True, qp=True, attr=True),
        "A1_noF4":    dict(f4=False, qp=True, attr=True),
        "A2_noQP":    dict(f4=True, qp=False, attr=True),
        "A3_nu10x":   dict(f4=True, qp=True, attr=True, nu=10.0*NU),
        "A4_attr10x": dict(f4=True, qp=True, attr=True, lam=10.0*LAM),
    }
    out = {}
    for name, ac in arms.items():
        t0 = time.time()
        _, _, rec = integrate(P0, P1, k2, K4, dx, box, dt, n_steps, ac, log_every=max(1, n_steps//8))
        v = verdict(rec, R0)
        out[name] = {
            "verdict": v, "R_0": R0,
            "R_tmax": rec["R"][-1] if rec["R"] else None,
            "R_max": max(rec["R"]) if rec["R"] else None,
            "dM": abs(rec["M"][-1]-rec["M"][0])/max(rec["M"][0], 1e-12) if rec["M"] else None,
            "dQ": abs(rec["Q"][-1]-rec["Q"][0])/max(rec["Q"][0], 1e-12) if rec["Q"] else None,
            "rad_frac": rec["rad"][-1] if rec["rad"] else None,
            "eps_mid_tmax": rec["eps"][-1] if rec["eps"] else None,
            "q_mid_tmax": rec["q"][-1] if rec["q"] else None,
            "seconds": round(time.time()-t0, 1),
        }
        print(f"[soliton] {name}: {out[name]}", flush=True)
    print("[soliton] RESULT " + json.dumps(out))
    os.makedirs("_diag", exist_ok=True)
    with open("_diag/soliton_self_trapping.json", "w") as f:
        json.dump(out, f, indent=2)
    return out

if __name__ == "__main__":
    main()
