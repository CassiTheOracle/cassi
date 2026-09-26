package dev.cassicraft.game.onboarding;

import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;

/** Vanilla chat presenter for the bounded onboarding receipt. */
public final class OnboardingPresenter {
    private OnboardingPresenter() {}

    public static void presentCompletion(ServerPlayer player, OnboardingCoordinator onboarding) {
        String receipt = onboarding.observeCompletion(player.getUUID());
        if (receipt != null) {
            player.sendSystemMessage(Component.literal(receipt));
        }
    }
}
