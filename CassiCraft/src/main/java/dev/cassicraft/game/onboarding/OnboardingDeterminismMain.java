package dev.cassicraft.game.onboarding;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

/** Targeted gate for the frozen ordinary-player onboarding contract. */
public final class OnboardingDeterminismMain {
    private static final UUID PLAYER = UUID.fromString("00000000-0000-0000-0000-000000000042");
    private static final Path RECIPE = Path.of("src/main/resources/data/cassicraft/recipe/weatherglass.json");
    private static final Path ADVANCEMENT = Path.of("src/main/resources/data/cassicraft/advancement/onboarding/weatherglass_acquired.json");

    public static void main(String[] args) throws Exception {
        String recipe = Files.readString(RECIPE);
        String advancement = Files.readString(ADVANCEMENT);
        OnboardingCoordinator onboarding = new OnboardingCoordinator();
        OnboardingCoordinator replay = new OnboardingCoordinator();

        boolean recipeIdentity = recipe.contains("minecraft:glass")
                && recipe.contains("minecraft:copper_ingot")
                && recipe.contains("minecraft:amethyst_shard")
                && recipe.contains("\"id\": \"cassicraft:weatherglass\"")
                && recipe.contains("\"count\": 1")
                && recipe.contains("\"GCG\"")
                && recipe.contains("\"AGA\"")
                && recipe.contains("\" C \"");
        boolean noExtraOutput = !recipe.contains("\"count\": 2") && !recipe.contains("energy") && !recipe.contains("matter");
        boolean sameContract = onboarding.discoveryText().equals(replay.discoveryText())
                && onboarding.classifyUse(false) == replay.classifyUse(false)
                && onboarding.classifyUse(true) == replay.classifyUse(true)
                && OnboardingCoordinator.PERSISTENCE_TIER.equals("SESSION_ONLY");
        boolean actionSeparation = onboarding.classifyUse(false) == OnboardingCoordinator.Action.FIELD_READ
                && onboarding.classifyUse(true) == OnboardingCoordinator.Action.EXPEDITION_START
                && onboarding.classifyUse(false) != onboarding.classifyUse(true);
        boolean teaching = advancement.contains("recipe_crafted")
                && advancement.contains("cassicraft:weatherglass")
                && advancement.contains("Plain use reads the local field. Sneak-use begins a Field Expedition.");
        boolean firstOnly = onboarding.observeCompletion(PLAYER) != null
                && onboarding.observeCompletion(PLAYER) == null
                && onboarding.hasCompletionReceipt(PLAYER);
        onboarding.clearSession();
        boolean sessionReset = !onboarding.hasCompletionReceipt(PLAYER)
                && onboarding.observeCompletion(PLAYER) != null;
        boolean noForbiddenPath = !OnboardingCoordinator.class.getName().contains("Command")
                && !OnboardingCoordinator.class.getName().contains("WorldWriter")
                && !OnboardingCoordinator.COMPLETION_RECEIPT.contains("energy minted")
                && !OnboardingCoordinator.COMPLETION_RECEIPT.contains("Q4");
        boolean honestPersistence = OnboardingCoordinator.PERSISTENCE_TIER.equals("SESSION_ONLY")
                && OnboardingCoordinator.COMPLETION_RECEIPT.contains("session-only");

        System.out.println("[onboarding] recipeIdentity=" + recipeIdentity + " oneOutput=" + noExtraOutput
                + " teaching=" + teaching + " sameContract=" + sameContract);
        System.out.println("[onboarding] actionSeparation=" + actionSeparation + " completionOnce=" + firstOnly
                + " sessionReset=" + sessionReset + " persistence=" + OnboardingCoordinator.PERSISTENCE_TIER);
        System.out.println("[onboarding] noCommandQ4WorldWriterPath=" + noForbiddenPath);
        if (!recipeIdentity || !noExtraOutput || !teaching || !sameContract || !actionSeparation
                || !firstOnly || !sessionReset || !noForbiddenPath || !honestPersistence) {
            throw new IllegalStateException("[onboarding] FAIL — frozen onboarding contract violated");
        }
        System.out.println("[onboarding] PASS — deterministic survival onboarding, separated actions, one bounded session receipt");
    }

    private OnboardingDeterminismMain() {}
}
