"""
DESI DR1 LRG_N monopole P(k) via FFT-based FKP estimator (numpy only).

Paints data and randoms with CIC onto a 3D mesh, FFTs, and computes
the FKP power spectrum using pypower's exact normalization conventions:

    F(k) = FFT(data_mesh) - alpha * FFT(rand_mesh)
    shot = sum_d w_d^2 + alpha^2 * sum_r w_r^2      (sum of squares)
    I2   = alpha * sum_r w_r^2
    P(k) = (|F(k)|^2 - shot) / I2   averaged over spherical shells

All modes are used (no Monte Carlo) -> cosmic-variance-limited errors.
For the log-periodic search only the relative shape matters; the smooth
polynomial fit absorbs any constant normalization.
"""
import numpy as np
from astropy.io import fits
from astropy.cosmology import FlatLambdaCDM
import time
import os, sys

PHI = (1 + np.sqrt(5)) / 2
COSMO = FlatLambdaCDM(H0=67.77, Om0=0.309)

# Paths relative to this script so it runs from anywhere
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'phi_periodic_pk_search'))

DATA_FILE = os.path.join(_HERE, 'desi_lrg_n', 'LRG_N_clustering.dat.fits')
RAN_FILES = [os.path.join(_HERE, 'desi_lrg_n', f'LRG_N_{i}_clustering.ran.fits') for i in range(18)]
OUT_PK = os.path.join(_HERE, 'desi_lrg_n_pk.txt')
N_RAN_FILES = 18  # full random set


def load_catalog(fname):
    hdul = fits.open(fname)
    d = hdul['LSS'].data
    hdul.close()
    good = d['Z'] > 0
    d = d[good]
    w = d['WEIGHT'].astype(float) * d['WEIGHT_FKP'].astype(float)
    return d['RA'], d['DEC'], d['Z'], w


def to_xyz(ra, dec, z):
    r = COSMO.comoving_distance(z).value / 0.6777  # Mpc/h
    ra_r, dec_r = np.radians(ra), np.radians(dec)
    return np.column_stack([
        r * np.cos(dec_r) * np.cos(ra_r),
        r * np.cos(dec_r) * np.sin(ra_r),
        r * np.sin(dec_r)
    ])


def paint_cic(pos, w, boxsize, nmesh):
    """Paint weighted positions onto a mesh with CIC assignment."""
    mesh = np.zeros((nmesh, nmesh, nmesh), dtype='f4')
    cell = boxsize / nmesh
    # Fractional cell coordinates
    f = pos / cell - 0.5
    i0 = np.floor(f).astype(int)
    frac = f - i0
    # Periodic wrap
    i0 = np.mod(i0, nmesh)
    i1 = np.mod(i0 + 1, nmesh)
    fx = frac[:, 0]; fy = frac[:, 1]; fz = frac[:, 2]

    # 8 CIC contributions (indices pre-wrapped)
    for dx, wx in [(0, 1 - fx), (1, fx)]:
        for dy, wy in [(0, 1 - fy), (1, fy)]:
            for dz, wz in [(0, 1 - fz), (1, fz)]:
                wc = w * wx * wy * wz
                ix = np.where(dx == 0, i0[:, 0], i1[:, 0])
                iy = np.where(dy == 0, i0[:, 1], i1[:, 1])
                iz = np.where(dz == 0, i0[:, 2], i1[:, 2])
                np.add.at(mesh, (ix, iy, iz), wc)
    return mesh


