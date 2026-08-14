extends Node
## ───────────────────────────────────────────────────────────────────────────
## verify_decoupled_perf — PERF PROBE for the decoupled Cassi physics engine
## (scripts/cassi_physics_engine.gd threaded local-RD runner).
##
## Reproduces and times the two reported symptoms with HARD NUMBERS:
##   (1) the DETACHED-physics LONG HANG — the engine's start_threaded bootstrap:
##       each engine instance's first submit_steps(1) BLOCKS the main thread on
##       `_setup_sem.wait()` until the worker finishes local-RD create + buffer
##       alloc + 2.5M-particle IC generation + field init + uploads, THEN runs
##       the first job and a FULL fp32 snapshot readback. That synchronous
##       block is the apparent hang (no progress feedback).
##   (2) MATTER-CONDENSING STUTTER — the particle-merge pass (particle_merge,
##       the live main.tscn "dust -> object" coalesce). Every merge cycle does
##       a ~35 MB host prefix-sum readback (cc) + two ~35 MB buffer_update
##       uploads (cs/ch) + an 8.9M-iteration CPU prefix-sum, with submit+sync
##       per cycle; in the decoupled path it stalls the worker's physics per
##       batch, in the non-decoupled path it self-stalls the global RD every
##       rendered frame (Trap T2).
##
## The probe instantiates its OWN engine(s) with private local RDs on worker
## threads — fully isolated from any live sim; it touches NO shared sim files.
## It prints a timing table and (reproducible) writes → res://_diag/
## decoupled_perf_report.json (gitignored), then quits itself (exit 0).
##
## LAUNCH (windowed — local RD needs a real GPU; NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <space-sim> \
##       res://scenes/verify_decoupled_perf.tscn
## ───────────────────────────────────────────────────────────────────────────

const ENGINE_SCRIPT := "res://scripts/cassi_physics_engine.gd"

# Baseline config mirroring the LIVE main.tscn geometry (so the merge spatial
# hash, which is geometry-driven, matches the ~8.9M cells the user's scene
# builds). default cluster_radius in engine = 50; main.tscn uses 120.
const LIVE_CLUSTER_RADIUS := 120.0
const LIVE_NUM_CLUSTERS := 10
const LIVE_GRID_N := 64

# ── probe sizes ──
# The hang is size-driven (2.5M particles → ~83 MB fp32 snapshot + a
# multi-second IC loop). We run the bootstrap at the FULL size to reproduce
# it; the per-step / merge cost quantification uses a smaller N so the probe
# stays bounded (the merge hash readback is particle-count INDEPENDENT).
const HANG_N_PARTICLES := 2500000
const PROFILE_N_PARTICLES := 300000

# Bounded step budgets so the probe is quick.
const HANG_BOOTSTRAP_STEPS := 4
const RUN_MIN_STEPS := 12          # steps for the per-step ms/step measurement
const PUBLISH_PROBE_STEPS := 0     # 0 = a pure publish (no new steps)

var report: Dictionary = {}
var _engine = null
var _cfg := {}


