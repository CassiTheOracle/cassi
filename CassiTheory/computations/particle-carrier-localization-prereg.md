# Particle Carrier Localization Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign asks whether the registered static particle action develops a
localized, retained carrier when the density-depletion coupling is increased
while every other coefficient remains fixed. The current finite-grid stationary
state spreads the carrier across the box because its gradient and self-repulsion
costs exceed the attraction supplied by the depleted Yang/Yin density. The
campaign turns that measured imbalance into a frozen five-point coupling scan,
selects the first fully reoptimized localized state, and then tests the selected
state on a larger domain and a finer grid.

The calculation can establish a finite-grid existence branch and test whether
its measured size survives the two registered grid changes. It cannot select a
physical carrier, derive the coupling from $\varphi$, establish continuum
existence, determine quantum numbers, or replace the separate temporal-stability
calculation.

## 1. Physical question and measured scale

At fixed carrier charge, the exterior threshold contributes the constant
$e_Cq_C$ to the static energy. Changing $e_C$ therefore shifts the carrier
multiplier and the exterior threshold together without changing the stationary
fields or the retention margin. The density-depletion coupling $h_C$ changes the
shape equation and is the direct control used here.

For a real nonnegative carrier $c$, define

$$
I_{\rm dep}=\int (1-\rho)c^2\,d^3x,
\qquad
I_4=\int c^4\,d^3x.
$$

The fixed-charge carrier equation gives

$$
\widehat\omega_C-e_C
=\frac{E_{\nabla c}+u_C I_4-h_C I_{\rm dep}}{q_C}.
$$

The hash-bound source state has

$$
\begin{aligned}
q_C&=4,\\
E_{\nabla c}&=0.8613894451307225,\\
I_4&=0.3011064231841705,\\
I_{\rm dep}&=0.20989339175113506,\\
\widehat\omega_C-e_C&=0.21191394517204765.
\end{aligned}
$$

These numbers show that the source carrier's gradient and self-repulsion
contribute $1.162495868314893$ to the integrated retention balance, while the
registered coupling supplies only $0.3148400876267026$. Additional optimizer
iterations at the same coefficient point cannot reverse this sign once the
stationary residual is already below the registered precision target.

The localization predicate requires
$\widehat\omega_C<0.73$, which leaves a numerical buffer of $0.02$ below the
exterior threshold $e_C=0.75$. Holding the source fields fixed gives the
reference coupling

$$
h_{C,\rm ref}
=\frac{E_{\nabla c}+u_CI_4+q_C(0.75-0.73)}{I_{\rm dep}}
=5.919652152689433.
$$

This value sets the scan scale. It is a frozen-field diagnostic rather than a
prediction of the fully coupled threshold because the Yang/Yin density, core,
and carrier all reoptimize at every scan point.

## 2. Immutable source

The sole primary initial condition is
`runs/20260902_particle_stationary_precision_v5/fields_block01.npz`, with
SHA-256
`ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e`.
It is the selected block in the hash-bound result receipt
`runs/20260902_particle_stationary_precision_v5/results.json`, whose SHA-256 is
`9decc9a751d7c833f92754eb3e5187da9056bc5ddda0c9bd125e188f4e90cfa5`.
The corresponding independent verification receipt has SHA-256
`7667c9617c3e4bd237e77e84226c78805d224002a18a192f25cce24cd2ce4b32`
and records a clean higher-precision stationary result.

The source grid is $(R,N,\Delta x)=(4,17,0.5)$ with fixed vacuum values on its
outer shell. The source physical-gradient RMS is
$5.4712481264035785\times10^{-5}$, its cutoff virial is
$1.348199173228824\times10^{-4}$, and its charge is exactly $4$ within the
stored precision. Its carrier radius is $2.5682251401285114$, its outer-shell
fraction is $0.015485205450071305$, and its multiplier is
$0.9619139451720476$. The source therefore supplies a stationary control and
fails both localization and retention.

Every primary scan arm reconstructs a fresh canonical preimage of this same
artifact. No arm starts from another scan endpoint, and no random number
generator is used. This prevents a strong-coupling solution from seeding a
weaker point and fixes the path dependence of the discrete search.

## 3. Frozen coefficient vectors

All static coefficients other than $h_C$ remain fixed at

