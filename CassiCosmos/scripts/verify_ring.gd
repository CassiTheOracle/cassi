extends Node
## Ring-roundness verification for the two-fluid wave front (Field mode).
##
## The user reports "the expansion ring becomes a square as it expands."
## The ring is the two-fluid wave front; ρ = EY+EI obeys the plain discrete
## wave equation (the φ-coupling cancels in ρ), and the squareness is the
## 7-point Laplacian's dispersion anisotropy: the fixed-brightness front is
## a rounded square, the corner-to-face gap growing linearly with radius.
##
## The 19-point isotropic stencil (axes 1/3, face-diagonals 1/6, center −4)
## removes the anisotropy (O(h⁶)). The shipped fix is in
## compute/cassi_two_fluid.glsl (lap_ey_at / lap_ei_at).
##
## This test measures the stencil's DISPERSION ANISOTROPY directly, on the
## sim's own PDE, with the sim's own shader:
##   - grid-periodic discrete plane waves (ψ = cos(2π·m·x/N) along [100] and
##     ψ = cos(2π·m·(x+y)/N) along [110]) are EXACT eigenfunctions of both
##     stencils — the m's are chosen so |k| matches within 1% (m=20 axis,
##     m=14 diagonal — deep in the dispersive regime where the squareness
##     lives, wavelength ≈ 3.2 cells);
##   - set EY = ψ, EI = ψ/φ so the ω₀²·(EY−φ·EI) coupling cancels exactly,
##     and the single-step acceleration equals the pure stencil action:
##     vel.x = dt·∇²ψ = −dt·symbol(k)·ψ;
##   - read symbol(k) along [100] and [110] from the velocity buffer and
##     require symbol[110]/symbol[100] ∈ [0.985, 1.015].
## The 7-point stencil measures 1.164 here (16% anisotropy); the 19-point
## measures 1.008 (its O(k⁶) residual is 0.8% — the check fails before the
## fix and passes after).
##
## Earlier attempts measured wave-front contour radii of q/ρ driven by the
## sim's hardcoded gaussian source (σ≈11.3 cells — the blob swamps the
## ring; q is Π-speckled; the transient ringing crests are not a clean
## discriminator) — all verified to read identically for both stencils.
## The plane-wave test is deterministic and unambiguous.
##
## Run: godot --path <repo> res://scenes/verify_ring.tscn

const N: int = 64
const TWO_PI: float = 6.28318530717958647693
const PHI: float = 1.618033988749895
# Periodic plane-wave modes on the 64³ grid (the discrete cosines must be
# grid-periodic or the wrap in idx3 breaks the eigenfunction property):
#   [100]: m=20  -> k = 2π·20/64 ≈ 1.9635 rad/cell (20 turns around the box)
#   [110]: m=14  -> k = 2π·14·√2/64 ≈ 1.9443 rad/cell (|k| within 1% of [100])
# Exact stencil symbols at these k (evaluated from the stencil sums):
#   19-point: s100 = 2(1−cos k) = 2.765367, s110 = 3 − (8/3)cos a − (1/3)cos 2a
#             = 2.787719  -> ratio = 1.0081  (PASS: O(k⁶) residual 0.8%)
#   7-point : s100 = 2.765367, s110 = 4(1−cos a) = 3.219639 -> ratio = 1.1643
#             (FAIL: 16% dispersion anisotropy — the rounded-square front)
const N_MODE_AXIS: int = 20
const N_MODE_DIAG: int = 14
const PROBE: int = 0          # probe cell (0, 0, 0): ψ = cos(0) = 1
const TOL: float = 0.015      # symbol[110]/symbol[100] must be within ±1.5%

var sim: Node3D
var _failures: int = 0
var _checks: int = 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("verify_ring: CassiSim not found in scene")
		get_tree().quit(1)
		return
	# PIN the grid stencil battery against the campaign defaults
	# (meshless/tree/φ-aspect/dual now default on): the dispersion
	# anisotropy gate runs the CUBE single-lattice two-fluid PDE.
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	sim.playing = false
	sim.gravity_mode = 0
	sim.mode = 1
	sim.source_strength = 0.0  # no source: the acceleration is pure stencil
	sim.dt = 0.01
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 300:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("verify_ring: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_ring: shaders ready after %d extra frames" % waited)
	sim.reinit()  # re-materialize the cube grid / single-lattice / meshless-off state
	sim.playing = false
	# Zero both particle masses — no mass-coupling source (rho = 0)
	var pos = PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	sim._rd.buffer_update(sim._pos_buf, 0, 32, pos.to_byte_array())
	_run()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


# Set EY = cos(k·x) (mode dir), EI = EY/φ (coupling cancels), zero vel/q.
func _set_plane_wave(mode100: bool) -> void:
	var k := TWO_PI * float(N_MODE_AXIS) / float(N)
	var ey = PackedFloat32Array()
	ey.resize(N * N * N)
	var ei = PackedFloat32Array()
	ei.resize(N * N * N)
	for kk in range(N):
		for j in range(N):
			for i in range(N):
				var ph: float
				if mode100:
					ph = k * float(i)
				else:
					# [110] mode m=14: phase = 2π·14·(i+j)/64 — periodic on grid
					ph = TWO_PI * float(N_MODE_DIAG) * float(i + j) / float(N)
				var v: float = cos(ph)
				var id := i + N * (j + N * kk)
				ey[id] = v
				ei[id] = v / PHI
	sim._rd.buffer_update(sim._field_ey, 0, N * N * N * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, N * N * N * 4, ei.to_byte_array())
	var zero = PackedFloat32Array()
	zero.resize(N * N * N * 4)
	sim._rd.buffer_update(sim._field_vel, 0, N * N * N * 16, zero.to_byte_array())


# Measure −symbol(k) = lap(ψ)/ψ = vel.x/(dt·ψ) at the probe cell.
func _measure_symbol() -> float:
	sim._physics_step()
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._field_vel, PROBE * 16, 16)
	var v = d.to_float32_array()
	return -v[0] / sim.dt  # ψ(probe) = cos(0) = 1


func _run() -> void:
	print("══════ verify_ring — N=%d, plane wave [100] n=%d (k=%.4f), [110] n=%d (k=%.4f) ══════" % [
		N, N_MODE_AXIS, TWO_PI * float(N_MODE_AXIS) / float(N),
		N_MODE_DIAG, TWO_PI * float(N_MODE_DIAG) * sqrt(2.0) / float(N)])
	_set_plane_wave(true)
	var s100 := _measure_symbol()
	_set_plane_wave(false)
	var s110 := _measure_symbol()
	var ratio := s110 / s100
	print("  symbol[100] = %.6f   symbol[110] = %.6f   ratio = %.4f" % [s100, s110, ratio])
	_check("ring: symbol[110]/symbol[100] ∈ [%.3f, %.3f] (7-point measured ~1.16)" % [1.0 - TOL, 1.0 + TOL],
		absf(ratio - 1.0) <= TOL, "ratio=%.4f" % ratio)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])
