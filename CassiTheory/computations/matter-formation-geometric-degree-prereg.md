# Geometric Degree Qualification of the Chiral-Lattice Formation Run

## Status: Preregistered—September 2026

## Abstract

The frozen classical chiral-lattice formation schedule has an `INCONCLUSIVE` first-schedule verdict because its smooth central-difference winding integral changes by more than the prescribed tolerance between the two finest grids. This calculation asks a narrower geometric question before any further evolution is authorized: do the retained lattice maps contain a resolved degree-$+1$/degree-$-1$ pair when degree is counted by regular-value preimages of a piecewise-geodesic map into $S^3$? The statistic, triangulation, controls, tolerances and decision tree below are fixed before this geometric diagnostic is implemented or evaluated.

<!-- geometric-degree-protocol:start -->

## 1. Question and scope

The supplied comparison model evolves a unit four-vector

$$
\mathbf n:T^3\longrightarrow S^3.
$$

Its reported winding density uses central finite differences. A localized map can therefore have a poorly converged integral even when the lattice vertices define a stable topological covering. The present calculation independently reconstructs the degree from generic regular-value preimages. It does not alter the frozen first-schedule verdict, select the chiral action, establish fermionic statistics, or identify the excitation with a physical particle.

The immutable primary inputs are every retained `state_*.npz` snapshot in:

- `runs/20260907_matter_formation_chiral_lattice/execution_recovery1/impulse_N48/`;
- `runs/20260907_matter_formation_chiral_lattice/execution_cpu1/impulse_N64/`;
- `runs/20260907_matter_formation_chiral_lattice/execution_cpu1/impulse_N48_halfdt/`.

The first two trajectories use $\Delta t=0.002$ at $N=48,64$; the third uses $\Delta t=0.001$ at $N=48$. All use $L=18$, $T=4$, $\mu=0.5266577616452649$, $\kappa=1$ and the same finite-energy impulse.

## 2. Piecewise-geodesic degree

Each periodic primitive cube is divided into the following six tetrahedra around its $(0,0,0)$ to $(1,1,1)$ body diagonal:

$$
\begin{aligned}
&(000,100,110,111),&&(000,110,010,111),\\
&(000,010,011,111),&&(000,011,001,111),\\
&(000,001,101,111),&&(000,101,100,111).
\end{aligned}
$$

For one oriented domain tetrahedron with primitive-coordinate vertices $x_a$ and field vertices $v_a\in S^3$, define

$$
D_x=\det[x_1-x_0,x_2-x_0,x_3-x_0],\qquad
D_v=\det[v_0,v_1,v_2,v_3].
$$

For a regular value $y\in S^3$, solve $Vc=y$, where $V=(v_0,v_1,v_2,v_3)$. The normalized affine interpolation covers $y$ in the interior precisely when all four coefficients satisfy $c_a>\tau_c$. Such a preimage contributes

$$
s=\operatorname{sign}(D_vD_x)
$$

to the degree. Tetrahedra with $|D_v|\le\tau_D$ are treated as degenerate and cannot contribute. The fixed numerical tolerances are

$$
\tau_c=10^{-10},\qquad \tau_D=10^{-13}.
$$

A snapshot is admissible only if its maximum nearest-neighbour target-space edge angle is below $\pi/2$. This keeps every retained tetrahedron inside a common hemisphere and makes normalized affine interpolation equivalent to its short geodesic simplex for the degree count.

## 3. Frozen regular values

Use $K=16$ deterministic targets. For $m=1,\ldots,16$, set

$$
q_m=\left(
\sin(m\sqrt2+0.11),
\sin(m\sqrt3+0.23),
\sin(m\sqrt5+0.37),
\sin(m\sqrt7+0.53)
\right),\qquad
y_m=\frac{q_m}{\lVert q_m\rVert}.
$$

No target may be replaced after inspecting a field. The primary receipt records every $y_m$, every tetrahedral hit, its sign, primitive coordinate and physical coordinate. A target with a coefficient within $10\tau_c$ of a simplex face, or with a contributing $|D_v|<10\tau_D$, makes that snapshot numerically ambiguous and fails qualification rather than triggering a target change.

## 4. Controls

The implementation must pass all of the following before any trajectory is interpreted.

