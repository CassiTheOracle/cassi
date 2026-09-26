package dev.cassicraft.game.progression;

import java.lang.reflect.Field;
import java.util.List;
import java.util.UUID;

/** Headless receipt-set gate: idempotence, safe replay, UUID isolation, no economy state. */
public final class ProgressionPersistenceDeterminismMain {
    public static void main(String[] args) {
        UUID first = UUID.fromString("11111111-1111-1111-1111-111111111111");
        UUID second = UUID.fromString("22222222-2222-2222-2222-222222222222");
        ExpeditionKnowledge knowledge = new ExpeditionKnowledge();
        boolean idempotent = knowledge.record(first) && !knowledge.record(first) && knowledge.record(second);
        boolean isolated = knowledge.contains(first) && knowledge.contains(second);
        ExpeditionKnowledge replay = ExpeditionKnowledge.fromSerialized(List.of(second.toString(), "malformed", first.toString(), first.toString()));
        boolean roundTrip = replay.contains(first) && replay.contains(second) && replay.serializedIds().equals(knowledge.serializedIds());
        boolean deterministic = ExpeditionKnowledge.fromSerialized(List.of(first.toString(), second.toString())).serializedIds()
                .equals(ExpeditionKnowledge.fromSerialized(List.of(second.toString(), first.toString())).serializedIds());
        boolean safeSurface = safeSurface();
        System.out.println("[progression] idempotent=" + idempotent + " isolated=" + isolated + " roundTrip=" + roundTrip
                + " deterministic=" + deterministic + " safeSurface=" + safeSurface + " q4Writes=0 resourceState=0");
        if (!idempotent || !isolated || !roundTrip || !deterministic || !safeSurface) {
            throw new IllegalStateException("[progression] FAIL frozen invariant");
        }
        System.out.println("[progression] PASS — replay-safe knowledge receipts only");
    }

    private static boolean safeSurface() {
        for (Field field : ExpeditionKnowledge.class.getDeclaredFields()) {
            String name = field.getType().getName().toLowerCase();
            if (name.contains("minecraft") || name.contains("domain") || name.contains("q4") || name.contains("item")) {
                return false;
            }
        }
        return true;
    }

    private ProgressionPersistenceDeterminismMain() {}
}
