package dev.cassicraft.client.predator;

import dev.cassicraft.game.predator.SignaturePredatorEntity;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.model.monster.zombie.ZombieModel;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.HumanoidMobRenderer;
import net.minecraft.client.renderer.entity.state.ZombieRenderState;
import net.minecraft.resources.Identifier;

/**
 * The signature predator's client renderer (signature-predator.md §8). A thin
 * no-asset renderer: it presents the vanilla {@link SignaturePredatorEntity}
 * (a {@code PathfinderMob}) through the <b>reused vanilla zombie model + vanilla
 * zombie texture</b> — no custom model, texture, or shader. It uses the vanilla
 * humanoid render pipeline ({@link HumanoidMobRenderer} extracts the generic
 * living/humanoid render state from any {@code Mob}) with the vanilla zombie
 * model layer ({@link ModelLayers#ZOMBIE}) and the vanilla zombie skin.
 *
 * <p>This is the vanilla-reuse path the mod's constraints demand (no mixins, no
 * new assets): the predator's rendering is a presentation of a vanilla mob, and
 * its hunt behavior stays in the entity's deterministic field-read tick. The
 * {@code ZombieRenderState} is the vanilla humanoid-undead state the zombie model
 * reads — a plain {@code PathfinderMob} fills only the generic-mob fields, which
 * the humanoid extractor populates; the zombie-specific fields (aggression,
 * conversion) simply stay at their defaults for a non-zombie body.
 *
 * <p>Registered on the client by mapping the {@code cassicraft:signature_predator}
 * entity type to this renderer's constructor (see the wiring request, Edit 8).
 */
public class SignaturePredatorRenderer extends
		HumanoidMobRenderer<SignaturePredatorEntity, ZombieRenderState, ZombieModel<ZombieRenderState>> {

	/** The vanilla zombie skin texture (no custom asset — the reused vanilla texture). */
	private static final Identifier TEXTURE =
			Identifier.fromNamespaceAndPath("minecraft", "textures/entity/zombie/zombie.png");

	public SignaturePredatorRenderer(EntityRendererProvider.Context context) {
		super(context,
				new ZombieModel<>(context.getModelSet().bakeLayer(ModelLayers.ZOMBIE)),
				0.5f);
	}

	/** The vanilla zombie model reads the vanilla undead-humanoid render state. */
	@Override
	public ZombieRenderState createRenderState() {
		return new ZombieRenderState();
	}

	/** The predator wears the vanilla zombie skin. */
	@Override
	public Identifier getTextureLocation(ZombieRenderState state) {
		return TEXTURE;
	}
}