1. **Constant vacuum:** the exact map $n=(1,0,0,0)$ on $N=16$ has zero preimages for all 16 targets.
2. **Analytic degree-one hedgehog:** the same radial profile and primitive geometry as the formation solver, initialized at $N=32,48,64$, has exactly one preimage of the same sign for every target. Its sign fixes the receipt labels `particle` and `antiparticle`; no expected sign is imposed in source code.
3. **Analytic separated pair:** the product of a scale-$1.5$ hedgehog centred at physical Cartesian coordinate $(-3,0,0)$ and the inverse hedgehog centred at $(+3,0,0)$ on the $N=48$, $L=18$ lattice has exactly one hit of each sign for at least 15 of 16 targets, total degree zero for every target, and median opposite-sign physical separation between $4$ and $8$.
4. **Orientation reversal:** reversing the domain-orientation factor while leaving the field-vertex order and interpolation fixed reverses every nonzero preimage sign while preserving the hit locations and counts.
5. **Target reproducibility:** two independent evaluations of every control are byte-identical after canonical JSON serialization.

The separated-pair allowance of one uncovered target accounts only for a target lying outside the finite-resolution image of the analytic product; no trajectory gate inherits that allowance.

## 5. Trajectory observables

For each snapshot and target, record positive and negative hit counts $h_m^+,h_m^-$ and net degree $d_m=h_m^+-h_m^-$. Define

$$
C_{\pm}=\frac1K\sum_{m=1}^K
\mathbf 1[h_m^+\ge1\ \land\ h_m^-\ge1],
\qquad
C_0=\frac1K\sum_{m=1}^K\mathbf 1[d_m=0].
$$

For targets with exactly one hit of each sign, record their minimum-image physical separation. The snapshot separation $S$ is the median over those targets. Cluster each sign's physical hit coordinates by their minimum-image circular mean and record the maximum within-sign RMS radius $R_{\rm hit}$ over both signs.

A snapshot contains a **geometrically resolved pair** exactly when:

- it is admissible under the $\pi/2$ edge-angle bound;
- $C_{\pm}=1$ and $C_0=1$;
- every target has exactly one hit of each sign;
- $S\ge4$;
- $R_{\rm hit}\le2$;
- no target is numerically ambiguous.

The snapshot-level definition is intentionally stricter than the analytic-pair control.

## 6. Persistence and refinement gates

For each trajectory, let $t_*$ be its first sampled time at which the snapshot-level pair condition passes.

- **Formation:** $t_*\le2$.
- **Persistence:** every retained snapshot from $t_*$ through $T=4$ passes the pair condition.
- **Time-step agreement:** the $N=48$ primary and half-step trajectories have the same pass/fail state at every common sampled time; their $S$ values differ by at most $0.25$ and their two sign-cluster centres differ by at most $0.25$ after the sign labels are matched.
- **Spatial refinement:** the $N=48$ and $N=64$ trajectories have the same pass/fail state at every common sampled time; their $S$ values differ by at most $0.50$ and their two sign-cluster centres differ by at most $0.50$ after minimum-image matching.
- **Degree conservation:** $d_m=0$ for every target at every admissible trajectory snapshot.

## 7. Frozen decision tree

1. If an input, source hash, control, schema, finite-value check, edge-angle bound, degeneracy check or independent reconstruction fails, return `INCONCLUSIVE`.
2. If either time-step agreement, spatial refinement or degree conservation fails, return `INCONCLUSIVE`.
3. If the $N=64$ trajectory has no formation time $t_*\le2$, return `DOES NOT EMERGE`.
4. If formation occurs but persistence fails before $T=4$, return `DOES NOT EMERGE`.
5. If formation, persistence, time-step agreement, spatial refinement and degree conservation all pass, return `EMERGES CONDITIONAL`.

`EMERGES CONDITIONAL` means only that the supplied massive chiral action and supplied finite-energy impulse generate a persistent geometrically resolved degree-opposite pair. It does not promote the action to canonical Cassi physics or assign particle identity.

## 8. Artifacts and stopping rule

The primary program writes a source-bound JSON receipt beneath
`runs/20260907_matter_formation_geometric_degree/primary/`. A separately implemented verifier reads the raw NPZ fields and primary receipt, reconstructs the triangulation, targets, controls and trajectory metrics without importing the primary module, and writes
`runs/20260907_matter_formation_geometric_degree/verification.json`.

The calculation stops after one primary evaluation and one independent verification. No target, tolerance, triangulation, clustering rule or decision threshold may be changed in response to the result. A changed protocol requires a new dated protocol and new output root.

<!-- geometric-degree-protocol:end -->

## References

- `computations/matter-formation-continuum-report.md` §32—supplied massive chiral action, frozen formation schedule and first-schedule verdict.
- `computations/matter_formation_chiral_lattice.py`—source trajectory implementation and retained raw fields.
- `computations/adjudicate_matter_formation_chiral_lattice.py`—frozen first-schedule reconciliation.
- `foundations/matter-completion-boundary.md` §14—scope of the conditional massive chiral comparison.
