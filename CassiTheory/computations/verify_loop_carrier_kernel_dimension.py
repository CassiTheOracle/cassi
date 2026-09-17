#!/usr/bin/env python3
"""§71: the closed-form kernel dimension of the composition-coexistence body, at its own point.

This audit does not integrate the field, does not re-run the spent body and does not amend
its frozen §1-§7 text. It reads the frozen declaration, the bound operator module and the
spent receipt, and answers four questions with numbers:

  1. the parameter tuple the run declared, read from the bound module (§0 of the protocol
     binds that module by digest, so its constants *are* the declared tuple) and from the
     receipt's own arm coordinates;
  2. theorem 6.3's three gap entries at that point, with the distance from the point to each
     of the three boundaries;
  3. `dim ker` of the frozen `mode_generator` at that point, by two independent routes (the
     frozen `closed_spectrum`'s zero count and the generator's own null space), with the
     labels of the kernel directions and the eigenstructure of the neighbouring modes;
  4. whether the one coordinate the run measured as retained is a kernel direction (a
     conservation law) or a count against `dim ker` (a capacity), with the branches written
     down before the arithmetic.

It also audits the reading domain the run actually used: the frozen executor's
`composition_profile` reduces the composition over the loop axis where §1.2 declares the
reduction over the exterior axis, so the coordinates the receipt holds are not the
coordinates the protocol declares. That is reported, not repaired: the spent body is frozen.

Exit 0 on a clean self-check against the literal table, 1 on a mismatch, 3 on a digest
mismatch (refusal). Usage: `python verify_loop_carrier_kernel_dimension.py [--collect]`.
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_REFUSED = 3

BOUND_MODULE_PATH = "computations/verify_loop_to_bubble_projection.py"
# The spent write body's own recorded offset law, read to place the exponent the audit cites.
WRITE_LAW_EXPONENT = 1.0302448806878108
RECEIPT_PATH = "runs/loop_carrier_composition_coexistence/verification.json"

# The frozen declaration's own digest, as the spent executor carries it. Read from the body
# at import; the literal here is a floor on what this audit is willing to read.
DECLARED_BODY_DIGEST = "09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25"

# Section 1.2 of the protocol, quoted by the audit to state what the reading domain *is*.
DECLARED_READING_ANCHOR = "c_{s,k}(t)"
DECLARED_READING_RANGE = "k=0,\\dots,23"

# The classification branches, fixed before the arithmetic below is read.
BRANCHES = (
    ("equal", "measured == dim ker: the retained coordinate is a kernel direction, so the "
              "retention is a conservation law of the frozen generator, not a capacity"),
    ("measured_smaller", "measured < dim ker: the carrier holds conserved coordinates the "
                         "declared drive cannot address -- a placement problem, not a second "
                         "writable level"),
    ("measured_larger", "measured > dim ker: the linear theory undercounts; the excess is "
                        "nonlinear storage and is the interesting outcome"),
)

# The degeneracy list the theorem attaches to each vanishing entry, as the predictive handle.
DEGENERACIES = (
    ("kappa -> 0", "species composition (the two carriers' ratio) becomes conserved"),
    ("r -> 0", "uniform direction imbalance becomes conserved"),
    ("d = omega = 0", "loop-nonuniform, direction-symmetric content becomes conserved"),
    ("d = r = 0", "ballistic +-m omega, zero real decay"),
)

ZERO_TOL = 1.0e-12
KERNEL_TOL = 1.0e-10
EIGEN_TOL = 1.0e-9


def digest_of(relative_path: str) -> str:
    with open(os.path.join(ROOT, relative_path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_body():
    import verify_loop_carrier_composition_coexistence as body

    if body.FROZEN_BODY_DIGEST != DECLARED_BODY_DIGEST:
        print("REFUSING: the frozen body's own digest literal is {0}, this audit reads {1}"
              .format(body.FROZEN_BODY_DIGEST, DECLARED_BODY_DIGEST))
        raise SystemExit(EXIT_REFUSED)
    return body


def bind(body) -> dict:
    """Every byte this audit reads, against the declaration that binds it."""
    observed = {
        "protocol_body_sha256": body.protocol_body_digest(),
        "executor_sha256": digest_of(os.path.relpath(body.PROBE_PATH, ROOT)
                                     if os.path.isabs(body.PROBE_PATH) else body.PROBE_PATH),
        "bound_module_sha256": digest_of(BOUND_MODULE_PATH),
        "receipt_sha256": digest_of(RECEIPT_PATH),
    }
    binding = body.check_binding(expect_body=DECLARED_BODY_DIGEST,
                                 expect_executor=observed["executor_sha256"])
    declared_bound = binding["declared"].get("bound_module_sha256")
    if declared_bound is not None and declared_bound != observed["bound_module_sha256"]:
        print("REFUSING: the declaration binds the operator module at {0}, this audit reads "
              "{1}".format(declared_bound, observed["bound_module_sha256"]))
        raise SystemExit(EXIT_REFUSED)
    observed["bound_module_declared_sha256"] = declared_bound
    observed["protocol_file_sha256"] = digest_of(body.PROTOCOL_PATH)
    observed["frozen_body_declared_sha256"] = DECLARED_BODY_DIGEST
    return observed


def declared_point(body, base, receipt) -> dict:
    """The tuple, from the bound module and the receipt's own arm coordinates."""
    frozen = base.frozen
    load_reference = receipt["arms"]["load_reference"]
    spec = body.CoexistenceSpec(0, "audit_point", "audit", body.LARGEST_LOAD,
                                (body.NO_WRITE, body.NO_WRITE, body.NO_WRITE), "itself")
    state = body.gate_load.loaded_seed(spec, base)
    rate = base.gate_rate(*base.projection(state))
    rate_through_split = body.split.gate_rate_of(state, base)[:, 0]
    rate_agrees = float(np.max(np.abs(rate - rate_through_split)))
    seed_coordinate = float(load_reference["coordinate"]["initial"])
    equilibrium_coordinate = float(load_reference["coordinate"]["final"])
    kappa_seed = (1.0 - seed_coordinate) * frozen.LAM
    return {
        "state": state,
        "rate": rate,
        "rate_through_split_gap": rate_agrees,
        "origin": {
            "phi": {"value": float(frozen.PHI), "origin": "frozen module PHI = (1+sqrt(5))/2"},
            "exchange": {"value": float(frozen.EXCHANGE),
                         "origin": "frozen module EXCHANGE"},
            "omega": {"value": float(frozen.OMEGA), "origin": "frozen module V / R"},
            "loop_diffusion": {"value": float(frozen.D_LOOP),
                               "origin": "frozen module D_ELL / R**2"},
            "lambda": {"value": float(frozen.LAM), "origin": "frozen module LAM"},
            "v": float(frozen.V), "r": float(frozen.R), "d_ell": float(frozen.D_ELL),
            "nx": int(frozen.NX), "n_chi": int(base.N_CHI),
            "kappa_seed": {"value": kappa_seed,
                           "origin": "LAM [1 - coordinate(load_reference, initial)]"},
            "kappa_equilibrium": {"value": (1.0 - equilibrium_coordinate) * frozen.LAM,
                                  "origin": "LAM [1 - coordinate(load_reference, final)]"},
            "seed_rate_min": float(np.min(rate)), "seed_rate_mean": float(np.mean(rate)),
            "seed_rate_max": float(np.max(rate)),
            "seed_coordinate": seed_coordinate,
            "equilibrium_coordinate": equilibrium_coordinate,
            "ray_distance_final": float(load_reference["ray_distance"]),
        },
    }


