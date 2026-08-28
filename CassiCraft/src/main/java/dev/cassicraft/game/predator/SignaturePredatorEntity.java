package dev.cassicraft.game.predator;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.Level;

/**
 * THE signature predator (signature-predator.md) — a vanilla entity that <b>hunts
 * by field signature</b>. The field as AI, embodied: it reads the published
 * coherence field at where it stands (never the player's coordinates), computes
 * the direction of rising signature ({@link SignatureSense}, the same
 * window-relative read the Weatherglass uses), moves a bounded step toward it
 * through <b>vanilla pathfinding</b> (wall-respecting, clamped walk speed —
 * never a teleport, never through walls), and when the signature peaks above the
 * on-trail threshold, presses the hunt into its aggro state.
 *
 * <p><b>The behavior loop is implemented on {@link #tick()}.</b> Each tick the
 * entity reads {@link SignatureSense#read} at its position against the freshest
 * published snapshot (the {@link SnapshotPublisher} is attached by the server-tick
 * coordinator, the same wiring as the minecart ride), takes the signature
 * gradient's unit direction, and sets a single one-step-ahead navigation target
 * along it — one vanilla <code>moveTo</code> per tick, bounded to at most one
 * {@link SignatureSense#STEP} block look-ahead, so no single tick can cross a
 * wall or a room (the boundary is the vanilla pathfinder, not a phantom speed).
 *
 * <p><b>Phase-1 boundary (honest).</b> This wave's predator is <b>read-only</b>:
 * it senses and hunts the signature gradient, but it does NOT perturb the field
 * (the Q4 {@code submitPerturbation} lane exists but is out of this wave's scope
 * for its attacks), does NOT write blocks, does NOT mint, does NOT teleport, and
 * does NOT see the player's coordinates — only the field at its own position. Its
 * "aggro" state is a pressed hunt (a named faster approach + a visible hint),
 * never a damage event and never a monster-table spawn. Death-by-Coda's
 * coherence-failure (signature-predator.md §5) is a later, Q4-gated layer.
 *
 * <p><b>Determinism.</b> The decision (read → gradient → target → speed) is a
 * pure function of the published snapshot and the entity's position: no RNG in
 * the hunt. Same field state → same movement. Cosmetic variation (if any) is
 * seed-derived only via the vanilla mob machinery and never touches the decision.
 *
 * <p>Rendering is the reused vanilla zombie renderer (no custom renderer, no
 * custom texture — registered on the client by mapping this type to
 * {@code ZombieRenderer}); an optional name tag rides the vanilla custom-name
 * machinery.
 */
public class SignaturePredatorEntity extends PathfinderMob {

	/**
	 * The hunt read cadence — re-read the field and re-target once every this
	 * many ticks. A bounded, felt cadence (the field's publish cadence, not a
	 * per-tick stream); the pathfinder moves continuously between re-reads, so
	 * the predator is not jittered every tick against the snapshot.
	 */
	public static final int HUNT_EVERY_TICKS = 2;

	/**
	 * The on-trail (aggro) approach speed scalar — how much faster the predator
	 * presses the hunt when its local signature is at/above
	 * {@link SignatureSense#ON_TRAIL_SIGNATURE}. [design] bounded to a modest
	 * press (1.4× the vanilla walk pace — it still walks, it does not sprint or
	 * fly); a deterministic function of the on-trail flag, never a roll. The
	 * vanilla pathfinder still clamps the actual ground speed to the movement-
	 * speed attribute, so this is a hunt-intensity dial, not a speed cheat.
	 */
	public static final float ON_TRAIL_SPEED_SCALAR = 1.4f;

	/** The wandering hunt speed as a fraction of the walk-speed attribute. */
	public static final float HUNT_SPEED_MODIFIER = 0.75f;

	private SnapshotPublisher publisher;
	private boolean onTrail;
	private int aggroTicks;

	public SignaturePredatorEntity(EntityType<? extends SignaturePredatorEntity> type, Level level) {
		super(type, level);
	}

	/** Keyed stats: a vanilla-pathfinder speed by default, with a real HP pool. */
	public static AttributeSupplier.Builder createAttributes() {
		return PathfinderMob.createMobAttributes()
				.add(Attributes.MOVEMENT_SPEED, 0.25D)
				.add(Attributes.MAX_HEALTH, 24.0D);
	}

	/**
	 * Attach the live publish handoff — called once by the server-tick
	 * coordinator it is spawned into. The entity reads {@code publisher.freshest()}
	 * each hunt step; never a block, never a write — the field is the only world
	 * it reads.
	 */
	public void attachPublisher(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/**
	 * The predator's behavior loop on tick: read the signature at its position,
	 * compute the hunt direction, press the hunt (or the aggro press when on the
	 * trail), and set one vanilla one-step-ahead navigation target along it.
	 * Deterministic — a pure function of the published snapshot + its position.
	 */
	@Override
	public void tick() {
		super.tick();

		SnapshotPublisher pub = this.publisher;
		if (this.level().isClientSide()) {
			// The decision law runs on the server (the field is published there);
			// the client just presents the vanilla mob.
			return;
		}
		if (pub == null || this.tickCount % HUNT_EVERY_TICKS != 0) {
			// No handoff yet: the predator holds (no world to read). The hunt
			// never guesses — honest fail-open on the field.
			return;
		}

		FieldSnapshot snap = pub.freshest();
		if (snap == null) {
			return; // the field has not published yet — no signature to hunt.
		}
		double[] center = SignatureSense.centerOf(snap);
		int bx = (int) Math.floor(this.getX());
		int by = (int) Math.floor(this.getY());
		int bz = (int) Math.floor(this.getZ());

		SignatureSense.Read sense = SignatureSense.read(snap, center, bx, by, bz);
		this.onTrail = sense.onTrail();
		if (this.onTrail) {
			this.aggroTicks++;
		} else {
			this.aggroTicks = 0;
		}

		float speed = HUNT_SPEED_MODIFIER * (float) this.getAttributeValue(Attributes.MOVEMENT_SPEED)
				* (this.onTrail ? ON_TRAIL_SPEED_SCALAR : 1.0f);

		if (sense.gradMag() <= SignatureSense.FLAT_GRADIENT_EPSILON) {
			return; // flat field — no legible direction to hunt; the predator holds.
		}

		// One-step-ahead target along the unit signature gradient, bounded to the
		// box interior so the read never falls off the field. The vanilla
		// pathfinder resolves the target through walls and at the clamped ground
		// speed — no teleport, no phantom speed.
		double len = Math.sqrt((double) sense.gradX() * sense.gradX()
				+ (double) sense.gradY() * sense.gradY()
				+ (double) sense.gradZ() * sense.gradZ());
		double step = SignatureSense.STEP;
		double tx = this.getX() + (sense.gradX() / len) * step;
		double ty = this.getY() + (sense.gradY() / len) * step;
		double tz = this.getZ() + (sense.gradZ() / len) * step;

		this.getNavigation().moveTo(tx, ty, tz, speed);
	}

	/** True when the predator's local signature read is on the trail (the aggro trigger). */
	public boolean isOnTrail() {
		return this.onTrail;
	}

	/** How many ticks the predator has continuously been on the trail (the aggro press). */
	public int aggroTicks() {
		return this.aggroTicks;
	}

	/** The optional name tag — the predator's tell (the desert-silence inversion, §3): visible only when named. */
	public void setPredatorName(String name) {
		this.setCustomName(Component.literal(name));
		this.setCustomNameVisible(true);
	}
}
