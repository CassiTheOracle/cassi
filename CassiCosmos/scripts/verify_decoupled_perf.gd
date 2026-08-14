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
	table.append(await _probe_bootstrap())
	# ── Publish/readback economics (pure-publish timings) ───────────────
	table.append(await _probe_publish())
	# ── Symptom 2: merge pass cost (per-batch readback + prefix-sum) ─────
	table.append(await _probe_merge())
	# ── Condensation / BH-accretion per-step chain cost (toggle) ────────
	table.append(await _probe_condensation())
	# ── Worker-thread local-RD float-atomic accumulation (FIX D pre-check) ─
	table.append(await _probe_worker_atomicaults())

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
# FIX A: the first submit is now NON-BLOCKING (queued). This probe measures
# (a) the submit call's own latency on the main thread (must be ~0 ms, not the
# old ~3.5 s block) and (b) the async time-to-first-publish via poll — the main
# thread free-pumps process frames while the worker builds the 2.5M ICs.
func _probe_bootstrap() -> Dictionary:
	print("\n── [perf] Probe 1: detached ENGINE BOOTSTRAP (now non-blocking / FIX A) ──")
	var t_start := _ms()
	var e = load(ENGINE_SCRIPT).new()
	var ok: bool = e.start_threaded(_base_cfg(HANG_N_PARTICLES, {"black_holes_enabled": false}))
	var t_started := _ms() - t_start
	if not ok:
		return _row("PROBE1 bootstrap start_threaded", "FAILED (local RD)")
	_engine = e
	# FIX A: the first submit queues the job and returns IMMEDIATELY — it must
	# NOT block ~3.5 s on setup. Measure the submit call itself.
	var t_sub := _ms()
	var ret = _engine.submit_steps(HANG_BOOTSTRAP_STEPS)
	var t_submit_ms := _ms() - t_sub
	var pub: Dictionary = await _await_first_publish(_engine)
	var snap: Dictionary = pub.get("snapshot", {})
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	var vel: PackedFloat32Array = snap.get("vel", PackedFloat32Array())
	var fq: PackedFloat32Array = snap.get("field_q", PackedFloat32Array())
	var pot: PackedFloat32Array = snap.get("pot", PackedFloat32Array())
	var exec := int(pub.get("executed", 0))
	var mb := (pos.size() + vel.size() + fq.size() + pot.size()) * 4 / (1024.0 * 1024.0)
	print("  [perf] start_threaded (shader load on main):  %d ms" % t_started)
	print("  [perf] BOOTSTRAP submit_steps(%d) MAIN-THREAD LATENCY: %d ms  (was ~3500 ms block)" % [HANG_BOOTSTRAP_STEPS, t_submit_ms])
	print("  [perf] async time-to-first-publish (worker IC build, NON-blocking): %d ms  ->  executed=%d, snapshot=%.1f MB" % [int(_last_first_pub_ms), exec, mb])
	var row := _row("PROBE1 bootstrap main-thread block", "%d ms (was ~3500 ms)" % t_submit_ms)
	row["_detail"] = {
		"start_threaded_ms": t_started, "submit_nonblock_ms": t_submit_ms,
		"async_first_publish_ms": int(_last_first_pub_ms),
		"executed": exec, "snapshot_mb": mb, "steps": HANG_BOOTSTRAP_STEPS,
	}
	# ms/step from the blocking path (worker steps + full publish per job).
	print("\n── [perf] Probe 1b: blocking submit per-job latency (post-bootstrap) ──")
	var t_tot := 0
	for _i in range(4):
		var tn := _ms()
		_engine.submit_steps(HANG_BOOTSTRAP_STEPS + (_i + 1) * 4, true)
		t_tot += _ms() - tn
	print("  [perf] per-job blocking submit (4 steps + snapshot): avg %d ms (%.2f ms/step)" % [t_tot / 4, float(t_tot) / 4.0 / 4.0])
	row["_detail"]["per_job_block_ms"] = t_tot / 4
	_stop_engine()
	return row


# FIX A helper: after the (non-blocking) first submit, poll the engine until
# setup_ready() and the first snapshot publish land, free-pumping process
# frames (proves the main thread never blocks). Returns the first publish.
var _last_first_pub_ms := 0.0
func _await_first_publish(eng) -> Dictionary:
	var t0 := _ms()
	var waited := 0
	while waited < 1200:   # up to ~20 s of free-pumped frames at 60 fps
		var pub: Dictionary = eng.poll()
		if not pub.is_empty() and pub.has("snapshot") and not (pub.get("snapshot", {}) as Dictionary).is_empty():
			_last_first_pub_ms = float(_ms() - t0)
			return pub
		# also track setup completion (informational) — the main thread is free
		await get_tree().process_frame
		waited += 1
	_last_first_pub_ms = float(_ms() - t0)
	return {}


