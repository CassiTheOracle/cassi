extern "C" {
#include "hash/sha256/sha256.h"
}

#include "common.h"
#include "llama-cassi.h"
#include "llama.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using session_ptr = std::unique_ptr<llama_cassi_context, decltype(&llama_cassi_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void set_u64_le(std::vector<uint8_t> & bytes, size_t offset, uint64_t value) {
    require(offset <= bytes.size() && bytes.size() - offset >= sizeof(value), "checkpoint revision offset is invalid");
    for (size_t index = 0; index < sizeof(value); ++index) {
        bytes[offset + index] = static_cast<uint8_t>((value >> (8 * index)) & 0xffU);
    }
}

void refresh_image_hash(std::vector<uint8_t> & bytes) {
    require(bytes.size() >= 32, "checkpoint is too short for an image hash");
    sha256_hash(bytes.data() + bytes.size() - 32, bytes.data(), bytes.size() - 32);
}

struct run_result {
    llama_cassi_token token = {};
    llama_cassi_stats stats = {};
};

run_result run_one(
        llama_cassi_context * session,
        const std::vector<llama_token> & prompt,
        bool exercise_pending_errors) {
    const int32_t begin_status = llama_cassi_begin(session, prompt.data(), prompt.size(), 1);
    require(begin_status == 0,
        std::string("begin failed: ") + llama_cassi_last_error(session));
    llama_cassi_token token = {};
    const llama_cassi_status next_status = llama_cassi_next(session, &token);
    if (next_status != LLAMA_CASSI_TOKEN) {
        llama_cassi_stats failure_stats = {};
        llama_cassi_get_stats(session, &failure_stats);
        throw std::runtime_error(
            std::string("next failed: ") + llama_cassi_last_error(session) +
            " service_calls=" + std::to_string(failure_stats.native_service_calls) +
            " prefill_tokens=" + std::to_string(failure_stats.native_prefill_tokens));
    }
    if (exercise_pending_errors) {
        llama_cassi_token untouched = {};
        require(llama_cassi_next(session, &untouched) == LLAMA_CASSI_ERROR &&
                std::strcmp(llama_cassi_last_error(session), "apprentice_invalid_transition") == 0,
            "pending next did not fail without consuming the result");
        const llama_token wrong = token.token == 0 ? 1 : 0;
        require(llama_cassi_accept(session, wrong) == -1 &&
                std::strcmp(llama_cassi_last_error(session), "apprentice_invalid_transition") == 0,
            "incorrect accept did not preserve the pending token");
    }
    const int32_t accept_status = llama_cassi_accept(session, token.token);
    require(accept_status == 0,
        std::string("accept failed: ") + llama_cassi_last_error(session));
    llama_cassi_token terminal = {};
    const llama_cassi_status terminal_status = llama_cassi_next(session, &terminal);
    require(terminal_status == LLAMA_CASSI_DONE,
        std::string("terminal next failed: ") + llama_cassi_last_error(session));
    const int32_t finish_status = llama_cassi_finish(session, false);
    require(finish_status == 0,
        std::string("finish failed: ") + llama_cassi_last_error(session));
    run_result result;
    result.token = token;
    llama_cassi_get_stats(session, &result.stats);
    return result;
}

llama_token greedy_teacher(
        llama_model * model,
        llama_context_params params,
        const std::vector<llama_token> & prompt) {
    context_ptr context(llama_init_from_model(model, params), llama_free);
    require(context != nullptr, "ordinary comparator context initialization failed");
    for (size_t index = 0; index < prompt.size(); ++index) {
        llama_token token = prompt[index];
        llama_pos position = static_cast<llama_pos>(index);
        int32_t n_seq_id = 1;
        llama_seq_id seq = 0;
        llama_seq_id * seq_ptr = &seq;
        int8_t logits = index + 1 == prompt.size() ? 1 : 0;
        llama_batch batch = {};
        batch.n_tokens = 1;
        batch.token = &token;
        batch.pos = &position;
        batch.n_seq_id = &n_seq_id;
        batch.seq_id = &seq_ptr;
        batch.logits = &logits;
        require(llama_decode(context.get(), batch) == 0, "ordinary comparator decode failed");
    }
    float * logits = llama_get_logits_ith(context.get(), -1);
    require(logits != nullptr, "ordinary comparator logits unavailable");
    const int32_t n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
    llama_token selected = 0;
    float best = -std::numeric_limits<float>::infinity();
    for (llama_token token = 0; token < n_vocab; ++token) {
        require(std::isfinite(logits[token]), "ordinary comparator produced nonfinite logits");
        if (logits[token] > best) {
            best = logits[token];
            selected = token;
        }
    }
    return selected;
}

} // namespace

