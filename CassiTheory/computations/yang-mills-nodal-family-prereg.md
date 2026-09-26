# Schedule-Wide Nodal Family Probe

## Status: Pre-registered—September 2026

## Abstract

The seven-link study of
`computations/yang-mills-exact-block-spectral-prereg.md` proves, at one row
(doubled cutoff $J=1$, coupling $x=1$), that the projected Ritz density
changes sign on the block, which makes the unrestricted conditional gap of
that cutoff measure exactly zero while the retained test space reports
$0.864465200076$. This probe asks whether that obstruction is a small-cutoff
artifact or a property of every scheduled row. It evaluates the normalized
Ritz wavefunction along two continuous paths in the block at twelve
scheduled rows and counts resolved sign changes. Paths, grid, resolution
threshold, decision tree and stopping rule are fixed here before
implementation. A resolved sign change along a continuous path in the block
manifold proves that the corresponding cutoff density has a nodal set, and
the vanishing Dirichlet-energy argument of §9.23 then applies to that row.

## 1. Question and scope

For the seven-link graph of the block study, does the normalized Ritz
wavefunction $\Omega_J(U_B;\eta)$ change sign along a continuous closed path
in the block at every scheduled $(J,x)$, or only at the smallest cutoff?

The probe measures sign changes only. It does not compute the exact
conditional gap of any row, does not modify the retained-rate numbers of the
sealed receipt, and supplies no cutoff-uniform or continuum statement.

## 2. Graph, state and paths

Use the seven-link graph, block links $\{0,1,2,3\}$, exterior links
$\{4,5,6\}$, truncation, Hamiltonian and Ritz convention of the block study,
with the shared algebra module
`computations/yang_mills_conditional_algebra.py`. Fix the exterior data at
the identity and vary one block link along the conjugacy loop

\[
U_e(\varphi)=\exp\!\Big(i\frac{\varphi}{2}\sigma_3\Big),
\qquad
\varphi=\frac{2\pi k}{48},\ k=0,\ldots,48,
\]

with the other block links fixed at the identity. Path A varies link $0$,
path B varies link $1$. The wavefunction is evaluated by the same
representation contraction that produces the analytic nodal control of the
sealed receipt.

## 3. Schedule

\[
J\in\{1,2,3\},
\qquad
x\in\left\{\tfrac14,1,4,16\right\},
\]

twelve rows, one Ritz vector per row, two paths per row.

## 4. Observables

For every row and path: the amplitude table $\Omega(\varphi_k)$, its sign
sequence, the number of resolved sign changes around the closed loop, the
smallest resolved modulus $|\Omega|$ and the interval in which each sign
change occurs.

Resolution rule: a value with $|\Omega|\le10^{-10}$ is unresolved and is
reported as a crossing candidate; a row whose endpoint values are unresolved
carries no verdict.

## 5. Decision tree and thresholds

| Rule | Verdict |
|---|---|
| Every scheduled row shows an odd number of resolved sign changes on at least one path, with $\Omega$ resolved at both ends of each change interval | `NODAL_PERSISTS_ACROSS_SCHEDULE` |
| At least one scheduled row shows zero resolved sign changes | `NODAL_CONFINED` |
| Endpoint or interior values unresolved, or the cross-check against the sealed nodal control fails | `INCONCLUSIVE` |

Cross-check: at $J=1$, $x=1$ the path endpoints must reproduce the sealed
control values $2.094120531213694$ at the identity and
$-0.03437408376157869$ at the antipodal configuration to $10^{-9}$ absolute.

## 6. Consequence attached to the verdict

A resolved sign change on a continuous path inside the block implies a
nonempty nodal set of the cutoff density $\rho\propto|\Omega|^2$, since
$\Omega$ is a polynomial in the link matrix elements and therefore
continuous. Smooth approximants to $\operatorname{sign}(\Omega)$ then have
Dirichlet energy tending to zero while their variance stays positive, as in
§9.23, so the unrestricted conditional Poincaré gap of that cutoff measure
vanishes. The verdict is a statement about the projected Ritz density, not
about the exact regulated vacuum measure, which is strictly positive by
§9.13.

## 7. Stopping rule and evidence boundary

One execution of the twelve-row schedule, single run, no re-run after
inspection. The receipt binds this protocol, the source
`computations/verify_yang_mills_nodal_family.py` and the shared algebra
module bind SHA-256, and must refuse to overwrite an existing receipt.

## 8. Obligations unchanged

Exact-vacuum fibre rate, transport score, cutoff removal, uniform
interacting recovery, thermodynamic limit and continuum construction remain
open.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.23—nodal Ritz obstruction, orbit identity and obligations.
- `computations/yang-mills-exact-block-spectral-prereg.md`—graph, truncation, coupling schedule and qualification rules.
- `computations/verify_yang_mills_exact_block_spectrum.py`—sealed primary receipt and analytic nodal control.
- `computations/yang_mills_conditional_algebra.py`—shared representation, contraction and conditional-moment conventions.
