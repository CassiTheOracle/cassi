"""CMB axis-magnitude check: is 12.40 deg = 2*pi/phi^7 the golden-angle closure residual?

Verifies the magnitude relation adopted in
`cosmology/observational_constraints.md` section 4 and
`speculations/observational-seti.md` section 4.2:

    measured dipole<->quadrupole separation   12.22 deg
    predicted magnitude 2*pi/phi^7 = 12.399 deg
         = the 13-seed closure residual of the golden-angle spiral
           (foundations/wake-geometry.md section 3b)

Run:  python computations/cmb_axis_closure_check.py
"""

import math

PHI = (1 + 5 ** 0.5) / 2


def deg(x):
    return math.degrees(x)


def main():
    print("=" * 78)
    print("CMB axis magnitude: golden-angle closure 2*pi/phi^7 vs measured 12.22 deg")
    print("=" * 78)

    print("\n-- 1. The closure ladder (foundations/wake-geometry.md sec 3b) --")
    ga = 2 * math.pi / PHI ** 2            # the golden angle, 137.5 deg
    print(f"  golden angle 2*pi/phi^2 = {deg(ga):.4f} deg")
    for k in (5, 13, 34, 89, 233, 610):
        r = (k * ga) % (2 * math.pi)
        r = min(r, 2 * math.pi - r)       # minimal angular return residual
        print(f"  {k:3d} seeds -> residual {deg(r):6.3f} deg")

    print("\n-- 2. The candidate magnitude 2*pi/phi^7 --")
    print(f"  phi^7 = {PHI ** 7:.6f}")
    print(f"  360/phi^7   = {360 / PHI ** 7:.6f} deg")
    print(f"  2*pi/phi^7  = {deg(2 * math.pi / PHI ** 7):.6f} deg")
    print(f"  neighbors: 2*pi/phi^6 = {deg(2 * math.pi / PHI ** 6):.3f} deg,"
          f"  2*pi/phi^8 = {deg(2 * math.pi / PHI ** 8):.3f} deg"
          f"  (the only phi-power near 12.2 deg is k = 7)")

    print("\n-- 3. Exact identity: 13 seeds = 5 turns - 2*pi/phi^7 --")
    r13 = 13 * ga % (2 * math.pi)
    r13 = min(r13, 2 * math.pi - r13)
    print(f"  13-seed residual = {deg(r13):.10f} deg")
    print(f"  2*pi/phi^7       = {deg(2 * math.pi / PHI ** 7):.10f} deg")
    print(f"  |difference|     = {abs(r13 - 2 * math.pi / PHI ** 7):.2e} rad (machine zero)")
    print(f"  algebra: 13/phi^2 - (5 - 1/phi^7) = {13 / PHI ** 2 - (5 - 1 / PHI ** 7):.2e}"
          f"  (exact: 1/phi^7 = 13*phi - 21)")

    print("\n-- 4. Measured separation (documented direction vectors) --")
    l1, b1 = math.radians(264), math.radians(48)    # CMB dipole
    l2, b2 = math.radians(260), math.radians(60)    # quadrupole-octopole axis
    cos_t = (math.sin(b1) * math.sin(b2)
             + math.cos(b1) * math.cos(b2) * math.cos(l1 - l2))
    theta = math.acos(max(-1.0, min(1.0, cos_t)))
    print(f"  spherical law of cosines: {deg(theta):.4f} deg")
    print(f"  pipeline value (two-fluid/run_cmb_lowl_pipeline.py): 12.22 deg")

    print("\n-- 5. Residual vs 12.22 deg --")
    pred = 2 * math.pi / PHI ** 7
    meas_1222 = math.radians(12.22)
    print(f"  (2*pi/phi^7 - 12.22)/12.22 = {(pred - meas_1222) / meas_1222:+.4f}"
          f"  ({abs((pred - meas_1222) / meas_1222) * 100:.2f}%)")
    print(f"  (2*pi/phi^7 - vectors)/vectors = {(pred - theta) / theta:+.4f}"
          f"  ({abs((pred - theta) / theta) * 100:.2f}%)")

    print("\n-- 6. Rung-difference readings (computed, for the record) --")
    print(f"  291.5 - 285 = 6.5 half-rungs: 360/phi^6.5 = {360 / PHI ** 6.5:.2f} deg"
          f"  -> does not yield the angle")
    print(f"  292 - 285 = 7 rungs: phi^7 is the power in the angle, but the geometric")
    print(f"  reading is the closure ladder's 13-seed level, which equals 2*pi/phi^7")
    print(f"  exactly (sec 3): the '7th power' and '13-seed' readings are the same")
    print(f"  number to all digits.")


if __name__ == "__main__":
    main()