int main(int argc, char ** argv) {
    if (argc < 6) {
        std::cerr << "usage: " << argv[0]
                  << " MODEL cpu|gpu FIELD_DEVICE OUTPUT_DIR MEMORY_MIB [--case lifecycle|transfer|pipeline]\n";
        return 2;
    }

    try {
        const std::string model_path = argv[1];
        const std::string native_device = argv[2];
        const std::string field_device = argv[3];
        const std::filesystem::path output_dir = argv[4];
        const uint64_t memory_mib = std::stoull(argv[5]);
        std::string selected_case = "lifecycle";
        if (argc == 8 && std::string(argv[6]) == "--case") {
            selected_case = argv[7];
        } else if (argc != 6) {
            throw std::runtime_error("invalid case arguments");
        }
        require(selected_case == "lifecycle" || selected_case == "transfer" || selected_case == "pipeline",
            "unsupported case");
        require(native_device == "cpu" || native_device == "gpu", "native device must be cpu or gpu");
        require(memory_mib > 0 && memory_mib <= UINT64_MAX / (1024 * 1024), "invalid memory budget");
        std::filesystem::create_directories(output_dir);

        ggml_backend_load_all();
        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = native_device == "gpu" ? 99 : 0;
        model_ptr model(llama_model_load_from_file(model_path.c_str(), model_params), llama_model_free);
        require(model != nullptr, "failed to load Qwen model");

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = 64;
        context_params.n_batch = 1;
        context_params.n_ubatch = 1;
        context_params.n_seq_max = 1;
        context_params.n_rs_seq = 0;
        context_params.cassi_modal = false;
        context_params.cassi_field_step = false;
        context_params.cassi_qi_field = false;
        context_params.no_perf = false;
        context_params.samplers = nullptr;
        context_params.n_samplers = 0;

        llama_cassi_params apprentice_params = llama_cassi_default_params();
        apprentice_params.memory_bytes = memory_mib * 1024 * 1024;
        apprentice_params.audit_interval = 0;
        apprentice_params.teacher_policy = LLAMA_CASSI_ADAPTIVE;
        apprentice_params.route_policy = LLAMA_CASSI_AUTO;
        apprentice_params.field_device = field_device.c_str();
        apprentice_params.model_path = model_path.c_str();
        if (selected_case == "pipeline") {
            apprentice_params.route_policy = LLAMA_CASSI_PIPELINE;
        }
        session_ptr session(
            llama_cassi_init(model.get(), context_params, apprentice_params), llama_cassi_free);
        require(session != nullptr, std::string("session initialization failed: ") + llama_cassi_last_error(nullptr));

        const llama_vocab * vocab = llama_model_get_vocab(model.get());
        std::vector<llama_token> prompt = common_tokenize(vocab, "Continue briefly. Label A:", true, true);
        require(!prompt.empty(), "test prompt tokenization failed");
        if (selected_case == "pipeline") {
            require(prompt.size() >= 2, "pipeline prompt did not contain two tokens");
            const std::vector<llama_token> pipeline_prompt(prompt.begin(), prompt.begin() + 2);
            const llama_token expected = greedy_teacher(model.get(), context_params, pipeline_prompt);
            const run_result first_pipeline = run_one(session.get(), pipeline_prompt, true);
            const run_result second_pipeline = run_one(session.get(), pipeline_prompt, false);
            const run_result field_pipeline = run_one(session.get(), pipeline_prompt, false);
            require(first_pipeline.token.token == expected && first_pipeline.token.native_dependency == 1 &&
                    first_pipeline.stats.full_teacher_queries == 0 &&
                    first_pipeline.stats.native_service_calls > 0 &&
                    first_pipeline.stats.native_logits_reads == 1 &&
                    first_pipeline.stats.field_observations > 4,
                "native service pipeline did not reproduce the ordinary greedy token");
            require(second_pipeline.token.token == expected && second_pipeline.stats.native_service_calls > 0,
                "second native service trajectory was not stable");
            require(field_pipeline.token.token == expected && field_pipeline.token.native_dependency == 0 &&
                    field_pipeline.token.decision_source == 0 &&
                    field_pipeline.stats.native_service_calls == 0 &&
                    field_pipeline.stats.full_teacher_queries == 0 &&
                    field_pipeline.stats.native_context_creations == 0 &&
                    field_pipeline.stats.native_logits_reads == 0 &&
                    field_pipeline.stats.native_cache_bytes_peak == 0 &&
                    field_pipeline.stats.logical_weight_bytes == 0 &&
                    field_pipeline.stats.native_ggml_nodes_executed == 0 &&
                    field_pipeline.stats.native_ggml_nodes_skipped > 0 &&
                    field_pipeline.stats.native_nodes_skipped_known,
                "mature pipeline did not become fully field-owned");
            const size_t trained_state_size = llama_cassi_state_size(session.get());
            std::vector<uint8_t> trained_checkpoint(trained_state_size);
            require(llama_cassi_state_get(
                        session.get(), trained_checkpoint.data(), trained_checkpoint.size()) ==
                    trained_checkpoint.size(),
                "trained pipeline checkpoint export failed");
            session_ptr fallback_session(
                llama_cassi_init(model.get(), context_params, apprentice_params), llama_cassi_free);
            require(fallback_session != nullptr &&
                    llama_cassi_state_set(
                        fallback_session.get(), trained_checkpoint.data(), trained_checkpoint.size()) == 0,
                "pipeline fallback session initialization failed");
            const std::vector<llama_token> alternate_tokens =
                common_tokenize(vocab, "A wholly unrelated request:", true, true);
            require(alternate_tokens.size() >= 2 && alternate_tokens[1] != pipeline_prompt[1],
                "pipeline fallback prompt did not diverge from the trained prefix");
            const std::vector<llama_token> alternate_prompt(
                alternate_tokens.begin(), alternate_tokens.begin() + 2);
            const run_result fallback = run_one(fallback_session.get(), alternate_prompt, false);
            const size_t fallback_layer_count =
                llama_cassi_attention_mask_get(fallback_session.get(), nullptr, 0);
            require(fallback_layer_count > 0, "pipeline fallback layer count was unavailable");
            const uint64_t fallback_observations =
                static_cast<uint64_t>(alternate_prompt.size()) *
                    (1 + 2 * fallback_layer_count) +
                8;
            require(fallback.token.native_dependency == 2 &&
                    fallback.stats.full_teacher_queries == 1 &&
                    fallback.stats.field_observations == fallback_observations,
                "failed field pipeline leaked staged service observations into teacher acceptance");
            session_ptr pipeline_rollback(
                llama_cassi_init(model.get(), context_params, apprentice_params), llama_cassi_free);
            require(pipeline_rollback != nullptr,
                std::string("pipeline rollback session initialization failed: ") +
                    llama_cassi_last_error(nullptr));
            const size_t rollback_state_size = llama_cassi_state_size(pipeline_rollback.get());
            std::vector<uint8_t> rollback_initial(rollback_state_size);
            require(llama_cassi_state_get(
                        pipeline_rollback.get(), rollback_initial.data(), rollback_initial.size()) ==
                    rollback_initial.size(),
                "pipeline rollback baseline export failed");
            require(llama_cassi_begin(
                        pipeline_rollback.get(), pipeline_prompt.data(), pipeline_prompt.size(), 1) == 0,
                "pipeline rollback begin failed");
            llama_cassi_token rollback_first = {};
            require(llama_cassi_next(pipeline_rollback.get(), &rollback_first) == LLAMA_CASSI_TOKEN &&
                    rollback_first.token == expected,
                "pipeline rollback first proposal failed");
            llama_cassi_stats rollback_pending_stats = {};
            llama_cassi_get_stats(pipeline_rollback.get(), &rollback_pending_stats);
            require(rollback_pending_stats.field_observations == 0 &&
                    rollback_pending_stats.pending_admission_payload_bytes_peak > 0 &&
                    rollback_pending_stats.pending_admission_payload_bytes_peak < rollback_pending_stats.field_bytes &&
                    rollback_pending_stats.pending_rollback_bytes_peak == 0,
                "pipeline proposal mutated or snapshotted the persistent field before acceptance");
            llama_cassi_cancel(pipeline_rollback.get());
            require(llama_cassi_accept(pipeline_rollback.get(), rollback_first.token) == -1 &&
                    llama_cassi_next(pipeline_rollback.get(), &rollback_first) ==
                        LLAMA_CASSI_CANCELLED &&
                    llama_cassi_finish(pipeline_rollback.get(), true) == 0,
                "pending pipeline cancellation did not fail closed");
            std::vector<uint8_t> rollback_cancelled(rollback_state_size);
            require(llama_cassi_state_get(
                        pipeline_rollback.get(),
                        rollback_cancelled.data(),
                        rollback_cancelled.size()) == rollback_cancelled.size() &&
                    rollback_cancelled == rollback_initial,
                "pending pipeline cancellation changed the field");
            require(llama_cassi_begin(
                        pipeline_rollback.get(), pipeline_prompt.data(), pipeline_prompt.size(), 1) == 0 &&
                    llama_cassi_next(pipeline_rollback.get(), &rollback_first) == LLAMA_CASSI_TOKEN &&
                    rollback_first.token == expected,
                "pipeline rollback replay proposal failed");
            require(llama_cassi_accept(pipeline_rollback.get(), rollback_first.token) == 0 &&
                    llama_cassi_rollback_accepted(pipeline_rollback.get()) == 0,
                "accepted pipeline transaction did not roll back");
            std::vector<uint8_t> rollback_restored(rollback_state_size);
            require(llama_cassi_state_get(
                        pipeline_rollback.get(), rollback_restored.data(), rollback_restored.size()) ==
                    rollback_restored.size() &&
                    rollback_restored == rollback_initial,
                "pipeline rollback did not restore the initial field");
            llama_cassi_stats pipeline_rollback_stats = {};
            llama_cassi_get_stats(pipeline_rollback.get(), &pipeline_rollback_stats);
            require(pipeline_rollback_stats.field_observations == 0 &&
                    pipeline_rollback_stats.engram_evictions == 0,
                "accepted pipeline rollback left field receipt counters");
            llama_cassi_token rollback_second = {};
            require(llama_cassi_next(pipeline_rollback.get(), &rollback_second) == LLAMA_CASSI_TOKEN &&
                    rollback_second.token == rollback_first.token &&
                    rollback_second.native_dependency == rollback_first.native_dependency,
                "pipeline rollback did not rebuild the native service prefix");
            require(llama_cassi_accept(pipeline_rollback.get(), rollback_second.token) == 0 &&
                    llama_cassi_finish(pipeline_rollback.get(), false) == 0,
                "pipeline rollback replay did not complete");
            const size_t mask_size = llama_cassi_attention_mask_get(session.get(), nullptr, 0);
            llama_cassi_info pipeline_info = {};
            std::vector<uint8_t> attention_mask(mask_size);
            require(llama_cassi_get_info(session.get(), &pipeline_info) == 0 &&
                    mask_size == pipeline_info.layers &&
                    llama_cassi_attention_mask_get(session.get(), attention_mask.data(), attention_mask.size()) == mask_size,
                "attention-service ownership mask was unavailable");
            const uint64_t attention_owned = std::count(attention_mask.begin(), attention_mask.end(), uint8_t{1});
            const size_t service_count = llama_cassi_service_stats_count(session.get());
            std::vector<llama_cassi_service_stats> service_stats(service_count);
            require(llama_cassi_service_stats_get(session.get(), service_stats.data(), service_stats.size()) == service_count,
                "pipeline service statistics were unavailable");
            uint64_t service_computed = 0;
            uint64_t service_skipped = 0;
            for (const llama_cassi_service_stats & item : service_stats) {
                service_computed += item.computed;
                service_skipped += item.skipped;
            }
            std::cout << "{\"schema\":\"cassi.apprentice.native-test.v1\","
                      << "\"case\":\"pipeline\",\"verdict\":\"PASS\","
                      << "\"field_device\":\"" << field_device << "\","
                      << "\"token\":" << field_pipeline.token.token << ","
                      << "\"trained_native_service_calls\":" << first_pipeline.stats.native_service_calls << ","
                      << "\"field_native_service_calls\":" << field_pipeline.stats.native_service_calls << ","
                      << "\"field_nodes_skipped\":" << field_pipeline.stats.native_ggml_nodes_skipped << ","
                      << "\"attention_service_owned_layers\":" << attention_owned << ","
                      << "\"attention_service_total_layers\":" << mask_size << ","
                      << "\"native_cache_tensor_bytes_displaced\":"
                      << (first_pipeline.stats.native_cache_bytes_peak - field_pipeline.stats.native_cache_bytes_peak) << ","
                      << "\"field_service_computed\":" << service_computed << ","
                      << "\"field_service_skipped\":" << service_skipped << ","
                      << "\"field_bytes\":" << first_pipeline.stats.field_bytes << ","
                      << "\"pending_admission_payload_bytes_peak\":"
                      << first_pipeline.stats.pending_admission_payload_bytes_peak << ","
                      << "\"pending_rollback_bytes_peak\":"
                      << first_pipeline.stats.pending_rollback_bytes_peak << "}\n";
            return 0;
        }

        const size_t state_size = llama_cassi_state_size(session.get());
        llama_cassi_stats initial_stats = {};
        llama_cassi_get_stats(session.get(), &initial_stats);
        require(state_size > initial_stats.field_bytes, "checkpoint size does not include field header");
        std::vector<uint8_t> short_buffer(32, 0xa5);
        require(llama_cassi_state_get(session.get(), short_buffer.data(), short_buffer.size()) == 0 &&
                std::all_of(short_buffer.begin(), short_buffer.end(), [](uint8_t value) { return value == 0xa5; }),
            "short state export performed a partial write");

        std::vector<uint8_t> initial_checkpoint(state_size);
        require(llama_cassi_state_get(session.get(), initial_checkpoint.data(), initial_checkpoint.size()) ==
                    initial_checkpoint.size(),
            "initial state export failed");
        llama_cassi_info initial_info = {};
        require(llama_cassi_get_info(session.get(), &initial_info) == 0 && initial_info.field_revision == 0,
            "initial field revision was not zero");
        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 1) == 0,
            "teacher cancellation begin failed");
        llama_cassi_token unaccepted_teacher_token = {};
        require(llama_cassi_next(session.get(), &unaccepted_teacher_token) == LLAMA_CASSI_TOKEN &&
                unaccepted_teacher_token.native_dependency == 2,
            "teacher cancellation next did not produce a pending teacher token");
        llama_cassi_stats pending_teacher_stats = {};
        llama_cassi_get_stats(session.get(), &pending_teacher_stats);
        require(pending_teacher_stats.field_observations == 0 &&
                pending_teacher_stats.pending_admission_payload_bytes_peak > 0 &&
                pending_teacher_stats.pending_admission_payload_bytes_peak < pending_teacher_stats.field_bytes &&
                pending_teacher_stats.pending_rollback_bytes_peak == 0,
            "unaccepted teacher proposal mutated or snapshotted the persistent field");
        llama_cassi_cancel(session.get());
        require(llama_cassi_accept(session.get(), unaccepted_teacher_token.token) == -1 &&
                llama_cassi_next(session.get(), &unaccepted_teacher_token) == LLAMA_CASSI_CANCELLED,
            "pending teacher cancellation did not fail closed");
        require(llama_cassi_finish(session.get(), true) == 0, "teacher cancellation finish failed");
        llama_cassi_info cancelled_teacher_info = {};
        require(llama_cassi_get_info(session.get(), &cancelled_teacher_info) == 0 &&
                cancelled_teacher_info.field_revision == initial_info.field_revision,
            "unaccepted teacher observations changed the retained revision");
        std::vector<uint8_t> cancelled_teacher_checkpoint(state_size);
        require(llama_cassi_state_get(
                    session.get(), cancelled_teacher_checkpoint.data(), cancelled_teacher_checkpoint.size()) ==
                    cancelled_teacher_checkpoint.size() &&
                cancelled_teacher_checkpoint == initial_checkpoint,
            "unaccepted teacher observations survived cancellation");

        const size_t service_layer_count = llama_cassi_attention_mask_get(session.get(), nullptr, 0);
        require(service_layer_count > 0, "apprenticeship service layer count was unavailable");
        const uint64_t teacher_observations_per_run =
            static_cast<uint64_t>(prompt.size()) * (1 + 2 * service_layer_count) + 8;
        const run_result first = run_one(session.get(), prompt, true);
        require(first.token.native_dependency == 2 && first.token.readout_kind == 2 &&
                first.stats.full_teacher_queries == 1 &&
                first.stats.field_observations == teacher_observations_per_run &&
                first.stats.pending_admission_payload_bytes_peak > 0 &&
                first.stats.pending_admission_payload_bytes_peak < first.stats.field_bytes &&
                first.stats.pending_rollback_bytes_peak == first.stats.field_bytes &&
                first.stats.committed_tokens == 1 && first.stats.teacher_guided_tokens == 1,
            "first trajectory was not explicitly teacher-guided and transactionally admitted");
        const run_result second = run_one(session.get(), prompt, false);
        require(second.token.token == first.token.token && second.token.native_dependency == 2 &&
                second.stats.field_observations == teacher_observations_per_run,
            "second bootstrap trajectory did not repeat and validate the teacher association");
        const run_result third = run_one(session.get(), prompt, false);
        require(third.token.token == first.token.token && third.token.native_dependency == 0 &&
                third.token.decision_source == 0 && third.token.readout_kind == 0 &&
                third.stats.full_teacher_queries == 0 && third.stats.field_observations == 0 &&
                third.stats.field_exact_tokens == 1,
            "mature text engrams did not replay without native execution");

        llama_cassi_stats before_exact_rollback_stats = {};
        llama_cassi_get_stats(session.get(), &before_exact_rollback_stats);
        std::vector<uint8_t> before_exact_rollback(state_size);
        require(llama_cassi_state_get(
                    session.get(), before_exact_rollback.data(), before_exact_rollback.size()) ==
                    before_exact_rollback.size(),
            "exact rollback baseline export failed");
        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 1) == 0,
            "exact rollback begin failed");
        llama_cassi_token exact_pending = {};
        require(llama_cassi_next(session.get(), &exact_pending) == LLAMA_CASSI_TOKEN &&
                exact_pending.readout_kind == 0 && exact_pending.native_dependency == 0,
            "exact rollback probe was not field-owned");
        require(llama_cassi_accept(session.get(), exact_pending.token) == 0,
            "exact rollback accept failed");
        require(llama_cassi_rollback_accepted(session.get()) == 0,
            "exact accepted transaction did not roll back");
        require(llama_cassi_finish(session.get(), true) == 0,
            "exact rollback finish failed");
        std::vector<uint8_t> after_exact_rollback(state_size);
        require(llama_cassi_state_get(
                    session.get(), after_exact_rollback.data(), after_exact_rollback.size()) ==
                    after_exact_rollback.size() &&
                after_exact_rollback == before_exact_rollback,
            "exact accepted transaction changed the field after rollback");
        llama_cassi_stats exact_rollback_stats = {};
        llama_cassi_get_stats(session.get(), &exact_rollback_stats);
        require(exact_rollback_stats.committed_tokens == 0 &&
                exact_rollback_stats.field_exact_tokens == 0 &&
                exact_rollback_stats.field_observations == 0 &&
                exact_rollback_stats.engram_evictions ==
                    before_exact_rollback_stats.engram_evictions,
            "exact rollback left committed-token or field accounting");

        llama_cassi_info info = {};
        require(llama_cassi_get_info(session.get(), &info) == 0 &&
                info.field_revision == 2 * teacher_observations_per_run &&
                info.field_bytes == third.stats.field_bytes,
            std::string("session info failed: ") + llama_cassi_last_error(session.get()));
        require(std::any_of(std::begin(info.model_sha256), std::end(info.model_sha256), [](uint8_t value) { return value != 0; }) &&
                std::any_of(std::begin(info.profile_sha256), std::end(info.profile_sha256), [](uint8_t value) { return value != 0; }),
            "session identities are empty");
        std::vector<uint8_t> checkpoint(state_size);
        require(llama_cassi_state_get(session.get(), checkpoint.data(), checkpoint.size()) == checkpoint.size(),
            std::string("state export failed: ") + llama_cassi_last_error(session.get()));

        llama_cassi_params context_teacher_params = apprentice_params;
        context_teacher_params.teacher_policy = LLAMA_CASSI_ALWAYS;
        session_ptr context_teacher_session(
            llama_cassi_init(model.get(), context_params, context_teacher_params), llama_cassi_free);
        require(context_teacher_session != nullptr &&
                llama_cassi_state_set(
                    context_teacher_session.get(), checkpoint.data(), checkpoint.size()) == 0,
            "context rollback teacher initialization failed");
        const auto run_audited_pair = [&]() {
            std::array<llama_token, 2> tokens = {};
            require(llama_cassi_begin(
                        context_teacher_session.get(), prompt.data(), prompt.size(), 2) == 0,
                "context rollback training begin failed");
            for (size_t index = 0; index < tokens.size(); ++index) {
                llama_cassi_token proposed = {};
                require(llama_cassi_next(context_teacher_session.get(), &proposed) == LLAMA_CASSI_TOKEN &&
                        proposed.native_dependency == 2,
                    "context rollback training proposal failed");
                tokens[index] = proposed.token;
                require(llama_cassi_accept(context_teacher_session.get(), proposed.token) == 0,
                    "context rollback training accept failed");
            }
            llama_cassi_token terminal = {};
            require(llama_cassi_next(context_teacher_session.get(), &terminal) == LLAMA_CASSI_DONE &&
                    llama_cassi_finish(context_teacher_session.get(), false) == 0,
                "context rollback training request did not complete");
            return tokens;
        };
        const std::array<llama_token, 2> first_audited_pair = run_audited_pair();
        const std::array<llama_token, 2> second_audited_pair = run_audited_pair();
        require(first_audited_pair == second_audited_pair &&
                first_audited_pair[0] != first_audited_pair[1],
            "context rollback training trajectory was not stable or discriminating");
        const size_t context_state_size = llama_cassi_state_size(context_teacher_session.get());
        std::vector<uint8_t> context_checkpoint(context_state_size);
        require(llama_cassi_state_get(
                    context_teacher_session.get(), context_checkpoint.data(), context_checkpoint.size()) ==
                    context_checkpoint.size(),
            "context rollback training checkpoint export failed");
        llama_cassi_params context_rollback_params = apprentice_params;
        context_rollback_params.audit_interval = 1;
        session_ptr context_rollback_session(
            llama_cassi_init(model.get(), context_params, context_rollback_params), llama_cassi_free);
        require(context_rollback_session != nullptr &&
                llama_cassi_state_set(
                    context_rollback_session.get(), context_checkpoint.data(), context_checkpoint.size()) == 0,
            "context rollback session initialization failed");
        require(llama_cassi_begin(
                    context_rollback_session.get(), prompt.data(), prompt.size(), 2) == 0,
            "context rollback probe begin failed");
        std::vector<uint8_t> context_before(context_state_size);
        require(llama_cassi_state_get(
                    context_rollback_session.get(), context_before.data(), context_before.size()) ==
                    context_before.size(),
            "context rollback baseline export failed");
        llama_cassi_stats context_before_stats = {};
        llama_cassi_get_stats(context_rollback_session.get(), &context_before_stats);
        llama_cassi_token context_first = {};
        require(llama_cassi_next(context_rollback_session.get(), &context_first) == LLAMA_CASSI_TOKEN &&
                context_first.token == second_audited_pair[0] &&
                context_first.native_dependency == 2 &&
                context_first.decision_source == 0 &&
                context_first.readout_kind == 0,
            "context rollback probe was not an audited exact field decision");
        require(llama_cassi_accept(context_rollback_session.get(), context_first.token) == 0,
            "context rollback learning accept failed");
        llama_cassi_stats context_accepted_stats = {};
        llama_cassi_get_stats(context_rollback_session.get(), &context_accepted_stats);
        require(context_accepted_stats.field_observations > context_before_stats.field_observations &&
                context_accepted_stats.pending_rollback_bytes_peak ==
                    context_accepted_stats.field_bytes,
            "context rollback probe did not enter the full-field learning transaction");
        std::vector<uint8_t> context_accepted(context_state_size);
        require(llama_cassi_state_get(
                    context_rollback_session.get(), context_accepted.data(), context_accepted.size()) ==
                    context_accepted.size(),
            "context rollback accepted-state export failed");
        require(llama_cassi_rollback_accepted(context_rollback_session.get()) == 0,
            "full-field context transaction did not roll back");
        std::vector<uint8_t> context_after(context_state_size);
        require(llama_cassi_state_get(
                    context_rollback_session.get(), context_after.data(), context_after.size()) ==
                    context_after.size() &&
                context_after == context_before,
            "full-field context rollback changed persistent field state");
        llama_cassi_stats context_after_stats = {};
        llama_cassi_get_stats(context_rollback_session.get(), &context_after_stats);
        require(context_after_stats.field_observations == context_before_stats.field_observations &&
                context_after_stats.engram_evictions == context_before_stats.engram_evictions &&
                context_after_stats.committed_tokens == context_before_stats.committed_tokens,
            "full-field context rollback left receipt accounting");
        llama_cassi_token context_replayed = {};
        require(llama_cassi_next(context_rollback_session.get(), &context_replayed) == LLAMA_CASSI_TOKEN &&
                context_replayed.token == context_first.token &&
                context_replayed.native_dependency == 2 &&
                context_replayed.decision_source == 0 &&
                context_replayed.readout_kind == 0,
            "full-field rollback did not restore the pre-accept context");
        require(llama_cassi_accept(context_rollback_session.get(), context_replayed.token) == 0,
            "post-rollback first token did not reaccept");
        std::vector<uint8_t> context_reaccepted(context_state_size);
        require(llama_cassi_state_get(
                    context_rollback_session.get(), context_reaccepted.data(), context_reaccepted.size()) ==
                    context_reaccepted.size() &&
                context_reaccepted == context_accepted,
            "post-rollback reaccept did not reproduce the original field transition");
        llama_cassi_token context_second = {};
        require(llama_cassi_next(context_rollback_session.get(), &context_second) == LLAMA_CASSI_TOKEN &&
                context_second.token == second_audited_pair[1] &&
                context_second.native_dependency == 2 &&
                context_second.decision_source == 0 &&
                context_second.readout_kind == 0,
            "post-rollback context did not continue along the learned trajectory");
        require(llama_cassi_accept(context_rollback_session.get(), context_second.token) == 0,
            "post-rollback second token did not accept");
        llama_cassi_token context_terminal = {};
        require(llama_cassi_next(context_rollback_session.get(), &context_terminal) == LLAMA_CASSI_DONE &&
                llama_cassi_finish(context_rollback_session.get(), false) == 0,
            "post-rollback learned continuation did not complete");
        std::vector<uint8_t> corrupted = checkpoint;
        corrupted.back() ^= 0x80;
        require(llama_cassi_state_set(session.get(), corrupted.data(), corrupted.size()) == -1 &&
                std::strcmp(llama_cassi_last_error(session.get()), "apprentice_checkpoint_invalid") == 0,
            "corrupt checkpoint was accepted");
        std::vector<uint8_t> after_rejection(state_size);
        require(llama_cassi_state_get(session.get(), after_rejection.data(), after_rejection.size()) == after_rejection.size() &&
                after_rejection == checkpoint,
            "failed checkpoint import mutated the field");
        require(llama_cassi_state_set(session.get(), checkpoint.data(), checkpoint.size()) == 0,
            "valid checkpoint did not round-trip");
        std::vector<uint8_t> terminal_revision = checkpoint;
        set_u64_le(terminal_revision, 48, std::numeric_limits<uint64_t>::max());
        refresh_image_hash(terminal_revision);
        require(llama_cassi_state_set(session.get(), terminal_revision.data(), terminal_revision.size()) == -1 &&
                std::strcmp(llama_cassi_last_error(session.get()), "apprentice_checkpoint_invalid") == 0,
            "maximum-revision checkpoint was accepted");
        require(llama_cassi_state_get(session.get(), after_rejection.data(), after_rejection.size()) ==
                    after_rejection.size() &&
                after_rejection == checkpoint,
            "maximum-revision checkpoint rejection mutated the field");

        llama_cassi_params revision_params = apprentice_params;
        revision_params.teacher_policy = LLAMA_CASSI_ALWAYS;
        session_ptr revision_session(
            llama_cassi_init(model.get(), context_params, revision_params), llama_cassi_free);
        require(revision_session != nullptr,
            std::string("revision-boundary session initialization failed: ") +
                llama_cassi_last_error(nullptr));
        std::vector<uint8_t> near_terminal_revision = checkpoint;
        set_u64_le(
            near_terminal_revision,
            48,
            std::numeric_limits<uint64_t>::max() - 1);
        refresh_image_hash(near_terminal_revision);
        require(llama_cassi_state_set(
                    revision_session.get(),
                    near_terminal_revision.data(),
                    near_terminal_revision.size()) == 0,
            "maximum-minus-one revision checkpoint was rejected");
        require(llama_cassi_begin(
                    revision_session.get(), prompt.data(), prompt.size(), 1) == 0,
            "revision-boundary begin failed");
        llama_cassi_token revision_pending = {};
        require(llama_cassi_next(revision_session.get(), &revision_pending) == LLAMA_CASSI_TOKEN &&
                revision_pending.native_dependency == 2,
            "revision-boundary teacher proposal failed");
        llama_cassi_stats revision_pending_stats = {};
        llama_cassi_get_stats(revision_session.get(), &revision_pending_stats);
        require(revision_pending_stats.field_observations == 0 &&
                revision_pending_stats.pending_admission_payload_bytes_peak > 0 &&
                revision_pending_stats.pending_rollback_bytes_peak == 0,
            "revision-boundary proposal mutated the field before acceptance");
        require(llama_cassi_accept(revision_session.get(), revision_pending.token) == -1 &&
                std::strcmp(
                    llama_cassi_last_error(revision_session.get()),
                    "apprentice_field_revision_overflow") == 0,
            "maximum-minus-one revision accepted a mutating transaction");
        llama_cassi_stats revision_failed_stats = {};
        llama_cassi_get_stats(revision_session.get(), &revision_failed_stats);
        require(revision_failed_stats.field_observations == 0 &&
                revision_failed_stats.pending_rollback_bytes_peak == 0,
            "revision-boundary preflight allocated rollback state or changed observation accounting");
        require(llama_cassi_finish(revision_session.get(), true) == 0,
            "revision-boundary finish failed");
        std::vector<uint8_t> after_revision_failure(state_size);
        require(llama_cassi_state_get(
                    revision_session.get(),
                    after_revision_failure.data(),
                    after_revision_failure.size()) == after_revision_failure.size(),
            "revision-boundary rollback state export failed");
        const auto revision_mismatch = std::mismatch(
            after_revision_failure.begin(), after_revision_failure.end(), near_terminal_revision.begin());
        require(revision_mismatch.first == after_revision_failure.end(),
            "revision-boundary failure changed field or context bytes at offset " +
                std::to_string(static_cast<size_t>(
                    std::distance(after_revision_failure.begin(), revision_mismatch.first))));

        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 1) == 0, "cancel begin failed");
        llama_cassi_token cancelled_token = {};
        require(llama_cassi_next(session.get(), &cancelled_token) == LLAMA_CASSI_TOKEN, "cancel next failed");
        llama_cassi_cancel(session.get());
        require(llama_cassi_accept(session.get(), cancelled_token.token) == -1 &&
                llama_cassi_next(session.get(), &cancelled_token) == LLAMA_CASSI_CANCELLED,
            "pending cancellation did not fail closed");
        require(llama_cassi_finish(session.get(), true) == 0, "cancel finish failed");
        llama_cassi_info cancelled_info = {};
        require(llama_cassi_get_info(session.get(), &cancelled_info) == 0 &&
                cancelled_info.field_revision == info.field_revision,
            "cancelled field-only output changed retained learning");

        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 0) == 0, "zero-predict begin failed");
        llama_cassi_token no_token = {};
        require(llama_cassi_next(session.get(), &no_token) == LLAMA_CASSI_DONE, "zero-predict request executed inference");
        require(llama_cassi_finish(session.get(), false) == 0, "zero-predict finish failed");

        std::cout << "{\"schema\":\"cassi.apprentice.native-test.v1\","
                  << "\"case\":\"" << selected_case << "\","
                  << "\"verdict\":\"PASS\","
                  << "\"field_device\":\"" << field_device << "\","
                  << "\"teacher_token\":" << first.token.token << ","
                  << "\"field_revision\":" << info.field_revision << ","
                  << "\"field_bytes\":" << info.field_bytes << ","
                  << "\"checkpoint_bytes\":" << checkpoint.size() << ","
                  << "\"pending_admission_payload_bytes_peak\":"
                  << pending_teacher_stats.pending_admission_payload_bytes_peak << ","
                  << "\"pending_rollback_bytes_peak\":"
                  << first.stats.pending_rollback_bytes_peak << ","
                  << "\"revision_overflow_rollback_bytes_peak\":"
                  << revision_failed_stats.pending_rollback_bytes_peak << "}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL test-cassi-apprentice-qwen: " << error.what() << "\n";
        return 1;
    }
}
