# Native counterflow and paired-helix measurement

## Status: Analysis specification frozen before current or helix outcomes—2026-09-15

This is a prospective analysis specification over the retained native-sphere data, not a claim that its parent simulations are newly preregistered. The parent concentration, containment, angular-velocity summaries and initialization defects are already known. Component wave-energy fluxes and paired-channel helicity have not been measured before this specification. No parent artifact is overwritten, and no new phase, current-carrying dynamics, winding force or material model is introduced.

The machine-readable thresholds, cases and conditional dense-run rule are in `native_counterflow_spec.json`. The data are `res://_diag/native_sphere_20260915d`, all 25 registered arms. Outputs go to `res://_diag/native_counterflow_20260915`. Production source is unchanged. The current shader and compiled resource are SHA-identical to those recorded by the parent campaign.

## Question and observable boundary

The user hypothesis is that two coupled flows organize into a double helix, with the expansive/contractive or inward/outward roles associated with the two field components. Separate three questions:

1. **Material/species transport:** are Yang and Yin separately identified inward/outward populations? The native wave state does not define such independent kinetic populations, velocities, compact phases or a constitutive map. This identification remains INCONCLUSIVE; do not manufacture populations by assigning particle velocities to species according to field signs.
2. **Native wave-energy radial counterflow:** do the actual two component wave-energy currents show sustained opposed radial transport about the particle cloud?
3. **Native wave-energy paired helix:** do distinguishable current channels have resolved separation, spatial winding and opposite directed motion, persisting over the final window?

A negative in (2) does not automatically negate (3): spatially separated counterflowing tubes need not have opposed currents at the same site or on the same edge. Local cancellation is a diagnostic, not a necessary criterion for a spatially separated double helix. Radial direction and direction along an axial helix remain distinct.

The primary window is code time 24 through 32 inclusive, 41 parent observations per arm. Analyze every retained time as descriptive context. Four kick boundary duplicates are represented once in time summaries, keeping the post-kick state and preserving both raw records. The center is the instantaneous particle mass COM, the radius scale is the arm's declared initial R, and physical site positions are tile positions minus fixed extents. No axis or center is selected by maximizing a helix score.

## Derivation from the executed native operator

The executed code is `compute/cassi_site_physics.glsl`, not the raster Voronoi operator and not the theory-side first-order density conversion solver. With winding=0, momentum cap=0 and radial_source=0, its fixed-graph semidiscrete equations are:

    dY/dt = pY; dI/dt = pI
    dpY/dt = c2 * V^(-1/3) * sum_j (Y_j-Y_i)/d_ij - omega2*(Y-phi*I) + S
    dpI/dt = c2 * V^(-1/3) * sum_j (I_j-I_i)/d_ij + omega2*(Y-phi*I) + S/sqrt(2)
    S = mass_scale * deposited_mass / V

Here V means the shader's guarded volume max(abs(V),0.005). All parent volumes exceed the guard. Distances use the shader's periodic minimum image. Structural inspection before this specification found all 25 recorded CSR graphs connected, reciprocal and duplicate-free. Their graphs and volumes are byte-fixed within each arm.

Coefficients in these formulas mean the actually encoded float32 push constants, including phi, and the shader's rounded sqrt(1/2). The JSON's displayed golden-ratio weight is its mathematical reference; the reconstruction uses that native rounded coefficient consistently in coupling and energy. This precision convention is fixed before any current outcomes.

The positive diagonal symmetrizer is m_i=V_i^(1/3), with component weights gY=1 and gI=phi. The corresponding graph wave energy is

    H = sum_i m_i/2 * (pY_i^2 + phi*pI_i^2)
      + omega2/2 * sum_i m_i*(Y_i-phi*I_i)^2
      + c2/2 * sum_undirected_edges [(Y_j-Y_i)^2 + phi*(I_j-I_i)^2]/d_ij.

The ordinary physical-volume kinetic energy would not symmetrize this operator. Therefore H is a code-unit native graph energy, not a calibrated physical energy or conserved particle mass. Component coupling energy is shared. The finite symplectic-Euler step does not exactly conserve H, even where the semidiscrete identity does.

Splitting each spring energy equally between its endpoints gives the outward bond power

    P_a(i->j) = -g_a*c2*(psi_a[j]-psi_a[i])*(p_a[i]+p_a[j])/(2*d_ij).

It is antisymmetric under edge reversal. The total per-site energy derivative obeys

    dh_i/dt + sum_j [P_Y(i->j)+P_I(i->j)] = m_i*S_i*(pY_i+phi*pI_i/sqrt(2)).

This is verified per node against the actual native RHS, not inferred from a globally canceling sum. A flux-vector reconstruction is J_a[i]=sum_j P_a(i->j)*dvec_ij/(2*V_i), with each periodic edge using its minimum-image vector. This is the specified local first moment of bond transport; it is not a newly evolved velocity field. Also retain the familiar -g_a*c2*p_a*gradient(psi_a) as a separately named continuum-like diagnostic, not as a replacement for the graph current.

