# Compact-Observable Decomposition of Charged-Wave Spatial Mismatch

## Status: Preregistered post hoc diagnostic—September 2026

## Abstract

This calculation decomposes the compact-cut discrepancy in the retained charged-wave states into cut energy, signed charge, axial momentum, radicand, and binding-ratio terms. It uses the immutable primary state archive from the spatial-convergence campaign and the archived row metadata. It contains no new evolution and does not alter the spatial-convergence receipt or its verdict. The calculation stops at the retained snapshots through $t=48$ and classifies the registered compact observable as denominator-conditioned or component-disagreeing when the original spatial comparison fails.

## 1. Frozen inputs and scope

The primary campaign receipt is
`runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911/result.json`, SHA-256 `c9619d8e431c840b8656ec470ec411ede23614bb20d8b200fbd6f7fd8b356ae9`.

The campaign verification receipt is
`runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911/verification.json`, SHA-256 `45755f677b83b11a65f1fb2271f6c85fa4844e068cc482e4cbb1c74a220abf64`.

The archived source identities that define the state metadata and observable formulas are:

- `computations/matter_formation_wave_capture_spatial_convergence.py`—`4deabd70cca5979c8de7b90d7ef71fda938b455d8195563d1d52de76faf91c6b`;
- `computations/matter_formation_wave_capture.py`—`6f8f6ceaced604e38aab1d08b53eadcf06aa4db1fd1b2f27459995c5d65a5aaa`;
- `computations/verify_matter_formation_wave_capture.py`—`e6111739e6c355a5e4015aca2c468a2855bc9b9a84d713709a7db518c1717a84`;
- `computations/verify_matter_formation_wave_capture_spatial_convergence.py`—`589a26fd4580b61056fdf31a3116981f50f2ec94e29d077b4b82afb130652126`.
The hashes are checked against the immutable files under
`runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911/sources/`. Live source hashes are recorded separately so source drift remains visible without changing the campaign identity.

The output directory is
`runs/20260911_matter_formation_compact_observable_decomposition_20260911`. The runner refuses an existing directory. The existing spatial-convergence receipt, its `primary/` states, its archived metadata, and its verifier receipts remain immutable.

The target rows are `S0`, `S1`, and `S2` for `pair256` and `antiphase256`. The `D0` domain-control rows and single/uncoupled controls remain outside the scientific decomposition. The runner validates the four archived state containers at $t=0,32,40,48$; it computes the late snapshot means over $t\in\{32,40,48\}$. These three retained states are the archive boundary for this post hoc diagnostic; they are not substituted for the spatial campaign's full $32\le t\le48$ trace means when quoting the original gate.

The diagnostic source is captured with its SHA-256 in the output receipt after the source is written. No source edit is permitted between preregistration and execution.

## 2. Archive contract

Each state is an NPZ archive with exactly the keys
`fields`, `velocities`, `r`, `axial`, `volume`, and `time`. The field and velocity arrays have shape $(3,n_r,n_z)$; `r` has shape $(n_r,)$; `axial` has shape $(n_z,)$; `volume` has shape $(n_r,1)$; and `time` is a scalar float64 array. All arrays are float64, finite, and loaded with `allow_pickle=False`.

The row metadata supplies the state path, SHA-256, embedded time, grid radius, spacing, coupling, initial energy, initial signed charge, and the archived trace. The runner requires path containment under the campaign `primary/` directory, exact declared hashes, unique times, exact target-row identities, and the expected grid geometry. A missing archive, hash mismatch, malformed array, nonfinite value, or time mismatch produces `INCONCLUSIVE—archive integrity failure`.

## 3. Fixed action and exact cut construction

The calculation uses the campaign constants

$$
A=\frac1{16},\quad c_\Psi=\frac18,\quad u_\rho=4,
\quad u_C=1,\quad K=1,
$$

$$
B=4.75,\qquad h_C=2.9598260763447164,
\qquad \Omega_\infty=\sqrt{B/A},
\qquad v_*=\sqrt{K/(2A)}.
$$

For each archived state, let $q=(f-1,x,y)$ and $v=\dot q$. The signed charge density is

$$
\rho=-2A(x\dot y-y\dot x).
$$

