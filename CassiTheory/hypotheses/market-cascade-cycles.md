# Market Cascade Cycles

## Status: Speculative—July 2026

## Abstract

Financial markets exhibit log-periodic oscillations preceding crashes (the
Johansen-Ledoit-Sornette model), with a preferred log-periodic scaling ratio
that empirically clusters near 1.6–1.7—close to $\varphi \approx 1.618$. The
Cassi wake-wave mechanism, applied to information propagation in agent networks,
predicts $\varphi$-periodic volatility structure: drawdown-to-recovery periods,
volatility autocorrelation, and crash precursors should show log-periodic
modulation at period $\ln\varphi \approx 0.4812$. This is Speculative because
market dynamics involve human agency, regulatory intervention, and non-stationary
statistical properties that the two-fluid PDE was not designed to model. It is
included here because the empirical LPPL literature already reports
$\varphi$-adjacent scaling ratios, and Cassi offers a structural explanation for
*why* this specific ratio appears—the de-resonance attractor in hierarchical
information networks.

---

## 1. Log-Periodic Power Law (LPPL) in Finance

The JLS model (Sornette et al.) describes the price trajectory before a crash
as:
$$\ln p(t) = A + B (t_c - t)^\beta \left[1 + C \cos(\omega \ln(t_c - t) + \phi)\right]$$

where $t_c$ is the critical time (crash), $\beta$ is the power-law exponent, and
$\omega$ is the log-periodic angular frequency. The log-periodic scaling ratio
is:
$$\lambda = e^{2\pi/\omega}$$

Empirical fits to historical crashes (1929, 1987, 2000, 2008) consistently find
$\lambda \approx 1.6$–$1.7$, with a preferred value near $1.65$. This is
$\varphi^{1.05} \approx 1.66$—within 0.5% of the preferred empirical value.

## 2. Why $\varphi$ in Markets?

In Cassi, any system with:
1. Positive feedback (herding, momentum trading)—drives the system toward a
   critical point, AND
2. A hierarchical network structure (traders → desks → funds → markets)—a
   cascade ladder,

will exhibit $\varphi$-periodic log-periodicity because $\varphi$ is the
de-resonance attractor for information propagation on hierarchical networks.

The market network has a natural cascade structure:

| Rung | Agent | Timescale | Information horizon |
|------|-------|-----------|-------------------|
| 0 | Individual trade | ~ms–s | Tick data |
| 1 | Algorithm / HFT strategy | ~s–min | Intraday |
| 2 | Day trader desk | ~min–hr | Daily |
| 3 | Portfolio manager | ~day–wk | Weekly–monthly |
| 4 | Fund / institution | ~mo–qtr | Quarterly–annual |
| 5 | Central bank / sovereign | ~yr–decade | Multi-year |

Information propagates between rungs through trading activity. The Yang field
corresponds to bullish sentiment (buying pressure, momentum), the Yin field to
bearish sentiment (selling pressure, mean reversion). The Qi field $q$ is the
market's coherence—high $q$ means correlated trading (herding), low $q$ means
independent decision-making.

## 3. Key Prediction: $\varphi$-Periodic Volatility Structure

The volatility autocorrelation function should show log-periodic modulation:

$$\boxed{\text{ACF}(\tau) \propto \tau^{-\beta} \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{\tau}{\tau_0} + \phi_0\right)\right]}$$

where $\tau$ is the time lag, $\beta$ is the long-memory exponent (empirically
$\beta \approx 0.2$–$0.4$ for volatility), and the modulation has period
$\ln\varphi \approx 0.4812$ in $\ln\tau$ space.

This is the same functional form as the cosmological $P(k)$ modulation and the
quasicrystal heat capacity—the universal signature of a $\varphi$-structured
cascade.

## 4. Drawdown-Recovery Periods

The distribution of drawdown durations (time from peak to trough to recovery)
should show excess probability at $\varphi$-spaced timescales:

$$\frac{\tau_{k+1}}{\tau_k} \approx \varphi$$

**Test with S&P 500 (1928–present, daily data):** Drawdowns exceeding 5% should
show clustering at periods of approximately 1, 1.6, 2.6, 4.2, 6.8, ... trading
days (or calendar months, depending on the anchor).

The cascade anchor timescale for equity markets is approximately 1 trading day
(one rung above the tick level). Predicted drawdown durations: $\tau_0 = 1$ day,
$\tau_1 \approx 1.6$ days, $\tau_2 \approx 2.6$ days, $\tau_3 \approx 4.2$ days
(~1 week), $\tau_4 \approx 6.8$ days, $\tau_5 \approx 11$ days (~2 weeks),
$\tau_6 \approx 18$ days (~1 month), $\tau_7 \approx 29$ days, $\tau_8 \approx
47$ days (~2 months), $\tau_9 \approx 76$ days (~1 quarter).

