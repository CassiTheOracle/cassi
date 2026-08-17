# Verify the within-scale balance fixed point eps*(rho) of the two-fluid
# element reaction (conv = wake), and the repeller nature of the phi-line.
# Companion to `soliton-self-trapping-pre-registration.md` §1 + §0.
#
# reaction (field_experience.py, frozen): conv = lambda*(1-q)*eps,
#   wake = kappa*tanh(eps/SAT), d_eps ∝ wake - conv.
# Fixed point: conv = wake  =>  lambda*(1-q(eps,rho))*eps = kappa*tanh(eps/SAT).
import math

PHI = (1 + math.sqrt(5)) / 2
PI_ = 1.0 / PHI
LAMBDA, KAPPA, SAT = 0.1, 0.05, 0.6

def f(e, rho):
    q = rho * rho / (rho * rho + PI_ * PI_ + e * e)
    return LAMBDA * (1.0 - q) * e - KAPPA * math.tanh(e / SAT)

def dflow(e, rho):
    h = 1e-5
    return -(f(e + h, rho) - f(e - h, rho)) / (2.0 * h)  # d(eps)/dt slope; stable if <0

def root(rho, lo, hi):
    for _ in range(150):
        m = 0.5 * (lo + hi)
        if f(m, rho) * f(lo, rho) <= 0.0:
            hi = m
        else:
            lo = m
    return 0.5 * (lo + hi)

def main():
    for rho in [1.0, 1.25, PHI, 2.0]:
        prev = (0.0001, f(0.0001, rho))
        e = 0.01
        roots = []
        while e < 2.6:
            v = f(e, rho)
            if prev[1] * v <= 0.0:
                roots.append(root(rho, prev[0], e))
            prev = (e, v)
            e += 0.01
        s0 = dflow(0.0, rho)
        row = f"rho={rho:.4f}: phi-line(eps=0) flow_slope={s0:+.4f} -> {'STABLE' if s0 < 0 else 'REPELLER'};  "
        cells = []
        for e0 in roots:
            s = dflow(e0, rho)
            q = rho * rho / (rho * rho + PI_ * PI_ + e0 * e0)
            cells.append(f"eps*={e0:.4f} q={q:.3f} flow_slope={s:+.4f} -> {'STABLE' if s < 0 else 'UNSTABLE'}")
        print(row + " | ".join(cells))

if __name__ == "__main__":
    main()
