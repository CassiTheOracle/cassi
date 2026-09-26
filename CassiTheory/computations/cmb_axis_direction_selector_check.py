"""CMB axis DIRECTION-selector check: is the observed axis direction—and the
12.22 deg dipole<->axis separation that the phi-magnitude is matched to—
selected by the bubble lattice, or is it degenerate with the solar-system
(ecliptic) frame?

Audit context (registry C10):
  magnitude: 12.40 deg = 2*pi/phi^7  (Derived -- golden-angle closure residual;
             foundations/wake-geometry.md sec 3b; the companion check
             computations/cmb_axis_closure_check.py verifies the identity
             13/phi^2 = 5 - 1/phi^7 and the 1.5% match to 12.22 deg).
  direction: quadrupole-octopole axis (l,b) = (260 deg, +60 deg), CMB dipole
             (264 deg, +48 deg) -- Calibrated from the measured direction
             vectors (cosmology/observational_constraints.md sec 4;
             two-fluid/run_cmb_lowl_pipeline.py).  No framework selector is
             documented for the direction: the boundary normal is fitted to
             the measured axis (post-hoc), and the internal->physical axis
             map (foundations/why-three-dimensions.md) resolves the *identity*
             of the Yang/Yin/string axes but not their absolute orientation.

Candidates tested here (a direction selector must pin 2 sky degrees of
freedom; the bubble lattice currently pins 0):
  A. Ecliptic-plane degeneracy of the "measured" 12.22 deg separation.
     The quadrupole-octopole axis is famous for lying near the ecliptic
     plane; the CMB dipole is the kinematic (peculiar-velocity) direction.
     If both vectors sit near the ecliptic plane, the mutual separation is
     dominated by their out-of-plane components -- i.e. the 12.22 deg datum
     inherits the solar-system frame.  Quantify the decomposition.
  B. Yang-Yin plane consistency: if dipole = Yang axis and axis = boundary
     normal both lie in the bubble's doublet (Yang-Yin) plane, the string
     axis is the cross product of the two measured directions.  Report the
     implied string-axis direction and its distance from notable frames --
     for the record: the framework does not predict the string-axis
     orientation, so this cannot select the direction a priori.
  C. The residual of the phi-magnitude against the ecliptic-degenerate
     component, i.e. what the match is worth once the direction is
     (possibly) a solar-system artifact.

Run:  python computations/cmb_axis_direction_selector_check.py
"""

import math

PHI = (1 + 5 ** 0.5) / 2

# Documented vectors (cosmology/observational_constraints.md sec 4.1;
# two-fluid/run_cmb_lowl_pipeline.py):
L_DIPOLE, B_DIPOLE = 264.0, 48.0      # CMB kinematic dipole (solar motion)
L_AXIS,   B_AXIS   = 260.0, 60.0      # quadrupole-octopole axis ("axis of evil")
MEASURED_SEP_DEG = 12.22              # documented value (data vectors)

# J2000 ecliptic north pole in galactic coordinates (degrees):
L_ECL_POLE, B_ECL_POLE = 96.337, 29.811
# J2000 vernal equinox (RA 0, Dec 0) in galactic coordinates (degrees):
L_EQUINOX, B_EQUINOX = 266.405, -28.936


def cart(l_deg, b_deg):
    """Unit vector in galactic coordinates."""
    l = math.radians(l_deg)
    b = math.radians(b_deg)
    return (math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b))


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def cross(u, v):
    return (u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0])


def norm(u):
    return math.sqrt(dot(u, u))


def angle_deg(u, v):
    c = dot(u, v) / (norm(u) * norm(v))
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def to_gal(v):
    """Unit vector -> galactic (l, b) in degrees (b in [-90, 90])."""
    x, y, z = v
    r = math.sqrt(x * x + y * y)
    l = math.degrees(math.atan2(y, x)) % 360.0
    b = math.degrees(math.atan2(z, r))
    return l, b


