#!/usr/bin/env python3
"""Cassi Three-Body Problem—Attractor Search & Periodic Orbits.

Finds stable configurations that Cassi 3BP converges to under Qi damping.
"""

import math
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI


def cassi_force_mag(r, sigma, xi, q=1.0):
    """Cassi force magnitude (attractive, negative)."""
    if r < 1e-10:
        return 0.0
    s = r / (sigma * math.sqrt(2.0))
    return -(math.erf(s) - math.sqrt(2.0/math.pi) * s * math.exp(-s*s)) / (r*r) * (1.0 + xi*q)


def cassi_3body_rhs(t, y, masses, sigma, xi, eta_qi):
    pos = y[0:9].reshape(3, 3)
    vel = y[9:18].reshape(3, 3)
    acc = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            if i == j: continue
            r_vec = pos[j] - pos[i]
            r = np.linalg.norm(r_vec)
            if r < 1e-10: continue
            acc[i] += cassi_force_mag(r, sigma, xi) * masses[j] * r_vec / r
    return np.concatenate([vel.flatten(), (acc - eta_qi * vel).flatten()])


def integrate(y0, masses, sigma, xi, eta_qi, t_span, n_steps=1000):
    t_eval = np.linspace(*t_span, n_steps)
    sol = solve_ivp(cassi_3body_rhs, t_span, y0, args=(masses, sigma, xi, eta_qi),
                    method='RK45', t_eval=t_eval, rtol=1e-9, atol=1e-11)
    return sol.t, sol.y.T

def newtonian_energy(y, masses):
    """Fast Newtonian energy for time-series monitoring."""
    pos = y[0:9].reshape(3, 3)
    vel = y[9:18].reshape(3, 3)
    KE = 0.5 * sum(m * np.dot(v, v) for m, v in zip(masses, vel))
    PE = 0.0
    for i in range(3):
        for j in range(i+1, 3):
            r = np.linalg.norm(pos[j] - pos[i])
            if r > 1e-10:
                PE -= masses[i] * masses[j] / r
    return KE + PE




# ── ICs ──────────────────────────────────────────────────────────────

def lagrange_eq(masses, a=1.0):
    m = masses[0]
    pos = np.array([[0, a/math.sqrt(3), 0],
                    [-a/2, -a/(2*math.sqrt(3)), 0],
                    [a/2, -a/(2*math.sqrt(3)), 0]])
    omega = math.sqrt(3.0 * m / a**3)
    vel = omega * np.array([[-pos[0,1], pos[0,0], 0],
                            [-pos[1,1], pos[1,0], 0],
                            [-pos[2,1], pos[2,0], 0]])
    return np.concatenate([pos.flatten(), vel.flatten()])


def hierarchical(masses, a_in=0.3, a_out=2.0):
    m1, m2, m3 = masses
    M12 = m1 + m2
    w_in = math.sqrt(M12 / a_in**3)
    r1, r2 = m2/M12*a_in, m1/M12*a_in
    pos = np.array([[r1,0,0], [-r2,0,0], [a_out,0,0]])
    vel = np.array([[0,w_in*r1,0], [0,-w_in*r2,0], [0,math.sqrt(M12/a_out**3)*a_out,0]])
    return np.concatenate([pos.flatten(), vel.flatten()])


# ── Analysis ─────────────────────────────────────────────────────────

