package dev.cassicraft.domain.snapshot;

import dev.cassicraft.domain.engine.EngineJob;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The immutable publish payload (BUILD-PLAN.md §4.1, chunk-field-quantization.md §2).
 * Byte-accurate to the corpus's canonical ≈ 6 MiB field-only snapshot:
 *
 * <pre>
 *   q           1 MiB  float[262,144]  field_q (coherence)      — ore/spawn gates
 *   pot (Φ)     1 MiB  float[262,144]  spectral Poisson real    — ∇(g·Φ) source
 *   grad        3 MiB  float[786,432]  ∇(g·Φ) vec3 trim         — entity steering
 *   rho (ρ)     1 MiB  float[262,144]  EY+EI single channel     — condensation, ε²
 *   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
 *   approx 6 MiB, plus EngineJob meta {executed, step_count, t,
 *   window_center, generation}.
 * </pre>
 *
 * <p>Fully immutable: every array is defensively copied at construction and never
 * mutated afterward. The worker fills a fresh snapshot off to the side, atomically
 * hands it off via {@link SnapshotPublisher}; the sampler reads it lock-free with
 * no torn state. This is the <em>only</em> cross-thread data structure in the mod.
 *
 * <p>The gradient trim is one flat contiguous {@code float[CELLS*3]} array
 * ({@code grad[cell*3 + comp]}, comp {@code 0=x,1=y,2=z}) since the FIX 1
 * bulk-storage rework — the defensive copy is a single {@code System.arraycopy}
 * instead of 262,144 small {@code float[3]} allocations (the publish clone's
 * measured GC churn), with the element order and per-cell vec3 layout semantics
 * preserved bit-for-bit.
 */
public record FieldSnapshot(
		float[] q,
		float[] pot,
		float[] grad,       // flat vec3 trim: [cell*3 + comp] (3 MiB)
		float[] rho,
		int generation,
		EngineJob job
) {

	public FieldSnapshot {
		q = q.clone();
		pot = pot.clone();
		grad = grad.clone();
		rho = rho.clone();
		job = job == null ? null : new EngineJob(job.executed(), job.stepCount(), job.t(), job.windowCenter());
	}

	/** Salt-stable content hash for the determinism gate (same snapshot → same hash). */
	public String contentHash() {
		java.security.MessageDigest md;
		try {
			md = java.security.MessageDigest.getInstance("SHA-256");
		} catch (java.security.NoSuchAlgorithmException e) {
			throw new IllegalStateException(e);
		}
		for (float[] b : new float[][] { q, pot, rho, grad }) {
			java.nio.ByteBuffer bb = java.nio.ByteBuffer.allocate(b.length * 4);
			bb.asFloatBuffer().put(b);
			md.update(bb.array());
		}
		byte[] d = md.digest();
		StringBuilder sb = new StringBuilder(d.length * 2);
		for (byte x : d) {
			sb.append(String.format("%02x", x));
		}
		return sb.toString();
	}
}
