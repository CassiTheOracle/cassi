
// Throwaway smoke harness: shared weight-bank group host (two rows, different
// prompt lengths) driven through LlamaBackend::step_group, cross-checked against
// two independent single-row LlamaBackend::step continuations on the same model.
#include "llama_backend.hpp"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

constexpr const char* kModelSha =
    "57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf";
constexpr const char* kModelPath =
    "C:/Users/Carina/workspaces/Cassi/CassiQwen/Qwen3.5-0.8B-Q4_0.gguf";

const char* env_or(const char* name, const char* fallback) {
    const char* value = std::getenv(name);
    return value != nullptr && value[0] != '\0' ? value : fallback;
}

}  // namespace

int main() {
    const std::string model_path = env_or("CASSIFI_SMOKE_MODEL", kModelPath);
    const std::string source_sha = env_or("CASSIFI_SMOKE_SHA", kModelSha);
    const std::uint32_t decode_rounds = static_cast<std::uint32_t>(
        std::atoi(env_or("CASSIFI_SMOKE_DECODE", "3")));

    cassifi::field_runtime::LlamaBackend backend(0U, true);
    if (!backend.available()) {
        std::printf("FAIL backend unavailable: %s\n", backend.reason().c_str());
        return 1;
    }
    std::printf("loading model...\n");
    std::fflush(stdout);
    backend.register_model(source_sha, model_path, 128U, 0);
    std::printf("model loaded\n");
    std::fflush(stdout);

    const std::vector<std::int32_t> prompt_a =
        backend.tokenize(source_sha, "She opened the door and");
    const std::vector<std::int32_t> prompt_b =
        backend.tokenize(source_sha, "He looked up and");
    std::printf("prompt_a=%zu prompt_b=%zu\n", prompt_a.size(), prompt_b.size());

    // Independent single-row continuations (exact identity baseline).
    auto run_single = [&](const std::vector<std::int32_t>& prompt, std::string task_id,
                          std::uint32_t rounds) {
        std::vector<std::int32_t> tokens = prompt;
        const std::string sampler_sha = backend.effective_sampler_sha256(
            source_sha, "greedy", 0.0, 0, 0.0);
        for (std::uint32_t round = 0; round < rounds; ++round) {
            const auto result = backend.step(task_id, source_sha, tokens, "greedy", 0.0, 0U, 0.0,
                                             sampler_sha);
            tokens.push_back(result.token);
            if (result.end_of_generation) break;
        }
        return tokens;
    };
    std::printf("running baselines...\n");
    std::fflush(stdout);
    const auto baseline_a = run_single(prompt_a, "baseline-a", decode_rounds);
    const auto baseline_b = run_single(prompt_b, "baseline-b", decode_rounds);
    std::printf("baseline_a=%zu baseline_b=%zu\n", baseline_a.size(), baseline_b.size());
    std::fflush(stdout);

    // Shared multi-sequence group host: both rows replay and decode together.
    std::printf("creating group...\n");
    std::fflush(stdout);
    const auto group_id = backend.create_group(source_sha, 2U);
    
    std::vector<std::vector<std::int32_t>> committed(2);
    std::int32_t last_sampled[2] = {};
    bool last_sampled_valid[2] = {false, false};
    std::vector<std::int32_t> prompts[2] = {prompt_a, prompt_b};
    bool completed_flag[2] = {false, false};
    std::uint32_t rounds = 0;
    const std::uint32_t max_rounds =
        static_cast<std::uint32_t>(std::max(prompt_a.size(), prompt_b.size())) + decode_rounds + 2U;
    while (rounds < max_rounds && !(completed_flag[0] || completed_flag[1])) {
        std::fflush(stdout);
        ++rounds;
        std::vector<cassifi::field_runtime::ModelGroupRowRequest> requests(2U);
        for (std::size_t row = 0; row < 2U; ++row) {
            auto& request = requests[row];
            request.tokens = committed[row];
            const bool prompt_done = committed[row].size() >= prompts[row].size();
            if (!prompt_done) {
                request.next_token = prompts[row][committed[row].size()];
                request.accept_sampled = false;
            } else {
                if (!last_sampled_valid[row]) {
                    std::printf("FAIL row %zu prompt ended without a sampled token\n", row);
                    return 1;
                }
                request.next_token = last_sampled[row];
                request.accept_sampled = true;
            }
            request.sampler_mode = "greedy";
            request.temperature = 0.0;
            request.top_k = 0;
            request.draw = 0.0;
        }
        auto results = backend.step_group(group_id, requests);
        if (results.size() != 2U) {
            std::printf("FAIL group returned %zu rows\n", results.size());
            return 1;
        }
        // ModelStepResult.token is the row's accepted token; sampled_token is
        // the fused head sample kept for the next decode round.
        for (std::size_t row = 0; row < 2U; ++row) {
            // The fused head sample feeds the next decode round; the accepted
            // token is what the group actually committed for this row.
            last_sampled[row] = results[row].sampled_token;
            last_sampled_valid[row] = true;
            committed[row].push_back(results[row].token);
            completed_flag[row] = results[row].end_of_generation;
        }
    }
    // The group's committed row stream must equal the independent baseline stream
    // (the sample trail may exceed the baseline only if the baseline stopped on
    // EOG first; that shows up as a prefix match and identical flag counts).
    for (std::size_t row = 0; row < 2U; ++row) {
        const auto& baseline = row == 0 ? baseline_a : baseline_b;
        const auto& shared = committed[row];
        const auto common = std::min<std::size_t>(baseline.size(), shared.size());
        if (shared.size() < baseline.size() ||
                !std::equal(baseline.begin(), baseline.begin() + static_cast<std::ptrdiff_t>(baseline.size()),
                    shared.begin())) {
            std::printf("FAIL row %zu diverged from its independent baseline (rounds=%u)\n", row, rounds);
            std::printf("baseline:"); for (const auto token : baseline) std::printf(" %d", token);
            std::printf("\ngroup:"); for (const auto token : shared) std::printf(" %d", token);
            std::printf("\n");
            return 1;
        }
        std::printf("row %zu fused stream (%zu tokens) matched baseline\n", row, shared.size());
        std::printf("  tokens:");
        for (std::int32_t token : shared) {
            std::printf(" %d", token);
        }
        std::printf("\n");
    }
    std::printf("PASS fused 2-row group stage trace matched two independent single-row runs "
                "(rounds=%u)\n",
                rounds);
    if (backend.group_count() != 1U || !backend.drop_group(group_id) || backend.group_count() != 0U) {
        std::printf("FAIL group drop lifecycle\n");
        return 1;
    }

    // Churn phase: row 0 leaves mid-run, the retained row keeps decoding, and
    // the seat rejoins with a fresh prompt whose stream must match its own
    // independent baseline (replay from position 0 overwrites stale cells).
    if (baseline_a.size() <= prompt_a.size() + 1U) {
        std::printf("FAIL churn precondition: row 0 never sampled past its prompt\n");
        return 1;
    }
    const std::vector<std::int32_t> prompt_c =
        backend.tokenize(source_sha, "The tide went");
    std::printf("running churn baselines (prompt_c=%zu)...\n", prompt_c.size());
    std::fflush(stdout);
    const auto baseline_c = run_single(prompt_c, "baseline-c", decode_rounds);
    // The retained row must outlive the rejoined member's whole stream, so it
    // decodes against a longer independent baseline.
    const auto churn_decode_b = static_cast<std::uint32_t>(
        decode_rounds + prompt_c.size() + decode_rounds + prompt_a.size() + 4U);
    const auto baseline_b_long = run_single(prompt_b, "baseline-b-long", churn_decode_b);
    std::printf("churn creating group...\n");
    std::fflush(stdout);
    const auto churn_id = backend.create_group(source_sha, 2U);

    committed[0].clear();
    committed[1].clear();
    prompts[0] = prompt_a;
    prompts[1] = prompt_b;
    last_sampled_valid[0] = false;
    last_sampled_valid[1] = false;
    completed_flag[0] = false;
    completed_flag[1] = false;
    bool present[2] = {true, true};

    struct IdentitySnapshot {
        std::uint32_t row{};
        std::uint64_t generation{};
        const void* row_state{};
        const void* native_context{};
    };
    auto snapshot = [&](std::uint32_t row) {
        const auto identity = backend.group_row_identity(churn_id, row);
        return IdentitySnapshot{identity.row, identity.member_generation,
                                identity.row_state, identity.native_context};
    };
    const std::size_t churn_cap = prompt_a.size() + prompt_c.size() + prompt_b.size() +
                                  3U * decode_rounds + 10U;
    int churn_phase = 0;  // 0: pre-leave, 1: seat inactive, 2: rejoined
    std::uint32_t inactive_rounds = 0;
    std::uint32_t churn_rounds = 0;
    IdentitySnapshot id0_before{}, id0_after{}, id1_before{};

    while (churn_rounds < churn_cap && (present[0] || present[1])) {
        ++churn_rounds;
        std::vector<cassifi::field_runtime::ModelGroupRowRequest> requests(2U);
        for (std::size_t row = 0; row < 2U; ++row) {
            auto& request = requests[row];
            request.tokens = committed[row];
            const bool prompt_done = committed[row].size() >= prompts[row].size();
            if (!prompt_done) {
                request.next_token = prompts[row][committed[row].size()];
                request.accept_sampled = false;
            } else {
                if (!last_sampled_valid[row]) {
                    std::printf("FAIL churn row %zu prompt ended without a sampled token\n", row);
                    return 1;
                }
                request.next_token = last_sampled[row];
                request.accept_sampled = true;
            }
            request.sampler_mode = "greedy";
            request.temperature = 0.0;
            request.top_k = 0;
            request.draw = 0.0;
        }
        auto results = backend.step_group(churn_id, requests);
        if (results.size() != 2U) {
            std::printf("FAIL churn group returned %zu rows\n", results.size());
            return 1;
        }
        for (std::size_t row = 0; row < 2U; ++row) {
            if (!present[row]) {
                // An absent seat must neither complete nor grow its history.
                if (results[row].end_of_generation ||
                        results[row].token_count != committed[row].size()) {
                    std::printf(
                        "FAIL churn absent row %zu advanced (count=%llu expected=%zu)\n",
                        row, static_cast<unsigned long long>(results[row].token_count),
                        committed[row].size());
                    return 1;
                }
                continue;
            }
            last_sampled[row] = results[row].sampled_token;
            last_sampled_valid[row] = true;
            committed[row].push_back(results[row].token);
            completed_flag[row] = results[row].end_of_generation;
        }
        // A row is done when it hits end of generation or has run out its
        // independent baseline length; done rows leave their seats so the
        // remaining member can finish (absent seats are never rejoined here).
        for (std::size_t row = 0; row < 2U; ++row) {
            if (!present[row]) continue;
            bool done = completed_flag[row];
            if (row == 1 || churn_phase == 2) {
                const std::size_t target = (row == 1)
                    ? baseline_b_long.size()
                    : baseline_c.size();
                if (committed[row].size() >= target) done = true;
            }
            if (done) {
                backend.leave_group(churn_id, static_cast<std::uint32_t>(row));
                present[row] = false;
            }
        }
        if (churn_phase == 0 && present[0] && !completed_flag[0] &&
                committed[0].size() >= prompts[0].size() + 1U) {
            id0_before = snapshot(0);
            id1_before = snapshot(1);
            std::printf(
                "churn identity before leave: row0 gen=%llu rs=%p ctx=%p | "
                "row1 gen=%llu rs=%p ctx=%p\n",
                static_cast<unsigned long long>(id0_before.generation),
                id0_before.row_state, id0_before.native_context,
                static_cast<unsigned long long>(id1_before.generation),
                id1_before.row_state, id1_before.native_context);
            std::fflush(stdout);
            if (!backend.leave_group(churn_id, 0U) || backend.leave_group(churn_id, 0U)) {
                std::printf("FAIL leave_group is not once-true idempotent\n");
                return 1;
            }
            present[0] = false;
            churn_phase = 1;
            inactive_rounds = 0;
            std::printf("churn row 0 left mid-run (committed=%zu)\n", committed[0].size());
            std::fflush(stdout);
        } else if (churn_phase == 1 && !present[0]) {
            ++inactive_rounds;
            if (inactive_rounds >= 2U) {
                const auto id0_mid = snapshot(0);
                const auto id1_mid = snapshot(1);
                if (id0_mid.row_state != id0_before.row_state ||
                        id0_mid.native_context != id0_before.native_context ||
                        id0_mid.generation != id0_before.generation) {
                    std::printf("FAIL seat 0 identity changed while inactive\n");
                    return 1;
                }
                if (id1_mid.row_state != id1_before.row_state ||
                        id1_mid.native_context != id1_before.native_context ||
                        id1_mid.generation != id1_before.generation) {
                    std::printf("FAIL retained row 1 identity changed during churn\n");
                    return 1;
                }
                const auto rejoined = backend.join_group(churn_id);
                if (rejoined != 0) {
                    std::printf("FAIL join_group returned %lld, expected seat 0\n",
                                static_cast<long long>(rejoined));
                    return 1;
                }
                id0_after = snapshot(0);
                std::printf(
                    "churn identity after join: row0 gen=%llu rs=%p ctx=%p "
                    "(generation %s)\n",
                    static_cast<unsigned long long>(id0_after.generation),
                    id0_after.row_state, id0_after.native_context,
                    id0_after.generation == id0_before.generation + 1U
                        ? "bumped"
                        : "UNCHANGED");
                std::fflush(stdout);
                if (id0_after.row_state != id0_before.row_state ||
                        id0_after.native_context != id0_before.native_context ||
                        id0_after.generation != id0_before.generation + 1U) {
                    std::printf("FAIL seat 0 did not keep its seat with a bumped generation\n");
                    return 1;
                }
                committed[0].clear();
                prompts[0] = prompt_c;
                last_sampled_valid[0] = false;
                completed_flag[0] = false;
                present[0] = true;
                churn_phase = 2;
            }
        }
    }
    if (churn_phase != 2 || present[0] || present[1]) {
        std::printf("FAIL churn did not reach both finished after rejoin "
                    "(phase=%d present=%d,%d rounds=%u)\n",
                    churn_phase, present[0], present[1], churn_rounds);
        return 1;
    }
    for (std::size_t row = 0; row < 2U; ++row) {
        const auto& baseline = row == 0 ? baseline_c : baseline_b_long;
        const auto& shared = committed[row];
        if (shared.size() < baseline.size() ||
                !std::equal(baseline.begin(),
                            baseline.begin() + static_cast<std::ptrdiff_t>(baseline.size()),
                            shared.begin())) {
            std::printf("FAIL churn row %zu diverged from its independent baseline\n", row);
            std::printf("baseline:");
            for (const auto token : baseline) std::printf(" %d", token);
            std::printf("\ngroup:");
            for (const auto token : shared) std::printf(" %d", token);
            std::printf("\n");
            return 1;
        }
        std::printf("churn row %zu stream (%zu tokens) matched its baseline\n",
                    row, shared.size());
    }
    std::printf(
        "PASS churn: seat 0 left mid-run and rejoined with a generation bump while "
        "row 1 kept its identity; both streams matched independent baselines "
        "(rounds=%u)\n",
        churn_rounds);
    if (backend.group_count() != 1U || !backend.drop_group(churn_id) ||
            backend.group_count() != 0U) {
        std::printf("FAIL churn group drop lifecycle\n");
        return 1;
    }
    return 0;
}