def analyze_lagrange_stability(masses, sigma, xi, eta_qi, a=1.0, t_max=200):
    """Test if Lagrange equilateral is stable under Cassi damping."""
    y0 = lagrange_eq(masses, a)
    t, states = integrate(y0, masses, sigma, xi, eta_qi, (0, t_max), 2000)

    # Track shape: compute side lengths and angles
    n = len(states)
    sides = np.zeros((n, 3))
    angles = np.zeros((n, 3))
    cassi_E = np.zeros(n)

    for k in range(n):
        pos = states[k, 0:9].reshape(3, 3)
        # Side lengths
        sides[k, 0] = np.linalg.norm(pos[1] - pos[0])
        sides[k, 1] = np.linalg.norm(pos[2] - pos[1])
        sides[k, 2] = np.linalg.norm(pos[0] - pos[2])
        # Angles (using law of cosines)
        for i in range(3):
            j, l = (i+1)%3, (i+2)%3
            a_side = sides[k, j]
            b_side = sides[k, (j+1)%3] if (j+1)%3 != i else sides[k, l]
            # angle at vertex i
            v1 = pos[j] - pos[i]
            v2 = pos[l] - pos[i]
            cos_ang = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-15)
            angles[k, i] = math.degrees(math.acos(np.clip(cos_ang, -1, 1)))
        cassi_E[k] = newtonian_energy(states[k], masses)

    return t, states, sides, angles, cassi_E


def search_periodic_orbit(masses, sigma, xi, eta_qi, a=1.0):
    """Shooting method: find period T such that y(T) = y(0) for Lagrange IC."""
    y0 = lagrange_eq(masses, a)

    def residual(T):
        t, states = integrate(y0, masses, sigma, xi, eta_qi, (0, T), 200)
        yT = states[-1]
        # Distance in phase space (positions only, ignore COM drift)
        pos0 = y0[0:9].reshape(3, 3)
        posT = yT[0:9].reshape(3, 3)
        # Center both
        com0 = np.mean(pos0, axis=0)
        comT = np.mean(posT, axis=0)
        pos0_c = pos0 - com0
        posT_c = posT - comT
        return np.sum((posT_c - pos0_c)**2)

    # Search for period near Keplerian value
    T_kepler = 2 * math.pi / math.sqrt(3.0 * masses[0] / a**3)
    print(f"  Keplerian period: T = {T_kepler:.4f}")

    # Scan periods
    Ts = np.linspace(T_kepler * 0.5, T_kepler * 2.0, 100)
    residuals = [residual(T) for T in Ts]
    best_idx = np.argmin(residuals)
    print(f"  Best period scan: T = {Ts[best_idx]:.4f}, residual = {residuals[best_idx]:.6e}")

    return Ts, residuals, T_kepler


# ── Plotting ─────────────────────────────────────────────────────────