def relations(point) -> dict:
    """The declared relations among the tuple, checked rather than assumed."""
    origin = point["origin"]
    return {
        "omega_is_v_over_r": float(origin["omega"]["value"] - origin["v"] / origin["r"]),
        "loop_diffusion_is_d_ell_over_r_squared": float(
            origin["loop_diffusion"]["value"] - origin["d_ell"] / origin["r"] ** 2),
        "kappa_seed_is_seed_rate_mean": float(
            origin["kappa_seed"]["value"] - origin["seed_rate_mean"]),
        "ratio_omega_over_exchange": origin["omega"]["value"] / origin["exchange"]["value"],
    }


def entries(kappa: float, phi: float, exchange: float, omega: float,
            loop_diffusion: float) -> dict:
    """Theorem 6.3's three entries at one declared point, each with its boundary."""
    root = cmath.sqrt(exchange ** 2 - omega ** 2).real
    return {
        "kappa_entry": kappa * (1.0 + phi),
        "exchange_entry": 2.0 * exchange,
        "loop_entry": loop_diffusion + exchange - root,
        "mode0_loop_entry": loop_diffusion,
        "root_argument": exchange ** 2 - omega ** 2,
        "root": root,
    }


def boundary_distances(entries_at_point: dict, kappa: float, phi: float,
                       exchange: float, omega: float, loop_diffusion: float) -> dict:
    """How far the declared point sits from each boundary, in the entry and in the dial."""
    return {
        "kappa_entry": entries_at_point["kappa_entry"],
        "kappa_dial": kappa,
        "exchange_entry": entries_at_point["exchange_entry"],
        "exchange_dial": exchange,
        "loop_entry": entries_at_point["loop_entry"],
        "loop_diffusion_dial": loop_diffusion,
        "omega_dial": omega,
        "joint_loop_dial": math.hypot(loop_diffusion, omega),
        "omega_minus_exchange": omega - exchange,
        "min_entry": min(entries_at_point["kappa_entry"], entries_at_point["exchange_entry"],
                         entries_at_point["loop_entry"]),
    }


def slow_rate(mode: int, exchange: float, omega: float, loop_diffusion: float) -> float:
    """LB38: g_m = d m^2 + r - Re sqrt(r^2 - m^2 Omega^2), complex above m Omega > r."""
    return (loop_diffusion * mode ** 2 + exchange
            - cmath.sqrt(exchange ** 2 - mode ** 2 * omega ** 2).real)


def spectra(body, base, frozen, kappa: float, phi: float, exchange: float, omega: float,
            loop_diffusion: float, modes=(0, 1, 2, 3)) -> dict:
    """Per mode: the frozen spectrum, its zero count, its gap, and the generator's null space."""
    out = {}
    for mode in modes:
        values = np.asarray(frozen.closed_spectrum(mode, kappa, exchange, omega,
                                                   loop_diffusion))
        generator = frozen.mode_generator(mode, kappa, exchange, omega, loop_diffusion)
        singular = np.linalg.svd(generator, compute_uv=False)
        nullity = int(np.sum(singular <= KERNEL_TOL * float(singular[0])))
        eigenvalues = np.linalg.eigvals(generator)
        zeros = int(np.sum(np.abs(values.real) <= ZERO_TOL))
        nonzero = sorted(abs(value.real) for value in values
                         if abs(value.real) > ZERO_TOL)
        route_gap = float(np.min(np.abs(eigenvalues.real)))
        chain = np.asarray(base.mode_spectrum(mode, kappa, exchange))
        kernel_vectors = []
        if nullity:
            u, s, vh = np.linalg.svd(generator)
            for row in range(len(singular) - nullity, len(singular)):
                vector = vh[row].conj()
                kernel_vectors.append(vector)
        out[mode] = {
            "spectrum": [complex(value) for value in values],
            "zeros": zeros,
            "gap": float(nonzero[0]) if nonzero else 0.0,
            "nullity": nullity,
            "generator_gap": route_gap,
            "spectrum_agrees_with_chain": float(np.max(np.abs(
                np.sort_complex(values) - np.sort_complex(chain)))),
            "slow_rate": slow_rate(mode, exchange, omega, loop_diffusion),
            "kernel_vectors": kernel_vectors,
        }
    # The loop family is increasing in m, so the minimum over all modes is the minimum over
    # the entries; check that rather than assume it.
    family = [slow_rate(mode, exchange, omega, loop_diffusion) for mode in range(1, 25)]
    out["family_increasing"] = bool(all(family[i] < family[i + 1]
                                        for i in range(len(family) - 1)))
    out["family_first"] = family[0]
    return out


def kernel_structure(vector: np.ndarray, phi: float) -> dict:
    """The kernel direction in the generator's own basis: (carrier, direction)."""
    # np.kron(conversion, eye(2)) orders the four components as (carrier, direction).
    y0, y1, i0, i1 = (complex(value) for value in vector)
    scale = max(abs(y0), abs(y1), abs(i0), abs(i1))
    return {
        "components": (y0 / scale, y1 / scale, i0 / scale, i1 / scale),
        "carrier_ratio": (y0 + y1) / (i0 + i1),
        "carrier_ratio_minus_phi": abs((y0 + y1) / (i0 + i1)) - phi,
        "direction_asymmetry_y": abs(y0 - y1) / scale,
        "direction_asymmetry_i": abs(i0 - i1) / scale,
        "epsilon_of_direction_pair": abs((y0 + y1) - phi * (i0 + i1)) / scale,
    }