The cylindrical distance is

$$
d=\sqrt{r^2+\zeta^2}.
$$

The frozen smooth-cut matrix is every pair

$$
R_{\mathrm{in}}\in\{4,6,8,10,12\},
\qquad
W\in\{2,4,6\}.
$$

For each pair, use

$$
 s=\operatorname{clamp}\left(\frac{d-R_{\mathrm{in}}}{W},0,1\right),
 \qquad
 w_{R_{\mathrm{in}},W}(d)=1-3s^2+2s^3.
$$

The cut is applied to both arrays before reconstruction:

$$
q^{(w)}=wq,\qquad v^{(w)}=wv.
$$

The registered reference cut is $(R_{\mathrm{in}},W)=(8,4)$. Matrix members are sensitivity evidence; they cannot replace the reference comparison in the decision rule.

The hard core is retained separately as

$$
\chi_8=\mathbf 1_{d^2<8^2}.
$$

The hard-core energy is the sum of the exact cell-energy allocation multiplied by $\chi_8$. It is not identified with the smooth-cut energy.

## 4. Reconstructed observables

For each state and every smooth-cut matrix member, reconstruct the following quantities from the raw fields.

1. **Smooth-cut energy.** Evaluate the exact finite-volume action energy on $(q^{(w)},v^{(w)})$, including the potential, kinetic terms, radial and axial gradient terms, and the radial and axial Dirichlet boundary terms generated by the cut.

2. **Smooth-cut signed charge.**

   $$
   Q_{\mathrm{cut}}=\sum_{i,j}V_i\,\rho_{ij}\,w_{ij}^2.
   $$

3. **Smooth-cut absolute charge and fraction.**

   $$
   |Q_{\mathrm{cut}}|=\left|Q_{\mathrm{cut}}\right|,
   \qquad
   f_{Q}=\frac{|Q_{\mathrm{cut}}|}{|Q_{\mathrm{initial}}|}.
   $$

4. **Smooth-cut axial momentum.** Use the verifier's finite-volume axial derivative: centered differences in the interior and first-order one-sided differences at both axial boundaries. Then evaluate

   $$
   P_{\mathrm{cut}}=-\sum_{i,j}V_i\left[
   c_\Psi v^{(w)}_{0,ij}\,\partial_\zeta q^{(w)}_{0,ij}
   +2A\left(v^{(w)}_{1,ij}\,\partial_\zeta q^{(w)}_{1,ij}
   +v^{(w)}_{2,ij}\,\partial_\zeta q^{(w)}_{2,ij}\right)\right].
   $$

5. **Binding radicand and ratio.**

   $$
   D_{\mathrm{cut}}=E_{\mathrm{cut}}^2-(v_*P_{\mathrm{cut}})^2,
   $$

   $$
   \mathcal B_{\mathrm{cut}}=
   \frac{\sqrt{D_{\mathrm{cut}}}}{\Omega_\infty|Q_{\mathrm{cut}}|}
   $$

   when $D_{\mathrm{cut}}\ge0$ and $Q_{\mathrm{cut}}\ne0$. A nonfinite or undefined value is an archive-integrity failure for this diagnostic.

6. **Numerator decomposition.** Record $E_{\mathrm{cut}}$, $v_*P_{\mathrm{cut}}$, $D_{\mathrm{cut}}$, $\sqrt{D_{\mathrm{cut}}}$, and $\Omega_\infty|Q_{\mathrm{cut}}|$ separately. The raw signed charge, absolute charge, and denominator fraction remain in the receipt alongside every ratio.

7. **Energy decomposition.** On the cut fields, record mediator potential, carrier potential, kinetic, radial-gradient, and axial-gradient energies. Their sum must equal $E_{\mathrm{cut}}$ within

   $$
   10^{-8}\max(1,|E_{\mathrm{cut}}|).
   $$

8. **Hard-core and shell observables.** Record hard-core energy, hard-core signed charge, hard-core absolute charge, and interface-shell energy using the uncut fields and the exact cell-energy allocation. These fields expose the distinction between a hard-core quantity and a cut-weighted quantity.

## 5. Comparison metrics and normalization

