"""Verify the frozen passive compact phase-current selection protocol."""

from __future__ import annotations

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0
G = 1.0
ETA = 0.05
NOTCH = 0.05
CHECK_EVERY = 100
ENERGY_TOL = 1.0e-10
RATIO_TOL = 0.02
SEEDS = ((1, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 13))
ARMS = (("primary", 64, 0.02, 30_000), ("resolution", 96, 0.01, 60_000))
TARGETS = (("phi", PHI), ("three_halves", 1.5), ("sqrt2", math.sqrt(2.0)))
TAU = 2.0 * math.pi


def wrap(angle: float) -> float:
    return (angle + math.pi) % TAU - math.pi


def winding(values: list[complex]) -> int:
    count = len(values)
    total = sum(
        wrap(
            math.atan2(values[(index + 1) % count].imag, values[(index + 1) % count].real)
            - math.atan2(values[index].imag, values[index].real)
        )
        for index in range(count)
    )
    return round(total / TAU)


def energy(yang: list[complex], yin: list[complex]) -> float:
    count = len(yang)
    total = 0.0
    for index in range(count):
        next_index = (index + 1) % count
        total += abs(yang[next_index] - yang[index]) ** 2
        total += abs(yin[next_index] - yin[index]) ** 2
        total += 0.5 * G * (abs(yang[index]) ** 2 - 1.0) ** 2
        total += 0.5 * G * (abs(yin[index]) ** 2 - 1.0) ** 2
        total += ETA * abs(yang[index] - yin[index]) ** 2
    return total


def initial_field(count: int, winding_number: int) -> list[complex]:
    return [
        (NOTCH if index == 0 else 1.0)
        * complex(
            math.cos(TAU * winding_number * index / count),
            math.sin(TAU * winding_number * index / count),
        )
        for index in range(count)
    ]


def evolve(count: int, dt: float, steps: int, p: int, q: int) -> dict[str, float | int | bool | None]:
    yang = initial_field(count, p)
    yin = initial_field(count, -q)
    initial_energy = energy(yang, yin)
    sampled_energy = initial_energy
    maximum_rise = 0.0
    minimum_amplitude = NOTCH

    for step in range(steps):
        next_yang: list[complex] = []
        next_yin: list[complex] = []
        for index in range(count):
            previous_index = (index - 1) % count
            next_index = (index + 1) % count
            laplacian_yang = yang[previous_index] + yang[next_index] - 2.0 * yang[index]
            laplacian_yin = yin[previous_index] + yin[next_index] - 2.0 * yin[index]
            next_yang.append(
                yang[index]
                + dt
                * (
                    laplacian_yang
                    + G * (1.0 - abs(yang[index]) ** 2) * yang[index]
                    + ETA * (yin[index] - yang[index])
                )
            )
            next_yin.append(
                yin[index]
                + dt
                * (
                    laplacian_yin
                    + G * (1.0 - abs(yin[index]) ** 2) * yin[index]
                    + ETA * (yang[index] - yin[index])
                )
            )
        yang, yin = next_yang, next_yin
        minimum_amplitude = min(
            minimum_amplitude,
            min(abs(value) for value in yang),
            min(abs(value) for value in yin),
        )
        if (step + 1) % CHECK_EVERY == 0:
            current_energy = energy(yang, yin)
            maximum_rise = max(maximum_rise, current_energy - sampled_energy)
            sampled_energy = current_energy

    final_yang = winding(yang)
    final_yin = winding(yin)
    counterflow = final_yang * final_yin < 0
    ratio = abs(final_yin / final_yang) if counterflow else None
    return {
        "initial_energy": initial_energy,
        "final_energy": energy(yang, yin),
        "maximum_rise": maximum_rise,
        "minimum_amplitude": minimum_amplitude,
        "yang_winding": final_yang,
        "yin_winding": final_yin,
        "counterflow": counterflow,
        "ratio": ratio,
    }


def target_hits(records: list[dict[str, float | int | bool | None]], target: float) -> int:
    return sum(
        bool(record["counterflow"])
        and abs(float(record["ratio"]) - target) <= RATIO_TOL
        for record in records
    )


def main() -> int:
    arm_records: list[tuple[str, list[dict[str, float | int | bool | None]]]] = []
    for name, count, dt, steps in ARMS:
        records = [evolve(count, dt, steps, p, q) for p, q in SEEDS]
        arm_records.append((name, records))

    passive_descent = all(
        float(record["final_energy"]) < float(record["initial_energy"])
        and float(record["maximum_rise"]) <= ENERGY_TOL
        for _, records in arm_records
        for record in records
    )
    hit_counts = {
        name: {target_name: target_hits(records, target) for target_name, target in TARGETS}
        for name, records in arm_records
    }
    phi_selected = all(
        hits["phi"] >= 2
        and hits["phi"] > hits["three_halves"]
        and hits["phi"] > hits["sqrt2"]
        for hits in hit_counts.values()
    )
    phi_absent = all(hits["phi"] == 0 for hits in hit_counts.values())

    if not passive_descent:
        verdict = "FAIL"
    elif phi_selected:
        verdict = "ADOPT"
    elif phi_absent:
        verdict = "REJECT"
    else:
        verdict = "NULL"

    print("Passive compact phase-current selection")
    for (name, count, dt, steps), (_, records) in zip(ARMS, arm_records, strict=True):
        print(f"{name}: N={count} dt={dt:g} steps={steps} T={dt * steps:g}")
        for (p, q), record in zip(SEEDS, records, strict=True):
            ratio = record["ratio"]
            ratio_text = "none" if ratio is None else f"{float(ratio):.6f}"
            orientation = "counter" if record["counterflow"] else "co-or-zero"
            print(
                f"  seed=({p},{q}) H0={float(record['initial_energy']):.6f} "
                f"HT={float(record['final_energy']):.6f} "
                f"w=({int(record['yang_winding'])},{int(record['yin_winding'])}) "
                f"orientation={orientation} ratio={ratio_text} "
                f"min_amp={float(record['minimum_amplitude']):.3e} "
                f"max_rise={float(record['maximum_rise']):.3e}"
            )
        hits = hit_counts[name]
        print(
            f"  hits: phi={hits['phi']} three_halves={hits['three_halves']} "
            f"sqrt2={hits['sqrt2']}"
        )
    print(f"PS1 sampled passive descent: {'PASS' if passive_descent else 'FAIL'}")
    print(f"PS2 emergent phi selection: {'PASS' if phi_selected else 'FAIL'}")
    print(f"VERDICT: {verdict}")
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