func _ready() -> void:
	# House rule: never run while the live sim process shares this GPU in a
	# way that distorts timings — the probe is its own process by design.
	print("[perf] decoupled-perf probe — baseline hang/condensation timing")
	report["machine"] = {
		"godot": "4.7 win64 console (windowed, local RD)",
		"note": "AMD RX 7900 XTX; timings include PCIe transfer + CPU loops",
	}
	await get_tree().process_frame

	var table := []
	# ── Symptom 1: the DETACHED bootstrap hang (full 2.5M) ─────────────
	table.append(_probe_bootstrap())
	# ── Publish/readback economics (pure-publish timings) ───────────────
	table.append(_probe_publish())
	# ── Symptom 2: merge pass cost (per-batch readback + prefix-sum) ─────
	table.append(await _probe_merge())
	# ── Condensation / BH-accretion per-step chain cost (toggle) ────────
	table.append(await _probe_condensation())

	report["timings"] = table
	print("\n══════ decoupled-perf probe — timing table ══════")
	for row in table:
		print("  %-46s %10s" % [row.label, row.value])
	print("════════════════════════════════════════════════")
	var out_dir := "res://_diag"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var f := FileAccess.open(out_dir + "/decoupled_perf_report.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
		print("[perf] report → res://_diag/decoupled_perf_report.json")
	get_tree().quit(0)


func _base_cfg(n_particles: int, extras: Dictionary) -> Dictionary:
	var c = {
		"grid_N": LIVE_GRID_N,
		"N_particles": n_particles,
		"dt": 0.002,
		"cluster_radius": LIVE_CLUSTER_RADIUS,
		"num_clusters": LIVE_NUM_CLUSTERS,
		"cluster_separation": 120.0,
		"gravity_mode": 0,          # river (the per-step chain stays deterministic)
		"meshless_mode": false,     # grid path (deterministic, no tree worker)
		"meshless_gravity": false,
		"dual_grid": true,
		"black_holes_enabled": false,
		"particle_merge": false,
		"bh_accretion": false,
		"seed": 7,                  # fixed ICs (reproducible; engine key is "seed")
	}
	for k in extras:
		c[k] = extras[k]
	return c


func _new_engine(cfg: Dictionary):
	var e = load(ENGINE_SCRIPT).new()
	if e.start_threaded(cfg):
		return e
	return null


func _ms() -> int:
	return Time.get_ticks_msec()


func _row(label: String, value: String) -> Dictionary:
	return {"label": label, "value": value}


# ── Probe 1: the detached bootstrap hang ──────────────────────────────────
func _probe_bootstrap() -> Dictionary:
	print("\n── [perf] Probe 1: detached ENGINE BOOTSTRAP (startup hang) ──")
	var t_start := _ms()
	var e = load(ENGINE_SCRIPT).new()
	var ok: bool = e.start_threaded(_base_cfg(HANG_N_PARTICLES, {"black_holes_enabled": false}))
	var t_started := _ms() - t_start
	if not ok:
		return _row("PROBE1 bootstrap start_threaded", "FAILED (local RD)")
	_engine = e
	# Bootstrap: first submit blocks on setup + first job + full snapshot.
	var t0 := _ms()
	var pub = _engine.submit_steps(HANG_BOOTSTRAP_STEPS)
	var t_boot := _ms() - t0
	var snap: Dictionary = pub.get("snapshot", {})
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	var vel: PackedFloat32Array = snap.get("vel", PackedFloat32Array())
	var fq: PackedFloat32Array = snap.get("field_q", PackedFloat32Array())
	var pot: PackedFloat32Array = snap.get("pot", PackedFloat32Array())
	var exec := int(pub.get("executed", 0))
	var mb := (pos.size() + vel.size() + fq.size() + pot.size()) * 4 / (1024.0 * 1024.0)
	print("  [perf] start_threaded (shader load on main):  %d ms" % t_started)
	print("  [perf] BOOTSTRAP submit_steps(%d) main-thread block: %d ms  ->  executed=%d, snapshot=%.1f MB" % [HANG_BOOTSTRAP_STEPS, t_boot, exec, mb])
	var row := _row("PROBE1 bootstrap block (startup hang)", "%d ms (2.5M ptl, %.0f MB snap)" % [t_boot, mb])
	row["_detail"] = {
		"start_threaded_ms": t_started, "bootstrap_block_ms": t_boot,
		"executed": exec, "snapshot_mb": mb, "steps": HANG_BOOTSTRAP_STEPS,
	}
	# ms/step from the blocking path (worker steps + full publish per job).
	print("\n── [perf] Probe 1b: blocking submit per-job latency ──")
	var t_tot := 0
	for _i in range(4):
		var tn := _ms()
		_engine.submit_steps(HANG_BOOTSTRAP_STEPS + (_i + 1) * 4, true)
		t_tot += _ms() - tn
	print("  [perf] per-job blocking submit (4 steps + snapshot): avg %d ms (%.2f ms/step)" % [t_tot / 4, float(t_tot) / 4.0 / 4.0])
	row["_detail"]["per_job_block_ms"] = t_tot / 4
	_stop_engine()
	return row


# ── Probe 2: publish / readback economics ─────────────────────────────────
func _probe_publish() -> Dictionary:
	print("\n── [perf] Probe 2: PUBLISH / readback economics (pure-publish jobs) ──")
	_engine = null
	_engine = _new_engine(_base_cfg(HANG_N_PARTICLES, {}))
	if _engine == null:
		return _row("PROBE2 publish fp32", "FAILED")
	# Bootstrap (blocking) — completes setup AND warms, then bring executed to 2.
	_engine.submit_steps(2, true)
	var n0: int = _engine._executed
	var t0 := _ms()
	_engine.submit_steps(n0, true, {"cadence": 1})  # pure publish fp32 (no new steps)
	var t_fp32 := _ms() - t0
	# packed fp16 mirror (the engine's packed snapshot halves pos/vel readback)
	var t1 := _ms()
	_engine.submit_steps(n0, true, {"cadence": 1, "packed": true})
	var t_packed := _ms() - t1
	print("  [perf] pure-publish fp32 (pos+vel+field_q+pot readback): %d ms" % t_fp32)
	print("  [perf] pure-publish PACKED fp16 (halved pos/vel readback): %d ms" % t_packed)
	var row := _row("PROBE2 publish readback fp32→packed", "%d ms → %d ms" % [t_fp32, t_packed])
	row["_detail"] = {"fp32_ms": t_fp32, "packed_ms": t_packed, "N": PROFILE_N_PARTICLES}
	_stop_engine()
	return row


# ── Probe 3: merge pass cost ──────────────────────────────────────────────
func _probe_merge() -> Dictionary:
	print("\n── [perf] Probe 3: MATTER-CONDENSING (particle merge) cost ──")
	var c3 := _base_cfg(PROFILE_N_PARTICLES, {"particle_merge": true})
	print("      [debug] cfg.particle_merge=%s (probe intends true)" % c3.particle_merge)
	# engine A: particle_merge ON  → measures the merge pass per batch
	var em = _new_engine(c3)
	if em == null:
		return _row("PROBE3 merge pass", "FAILED (merge buffers)")
	var em2 = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"particle_merge": false}))
	if em2 == null:
		em.stop_threaded()
		return _row("PROBE3 merge twin", "FAILED")
	# start_threaded is ASYNC: setup completes on the worker, so the merge hash
	# buffers are NOT sized until setup() runs. Bootstrap BOTH (blocking) — this
	# both completes setup (so _merge_hash_total is real) and WARMS the pipelines
	# so the timed batch below is cold-start free.
	em.submit_steps(2, true)
	em2.submit_steps(2, true)
	await get_tree().process_frame
	print("      [debug] em.particle_merge=%s hash=(%d,%d,%d) total=%d  em2.particle_merge=%s" % [
		em.particle_merge, em._merge_hash_nx, em._merge_hash_ny, em._merge_hash_nz,
		em._merge_hash_total, em2.particle_merge])
	var hash_total: int = em._merge_hash_total
	var hash_mb: float = hash_total * 4.0 / (1024.0 * 1024.0)
	# a fresh equal batch on each warm engine — the delta IS the pure merge cost
	var margin_steps := 8
	var t_m_0 := _ms()
	em.submit_steps(2 + margin_steps, true)
	var t_m := _ms() - t_m_0
	var t_nm_0 := _ms()
	em2.submit_steps(2 + margin_steps, true)
	var t_nm := _ms() - t_nm_0
	var merge_overhead_ms: float = float(t_m - t_nm)
	print("      merge hash cells = %d  (%.1f MB read / %.1f MB upload per cycle)" % [hash_total, hash_mb, hash_mb])
	print("  [perf] %d-step batch WITHOUT merge: %d ms (%.2f ms/step)" % [margin_steps, t_nm, float(t_nm) / margin_steps])
	print("  [perf] %d-step batch WITH    merge: %d ms (%.2f ms/step)  -> merge overhead ≈ %+d ms/batch" % [margin_steps, t_m, float(t_m) / margin_steps, int(merge_overhead_ms)])
	print("  [perf] merge cycles run (engine lifetime): %d" % em._merge_cycles_run)
	var row := _row("PROBE3 merge overhead per batch", "%+d ms (%d hash cells)" % [int(merge_overhead_ms), hash_total])
	row["_detail"] = {
		"hash_total": hash_total, "hash_readback_mb": hash_mb,
		"batch_no_merge_ms": t_nm, "batch_with_merge_ms": t_m,
		"merge_overhead_ms": int(merge_overhead_ms),
		"merge_cycles_lifetime": em._merge_cycles_run,
	}
	em.stop_threaded()
	em2.stop_threaded()
	_engine = null
	return row


