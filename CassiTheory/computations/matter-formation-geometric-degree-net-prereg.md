# Net-Degree Qualification of the Chiral-Lattice Formation Run

## Status: Preregistered—September 2026

## 1. Question

Does the retained degree-zero impulse form and preserve a spatially resolved degree-$+1$/degree-$-1$ pair in the supplied massive chiral action when the degree calculation is qualified by controls that test topological degree rather than injectivity of a finite simplicial map?

The trajectory fields, regular values, triangulation, tolerances, formation thresholds and stopping time are fixed inputs. This calculation only applies the defining signed-preimage sum to the analytic degree-one control and reconstructs the retained raw fields. It does not modify or continue the trajectories.

<!-- geometric-net-degree-protocol:start -->
## 2. Fixed inputs

Use the retained raw snapshots and source receipts for:

- `impulse_N48`: $N=48$, $L=18$, $\Delta t=0.002$, $T=4$;
- `impulse_N48_halfdt`: $N=48$, $L=18$, $\Delta t=0.001$, $T=4$;
- `impulse_N64`: $N=64$, $L=18$, $\Delta t=0.002$, $T=4$.

Use the six-tetrahedron Freudenthal decomposition of every primitive cube, the bubble-lattice primitive basis with $p_\parallel=2$, coefficient tolerance $\tau_c=10^{-10}$, determinant tolerance $\tau_D=10^{-13}$ and the 16 fixed regular values

$$
y_m=\frac{1}{\lVert q_m\rVert}
\left(
\sin(m\sqrt2+0.11),
\sin(m\sqrt3+0.23),
\sin(m\sqrt5+0.37),
\sin(m\sqrt7+0.53)
\right),
\quad m=1,\ldots,16.
$$

For each target, solve for its coefficients in each image tetrahedron. Count a preimage only when every coefficient exceeds $\tau_c$. Mark the snapshot ambiguous if a near-simplex coefficient lies within $10\tau_c$ of a face or a contributing determinant has magnitude below $10\tau_D$. The signed preimage sum is the target degree.

## 3. Controls

Every control must be admissible under maximum nearest-neighbour target-space edge angle $<\pi/2$ and must have no ambiguity.

1. **Constant vacuum:** the exact map $n=(1,0,0,0)$ on $N=16$ has degree zero and no preimage for every target.
2. **Analytic degree-one hedgehog:** the massive radial profile on $N=32,48,64$ has the same nonzero net degree of magnitude one for all 16 targets. Extra opposite-sign preimage pairs are allowed because they do not change the degree of a regular map. The common sign fixes the receipt labels.
3. **Analytic separated pair:** the product of a scale-$1.5$ hedgehog centred at $(-3,0,0)$ and the inverse hedgehog centred at $(+3,0,0)$ on $N=48$, $L=18$ has one hit of each sign for at least 15 targets, net degree zero for all targets and median opposite-sign separation in $[4,8]$.
4. **Orientation reversal:** reversing only the domain orientation preserves every hit location and multiplicity and reverses every hit sign.
5. **Reproducibility:** two evaluations of all controls are byte-identical after canonical JSON serialization.

The hedgehog control tests degree through the signed sum $d_m=h_m^+-h_m^-$. It does not impose one-to-one coverage by a piecewise-geodesic finite-grid map.

## 4. Trajectory pair observable

For every retained snapshot, record every preimage and define

$$
C_\pm=\frac1{16}\sum_m\mathbf1[h_m^+\ge1\land h_m^-\ge1],
\qquad
C_0=\frac1{16}\sum_m\mathbf1[d_m=0].
$$

A snapshot contains a resolved pair exactly when it is admissible, unambiguous, has $C_\pm=C_0=1$, has exactly one hit of each sign for every target, has median opposite-sign separation $S\ge4$, and has maximum within-sign hit-cluster RMS radius $R_{\rm hit}\le2$.

Formation requires the first passing retained sample to satisfy $t_*\le2$. Persistence requires every retained sample from $t_*$ through $T=4$ to pass. Degree conservation requires $d_m=0$ for every target at every admissible trajectory snapshot.

## 5. Numerical comparisons

The $N=48$ primary and half-step trajectories must have identical pair pass/fail state at every common sample through $T=4$. When both snapshots pass, their separations and both sign-cluster centres must agree within $0.25$ in physical distance.

The $N=48$ and $N=64$ trajectories must have identical pair pass/fail state at every common sample through $T=4$. When both snapshots pass, their separations and both sign-cluster centres must agree within $0.50$ in physical distance. The common physical periodic cell is used for minimum-image matching.

## 6. Decision tree

1. A missing or hash-mismatched source, malformed or nonfinite datum, failed control, ambiguity, inadmissible trajectory snapshot, failed time-step comparison, failed spatial comparison, failed degree conservation or failed independent reconstruction returns `INCONCLUSIVE`.
2. If qualification passes and the $N=64$ trajectory has no $t_*\le2$, return `DOES NOT EMERGE`.
3. If formation occurs but persistence fails before $T=4$, return `DOES NOT EMERGE`.
4. If every qualification, formation and persistence condition passes, return `EMERGES CONDITIONAL`.

`DOES NOT EMERGE` is restricted to this action, retained degree-zero impulse and sampled window. `EMERGES CONDITIONAL` would establish only classical pair formation and persistence in the supplied effective model.

## 7. Programs and stopping rule

The primary program may reuse the source-bound geometric primitives in `computations/matter_formation_geometric_degree.py`. The verifier must use the separately implemented primitives in `computations/verify_matter_formation_geometric_degree.py` and may not import the primary implementation. Both programs bind their complete dependency and input hashes.

Run one primary reconstruction and one independent verification in fresh directories under `runs/20260907_matter_formation_geometric_degree_net/`. Stop after the verdict. Do not tune targets, tolerances, pair criteria or the supplied trajectory.
<!-- geometric-net-degree-protocol:end -->

## References

- `computations/matter-formation-continuum-report.md` §32—supplied massive chiral action, lattice Hamiltonian and retained trajectory identities.
- `computations/matter_formation_chiral_lattice.py`—source of the immutable trajectory fields.
- `computations/matter-formation-geometric-degree-prereg.md`—geometric regular-value construction and source trajectory boundary.