def plot_stability(t, sides, angles, cassi_E, xi, eta_qi, filename):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Side lengths
    ax = axes[0, 0]
    colors = ['red', 'green', 'blue']
    for i in range(3):
        ax.plot(t, sides[:, i], color=colors[i], lw=1, label=f'side {i+1}')
    ax.set_title('Side Lengths (equilateral = constant)')
    ax.set_xlabel('Time'); ax.legend(); ax.grid(True, alpha=0.3)

    # Angles
    ax = axes[0, 1]
    for i in range(3):
        ax.plot(t, angles[:, i], color=colors[i], lw=1, label=f'angle {i+1}')
    ax.axhline(60, color='k', linestyle='--', alpha=0.3, label='60°')
    ax.set_title('Angles (equilateral = 60°)')
    ax.set_xlabel('Time'); ax.legend(); ax.grid(True, alpha=0.3)

    # Energy
    ax = axes[1, 0]
    ax.plot(t, cassi_E, 'k-', lw=1)
    ax.set_title('Newtonian Energy (reference)')
    ax.set_xlabel('Time'); ax.set_ylabel('E'); ax.grid(True, alpha=0.3)

    # Side length ratios (deviation from equilateral)
    ax = axes[1, 1]
    mean_side = np.mean(sides, axis=1)
    for i in range(3):
        ratio = sides[:, i] / (mean_side + 1e-15)
        ax.plot(t, ratio - 1.0, color=colors[i], lw=1, label=f'side {i+1}')
    ax.axhline(0, color='k', linestyle='--', alpha=0.3)
    ax.set_title('Deviation from Equilateral (0 = perfect)')
    ax.set_xlabel('Time'); ax.legend(); ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.1, 0.1)

    plt.suptitle(f'Lagrange Stability: xi={xi}, eta={eta_qi}', fontsize=12)
    plt.tight_layout()
    plt.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def plot_period_search(Ts, residuals, T_kepler, xi, eta_qi, filename):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.semilogy(Ts, [max(r, 1e-15) for r in residuals], 'b-', lw=1.5)
    ax.axvline(T_kepler, color='r', linestyle='--', label=f'Keplerian T={T_kepler:.3f}')
    ax.set_xlabel('Period T')
    ax.set_ylabel('Residual |y(T)-y(0)|^2')
    ax.set_title(f'Periodic Orbit Search (xi={xi}, eta={eta_qi})')
    ax.legend(); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    masses = np.array([1.0, 1.0, 1.0])
    sigma = 0.1

    print("=" * 65)
    print("Cassi Three-Body: Attractor Search & Periodic Orbits")
    print("=" * 65)

    # ── Test 1: Lagrange stability under different damping ──────────
    for eta_qi in [0.0, 0.05, 0.1, 0.2]:
        print(f"\n{'─' * 55}")
        print(f"  Lagrange stability: eta_Qi = {eta_qi}")
        print(f"{'─' * 55}")
        t, states, sides, angles, cassi_E = analyze_lagrange_stability(
            masses, sigma, xi=18.0, eta_qi=eta_qi, a=1.0, t_max=200)
        # Final shape quality
        final_sides = sides[-1]
        shape_error = np.std(final_sides) / np.mean(final_sides)
        final_angles = angles[-1]
        angle_error = np.std(final_angles)
        print(f"  Final side lengths: {final_sides}")
        print(f"  Shape error (side std/mean): {shape_error:.6f}")
        print(f"  Final angles: {final_angles}")
        print(f"  Angle std: {angle_error:.2f}°")
        print(f"  E_Cassi: {cassi_E[0]:.4f} -> {cassi_E[-1]:.4f}")
        plot_stability(t, sides, angles, cassi_E, 18.0, eta_qi,
                       f"cassi_3body_stability_eta{eta_qi:.2f}.png")

    # ── Test 2: Periodic orbit search ────────────────────────────────
    print(f"\n{'─' * 55}")
    print(f"  Periodic orbit search (xi=18, eta=0.1)")
    print(f"{'─' * 55}")
    Ts, residuals, T_kepler = search_periodic_orbit(masses, sigma, xi=18.0, eta_qi=0.1, a=1.0)
    plot_period_search(Ts, residuals, T_kepler, 18.0, 0.1,
                       f"cassi_3body_period_search.png")

    # ── Test 3: Random ICs -> attractor ─────────────────────────────
    print(f"\n{'─' * 55}")
    print(f"  Random ICs -> attractor convergence")
    print(f"{'─' * 55}")
    np.random.seed(42)
    for trial in range(3):
        # Random positions in [-1,1]^3, zero net momentum
        pos = np.random.randn(3, 3) * 0.5
        pos -= np.mean(pos, axis=0)  # zero COM
        vel = np.random.randn(3, 3) * 0.1
        vel -= np.mean(vel * masses[:, None], axis=0) / np.mean(masses)  # zero momentum
        y0 = np.concatenate([pos.flatten(), vel.flatten()])
        t, states = integrate(y0, masses, sigma, xi=18.0, eta_qi=0.1,
                              t_span=(0, 100), n_steps=1000)

        # Final configuration
        final_pos = states[-1, 0:9].reshape(3, 3)
        final_vel = states[-1, 9:18].reshape(3, 3)
        sides_final = [np.linalg.norm(final_pos[(i+1)%3] - final_pos[i]) for i in range(3)]
        speeds = [np.linalg.norm(final_vel[i]) for i in range(3)]
        E_final = newtonian_energy(states[-1], masses)
        print(f"  Trial {trial+1}: sides={sides_final}, speeds={speeds}, E={E_final:.4f}")

    print("\n" + "=" * 65)
    print("Done.")
    print("=" * 65)


if __name__ == '__main__':
    main()
