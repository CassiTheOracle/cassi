# Embodied World-Field Intelligence Settling-Horizon Pre-registration

## Status: Frozen—2026-08-31

The frozen v3 run in `research/field_intelligence/embodied_learning_v3_prereg.md` confirmed the support gate but rejected the 120-step replay horizon: all five learned trajectories moved toward their targets, with terminal distances 2.2841, 1.6446, 1.8786, 0.7166, and 2.2841 from the common initial distance 6.0000, while the cleared field remained exactly at 6.0000. Only one trajectory crossed the frozen 0.75 radius, so FI3 and FI6 were `FAIL`.

## Changed hypothesis

The learned field policy is directional and causal, but the replay observation ended after 2.4 simulation-time units. The probe is not teleported or directly impulsed: the learned field sets a bounded medium flow and the retained RealSim viscosity path moves the body toward it. This physical actuator has a settling transient.

The learning rule, support gate, actuation, viscosity, target set, target radius, initial state, training horizon, controls, ABI, and all numerical thresholds remain unchanged. Only the replay observation horizon changes from 120 to 300 field steps, or from 2.4 to 6.0 simulation-time units at the frozen $\Delta t=0.02$. The interactive demonstration uses the same horizon.

## Frozen rerun

The focused `verify_field_intelligence` arm runs once with FI0–FI9 and the 300-step replay horizon:

- learned and restored replay must each succeed on at least 4/5 targets;
- cleared and $\eta=0$ replay must succeed on at most 1/5;
- shuffled reward must succeed on at most 2/5;
- learned median terminal distance must be at most half the cleared median;
- restored terminal distances must match learned replay within 0.20 per target;
- every hard ABI, identity, bounds, snapshot, render-purity, same-list receipt, and lifecycle gate must remain `PASS`;
- the process must report no leaked RenderingDevice storage buffers across FI9 reinitialization.

Any hard-gate regression, behavioral miss, or resource leak is `REJECT`. A full battery run is allowed only after this run passes.