For each target arm, compute late means at each cut for `S0`, `S1`, and `S2`. Form the adjacent comparisons `S0→S1` and `S1→S2`. The reference comparison is `S1→S2` at $(8,4)$.

For a left/right comparison, use the same normalization convention as the spatial-convergence verifier:

$$
S_E=\max(1,|E_{0,L}|,|E_{0,R}|),
\qquad
S_Q=\max(1,|Q_{0,L}|,|Q_{0,R}|).
$$

The normalized comparison errors are

$$
 e_E=\frac{|\bar E_{\mathrm{cut},L}-\bar E_{\mathrm{cut},R}|}{S_E},
 \qquad
 e_Q=\frac{|\bar Q_{\mathrm{cut},L}-\bar Q_{\mathrm{cut},R}|}{S_Q},
$$

$$
 e_M=\frac{|\overline{v_*P}_{L}-\overline{v_*P}_{R}|}{S_E},
 \qquad
 e_D=\frac{|\overline{\sqrt{D}}_{L}-\overline{\sqrt{D}}_{R}|}{S_E},
$$

and

$$
 e_{\mathcal B}=|\bar{\mathcal B}_{L}-\bar{\mathcal B}_{R}|.
$$

The comparison tolerance is the spatial-convergence tolerance

$$
\tau_{\mathrm{comparison}}=0.05.
$$

A ratio failure means $e_{\mathcal B}\ge\tau_{\mathrm{comparison}}$, matching the campaign's strict pass condition $e_{\mathcal B}<\tau_{\mathrm{comparison}}$. The decomposition receipt also reports $e_E$, $e_Q$, $e_M$, and $e_D$ without collapsing them into the ratio. It reports the left and right raw $E_{\mathrm{cut}}$, $Q_{\mathrm{cut}}$, $|Q_{\mathrm{cut}}|$, $f_Q$, $v_*P_{\mathrm{cut}}$, $D_{\mathrm{cut}}$, and $\mathcal B_{\mathrm{cut}}$ means.
### 5.1 Registered full-trace aggregation

The registered spatial comparison is the primary mismatch diagnosed by this
follow-up. For every target row, select every primary trace sample whose
embedded time satisfies $t\ge32$. Compute one mean per registered observable
over that complete late trace, then compare adjacent levels `S0\to S1` and
`S1\to S2`. This aggregation is separate from the four archived states used
by the compact-cut matrix reconstruction: $t=0$ is used for an initial-state
audit, while $t=32,40,48$ supply the finite-volume decomposition snapshots.

The registered observables and fixed comparison scales are

$$
\begin{aligned}
S_E&=\max(1,|E_{0,L}|,|E_{0,R}|),&
S_Q&=\max(1,|Q_{0,L}|,|Q_{0,R}|),\\
S_{f_Q}&=1,&S_{\mathrm{rms}}&=8,&
S_{\mathcal B}&=1,&S_{\mathrm{shell}}&=1.
\end{aligned}
$$

The observable order is `energy`, `charge`, `core_fraction`, `core_rms`,
`binding_ratio`, and `shell_energy_fraction`. For each observable $o$,

$$
e_o=\frac{|\bar o_L-\bar o_R|}{S_o}.
$$

The registered comparison passes when every error is finite, the maximum
error is strictly below $0.05$, and the primary runner's monotone
`S1\to S2` condition is satisfied. The follow-up stores these full-trace
means and errors and reproduces the archived primary comparison errors within
$10^{-12}$. This binds the decomposition to the registered spatial mismatch,
including the pair-arm binding-ratio error, rather than substituting the
four-snapshot matrix mean.

### 5.2 Independent method control

The verification receipt's independent-method comparison is an orthogonal
control. It compares the primary `S1` trace with independently evolved RK4
snapshots at $t\in\{0,32,40,48\}$ for
`energy`, `charge`, `core_fraction`, `core_rms`, `binding_ratio`,
`shell_energy_fraction`, `core_energy`, and `mediator_depletion`. Its
per-sample, per-observable error is

$$
e_{\mathrm{method}}=
\frac{|o_{\mathrm{primary}}-o_{\mathrm{independent}}|}
{\max(1,|o_{\mathrm{primary}}|,|o_{\mathrm{independent}}|)}.
$$

