#!/usr/bin/env python3
"""phi-periodic P(k) detection pipeline—targeted matched-filter test.

Falsifiable prediction: Delta(ln k) = ln(phi) = 0.4812 in matter P(k).
The log-period is fixed; amplitude, phase, detrending, window, and statistical choices are declared analysis inputs.
"""

import numpy as np
import os, json
from datetime import datetime

PHI = (1 + np.sqrt(5)) / 2
LN_PHI = np.log(PHI)


def pk_eh(k, h=0.6736, Om=0.3153, Ob=0.0493, ns=0.9649):
    """Eisenstein & Hu (1998) transfer function with BAO wiggles."""
    th = 2.7255 / 2.7
    Omh2 = Om * h**2
    Obh2 = Ob * h**2
    s = 44.5 * np.log(9.83 / Omh2) / np.sqrt(1 + 10 * Obh2**0.75)
    a = 1 - 0.328 * np.log(431 * Omh2) * Obh2 / Omh2 \
        + 0.38 * np.log(22.3 * Omh2) * (Obh2 / Omh2)**2
    G = Omh2 * h * a
    q = k / (G + 1e-30)
    L0 = np.log(2 * np.e + 1.8 * q)
    C0 = 14.2 + 731.0 / (1 + 62.5 * q)
    T0 = L0 / (L0 + C0 * q**2 + 1e-30)
    ks = k * s + 1e-30
    j0 = np.sin(ks) / ks
    bn = 8.41 * Omh2**0.435
    ksl = 1.6 * Obh2**0.52 * Omh2**0.73 * (1 + (10.4 * Omh2)**(-0.95))
    Tb = (np.exp(-(k / (ksl + 1e-30))**1.4)
          / (1 + (bn / (ks + 1e-30))**3)
          * j0 / (1 + (ks / 5.4)**4 + 1e-30))
    T = Obh2 / Omh2 * Tb + (1 - Obh2 / Omh2) * T0
    return (k / 0.05)**(ns - 1) * T**2