def reading_domain(body, base, point) -> dict:
    """What the run actually read: the frozen reduction, probed on declared-shaped states."""
    state = point["state"]
    shape = state.shape
    loop_axis, exterior_axis = base.LOOP_AXIS, base.EXTERIOR_AXIS
    n_chi, n_x = shape[loop_axis], shape[exterior_axis]
    chi = 2.0 * math.pi * np.arange(n_chi) / n_chi
    x = 2.0 * math.pi * np.arange(n_x) / n_x
    loop_only = np.empty_like(state)
    loop_only[0] = (1.05 + 0.11 * np.cos(chi))[None, None, :] + 0.0 * state[0]
    loop_only[1] = (1.05 + 0.0 * np.cos(chi))[None, None, :] + 0.0 * state[1]
    exterior_only = np.empty_like(state)
    exterior_only[0] = (1.05 + 0.11 * np.cos(x))[None, :, None] + 0.0 * state[0]
    exterior_only[1] = (1.05 + 0.0 * np.cos(x))[None, :, None] + 0.0 * state[1]

    def declared(probe):
        """§1.2's own object: mean over the exterior axis, indexed by the loop sample."""
        # The composition carries the state's own three axes minus the carrier: the
        # declared reduction is the mean over the exterior axis, index 1 here, indexed by
        # the loop sample.
        composition = base.frozen.bounded_q(probe[0], probe[1])
        return composition.mean(axis=1)

    out = {}
    for label, probe in (("loop_only", loop_only), ("exterior_only", exterior_only)):
        implemented = body.composition_profile(probe, base)
        declared_object = declared(probe)
        out[label] = {
            "implemented_shape": tuple(int(value) for value in implemented.shape),
            "declared_shape": tuple(int(value) for value in declared_object.shape),
            "implemented_spread": float(np.max(implemented, axis=1).max()
                                        - np.min(implemented, axis=1).min()),
            "implemented_row_spread": float(np.max(implemented[0]) - np.min(implemented[0])),
            "declared_row_spread": float(np.max(declared_object[0])
                                         - np.min(declared_object[0])),
        }
    protocol = body.protocol_text()
    quoted = [line.strip() for line in protocol.splitlines()
              if DECLARED_READING_ANCHOR in line]
    out["declared_line_quoted"] = bool(quoted)
    out["declared_samples_24_quoted"] = any(DECLARED_READING_RANGE in line
                                            for line in quoted)
    out["declared_line_text"] = quoted[0] if quoted else ""
    out["implemented_line_quoted"] = ("composition.mean(axis=base.EXTERIOR_AXIS)"
                                      in open(os.path.join(
                                          HERE, "verify_loop_carrier_composition_coexistence.py"),
                                          encoding="utf-8").read())
    out["n_x"] = int(n_x)
    out["n_chi"] = int(n_chi)
    out["cosine_docstring_claims_48"] = "48-vector" in (
        body.direction_cosine.__doc__ or "")
    out["group_length"] = int(body.group_of(body.composition_profile(state, base))[0].shape[0])
    return out


def receipt_times(body, receipt) -> dict:
    """The read times the receipt's group keys stand for, from its own schedule."""
    schedule = receipt["arms"]["write_A"]["schedule"]
    dt = float(schedule["dt"])
    samples = [int(value) for value in schedule["samples"]]
    times = [index * dt for index in samples]
    return {"dt": dt, "samples": samples, "times": times,
            "t1": body.PHASE_STEPS * dt, "t2": 2 * body.PHASE_STEPS * dt,
            "t3": float(schedule["horizon"]),
            "release_offsets": list(receipt["thresholds"]["horizons"]),
            "release_times": [2 * body.PHASE_STEPS * dt + offset
                              for offset in receipt["thresholds"]["horizons"]]}


def measurement(body, base, receipt, point, entries_equilibrium: dict) -> dict:
    """The receipt's own numbers, and what they say against the closed form."""
    arms = receipt["arms"]
    displacement = receipt["displacements"]
    times = receipt_times(body, receipt)
    span_release = times["t3"] - times["t2"]
    span_first = times["t2"] - times["t1"]
    write_a = displacement["write_A"]["groups"]
    write_b = displacement["write_B"]["groups"]
    joint = displacement["joint_AB"]["groups"]
    erase = displacement["erase_A"]["groups"]
    fitted = float(receipt["clock"]["measured"]["rate"])
    predicted = entries_equilibrium["kappa_entry"]
    joint_odd_gap = abs(math.log(joint["t2"]["odd_norm"] / joint["t1"]["odd_norm"]))
    erase_odd_gap = abs(math.log(erase["t2"]["odd_norm"] / erase["t1"]["odd_norm"]))
    retention = abs(write_a["t3"]["even_norm"] - write_a["t2"]["even_norm"]) / \
        write_a["t2"]["even_norm"]
    decay_prediction = 1.0 - math.exp(-predicted * span_release)
    additive = receipt["decision"]["additive"]
    return {
        "times": times,
        "additive_even_relative_gap": float(additive["even"]["relative_gap"]),
        "additive_even_cosine": float(additive["even"]["cosine"]),
        "additive_odd_relative_gap": float(additive["odd"]["relative_gap"]),
        "erase_against_joint_relative_gap": float(
            receipt["decision"]["erase_match"]["against_joint"]["relative_gap"]),
        "declared_nu": float(receipt["clock"]["declared"]["declared"]),
        "fitted_clock": fitted,
        "fitted_clock_minus_kappa_entry": fitted - predicted,
        "fitted_clock_ratio": fitted / predicted,
        "declared_nu_ratio": float(receipt["clock"]["declared"]["declared"]) / predicted,
        "A_t1": float(write_a["t1"]["even_norm"]),
        "A_t2": float(write_a["t2"]["even_norm"]),
        "A_t3": float(write_a["t3"]["even_norm"]),
        "A_odd_t1": float(write_a["t1"]["odd_norm"]),
        "A_odd_t2": float(write_a["t2"]["odd_norm"]),
        "A_odd_t3": float(write_a["t3"]["odd_norm"]),
        "B_even_t1": float(write_b["t1"]["even_norm"]),
        "B_even_t3": float(write_b["t3"]["even_norm"]),
        "B_odd_t1": float(write_b["t1"]["odd_norm"]),
        "B_odd_t2": float(write_b["t2"]["odd_norm"]),
        "B_odd_t3": float(write_b["t3"]["odd_norm"]),
        "joint_odd_t1": float(joint["t1"]["odd_norm"]),
        "joint_odd_t2": float(joint["t2"]["odd_norm"]),
        "joint_odd_t3": float(joint["t3"]["odd_norm"]),
        "erase_odd_t1": float(erase["t1"]["odd_norm"]),
        "erase_odd_t2": float(erase["t2"]["odd_norm"]),
        "erase_odd_rate_over_t1_to_t2": joint_odd_gap / span_first,
        "erase_odd_rate_over_t1_to_t2_alt": erase_odd_gap / span_first,
        "erase_odd_ratio_to_kappa_entry": (joint_odd_gap / span_first) / predicted,
        "retention_relative_change_t2_to_t3": retention,
        "gap_prediction_over_release": decay_prediction,
        "retention_vs_gap_factor": decay_prediction / max(retention, 1e-300),
        "preflight_A_even": float(receipt["preflight"]["readings"]["A"]["even_norm"]),
        "preflight_A_odd": float(receipt["preflight"]["readings"]["A"]["odd_norm"]),
        "preflight_B_even": float(receipt["preflight"]["readings"]["B"]["even_norm"]),
        "preflight_B_odd": float(receipt["preflight"]["readings"]["B"]["odd_norm"]),
        "coordinate_reference_t3": float(receipt["decision"]["scalar"]["reference"]),
        "coordinate_write_A_t3": float(receipt["decision"]["scalar"]["write_A"]),
        "coordinate_write_B_t3": float(receipt["decision"]["scalar"]["write_B"]),
        "coordinate_joint_t3": float(receipt["decision"]["scalar"]["joint_AB"]),
        "coordinate_erase_t3": float(receipt["decision"]["scalar"]["erase_A"]),
        "reference_ray_distance_final": float(arms["load_reference"]["ray_distance"]),
        "reference_ray_distance_at_t3": float(
            arms["load_reference"]["ray_distance_at"]["t3"]),
        "write_A_ray_distance_at_t3": float(arms["write_A"]["ray_distance_at"]["t3"]),
        "verdicts": dict(receipt["verdicts"]),
        "status": receipt["status"],
        "gates_passed": int(sum(1 for gate in receipt["gates"] if gate["passed"])),
        "gates_total": len(receipt["gates"]),
        "runtime_seconds": float(receipt["runtime_seconds"]),
    }