def main():
    print("=" * 78)
    print("CMB axis DIRECTION-selector check: who picks (260 deg, +60 deg)?")
    print("=" * 78)

    d = cart(L_DIPOLE, B_DIPOLE)   # dipole (Yang-axis candidate)
    a = cart(L_AXIS, B_AXIS)       # quadrupole-octopole axis (boundary normal)
    p = cart(L_ECL_POLE, B_ECL_POLE)   # ecliptic north pole
    q = cart(L_EQUINOX, B_EQUINOX)     # vernal equinox

    print("\n-- 1. The measured datum: dipole<->axis separation --")
    sep = angle_deg(d, a)
    print(f"  vectors: dipole ({L_DIPOLE:.0f}°, {B_DIPOLE:.0f}°),"
          f" axis ({L_AXIS:.0f}°, {B_AXIS:.0f}°)")
    print(f"  spherical-law separation = {sep:.3f} deg"
          f"  (documented 12.22 deg; 2*pi/phi^7 = {math.degrees(2*math.pi/PHI**7):.4f} deg)")
    print(f"  residual vs closure = {(math.degrees(2*math.pi/PHI**7)-sep)/sep:+.3%}"
          f"  (documented {((math.degrees(2*math.pi/PHI**7)-MEASURED_SEP_DEG)/MEASURED_SEP_DEG):+.3%})")

    print("\n-- 2. Candidate A: ecliptic-plane degeneracy of the datum --")
    print(f"  ecliptic north pole (gal): ({L_ECL_POLE:.3f}°, {B_ECL_POLE:.3f}°)")
    ang_axis_pole = angle_deg(a, p)
    ang_dip_pole = angle_deg(d, p)
    b_ecl_axis = 90.0 - ang_axis_pole
    b_ecl_dip = 90.0 - ang_dip_pole
    print(f"  angle(axis, ecliptic pole)   = {ang_axis_pole:.2f} deg"
          f"  -> ecliptic latitude {b_ecl_axis:+.2f} deg"
          f"  (|b| < 1 deg: the axis lies IN the ecliptic plane)")
    print(f"  angle(dipole, ecliptic pole) = {ang_dip_pole:.2f} deg"
          f"  -> ecliptic latitude {b_ecl_dip:+.2f} deg"
          f"  (11-12 deg out of the plane)")
    # In-plane (ecliptic longitude) and out-of-plane (latitude) decomposition.
    # Project both vectors onto the ecliptic plane and compare angles.
    d_in = (d[0] - dot(d, p) * p[0], d[1] - dot(d, p) * p[1], d[2] - dot(d, p) * p[2])
    a_in = (a[0] - dot(a, p) * a[0], a[1] - dot(a, p) * a[1], a[2] - dot(a, p) * a[2])
    dl_inplane = angle_deg(d_in, a_in)          # ~ ecliptic longitude difference
    db_outplane = abs(b_ecl_dip - b_ecl_axis)   # ecliptic latitude difference
    print(f"  decomposition of the {sep:.2f} deg separation:")
    print(f"    in-plane (ecliptic-longitude) component  = {dl_inplane:.2f} deg")
    print(f"    out-of-plane (ecliptic-latitude) comp.   = {db_outplane:.2f} deg"
          f"  (dominates: {(db_outplane/sep)*100:.1f}% of the datum)")
    # Cross-check with spherical Pythagoras on the small patch.
    approx = math.degrees(math.hypot(
        math.radians(dl_inplane) * math.cos(math.radians((b_ecl_dip + b_ecl_axis) / 2)),
        math.radians(db_outplane)))
    print(f"    sqrt[(dl*cos b)^2 + db^2] = {approx:.2f} deg (self-check vs {sep:.2f} deg)")
    print(f"\n  Reading: the 'measured' 12.22 deg is almost entirely the dipole's")
    print(f"  height above the ecliptic plane given the axis sits ~in the plane.")
    print(f"  The axis-of-evil ecliptic alignment is the documented large-angle")
    print(f"  anomaly (Schwarz+ 2004, Land & Magueijo 2005); if it is a solar-")
    print(f"  system/foreground selection, the 12.22 deg target itself is a")
    print(f"  foreground-frame artifact and the 12.40 deg closure matches it.")
    print(f"\n  Null test of the ecliptic-pinned alternative: if the boundary normal")
    print(f"  were exactly in the ecliptic plane (its observed placement), the")
    print(f"  dipole<->axis separation would equal |dipole ecliptic latitude| =")
    print(f"  {abs(b_ecl_dip):.2f} deg -- {(abs(b_ecl_dip)/math.degrees(2*math.pi/PHI**7)-1):+.1%}"
          f" from the closure value and {(abs(b_ecl_dip)/MEASURED_SEP_DEG-1):+.1%} from the datum.")
    print(f"  The ecliptic geometry alone reproduces the separation at ~7-8%")

    print("\n-- 3. Candidate B: Yang-Yin plane consistency (implied string axis) --")
    n = cross(d, a)
    n = (n[0] / norm(n), n[1] / norm(n), n[2] / norm(n))
    l_n, b_n = to_gal(n)
    print(f"  implied string axis  n = d x a / |d x a| = ({l_n:.1f}°, {b_n:+.1f}°)"
          f"  (or the antipode)")
    print(f"  angle to ecliptic pole: {angle_deg(n, p):.1f} deg"
          f"  | galactic pole (0, 90): {angle_deg(n, cart(0, 90)):.1f} deg"
          f"  | Virgo (283.8, +74.5): {angle_deg(n, cart(283.8, 74.5)):.1f} deg"
          f"  | cold spot (208, -57): {angle_deg(n, cart(208.0, -57.0)):.1f} deg")
    print(f"  equinox-projected: angle(implied string axis, equinox) = {angle_deg(n, q):.1f} deg")
    print(f"  Reading: the Yang-Yin-plane hypothesis is a consistency statement,")
    print(f"  not a selector -- the framework does not predict n's orientation,")

    print("\n-- 4. Candidate C: what a genuine selector must pin --")
    print(f"  Direction = 2 free sky parameters; framework pins 0.")
    print(f"  Available framework directions: Yang axis (a bubble-interior axis),")
    print(f"  string axis (cascade direction), boundary normal (nearest-boundary")
    print(f"  direction, set by the observer's offset from the bubble centre).")
    print(f"  The PDE is rotation-invariant: the absolute orientation of these")
    print(f"  axes is set by the primordial string's initial orientation, which")
    print(f"  is a calibration, not a derivation; the Milky Way's position inside")
    print(f"  the rung-285 bubble (191 Mpc) is likewise a calibration input.")
    print(f"  The 12.40 deg magnitude is an azimuthal closure residual in the")
    print(f"  pole-spiral plane; its projection onto the sky separation is not")
    print(f"  derived (foundations/wake-geometry.md sec 3b; registry C10).")

    print("\n-- 5. Verdict summary --")
    print(f"  magnitude: 12.40 deg = 2*pi/phi^7 (Derived; {MEASURED_SEP_DEG:.2f} deg datum,"
          f" vector-recomputed {sep:.2f} deg, 1.3-1.5% match)")
    print(f"  direction: no bubble-lattice selector exists; the observed")
    print(f"  placement is degenerate with the ecliptic frame (axis 0.8 deg off the")
    print(f"  plane; dipole 11.4 deg off; separation ~= dipole's ecliptic height)")
    print(f"  -> the 12.22 deg target inherits the solar-system frame, so the")
    print(f"  phi-magnitude match is entangled with the foreground question.")
    print(f"  Selector required for closure: an a priori orientation of the")
    print(f"  bubble's Frenet-Serret frame in the sky frame (rotation-invariance")
    print(f"  breaking), plus exclusion of the ecliptic/foreground selection.")


if __name__ == "__main__":
    main()
