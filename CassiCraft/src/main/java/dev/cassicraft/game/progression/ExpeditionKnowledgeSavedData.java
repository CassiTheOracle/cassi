package dev.cassicraft.game.progression;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.resources.Identifier;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.saveddata.SavedDataType;
import java.util.List;
import java.util.UUID;

/** World-saved completed-expedition knowledge receipts; no active expedition state. */
public final class ExpeditionKnowledgeSavedData extends SavedData {
    private static final Codec<ExpeditionKnowledgeSavedData> CODEC = RecordCodecBuilder.create(instance -> instance.group(
            Codec.INT.optionalFieldOf("version", ExpeditionKnowledge.VERSION).forGetter(data -> ExpeditionKnowledge.VERSION),
            Codec.STRING.listOf().optionalFieldOf("completed", List.of()).forGetter(data -> List.copyOf(data.knowledge.serializedIds()))
    ).apply(instance, (version, identifiers) -> new ExpeditionKnowledgeSavedData(ExpeditionKnowledge.fromSerialized(identifiers))));

    public static final SavedDataType<ExpeditionKnowledgeSavedData> TYPE = new SavedDataType<>(
            Identifier.fromNamespaceAndPath("cassicraft", "expedition_knowledge"),
            ExpeditionKnowledgeSavedData::new,
            CODEC,
            DataFixTypes.SAVED_DATA_MAP_DATA
    );

    private final ExpeditionKnowledge knowledge;

    public ExpeditionKnowledgeSavedData() {
        this(new ExpeditionKnowledge());
    }

    private ExpeditionKnowledgeSavedData(ExpeditionKnowledge knowledge) {
        this.knowledge = knowledge;
    }

    /** True and dirty only for a newly recorded completed-expedition receipt. */
    public boolean record(UUID playerId) {
        boolean changed = knowledge.record(playerId);
        if (changed) {
            setDirty();
        }
        return changed;
    }

    public boolean contains(UUID playerId) {
        return knowledge.contains(playerId);
    }
}
