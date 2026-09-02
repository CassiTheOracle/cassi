# Embodied World-Field Intelligence Signed-Axis Coverage Pre-registration

## Status: Frozen—2026-08-31

The frozen v4 run in `research/field_intelligence/embodied_learning_v4_prereg.md` passed every hard and control gate, eliminated the 30-buffer reinitialization leak, and reduced learned median terminal distance from 6.0000 to 0.6963. Three of five targets succeeded. The sole unpaired axis exposed the remaining failure: the target set trained $+z$ but omitted $-z$. The $+z$ replay approached the goal and then entered the unseen $-z$ error context after crossing it, ending at distance 4.0260. Both signed contexts were already trained for $x$ and $y$.

## Changed hypothesis

The six-lobe policy requires full signed-axis context coverage. The target curriculum gains the missing sixth target $(0,0,-6)$ in both the deterministic verifier and the interactive demonstration. No shader, learning-rule, transduction, physical parameter, target radius, step count, ABI, control, or threshold changes.

This is not a special-case correction for $z$: it restores the symmetry implied by the fixed actuator set $\{+x,-x,+y,-y,+z,-z\}$. A probe that crosses any target can then query the learned opposite-error context and brake through the same field-owned policy.

## Frozen rerun

The focused `verify_field_intelligence` arm runs once with FI0–FI9 and six targets:

- learned and restored replay must each succeed on at least 5/6 targets;
- cleared and $\eta=0$ replay must succeed on at most 1/6;
- shuffled reward must succeed on at most 2/6;
- learned median terminal distance must be at most half the cleared median;
- restored terminal distances must match learned replay within 0.20 per target;
- every hard ABI, identity, bounds, snapshot, render-purity, same-list receipt, lifecycle, and resource-ownership gate must remain `PASS`.

Any behavioral miss, hard-gate regression, or resource leak is `REJECT`. A full battery run is allowed only after this run passes.
