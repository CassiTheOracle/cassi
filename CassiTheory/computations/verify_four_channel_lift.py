#!/usr/bin/env python3
"""Verify the minimal four-channel counterflow lift and its non-uniqueness.

Run from the CassiTheory repository root:

    python computations/verify_four_channel_lift.py

The calculation is an algebraic compatibility audit, not a fit.  It asks
whether the canonical two-density state plus one signed directional moment can
uniquely recover four independently populated channels, and whether the
canonical conversion matrix selects a unique direction-resolved lift.
"""

from __future__ import annotations

import numpy as np


PHI = (1.0 + np.sqrt(5.0)) / 2.0
ATOL = 2.0e-11

# Channel order: Yang/out, Yang/in, Yin/out, Yin/in.  "Out" and "in"
# require a declared oriented physical coordinate; they are labels here.
HADAMARD = np.array(
    [
        [1.0, 1.0, 1.0, 1.0],   # N: total population
        [1.0, 1.0, -1.0, -1.0], # P: Yang-minus-Yin contrast
        [1.0, -1.0, 1.0, -1.0], # D: out-minus-in contrast
        [1.0, -1.0, -1.0, 1.0], # C: species-direction association
    ]
)

# At best, the existing two-fluid state plus one signed current supplies the
# first three moments.  The fourth row is the unresolved association mode.
OBSERVED = HADAMARD[:3]
SPECIES_SUM = np.array(
    [
        [1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 1.0],
    ]
)
DIRECTION = HADAMARD[2]
ASSOCIATION = HADAMARD[3]


def conversion_lift(mix_fraction: float, kappa: float) -> np.ndarray:
    """Return one positive, conservative lift of canonical conversion.

    mix_fraction=1 preserves the directional label during Yang/Yin conversion;
    mix_fraction=0 flips it; intermediate values mix the two.  Every value in
    [0,1] aggregates to the same canonical two-density conversion, so the
    aggregate conversion equations do not select the mixing fraction.
    """

    if not 0.0 <= mix_fraction <= 1.0:
        raise ValueError("mix_fraction must lie in [0, 1]")
    if kappa < 0.0:
        raise ValueError("kappa must be nonnegative")
    return kappa * np.array(
        [
            [-1.0, 0.0, PHI * mix_fraction, PHI * (1.0 - mix_fraction)],
            [0.0, -1.0, PHI * (1.0 - mix_fraction), PHI * mix_fraction],
            [mix_fraction, 1.0 - mix_fraction, -PHI, 0.0],
            [1.0 - mix_fraction, mix_fraction, 0.0, -PHI],
        ]
    )


def ring_generator(clockwise_rate: float, counterclockwise_rate: float) -> np.ndarray:
    """Return positive kinetics on the species-by-direction square perimeter."""

    if clockwise_rate < 0.0 or counterclockwise_rate < 0.0:
        raise ValueError("ring rates must be nonnegative")
    generator = np.zeros((4, 4))
    cycle = (0, 1, 3, 2)  # Y/out -> Y/in -> I/in -> I/out
    for position, source in enumerate(cycle):
        generator[cycle[(position + 1) % 4], source] += clockwise_rate
        generator[cycle[(position - 1) % 4], source] += counterclockwise_rate
        generator[source, source] -= clockwise_rate + counterclockwise_rate
    return generator


def clocked_ring_shift() -> np.ndarray:
    """Return one synchronous quarter-turn around the channel square."""

    shift = np.zeros((4, 4))
    cycle = (0, 1, 3, 2)  # Y/out -> Y/in -> I/in -> I/out
    for position, source in enumerate(cycle):
        shift[cycle[(position + 1) % 4], source] = 1.0
    return shift