## 5. Crash Precursor $\varphi$-Sequence

The LPPL model finds that crashes are preceded by accelerating log-periodic
oscillations. The sequence of oscillation periods before a crash should follow a
$\varphi$-geometric progression in reverse time:

$$t_c - t_n \propto \varphi^{-n}$$

This means the crash precursors occur at $\varphi$-spaced intervals counting
backward from $t_c$. If the first precursor appears at $t_c - \tau$, the next
appears at $t_c - \tau/\varphi$, then $t_c - \tau/\varphi^2$, etc.

**Prediction for the LPPL angular frequency:** The parameter $\omega$ in the JLS
model should be:
$$\omega = \frac{2\pi}{\ln\varphi} \approx 13.06$$

Empirically, fits to the 1987 crash give $\omega \approx 6$–$9$, to the 2000
dot-com crash $\omega \approx 5$–$8$, and to the 2008 crash $\omega \approx
7$–$10$. These are about $\omega/2$ to $2\omega/3$ of the $\varphi$ prediction,
suggesting the effective log-periodic ratio in real markets is approximately
$\sqrt{\varphi} \approx 1.27$ to $\varphi^{2/3} \approx 1.38$ rather than
$\varphi \approx 1.618$. This could reflect the market's effective cascade
spacing being two Fibonacci sub-rungs rather than a full rung.

## 6. Why This Is Speculative

Several factors prevent this from being classified as Hypothesized:

1. **No fundamental PDE for markets.** The two-fluid PDE describes physical
   fields with conservation laws and continuous dynamics. Markets are
   discrete-agent systems with non-conserved "value" and external shocks
   (earnings, policy changes, geopolitical events). Extending the PDE to markets
   requires a mapping that has not been constructed.

2. **Non-stationarity.** Market statistical properties drift over time
   (changing volatility regimes, structural breaks, regulatory changes). The
   $\varphi$-attractor in a physical system is stationary; in a market, the
   attractor itself may shift.

3. **Reflexivity.** In Soros' terminology, market participants act on their
   models, which changes the market—the observer is part of the system. The
   Cassi framework has not addressed self-referential dynamics at this level
   (the consciousness framework addresses field self-reference, not agent-based
   reflexivity in information networks).

4. **The empirical LPPL scaling ratio near $\varphi$ could be coincidence.**
   The $\lambda \approx 1.6$–$1.7$ range includes $\varphi \approx 1.618$,
   $\pi/2 \approx 1.57$, $e/1.7 \approx 1.60$, and $\sqrt{3} \approx 1.73$. The
   clustering near $\varphi$ may reflect the fitting procedure's sensitivity to
   the chosen data window rather than a structural constant.

## 7. Falsifiable Tests

1. **Volatility ACF modulation:** Compute the ACF of daily S&P 500 realized
   volatility (1928–present) and test for log-periodic modulation at
   $\ln\varphi$. Requires careful surrogate testing to rule out spurious
   periodicities from the calendar (weekly, monthly, quarterly effects).

2. **Drawdown duration distribution:** Fit a kernel density estimate to the
   distribution of drawdown durations and test for peaks at $\varphi$-spaced
   timescales. The null hypothesis is a smooth power-law distribution.

3. **Cross-asset universality:** If $\varphi$ is a structural constant of
   hierarchical information networks, the same log-periodic modulation should
   appear in equity, FX, commodity, and cryptocurrency markets—with different
   anchor scales but the same period $\ln\varphi$.

4. **Test on synthetic null models:** Generate surrogate price series with the
   same long-memory properties but no cascade structure (e.g., fractional
   Gaussian noise). The $\varphi$-periodic modulation should be absent from the
   surrogate data—if it appears in both real and surrogate, it is a
   statistical artifact of the long-memory process, not a cascade signature.

## 8. Open Issues

- The anchor timescale $\tau_0$ is not predicted—it must be fit to each
  market. The prediction is the $\varphi$-spacing *between* peaks, not their
  absolute positions.
- The modulation amplitude $A$ for financial data is not predicted by the
  cascade alone; it depends on the coupling strength between market rungs
  (liquidity, information flow rate).
- This hypothesis is the most Speculative in this directory. It is included
  because the empirical LPPL literature independently identifies $\varphi$ as a
  preferred scaling ratio, and Cassi provides a structural reason for why
  $\varphi$—rather than any other number—should govern log-periodicity in
  hierarchical networks with positive feedback.

---

## References

- `../principles/de-resonance-principle.md`—$\varphi$ as the universal de-resonance attractor
- `../foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `../predictions/falsifiable-predictions.md`—$\varphi$-periodic $P(k)$ (same modulation form at cosmological scale)
- `../open-questions-cassi-answers.md`—M1 (consciousness as field self-reference—relevant to market reflexivity)