def classify(measurement_at_point: dict, kernel: dict) -> dict:
    """Apply the branches fixed at the top of this file."""
    measured = 0
    if measurement_at_point["A_t3"] >= ZERO_TOL:
        measured += 1
    with_rho = kernel["with_rho_mode"]
    without_rho = kernel["without_rho_mode"]
    return {
        "measured_retained_coordinates": measured,
        "dim_ker_with_rho_mode": with_rho,
        "dim_ker_without_rho_mode": without_rho,
        "branch": ("equal" if measured == with_rho else
                   ("measured_smaller" if measured < with_rho else "measured_larger")),
        "branch_against_excluded_count": ("equal" if measured == without_rho else
                                          ("measured_smaller" if measured < without_rho
                                           else "measured_larger")),
    }


# Every number the audit prints, pinned. Collected from the first pass of this script
# against the receipt named in RECEIPT_PATH, then checked on every later pass.
LITERALS = {
    "A_odd_t1": 0.0,
    "A_odd_t2": 2.9373740229761033e-16,
    "A_odd_t3": 0.0,
    "A_t1": 0.0035782503187010394,
    "A_t2": 0.0035854949067870424,
    "A_t3": 0.003585494912706732,
    "B_even_t1": 8.054468970674446e-05,
    "B_even_t3": 8.080466456044417e-05,
    "B_odd_t1": 2.9373740229761033e-16,
    "B_odd_t2": 1.4686870114880517e-16,
    "B_odd_t3": 0.0,
    "additive_even_cosine": 1.0,
    "additive_even_relative_gap": 0.022781598592640784,
    "bound_module_sha256": 'd687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1',
    "chain_lb39_gap": 0.013839094166127715,
    "classify_branch": 'equal',
    "classify_branch_excluded": 'measured_larger',
    "coordinate_erase_t3": 0.8917901001114138,
    "coordinate_joint_t3": 0.8917899977049457,
    "coordinate_reference_t3": 0.8923974885141119,
    "coordinate_write_A_t3": 0.8918038559489984,
    "coordinate_write_B_t3": 0.8923841276699156,
    "declared_line_present": True,
    "declared_nu": 0.01119569724312185,
    "declared_nu_ratio": 0.9935585517629607,
    "declared_samples_24_present": True,
    "dim_ker_modes_0_1": 1,
    "dim_ker_modes_0_to_3": 1,
    "dim_ker_without_rho": 0,
    "domain_cosine_docstring_claims_48": True,
    "domain_declared_coordinates": 48,
    "domain_declared_line_present": True,
    "domain_exterior_only_declared_row_spread": 0.0,
    "domain_exterior_only_implemented_row_spread": 0.06938268539288772,
    "domain_group_length": 7,
    "domain_implemented_coordinates": 14,
    "domain_implemented_line_present": True,
    "domain_loop_only_declared_row_spread": 0.07376815905011214,
    "domain_loop_only_implemented_row_spread": 0.0,
    "domain_n_chi": 24,
    "domain_n_x": 7,
    "entry_exchange_seeded": 1.2,
    "entry_kappa_equilibrium": 0.011268281293796237,
    "entry_kappa_seeded": 0.017133744076175704,
    "entry_kappa_seeded_min": 0.013839094166127715,
    "entry_loop_equilibrium": 0.27276406320767016,
    "entry_loop_seeded": 0.27276406320767016,
    "entry_min_equilibrium": 0.011268281293796237,
    "equilibrium_coordinate": 0.8923974885141119,
    "erase_against_joint_relative_gap": 0.00016834098570927907,
    "erase_odd_rate": 0.011334032054212044,
    "erase_odd_rate_ratio": 1.005835030090348,
    "erase_odd_t1": 7.185740297158022e-08,
    "erase_odd_t2": 4.379025443956683e-10,
    "exchange": 0.6,
    "executor_sha256": '3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1',
    "family_increasing": True,
    "fitted_clock": 0.011268281516184584,
    "fitted_clock_minus_entry": 2.2238834732069002e-10,
    "fitted_clock_ratio": 1.0000000197357823,
    "gap_prediction_over_release": 0.9937221428959869,
    "gates_passed": 14,
    "gates_total": 14,
    "generator_gap_mode0": 9.063995872770853e-17,
    "generator_gap_mode1": 0.27276406320766994,
    "joint_loop_dial": 0.47273325502140445,
    "joint_odd_t1": 7.185740297158022e-08,
    "joint_odd_t2": 4.379586482395071e-10,
    "joint_odd_t3": 0.0,
    "kappa_equilibrium": 0.0043041004594355226,
    "kappa_seed": 0.006544507882556952,
    "kappa_seed_identity_residual": -6.071532165918825e-18,
    "lambda": 0.04,
    "loop_diffusion": 0.044982698961937725,
    "loop_diffusion_relation_residual": 0.0,
    "measured_retained_coordinates": 1,
    "mode0_gap": 0.0112682812937962,
    "mode0_kernel_carrier_ratio": (1.6180339887498865-0j),
    "mode0_kernel_direction_asymmetry": 1.845754383899907e-16,
    "mode0_kernel_epsilon_residual": 1.0336224549839478e-14,
    "mode0_zeros": 1,
    "mode1_gap": 0.27276406320767016,
    "mode1_zeros": 0,
    "mode2_gap": 0.7799307958477508,
    "mode3_gap": 1.0048442906574395,
    "omega": 0.4705882352941177,
    "omega_is_v_over_r_residual": 0.0,
    "omega_minus_exchange": -0.12941176470588228,
    "omega_over_exchange": 0.7843137254901962,
    "phi": 1.618033988749895,
    "preflight_A_even": 2.5753540367077486e-06,
    "preflight_A_odd": 6.529026343075532e-07,
    "preflight_B_even": 6.424958490062066e-07,
    "preflight_B_odd": 2.547515185086473e-06,
    "protocol_body_sha256": '09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25',
    "read_t1": 450.0,
    "read_t2": 900.0,
    "read_t3": 1350.0,
    "receipt_sha256": '9724143b98cf394eb9948741d3a117c4cc1e4b14fe54ff2ad9e81dfddb8bf60f',
    "reference_ray_distance_at_t3": 5.297914102411338e-08,
    "reference_ray_distance_final": 5.297914102411338e-08,
    "retention_relative_change": 1.6510104756966052e-09,
    "retention_vs_gap_factor": 601887242.7061428,
    "runtime_seconds": 305.6016502380371,
    "seed_coordinate": 0.8363873029360762,
    "seed_rate_max": 0.007947406903627875,
    "seed_rate_mean": 0.006544507882556958,
    "seed_rate_min": 0.005286063597950403,
    "spectrum_agrees_chain_mode0": 0.0,
    "spectrum_agrees_chain_mode1": 0.0,
    "status": 'PASS',
    "write_law_exponent_present": True,
    "write_law_exponents_recorded": 5,
    "write_protocol_sha256": 'c3f3ca5c230ec4ad45c8e4a85e4cc7c648e44ecf13a3a034ac43a7389b41cc0b',
    "write_law_exponent": 1.0302448806878108,
}