def rk4(generator: np.ndarray, state: np.ndarray, duration: float, steps: int) -> np.ndarray:
    """Evolve the constant linear system without a SciPy dependency."""

    value = state.astype(float).copy()
    dt = duration / steps
    for _ in range(steps):
        k1 = generator @ value
        k2 = generator @ (value + 0.5 * dt * k1)
        k3 = generator @ (value + 0.5 * dt * k2)
        k4 = generator @ (value + dt * k3)
        value += (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return value


def main() -> None:
    identity_error = float(np.max(np.abs(HADAMARD @ HADAMARD.T - 4.0 * np.eye(4))))
    assert identity_error < ATOL
    assert np.linalg.matrix_rank(HADAMARD) == 4
    assert np.linalg.matrix_rank(OBSERVED) == 3

    # Two nonnegative four-channel states with the same total, species
    # contrast, and net direction, but different species-direction association.
    state_a = np.array([0.40, 0.10, 0.20, 0.30])
    state_b = state_a + 0.05 * ASSOCIATION
    observed_collision = float(np.max(np.abs(OBSERVED @ state_a - OBSERVED @ state_b)))
    association_gap = float(abs(ASSOCIATION @ state_a - ASSOCIATION @ state_b))
    assert np.min(state_b) >= 0.0
    assert observed_collision < ATOL
    assert association_gap > 0.0
    correlation_identity_errors = []
    connected_correlations = []
    for state in (state_a, state_b):
        total, species, direction, association = HADAMARD @ state
        connected = association / total - species * direction / total ** 2
        determinant = state[0] * state[3] - state[1] * state[2]
        correlation_identity_errors.append(
            abs(connected - 4.0 * determinant / total ** 2)
        )
        connected_correlations.append(float(connected))
    correlation_identity_error = float(max(correlation_identity_errors))
    connected_correlation_gap = float(np.ptp(connected_correlations))
    assert correlation_identity_error < ATOL
    assert connected_correlation_gap > 0.0

    # All four Hadamard moments do reconstruct the four channels exactly.
    moments = HADAMARD @ state_a
    reconstructed = HADAMARD.T @ moments / 4.0
    reconstruction_error = float(np.max(np.abs(reconstructed - state_a)))
    assert reconstruction_error < ATOL

    # Fixed-total nonnegative populations occupy a 3-simplex: the four vertex
    # differences relative to one vertex span three affine dimensions.
    simplex_vertices = np.eye(4)
    simplex_dimension = int(
        np.linalg.matrix_rank(simplex_vertices[1:] - simplex_vertices[0])
    )
    assert simplex_dimension == 3

    # Exhibit a continuous family of direction-resolved generators that all
    # reduce to the same canonical rank-one conversion on (E_Y, E_I).
    kappa = 0.07
    canonical = kappa * np.array([[-1.0, PHI], [1.0, -PHI]])
    mix_fractions = (0.0, 0.5, 1.0)
    generators = [
        conversion_lift(mix_fraction, kappa)
        for mix_fraction in mix_fractions
    ]
    aggregation_errors = [
        float(np.max(np.abs(SPECIES_SUM @ generator - canonical @ SPECIES_SUM)))
        for generator in generators
    ]
    assert max(aggregation_errors) < ATOL
    assert np.max(np.abs(generators[0] - generators[-1])) > 0.0
    off_diagonal_minimum = min(
        float(np.min(generator - np.diag(np.diag(generator))))
        for generator in generators
    )
    conservation_error = max(
        float(np.max(np.abs(np.sum(generator, axis=0))))
        for generator in generators
    )
    assert off_diagonal_minimum >= 0.0
    assert conservation_error < ATOL

    # Numerically evolve the same initial condition.  Species totals are
    # identical for every lift, while directional observables are not.
    evolved = [rk4(generator, state_a, duration=5.0, steps=2000) for generator in generators]
    aggregates = np.stack([SPECIES_SUM @ state for state in evolved])
    aggregate_spread = float(np.max(np.ptp(aggregates, axis=0)))
    direction_values = np.array([DIRECTION @ state for state in evolved])
    association_values = np.array([ASSOCIATION @ state for state in evolved])
    direction_spread = float(np.ptp(direction_values))
    association_spread = float(np.ptp(association_values))
    minimum_population = float(min(np.min(state) for state in evolved))
    assert aggregate_spread < ATOL
    assert max(direction_spread, association_spread) > 1.0e-4
    assert minimum_population >= -ATOL

    # The four labels form a species-by-direction square graph, even though
    # their fixed-total population state space is a tetrahedron.  Circulation
    # around that graph can carry a phase-like rotating first harmonic in
    # (P,D), but positive linear rates make it transient:
    #
    #   d/dt [P,D]^T = [[-gamma, -omega], [omega, -gamma]] [P,D]^T,
    #
    # where gamma=r_+ + r_- and omega=r_- - r_+ for the cycle orientation
    # above.  Nonnegative rates imply gamma >= |omega|, so nonzero rotation
    # cannot be undamped in this model.
    clockwise_rate = 0.35
    counterclockwise_rate = 0.10
    ring = ring_generator(clockwise_rate, counterclockwise_rate)
    rotor_projection = HADAMARD[1:3]
    rotor_embedding = rotor_projection.T / 4.0
    rotor_matrix = rotor_projection @ ring @ rotor_embedding
    rotor_decay = clockwise_rate + counterclockwise_rate
    rotor_frequency = counterclockwise_rate - clockwise_rate
    expected_rotor = np.array(
        [
            [-rotor_decay, -rotor_frequency],
            [rotor_frequency, -rotor_decay],
        ]
    )
    rotor_generator_error = float(np.max(np.abs(rotor_matrix - expected_rotor)))
    assert rotor_generator_error < ATOL
    assert rotor_decay >= abs(rotor_frequency)
    rotor_turns_per_efold = abs(rotor_frequency) / (
        2.0 * np.pi * rotor_decay
    )
    one_turn_amplitude_retention = np.exp(
        -2.0 * np.pi * rotor_decay / abs(rotor_frequency)
    )
    assert rotor_turns_per_efold <= 1.0 / (2.0 * np.pi) + ATOL
    assert one_turn_amplitude_retention <= np.exp(-2.0 * np.pi) + ATOL
    moment_generator = HADAMARD @ ring @ HADAMARD.T / 4.0
    expected_moment_generator = np.array(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, -rotor_decay, -rotor_frequency, 0.0],
            [0.0, rotor_frequency, -rotor_decay, 0.0],
            [0.0, 0.0, 0.0, -2.0 * rotor_decay],
        ]
    )
    full_ring_generator_error = float(
        np.max(np.abs(moment_generator - expected_moment_generator))
    )
    assert full_ring_generator_error < ATOL

    # A synchronous discrete update can realize an exact quarter-turn.  It is
    # a positive, conservative permutation, but the external tick is extra
    # structure rather than a time-homogeneous continuous-rate law.
    clocked_shift = clocked_ring_shift()
    clocked_moment_map = HADAMARD @ clocked_shift @ HADAMARD.T / 4.0
    expected_clocked_moment_map = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, -1.0],
        ]
    )
    clocked_rotation_error = float(
        np.max(np.abs(clocked_moment_map - expected_clocked_moment_map))
    )
    clocked_four_step_error = float(
        np.max(np.abs(np.linalg.matrix_power(clocked_shift, 4) - np.eye(4)))
    )
    clocked_conservation_error = float(
        np.max(np.abs(np.sum(clocked_shift, axis=0) - 1.0))
    )
    assert clocked_rotation_error < ATOL
    assert clocked_four_step_error < ATOL
    assert clocked_conservation_error < ATOL
    assert float(np.min(clocked_shift)) >= 0.0

    rotor_initial = np.array([0.40, 0.30, 0.20, 0.10])

    balanced_rate = 0.20
    balanced_ring = ring_generator(balanced_rate, balanced_rate)
    balanced_rotor = rotor_projection @ balanced_ring @ rotor_embedding
    detailed_balance_phase_rate = 0.5 * float(
        balanced_rotor[1, 0] - balanced_rotor[0, 1]
    )
    assert abs(detailed_balance_phase_rate) < ATOL
    stationary_state = np.full(4, 0.25)
    stationary_residual = float(np.max(np.abs(ring @ stationary_state)))
    stationary_cycle_current = float(
        (clockwise_rate - counterclockwise_rate) * stationary_state[0]
    )
    balanced_cycle_current = float(
        (balanced_rate - balanced_rate) * stationary_state[0]
    )
    assert stationary_residual < ATOL
    assert stationary_cycle_current > 0.0
    assert abs(balanced_cycle_current) < ATOL
    sample_times = np.linspace(0.0, 4.0, 41)
    rotor_states = [
        rotor_initial
        if time == 0.0
        else rk4(ring, rotor_initial, duration=float(time), steps=max(1, int(500 * time)))
        for time in sample_times
    ]
    rotor_modes = np.stack([rotor_projection @ state for state in rotor_states])
    rotor_amplitudes = np.linalg.norm(rotor_modes, axis=1)
    rotor_phases = np.unwrap(np.arctan2(rotor_modes[:, 1], rotor_modes[:, 0]))
    fitted_decay = -float(np.polyfit(sample_times, np.log(rotor_amplitudes), 1)[0])
    fitted_frequency = float(np.polyfit(sample_times, rotor_phases, 1)[0])
    rotor_minimum_population = float(min(np.min(state) for state in rotor_states))
    assert abs(fitted_decay - rotor_decay) < 2.0e-10
    rotor_phase_residual = float(
        np.max(
            np.abs(
                rotor_phases
                - (rotor_phases[0] + rotor_frequency * sample_times)
            )
        )
    )
    assert abs(fitted_frequency - rotor_frequency) < 2.0e-10
    assert rotor_minimum_population >= -ATOL

    assert rotor_phase_residual < 2.0e-10
    print("Four-channel counterflow lift audit")
    print(f"  hadamard_identity_max_error: {identity_error:.3e}")
    print(f"  full_channel_rank: {np.linalg.matrix_rank(HADAMARD)}")
    print(f"  two_fluids_plus_one_direction_rank: {np.linalg.matrix_rank(OBSERVED)}")
    print(f"  unresolved_linear_dimension: {4 - np.linalg.matrix_rank(OBSERVED)}")
    print(f"  fixed_total_nonnegative_state_dimension: {simplex_dimension}")
    print(f"  nonnegative_collision_observable_error: {observed_collision:.3e}")
    print(f"  hidden_association_gap: {association_gap:.6f}")
    print(f"  connected_correlation_identity_error: {correlation_identity_error:.3e}")
    print(f"  hidden_connected_correlation_gap: {connected_correlation_gap:.6f}")
    print(f"  full_moment_reconstruction_error: {reconstruction_error:.3e}")
    print(f"  lift_aggregation_max_error: {max(aggregation_errors):.3e}")
    print(f"  lift_conservation_max_error: {conservation_error:.3e}")
    print(f"  lift_off_diagonal_minimum: {off_diagonal_minimum:.6f}")
    print(f"  evolved_species_total_spread: {aggregate_spread:.3e}")
    print(f"  evolved_direction_spread: {direction_spread:.6f}")
    print(f"  evolved_association_spread: {association_spread:.6f}")
    print(f"  minimum_evolved_population: {minimum_population:.6f}")
    print(f"  rotor_generator_max_error: {rotor_generator_error:.3e}")
    print(f"  full_ring_generator_max_error: {full_ring_generator_error:.3e}")
    print(f"  clocked_quarter_turn_error: {clocked_rotation_error:.3e}")
    print(f"  clocked_four_step_return_error: {clocked_four_step_error:.3e}")
    print(f"  clocked_conservation_error: {clocked_conservation_error:.3e}")
    print(f"  rotor_phase_rate: {fitted_frequency:.6f}")
    print(f"  rotor_amplitude_decay_rate: {fitted_decay:.6f}")
    print(f"  rotor_positive_rate_bound: decay >= |phase rate| ({rotor_decay:.2f} >= {abs(rotor_frequency):.2f})")
    print(f"  rotor_turns_per_efold: {rotor_turns_per_efold:.6f}")
    print(f"  one_turn_amplitude_retention: {one_turn_amplitude_retention:.6e}")
    print(f"  rotor_minimum_population: {rotor_minimum_population:.6f}")
    print(f"  rotor_phase_linearity_error: {rotor_phase_residual:.3e}")
    print(f"  detailed_balance_phase_rate: {detailed_balance_phase_rate:.6f}")
    print(f"  stationary_distribution_residual: {stationary_residual:.3e}")
    print(f"  stationary_directed_edge_current: {stationary_cycle_current:.6f}")
    print(f"  detailed_balance_edge_current: {balanced_cycle_current:.6f}")
    print("VERDICT: NO UNIQUE FOUR-CHANNEL LIFT FROM THE CANONICAL TWO-FLUID STATE")
    print(
        "CONDITIONAL RESULT: four nonnegative directional populations form a "
        "valid R^4 kinetic extension, with a 3-simplex after fixing total density."
    )
    print(
        "CONDITIONAL ROTOR: a directed four-cycle has an emergent phase-like "
        "mode, but positive linear kinetics damp it; sustained phase requires "
        "additional driven or nonlinear dynamics."
    )
    print(
        "CONDITIONAL CLOCKED ROTOR: a synchronous channel permutation makes "
        "an exact contrast-preserving quarter-turn per tick, but the clock is "
        "additional dynamics."
    )


if __name__ == "__main__":
    main()
