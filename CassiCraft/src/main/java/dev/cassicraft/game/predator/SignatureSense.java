package dev.cassicraft.game.predator;

import dev.cassicraft.domain.engine.TwoFluidSolver;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The signature-predator's sense (signature-predator.md §1 — the Coda's read;
 * Phase-1 slice §8). A <b>pure, Minecraft-free</b> read of the published field
 * at the predator's window-relative position: the local coherence signature —
 * {@code q} (the wake's coherence), {@code ε²} (the churn / the vent), and the
 * <b>signature gradient</b> — the direction of rising signature the predator
 * hunts along.
 *
 * <p><b>What a window-relative position means.</b> The predator never sees the
 * player's coordinates. It holds its own block position against the snapshot's
 * published window center and samples the field there via the same fused
 * 8-corner traversal the Weatherglass uses ({@link Quantizer#sampleReading}).
 * Its entire world is the field's published channels at where it stands — the
 * field as AI, embodied. It reads the field, never the player.
 *
 * <p><b>The signature.</b> The corpus's trail is the organized-perturbation
 * footprint — a local elevation of organization ({@code q}, coherence) plus the
 * {@code ε²} vent ({@code ε² = (EY−φ·EI)²}, the decoherence byproduct); in flat
 * disorder it is the one coherent thing (signature-predator.md §1.1). Phase-1
 * publishes no per-trail phase-matching factor {@code M} (open-Q2 DECIDED:
 * {@code M} is a deferred probe, not a Phase-1 publication), so the resonance's
 * phase-stability collapses toward magnitude — this sense reads the signature
 * as the <b>designed</b> combination {@code S = q · (1 + ε²)}: elevated
 * organization ({@code q}) weighted by the strain ({@code ε²}) that marks a
 * vent, per §7d's [design]-over-engine-real boundary. It is a <i>reading</i> of
 * the engine-real {@code q}/{@code ε²}, never a claim that the engine "hunts"
 * anything itself.
 *
 * <p><b>The signature gradient.</b> The hunt direction is the finite difference
 * of {@code S} over the published channels at the predator's position — sampled
 * one cell east/north/up along each axis, centered differences clipped to the
 * box, so it points toward rising signature (the trail). Evaluated at the block
 * center grid the quantizer already visits, a pure deterministic function of the
 * published snapshot. When the local signature exceeds a named on-trail
 * threshold, the predator is <i>on</i> the trail and the sense flags the aggro
 * trigger (signature-predator.md §2.3's recognition gate, inverted).
 *
 * <p>Never mutates — a pure read. Minecraft-free: compiles against the domain +
 * sampler only, so the determinism gate that replays the hunt is headless.
 */
public final class SignatureSense {

	/**
	 * The signature sampling step — how many block-centers east/north/up the
	 * finite-difference probes for the signature gradient, relative to the
	 * predator's position. One 3 m grid cell (the quantizer's cell is 3 m wide,
	 * {@code CassiFieldThread.CELL_WORLD_WIDTH}); steps out of the box read zero
	 * (empty air), so a predator at the box edge leans toward the interior — the
	 * field ends at the box, honestly.
	 */
	public static final int STEP = 1;

	/**
	 * The on-trail threshold — the local signature {@code S = q·(1+ε²)} at or
	 * above which the predator is <i>on the trail</i> and switches to its aggro
	 * state (signature-predator.md §2.3's recognition gate, inverted). [design]
	 * calibrated to the coherent condensed body's read (see
	 * {@code PredatorDeterminismMain}'s measured magnitudes): the body's
	 * coherent bulk runs {@code q ≈ 1.0…1.2} with {@code ε² ≈ 0.03}, so a blob
	 * on the drain-adjacent coherent field carries {@code S ≳ 1.0}; the thin
	 * vacuum above the body carries {@code S ≈ 0} (nothing legible to read). The
	 * threshold is tuning the predator slice owns; the trigger is the built field's
	 * real {@code q}/{@code ε²}, never a scripted timer.
	 */
	public static final float ON_TRAIL_SIGNATURE = 1.0f;

	/**
	 * The signature gradient magnitude below which the field is locally flat —
	 * the predator stands still (no legible direction to hunt). Kept at zero so
	 * only a genuinely zero signature gradient stops the motion (the hunt is
	 * pure: any measurable lean toward a higher signature is a lean to move).
	 */
	public static final float FLAT_GRADIENT_EPSILON = 0.0f;

	private SignatureSense() {
	}

	/**
	 * The sense read at one block position: the local signature's two channels,
	 * the designed scalar {@code S}, the finite-difference gradient of {@code S}
	 * (the hunt direction), the gradient magnitude, and the on-trail flag.
	 */
	public record Read(
			float q, float eps2, float signature,
			float gradX, float gradY, float gradZ, float gradMag,
			boolean onTrail) {
	}

	/**
	 * Sample the sense at a block position against a snapshot's window center.
	 *
	 * @param snap the published snapshot (freshest; the only world the predator reads)
	 * @param windowCenter the snapshot's job window center (the domain box origin)
	 * @param blockX/Y/Z the predator's block position (window-relative — it never
	 *        sees the player's coordinates, only where it stands in the field)
	 */
	public static Read read(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		Quantizer.FieldReading here = Quantizer.sampleReading(snap, windowCenter, blockX, blockY, blockZ);
		float q = here.q();
		float eps2 = here.eps2();
		float s = signature(q, eps2);

		// Finite difference of S over the published channels: centered differences
		// clamped to the box (+/- x/east, y/up, z/north).
		float sxm = signatureAt(snap, windowCenter, blockX - STEP, blockY, blockZ);
		float sxp = signatureAt(snap, windowCenter, blockX + STEP, blockY, blockZ);
		float sym = signatureAt(snap, windowCenter, blockX, blockY - STEP, blockZ);
		float syp = signatureAt(snap, windowCenter, blockX, blockY + STEP, blockZ);
		float szm = signatureAt(snap, windowCenter, blockX, blockY, blockZ - STEP);
		float szp = signatureAt(snap, windowCenter, blockX, blockY, blockZ + STEP);

		float gx = 0.5f * (sxp - sxm);
		float gy = 0.5f * (syp - sym);
		float gz = 0.5f * (szp - szm);
		float gradMag = (float) Math.sqrt((double) gx * gx + (double) gy * gy + (double) gz * gz);
		boolean onTrail = s >= ON_TRAIL_SIGNATURE;
		return new Read(q, eps2, s, gx, gy, gz, gradMag, onTrail);
	}

	/** The designed signature scalar {@code S = q·(1+ε²)} at a point. */
	public static float signature(float q, float eps2) {
		return q * (1.0f + eps2);
	}

	/** The signature at a neighboring block (zero out-of-box — empty air has no trail). */
	private static float signatureAt(FieldSnapshot snap, double[] windowCenter,
			int x, int y, int z) {
		Quantizer.CellSample c = Quantizer.sampleAt(snap, windowCenter, x, y, z);
		return signature(c.rho() <= 0f ? 0f : c.q(), c.eps2());
	}

	/** The snapshot's window center, falling back to the domain origin if the job is windowless. */
	public static double[] centerOf(FieldSnapshot snap) {
		if (snap.job() != null && !snap.job().isWindowless()) {
			return snap.job().windowCenter();
		}
		return new double[] { 0, 0, 0 };
	}
}
