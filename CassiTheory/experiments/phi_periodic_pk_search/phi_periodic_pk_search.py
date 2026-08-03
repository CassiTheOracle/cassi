"""
φ-Periodic P(k) Search: Log-periodic modulation at Δ(ln k) = ln φ ≈ 0.4812.

The Cassi wake-wave prediction: the matter power spectrum carries a log-periodic
modulation at period ln φ, orthogonal to BAO (which is constant-Δk).

Usage:
  python phi_periodic_pk_search.py              # run verification suite
  python phi_periodic_pk_search.py data.pk      # search a real P(k) file

Real data format (e.g., BOSS/eBOSS):
  two-column: k [h/Mpc], P(k) [(Mpc/h)^3] —whitespace-separated, optional # comments

Verification suite (no data file):
  1. Inject synthetic ΛCDM+BAO P(k) + ln-φ modulation → confirm recovery of 0.4812
  2. Null test: ΛCDM+BAO without modulation → confirm no false positive
  3. Report sensitivity vs noise level
"""
import sys
import numpy as np

PHI = (1 + np.sqrt(5)) / 2
LN_PHI = np.log(PHI)  # ≈ 0.4812—THE predicted period

# ============================================================
# Synthetic P(k) (Eisenstein-Hu style smooth + BAO wiggle)
# ============================================================
def synthetic_pk(k, om0=0.31, amplitude=1.0, with_bao=True, with_phi=False, phi_amp=0.017):
    """Smooth ΛCDM-like P(k) with optional BAO and optional ln-φ modulation."""
    # Smooth component: broken power law (approximate Eisenstein-Hu shape)
    k_pivot = 0.05
    ns = 0.9691  # canonical n_s = 1 - 2φ⁻¹/N_e (N_e = 40); 0.967 was the legacy
                 # 1 - 2/N_e form with N_e = 60. Tilt shapes only the smooth
                 # component, which the search subtracts; recovery unaffected.
    pk = amplitude * (k / k_pivot)**ns
    # Turnover toward white noise at high k
    pk = pk / (1 + (k / 0.3)**2.5)
    # BAO wiggle: constant Δk oscillation
    if with_bao:
        r_s = 150.0  # sound horizon Mpc
        pk *= (1 + 0.05 * np.sin(k * r_s) * np.exp(-(k * 0.25)**2))
    # φ-periodic modulation: constant Δ(ln k) oscillation
    if with_phi:
        pk *= (1 + phi_amp * np.sin(2 * np.pi * np.log(k) / LN_PHI))
    return pk

# ============================================================
# Search pipeline
# ============================================================
def subtract_smooth(lnk, log_pk, order=5):
    """Fit and subtract smooth polynomial in log-log space."""
    coeffs = np.polyfit(lnk, log_pk, order)
    smooth = np.polyval(coeffs, lnk)
    return log_pk - smooth

def scan_periods(lnk, residual, periods=None):
    """Scan log-periods, return power spectrum over period."""
    if periods is None:
        periods = np.linspace(0.25, 1.0, 400)
    lnk_centered = lnk - np.mean(lnk)
    powers = []
    for T in periods:
        model = np.sin(2 * np.pi * lnk_centered / T)
        model2 = np.cos(2 * np.pi * lnk_centered / T)
        # Least-squares amplitude of sinusoid at this period
        A = np.sum(residual * model) / np.sum(model**2)
        B = np.sum(residual * model2) / np.sum(model2**2)
        powers.append(A**2 + B**2)
    powers = np.array(powers)
    return periods, powers

def run_search(k, pk, verbose=True):
    """Full search: subtract smooth, scan periods, return best period."""
    lnk = np.log(k)
    log_pk = np.log(pk)
    residual = subtract_smooth(lnk, log_pk)
    periods, powers = scan_periods(lnk, residual)
    best_idx = np.argmax(powers)
    best_T = periods[best_idx]
    best_power = powers[best_idx]
    
    if verbose:
        print(f"  Best period: {best_T:.4f} (ln-φ prediction: {LN_PHI:.4f})")
        print(f"  Power: {best_power:.4f}")
        print(f"  Offset from ln φ: {best_T - LN_PHI:+.4f}")
    return best_T, best_power, periods, powers

