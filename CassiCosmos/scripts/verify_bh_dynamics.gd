extends Node3D
## Stage-1 verification of the BH FIELD CHANNEL (BH_DYNAMICS_PLAN.md §1):
## the BH sector as a field SOURCE (its mass enters the particles' own
## fixed-point deposit) and a TEST BODY (its motion mirrors the particle
## arm's cached-acc KDK and samples the same ∇(g·Φ) through the shared
## include).
##
## Gates, plant discipline, bounds and the decision tree are PRE-REGISTERED
## before this file ever ran — read research/bh_dynamics/BH_DYNAMICS_PREREG.md
## first; the bounds here are the pre-registration's, never a post-hoc number.
## Every bound is derived there from the source (fixed-point arithmetic, the
## deposit's per-cell clamp, fp32 rounding, the KDK's own algebra).
##
## Configuration (pre-registered): grid 64, cube half-extent 37.5, dt 0.02,
## river mode 0, dual lattice ON, freeze_field (the PDE is out of scope),
## a UNIFORM asymmetric field EY = 0.6 / EI = 0.5 so π/ρ is a known constant
## everywhere, BH records planted at M = 200 (below the deposit's 606.81
## per-cell clamp ceiling), test particles planted MASS-0 so they are
## integrated but deposit nothing (that is what makes BH3 an exact claim).
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   <console exe> --path . res://scenes/verify_bh_dynamics.tscn
## Receipt: res://_diag/bh_dynamics/bh_dynamics_receipt.json

const GRID_N := 64            # box = cube, half-extent cluster_radius·1.5 = 37.5
const DT := 0.02
const M_BH := 200.0           # planted BH mass (< the 606.8148 deposit ceiling)
const D_SEP := 4.0            # each BH of the pair sits at ±D_SEP on x
const EY0 := 0.6              # uniform asymmetric field: π/ρ = 0.1/1.1
const EI0 := 0.5
const ACC_R := 0.5            # accretion radius (world units)
const STEPS_PARITY := 64      # BH3b/BH5: steps after the initial one

# Pre-registered bounds (BH_DYNAMICS_PREREG.md §2). Do not widen these after a
# run: a FAIL is a deliverable, and a bound may only change if its DERIVATION
# in the pre-registration was wrong.
const TOL_LEDGER := 1.0e-5     # Σρ/M — partition-of-unity rounding, ≤ ~2.4e-7
const RHO_700 := 660.6875      # BH1c: 700 − clamp loss 39.3125 (exact prediction)
const TOL_RHO_700 := 0.007     # 27 contributions × ½ count + convert rounding
const TOL_MOMENTUM := 1.0e-3   # V vs Σm·v/M_total (one division + atomic order)
const TOL_REACTION := 1.0e-4   # |Δv0+Δv1|/|Δv0| — FFT asymmetry headroom
const TOL_SELF := 1.0e-3       # |Δv_self|/|Δv_mutual| — estimate ~3.4e-6
const TOL_SLOPE := 0.05        # BH5b: |Δsep| vs |Δv|·dt over the first step
const ULP_REL := 2.3841858e-7  # 2^-22 — the PASS(1ULP) investigation ceiling

var _rd: RenderingDevice = null
var _checks := 0
var _failures := 0
var _t0 := 0
var _eng = null
var _receipt := {"probe": "verify_bh_dynamics", "prereg": "research/bh_dynamics/BH_DYNAMICS_PREREG.md", "gates": [], "measurements": {}}


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("BH0 local RD acquired", false, "no RD — run windowed, not --headless")
		_finish()
		return
	_check("BH0 local RD acquired", true)
	_arm_ledger()      # BH1: source ledger + the deposit clamp ceiling
	_arm_momentum()    # BH2: conserved mass AND momentum transfer
	_arm_parity()      # BH3/BH4/BH5: the test-body claim, self-force, pair motion
	_arm_off()         # BH6: default-off bit-identity
	_arm_predicate()   # BH6g: host predicate
	_finish()


# ── Arming ──────────────────────────────────────────────────────────────────