## Radial transport measurements

At r/R=0.25, 0.5, 0.75 and 1.0, sum exact graph bond powers across the cut between inside and outside sites. Orient each crossing outward. Retain four nonnegative powers: Y-out, Y-in, I-out and I-in, plus crossing-edge counts, total power, per-species directional bias, net power and species-direction association. These are power categories, not material populations.

The primary radial cut is r=R/2. Bias_a=(out_a-in_a)/(out_a+in_a). Sustained radial counterflow requires opposite bias signs, each absolute bias >=0.5, component throughput balance 2*min(totalY,totalI)/(totalY+totalI)>=0.5, and at least 32 crossing edges. At least 80% of all final-window samples must satisfy these conditions. A frozen zero-current arm is a negative control, not evidence that an unattempted comparison passed. Zero-power cases and attempted denominators are explicit.

Measure same-edge cancellation and current alignment separately in the core r<=R/2 and cloud r<=R. They cannot substitute for the radial cut or helix test.

## Paired-channel geometry

Use the current intensity weights V*|J_Y| and V*|J_I| in the sphere r<=R. The candidate axis comes from their combined spatial covariance: choose the eigenvector adjacent to the larger of the prolate and oblate eigenvalue gaps. The gap ratio must be >=1.25 for an identifiable axis. Choose a deterministic right-handed transverse frame. Do not optimize the axis for winding or scan pitches.

Divide -R<=z<=R into eight axial slices. Record separate weighted channel centroids, transverse RMS widths, effective site counts, mean currents and directional coherence. A resolved pair requires effective count >=8 per channel, slice width >= native h=(domain_volume/site_count)^(1/3), centroid separation >=2h and separation >=sqrt(widthY^2+widthI^2). Record failed conditions even when the full detector is false.

Measure the separation-vector angle versus z on the longest consecutive resolved run. At least six consecutive slices are needed. At least a half turn must be present; adjacent principal increments must remain below pi/2; a linear angle fit must have R^2>=0.8, with >=80% of increments consistent with the winding sign. This is an interval twist observable, not a quantized topological invariant or an assumed rung pitch.

Mean channel currents must have directional coherence >=0.5 and absolute alignment with the measured channel tangent >=0.7. At least 75% of resolved slices must carry opposing channel directions along the axis. Geometry with coflow must fail the counterdirected-helix predicate. Coincident or broad overlapping channels must fail resolved separation.

A persistent paired-helix result needs the full predicate in >=80% of all final-window frames, >=90% handedness agreement among detected frames, adjacent detected axes with absolute cosine >=cos(30 degrees), and changes in sampled interval twist <=0.25 turn. All masks and sample counts are retained. The inference is limited to this axis-resolved channel class; it does not exclude every bent, knotted or toroidal configuration.

## Calibration, independent verification and stopping

Before applying science classification, exercise the detector on declared analytic geometries, including a straight counterflow, helical counterflow, helical coflow, coincident channels, radial flow, zero current and a rotated helical counterflow. The analytic helix parameters and grid are fixed in the JSON. These are measurement calibration inputs, not evidence that the native PDE forms a helix. Repair implementation defects if needed, but do not change frozen criteria to accommodate science outcomes.

Reconstruct the GLSL graph gradient and Laplacian from stored fields and compare against both recorded GPU endpoints of every arm using the specified float32 tolerances. Check all consumed stored/decoded hashes and initial/final fixed graph identity. Check the semidiscrete energy identity per node with nonzero comparison counts. Independently recompute representative actual bond powers, radial cut sums, and geometry from raw/analytic inputs without importing the production metric helper. Mutate an actual computed bond power or a rehashed endpoint gradient to prove its corresponding check fires. Do not edit original raw files.

Apply the frozen even/odd temporal sub-sample diagnostic. If any primary evolving arm satisfies persistent radial counterflow, or any primary evolving frame detects counterdirected helical channels, run the first triggered primary configuration and its other seed through the unchanged native engine with every accepted step captured in the final window. At most two dense arms, dt=0.02 and t_end=32, no new physics or longer observation window. Dense data are required before upgrading an apparent positive. No dense GPU rerun is needed merely to reproduce an already measured negative necessary condition; negative conclusions remain bounded to the retained observations and this geometry class.

Integrity failure yields INCONCLUSIVE. Valid persistent radial opposition yields SUPPORTS for native wave-energy radial counterflow; otherwise CONTRADICTS for that registered hypothesis. Valid persistent counterdirected helical channels, confirmed densely when triggered, yield SUPPORTS for the measured native wave-energy channel hypothesis. Otherwise report DOES NOT EMERGE in the tested geometry, or INCONCLUSIVE when actual numerical/temporal quality prevents a decision. The independent material/species-current identification remains INCONCLUSIVE regardless of wave-current results.

No new production source, shader, default, physical-matter mode or black-hole sector is introduced. No new theory claim or repository-wide test suite is added. Measured outputs, calibration evidence, independent verification and the final report are the deliverable.