# ── Probe 4: condensation / BH-integrate chain cost ───────────────────────
func _probe_condensation() -> Dictionary:
	print("\n── [perf] Probe 4: BH chain (condensation scan every 100 steps, BH-integrate every step) ──")
	var eA = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"black_holes_enabled": false}))
	var eB = _new_engine(_base_cfg(PROFILE_N_PARTICLES, {"black_holes_enabled": true, "bh_accretion": false}))
	if eA == null or eB == null:
		return _row("PROBE4 BH chain", "FAILED")
	# Bootstrap BOTH (setup is async) + warm pipelines before timing.
	eA.submit_steps(2, true)
	eB.submit_steps(2, true)
	await get_tree().process_frame
	# run enough steps to cross a condensation dispatch (every 100 steps) on B
	var steps := 102
	var ta_0 := _ms()
	eA.submit_steps(2 + steps, true)
	var ta := _ms() - ta_0
	var tb_0 := _ms()
	eB.submit_steps(2 + steps, true)
	var tb := _ms() - tb_0
	print("  [perf] BH OFF: %d steps, %d ms  -> %.2f ms/step" % [steps, ta, float(ta) / steps])
	print("  [perf] BH  ON: %d steps, %d ms  -> %.2f ms/step  (condensation every 100, BH-integrate every step)" % [steps, tb, float(tb) / steps])
	var row := _row("PROBE4 BH-chain ms/step (off→on)", "%.2f → %.2f ms/step" % [float(ta) / steps, float(tb) / steps])
	row["_detail"] = {"off_ms": ta, "on_ms": tb, "steps": steps}
	eA.stop_threaded()
	eB.stop_threaded()
	_engine = null
	return row


func _stop_engine() -> void:
	if _engine != null:
		_engine.stop_threaded()
		_engine = null