## BH1: a BH-only engine (N_particles = 0) still converts its mass into ρ, on
## the base lattice and on the dual lattice; the ledger is exact below the
## deposit's per-cell clamp and loses exactly the predicted amount above it.
func _arm_ledger() -> void:
	_eng = _make_engine(true, false, 0, false, false)
	if _eng == null:
		return
	# Prerequisite diagnostic (not a gate): the convert pass is gated on the
	# particle deposit set, which at N_particles = 0 exists only because the
	# engine allocates maxi(N,1)-sized particle buffers. A BH-only run with no
	# convert has no ρ at all — if this is false, the ledger gates below fail
	# for that reason and this line names it.
	var convert_set_ok: bool = _eng._us_mass_dep_0.is_valid()
	_receipt["measurements"]["bh1_convert_set_at_n0"] = convert_set_ok
	print("[VerifyBHDyn] N=0 deposit set valid=%s (convert gate)" % convert_set_ok)
	# (a) two records, 200 + 100.
	_eng.plant_bh(0, Vector3.ZERO, 200.0)
	_eng.plant_bh(1, Vector3(D_SEP, 0.0, 0.0), 100.0)
	_eng.run_steps(1)
	var rho_a := _read_rho_sum(_eng)
	_check("BH1a BH-only: Σρ == Σ planted mass (200 + 100)",
		absf(rho_a / 300.0 - 1.0) <= TOL_LEDGER,
		"Σρ=%.5f ratio=%.8f" % [rho_a, rho_a / 300.0])
	_check("BH1f live channel writes the analytic term OFF (bh[3].x = 0)",
		_read_header_float(_eng, 48) == 0.0, "float48=%.1f" % _read_header_float(_eng, 48))
	# (b) one record at 600 — below the 606.8148 ceiling.
	_eng.plant_bh(1, Vector3(D_SEP, 0.0, 0.0), 0.0)
	_eng.plant_bh(0, Vector3.ZERO, 600.0)
	_eng.run_steps(1)
	var rho_b := _read_rho_sum(_eng)
	_check("BH1b single M = 600 (below the 606.8148 ceiling): Σρ == M",
		absf(rho_b / 600.0 - 1.0) <= TOL_LEDGER,
		"Σρ=%.5f ratio=%.8f" % [rho_b, rho_b / 600.0])
	# (c) one record at 700 — above it: the centre cell clamps at 2^32−256.
	_eng.plant_bh(0, Vector3.ZERO, 700.0)
	_eng.run_steps(1)
	var rho_c := _read_rho_sum(_eng)
	_check("BH1c M = 700 clamps exactly as predicted (Σρ == 660.6875)",
		absf(rho_c - RHO_700) <= TOL_RHO_700,
		"Σρ=%.5f expected=%.5f (loss %.5f = the clamped 0.75³ cell)" % [rho_c, RHO_700, 700.0 - rho_c])
	_receipt["measurements"]["bh1_ratio_300"] = rho_a / 300.0
	_receipt["measurements"]["bh1_ratio_600"] = rho_b / 600.0
	_receipt["measurements"]["bh1_rho_700"] = rho_c
	_receipt["measurements"]["bh1_clamp_ceiling"] = 4294967040.0 / (0.421875 * 16777216.0)
	_eng.shutdown(); _eng = null
	# (d) dual lattice: the same mass must arrive on the shifted chain too.
	_eng = _make_engine(true, false, 0, false, true)
	if _eng == null:
		return
	_eng.plant_bh(0, Vector3.ZERO, 200.0)
	_eng.run_steps(1)
	var rho_d := _read_rho_sum(_eng)
	_check("BH1e dual lattice: the shifted chain carries the BH mass as well",
		absf(rho_d / 200.0 - 1.0) <= TOL_LEDGER,
		"Σρ=%.5f ratio=%.8f" % [rho_d, rho_d / 200.0])
	_receipt["measurements"]["bh1_ratio_dual"] = rho_d / 200.0
	_eng.shutdown(); _eng = null


