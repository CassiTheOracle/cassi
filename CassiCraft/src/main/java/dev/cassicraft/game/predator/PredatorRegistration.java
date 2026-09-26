package dev.cassicraft.game.predator;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;

/**
 * The signature predator's entity-type registration (signature-predator.md —
 * the Phase-1 embodied slice). Registers the {@link SignaturePredatorEntity} as
 * a vanilla {@link EntityType} under {@code cassicraft:signature_predator},
 * built with a {@link MobCategory#MONSTER} factory and rendered on the client
 * with the reused vanilla zombie renderer (no custom renderer, no custom
 * texture — mapped via {@code EntityRendererRegistry}, Fabric API only).
 *
 * <p>Called once from {@code CassiCraft.onInitialize} (the wiring request); the
 * static {@link #TYPE} is then referenced by the spawn command and the
 * attributes registration. No mixins: pure built-in-registry registration.
 */
public final class PredatorRegistration {

	/** The registered entity type (filled at mod init; null only before mod init). */
	public static EntityType<SignaturePredatorEntity> TYPE;

	private PredatorRegistration() {
	}

	/**
	 * Register the entity type into {@link BuiltInRegistries#ENTITY_TYPE} under
	 * {@code cassicraft:signature_predator} and stash it in {@link #TYPE}. Safe
	 * to call once from mod init.
	 */
	public static void register() {
		if (TYPE != null) {
			return; // already registered (idempotent).
		}
		Identifier id = Identifier.fromNamespaceAndPath("cassicraft", "signature_predator");
		ResourceKey<EntityType<?>> key = ResourceKey.create(Registries.ENTITY_TYPE, id);
		EntityType<SignaturePredatorEntity> type = EntityType.Builder
				.of(SignaturePredatorEntity::new, MobCategory.MONSTER)
				.sized(0.6f, 1.95f)
				.build(key);
		TYPE = Registry.register(BuiltInRegistries.ENTITY_TYPE, key, type);
	}
}
