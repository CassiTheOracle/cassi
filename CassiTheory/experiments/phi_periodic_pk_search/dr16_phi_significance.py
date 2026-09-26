"""
DR16 φ-Periodic P(k) Significance Test

Compares the DR16 LRG power spectrum against the null distribution
established by 1000 EZmocks (no Cassi signal).

Method:
  1. For each P(k) (data + 1000 mocks):
     a. Subtract smooth polynomial (log-log, order 5)
     b. Scan log-periods 0.25-1.0 for sinusoidal power
     c. Record best period and best power
  2. Null distribution = best-power distribution from mocks
  3. Data significance = percentile of data's best power
  4. Also: fraction of mocks whose best period lands near ln φ
     with comparable power (the "false alignment" rate)

Usage: python dr16_phi_significance.py
"""
import numpy as np
import glob, os, time

PHI = (1 + np.sqrt(5)) / 2
LN_PHI = np.log(PHI)  # 0.4812
EXPECTED_MOCKS = 1000
_HERE = os.path.dirname(os.path.abspath(__file__))


def load_pk(path, col=2):
    """Load k and P0. Handles 2-column clean files or 7-column raw files."""
    d = np.loadtxt(path, comments='#')
    if d.ndim == 1:
        return None, None
    if d.shape[1] == 2:
        k, pk = d[:, 0], d[:, 1]
    else:
        k = d[:, 1]
        pk = d[:, col]
    mask = (k > 0) & (pk > 0) & np.isfinite(pk)
    return k[mask], pk[mask]

def subtract_smooth(lnk, log_pk, order=5):
    coeffs = np.polyfit(lnk, log_pk, order)
    return log_pk - np.polyval(coeffs, lnk)

def scan_periods(lnk, residual, periods):
    lnk_c = lnk - np.mean(lnk)
    powers = np.zeros(len(periods))
    for i, T in enumerate(periods):
        model_s = np.sin(2 * np.pi * lnk_c / T)
        model_c = np.cos(2 * np.pi * lnk_c / T)
        A = np.sum(residual * model_s) / np.sum(model_s**2)
        B = np.sum(residual * model_c) / np.sum(model_c**2)
        powers[i] = A**2 + B**2
    return powers

def best_period_power(k, pk, periods=None):
    if periods is None:
        periods = np.linspace(0.25, 1.0, 300)
    lnk = np.log(k)
    residual = subtract_smooth(lnk, np.log(pk))
    powers = scan_periods(lnk, residual, periods)
    idx = np.argmax(powers)
    return periods[idx], powers[idx], residual, lnk

# ============================================================
print("=" * 62)
print("DR16 φ-Periodic P(k) Significance Test")
print("=" * 62)

periods = np.linspace(0.25, 1.0, 300)

# --- Data ---
k_data, pk_data = load_pk(os.path.join(_HERE, 'dr16_lrg_pk_clean.txt'))
if k_data is None or len(k_data) < 20:
    raise RuntimeError("DR16 data file has fewer than 20 valid positive bins")
T_data, P_data, res_data, lnk_data = best_period_power(k_data, pk_data, periods)
if not np.isfinite(P_data):
    raise RuntimeError("DR16 best-period power is non-finite")
print(f"\nData (DR16 LRG NGCSGC, {len(k_data)} bins):")
print(f"  Best period: {T_data:.4f}  (ln φ = {LN_PHI:.4f}, Δ = {T_data - LN_PHI:+.4f})")
print(f"  Best power:  {P_data:.6f}")

# --- Mocks ---
mock_files = sorted(glob.glob(os.path.join(
    _HERE, 'ezmock_pk', 'Power_Spectrum_comb_NGCSGC_ezmocks_*.txt')))
print(f"\nEZmocks found: {len(mock_files)}")

mock_T = np.zeros(len(mock_files))
mock_P = np.zeros(len(mock_files))
for i, f in enumerate(mock_files):
    k, pk = load_pk(f)
    if k is None or len(k) < 20:
        continue
    T, P, _, _ = best_period_power(k, pk, periods)
    mock_T[i], mock_P[i] = T, P
    if (i + 1) % 200 == 0:
        print(f"  processed {i+1}/{len(mock_files)}")