## BH2: a swallow delivers mass AND momentum. The cloud is mirror-symmetric
## about the centred BH, so its own field gradient at the BH is a rounding
## residual and the velocity check isolates the transfer.
func _arm_momentum() -> void:
	_eng = _make_engine(true, true, 8, false, true)
	if _eng == null:
		return
	var masses := PackedFloat32Array([1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0])
	var xs := PackedFloat32Array([0.05, -0.05, 0.10, -0.10, 0.15, -0.15, 0.20, -0.20])
	var pos := PackedFloat32Array()
	var vel := PackedFloat32Array()
	var sum_m := 0.0
	var sum_p := Vector3.ZERO
	for i in range(8):
		pos.append_array(PackedFloat32Array([xs[i], 0.0, 0.0, masses[i]]))
		var vi := Vector3(0.1 * float(i + 1), 0.0, 0.3)
		vel.append_array(PackedFloat32Array([vi.x, vi.y, vi.z, 0.0]))
		sum_m += masses[i]
		sum_p += vi * masses[i]
	_plant_particles(_eng, pos, vel)
	_eng.plant_bh(0, Vector3.ZERO, M_BH)
	_eng.run_steps(1)
	var bh := _read_bh(_eng, 0)
	var v := Vector3(bh[4], bh[5], bh[6])
	var expected := sum_p / (M_BH + sum_m)
	_check("BH2a swallow ledger: BH mass == M + Σm (200 + 20)",
		absf(bh[3] - (M_BH + sum_m)) <= 1.0e-4,
		"mass=%.5f expected=%.5f" % [bh[3], M_BH + sum_m])
	var rel := (v - expected).length() / maxf(expected.length(), 1.0e-12)
	_check("BH2b momentum transfer: V == Σm·v / M_total",
		rel <= TOL_MOMENTUM,
		"V=(%.8f,%.8f,%.8f) expected=(%.8f,%.8f,%.8f) rel=%s" % [
			v.x, v.y, v.z, expected.x, expected.y, expected.z, _sci(rel)])
	# BH2e (BH_DYNAMICS_PREREG.md §3b): the same plant with accretion OFF gives
	# the BH's own field kick for this exact configuration, so the transfer is
	# isolated by subtraction rather than assumed away. The deposit for the
	# swallow step was built BEFORE the swallow in both runs, so both BHs sample
	# the same field.
	var ctrl = _make_engine(true, false, 8, false, true)
	if ctrl != null:
		var cpos := PackedFloat32Array()
		var cvel := PackedFloat32Array()
		for i in range(8):
			cpos.append_array(PackedFloat32Array([xs[i], 0.0, 0.0, masses[i]]))
			var vi := Vector3(0.1 * float(i + 1), 0.0, 0.3)
			cvel.append_array(PackedFloat32Array([vi.x, vi.y, vi.z, 0.0]))
		_plant_particles(ctrl, cpos, cvel)
		ctrl.plant_bh(0, Vector3.ZERO, M_BH)
		ctrl.run_steps(1)
		var cb := _read_bh(ctrl, 0)
		var kick := Vector3(cb[4], cb[5], cb[6])
		var transferred := v - kick
		# The book is handed the swallow-instant velocities, which the control
		# run measures directly: same plant, same deposit, one step, particles
		# alive. Build the expected impulse from THOSE, over the final mass.
		var cweights := _read_posw(ctrl, 8)
		var cvels := _read_vel(ctrl, 8)
		var sum_pm := Vector3.ZERO
		var sum_mm := 0.0
		for i in range(8):
			var vi := Vector3(cvels[i * 4], cvels[i * 4 + 1], cvels[i * 4 + 2])
			sum_pm += vi * cweights[i]
			sum_mm += cweights[i]
		var expected_meas := sum_pm / (M_BH + sum_mm)
		var rel_xfer := (transferred - expected_meas).length() / maxf(expected_meas.length(), 1.0e-12)
		_receipt["measurements"]["bh2e_expected_planted"] = [expected.x, expected.y, expected.z]
		_receipt["measurements"]["bh2e_expected_measured"] = [
			expected_meas.x, expected_meas.y, expected_meas.z]
		_check("BH2e transfer isolated against the same-config field kick",
			rel_xfer <= TOL_MOMENTUM,
			"V−kick=(%.8f,%.8f,%.8f) expected(measured)=(%.8f,%.8f,%.8f) rel=%s kick=(%s,%s,%s)" % [
				transferred.x, transferred.y, transferred.z,
				expected_meas.x, expected_meas.y, expected_meas.z,
				_sci(rel_xfer), _sci(kick.x), _sci(kick.y), _sci(kick.z)])
		_receipt["measurements"]["bh2e_kick"] = [kick.x, kick.y, kick.z]
		_receipt["measurements"]["bh2e_transfer_rel"] = rel_xfer
		# Which input carries the 2.1e-3? The control's particles SURVIVE, so
		# their post-step velocities vs the planted ones separate "the buffer
		# was rescaled" from "the book lost weight".
		var cv := _read_vel(ctrl, 8)
		_receipt["measurements"]["bh2e_ctrl_vel_ratio"] = [
			cv[0] / 0.1, cv[12 + 2] / 0.3, _read_posw(ctrl, 8)[0]]
		var sv := _read_vel(_eng, 8)
		_receipt["measurements"]["bh2e_dead_vel_ratio"] = [
			sv[0] / 0.1, sv[2] / 0.3, sv[28 + 0] / 0.8, sv[28 + 2] / 0.3]
		ctrl.shutdown()
	else:
		_check("BH2e transfer isolated against the same-config field kick", false, "control engine failed")

	var book := _read_dyn(_eng, 0)
	_check("BH2c the pending book is left at exactly zero",
		book == Vector4.ZERO, "book=%s" % str(book))
	var dead := _read_posw(_eng, 8)
	var all_dead := true
	for w in dead:
		if w != 0.0:
			all_dead = false
	_check("BH2d every swallowed particle is marked dead (pos.w = 0)", all_dead, "pos.w=%s" % str(dead))
	_receipt["measurements"]["bh2_velocity_rel"] = rel
	_receipt["measurements"]["bh2_velocity"] = [v.x, v.y, v.z]
	_eng.shutdown(); _eng = null


