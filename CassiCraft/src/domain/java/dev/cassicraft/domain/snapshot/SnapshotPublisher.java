package dev.cassicraft.domain.snapshot;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * MODULE 1 — FIELD DOMAIN. NO Minecraft imports (domain source-set gate).
 *
 * <p>The publish handoff — the only cross-thread structure in the entire mod
 * (BUILD-PLAN.md §4.2, §9.3; async-field-domain.md §5.1). The worker publishes an
 * <b>immutable</b> {@link FieldSnapshot} under a single volatile write of the
 * full reference with a monotonic generation; the sampler reads it lock-free.
 *
 * <p>Because a {@link FieldSnapshot} is fully immutable and never mutated after
 * handoff, a single {@code volatile} reference write is sufficient and correct:
 * the reader either sees the whole new snapshot or none, never a torn one. The
 * sampler calls {@link #freshest()} with no lock held and owns the reference.
 * Stale-generation dropping ({@code _consumed_gen} / {@code _res_gen}) is
 * preserved: {@link #freshest()} returns the latest published snapshot, and the
 * sampler observes only a monotonically increasing generation.
 *
 * <p>Generation authority lives here, so publish order — not caller bookkeeping —
 * owns monotonicity. The worker asks for the next generation, builds the snapshot
 * exactly once under it, and hands it back for a single volatile write (no
 * second defensive copy, matching the corpus's "fresh alloc per publish, measure
 * GC before optimizing" note, BUILD-PLAN.md §4.2).
 */
public final class SnapshotPublisher {

	private final AtomicInteger generation = new AtomicInteger(0);
	private volatile FieldSnapshot latest;

	/**
	 * Reserve the next monotonically-increasing generation for an in-flight publish.
	 * Call exactly once per {@link #publish(FieldSnapshot)} on the worker.
	 */
	public int allocateGeneration() {
		return generation.incrementAndGet();
	}

	/**
	 * Publish a fully-built, immutable snapshot stamped with the generation
	 * returned by {@link #allocateGeneration()}. A single volatile write; the
	 * reader never sees a torn snapshot. The caller must not mutate the arrays
	 * afterward — build a fresh snapshot next job.
	 */
	public void publish(FieldSnapshot snapshot) {
		this.latest = snapshot;
	}

	/**
	 * Volatile load of the freshest snapshot, or {@code null} if none yet. Never
	 * blocks; the caller owns the returned reference and may read it lock-free.
	 */
	public FieldSnapshot freshest() {
		return latest;
	}

	/** The current generation counter (monotonic). */
	public int generation() {
		return generation.get();
	}
}