$$
\begin{aligned}
&\alpha_{\mathfrak s}=1,\quad u_\rho=4,\quad u_\varphi=4,
\quad \gamma_x=\gamma_{\mathfrak s}=1,\quad u_H=4,\\
&k_{Cx}=k_{C\mathfrak s}=1,\quad e_C=0.75,\quad u_C=1,
\quad q_C=4,\quad L_{\mathfrak s}=1,\quad \xi_{\rm gf}=1.
\end{aligned}
$$

The source control uses $h_C=1.5$. The five reoptimized values are frozen in
ascending order as follows:

| Order | Multiplier of $h_{C,\rm ref}$ | $h_C$ |
|---:|---:|---:|
| 1 | $0.50$ | $2.9598260763447164$ |
| 2 | $0.75$ | $4.439739114517074$ |
| 3 | $1.00$ | $5.919652152689433$ |
| 4 | $1.25$ | $7.399565190861791$ |
| 5 | $1.50$ | $8.879478229034149$ |

The scan order, candidate values, and stopping rule are immutable. No coupling
is inserted between these values after observing an outcome. A separate
exploratory campaign and a new preregistration would be required to refine a
bracket.

## 4. Frozen optimization and stopping rule

Each primary candidate starts from the source physical fields and runs at most
four fresh strong-Wolfe L-BFGS blocks. Every block uses `max_iter=880`,
`max_eval=1100`, `history_size=20`, `tolerance_grad=1e-10`, and
`tolerance_change=1e-12`. A block resets the L-BFGS history while preserving the
accepted physical endpoint from the preceding block.

A primary arm becomes numerically qualified at the first endpoint that has
finite fields and diagnostics, passes the registered charge, boundary,
stationarity, gauge, and outer-flux conditions, and reaches a physical-gradient
RMS no larger than $1.20\times10^{-4}$. Later blocks for that coupling do not
run. If no endpoint qualifies within four blocks, that candidate is recorded
as numerically unqualified and the scan proceeds to the next frozen value. The
scan stops only after all five candidates are evaluated or one candidate
satisfies the localization predicate.

A numerically qualified endpoint is localized and retained only when all four
of the following physical conditions hold:

1. the fraction of carrier norm in the outer two-cell shell is at most
   $10^{-3}$;
2. the carrier RMS radius is smaller than $R/2$;
3. the carrier multiplier is below $0.73$, leaving the declared exterior
   retention buffer;
4. the maximum Yang/Yin density depletion is at least $0.10$.

A qualified endpoint that misses any of these conditions is a measured negative
at that coupling, and the scan proceeds to the next frozen value. A numerically
unqualified endpoint carries no localization verdict and also proceeds to the
next value. The first qualified endpoint satisfying all four physical
conditions is selected, and no stronger primary coupling runs. If every frozen
value is a qualified negative, the campaign reports that no localized retained
primary appears within the declared coupling bracket. If no candidate is
selected and at least one value remains numerically unqualified, the scan is
inconclusive rather than negative.

Every block writes its physical fields, SHA-256, optimizer history, physical
energy decomposition, physical-gradient RMS, virial response, charge,
boundary residual, gauge diagnostics, flux diagnostics, carrier radius,
outer-carrier fraction, density depletion, and carrier multiplier. The saved
fields determine the scientific diagnostics; raw optimizer-gradient summaries
are auxiliary execution receipts.

## 5. Larger-domain and finer-grid test

When a primary endpoint is selected, the same coefficient vector is tested on
two independently initialized grids. The larger-domain grid is
$(R,N,\Delta x)=(5,21,0.5)$, and the finer grid is
$(R,N,\Delta x)=(4,21,0.4)$. Each begins from the deterministic
`separated_core` analytic seed in `computations/particle_stationary_bvp.py`,
runs the frozen 800-step Adam plus 120-iteration L-BFGS initialization, and then
runs at most six continuation blocks with the settings in Section 4.

Each comparison grid must independently reach the numerical and localization
conditions in Section 4. Its physical energy must agree with the selected
primary within $5\%$, its core length within $0.75$, its carrier multiplier
within $0.10$, and its carrier radius within $10\%$. The radius comparison uses
the absolute radii because every candidate entering this test already has an
outer-carrier fraction below $1\%$.