def main():
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    rdir = f"runs/{rid}_pk_phi"
    os.makedirs(rdir, exist_ok=True)

    k = np.logspace(-2.3, -0.3, 120)
    lnk = np.log(k)
    amp = 0.025
    deg = 7
    kbao = 0.0426

    # 1. Compute P(k)
    pk_lcdm = pk_eh(k)
    pk_cassi = pk_lcdm * (1 + amp * np.sin(2 * np.pi * lnk / LN_PHI))

    # 2. Smooth template
    c = np.polyfit(lnk, np.log(pk_lcdm), deg)
    smooth = np.exp(np.polyval(c, lnk))

    # 3. BAO subtraction
    resid_lcdm = pk_lcdm / smooth - 1
    bao_m = np.sin(2 * np.pi * k / kbao) * np.exp(-k / 0.3)
    Ab = np.sum(resid_lcdm * bao_m) / (np.sum(bao_m**2) + 1e-30)

    resid_raw = pk_cassi / smooth - 1
    resid = resid_raw - Ab * bao_m
    resid_null = resid_lcdm - Ab * bao_m

    # 4. Targeted matched filter at LN_PHI
    sig_m = np.sin(2 * np.pi * lnk / LN_PHI)
    As = np.sum(resid * sig_m) / (np.sum(sig_m**2) + 1e-30)
    An = np.sum(resid_null * sig_m) / (np.sum(sig_m**2) + 1e-30)
    sP = As**2

    # 5. Null distribution: power at random periods
    np.random.seed(42)
    null_ps = []
    for _ in range(300):
        T = LN_PHI + np.random.uniform(-0.3, 0.3)
        if 0.15 < T < 1.2:
            m = np.sin(2 * np.pi * lnk / T)
            a = np.sum(resid_null * m) / (np.sum(m**2) + 1e-30)
            null_ps.append(a**2)
    null_ps = np.array(null_ps)
    nm = np.mean(null_ps)
    ns = np.std(null_ps)
    sigma = (sP - nm) / max(ns, 1e-30)

    # 6. DESI sensitivity with fixed smooth template
    print("=" * 60)
    print("  PHI-PERIODIC P(k)—TARGETED MATCHED FILTER")
    print("=" * 60)
    print(f"  ln(phi) = {LN_PHI:.4f}")
    print(f"  Cassi modulation: {amp*100:.1f}%")
    print(f"  BAO amplitude: {Ab:.4f}")
    print(f"  Noiseless detection:")
    print(f"    Signal amplitude:  {As:.2e}")
    print(f"    Null amplitude:    {An:.2e}")
    print(f"    Signal power:      {sP:.2e}")
    print(f"    Null mean:         {nm:.2e} +/- {ns:.2e}")
    print(f"    Significance:      {sigma:.1f} sigma")
    print()

    # Use FIXED smooth template (not re-fit to noisy data)
    # to avoid absorbing the Cassi signal into the smooth component.
    print("  DESI SENSITIVITY (1% noise, 120 bins, 200 trials):")
    for atest in [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05]:
        det = 0
        nt = 200
        for _ in range(nt):
            mod = 1 + atest * np.sin(2 * np.pi * lnk / LN_PHI)
            pn = pk_lcdm * mod * (1 + 0.01 * np.random.randn(len(k)))
            # Fixed smooth (pre-computed from noiseless LCDM)
            r2 = pn / smooth - 1
            # Re-fit BAO amplitude (but keep fixed smooth)
            Ab2 = np.sum(r2 * bao_m) / (np.sum(bao_m**2) + 1e-30)
            rc = r2 - Ab2 * bao_m
            # Signal power
            As2 = np.sum(rc * sig_m) / (np.sum(sig_m**2) + 1e-30)
            sP2 = As2**2
            # Null power from 20 nearby periods
            np2 = np.mean([
                (np.sum(rc * np.sin(2*np.pi*lnk/(LN_PHI+0.05*j*(-1)**j)))
                 / (np.sum(np.sin(2*np.pi*lnk/(LN_PHI+0.05*j*(-1)**j))**2) + 1e-30))**2
                for j in range(1, 21)
            ])
            if np2 > 0 and sP2 > 9 * np2:
                det += 1
        dr = det / nt * 100
        if dr >= 95:
            fl = "CONFIRMED"
        elif dr >= 68:
            fl = "detectable"
        elif dr >= 30:
            fl = "hinted"
        else:
            fl = "not detectable"
        print(f"    {atest*100:4.1f}%: {dr:5.0f}% detection rate  ({fl})")

    print()
    print(f"  Figure: {rdir}/pk_phi_periodic.png")

    # Save results
    with open(f"{rdir}/results.json", "w") as f:
        json.dump({
            "ln_phi": LN_PHI,
            "cassi_amplitude": amp,
            "noiseless_sigma": float(sigma),
        }, f, indent=2)

    # Plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 3, figsize=(16, 5))

    ax[0].loglog(k, pk_lcdm * k**1.5, "k-", alpha=0.4, label="LCDM")
    ax[0].loglog(k, pk_cassi * k**1.5, "r-", alpha=0.6,
                 label=f"Cassi ({amp*100:.0f}% mod)")
    ax[0].set(xlabel="k [h/Mpc]", ylabel="k^1.5 P(k)")
    ax[0].set_title("Power Spectrum with BAO Wiggles")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    ax[1].semilogx(k, resid_null * 100, "k-", alpha=0.4, label="LCDM (null)")
    ax[1].semilogx(k, resid * 100, "r-", alpha=0.7,
                   label=f"Cassi ({amp*100:.0f}% mod)")
    ax[1].axhline(0, color="k", lw=0.5)
    for i in range(-4, 8):
        km = np.exp(lnk[0] + i * LN_PHI)
        if k[0] < km < k[-1]:
            ax[1].axvline(km, color="C0", ls=":", alpha=0.2)
    ax[1].set(xlabel="k [h/Mpc]", ylabel="Residual [%]")
    ax[1].set_title("BAO-Subtracted Residual + Cassi Modulation")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    ax[2].hist(null_ps, bins=25, alpha=0.5, color="gray", label="Null powers")
    ax[2].axvline(sP, color="r", lw=2,
                  label=f"Signal: {sigma:.0f}$\\sigma$")
    ax[2].axvline(nm, color="k", ls="--", lw=1)
    ax[2].set(xlabel="Matched-filter power")
    ax[2].set_title(f"Detection at ln($\\varphi$) = {LN_PHI:.4f}")
    ax[2].legend(fontsize=8)
    ax[2].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{rdir}/pk_phi_periodic.png", dpi=120)
    plt.close()
    print("  Done.")


if __name__ == "__main__":
    main()