# ── Probe 2: publish / readback economics ─────────────────────────────────
func _probe_publish() -> Dictionary:
	print("\n── [perf] Probe 2: PUBLISH / readback economics (pure-publish jobs) ──")
	_engine = null
	_engine = _new_engine(_base_cfg(HANG_N_PARTICLES, {}))
	if _engine == null:
		return _row("PROBE2 publish fp32", "FAILED")
	# First submit is non-blocking (FIX A) — queue and await the first publish
	# (main thread free-pumps), then bring executed to 2 for a warm baseline.
	_engine.submit_steps(2)
	await _await_first_publish(_engine)
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
	# First submit is non-blocking (FIX A). Await the first publish on both so
	# setup completes (so _merge_hash_total is real) AND pipelines warm — the
	# main thread free-pumps; the timed batch below is cold-start free.
	em.submit_steps(2)
	em2.submit_steps(2)
	await _await_first_publish(em)
	await _await_first_publish(em2)
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
	# First submit is non-blocking (FIX A). Await the first publish on both to
	# complete setup + warm (main thread free-pumps) before timing.
	eA.submit_steps(2)
	eB.submit_steps(2)
	await _await_first_publish(eA)
	await _await_first_publish(eB)
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


# ── Probe 5: worker-thread local-RD FLOAT-ATOMIC accumulation check ───────
# Settles FIX D empirically: does the BH-accretion float atomicAdd
# (OpAtomicFAddEXT) actually accumulate on the WORKER-thread local RD (the
# decoupled path) — or only warn during teardown? We plant a BH record via the
# engine's own _bh_init_bytes member (the worker re-uploads it each batch),
# set bh_accretion ON with particle_merge OFF (so any pos.w=0 deaths are from
# ACCRETION alone, not from a merge zeroing), and count deaths in the returned
# snapshot. If the float atomic worked, in-radius particles die → pos.w=0.
func _probe_worker_atomicaults() -> Dictionary:
	print("\n── [perf] Probe 5: BH-ACCERTION float atomic on the WORKER local RD ──")
	var cfg := _base_cfg(100000, {
		"black_holes_enabled": true, "bh_accretion": true,
		"particle_merge": false,
		"bh_accretion_radius": 100.0, "cluster_radius": 40.0,
		"num_clusters": 1, "cluster_separation": 0.0,
		"source_strength": 0.0, "bh_acc_rate": 0.0,
	})
	var e = load(ENGINE_SCRIPT).new()
	if not e.start_threaded(cfg):
		return _row("PROBE5 worker accretion atomic", "FAILED (start)")
	# First submit is non-blocking (FIX A). Await the first publish so setup
	# completes (and _apply_gravity_calibration is done — _bh_init_bytes is
	# final). THEN plant the BH so the worker re-uploads my planted header
	# verbatim every batch (no race with setup).
	e.submit_steps(1)
	await _await_first_publish(e)
	var b: PackedByteArray = e._bh_init_bytes.duplicate()
	if b.size() < 96:
		e.stop_threaded()
		return _row("PROBE5 worker accretion atomic", "FAILED (header)")
	b.encode_float(64, 0.0); b.encode_float(68, 0.0); b.encode_float(72, 0.0)
	b.encode_float(76, 5.0)   # planted BH mass 5.0 at origin
	b.encode_float(80, 0.0); b.encode_float(84, 0.0); b.encode_float(88, 0.0)
	b.encode_float(92, 0.0)
	e._bh_init_bytes = b
	# R_acc=100 covers the whole Plummer ball -> if the atomic fires, the bulk of
	# the ~100k particles die (pos.w=0). bh_acc_rate=0 kills integrate growth so
	# accretion is the only death source (no merge in this config).
	var dead := 0
	var total := 0
	var t0 := _ms()
	var pub = e.submit_steps(6, true, {"cadence": 1})   # cadence 1 forces a publish on this job
	var dt_ms := _ms() - t0
	var snap: Dictionary = pub.get("snapshot", {})
	var pos: PackedFloat32Array = snap.get("pos", PackedFloat32Array())
	total = pos.size() / 4
	for i in range(pos.size() / 4):
		if pos[i * 4 + 3] <= 0.0: dead += 1
	print("      [perf] worker BH-accretion: %d/%d particles dead (pos.w=0) after 6 steps, job=%d ms (R_acc=100, planted BH mass 5)" % [dead, total, dt_ms])
	var worked := dead > 0
	print("      [perf] => float-atomic accretion on worker local RD: %s" % ("ACCUMULATES (works)" if worked else "NO DEATHS (atomic did not fire)"))
	var row := _row("PROBE5 worker accretion float-atomic", "WORKS (%d dead)" % dead if worked else "NO-OP (%d dead)" % dead)
	row["_detail"] = {"dead": dead, "total": total, "job_ms": dt_ms, "atomic_worked": worked}
	e.stop_threaded()
	_engine = null
	return row