The larger-domain and finer-grid states are independent basin reconstructions.
Agreement therefore measures whether the localized scale is reproduced without
embedding or interpolating the selected primary field into either comparison
grid.

## 6. Independent verification

The independent verifier is
`computations/verify_particle_carrier_localization.py`. It does not import the
primary campaign driver. Its NumPy energy and PyTorch first-variation
implementations take $h_C$ as an explicit argument, while the full remaining
coefficient vector is checked against the manifest for every arm. This prevents
a variable-coupling artifact from being certified with the source value
$h_C=1.5$.

Before optimization, the verifier checks every manifest hash, the complete
source receipt chain, the source artifact schema and shell values, the
independently recomputed source diagnostics, the retention-balance arithmetic,
the five frozen coupling values, the full coefficient vector, and the freshness
of the output path. The primary driver refuses to run unless this preflight
receipt is clean and names the same manifest hash.

After execution, the verifier loads every NPZ with `allow_pickle=False`, checks
its schema and byte-stream hash, and independently recomputes the physical
energy components, fixed-charge physical first variation, virial diagnostics,
boundary values, gauge measures, magnetic flux, carrier geometry, depletion,
and multiplier at that arm's declared $h_C$. It reconstructs the scan stopping
point, selected coupling, grid comparisons, and scientific verdict from the
saved fields. Unregistered output files, nonfinite optimizer histories, a
changed coefficient vector, a later-than-allowed selected candidate, or any
primary/verifier mismatch makes the result inconclusive.

Primary and independent scalar values must satisfy

$$
|x_{\rm primary}-x_{\rm independent}|
\le 10^{-8}+10^{-6}|x_{\rm independent}|.
$$

Exact booleans, strings, dimensions, coefficient values, candidate order, and
hashes must match exactly. The tolerance compares two implementations of the
same finite-grid functional; it does not relax a physical threshold.

## 7. Verdict tree

A clean localized primary with matching larger-domain and finer-grid states
receives `EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH`.
This is the strongest available outcome because the same localized scale is
then reproduced on both registered grid changes.

A clean localized primary whose comparison grids complete but miss localization
or the matching tolerances receives
`EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY`. The result establishes a
discrete existence point while leaving spatial qualification unresolved.

Five numerically qualified primary negatives receive
`DOES NOT EMERGE—NO LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET`. This outcome
rules out only the declared source basin, coefficient line, coupling bracket,
field class, and finite grid.

A manifest, source, execution, qualification, artifact, or independent-check
failure receives `INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION`. No
scientific sign is assigned to unqualified fields.

## 8. Scientific boundary and next decision

A domain-and-resolution-matched result permits a new preregistered physical
quotient and low-spectrum calculation at the selected coefficient vector. The
global phase mode must become spatially resolved and the nonnegative low
spectrum must reproduce on the comparison grids before the branch can advance
toward temporal dynamics.

A finite-grid-only result requires a frozen domain and resolution recovery
campaign around the selected coupling. A negative bracket result requires a
new physical mechanism or a separately justified scan axis; post-result tuning
of $h_C$ is excluded. Every outcome leaves physical carrier identity, units,
continuum existence, non-$C_4$ deformations, topology-changing competitors,
the mixed temporal spectrum, decay channels, lifetime, spin, and statistics
open.

## References

- `computations/particle_stationary_bvp.py`—static functional, field map,
  deterministic basin seeds, and physical diagnostics.
- `computations/particle_stationary_q2_recovery_v2.py`—canonical field
  reconstruction and deterministic continuation engine.
- `computations/verify_particle_stationary_q2_recovery_v2.py`—independent
  finite-grid geometry, gauge, flux, and diagnostic routines used only through
  the explicitly parameterized verifier.
- `computations/particle-stationary-precision-v5-report.md`—source stationary
  background and precision boundary.
- `computations/particle-physical-hessian-precision-v2-report.md`—one-point
  finite-grid energetic spectrum at the source coefficient vector.
- `foundations/core-trapped-charge-support.md`—carrier binding and retention
  conditions.
- `foundations/particle-stationary-action-closure.md`—dimensionless static
  particle action and fluctuation boundary.
- `foundations/matter-completion-boundary.md`—remaining requirements for a
  physical matter claim.