## BH3/BH5: two equal BHs with a MASS-0 test particle co-located with each.
## The BH and the particle must follow the same trajectory to the last bit;
## the pair must close monotonically, and the first step's Δsep must match
## the independently measured Δv·dt.
func _arm_parity() -> void:
	_eng = _make_engine(true, false, 2, false, true)
	if _eng == null:
		return
	_plant_particles(_eng,
		PackedFloat32Array([-D_SEP, 0.0, 0.0, 0.0, D_SEP, 0.0, 0.0, 0.0]),
		PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
	_eng.plant_bh(0, Vector3(-D_SEP, 0.0, 0.0), M_BH)
	_eng.plant_bh(1, Vector3(D_SEP, 0.0, 0.0), M_BH)
	var sep0 := _separation(_eng)
	_eng.run_steps(1)
	var vel := _read_vel(_eng, 2)
	var bh0 := _read_bh(_eng, 0)
	var bh1 := _read_bh(_eng, 1)
	var dv_test0 := Vector3(vel[0], vel[1], vel[2])
	var dv_test1 := Vector3(vel[4], vel[5], vel[6])
	var dv_bh0 := Vector3(bh0[4], bh0[5], bh0[6])
	var dv_bh1 := Vector3(bh1[4], bh1[5], bh1[6])
	var parity0 := (dv_bh0 - dv_test0).length()
	var parity1 := (dv_bh1 - dv_test1).length()
	var ref0 := maxf(dv_test0.length(), 1.0e-30)
	var ref1 := maxf(dv_test1.length(), 1.0e-30)
	var v0 := _parity_verdict(parity0, ref0)
	var v1 := _parity_verdict(parity1, ref1)
	_check("BH3a step-1 law parity: BH Δv == massless-test Δv [%s]" % v0[1],
		v0[0], "|Δv_BH − Δv_test|=%s rel=%s (|Δv|=%s)" % [_sci(parity0), _sci(parity0 / ref0), _sci(dv_test0.length())])
	_check("BH3a step-1 law parity: BH Δv == massless-test Δv [%s]" % v1[1],
		v1[0], "|Δv_BH − Δv_test|=%s rel=%s (|Δv|=%s)" % [_sci(parity1), _sci(parity1 / ref1), _sci(dv_test1.length())])
	_check("BH3e attraction: each BH is kicked toward the other",
		dv_bh0.x > 0.0 and dv_bh1.x < 0.0,
		"Δv0.x=%s Δv1.x=%s" % [_sci(dv_bh0.x), _sci(dv_bh1.x)])
	var react := (dv_bh0 + dv_bh1).length() / maxf(dv_bh0.length(), 1.0e-12)
	_check("BH3f equal masses kick equal and opposite",
		react <= TOL_REACTION, "|Δv0+Δv1|/|Δv0|=%s" % _sci(react))
	var sep1 := _separation(_eng)
	var pred := dv_bh0.length() * DT
	_check("BH5b the position change matches the independently measured kick",
		absf((sep0 - sep1) - pred) <= TOL_SLOPE * pred,
		"Δsep=%s predicted=|Δv|·dt=%s rel=%s" % [_sci(sep0 - sep1), _sci(pred), _sci(absf((sep0 - sep1) - pred) / pred)])
	_receipt["measurements"]["bh3_parity_step1"] = [parity0, parity1]
	_receipt["measurements"]["bh3_reaction_rel"] = react
	_receipt["measurements"]["bh3_kick"] = dv_bh0.length()
	# The common (non-action-reaction) component of the pair's kicks — the
	# observable of the deposit's reflection asymmetry (BH_DYNAMICS_PREREG §3b).
	_receipt["measurements"]["bh3_common_component"] = (dv_bh0 + dv_bh1) * 0.5
	# ── BH3g: the BH must sample the ACTIVE field role ─────────────────────
	# The two-fluid pp chain flips _field_role_b, so the finalize's set 0 has
	# to follow _active_nbody_field_set() the way the particle arm's does. The
	# A-role kick above is nonzero, which is what makes this arm non-vacuous:
	# with the pp role selected and its buffers unwritten (zero field here),
	# a finalize still reading the base role would return the A kick while the
	# particle gets zero.
	var rr = _make_engine(true, false, 2, false, true)
	if rr != null:
		_plant_particles(rr,
			PackedFloat32Array([-D_SEP, 0.0, 0.0, 0.0, D_SEP, 0.0, 0.0, 0.0]),
			PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
		rr.plant_bh(0, Vector3(-D_SEP, 0.0, 0.0), M_BH)
		rr.plant_bh(1, Vector3(D_SEP, 0.0, 0.0), M_BH)
		rr._field_role_b = true
		rr.run_steps(1)
		var rvel := _read_vel(rr, 2)
		var rbh0 := _read_bh(rr, 0)
		var rk_bh := Vector3(rbh0[4], rbh0[5], rbh0[6])
		var rk_test := Vector3(rvel[0], rvel[1], rvel[2])
		var rpar := (rk_bh - rk_test).length()
		var role_effective := (rk_bh - dv_bh0).length() > 0.0
		_check("BH3g field-role B: the BH samples the ACTIVE role",
			rpar == 0.0 and role_effective,
			"|Δv_BH−Δv_test|=%s |Δv_B|=%s vs |Δv_A|=%s (role took effect=%s)" % [
				_sci(rpar), _sci(rk_bh.length()), _sci(dv_bh0.length()), str(role_effective)])
		_receipt["measurements"]["bh3g_role_b_parity"] = rpar
		_receipt["measurements"]["bh3g_role_b_kick"] = rk_bh.length()
		rr.shutdown()
	else:
		_check("BH3g field-role B: the BH samples the ACTIVE role", false, "engine failed")
	# ── Continue: BH3b/BH3c over 64 steps, BH5a monotonicity ────────────────
	var seps := [sep0, sep1]
	for i in range(STEPS_PARITY - 1):
		_eng.run_steps(1)
		seps.append(_separation(_eng))
	vel = _read_vel(_eng, 2)
	bh0 = _read_bh(_eng, 0)
	bh1 = _read_bh(_eng, 1)
	var ppos := _read_pos(_eng, 2)
	var dp0 := absf(bh0[0] - ppos[0]) + absf(bh0[1] - ppos[1]) + absf(bh0[2] - ppos[2])
	var dp1 := absf(bh1[0] - ppos[4]) + absf(bh1[1] - ppos[5]) + absf(bh1[2] - ppos[6])
	var dv0 := Vector3(bh0[4] - vel[0], bh0[5] - vel[1], bh0[6] - vel[2]).length()
	var dv1 := Vector3(bh1[4] - vel[4], bh1[5] - vel[5], bh1[6] - vel[6]).length()
	var p0ref := maxf(absf(bh0[0]), absf(bh0[1])) + maxf(absf(bh0[2]), 1.0)
	var q0 := _parity_verdict(dv0, maxf(Vector3(vel[0], vel[1], vel[2]).length(), 1.0e-30),
		parity0 / ref0)
	var q1 := _parity_verdict(dv1, maxf(Vector3(vel[4], vel[5], vel[6]).length(), 1.0e-30),
		parity1 / ref1)
	_check("BH3b 64-step law parity: BH velocity == test velocity [%s]" % q1[1],
		q1[0], "|Δv|=%s rel=%s (step-1 rel=%s)" % [_sci(dv1), _sci(dv1 / maxf(Vector3(vel[4], vel[5], vel[6]).length(), 1.0e-30)), _sci(parity1 / ref1)])
	_check("BH3b 64-step law parity: BH velocity == test velocity [%s]" % q0[1],
		q0[0], "|Δv|=%s rel=%s (step-1 rel=%s)" % [_sci(dv0), _sci(dv0 / maxf(Vector3(vel[0], vel[1], vel[2]).length(), 1.0e-30)), _sci(parity0 / ref0)])
	# Position parity: exact, else the 1-ULP class scaled by the accumulated
	# step count (a 1-ulp velocity difference integrates to ≤ k·2^-22·|v|·dt,
	# far below this in world units; the floor keeps it a world-unit statement
	# rather than a ratio against a small displacement).
	var pbound := ULP_REL * float(STEPS_PARITY) * maxf(p0ref, 1.0)
	var pos_exact := dp0 == 0.0 and dp1 == 0.0
	var pos_ok := pos_exact or (dp0 <= pbound and dp1 <= pbound)
	_check("BH3c 64-step trajectory parity: BH position == test position [%s]"
		% ("exact" if pos_exact else "1ULP"),
		pos_ok, "|Δp|_0=%s |Δp|_1=%s bound=%s" % [_sci(dp0), _sci(dp1), _sci(pbound)])
	var monotone := true
	for i in range(1, seps.size()):
		if seps[i] > seps[i - 1] + 1.0e-9:
			monotone = false
	_check("BH5a the pair closes monotonically through the field",
		monotone and seps[-1] < seps[0],
		"sep: %.5f → %.5f (min %.5f) over %d steps" % [seps[0], seps[-1], _minv(seps), seps.size() - 1])
	_receipt["measurements"]["bh3_parity_64"] = [dv0, dv1]
	_receipt["measurements"]["bh3_pos_parity_64"] = [dp0, dp1]
	_receipt["measurements"]["bh5_separation"] = [seps[0], seps[1], seps[-1]]
	_receipt["measurements"]["bh5_min"] = _minv(seps)
	_eng.shutdown(); _eng = null

	# ── BH4: the self-force at the grid-symmetric centre ────────────────────
	_eng = _make_engine(true, false, 0, false, true)
	if _eng == null:
		return
	_eng.plant_bh(0, Vector3.ZERO, M_BH)
	_eng.run_steps(1)
	var solo := _read_bh(_eng, 0)
	var dv_self := Vector3(solo[4], solo[5], solo[6]).length()
	var frac := dv_self / maxf(dv_bh0.length(), 1.0e-30)
	_check("BH4 self-force bound: a centred BH's own well barely moves it",
		frac <= TOL_SELF,
		"|Δv_self|=%s = %s × |Δv_mutual at 4.0| (%s)" % [_sci(dv_self), _sci(frac), _sci(dv_bh0.length())])
	_receipt["measurements"]["bh4_self"] = dv_self
	_receipt["measurements"]["bh4_self_over_mutual"] = frac
	_eng.shutdown(); _eng = null


## BH6: with the channel off, the legacy path is untouched: no deposit, no new
## pipeline/set, no new write, the record carried unchanged except the legacy
## integrate's own age counter.
func _arm_off() -> void:
	_eng = _make_engine(false, false, 0, false, true)
	if _eng == null:
		return
	_eng.plant_bh(0, Vector3.ZERO, M_BH, Vector3.ZERO, 5.0)
	var planted := _read_bh(_eng, 0)
	_eng.run_steps(1)
	var after := _read_bh(_eng, 0)
	var rho := _read_rho_sum(_eng)
	var analytic := _read_header_float(_eng, 48)
	var bits_same := true
	for i in range(3):
		if planted[i] != after[i]:
			bits_same = false
	for i in range(4, 7):
		if planted[i] != after[i]:
			bits_same = false
	if planted[3] != after[3]:
		bits_same = false
	_check("BH6a channel OFF: nothing is deposited (Σρ == 0 exactly)",
		rho == 0.0, "Σρ=%.8f" % rho)
	_check("BH6b channel OFF: the analytic point term is written ON (bh[3].x = 1)",
		analytic == 1.0, "float48=%.1f" % analytic)
	_check("BH6c channel OFF: pos/mass/vel bit-identical to the plant",
		bits_same, "planted=%s after=%s" % [str(planted), str(after)])
	_check("BH6d channel OFF: the legacy integrate still runs (age += 1)",
		after[7] == 6.0, "age=%.3f (planted 5.0 + 1 step; the dispatch is one workgroup, see the grid arm's 2.6 note)" % after[7])
	_check("BH6e channel OFF: the field-channel shaders are never loaded",
		not _eng._bh_dep_shader.is_valid() and not _eng._bh_fin_shader.is_valid() \
			and not _eng._bh_dep_pipe.is_valid() and not _eng._us_bh_dep_0.is_valid() \
			and not _eng._bh_fin_pipe.is_valid() and not _eng._us_bh_fin_0_a.is_valid() \
			and not _eng._us_bh_fin_0_b.is_valid() and not _eng._us_bh_fin_1.is_valid(),
		"dep_shader=%s fin_shader=%s dep_pipe=%s dep_set=%s fin_pipe=%s fin_set0a=%s fin_set0b=%s fin_set1=%s" % [
			_eng._bh_dep_shader.is_valid(), _eng._bh_fin_shader.is_valid(),
			_eng._bh_dep_pipe.is_valid(), _eng._us_bh_dep_0.is_valid(),
			_eng._bh_fin_pipe.is_valid(), _eng._us_bh_fin_0_a.is_valid(),
			_eng._us_bh_fin_0_b.is_valid(), _eng._us_bh_fin_1.is_valid()])
	var dyn_zero := _read_all_zero(_eng._bh_dyn_buf, 15 * 16)
	var acc_zero := _read_all_zero(_eng._bh_acc_buf, 15 * 16)
	_check("BH6f channel OFF: the momentum book and the BH acc cache are never written",
		dyn_zero and acc_zero, "dyn_zero=%s acc_zero=%s" % [dyn_zero, acc_zero])
	_eng.shutdown(); _eng = null


## BH6g: the live predicate is host state — no GPU run needed.
func _arm_predicate() -> void:
	_eng = _make_engine(true, false, 0, false, false)
	if _eng == null:
		return
	var cases := [
		{"mode": 2, "meshless": false, "why": "analytic Plummer mode"},
		{"mode": 1, "meshless": false, "why": "heuristic mode"},
		{"mode": 5, "meshless": false, "why": "tree-river mode"},
	]
	var ok := true
	var detail := ""
	for c in cases:
		_eng.gravity_mode = int(c["mode"])
		var live: bool = _eng.bh_field_channel_live()
		if live:
			ok = false
		detail += "mode=%d → live=%s (%s); " % [c["mode"], live, c["why"]]
	_eng.gravity_mode = 0
	_eng.meshless_mode = true
	_eng.meshless_gravity = true
	if _eng.bh_field_channel_live():
		ok = false
		detail += "meshless tree → live=true (unexpected); "
	_eng.meshless_mode = false
	_eng.meshless_gravity = false
	_eng.gridless_physics = true
	if _eng.bh_field_channel_live():
		ok = false
		detail += "gridless site chain → live=true (unexpected); "
	_eng.gridless_physics = false
	if not _eng.bh_field_channel_live():
		ok = false
		detail += "mode=0 grid → live=false (unexpected); "
	_check("BH6g the channel is inert outside the grid river chain", ok, detail)
	_eng.shutdown(); _eng = null


# ── Engine plumbing ─────────────────────────────────────────────────────────

func _make_engine(fc: bool, accretion: bool, npart: int, own_rd: bool, dual: bool):
	var eng = load("res://scripts/cassi_physics_engine.gd").new()
	var cfg := {
		"rd": _rd, "rd_global": false, "owns_rd": own_rd,
		"grid_N": GRID_N, "N_particles": npart, "dt": DT,
		"cluster_radius": 25.0, "box_aspect": Vector3(1.0, 1.0, 1.0),
		"freeze_field": true, "gravity_mode": 0, "source_strength": 0.0,
		"black_holes_enabled": true, "bh_field_channel": fc,
		"dual_grid": dual, "meshless_mode": false, "meshless_gravity": false,
		"particle_merge": false,
		"bh_accretion": accretion, "bh_accretion_radius": ACC_R,
		"bh_acc_rate": 0.0, "bh_max_age": 0.0,
		"qi_condensation_threshold": 1.0e6,
		"initial_radius_fraction": 0.9,
	}
	if not eng.setup(cfg):
		_check("engine setup (fc=%s acc=%s np=%d dual=%s)" % [fc, accretion, npart, dual],
			false, "setup() returned false")
		return null
	_plant_field(eng)
	return eng


## Uniform asymmetric field: π/ρ is a known constant everywhere, so the force
## comes from the planted masses alone and BH3 compares like with like.
func _plant_field(eng) -> void:
	var f := PackedFloat32Array()
	f.resize(GRID_N * GRID_N * GRID_N)
	f.fill(EY0)
	_rd.buffer_update(eng._field_ey, 0, f.size() * 4, f.to_byte_array())
	f.fill(EI0)
	_rd.buffer_update(eng._field_ei, 0, f.size() * 4, f.to_byte_array())


func _plant_particles(eng, pos: PackedFloat32Array, vel: PackedFloat32Array) -> void:
	_rd.buffer_update(eng._pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(eng._vel_buf, 0, vel.size() * 4, vel.to_byte_array())


# ── Readbacks ───────────────────────────────────────────────────────────────

## BH record slot → [pos.x, pos.y, pos.z, mass, vel.x, vel.y, vel.z, age].
func _read_bh(eng, slot: int) -> Array:
	var f := _rd.buffer_get_data(eng._bh_buf, 64 + slot * 32, 32).to_float32_array()
	if f.size() < 8:
		return [0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0]
	return [f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7]]


func _read_dyn(eng, slot: int) -> Vector4:
	var f := _rd.buffer_get_data(eng._bh_dyn_buf, slot * 16, 16).to_float32_array()
	if f.size() < 4:
		return Vector4(-1.0, 0.0, 0.0, 0.0)
	return Vector4(f[0], f[1], f[2], f[3])


func _read_vel(eng, n: int) -> PackedFloat32Array:
	return _rd.buffer_get_data(eng._vel_buf, 0, n * 16).to_float32_array()


## Particle positions (vec4 each: xyz + mass) — the BH3c trajectory statistic
## compares LIKE with LIKE; run 2 compared these against the velocity buffer.
func _read_pos(eng, n: int) -> PackedFloat32Array:
	return _rd.buffer_get_data(eng._pos_buf, 0, n * 16).to_float32_array()


func _read_posw(eng, n: int) -> PackedFloat32Array:
	var raw := _rd.buffer_get_data(eng._pos_buf, 0, n * 16).to_float32_array()
	var w := PackedFloat32Array()
	for i in range(n):
		w.append(raw[i * 4 + 3])
	return w


func _read_header_float(eng, byte_off: int) -> float:
	var f := _rd.buffer_get_data(eng._bh_buf, byte_off, 4).to_float32_array()
	return f[0] if f.size() >= 1 else -999.0


func _read_rho_sum(eng) -> float:
	var rh := _rd.buffer_get_data(eng._mass_density_buf, 0, GRID_N * GRID_N * GRID_N * 4).to_float32_array()
	var tot := 0.0
	for v in rh:
		tot += v
	return tot


func _read_all_zero(rid: RID, nbytes: int) -> bool:
	var f := _rd.buffer_get_data(rid, 0, nbytes).to_float32_array()
	for v in f:
		if v != 0.0:
			return false
	return true


func _separation(eng) -> float:
	var a := _read_bh(eng, 0)
	var b := _read_bh(eng, 1)
	return Vector3(a[0] - b[0], a[1] - b[1], a[2] - b[2]).length()


func _minv(a: Array) -> float:
	var m: float = a[0]
	for v in a:
		if float(v) < m:
			m = float(v)
	return m


## The pre-registered BH3 decision tree (BH_DYNAMICS_PREREG.md §2/BH3):
##   residual exactly 0.0                    → PASS (the claim)
##   ≤ 2^-22 relative, bounded growth        → PASS(1ULP) — a compiler
##     contraction artifact: same magnitude at every step, never growing
##   larger, or growing super-linearly       → FAIL (the sampler or the
##     integrator differs, which is exactly what this gate exists to catch)
## `prev_rel` is the step-1 relative residual when classifying a later step
## (default -1 = this IS the first measurement, no growth comparison).
func _parity_verdict(res: float, ref: float, prev_rel := -1.0) -> Array:
	var rel := res / maxf(ref, 1.0e-30)
	if res == 0.0:
		return [true, "exact"]
	if rel > ULP_REL:
		return [false, "FAIL rel=%s > 2^-22" % _sci(rel)]
	if prev_rel > 0.0 and rel > maxf(4.0 * prev_rel, ULP_REL):
		return [false, "FAIL growth: rel=%s vs step-1 %s" % [_sci(rel), _sci(prev_rel)]]
	return [true, "1ULP rel=%s" % _sci(rel)]


# ── Reporting ───────────────────────────────────────────────────────────────

## GDScript's % operator has NO %e specifier: an unsupported conversion does
## not raise, it returns the raw template, so every measured number in the
## message (and in the receipt's gate rows) silently reads as "%.3e". All
## scientific-notation output goes through here instead.
func _sci(x: float) -> String:
	return String.num_scientific(x)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	_receipt["gates"].append({"name": name, "pass": ok, "detail": detail})
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _eng != null:
		_eng.shutdown(); _eng = null
	if _rd != null:
		_rd.free(); _rd = null  # RenderingDevice has no free_rendering_device() in 4.7
	var d_ms := Time.get_ticks_msec() - _t0
	_receipt["checks"] = _checks
	_receipt["failures"] = _failures
	_receipt["elapsed_ms"] = d_ms
	_receipt["result"] = "PASS" if _failures == 0 else "FAIL"
	var dir := DirAccess.open("res://")
	if dir != null and not dir.dir_exists("_diag"):
		dir.make_dir("_diag")
	if dir != null and not dir.dir_exists("_diag/bh_dynamics"):
		dir.make_dir("_diag/bh_dynamics")
	var fa := FileAccess.open("res://_diag/bh_dynamics/bh_dynamics_receipt.json", FileAccess.WRITE)
	if fa != null:
		fa.store_string(JSON.stringify(_receipt, "  "))
		fa.close()
	print("[VerifyBHDyn] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, d_ms])
	print("[VerifyBHDyn] RESULT: %s" % _receipt["result"])
	get_tree().quit(0 if _failures == 0 else 1)