The method control passes only when every declared error is finite, no
snapshot failure is present, and the maximum error is strictly below $0.05$.
The receipt records this control and its normalization. The diagnostic scope
is the registered spatial `S1\to S2` mismatch; the independent-method result
is recorded as a cross-check alongside the compact-cut causal branches.

### 5.3 Compact component normalization and cut-gradient convention

For the compact-cut matrix, compare the five recomputed cut-energy components
`cut_mediator_potential`, `cut_carrier_potential`,
`cut_kinetic_energy`, `cut_radial_gradient`, and `cut_axial_gradient` with

$$
e_c=\frac{|\bar c_L-\bar c_R|}{S_E}.
$$

Each $e_c$ has the same $0.05$ component threshold as the additive
cut-energy, cut-charge, and momentum errors. The
$10^{-8}$ `DECOMPOSITION_TOL` is used only for the identity
$\sum_c c=E_{\mathrm{cut}}$ at each reconstructed state; it cannot pass or
fail a cross-level component comparison.

The cut-energy components are evaluated by recomputing the finite-volume
potential, kinetic, face-gradient, and boundary terms from the masked fields
$q^{(w)}$ and $v^{(w)}$. The radial and axial gradients therefore include
the gradients generated at the smooth-cut interface. The uncut cell-energy
allocation is reserved for the hard-core and interface-shell observables and
is not used as the compact-cut component decomposition.


## 6. Reconstruction and decision rule

Before interpreting any comparison, the runner must pass:

1. exact input receipt hashes and source identities;
2. archive containment, state hashes, keys, dtype, shapes, geometry, finite values, and embedded times;
3. default-cut reconstruction against the archived primary trace at $t=0,32,40,48$ for the registered observables, with
   $|x-y|\le5\times10^{-8}\max(1,|y|)$;
4. the cut-energy component identity at every target state and cut;
5. finite output with complete matrix entries.

The two causal branches apply to the reference `S1→S2` comparison at $(8,4)$:

- **DENOMINATOR-CONDITIONED:** at least one target arm has a ratio failure, while $e_E<0.05$, $e_Q<0.05$, $e_M<0.05$, and every compact energy-component error $e_c<0.05$, and both left and right $f_Q$ values are below the campaign retained-charge fraction $0.25$. This branch identifies a ratio discrepancy in a low-retained-charge compact observable whose additive and recomputed energy components remain within the comparison tolerance.

- **COMPONENT-DISAGREEMENT:** at least one target arm has a ratio failure and either an additive error $e_E\ge0.05$, $e_Q\ge0.05$, or $e_M\ge0.05$, a compact energy-component error $e_c\ge0.05$, or one side has $f_Q\ge0.25$. This branch identifies an additive compact-observable disagreement or a comparison with substantial retained charge.

If both causal branch conditions occur across the two target arms, `COMPONENT-DISAGREEMENT` takes precedence over `DENOMINATOR-CONDITIONED`. If neither target reference comparison has a ratio failure, record `NO_RATIO_FAILURE`; this is the no-failure terminal result rather than a causal branch. If archive or reconstruction checks fail, record `INCONCLUSIVE—archive integrity failure` and do not evaluate a scientific branch. Matrix sensitivity entries are reported for context and cannot override the reference result.

The diagnostic has no formation acceptance criterion. It cannot change the spatial-convergence verdict, establish a bound remnant, or license a new evolution. Any preparation, coupling, width, phase, domain, grid, or final-time change requires a separate evolution preregistration.

## References

- `computations/matter_formation_wave_capture_spatial_convergence_prereg.md`—spatial-convergence schedule, comparison tolerance, retained archive, and stopping rule.
- `computations/matter_formation_wave_capture.py`—finite-volume action, cut-weighted energy, charge, momentum, and binding ratio.
- `computations/verify_matter_formation_wave_capture.py`—independent metric formulas, cut mask, cell-energy allocation, and archive validation.
- `computations/verify_matter_formation_wave_capture_spatial_convergence.py`—primary comparison and verifier tolerances.
- `foundations/matter-completion-boundary.md` §§16–18—charged coexistence, radial condensation, and localized minimizer scope.
