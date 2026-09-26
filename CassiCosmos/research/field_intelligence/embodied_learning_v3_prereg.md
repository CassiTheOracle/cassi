# Embodied World-Field Intelligence Support-Gate Pre-registration

## Status: Frozen—2026-08-31

The frozen v2 run in `research/field_intelligence/embodied_learning_v2_prereg.md` kept all hard ABI, identity, bounds, snapshot, render-purity, same-list receipt, control, and lifecycle gates green. It also made the cleared field causally inert and reduced learned median terminal distance from 6.0000 to 2.1456. No trajectory entered the frozen 0.75 success radius, so FI3 and FI6 were `FAIL` and the absolute-score confidence transduction was `REJECT`.

## Changed hypothesis

The learned field selected useful actions, but multiplying actuation by the absolute plasticity magnitude underdrove replay. Plasticity magnitude records reward history and exposure; it is not a calibrated velocity fraction. The replacement uses positive learned support as a gate while retaining the v2 distance taper:

$$
c(P)=\begin{cases}
1,&\text{training},\\
1,&P_{\rm selected}>\max(10^{-4},0.01P_{\max}),\\
0,&\text{{otherwise}},
\end{cases}
$$

$$
a(d)=\operatorname{clip}(d/R_{\rm organ},0,1),
$$

$$
\mathbf u=c(P)a(d)u_{\max}\hat{\mathbf e}_{\rm selected}.
$$

The learned spatial ordering still determines the actuator; the gate only removes the unsupported absolute-score attenuation. A cleared field has $P=0$ everywhere and therefore commands no flow. The PDE source, ordinary RealSim viscosity coupling, target set, update law, controls, ABI, and all numerical thresholds stay unchanged.

## Frozen rerun

The focused `verify_field_intelligence` arm runs once with the unchanged FI0–FI9 protocol:

- learned and restored replay must each succeed on at least 4/5 targets;
- cleared and $\eta=0$ replay must succeed on at most 1/5;
- shuffled reward must succeed on at most 2/5;
- learned median terminal distance must be at most half the cleared median;
- restored terminal distances must match learned replay within 0.20 per target;
- every hard ABI, identity, bounds, snapshot, render-purity, same-list receipt, and lifecycle gate must remain `PASS`.

Any hard-gate regression or behavioral miss is `REJECT`. A full battery run is allowed only after FI0–FI9 all pass.
