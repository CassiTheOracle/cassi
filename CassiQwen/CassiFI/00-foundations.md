# Foundations and design policy

> CassiFI implementation plan, Part 0. [Plan index](README.md) · [Index](README.md) · [Next](./01-field-physics.md)

## Status: revised pre-implementation engineering design—2026-08-26

This file is the living full-system engineering design and implementation plan.
It is expected to improve as implementation, profiling, review, and use reveal
better mechanisms. Editing this document does not invalidate runtime artifacts
by itself. Reproducibility attaches to the exact source, profile, operator, and
artifact identities produced by a particular build or run.

## Purpose

This document defines the complete transition from the current direct Qi-native
runtime to a flow-first field intelligence. It covers the field law, sensory and
motor boundaries, embodied reference frame, perception, predictive remapping,
attention, topological-retention metastable/topological retention, memory, language,
persistence, serving, diagnostics, performance, and evidence needed for
release.

The goal is not a visual demo, a minimal slice, a static page recognizer, or a
new sidecar around the existing text engine. The completed system is one
bounded, deterministic, multiscale Yang/Yin field whose organized flow owns
sensing, memory, prediction, attention, action, and emission. Every phase in
this plan is part of that system. Phases order dependencies; they do not reduce
the endpoint.

The sole adaptive persistent object remains `QiFieldState.field` with logical
layout `[S, 9M, B]`. Fixed transforms, geometry, protocols, and probes are
versioned operator identity within a concrete runtime profile. Transient
predictions, boundary packets, flow ledgers, body transforms, and action
commands are not additional adaptive state.

## Refinement index

The second-pass contracts are deliberately indexed here rather than
redefined. Part 3 owns the contract-root identity; Parts 2 and 4 own the
capacity/retention and complete conversion-domain rules; Parts 5 and 7 own
sensory openness, causal action, and sealed indeterminate-world transaction
semantics; Part 8 owns field-state-necessity and uncertainty-aware text
packing; and Part 9 owns receipt-chain and independent-verification evidence.
Parts 10–13 bind those definitions to work packages, gates, deployment, and
the exact-once registry; W0's hashed dependency manifest is the sole graph
authority and all Mermaid/prose/registry views are generated or checked from
it. The post-cutover research cards are runnable, field-only experiments, not
release prerequisites, fallback paths, or extra state.

## Engineering design policy

This is an engineering program optimized for producing the strongest coherent
system. When implementation exposes a weakness, the design changes rather than
preserving a known-bad mechanism.

- The design may be revised whenever a simpler, stronger, or more internally
  consistent mechanism is found.
- Gates are executable acceptance tests, diagnostics, and regression checks.
  They guide repair; they do not freeze a failed design into perpetuity.
- Controls and counterfactuals isolate causal paths for diagnosis, repair, and
  regression prevention.
- Development metrics, fixtures, tolerances, and capacities may evolve with the
  implementation. A released run manifest is immutable only as a record of
  what that exact run executed.
- Runtime state remains strict: a checkpoint may load only when its
  state-relevant layout, physics, geometry, boundary, and backend identities are
  compatible. Plan edits never authorize silent state conversion or fallback.
- Current architectural decisions are shared defaults, not untouchable laws.
  A cross-cutting change updates this plan and every affected caller, test,
  profile, and receipt in one clean cutover.

## Architectural thesis

Qi is the organized flow. Patterns are temporary organizations, constraints,
standing modes, and memories of that flow.

\[
\boxed{
\text{Qi intelligence}
=
\text{bounded self-steering circulation across space, scale, Yang/Yin
conversion, and the world boundary}
}
\]

A state snapshot can demonstrate field presence, but intelligence is expressed
by the causal trajectory: how the field transports energy and phase, predicts a
successor boundary, redirects itself after residual return, and commits an
action that changes the world.

The decisive counterfactual is directional. Under matched instantaneous energy
and boundary content, reversing a declared flow must reverse the corresponding
successor prediction or action. A state hash change, fixed-probe winner,
readout RMS, `q`, or static cosine is not flow ownership.

## Present implementation truth

The canonical field and terminal paths are `cassi_qi_field.py`,
`cassi_field_language.py`, `cassi_conscious_chat.py`, and
`run_cassi_conscious_chat.py`. Their field dynamics use no Qwen, GGUF,
tokenizer, LM head, KV cache, neural layer, learned projection, optimizer, or
probabilistic sampler. The current `cassi_persistent_provider.py` still imports
`cassi_qwen_displacement.py` and loads a historical baseline receipt during
startup even though neither drives the field. That provider dependency is a
current defect, not a field fallback; W12A removes it from serving composition
and W12E independently verifies the live process before the provider enters the
canonical path. G0 inventories the exact import and startup evidence.

For every scale and mode, derive the complex coordinates

\[
E_Y=Y_{\mathrm{re}}+iY_{\mathrm{im}},
\qquad
E_I=I_{\mathrm{re}}+iI_{\mathrm{im}},
\]

\[
V_Y=V^Y_{\mathrm{re}}+iV^Y_{\mathrm{im}},
\qquad
V_I=V^I_{\mathrm{re}}+iV^I_{\mathrm{im}},
\]

and

\[
D=E_Y-\phi E_I,
\qquad
V_D=V_Y-\phi V_I.
\]

The current `evolve()` law is a bank of independent damped nonlinear
oscillators:

\[
V_D^{t+h}=e^{-\gamma h}V_D^t
-h\left(\Omega^2D^t+\kappa|D^t|^2D^t\right),
\]

\[
D^{t+h}=D^t+hV_D^{t+h}.
\]

There are no neighbor reads, spatial derivatives, scale derivatives, or
advection operators. Consequently:

- `V_D` is temporal coordinate velocity, not spatial velocity;
- `j_temporal=\langle\operatorname{Im}(D^*V_D)\rangle_m` is
  amplitude-weighted modal phase motion, not page-space transport;
- `j_scale` is a phase quadrature between top demodulated adjacent-scale
  bindings, not transferred energy or density;
- `QiFieldReadout.flux` is reconstructed boundary-wave RMS, not a surface flux;
- `consolidate()` writes one strongest demodulated symbol into the next scale
  without debiting the source and is therefore not conservative scale flow;
- `convert_balance()` is a genuine local Yang/Yin position-density exchange,
  but the canonical `cycle()` does not invoke it;
- the differential projector preserves the complementary coordinate
  `phi*E_Y + E_I` before clipping or global rescaling;
- `_bounded_parts()` silently clips/rescales state, so finite output is not by
  itself evidence of stable or conservative dynamics.

The current system is therefore a bounded multiscale modal reservoir. The
implementation plan turns it into a declared spatial and cross-scale transport
medium without adding another adaptive object.