valid = (mock_P > 0) & np.isfinite(mock_P) & np.isfinite(mock_T)
valid_files = [f for f, keep in zip(mock_files, valid) if keep]
mock_T, mock_P = mock_T[valid], mock_P[valid]
print(f"Valid mocks: {len(mock_P)}")
if len(mock_P) != EXPECTED_MOCKS:
    raise RuntimeError(
        f"Null calibration unavailable: expected {EXPECTED_MOCKS} valid EZmocks, "
        f"found {len(mock_P)}")

# --- Significance ---
# 1. Percentile of data power in null power distribution
pct = 100 * (mock_P < P_data).mean()
print(f"\n=== Significance ===")
print(f"Data power {P_data:.6f} exceeds {pct:.1f}% of mock powers")
print(f"→ Data is at the {pct:.1f}th percentile of the null distribution")

# 2. False-alignment rate: mocks with best period near ln φ
near = np.abs(mock_T - LN_PHI) < 0.03
print(f"  Mocks with best period within 0.03 of ln φ: {near.sum()}/{len(mock_P)} "
      f"({100*near.mean():.1f}%)")

# 3. Mocks with period near ln φ AND power ≥ data
near_power = np.abs(mock_T - LN_PHI) < 0.03
strong_near = near_power & (mock_P >= P_data)
print(f"  Mocks with period near ln φ AND power ≥ data: {strong_near.sum()}/{len(mock_P)}")

# 4. Bootstrap significance: how often does a random period win?
#    If data's best period is genuinely ln φ, it should be near ln φ AND
#    the power at ln φ specifically should be a local peak.
#    Compute power AT ln φ for data and mocks:
def power_at(lnk, residual, T):
    lnk_c = lnk - np.mean(lnk)
    s = np.sin(2 * np.pi * lnk_c / T)
    c = np.cos(2 * np.pi * lnk_c / T)
    A = np.sum(residual * s) / np.sum(s**2)
    B = np.sum(residual * c) / np.sum(c**2)
    return A**2 + B**2

P_data_phi = power_at(lnk_data, res_data, LN_PHI)
if not np.isfinite(P_data_phi):
    raise RuntimeError("DR16 power at ln(phi) is non-finite")
print(f"\nPower specifically at ln φ = {P_data_phi:.6f} (vs best {P_data:.6f})")
ratio = P_data_phi / P_data if P_data > 0 else 0
print(f"Ratio P(ln φ)/P(best) = {ratio:.2f}")

mock_P_phi = np.zeros(len(mock_P))
for i in range(len(mock_P)):
    k, pk = load_pk(valid_files[i])
    if k is None or len(k) < 20:
        raise RuntimeError(f"Validated mock became unreadable: {valid_files[i]}")
    lnk = np.log(k)
    res = subtract_smooth(lnk, np.log(pk))
    mock_P_phi[i] = power_at(lnk, res, LN_PHI)
if not np.all(np.isfinite(mock_P_phi)):
    raise RuntimeError("At least one validated mock produced non-finite power at ln(phi)")

pct_phi = 100 * (mock_P_phi < P_data_phi).mean()
print(f"Power at ln φ exceeds {pct_phi:.1f}% of mocks (one-sided p = {1 - pct_phi/100:.3f})")

# --- Summary ---
print("\n" + "=" * 62)
print("VERDICT")
print("=" * 62)
print(f"Best-fit period: {T_data:.4f} vs prediction {LN_PHI:.4f} (Δ={T_data-LN_PHI:+.4f})")
if pct >= 99:
    print(f"Data power is at {pct:.1f}th percentile → suggestive")
elif pct >= 95:
    print(f"Data power is at {pct:.1f}th percentile → marginal hint")
else:
    print(f"Data power is at {pct:.1f}th percentile → consistent with noise")
print(f"Note: 32 bins span ~8.6 log-periods; {len(mock_P)} mocks for the null")