def fkp_power(pos_d, w_d, pos_r, w_r, boxsize, nmesh, kmin, kmax, nkbins):
    """FFT-based FKP monopole power spectrum (numpy, float32 meshes).

    Painting: weight per cell (no density factor). FFT: raw numpy (no 1/N).
    The painted-field FFT equals the continuous sum F(k)=Σ w_i e^{ik·r_i}
    up to CIC assignment smoothing, so:
      I2   = Σ_d w_d²          (standard FKP normalization)
      shot = Σ_d w_d² + α² Σ_r w_r²
      P(k) = ⟨|F|²/W2⟩/I2 − shot/I2   (W2 = CIC kernel squared)
    α = Σw_d/Σw_r (measured ratio) so the window cancels exactly.
    """
    t0 = time.time()
    print(f"  Painting data mesh ({nmesh}³, box {boxsize:.0f} Mpc/h)...")
    mesh_d = paint_cic(pos_d, w_d, boxsize, nmesh)
    mesh_r = paint_cic(pos_r, w_r, boxsize, nmesh)
    print(f"  Painting done ({time.time()-t0:.1f}s)")

    # FKP normalization (MEASURED units — no ×18)
    alpha = w_d.sum() / w_r.sum()
    I2 = (w_d**2).sum()
    shot = I2 + alpha**2 * (w_r**2).sum()
    print(f"  alpha = {alpha:.6f}, I2 = {I2:.0f}, shot = {shot:.0f}, shot/I2 = {shot/I2:.4f}")

    # FFTs — one at a time, cast to complex64 to save memory
    print(f"  FFT data...")
    FFT_d = np.fft.rfftn(mesh_d).astype(np.complex64)
    del mesh_d
    print(f"  FFT randoms...")
    FFT_r = np.fft.rfftn(mesh_r).astype(np.complex64)
    del mesh_r
    F = FFT_d - alpha * FFT_r
    del FFT_d, FFT_r
    P_raw = np.abs(F)**2  # float32
    del F
    print(f"  FFT done ({time.time()-t0:.1f}s)")

    # k grids (1D, no full 3D meshgrid)
    k_nyq = np.pi * nmesh / boxsize
    print(f"  Nyquist k = {k_nyq:.4f} h/Mpc (need ≥ {kmax})")
    dk_f = 2 * np.pi / boxsize
    kx = dk_f * np.fft.fftfreq(nmesh).astype(np.float32) * nmesh
    ky = kx.copy()
    kz = dk_f * np.fft.rfftfreq(nmesh).astype(np.float32) * nmesh

    # Per-mode k magnitude via broadcasting (float32, no 3D temp of f8)
    # kmag[i,j,l] = sqrt(kx[i]² + ky[j]² + kz[l]²)
    cell = boxsize / nmesh
    # CIC compensation: |W|² = prod_axes sinc⁴(k_axis·cell/2)
    with np.errstate(divide='ignore', invalid='ignore'):
        W2x = np.sinc(kx * cell / (2 * np.pi))**4
        W2y = np.sinc(ky * cell / (2 * np.pi))**4
        W2z = np.sinc(kz * cell / (2 * np.pi))**4
    # Guard near-zero (k=0 gives sinc=1, fine; nothing is zero elsewhere)

    k_edges = np.linspace(kmin, kmax, nkbins + 1)
    k_centers = 0.5 * (k_edges[:-1] + k_edges[1:])
    P_bins = np.zeros(nkbins)
    N_modes = np.zeros(nkbins)

    # Loop over shells; compute W2 per shell by broadcasting 1D arrays
    for i in range(nkbins):
        k_lo, k_hi = k_edges[i], k_edges[i+1]
        # Per-shell masks without materializing full kmag: iterate axes
        # Use a chunked approach: mask x,y then slice z
        # Simpler: compute kmag in float32 with broadcasting but chunked over kz
        n_chunks = 16
        nz = len(kz)
        cum_num = 0.0
        cum_P = 0.0
        for c in range(n_chunks):
            zs = slice(c * nz // n_chunks, (c + 1) * nz // n_chunks)
            kmag_c = np.sqrt(kx[:, None, None]**2 + ky[None, :, None]**2
                             + kz[None, None, zs]**2).astype(np.float32)
            mask_c = (kmag_c >= k_lo) & (kmag_c < k_hi)
            n_c = mask_c.sum()
            if n_c == 0:
                continue
            w2_c = (W2x[:, None, None] * W2y[None, :, None]
                    * W2z[None, None, zs])
            cum_num += n_c
            cum_P += (P_raw[:, :, zs][mask_c] / w2_c[mask_c]).sum()
        if cum_num > 0:
            N_modes[i] = cum_num
            P_bins[i] = (cum_P / cum_num - shot) / I2

    print(f"  Binning done ({time.time()-t0:.1f}s), total modes: {N_modes.sum():.0f}")
    return k_centers, P_bins, N_modes


def main():
    t0 = time.time()
    print("=" * 62)
    print("DESI DR1 LRG_N P(k): FFT-based FKP estimator (numpy)")
    print("=" * 62)

    print(f"\nLoading {DATA_FILE}...")
    ra_d, dec_d, z_d, w_d = load_catalog(DATA_FILE)
    print(f"  {len(z_d)} galaxies, z ∈ [{z_d.min():.3f}, {z_d.max():.3f}], Σw = {w_d.sum():.0f}")

    print(f"\nLoading {len(RAN_FILES)} random files...")
    ra_r_all, dec_r_all, z_r_all, w_r_all = [], [], [], []
    for fname in RAN_FILES:
        ra, dec, z, w = load_catalog(fname)
        ra_r_all.append(ra); dec_r_all.append(dec); z_r_all.append(z); w_r_all.append(w)
    ra_r = np.concatenate(ra_r_all)
    dec_r = np.concatenate(dec_r_all)
    z_r = np.concatenate(z_r_all)
    w_r = np.concatenate(w_r_all)
    print(f"  {len(z_r)} randoms total, Σw = {w_r.sum():.0f}")

    print("\nConverting to Cartesian...")
    pos_d = to_xyz(ra_d, dec_d, z_d)
    pos_r = to_xyz(ra_r, dec_r, z_r)

    # Use one redshift bin (0.6 < z < 0.8) to keep the box compact
    z_lo, z_hi = 0.6, 0.8
    m_d = (z_d >= z_lo) & (z_d <= z_hi)
    m_r = (z_r >= z_lo) & (z_r <= z_hi)
    pos_d, w_d = pos_d[m_d], w_d[m_d]
    pos_r, w_r = pos_r[m_r], w_r[m_r]
    print(f"  z∈[{z_lo},{z_hi}] bin: {len(w_d)} galaxies, {len(w_r)} randoms")

    # Box: cover data extent with margin
    lo = np.minimum(pos_d.min(axis=0), pos_r.min(axis=0))
    hi = np.maximum(pos_d.max(axis=0), pos_r.max(axis=0))
    boxsize = float(np.max(hi - lo) * 1.15)
    print(f"  Box size: {boxsize:.0f} Mpc/h (data extent {np.max(hi-lo):.0f})")

    # Choose nmesh for kmax=0.3: nmesh = 2*kmax*boxsize/pi
    nmesh = int(2 * 0.30 * boxsize / np.pi)
    nmesh = max(128, 2 ** int(np.ceil(np.log2(nmesh))))
    print(f"  nmesh = {nmesh} (Nyquist = {np.pi * nmesh / boxsize:.3f} h/Mpc)")

    # Shift to box center for correct phase handling (mesh from 0..box)
    pos_d = pos_d - lo
    pos_r = pos_r - lo

    k, P0, nmodes = fkp_power(pos_d, w_d, pos_r, w_r,
                              boxsize, nmesh, kmin=0.005, kmax=0.3, nkbins=50)

    # Save only bins with adequate mode counts
    good = nmodes > 50
    k, P0, nmodes = k[good], P0[good], nmodes[good]
    np.savetxt(OUT_PK, np.column_stack([k, P0]),
               header='k[h/Mpc] P0[(Mpc/h)^3] FKP monopole (FFT)', comments='#')

    print(f"\nSaved {OUT_PK}: {len(k)} bins")
    print(f"P0 range: [{P0.min():.1f}, {P0.max():.1f}]")
    print(f"Modes/bin: [{nmodes.min():.0f}, {nmodes.max():.0f}]")

    # Sanity: low-k amplitude
    P_low = np.interp(0.01, k, P0) if k.min() < 0.01 else P0[0]
    print(f"P0(k=0.01) ≈ {P_low:.0f} (expect ~10^3-10^4 for LRG)")

    # Run φ-periodic search
    print("\n" + "=" * 62)
    print("Running φ-periodic search on measured P0(k)...")
    print("=" * 62)
    from phi_periodic_pk_search import run_search
    best_T, best_power, periods, powers = run_search(k, P0)
    print(f"\n  Best log-period: {best_T:.4f}")
    print(f"  Cassi prediction: ln φ = {np.log(PHI):.4f} (Δ = {best_T - np.log(PHI):+.4f})")
    if abs(best_T - np.log(PHI)) < 0.03:
        print("  ✓ Consistent with ln-φ prediction — investigate further!")
    else:
        print("  No ln-φ signal at the predicted period.")
    print(f"\nTotal elapsed: {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
