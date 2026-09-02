# Embodied World-Field Intelligence Convergence Repair Pre-registration

## Status: Frozen—2026-08-31

The first frozen run in `research/field_intelligence/embodied_learning_prereg.md` produced two distinct outcomes:

- the unbounded interpretation of fast Yang/Yin derivatives as 3-D medium flow was `REJECT` after non-finite particle trajectories;
- after separating the FI transport interpretation from the retained PDE derivatives, all hard gates passed and learned replay reduced median distance from 7.2551 to 1.2793, but only 1/5 trajectories ended inside the frozen 0.75 success radius. FI3 and FI6 therefore remained `FAIL`.

This is a new, narrower engineering hypothesis. The fixture, target set, step counts, success radius, thresholds, buffer ABI, update law, ownership, and controls stay unchanged. The rejected constant-amplitude transduction is not run again.

## Changed hypothesis

A learned action is useful but does not settle because constant medium-flow amplitude carries the probe through the target. The replacement transduction is frozen as:

$$
c(P)=\begin{cases}
1,&\text{training},\\
\operatorname{clip}(P_{\rm selected}/P_{\max},0,1),&\text{replay},
\end{cases}
$$

$$
a(d)=\operatorname{clip}(d/R_{\rm organ},0,1),
$$

$$
\mathbf u=c(P)a(d)u_{\max}\hat{\mathbf e}_{\rm selected}.
$$

This makes the learned score a causal replay gate and tapers the commanded medium flow as the probe approaches the target. Zeroed $P$ commands zero flow; training exploration remains fully actuated. The ordinary RealSim viscosity path still converts medium flow to particle motion.

The deterministic shuffled-reward control now uses a full 32-bit integer avalanche before assigning reward sign. This removes the parity correlation between the former alternating sign and the six-action exploration cycle while preserving every reward magnitude.

## Frozen rerun

The focused `verify_field_intelligence` arm runs once with the unchanged FI0–FI9 gates from the first protocol. In particular:

- learned and restored replay must each succeed on at least 4/5 targets;
- cleared and $\eta=0$ replay must succeed on at most 1/5;
- shuffled reward must succeed on at most 2/5;
- learned median terminal distance must be at most half the cleared median;
- restored terminal distances must match learned replay within 0.20 per target;
- every hard ABI, identity, bounds, snapshot, render-purity, same-list receipt, and lifecycle gate must remain `PASS`.

Any hard-gate regression or behavioral miss is `REJECT`. A full battery run is allowed only after FI0–FI9 all pass.