def self_check(values: dict, collect: bool) -> int:
    """Compare every printed number against the literal table."""
    problems = []
    rows = []
    for key in sorted(values):
        observed = values[key]
        if collect:
            rows.append('    "{0}": {1!r},'.format(key, observed))
            continue
        if key not in LITERALS:
            problems.append("unpinned value {0}".format(key))
            continue
        expected = LITERALS[key]
        if isinstance(observed, str) or isinstance(observed, bool):
            if observed != expected:
                problems.append("{0}: expected {1!r}, observed {2!r}".format(
                    key, expected, observed))
        elif isinstance(observed, (int, float)):
            if not math.isclose(float(observed), float(expected), rel_tol=1e-9,
                                abs_tol=1e-15):
                problems.append("{0}: expected {1!r}, observed {2!r}".format(
                    key, expected, observed))
        else:
            if observed != expected:
                problems.append("{0}: expected {1!r}, observed {2!r}".format(
                    key, expected, observed))
    if collect:
        print("\n".join(rows))
        return EXIT_PASS
    if problems:
        print("SELF-CHECK FAILED")
        for problem in problems:
            print("  {0}".format(problem))
        return EXIT_FAIL
    print("self-check: {0} pinned values agree".format(len(LITERALS)))
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true",
                        help="print the literal table instead of checking it")
    options = parser.parse_args(argv)

    body = load_body()
    binding = bind(body)
    base = body.load_modules()
    frozen = base.frozen
    receipt = body.load_json(RECEIPT_PATH)
    phi = float(frozen.PHI)

    print("== binding")
    for key in sorted(binding):
        print("  {0} = {1}".format(key, binding[key]))

    point = declared_point(body, base, receipt)
    origin = point["origin"]
    print("\n== the declared tuple (frozen module, bound by §0; receipt for the coordinates)")
    for key in ("phi", "v", "r", "d_ell", "exchange", "lambda", "omega", "loop_diffusion"):
        item = origin[key] if isinstance(origin.get(key), dict) else {"value": origin[key],
                                                                     "origin": "frozen module"}
        print("  {0:16s} = {1!r:22s}  [{2}]".format(key, item["value"], item["origin"]))
    print("  nx               = {0}   n_chi = {1}".format(origin["nx"], origin["n_chi"]))
    print("  kappa(x) over the seeded state: min {0!r} mean {1!r} max {2!r}".format(
        origin["seed_rate_min"], origin["seed_rate_mean"], origin["seed_rate_max"]))
    print("  kappa_seed     = {0!r}  [LAM (1 - A_seed), A_seed = {1!r}]".format(
        origin["kappa_seed"]["value"], origin["seed_coordinate"]))
    print("  kappa_equilibrium = {0!r}  [A_eq = {1!r}]".format(
        origin["kappa_equilibrium"]["value"], origin["equilibrium_coordinate"]))
    print("  reference ray distance, final = {0!r}".format(origin["ray_distance_final"]))
    checks = relations(point)
    for key in sorted(checks):
        print("  relation {0} = {1!r}".format(key, checks[key]))
    print("  gate_rate through the split executor, max gap = {0!r}".format(
        point["rate_through_split_gap"]))

    print("\n== theorem 6.3's entries and the distance to each boundary")
    table = {}
    for label, kappa in (("seeded", origin["kappa_seed"]["value"]),
                         ("seeded_min_over_x", origin["seed_rate_min"]),
                         ("seeded_max_over_x", origin["seed_rate_max"]),
                         ("equilibrium", origin["kappa_equilibrium"]["value"])):
        at_point = entries(kappa, phi, origin["exchange"]["value"],
                           origin["omega"]["value"], origin["loop_diffusion"]["value"])
        distances = boundary_distances(at_point, kappa, phi, origin["exchange"]["value"],
                                       origin["omega"]["value"],
                                       origin["loop_diffusion"]["value"])
        table[label] = {"kappa": kappa, "entries": at_point, "distances": distances}
        print("  at kappa = {0!r} ({1}):".format(kappa, label))
        print("    entry kappa(1+phi)      = {0!r}".format(at_point["kappa_entry"]))
        print("    entry 2r                = {0!r}".format(at_point["exchange_entry"]))
        print("    entry d + r - Re root   = {0!r}  (root = {1!r}, arg = {2!r})".format(
            at_point["loop_entry"], at_point["root"], at_point["root_argument"]))
        print("    mode 0 loop counterpart = {0!r}".format(at_point["mode0_loop_entry"]))
        print("    min entry (the gap)     = {0!r}".format(distances["min_entry"]))
        print("    dial distances: kappa {0!r}, r {1!r}, (d,omega) {2!r}, omega-r {3!r}".format(
            distances["kappa_dial"], distances["exchange_dial"],
            distances["joint_loop_dial"], distances["omega_minus_exchange"]))
    vanished = [name for name, value in (
        ("kappa", table["equilibrium"]["entries"]["kappa_entry"]),
        ("2r", table["equilibrium"]["entries"]["exchange_entry"]),
        ("d + r - Re root", table["equilibrium"]["entries"]["loop_entry"]),
        ("d", table["equilibrium"]["entries"]["mode0_loop_entry"])) if abs(value) <= ZERO_TOL]
    print("  entries that vanish at the equilibrium point: {0}".format(
        vanished if vanished else "none"))
    print("  chain's own LB39 gap at the seeded point (min over x) = {0!r}".format(
        float(base.internal_gap(point["rate"], origin["exchange"]["value"]))))

    print("\n== dim ker of the frozen mode_generator, two routes")
    kernel = {}
    for label, kappa in (("seeded", origin["kappa_seed"]["value"]),
                         ("equilibrium", origin["kappa_equilibrium"]["value"])):
        block = spectra(body, base, frozen, kappa, phi, origin["exchange"]["value"],
                        origin["omega"]["value"], origin["loop_diffusion"]["value"])
        kernel[label] = block
        print("  at kappa = {0!r} ({1}):".format(kappa, label))
        for mode in (0, 1, 2, 3):
            record = block[mode]
            print("    mode {0}: closed_spectrum {1}".format(mode, [
                (round(value.real, 12), round(value.imag, 12))
                for value in record["spectrum"]]))
            print("      |Re| nonzero {0}  gap {1!r}  slow_rate {2!r}".format(
                [round(abs(value.real), 12) for value in record["spectrum"]],
                record["gap"], record["slow_rate"]))
            print("      zeros {0}  generator nullity {1}  gap via generator {2!r}"
                  "  chain spectrum max gap {3!r}".format(
                      record["zeros"], record["nullity"], record["generator_gap"],
                      record["spectrum_agrees_with_chain"]))
            for vector in record["kernel_vectors"]:
                print("      kernel direction {0}".format(
                    kernel_structure(vector, phi)))
    print("  loop family increasing in m: {0}  (m=1 entry {1!r})".format(
        kernel["equilibrium"]["family_increasing"], kernel["equilibrium"]["family_first"]))
    at_equilibrium = kernel["equilibrium"]
    counts = {
        "with_rho_mode": sum(at_equilibrium[mode]["nullity"] for mode in (0, 1)),
        "without_rho_mode": sum(at_equilibrium[mode]["nullity"] for mode in (1, 2, 3)),
        "modes_0_to_3": sum(at_equilibrium[mode]["nullity"] for mode in (0, 1, 2, 3)),
    }
    print("  dim ker over the declared mode content {{0,1}} = {0}".format(
        counts["with_rho_mode"]))
    print("  dim ker with the total-density mode excluded  = {0}".format(
        counts["without_rho_mode"]))
    print("  mode-0 kernel labels: the carrier ratio phi:1 (epsilon = e_Y - phi e_I = 0, "
          "orientation-symmetric, chi-uniform)")
    for entry, meaning in DEGENERACIES:
        print("    degenerate dial {0}: {1}".format(entry, meaning))
    print("  mode-1 eigenstructure: rates {0!r} against the direction pair "
          "(d + r) -+ Re root".format(
              sorted(round(abs(value.real), 12) for value in at_equilibrium[1]["spectrum"])))

    print("\n== the reading domain the run actually used")
    domain = reading_domain(body, base, point)
    print("  declared line present in the protocol: {0}   implemented line present: {1}"
          .format(domain["declared_line_quoted"], domain["implemented_line_quoted"]))
    print("  §1.2 declares: {0}".format(domain["declared_line_text"]))
    print("  the declared domain indexes 24 loop samples: {0}".format(
        domain["declared_samples_24_quoted"]))
    print("  declared domain: {0} coordinates (2 orientations x {1} loop samples)".format(
        2 * domain["n_chi"], domain["n_chi"]))
    print("  implemented domain: {0} coordinates (2 orientations x {1} exterior points)"
          .format(2 * domain["n_x"], domain["n_x"]))
    for label in ("loop_only", "exterior_only"):
        record = domain[label]
        print("  probe {0}: implemented shape {1} spread {2!r} (row spread {3!r}); "
              "declared shape {4} row spread {5!r}".format(
                  label, record["implemented_shape"], record["implemented_spread"],
                  record["implemented_row_spread"], record["declared_shape"],
                  record["declared_row_spread"]))
    print("  stored group vector length = {0} (nx = {1})".format(domain["group_length"],
                                                               domain["n_x"]))
    print("  the executor's own direction_cosine docstring still claims a 48-vector: {0}"
          .format(domain["cosine_docstring_claims_48"]))
    print("  consequence: the coordinates the receipt holds are chi-uniform in their "
          "chi-dependence, so they can only see the mode-0 sector")

    print("\n== the measurement against the closed form")
    measured = measurement(body, base, receipt, point,
                           table["equilibrium"]["entries"])
    print("  read times: t1 {0!r} t2 {1!r} t3 {2!r}, release samples {3}".format(
        measured["times"]["t1"], measured["times"]["t2"], measured["times"]["t3"],
        [round(value, 3) for value in measured["times"]["release_times"]]))
    print("  fitted clock {0!r} vs kappa(1+phi) at the equilibrium {1!r}".format(
        measured["fitted_clock"], table["equilibrium"]["entries"]["kappa_entry"]))
    print("    difference {0!r}  ratio {1!r}".format(
        measured["fitted_clock_minus_kappa_entry"], measured["fitted_clock_ratio"]))
    print("    declared nu {0!r}  ratio to the entry {1!r}".format(
        measured["declared_nu"], measured["declared_nu_ratio"]))
    print("  retained even group of write_A: t1 {0!r} t2 {1!r} t3 {2!r}".format(
        measured["A_t1"], measured["A_t2"], measured["A_t3"]))
    print("    relative change t2 -> t3 over {0!r} units = {1!r}; the gap would predict a "
          "decay of {2!r} over the release window".format(
              measured["times"]["t3"] - measured["times"]["t2"],
              measured["retention_relative_change_t2_to_t3"],
              measured["gap_prediction_over_release"]))
    print("    retention beats the gap prediction by a factor {0!r}".format(
        measured["retention_vs_gap_factor"]))
    print("  odd groups: write_A {0!r} {1!r} {2!r}, write_B {3!r} {4!r} {5!r}".format(
        measured["A_odd_t1"], measured["A_odd_t2"], measured["A_odd_t3"],
        measured["B_odd_t1"], measured["B_odd_t2"], measured["B_odd_t3"]))
    print("  write_B even group: t1 {0!r} t3 {1!r}".format(measured["B_even_t1"],
                                                           measured["B_even_t3"]))
    print("  joint/erase odd residue: {0!r} then {1!r}; rate over t1->t2 {2!r} "
          "({3!r} x the kappa entry)".format(
              measured["joint_odd_t1"], measured["joint_odd_t2"],
              measured["erase_odd_rate_over_t1_to_t2"],
              measured["erase_odd_ratio_to_kappa_entry"]))
    print("  pre-flight one-step action: A even {0!r} odd {1!r}; B even {2!r} odd {3!r}"
          .format(measured["preflight_A_even"], measured["preflight_A_odd"],
                  measured["preflight_B_even"], measured["preflight_B_odd"]))
    print("  the scalar A at t3: reference {0!r} write_A {1!r} write_B {2!r} joint {3!r} "
          "erase {4!r}".format(measured["coordinate_reference_t3"],
                               measured["coordinate_write_A_t3"],
                               measured["coordinate_write_B_t3"],
                               measured["coordinate_joint_t3"],
                               measured["coordinate_erase_t3"]))
    print("  the reference's own ray distance: at t3 {0!r}, final {1!r} (the load's "
          "epsilon excursion is gone)".format(measured["reference_ray_distance_at_t3"],
                                               measured["reference_ray_distance_final"]))
    print("  the two writes' retained even displacements: cosine {0!r}, relative gap "
          "{1!r}; the erase arm against the joint: {2!r}".format(
              measured["additive_even_cosine"], measured["additive_even_relative_gap"],
              measured["erase_against_joint_relative_gap"]))
    print("    a cosine of 1 is what one conserved coordinate with two injectors looks "
          "like: the additivity is the degeneracy, not a second capacity")
    write_protocol = body.prior.PROTOCOL_PATH
    write_text = open(os.path.join(ROOT, write_protocol), encoding="utf-8").read()
    exponents = []
    for piece in write_text.split("delta_g^{")[1:]:
        if "}" not in piece:
            continue
        head = piece.split("}")[0].lstrip("\\, ")
        try:
            exponents.append(float(head))
        except ValueError:
            continue
    write_law_present = WRITE_LAW_EXPONENT in exponents
    print("  the write body's own recorded offset law: exponent {0!r} among {1} recorded "
          "exponents from {2} (digest {3})".format(
              WRITE_LAW_EXPONENT, len(exponents), write_protocol,
              digest_of(write_protocol)))
    print("  receipt: status {0}, gates {1}/{2}, {3!r} s, verdicts {4}".format(
        measured["status"], measured["gates_passed"], measured["gates_total"],
        measured["runtime_seconds"], measured["verdicts"]))

    print("\n== the classification, against branches fixed before the arithmetic")
    for name, meaning in BRANCHES:
        print("  {0:16s} {1}".format(name, meaning))
    verdict = classify(measured, counts)
    for key in sorted(verdict):
        print("  {0} = {1}".format(key, verdict[key]))
    print("  the measured one is the conserved direction: the composition's sensitivity to "
          "the decaying epsilon direction is proportional to epsilon itself, which the "
          "reference arm drives to {0!r}".format(measured["reference_ray_distance_at_t3"]))
    print("  so the retention of write_A's even group is the conservation law the excluded "
          "mode carries, and the write law's exponent is the response of a conserved "
          "coordinate rather than a capacity")
    print("  the odd class: writable (pre-flight B odd {0!r} against even {1!r}) but "
          "retaining nothing (single-write odd groups at {2!r} and {3!r})".format(
              measured["preflight_B_odd"], measured["preflight_B_even"],
              measured["A_odd_t3"], measured["B_odd_t3"]))

    values = {
        "phi": phi,
        "exchange": origin["exchange"]["value"],
        "omega": origin["omega"]["value"],
        "loop_diffusion": origin["loop_diffusion"]["value"],
        "lambda": origin["lambda"]["value"],
        "kappa_seed": origin["kappa_seed"]["value"],
        "kappa_equilibrium": origin["kappa_equilibrium"]["value"],
        "seed_rate_min": origin["seed_rate_min"],
        "seed_rate_mean": origin["seed_rate_mean"],
        "seed_rate_max": origin["seed_rate_max"],
        "seed_coordinate": origin["seed_coordinate"],
        "equilibrium_coordinate": origin["equilibrium_coordinate"],
        "reference_ray_distance_final": origin["ray_distance_final"],
        "omega_is_v_over_r_residual": checks["omega_is_v_over_r"],
        "loop_diffusion_relation_residual": checks["loop_diffusion_is_d_ell_over_r_squared"],
        "kappa_seed_identity_residual": checks["kappa_seed_is_seed_rate_mean"],
        "omega_over_exchange": checks["ratio_omega_over_exchange"],
        "entry_kappa_seeded": table["seeded"]["entries"]["kappa_entry"],
        "entry_exchange_seeded": table["seeded"]["entries"]["exchange_entry"],
        "entry_loop_seeded": table["seeded"]["entries"]["loop_entry"],
        "entry_kappa_seeded_min": table["seeded_min_over_x"]["entries"]["kappa_entry"],
        "entry_kappa_equilibrium": table["equilibrium"]["entries"]["kappa_entry"],
        "entry_loop_equilibrium": table["equilibrium"]["entries"]["loop_entry"],
        "entry_min_equilibrium": table["equilibrium"]["distances"]["min_entry"],
        "omega_minus_exchange": table["equilibrium"]["distances"]["omega_minus_exchange"],
        "joint_loop_dial": table["equilibrium"]["distances"]["joint_loop_dial"],
        "chain_lb39_gap": float(base.internal_gap(point["rate"],
                                                  origin["exchange"]["value"])),
        "dim_ker_modes_0_1": counts["with_rho_mode"],
        "dim_ker_without_rho": counts["without_rho_mode"],
        "dim_ker_modes_0_to_3": counts["modes_0_to_3"],
        "mode0_zeros": at_equilibrium[0]["zeros"],
        "mode0_gap": at_equilibrium[0]["gap"],
        "mode1_zeros": at_equilibrium[1]["zeros"],
        "mode1_gap": at_equilibrium[1]["gap"],
        "mode2_gap": at_equilibrium[2]["gap"],
        "mode3_gap": at_equilibrium[3]["gap"],
        "family_increasing": at_equilibrium["family_increasing"],
        "mode0_kernel_carrier_ratio": kernel_structure(
            at_equilibrium[0]["kernel_vectors"][0], phi)["carrier_ratio"],
        "mode0_kernel_epsilon_residual": kernel_structure(
            at_equilibrium[0]["kernel_vectors"][0], phi)["epsilon_of_direction_pair"],
        "mode0_kernel_direction_asymmetry": kernel_structure(
            at_equilibrium[0]["kernel_vectors"][0], phi)["direction_asymmetry_y"],
        "spectrum_agrees_chain_mode0": at_equilibrium[0]["spectrum_agrees_with_chain"],
        "spectrum_agrees_chain_mode1": at_equilibrium[1]["spectrum_agrees_with_chain"],
        "generator_gap_mode0": at_equilibrium[0]["generator_gap"],
        "generator_gap_mode1": at_equilibrium[1]["generator_gap"],
        "domain_declared_coordinates": 2 * domain["n_chi"],
        "domain_implemented_coordinates": 2 * domain["n_x"],
        "domain_group_length": domain["group_length"],
        "domain_n_x": domain["n_x"],
        "domain_n_chi": domain["n_chi"],
        "domain_loop_only_implemented_row_spread": domain["loop_only"][
            "implemented_row_spread"],
        "domain_loop_only_declared_row_spread": domain["loop_only"]["declared_row_spread"],
        "domain_exterior_only_implemented_row_spread": domain["exterior_only"][
            "implemented_row_spread"],
        "domain_exterior_only_declared_row_spread": domain["exterior_only"][
            "declared_row_spread"],
        "domain_declared_line_present": domain["declared_line_quoted"],
        "domain_implemented_line_present": domain["implemented_line_quoted"],
        "domain_cosine_docstring_claims_48": domain["cosine_docstring_claims_48"],
        "read_t1": measured["times"]["t1"],
        "read_t2": measured["times"]["t2"],
        "read_t3": measured["times"]["t3"],
        "write_law_exponent": WRITE_LAW_EXPONENT if write_law_present else 0.0,
        "write_law_exponent_present": write_law_present,
        "write_law_exponents_recorded": len(exponents),
        "write_protocol_sha256": digest_of(write_protocol),
        "additive_even_relative_gap": measured["additive_even_relative_gap"],
        "additive_even_cosine": measured["additive_even_cosine"],
        "erase_against_joint_relative_gap": measured["erase_against_joint_relative_gap"],
        "declared_line_present": domain["declared_line_quoted"],
        "declared_samples_24_present": domain["declared_samples_24_quoted"],
        "fitted_clock": measured["fitted_clock"],
        "fitted_clock_minus_entry": measured["fitted_clock_minus_kappa_entry"],
        "fitted_clock_ratio": measured["fitted_clock_ratio"],
        "declared_nu": measured["declared_nu"],
        "declared_nu_ratio": measured["declared_nu_ratio"],
        "A_t1": measured["A_t1"],
        "A_t2": measured["A_t2"],
        "A_t3": measured["A_t3"],
        "A_odd_t1": measured["A_odd_t1"],
        "A_odd_t2": measured["A_odd_t2"],
        "A_odd_t3": measured["A_odd_t3"],
        "B_even_t1": measured["B_even_t1"],
        "B_even_t3": measured["B_even_t3"],
        "B_odd_t1": measured["B_odd_t1"],
        "B_odd_t2": measured["B_odd_t2"],
        "B_odd_t3": measured["B_odd_t3"],
        "joint_odd_t1": measured["joint_odd_t1"],
        "joint_odd_t2": measured["joint_odd_t2"],
        "joint_odd_t3": measured["joint_odd_t3"],
        "erase_odd_t1": measured["erase_odd_t1"],
        "erase_odd_t2": measured["erase_odd_t2"],
        "erase_odd_rate": measured["erase_odd_rate_over_t1_to_t2"],
        "erase_odd_rate_ratio": measured["erase_odd_ratio_to_kappa_entry"],
        "retention_relative_change": measured["retention_relative_change_t2_to_t3"],
        "gap_prediction_over_release": measured["gap_prediction_over_release"],
        "retention_vs_gap_factor": measured["retention_vs_gap_factor"],
        "preflight_A_even": measured["preflight_A_even"],
        "preflight_A_odd": measured["preflight_A_odd"],
        "preflight_B_even": measured["preflight_B_even"],
        "preflight_B_odd": measured["preflight_B_odd"],
        "coordinate_reference_t3": measured["coordinate_reference_t3"],
        "coordinate_write_A_t3": measured["coordinate_write_A_t3"],
        "coordinate_write_B_t3": measured["coordinate_write_B_t3"],
        "coordinate_joint_t3": measured["coordinate_joint_t3"],
        "coordinate_erase_t3": measured["coordinate_erase_t3"],
        "reference_ray_distance_at_t3": measured["reference_ray_distance_at_t3"],
        "status": measured["status"],
        "gates_passed": measured["gates_passed"],
        "gates_total": measured["gates_total"],
        "runtime_seconds": measured["runtime_seconds"],
        "measured_retained_coordinates": verdict["measured_retained_coordinates"],
        "classify_branch": verdict["branch"],
        "classify_branch_excluded": verdict["branch_against_excluded_count"],
        "protocol_body_sha256": binding["protocol_body_sha256"],
        "executor_sha256": binding["executor_sha256"],
        "bound_module_sha256": binding["bound_module_sha256"],
        "receipt_sha256": binding["receipt_sha256"],
    }
    print("\n== self-check")
    return self_check(values, options.collect)


if __name__ == "__main__":
    raise SystemExit(main())