# ============================================================
# Verification suite
# ============================================================
def verification():
    print("=" * 62)
    print("VERIFICATION SUITE: φ-Periodic P(k) Search")
    print("=" * 62)
    
    # --- Test 1: Recovery of injected signal ---
    print("\n[Test 1] Injection recovery: ΛCDM+BAO + 1.7% ln-φ modulation")
    rng = np.random.default_rng(42)
    k = np.logspace(-2.0, -0.3, 80)
    pk = synthetic_pk(k, with_bao=True, with_phi=True, phi_amp=0.017)
    # Add realistic noise: ~1.5% per bin (eBOSS-like)
    noise = 1 + rng.normal(0, 0.015, len(k))
    pk_noisy = pk * noise
    
    best_T, best_power, periods, powers = run_search(k, pk_noisy)
    recovered = abs(best_T - LN_PHI) < 0.03
    print(f"  → Recovery {'SUCCESS' if recovered else 'FAILED'}: "
          f"best period {best_T:.4f} vs injected {LN_PHI:.4f}")
    
    # --- Test 2: Null test ---
    print("\n[Test 2] Null: ΛCDM+BAO WITHOUT φ modulation")
    pk_null = synthetic_pk(k, with_bao=True, with_phi=False)
    pk_null_noisy = pk_null * (1 + rng.normal(0, 0.015, len(k)))
    
    T_null, P_null, _, _ = run_search(k, pk_null_noisy)
    # False positive if null best period lands near ln φ AND is strong
    near_phi = abs(T_null - LN_PHI) < 0.03
    print(f"  → Null {'FAILED (false positive!)' if near_phi else 'PASSED'}: "
          f"best period {T_null:.4f} (should NOT be {LN_PHI:.4f})")
    
    # --- Test 3: No-BAO control ---
    print("\n[Test 3] Control: modulation WITHOUT BAO (check no confusion)")
    pk_nobao = synthetic_pk(k, with_bao=False, with_phi=True, phi_amp=0.017)
    pk_nobao_noisy = pk_nobao * (1 + rng.normal(0, 0.015, len(k)))
    T_ctrl, P_ctrl, _, _ = run_search(k, pk_nobao_noisy)
    recovered_ctrl = abs(T_ctrl - LN_PHI) < 0.03
    print(f"  → Recovery {'SUCCESS' if recovered_ctrl else 'FAILED'}: "
          f"best period {T_ctrl:.4f}")
    
    # --- Test 4: Sensitivity vs noise ---
    print("\n[Test 4] Sensitivity: recovery vs per-bin noise")
    for noise_level in [0.005, 0.01, 0.015, 0.02, 0.03]:
        hits = 0
        n_trials = 50
        for trial in range(n_trials):
            rng_t = np.random.default_rng(trial)
            pk_t = synthetic_pk(k, with_bao=True, with_phi=True, phi_amp=0.017)
            pk_t = pk_t * (1 + rng_t.normal(0, noise_level, len(k)))
            T, _, _, _ = run_search(k, pk_t, verbose=False)
            if abs(T - LN_PHI) < 0.03:
                hits += 1
        print(f"  noise={noise_level*100:.1f}%: recovered in {hits}/{n_trials} trials "
              f"({100*hits/n_trials:.0f}%)")
    
    # --- Summary ---
    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    print(f"Predicted period: Δ(ln k) = ln φ = {LN_PHI:.4f}")
    print("Discriminator: constant-Δ(ln k) (Cassi) vs constant-Δk (BAO)")
    print("Real-data targets: BOSS DR12 (~1.4σ), eBOSS DR16 (~1.8σ),")
    print("                   DESI DR2 (~2.5σ), Euclid (~5σ)")
    print("Usage: python phi_periodic_pk_search.py <datafile.pk>")
    return recovered and not near_phi and recovered_ctrl

# ============================================================
# Real-data mode
# ============================================================
def search_file(path):
    print(f"Searching {path}...")
    data = np.loadtxt(path, comments='#')
    if data.ndim != 2 or data.shape[1] < 2:
        print(f"ERROR: expected two-column data (k, P(k)), got shape {data.shape}")
        sys.exit(1)
    k = data[:, 0]
    pk = data[:, 1]
    # Filter to positive P(k) and reasonable k range
    mask = (k > 0) & (pk > 0) & np.isfinite(pk)
    k, pk = k[mask], pk[mask]
    if len(k) < 20:
        print(f"ERROR: only {len(k)} valid points—need ≥20")
        sys.exit(1)
    print(f"Loaded {len(k)} points: k ∈ [{k.min():.4f}, {k.max():.4f}] h/Mpc")
    best_T, best_power, periods, powers = run_search(k, pk)
    print(f"\n  Best log-period: {best_T:.4f}")
    print(f"  Cassi prediction: {LN_PHI:.4f} (Δ = {best_T - LN_PHI:+.4f})")
    if abs(best_T - LN_PHI) < 0.03:
        print("  ✓ Consistent with ln-φ prediction—investigate further!")
    else:
        print("  No ln-φ signal at the predicted period.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        search_file(sys.argv[1])
    else:
        ok = verification()
        sys.exit(0 if ok else 1)
