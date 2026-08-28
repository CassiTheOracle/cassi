extends SceneTree
## Headless unit battery for scripts/envelope_tracker.gd (the B-build
## tracking envelope). Run: godot --headless --script res://_diag/b_track_unit.gd
## Exit 0 = all PASS; 1 = any FAIL.

const BOX := Vector3(60.7, 60.7, 60.7)   # a CUBE box: the aspect-preserving scale is driven by the max axis

var _fail := 0

func _initialize() -> void:
	var t := EnvelopeTracker.new()
	# ── case 1: no-op (the canary) — a 45-unit envelope is inside the
	#    [shrink 0.70x, grow 1.10x] hysteresis band of the 60.7 tile.
	t.center = Vector3.ZERO
	t.extent = BOX
	_assert_close("case1 no-op extent", _uniform(-45.0, 45.0, 400), t, BOX, 1e-3, 0)

	# ── case 2: grow — a 70-unit envelope exceeds 1.10 x 60.7 -> re-fit,
	#    aspect-preserving (the tile = the tracker's demand on every axis).
	t = EnvelopeTracker.new()
	t.center = Vector3.ZERO
	t.extent = BOX
	t.compute(_uniform(-70.0, 70.0, 400))
	_check(absf(t.extent.x - t.last_demand) < 1e-3 * t.last_demand, "case2 grow extent.x")
	_check(absf(t.extent.y - t.extent.x) < 1e-3 * t.extent.x, "case2 grow aspect y")
	_check(absf(t.extent.z - t.extent.x) < 1e-3 * t.extent.x, "case2 grow aspect z")
	_check(t.re_fits == 1, "case2 grow re_fits")

	# ── case 3: shrink — a 30-unit envelope < 0.70 x 60.7 -> re-fit down.
	t = EnvelopeTracker.new()
	t.center = Vector3.ZERO
	t.extent = BOX
	t.compute(_uniform(-30.0, 30.0, 400))
	_check(absf(t.extent.x - t.last_demand) < 1e-3 * t.last_demand, "case3 shrink extent.x")
	_check(t.re_fits == 1, "case3 shrink re_fits")

	# ── case 4: move cap — a 100-unit X demand is clamped to 0.25 x the
	#    min extent (the demand is X-only so the clamp is along X).
	t = EnvelopeTracker.new()
	t.center = Vector3.ZERO
	t.extent = Vector3(10.0, 10.0, 10.0)
	t.compute(_rod(90.0, 110.0, 400))
	_check(absf(t.center.x - 0.25 * t.extent.x) < 1e-4, "case4 move cap")
	_check(t.center.y == 0.0 and t.center.z == 0.0, "case4 cap axes")

	# ── case 5: min-extent floor — a point-like structure must not
	#    collapse the tile below the floor.
	t = EnvelopeTracker.new()
	t.center = Vector3.ZERO
	t.extent = BOX
	t.compute(_uniform(-0.2, 0.2, 400))
	_check(absf(t.extent.x - 1.0) < 1e-6, "case5 floor extent.x")

	# ── case 6: robustness — a straggler at 5000 must NOT blow the tile
	#    (the 99.5% percentile excludes it).
	t = EnvelopeTracker.new()
	t.center = Vector3.ZERO
	t.extent = BOX
	var rob := _uniform(-45.0, 45.0, 400)
	rob.append(5000.0)
	rob.append(0.0)
	rob.append(0.0)
	t.compute(rob)
	_check(absf(t.extent.x - BOX.x) < 1e-3, "case6 robust extent.x")
	_check(t.center.length() < 1.0, "case6 robust center")

	# ── case 7: determinism — identical input -> bit-identical state.
	var s := _uniform(-70.0, 70.0, 400)
	var a := EnvelopeTracker.new()
	var b := EnvelopeTracker.new()
	a.center = Vector3.ZERO
	b.center = Vector3.ZERO
	a.extent = BOX
	b.extent = BOX
	a.compute(s)
	b.compute(s)
	_check(a.center == b.center and a.extent == b.extent
		and a.last_demand == b.last_demand and a.re_fits == b.re_fits,
		"case7 determinism")

	if _fail == 0:
		print("[BUnit] envelope tracker: ALL PASS (7 cases)")
		quit(0)
	else:
		print("[BUnit] envelope tracker: %d FAILS" % _fail)
		quit(1)


## X-only rod sample: X uniform in [lo, hi], Y/Z ~ 0 (a pure X demand).
func _rod(lo: float, hi: float, count: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(count * 3)
	for i in range(count):
		out[i * 3] = lo + (hi - lo) * randf()
		out[i * 3 + 1] = 0.0
		out[i * 3 + 2] = 0.0
	return out


## Uniform-box sample helper (uses the global RNG — fine for the
## tolerance-based cases; case 7 compares two computes on the SAME array).
func _uniform(lo: float, hi: float, count: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(count * 3)
	for i in range(count):
		out[i * 3] = lo + (hi - lo) * randf()
		out[i * 3 + 1] = lo + (hi - lo) * randf()
		out[i * 3 + 2] = lo + (hi - lo) * randf()
	return out


func _assert_close(tag: String, samples: PackedFloat32Array, t: EnvelopeTracker,
		expect_ext: Vector3, tol: float, expect_re: int) -> void:
	var ok := true
	for a in range(3):
		if absf(t.extent[a] - expect_ext[a]) > tol * maxf(expect_ext[a], 1.0):
			ok = false
	if t.re_fits != expect_re:
		ok = false
	_check(ok, tag)


func _check(ok: bool, tag: String) -> void:
	if ok:
		print("[BUnit] PASS  %s" % tag)
	else:
		_fail += 1
		print("[BUnit] FAIL  %s" % tag)
