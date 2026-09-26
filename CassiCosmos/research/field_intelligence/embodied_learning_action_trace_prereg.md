# Embodied World-Field Intelligence Action-Trace Diagnostic Pre-registration

## Status: Frozen—2026-08-31

The v5 curriculum repaired signed-axis coverage but still ended at 3/6 successes. Learned replay reduced every terminal distance below the cleared value and the paired $z$ contexts no longer diverged, so the remaining cause is unresolved between policy-selection instability and physical settling.

## Frozen diagnostic

Run the unchanged six-target verifier once. During the first frozen learned replay only, sample every 12 field steps:

- target index and logical tick;
- probe position and target distance;
- selected actuator and bounded control vector;
- selected score and support margin.

No update law, shader, target, step count, parameter, gate, or control changes are allowed in this diagnostic run.

## Decision tree

For each sample outside the 0.75 target radius, derive the desired signed actuator from the dominant component of target minus probe.

- If fewer than 90% of supported samples select that actuator, the next change must repair policy readout or spatial context sampling.
- If at least 90% select it but terminal distance remains outside the radius, the next change must repair physical settling without changing the learned action.
- If learned samples lose positive support, the next change must repair the support representation.

The diagnostic itself has no adoption verdict and does not authorize a full battery run.
