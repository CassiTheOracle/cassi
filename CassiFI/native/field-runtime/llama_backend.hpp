#pragma once

#include "protocol.hpp"
#include "field_image.hpp"
#include <algorithm>

#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#ifdef CASSIFI_HAVE_LLAMA
#include "llama-cassi.h"
#include "llama.h"
#endif

namespace cassifi::field_runtime {

struct ModelRegistration {
    std::string status;
    std::string source_sha256;
    std::string description;
    std::uint64_t vocabulary_size{};
    std::uint64_t context_size{};
    std::uint64_t model_bytes{};
};

struct ModelStepResult {
    std::int32_t token{};
    bool end_of_generation{};
    // Multi-row group hosts: the fused head sample for this row, distinct from
    // `token` when a prompt-replay round commits the prompt token instead.
    std::int32_t sampled_token{};
    std::string replay_sha256;
    std::uint64_t token_count{};
    std::string stage_trace_sha256;
    std::uint64_t exact_stages{};
    std::uint64_t embedding_stages{};
    std::uint64_t attention_stages{};
    std::uint64_t ffn_stages{};
    std::uint64_t head_stages{};
    std::uint64_t ggml_nodes{};
    std::uint64_t logical_weight_bytes{};
    std::int32_t seq_id{};
    std::int32_t position{};
    bool accepted{true};
    bool draft_matched{false};
    std::string native_operation_id{};
    std::string sequence_id{};
    std::string input_tokens_sha256{};
    std::string sampler_sha256{};
    std::string native_predecessor_sha256{};
    std::string native_successor_sha256{};
    std::optional<GraphSiteReceiptWire> graph_site_receipt{};
    std::string graph_receipt_wire_sha256{};
    std::string native_graph_site_receipt_sha256{};
    std::string field_candidate_id{};
    std::string ticket_id{};
    bool graph_site_rejected{};
};

#ifdef CASSIFI_HAVE_LLAMA

// Shared weight-bank group row request. `tokens` is the row's committed history
// (empty at group creation; grows by exactly one accepted token per round) and
// `next_token` is the token committed in this round. Prompt replay may supply
// any valid token; once decoding, `accept_sampled` requires `next_token` to
// equal the previous round's head sample. The current head sample is returned
// for the following round, after the committed token has reached every stage.
struct ModelGroupRowRequest {
    std::vector<std::int32_t> tokens;
    std::int32_t next_token{};
    bool accept_sampled{};
    std::string sampler_mode;
    double temperature{};
    std::uint32_t top_k{};
    double draw{};
};

using ModelGroupId = std::uint64_t;


class LlamaBackend {
public:
    explicit LlamaBackend(std::uint32_t device_index, bool enabled = true)
        : device_index_(device_index), disabled_(!enabled) {
        if (!enabled) return;
        ::llama_backend_init();
        initialized_ = true;
    }

    LlamaBackend(const LlamaBackend&) = delete;
    LlamaBackend& operator=(const LlamaBackend&) = delete;

    ~LlamaBackend() {
        tasks_.clear();
        models_.clear();
        if (initialized_) ::llama_backend_free();
    }

    [[nodiscard]] bool available() const noexcept { return initialized_; }
    [[nodiscard]] std::string reason() const { return initialized_ ? std::string{} : (disabled_ ? "disabled by --cpu-only" : "llama.cpp backend is unavailable"); }
    [[nodiscard]] std::size_t task_count() const noexcept { return tasks_.size(); }
    [[nodiscard]] std::size_t model_count() const noexcept { return models_.size(); }

    std::string effective_sampler_sha256(
        const std::string& source_sha256,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw) const {
        const auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        const auto& model = *model_found->second;
        const auto sampler = sampler_from_request(sampler_mode, temperature, top_k, draw,
            static_cast<std::uint32_t>(llama_vocab_n_tokens(model.vocab)));
        std::array<char, 65> digest{};
        if (llama_cassi_sampler_sha256(sampler, digest.data()) != 0)
            throw ProtocolError("llama.cpp could not hash the effective sampler tuple");
        const std::string result(digest.data());
        require_hex_sha256(result, "effective sampler_sha256");
        return result;
    }

    ModelRegistration register_model(
        const std::string& source_sha256,
        const std::string& path,
        std::uint32_t context_size,
        std::int32_t gpu_layers) {
        require_hex_sha256(source_sha256, "model source_sha256");
        if (path.empty() || path.size() > 32'768U) throw ProtocolError("model path is invalid");
        if (context_size < 2U || context_size > 1'048'576U) throw ProtocolError("model context size is outside its bound");
        if (auto found = models_.find(source_sha256); found != models_.end()) {
            if (found->second->path != path || found->second->context_size != context_size || found->second->gpu_layers != gpu_layers) {
                throw ProtocolError("model identity is already bound to different loading parameters");
            }
            return describe(*found->second, "already-loaded");
        }

        auto params = llama_model_default_params();
        params.n_gpu_layers = gpu_layers;
        params.main_gpu = static_cast<std::int32_t>(device_index_);
        params.check_tensors = true;
        auto* raw_model = llama_model_load_from_file(path.c_str(), params);
        if (!raw_model) throw ProtocolError("llama.cpp could not load the registered GGUF model");

        auto entry = std::make_unique<Model>();
        entry->source_sha256 = source_sha256;
        entry->source_digest = parse_digest(source_sha256);
        entry->path = path;
        entry->context_size = context_size;
        entry->gpu_layers = gpu_layers;
        entry->field_device = gpu_layers == 0 ? "CPU" : "Vulkan0";
        entry->model.reset(raw_model);
        entry->vocab = llama_model_get_vocab(raw_model);
        if (!entry->vocab || llama_vocab_n_tokens(entry->vocab) <= 0) {
            throw ProtocolError("registered GGUF model has no usable vocabulary");
        }
        const auto key = entry->source_sha256;
        const auto registration = describe(*entry, "loaded");
        models_.emplace(key, std::move(entry));
        return registration;
    }

    GraphSitePreflightWire graph_site_preflight(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw,
        const std::string& expected_sampler_sha256,
        const std::string& sequence_id,
        const std::string& native_operation_id) {
        if (task_id.empty() || task_id.size() > 127U || sequence_id.empty() ||
                sequence_id.size() > 127U || native_operation_id.empty() ||
                native_operation_id.size() > 512U)
            throw ProtocolError("graph-site preflight requires bounded task, sequence, and operation identities");
        require_hex_sha256(expected_sampler_sha256, "graph-site sampler_sha256");
        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        auto& model = *model_found->second;
        if (tokens.empty() || tokens.size() >= model.context_size)
            throw ProtocolError("graph-site preflight input history is outside the model context bound");
        const auto vocabulary_size = static_cast<std::uint32_t>(llama_vocab_n_tokens(model.vocab));
        for (const auto token : tokens) {
            if (token < 0 || static_cast<std::uint32_t>(token) >= vocabulary_size)
                throw ProtocolError("graph-site preflight input history contains an invalid token");
        }
        const auto sampler = sampler_from_request(sampler_mode, temperature, top_k, draw, vocabulary_size);
        auto task_found = tasks_.find(task_id);
        if (task_found == tasks_.end()) {
            auto task = create_task(model, tokens);
            task->task_id = task_id;
            task->source_sha256 = source_sha256;
            task_found = tasks_.emplace(task_id, std::move(task)).first;
        }
        auto& task = *task_found->second;
        if (task.source_sha256 != source_sha256 || task.completed ||
                task.tokens.size() != tokens.size() ||
                !std::equal(tokens.begin(), tokens.end(), task.tokens.begin()))
            throw ProtocolError("graph-site preflight input history diverges from its native task");
        std::vector<llama_cassi_graph_site_descriptor> descriptors(kMaxGraphSiteDescriptors);
        llama_cassi_graph_site_preflight_result native{};
        const auto count = llama_cassi_graph_site_preflight_with_sampler(
            task.context.get(), task_id.c_str(), sequence_id.c_str(), sampler,
            &native, descriptors.data(), descriptors.size());
        if (count > descriptors.size())
            throw ProtocolError("graph-site preflight descriptor count exceeds its bound");
        llama_cassi_info info{};
        if (llama_cassi_get_info(task.context.get(), &info) != 0)
            throw_context_error(task.context.get(), "llama.cpp did not expose the preflight model geometry");
        GraphSitePreflightWire result{};
        result.ready = native.ready ? 1U : 0U;
        result.native_seq_id = native.native_seq_id;
        result.next_position = native.next_position;
        result.context_limit = info.context_limit;
        if (native.next_position >= 0 && info.context_limit > static_cast<std::uint32_t>(native.next_position))
            result.remaining_tokens = info.context_limit - static_cast<std::uint32_t>(native.next_position);
        result.task_id = native.task_id;
        result.sequence_id = native.sequence_id;
        result.source_sha256 = native.source_sha256;
        result.model_sha256 = native.model_sha256;
        result.tokenizer_sha256 = native.tokenizer_sha256;
        result.native_predecessor_sha256 = native.predecessor_sha256;
        result.context_limit = info.context_limit;
        result.model_embedding_width = info.embedding_width;
        result.model_layer_count = info.layers;
        result.native_field_epoch_sha256 = native.native_field_epoch_sha256;
        result.native_preflight_sha256 = native.native_preflight_sha256;
        result.sampler_sha256 = native.sampler_sha256;
        result.native_operation_id = native_operation_id;
        switch (native.sampler_mode) {
            case LLAMA_CASSI_SAMPLER_GREEDY: result.sampler_mode = "greedy"; break;
            case LLAMA_CASSI_SAMPLER_CATEGORICAL: result.sampler_mode = "categorical"; break;
            default: throw ProtocolError("native graph-site preflight returned an unsupported sampler mode");
        }
        result.sampler_temperature = native.sampler_temperature;
        result.sampler_top_k = native.sampler_top_k;
        result.sampler_draw = native.sampler_draw;
        if (result.ready != 0U) {
            if (result.sampler_mode != sampler_mode ||
                    result.sampler_temperature != static_cast<double>(sampler.temperature) ||
                    result.sampler_top_k != sampler.top_k || result.sampler_draw != sampler.draw)
                throw ProtocolError("native graph-site preflight changed the effective sampler tuple");
            if (result.sampler_sha256 != expected_sampler_sha256)
                throw ProtocolError("native graph-site preflight sampler digest differs from its exact request tuple");
        }
        result.refusal = native.refusal;
        result.sites.reserve(count);
        for (std::size_t index = 0; index < count; ++index) {
            const auto& site = descriptors[index];
            result.sites.push_back(GraphSiteDescriptorWire{
                site.kind, site.supported ? 1U : 0U, site.layer, site.input_width,
                site.output_width, site.stage, site.site, site.specialist,
                site.input_tensor, site.output_tensor, site.dependencies_json, site.refusal});
        }
        if (result.ready != 0U) {
            if (result.task_id != task_id || result.sequence_id != sequence_id ||
                    result.source_sha256 != source_sha256 || result.native_seq_id < 0 ||
                    tokens.empty() ||
                    result.next_position != static_cast<std::int32_t>(tokens.size() - 1))
                throw ProtocolError("native graph-site preflight returned a mismatched task binding");
        }
        if (result.ready != 0U) task.pending_preflight = result;
        return result;
    }
    ModelStepResult step_graph_site_candidate(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const std::string& native_operation_id,
        const std::string& sequence_id,
        const std::string& field_candidate_id,
        const std::string& ticket_id,
        const GraphSiteCandidateWire& candidate) {
        if (field_candidate_id.empty() || field_candidate_id.size() > 512U ||
                ticket_id.empty() || ticket_id.size() > 64U ||
                native_operation_id.empty() || native_operation_id.size() > 512U ||
                sequence_id.empty() || sequence_id.size() > 127U)
            throw ProtocolError("graph-site candidate requires bounded physical, ticket, and sequence identities");
        auto task_found = tasks_.find(task_id);
        if (task_found == tasks_.end()) throw ProtocolError("graph-site candidate task is not resident");
        auto& task = *task_found->second;
        if (!task.pending_preflight.has_value())
            throw ProtocolError("graph-site candidate has no native preflight");
        const auto& preflight = *task.pending_preflight;
        if (preflight.ready == 0U || task.source_sha256 != source_sha256 ||
                task.task_id != task_id || task.completed || task.pending_graph_receipt.has_value() ||
                task.tokens.size() != tokens.size() ||
                !std::equal(tokens.begin(), tokens.end(), task.tokens.begin()))
            throw ProtocolError("graph-site candidate does not match a ready native preflight");
        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        auto& model = *model_found->second;
        const auto expected_sampler = sampler_from_request(candidate.sampler_mode,
            candidate.sampler_temperature, candidate.sampler_top_k, candidate.sampler_draw,
            static_cast<std::uint32_t>(llama_vocab_n_tokens(model.vocab)));
        if (candidate.task_id != task_id || candidate.source_sha256 != source_sha256 ||
                candidate.model_sha256 != preflight.model_sha256 ||
                candidate.tokenizer_sha256 != preflight.tokenizer_sha256 ||
                candidate.sequence_id != sequence_id ||
                candidate.native_operation_id != native_operation_id ||
                preflight.task_id != task_id || preflight.sequence_id != sequence_id ||
                preflight.native_operation_id != native_operation_id ||
                candidate.native_preflight_sha256 != preflight.native_preflight_sha256 ||
                candidate.native_predecessor_sha256 != preflight.native_predecessor_sha256 ||
                candidate.native_field_epoch_sha256 != preflight.native_field_epoch_sha256 ||
                candidate.seq_id != preflight.native_seq_id ||
                candidate.position != preflight.next_position ||
                candidate.sampler_sha256 != preflight.sampler_sha256 ||
                candidate.sampler_mode != preflight.sampler_mode ||
                candidate.sampler_temperature != preflight.sampler_temperature ||
                candidate.sampler_top_k != preflight.sampler_top_k ||
                candidate.sampler_draw != preflight.sampler_draw ||
                expected_sampler.mode != (preflight.sampler_mode == "greedy"
                    ? LLAMA_CASSI_SAMPLER_GREEDY : LLAMA_CASSI_SAMPLER_CATEGORICAL) ||
                expected_sampler.temperature != static_cast<float>(preflight.sampler_temperature) ||
                expected_sampler.top_k != preflight.sampler_top_k ||
                expected_sampler.draw != preflight.sampler_draw ||
                candidate.ticket_id != ticket_id || candidate.guard_candidate_id != ticket_id ||
                candidate.candidate_sequence_id != sequence_id ||
                candidate.candidate_source_sha256 != source_sha256 ||
                candidate.owner_snapshot_sha256 != candidate.guard_owner_snapshot_sha256 ||
                candidate.owner_field_epoch_sha256 != candidate.guard_field_epoch_sha256 ||
                candidate.native_predecessor_sha256 != candidate.guard_native_predecessor_sha256 ||
                candidate.native_preflight_sha256 != candidate.guard_native_preflight_sha256 ||
                candidate.request_sha256_pending != 1U || !candidate.request_sha256.empty())
            throw ProtocolError("graph-site ticket disagrees with the exact preflight binding");
        if (candidate.kind != LLAMA_CASSI_GRAPH_SITE_EXPERTS &&
                candidate.kind != LLAMA_CASSI_GRAPH_SITE_RECURRENT &&
                candidate.kind != LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY &&
                candidate.kind != LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE)
            throw ProtocolError("native graph-site candidate kind is unavailable");
        const auto descriptor = std::find_if(preflight.sites.begin(), preflight.sites.end(),
            [&](const GraphSiteDescriptorWire& site) {
                return site.kind == candidate.kind && site.layer == candidate.layer &&
                    site.supported != 0U && site.input_width == candidate.input_width &&
                    site.output_width == candidate.output_width &&
                    site.stage == candidate.stage && site.site == candidate.site &&
                    site.specialist == candidate.specialist &&
                    site.input_tensor == candidate.input_tensor &&
                    site.output_tensor == candidate.output_tensor &&
                    site.dependencies_json == candidate.dependencies_json;
            });
        if (descriptor == preflight.sites.end())
            throw ProtocolError("graph-site candidate does not match a supported native descriptor");
        if (task.pending_field_candidate_id.size() != 0U)
            throw ProtocolError("a graph-site field candidate is already pending");

        llama_cassi_graph_site_candidate native_candidate{};
        native_candidate.kind = static_cast<llama_cassi_graph_site_kind>(candidate.kind);
        native_candidate.seq_id = candidate.seq_id;
        native_candidate.position = candidate.position;
        native_candidate.layer = candidate.layer;
        native_candidate.owner_generation = candidate.owner_generation;
        native_candidate.predecessor_generation = candidate.predecessor_generation;
        native_candidate.sequence_id = candidate.candidate_sequence_id.c_str();
        native_candidate.source_sha256 = candidate.candidate_source_sha256.c_str();
        native_candidate.architecture = candidate.architecture.c_str();
        native_candidate.backend = candidate.backend.c_str();
        native_candidate.input_tensor = candidate.input_tensor.c_str();
        native_candidate.output_tensor = candidate.output_tensor.c_str();
        native_candidate.tensor_dtype = candidate.tensor_dtype.c_str();
        native_candidate.stage = candidate.stage.c_str();
        native_candidate.site = candidate.site.c_str();
        native_candidate.specialist = candidate.specialist.c_str();
        native_candidate.request_sha256 = candidate.request_sha256.c_str();
        native_candidate.request_sha256_pending = candidate.request_sha256_pending != 0U;
        native_candidate.invocation_sha256 = candidate.invocation_sha256.c_str();
        native_candidate.candidate_sha256 = candidate.candidate_sha256.c_str();
        native_candidate.intervention_order = candidate.intervention_order.c_str();
        native_candidate.dependencies_json = candidate.dependencies_json.c_str();
        native_candidate.method_key = candidate.method_key.c_str();
        native_candidate.method_generation = candidate.method_generation;
        native_candidate.input_width = candidate.input_width;
        native_candidate.rank = candidate.rank;
        native_candidate.output_width = candidate.output_width;
        native_candidate.a = candidate.a.data();
        native_candidate.a_count = candidate.a.size();
        native_candidate.b = candidate.b.data();
        native_candidate.b_count = candidate.b.size();
        native_candidate.bias = candidate.bias.data();
        native_candidate.bias_count = candidate.bias.size();
        native_candidate.conv_history_rows = candidate.conv_history_rows;
        native_candidate.conv_history_channels = candidate.conv_history_channels;
        native_candidate.recurrent_state_heads = candidate.recurrent_state_heads;
        native_candidate.recurrent_state_value_width = candidate.recurrent_state_value_width;
        native_candidate.recurrent_state_key_width = candidate.recurrent_state_key_width;
        native_candidate.attn_kv_heads = candidate.attn_kv_heads;
        native_candidate.attn_kv_head_width = candidate.attn_kv_head_width;
        native_candidate.input_support_anchor = candidate.input_support_anchor.data();
        native_candidate.input_support_anchor_count = candidate.input_support_anchor.size();
        native_candidate.input_support_radius = candidate.input_support_radius;
        native_candidate.input_support_anchor_norm = candidate.input_support_anchor_norm;
        native_candidate.expected_expert_ids = candidate.expected_expert_ids.data();
        native_candidate.expected_expert_ids_count = candidate.expected_expert_ids.size();
        llama_cassi_graph_site_candidate_guard guard{};
        guard.candidate_id = candidate.guard_candidate_id.c_str();
        guard.verb = candidate.verb;
        guard.native_preflight_sha256 = candidate.guard_native_preflight_sha256.c_str();
        guard.native_predecessor_sha256 = candidate.guard_native_predecessor_sha256.c_str();
        guard.owner_snapshot_sha256 = candidate.guard_owner_snapshot_sha256.c_str();
        guard.field_epoch_sha256 = candidate.guard_field_epoch_sha256.c_str();
        guard.input_support_anchor = candidate.input_support_anchor.data();
        guard.input_support_anchor_count = candidate.input_support_anchor.size();
        guard.input_support_radius = candidate.input_support_radius;
        guard.input_support_anchor_norm = candidate.input_support_anchor_norm;
        guard.expected_expert_ids = candidate.expected_expert_ids.data();
        guard.expected_expert_ids_count = candidate.expected_expert_ids.size();

        const auto sampler = sampler_from_request(candidate.sampler_mode,
            candidate.sampler_temperature, candidate.sampler_top_k, candidate.sampler_draw,
            static_cast<std::uint32_t>(llama_vocab_n_tokens(model.vocab)));
        if (llama_cassi_set_sampler(task.context.get(), sampler) != 0)
            throw_context_error(task.context.get(), "llama.cpp rejected the candidate sampler");
        bool candidate_staged = false;
        bool pending_token = false;
        const auto cleanup = [&]() noexcept {
            if (pending_token) {
                (void) llama_cassi_discard_pending(task.context.get());
            } else {
                (void) llama_cassi_sampler_discard(task.context.get());
            }
            if (candidate_staged)
                llama_cassi_context_graph_site_candidate_clear(task.context.get(), ticket_id.c_str());
            task.pending_field_candidate_id.clear();
            task.pending_ticket_id.clear();
            task.pending_native_operation_id.clear();
            task.pending_sequence_id.clear();
            task.pending_graph_receipt.reset();
            task.pending_graph_receipt_wire_sha256.clear();
        };
        const auto copy_measured_stage_trace = [&](
                const llama_cassi_graph_site_candidate_receipt& native_receipt) {
            if (native_receipt.stage_event_count > kMaxGraphSiteDescriptors ||
                    (native_receipt.stage_event_count != 0U && native_receipt.stage_events == nullptr))
                throw ProtocolError("llama.cpp graph-site receipt has an invalid measured stage trace");
            std::vector<std::string> trace;
            trace.reserve(native_receipt.stage_event_count);
            for (std::size_t index = 0; index < native_receipt.stage_event_count; ++index) {
                const auto& event = native_receipt.stage_events[index];
                switch (event.kind) {
                    case LLAMA_CASSI_GRAPH_SITE_STAGE_EMBED:
                        if (event.layer != -1)
                            throw ProtocolError("native graph-site embedding trace has an invalid layer");
                        trace.emplace_back("embedding");
                        break;
                    case LLAMA_CASSI_GRAPH_SITE_STAGE_HEAD:
                        if (event.layer != -1)
                            throw ProtocolError("native graph-site head trace has an invalid layer");
                        trace.emplace_back("head");
                        break;
                    case LLAMA_CASSI_GRAPH_SITE_STAGE_ATTENTION:
                        if (event.layer < 0)
                            throw ProtocolError("native graph-site attention trace has an invalid layer");
                        trace.emplace_back("attention:" + std::to_string(event.layer));
                        break;
                    case LLAMA_CASSI_GRAPH_SITE_STAGE_FFN:
                        if (event.layer < 0)
                            throw ProtocolError("native graph-site FFN trace has an invalid layer");
                        trace.emplace_back("ffn:" + std::to_string(event.layer));
                        break;
                    default:
                        throw ProtocolError("native graph-site stage trace contains an unknown event kind");
                }
            }
            return trace;
        };
        const auto rejected_result = [&](const llama_cassi_graph_site_candidate_receipt& native_receipt) {
            if (!native_receipt.attempted || native_receipt.admitted ||
                    native_receipt.refusal[0] == '\0')
                throw ProtocolError("llama.cpp returned an incomplete graph-site refusal");
            const auto actual_count = native_receipt.actual_expert_ids_count;
            if (actual_count > kMaxGraphSiteDescriptors ||
                    (actual_count != 0U && native_receipt.actual_expert_ids == nullptr))
                throw ProtocolError("llama.cpp graph-site refusal has an invalid measured expert route");
            if (candidate.kind != LLAMA_CASSI_GRAPH_SITE_EXPERTS && actual_count != 0U)
                throw ProtocolError("llama.cpp non-expert graph-site refusal unexpectedly reported expert IDs");
            GraphSiteReceiptWire receipt{};
            receipt.expected_expert_ids = candidate.expected_expert_ids;
            if (actual_count != 0U) {
                receipt.actual_expert_ids.assign(native_receipt.actual_expert_ids,
                    native_receipt.actual_expert_ids + actual_count);
                for (const auto expert_id : receipt.actual_expert_ids) {
                    if (expert_id < 0)
                        throw ProtocolError("llama.cpp graph-site refusal reported a negative expert ID");
                }
            }
            receipt.stage_trace = copy_measured_stage_trace(native_receipt);
            if (!receipt.stage_trace.empty())
                receipt.stage_trace_sha256 =
                    detail::canonical_graph_site_trace_sha256(receipt.stage_trace);
            receipt.ticket_id = ticket_id;
            receipt.field_candidate_id = field_candidate_id;
            receipt.ticket_sha256 = candidate.ticket_sha256;
            receipt.preflight_sha256 = candidate.preflight_sha256;
            receipt.native_preflight_sha256 = candidate.native_preflight_sha256;
            receipt.source_sha256 = candidate.source_sha256;
            receipt.model_sha256 = candidate.model_sha256;
            receipt.tokenizer_sha256 = candidate.tokenizer_sha256;
            receipt.task_id = task_id;
            receipt.sequence_id = sequence_id;
            receipt.native_operation_id = native_operation_id;
            receipt.seq_id = candidate.seq_id;
            receipt.position = candidate.position;
            receipt.accepted_token_id = -1;
            receipt.input_token_count = tokens.size();
            receipt.input_tokens_sha256 = input_tokens_sha256(tokens);
            receipt.stage = candidate.stage;
            receipt.layer = candidate.layer;
            receipt.site = candidate.site;
            receipt.specialist = candidate.specialist;
            receipt.invocation_sha256 = candidate.invocation_sha256;
            receipt.request_sha256 = native_receipt.request_sha256;
            receipt.candidate_sha256 = candidate.candidate_sha256;
            receipt.dependencies_json = candidate.dependencies_json;
            receipt.method_key = candidate.method_key;
            receipt.method_generation = candidate.method_generation;
            receipt.intervention_order = candidate.intervention_order;
            receipt.graph_predecessor_sha256 = candidate.candidate_predecessor_sha256;
            receipt.owner_snapshot_sha256 = candidate.owner_snapshot_sha256;
            receipt.owner_field_epoch_sha256 = candidate.owner_field_epoch_sha256;
            receipt.native_field_epoch_sha256 = candidate.native_field_epoch_sha256;
            receipt.native_predecessor_sha256 = candidate.native_predecessor_sha256;
            receipt.sampler_sha256 = candidate.sampler_sha256;
            receipt.sampler_mode = candidate.sampler_mode;
            receipt.sampler_temperature = candidate.sampler_temperature;
            receipt.sampler_top_k = candidate.sampler_top_k;
            receipt.sampler_draw = candidate.sampler_draw;
            receipt.input_sha256 = native_receipt.input_sha256;
            receipt.output_sha256 = native_receipt.output_sha256;
            receipt.refusal = native_receipt.refusal;
            receipt.attempted = 1U;
            receipt.admitted = 0U;
            receipt.owner_generation = candidate.owner_generation;
            const auto receipt_wire = encode_graph_site_receipt(receipt);
            const auto receipt_wire_sha = hex_digest(sha256(receipt_wire));
            ModelStepResult result{};
            result.token = -1;
            result.sampled_token = -1;
            result.seq_id = candidate.seq_id;
            result.position = candidate.position;
            result.accepted = false;
            result.graph_site_rejected = true;
            result.native_operation_id = native_operation_id;
            result.sequence_id = sequence_id;
            result.input_tokens_sha256 = receipt.input_tokens_sha256;
            result.sampler_sha256 = candidate.sampler_sha256;
            result.native_predecessor_sha256 = candidate.native_predecessor_sha256;
            result.graph_site_receipt = std::move(receipt);
            result.graph_receipt_wire_sha256 = receipt_wire_sha;
            result.field_candidate_id = field_candidate_id;
            result.ticket_id = ticket_id;
            cleanup();
            return result;
        };
        try {
            if (!llama_cassi_context_graph_site_candidate_set(
                    task.context.get(), &native_candidate, &guard))
                throw_context_error(task.context.get(), "llama.cpp rejected the owner-held graph-site candidate");
            candidate_staged = true;
            llama_cassi_stats stats_before{};
            llama_cassi_get_stats(task.context.get(), &stats_before);
            const auto services_before = service_stats(task.context.get());
            llama_cassi_token selected{};
            const auto status = llama_cassi_next(task.context.get(), &selected);
            const bool token_available = status == LLAMA_CASSI_TOKEN && selected.token >= 0 &&
                selected.token < llama_vocab_n_tokens(model.vocab);
            llama_cassi_graph_site_candidate_receipt native_receipt{};
            if (!llama_cassi_context_graph_site_candidate_get_result(task.context.get(), &native_receipt))
                throw_context_error(task.context.get(), "llama.cpp did not return the graph-site receipt");
            if (native_receipt.attempted && !native_receipt.admitted) {
                pending_token = status == LLAMA_CASSI_TOKEN;
                return rejected_result(native_receipt);
            }
            if (!token_available)
                throw_context_error(task.context.get(), "llama.cpp did not produce an exact native graph-site token");
            pending_token = true;
            std::vector<std::int32_t> actual_expert_ids;
            if (candidate.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                if (native_receipt.actual_expert_ids == nullptr ||
                        native_receipt.actual_expert_ids_count == 0U ||
                        native_receipt.actual_expert_ids_count > kMaxGraphSiteDescriptors)
                    throw ProtocolError("llama.cpp admitted graph-site receipt omitted its measured expert route");
                actual_expert_ids.assign(native_receipt.actual_expert_ids,
                    native_receipt.actual_expert_ids + native_receipt.actual_expert_ids_count);
                for (const auto expert_id : actual_expert_ids) {
                    if (expert_id < 0)
                        throw ProtocolError("llama.cpp graph-site receipt contains a negative measured expert ID");
                }
                if (actual_expert_ids.size() != candidate.expected_expert_ids.size() ||
                        !std::equal(actual_expert_ids.begin(), actual_expert_ids.end(),
                            candidate.expected_expert_ids.begin()))
                    throw ProtocolError("llama.cpp admitted a graph-site candidate with a different measured expert route");
            } else if (native_receipt.actual_expert_ids_count != 0U) {
                throw ProtocolError("llama.cpp non-expert graph-site receipt unexpectedly reported expert IDs");
            }
            if (!native_receipt.attempted || !native_receipt.admitted ||
                    !native_receipt.request_sha256_pending ||
                    native_receipt.candidate_id != ticket_id ||
                    native_receipt.owner_generation != candidate.owner_generation ||
                    native_receipt.method_generation != candidate.method_generation ||
                    std::strcmp(native_receipt.request_sha256, native_receipt.input_sha256) != 0 ||
                    native_receipt.invocation_sha256 != candidate.invocation_sha256 ||
                    native_receipt.candidate_sha256 != candidate.candidate_sha256 ||
                    native_receipt.predecessor_sha256 != candidate.candidate_predecessor_sha256 ||
                    native_receipt.native_predecessor_sha256 != candidate.native_predecessor_sha256 ||
                    native_receipt.sampler_sha256 != candidate.sampler_sha256 ||
                    selected.decision_source != 2U || selected.native_dependency != 1U ||
                    selected.readout_kind != 3U)
                throw ProtocolError("native graph-site receipt disagrees with its exact staged candidate");
            char provisional_sha[65]{};
            if (llama_cassi_context_provisional_state_sha256(task.context.get(), provisional_sha) != 0)
                throw_context_error(task.context.get(), "llama.cpp did not expose the provisional native successor");
            const std::string native_successor(provisional_sha);
            if (native_receipt.native_successor_sha256 != native_successor)
                throw ProtocolError("native graph-site receipt successor differs from provisional native state");
            auto measured_stage_trace = copy_measured_stage_trace(native_receipt);
            if (measured_stage_trace.empty())
                throw ProtocolError("llama.cpp admitted graph-site receipt omitted its measured stage trace");
            const auto measured_stage_trace_sha256 =
                detail::canonical_graph_site_trace_sha256(measured_stage_trace);
            llama_cassi_stats stats_after{};
            llama_cassi_get_stats(task.context.get(), &stats_after);
            const auto services_after = service_stats(task.context.get());
            if (services_before.size() != services_after.size())
                throw ProtocolError("llama.cpp graph-site stage inventory changed during a token");
            std::uint64_t embedding_stages = 0;
            std::uint64_t attention_stages = 0;
            std::uint64_t ffn_stages = 0;
            std::uint64_t head_stages = 0;
            for (std::size_t index = 0; index < services_after.size(); ++index) {
                if (services_after[index].computed < services_before[index].computed)
                    throw ProtocolError("llama.cpp graph-site stage counter regressed");
                const auto delta = services_after[index].computed - services_before[index].computed;
                switch (services_after[index].kind) {
                    case LLAMA_CASSI_EMBED: embedding_stages += delta; break;
                    case LLAMA_CASSI_ATTENTION: attention_stages += delta; break;
                    case LLAMA_CASSI_FFN: ffn_stages += delta; break;
                    case LLAMA_CASSI_HEAD: head_stages += delta; break;
                    default: break;
                }
            }
            const auto exact_stages = stats_after.native_exact_stages - stats_before.native_exact_stages;
            if (embedding_stages != 1U || head_stages != 1U ||
                    attention_stages != ffn_stages ||
                    exact_stages != embedding_stages + attention_stages + ffn_stages + head_stages)
                throw ProtocolError("llama.cpp graph-site exact stage trace is incomplete");
            GraphSiteReceiptWire receipt{};
            receipt.ticket_id = ticket_id;
            receipt.field_candidate_id = field_candidate_id;
            receipt.ticket_sha256 = candidate.ticket_sha256;
            receipt.preflight_sha256 = candidate.preflight_sha256;
            receipt.native_preflight_sha256 = candidate.native_preflight_sha256;
            receipt.source_sha256 = candidate.source_sha256;
            receipt.model_sha256 = candidate.model_sha256;
            receipt.tokenizer_sha256 = candidate.tokenizer_sha256;
            receipt.task_id = task_id;
            receipt.sequence_id = sequence_id;
            receipt.native_operation_id = native_operation_id;
            receipt.seq_id = candidate.seq_id;
            receipt.position = candidate.position;
            receipt.accepted_token_id = selected.token;
            receipt.input_token_count = tokens.size();
            receipt.input_tokens_sha256 = input_tokens_sha256(tokens);
            receipt.replay_sha256 = replay_digest(source_sha256, tokens, selected.token);
            receipt.token_count = tokens.size() + 1U;
            receipt.stage = candidate.stage;
            receipt.layer = candidate.layer;
            receipt.site = candidate.site;
            receipt.specialist = candidate.specialist;
            receipt.invocation_sha256 = native_receipt.invocation_sha256;
            receipt.request_sha256 = native_receipt.request_sha256;
            receipt.candidate_sha256 = native_receipt.candidate_sha256;
            receipt.dependencies_json = candidate.dependencies_json;
            receipt.method_key = candidate.method_key;
            receipt.method_generation = native_receipt.method_generation;
            receipt.intervention_order = candidate.intervention_order;
            receipt.graph_predecessor_sha256 = native_receipt.predecessor_sha256;
            receipt.owner_snapshot_sha256 = candidate.owner_snapshot_sha256;
            receipt.owner_field_epoch_sha256 = candidate.owner_field_epoch_sha256;
            receipt.native_field_epoch_sha256 = candidate.native_field_epoch_sha256;
            receipt.native_predecessor_sha256 = native_receipt.native_predecessor_sha256;
            receipt.sampler_sha256 = native_receipt.sampler_sha256;
            receipt.sampler_mode = candidate.sampler_mode;
            receipt.sampler_temperature = candidate.sampler_temperature;
            receipt.sampler_top_k = candidate.sampler_top_k;
            receipt.sampler_draw = candidate.sampler_draw;
            receipt.input_sha256 = native_receipt.input_sha256;
            receipt.output_sha256 = native_receipt.output_sha256;
            receipt.expected_expert_ids = candidate.expected_expert_ids;
            receipt.actual_expert_ids = std::move(actual_expert_ids);
            receipt.stage_trace = std::move(measured_stage_trace);
            receipt.stage_trace_sha256 = measured_stage_trace_sha256;
            receipt.candidate_successor_sha256 = native_receipt.successor_sha256;
            receipt.native_successor_sha256 = native_successor;
            receipt.successor_state_json = native_receipt.successor_state_json;
            receipt.attempted = 1U;
            receipt.admitted = 1U;
            receipt.owner_generation = native_receipt.owner_generation;
            receipt.operators_omitted = native_receipt.operators_omitted;
            receipt.weights_omitted = native_receipt.weights_omitted;
            receipt.weight_bytes_omitted = native_receipt.weight_bytes_omitted;
            receipt.transfer_bytes_omitted = native_receipt.transfer_bytes_omitted;
            receipt.added_flops = native_receipt.added_flops;
            const auto receipt_wire = encode_graph_site_receipt(receipt);
            const auto receipt_wire_sha = hex_digest(sha256(receipt_wire));
            ModelStepResult result{
                selected.token,
                llama_vocab_is_eog(model.vocab, selected.token),
                selected.token,
                receipt.replay_sha256,
                receipt.token_count,
                receipt.stage_trace_sha256,
                exact_stages,
                embedding_stages,
                attention_stages,
                ffn_stages,
                head_stages,
                stats_after.native_ggml_nodes_executed - stats_before.native_ggml_nodes_executed,
                stats_after.logical_weight_bytes - stats_before.logical_weight_bytes,
            };
            result.seq_id = candidate.seq_id;
            result.position = candidate.position;
            result.accepted = false;
            result.native_operation_id = native_operation_id;
            result.sequence_id = sequence_id;
            result.input_tokens_sha256 = receipt.input_tokens_sha256;
            result.sampler_sha256 = candidate.sampler_sha256;
            result.native_predecessor_sha256 = receipt.native_predecessor_sha256;
            result.native_successor_sha256 = native_successor;
            result.graph_site_receipt = std::move(receipt);
            result.graph_receipt_wire_sha256 = receipt_wire_sha;
            result.field_candidate_id = field_candidate_id;
            result.ticket_id = ticket_id;
            task.pending_field_candidate_id = field_candidate_id;
            task.pending_ticket_id = ticket_id;
            task.pending_native_operation_id = native_operation_id;
            task.pending_sequence_id = sequence_id;
            task.pending_token = selected.token;
            task.pending_end_of_generation = result.end_of_generation;
            task.pending_graph_receipt = *result.graph_site_receipt;
            task.pending_graph_receipt_wire_sha256 = receipt_wire_sha;
            return result;
        } catch (...) {
            cleanup();
            throw;
        }
    }

    ModelStepResult confirm_graph_site_candidate(
        const std::string& task_id,
        const std::string& field_candidate_id,
        const std::string& ticket_id,
        const std::string& native_operation_id,
        const std::string& expected_receipt_wire_sha256,
        const std::string& expected_receipt_sha256) {
        require_hex_sha256(expected_receipt_wire_sha256, "graph receipt wire sha256");
        require_hex_sha256(expected_receipt_sha256, "canonical graph receipt sha256");
        auto task_found = tasks_.find(task_id);
        if (task_found == tasks_.end()) throw ProtocolError("graph-site confirmation task is not resident");
        auto& task = *task_found->second;
        if (!task.pending_graph_receipt.has_value() ||
                task.pending_field_candidate_id != field_candidate_id ||
                task.pending_ticket_id != ticket_id ||
                task.pending_native_operation_id != native_operation_id ||
                task.pending_graph_receipt_wire_sha256 != expected_receipt_wire_sha256)
            throw ProtocolError("graph-site confirmation does not match the exact pending candidate");
        const auto& receipt = *task.pending_graph_receipt;
        if (receipt.ticket_id != ticket_id || receipt.field_candidate_id != field_candidate_id ||
                receipt.native_operation_id != native_operation_id ||
                receipt.accepted_token_id != task.pending_token)
            throw ProtocolError("graph-site confirmation differs from its measured receipt");
        std::string accepted_receipt_sha256 = expected_receipt_sha256;
        ModelStepResult result{
            receipt.accepted_token_id,
            task.pending_end_of_generation,
            receipt.accepted_token_id,
            receipt.replay_sha256,
            receipt.token_count,
        };
        result.accepted = true;
        result.native_operation_id = native_operation_id;
        result.sequence_id = receipt.sequence_id;
        result.input_tokens_sha256 = receipt.input_tokens_sha256;
        result.sampler_sha256 = receipt.sampler_sha256;
        result.native_predecessor_sha256 = receipt.native_predecessor_sha256;
        result.native_successor_sha256 = receipt.native_successor_sha256;
        result.graph_site_receipt = receipt;
        result.graph_receipt_wire_sha256 = task.pending_graph_receipt_wire_sha256;
        result.native_graph_site_receipt_sha256 = accepted_receipt_sha256;
        result.field_candidate_id = field_candidate_id;
        result.ticket_id = ticket_id;
        result.seq_id = receipt.seq_id;
        result.position = receipt.position;
        task.tokens.reserve(task.tokens.size() + 1U);
        if (llama_cassi_accept(task.context.get(), task.pending_token) != 0)
            throw_context_error(task.context.get(), "llama.cpp could not accept the measured graph-site token");
        llama_cassi_context_graph_site_candidate_clear(task.context.get(), ticket_id.c_str());
        task.tokens.push_back(task.pending_token);
        task.completed = task.pending_end_of_generation;
        task.accepted_field_candidate_id = std::move(task.pending_field_candidate_id);
        task.accepted_ticket_id = std::move(task.pending_ticket_id);
        task.accepted_native_operation_id = std::move(task.pending_native_operation_id);
        task.accepted_graph_preflight = std::move(task.pending_preflight);
        task.accepted_graph_receipt = std::move(task.pending_graph_receipt);
        task.accepted_graph_receipt_wire_sha256 = std::move(task.pending_graph_receipt_wire_sha256);
        task.accepted_graph_receipt_sha256 = std::move(accepted_receipt_sha256);
        task.pending_sequence_id.clear();
        task.pending_token = 0;
        task.pending_end_of_generation = false;
        return result;
    }

    void discard_graph_site_candidate(
        const std::string& task_id,
        const std::string& field_candidate_id,
        const std::string& ticket_id) {
        auto task_found = tasks_.find(task_id);
        if (task_found == tasks_.end()) return;
        auto& task = *task_found->second;
        if (!task.pending_graph_receipt.has_value()) return;
        if (task.pending_field_candidate_id != field_candidate_id ||
                task.pending_ticket_id != ticket_id)
            throw ProtocolError("graph-site rollback identity does not match the pending candidate");
        if (llama_cassi_discard_pending(task.context.get()) != 0)
            throw_context_error(task.context.get(), "llama.cpp could not discard the provisional graph-site token");
        llama_cassi_context_graph_site_candidate_clear(task.context.get(), ticket_id.c_str());
        task.pending_field_candidate_id.clear();
        task.pending_ticket_id.clear();
        task.pending_native_operation_id.clear();
        task.pending_sequence_id.clear();
        task.pending_token = 0;
        task.pending_end_of_generation = false;
        task.pending_graph_receipt.reset();
        task.pending_graph_receipt_wire_sha256.clear();
    }

    void rollback_accepted_graph_site_candidate(
        const std::string& task_id,
        const std::string& field_candidate_id,
        const std::string& ticket_id,
        const std::string& native_operation_id) {
        auto task_found = tasks_.find(task_id);
        if (task_found == tasks_.end()) throw ProtocolError("graph-site rollback task is not resident");
        auto& task = *task_found->second;
        if (!task.accepted_graph_receipt.has_value() ||
                task.accepted_field_candidate_id != field_candidate_id ||
                task.accepted_ticket_id != ticket_id ||
                task.accepted_native_operation_id != native_operation_id ||
                task.tokens.empty() ||
                task.tokens.back() != task.accepted_graph_receipt->accepted_token_id)
            throw ProtocolError("graph-site rollback identity does not match the latest accepted candidate");
        if (llama_cassi_rollback_accepted(task.context.get()) != 0)
            throw_context_error(task.context.get(), "llama.cpp could not restore the accepted graph-site predecessor");
        task.tokens.pop_back();
        task.completed = false;
        task.accepted_graph_preflight.reset();
        task.accepted_graph_receipt.reset();
        task.accepted_field_candidate_id.clear();
        task.accepted_ticket_id.clear();
        task.accepted_native_operation_id.clear();
        task.accepted_graph_receipt_wire_sha256.clear();
        task.accepted_graph_receipt_sha256.clear();
    }
    ModelStepResult replay_graph_site_step(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const GraphSiteReplayStepWire& replay) {
        require_hex_sha256(replay.expected_ticket_sha256, "replay ticket sha256");
        require_hex_sha256(replay.expected_graph_receipt_sha256, "replay receipt wire sha256");
        require_hex_sha256(replay.expected_native_graph_site_receipt_sha256, "replay canonical receipt sha256");
        if (replay.committed_candidate.empty() || replay.history_complete > 1U)
            throw ProtocolError("graph-site replay record is incomplete");
        auto candidate = decode_graph_site_candidate(replay.committed_candidate);
        if (candidate.task_id != task_id || candidate.source_sha256 != source_sha256 ||
                candidate.native_operation_id != replay.native_operation_id ||
                candidate.candidate_predecessor_sha256 != replay.owner_predecessor_sha256 ||
                candidate.native_predecessor_sha256 != replay.native_predecessor_sha256 ||
                candidate.native_preflight_sha256 != replay.native_preflight_sha256 ||
                candidate.sampler_sha256 != replay.sampler_sha256 ||
                candidate.sampler_mode != replay.sampler_mode ||
                candidate.sampler_temperature != replay.sampler_temperature ||
                candidate.sampler_top_k != replay.sampler_top_k ||
                candidate.sampler_draw != replay.sampler_draw ||
                replay.input_token_count != tokens.size() ||
                replay.input_tokens_sha256 != input_tokens_sha256(tokens) ||
                replay.token_count != tokens.size() + 1U)
            throw ProtocolError("graph-site replay record disagrees with its exact candidate or input history");
        auto task_found = tasks_.find(task_id);
        if (task_found != tasks_.end()) {
            auto& task = *task_found->second;
            if (replay.sequence_index != task.replay_next_index ||
                    (replay.sequence_index != 0U &&
                     task.last_replay_owner_successor_sha256 != replay.owner_predecessor_sha256))
                throw ProtocolError("graph-site replay predecessor or sequence index is discontinuous");
        } else if (replay.sequence_index != 0U) {
            throw ProtocolError("graph-site replay history does not start at its first sequence index");
        }
        auto preflight = graph_site_preflight(task_id, source_sha256, tokens,
            candidate.sampler_mode, candidate.sampler_temperature, candidate.sampler_top_k,
            candidate.sampler_draw, candidate.sampler_sha256, candidate.sequence_id,
            candidate.native_operation_id);
        if (preflight.ready == 0U ||
                preflight.native_predecessor_sha256 != replay.native_predecessor_sha256 ||
                preflight.native_preflight_sha256 != replay.native_preflight_sha256)
            throw ProtocolError("native graph-site replay preflight does not match the accepted predecessor");
        const std::string owner_successor = replay.owner_successor_sha256;
        try {
            const auto staged = step_graph_site_candidate(task_id, source_sha256, tokens,
                candidate.native_operation_id, candidate.sequence_id, replay.field_candidate_id,
                candidate.ticket_id, candidate);
            if (!staged.graph_site_receipt.has_value())
                throw ProtocolError("native graph-site replay returned no measured receipt");
            const auto& receipt = *staged.graph_site_receipt;
            if (replay.expected_ticket_sha256 != receipt.ticket_sha256 ||
                    staged.graph_receipt_wire_sha256 != replay.expected_graph_receipt_sha256 ||
                    receipt.accepted_token_id != replay.accepted_token_id ||
                    staged.replay_sha256 != replay.replay_sha256 ||
                    staged.stage_trace_sha256 != replay.stage_trace_sha256 ||
                    staged.token_count != replay.token_count ||
                    receipt.graph_predecessor_sha256 != replay.owner_predecessor_sha256 ||
                    receipt.candidate_successor_sha256 != replay.owner_successor_sha256 ||
                    receipt.native_predecessor_sha256 != replay.native_predecessor_sha256 ||
                    receipt.native_successor_sha256 != replay.native_successor_sha256 ||
                    receipt.native_preflight_sha256 != replay.native_preflight_sha256 ||
                    receipt.sampler_sha256 != replay.sampler_sha256 ||
                    receipt.seq_id != candidate.seq_id || receipt.position != candidate.position)
                throw ProtocolError("re-executed graph-site receipt differs from the exact accepted owner history");
            auto result = confirm_graph_site_candidate(task_id, replay.field_candidate_id,
                candidate.ticket_id, candidate.native_operation_id,
                replay.expected_graph_receipt_sha256,
                replay.expected_native_graph_site_receipt_sha256);
            auto& committed_task = *tasks_.at(task_id);
            committed_task.replay_next_index += 1U;
            committed_task.replay_active = replay.history_complete == 0U;
            committed_task.last_replay_owner_successor_sha256 = owner_successor;
            return result;
        } catch (...) {
            try {
                discard_graph_site_candidate(task_id, replay.field_candidate_id, candidate.ticket_id);
            } catch (...) {
                if (auto pending = tasks_.find(task_id); pending != tasks_.end())
                    pending->second->completed = true;
            }
            throw;
        }
    }
    ModelStepResult step(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw,
        const std::string& sampler_sha256,
        const std::string& native_operation_id = {},
        const std::string& sequence_id = {}) {
        require_hex_sha256(sampler_sha256, "model sampler_sha256");
        if (native_operation_id.size() > 512U || sequence_id.size() > 127U)
            throw ProtocolError("native operation or logical sequence identity exceeds its bound");
        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        auto& model = *model_found->second;
        if (tokens.empty() || tokens.size() >= model.context_size) throw ProtocolError("model token history is outside the context bound");
        const auto vocabulary_size = llama_vocab_n_tokens(model.vocab);
        if (std::any_of(tokens.begin(), tokens.end(), [vocabulary_size](std::int32_t token) {
                return token < 0 || token >= vocabulary_size;
            })) {
            throw ProtocolError("model token history contains an invalid token");
        }

        auto task_found = tasks_.find(task_id);
        const bool history_matches = task_found != tasks_.end() &&
            task_found->second->tokens.size() == tokens.size() &&
            std::equal(task_found->second->tokens.begin(), task_found->second->tokens.end(), tokens.begin());
        if (!history_matches || task_found->second->source_sha256 != source_sha256) {
            auto replacement = create_task(model, tokens);
            replacement->task_id = task_id;
            replacement->source_sha256 = source_sha256;
            tasks_.insert_or_assign(task_id, std::move(replacement));
            task_found = tasks_.find(task_id);
        }
        auto& task = *task_found->second;
        task.pending_preflight.reset();
        if (task.completed) throw ProtocolError("model task has already reached end of generation");

        llama_cassi_sampler_params sampler{};
        if (sampler_mode == "greedy") {
            sampler.mode = LLAMA_CASSI_SAMPLER_GREEDY;
            sampler.temperature = 1.0F;
            sampler.top_k = 0;
            sampler.draw = 0.0;
        } else if (sampler_mode == "categorical") {
            if (!std::isfinite(temperature) || temperature <= 0.0 ||
                    !std::isfinite(draw) || draw < 0.0 || draw >= 1.0 ||
                    top_k > static_cast<std::uint32_t>(vocabulary_size)) {
                throw ProtocolError("native model sampler parameters are invalid");
            }
            sampler.mode = LLAMA_CASSI_SAMPLER_CATEGORICAL;
            sampler.temperature = static_cast<float>(temperature);
            sampler.top_k = top_k;
            sampler.draw = draw;
        } else {
            throw ProtocolError("native model sampler mode is unsupported");
        }

        llama_cassi_stats stats_before{};
        llama_cassi_get_stats(task.context.get(), &stats_before);
        const auto services_before = service_stats(task.context.get());
        if (llama_cassi_set_sampler(task.context.get(), sampler) != 0) {
            throw_context_error(task.context.get(), "llama.cpp rejected the field-owned sampler state");
        }
        llama_cassi_token selected{};
        const auto status = llama_cassi_next(task.context.get(), &selected);
        if (status != LLAMA_CASSI_TOKEN) {
            throw_context_error(task.context.get(), "llama.cpp exact pipeline did not produce one token");
        }
        if (selected.decision_source != 2U || selected.native_dependency != 1U || selected.readout_kind != 3U) {
            throw ProtocolError("llama.cpp returned a token outside the exact staged pipeline");
        }
        if (llama_cassi_accept(task.context.get(), selected.token) != 0) {
            throw_context_error(task.context.get(), "llama.cpp could not commit the exact pipeline token");
        }
        task.tokens.push_back(selected.token);

        llama_cassi_stats stats_after{};
        llama_cassi_get_stats(task.context.get(), &stats_after);
        const auto services_after = service_stats(task.context.get());
        if (stats_after.field_bytes != 0U || stats_after.native_exact_tokens - stats_before.native_exact_tokens != 1U) {
            throw ProtocolError("llama.cpp exact pipeline ownership accounting failed");
        }

        std::uint64_t embedding_stages = 0;
        std::uint64_t attention_stages = 0;
        std::uint64_t ffn_stages = 0;
        std::uint64_t head_stages = 0;
        if (services_before.size() != services_after.size()) throw ProtocolError("llama.cpp stage inventory changed during a token");
        for (std::size_t index = 0; index < services_after.size(); ++index) {
            if (services_after[index].computed < services_before[index].computed) throw ProtocolError("llama.cpp stage counter regressed");
            const auto delta = services_after[index].computed - services_before[index].computed;
            switch (services_after[index].kind) {
                case LLAMA_CASSI_EMBED: embedding_stages += delta; break;
                case LLAMA_CASSI_ATTENTION: attention_stages += delta; break;
                case LLAMA_CASSI_FFN: ffn_stages += delta; break;
                case LLAMA_CASSI_HEAD: head_stages += delta; break;
                default: break;
            }
        }
        const auto exact_stages = stats_after.native_exact_stages - stats_before.native_exact_stages;
        if (head_stages != 1U || embedding_stages == 0U || attention_stages != ffn_stages ||
                exact_stages != embedding_stages + attention_stages + ffn_stages + head_stages) {
            throw ProtocolError("llama.cpp exact stage trace is incomplete");
        }
        const bool end_of_generation = llama_vocab_is_eog(model.vocab, selected.token);
        task.completed = end_of_generation;
        const auto ggml_nodes = stats_after.native_ggml_nodes_executed - stats_before.native_ggml_nodes_executed;
        const auto logical_weight_bytes = stats_after.logical_weight_bytes - stats_before.logical_weight_bytes;
        auto result = ModelStepResult{
            selected.token,
            end_of_generation,
            selected.token,
            replay_digest(source_sha256, task.tokens),
            task.tokens.size(),
            stage_trace_digest(tokens, sampler_mode, temperature, top_k, draw, selected.token,
                exact_stages, embedding_stages, attention_stages, ffn_stages, head_stages,
                ggml_nodes, logical_weight_bytes),
            exact_stages,
            embedding_stages,
            attention_stages,
            ffn_stages,
            head_stages,
            ggml_nodes,
            logical_weight_bytes,
        };
        result.native_operation_id = native_operation_id;
        result.sampler_sha256 = sampler_sha256;
        result.sequence_id = sequence_id;
        result.seq_id = 0;
        result.position = static_cast<std::int32_t>(tokens.size());
        result.input_tokens_sha256 = input_tokens_sha256(tokens);
        return result;
    }

    // One-pass draft verification. `draft_tokens[0]` is checked against the
    // target's own exact-pipeline sample; when it matches and further draft
    // tokens remain, the continuations (`draft_tokens[1:]`) are verified in one
    // native forward pass via the fork's llama_cassi_verify_draft/verify_commit.
    // `draws` and `native_operation_ids` each carry draft_tokens.size() + 1
    // entries: one per draft position plus one for the target's own sample at
    // the first divergence or a bonus token beyond the whole draft. Falls back
    // to an ordinary single-token result (draft_matched reflecting the
    // position-0 comparison) when the first position mismatches, no
    // continuations remain, or the native verifier cannot run this round (for
    // example insufficient ubatch/recurrent-state capacity); the caller always
    // gets at least one committed row. A committed row's stage counters are an
    // even share of the round's measured total: one native forward pass decodes
    // exactly one token for a fixed model/context shape, so the share is exact,
    // not an estimate; any remainder from integer division lands on the
    // round's last row so the reported total always matches what was measured.
    std::vector<ModelStepResult> verify_draft(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        std::span<const std::int32_t> draft_tokens,
        std::span<const double> draws,
        const std::string& sampler_sha256,
        std::span<const std::string> native_operation_ids,
        const std::string& sequence_id = {}) {
        require_hex_sha256(sampler_sha256, "model sampler_sha256");
        if (sequence_id.size() > 127U) throw ProtocolError("logical sequence identity exceeds its bound");
        if (draft_tokens.empty() || draft_tokens.size() > LLAMA_CASSI_MAX_DRAFT_TOKENS)
            throw ProtocolError("draft verify token count is out of bounds");
        if (draws.size() != draft_tokens.size() + 1U || native_operation_ids.size() != draws.size())
            throw ProtocolError("draft verify draws or operation identity count mismatches the draft length");
        for (const auto& id : native_operation_ids)
            if (id.size() > 512U) throw ProtocolError("native operation identity exceeds its bound");

        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        auto& model = *model_found->second;
        if (tokens.empty() || tokens.size() >= model.context_size) throw ProtocolError("model token history is outside the context bound");
        const auto vocabulary_size = llama_vocab_n_tokens(model.vocab);
        auto token_in_range = [vocabulary_size](std::int32_t token) { return token >= 0 && token < vocabulary_size; };
        if (!std::all_of(tokens.begin(), tokens.end(), token_in_range))
            throw ProtocolError("model token history contains an invalid token");
        if (!std::all_of(draft_tokens.begin(), draft_tokens.end(), token_in_range))
            throw ProtocolError("model draft token is invalid");

        auto task_found = tasks_.find(task_id);
        const bool history_matches = task_found != tasks_.end() &&
            task_found->second->tokens.size() == tokens.size() &&
            std::equal(task_found->second->tokens.begin(), task_found->second->tokens.end(), tokens.begin());
        if (!history_matches || task_found->second->source_sha256 != source_sha256) {
            auto replacement = create_task(model, tokens);
            replacement->task_id = task_id;
            replacement->source_sha256 = source_sha256;
            tasks_.insert_or_assign(task_id, std::move(replacement));
            task_found = tasks_.find(task_id);
        }
        auto& task = *task_found->second;
        task.pending_preflight.reset();
        if (task.completed) throw ProtocolError("model task has already reached end of generation");

        llama_cassi_stats stats_before{};
        llama_cassi_get_stats(task.context.get(), &stats_before);
        const auto services_before = service_stats(task.context.get());

        const auto sampler0 = sampler_from_request(sampler_mode, temperature, top_k, draws[0], vocabulary_size);
        if (llama_cassi_set_sampler(task.context.get(), sampler0) != 0)
            throw_context_error(task.context.get(), "llama.cpp rejected the field-owned sampler state");
        llama_cassi_token selected0{};
        if (llama_cassi_next(task.context.get(), &selected0) != LLAMA_CASSI_TOKEN)
            throw_context_error(task.context.get(), "llama.cpp exact pipeline did not produce one token");
        if (selected0.decision_source != 2U || selected0.native_dependency != 1U || selected0.readout_kind != 3U)
            throw ProtocolError("llama.cpp returned a token outside the exact staged pipeline");

        const bool position0_matches = selected0.token == draft_tokens[0];
        const bool attempt_verify = position0_matches && draft_tokens.size() > 1U;

        std::vector<llama_cassi_sampler_params> target_samplers;
        std::int32_t verify_status = -1;
        llama_cassi_draft_verify_receipt receipt{};
        const std::string proposal_digest = input_tokens_sha256(draft_tokens);
        if (attempt_verify) {
            const auto draft_count = static_cast<std::uint32_t>(draft_tokens.size() - 1U);
            target_samplers.reserve(draft_count + 1U);
            for (std::uint32_t i = 0; i < draft_count + 1U; ++i)
                target_samplers.push_back(sampler_from_request(sampler_mode, temperature, top_k, draws[i + 1U], vocabulary_size));
            std::vector<double> proposal_probabilities(draft_count, 1.0);
            llama_cassi_draft_verify_request request{};
            request.draft_tokens = draft_tokens.data() + 1;
            request.proposal_probabilities = proposal_probabilities.data();
            request.draft_count = draft_count;
            request.target_samplers = target_samplers.data();
            request.target_sampler_count = target_samplers.size();
            request.task_id = task_id.c_str();
            request.sequence_id = sequence_id.c_str();
            request.native_operation_id = native_operation_ids[1].c_str();
            request.proposal_sha256 = proposal_digest.c_str();
            request.owner_predecessor_sha256 = "";
            request.sampler_sha256 = sampler_sha256.c_str();
            verify_status = llama_cassi_verify_draft(task.context.get(), &request, &receipt);
        }

        std::vector<ModelStepResult> rows;
        std::vector<std::int32_t> running_tokens(tokens.begin(), tokens.end());

        if (verify_status == 0) {
            if (llama_cassi_verify_commit(task.context.get(), receipt.receipt_sha256) != 0)
                throw_context_error(task.context.get(), "llama.cpp could not commit the verified draft");
            const std::uint64_t committed_rows = 1U + receipt.output_count; // position0 + (accepted continuations + final)

            llama_cassi_stats stats_after{};
            llama_cassi_get_stats(task.context.get(), &stats_after);
            const auto services_after = service_stats(task.context.get());
            if (stats_after.field_bytes != 0U ||
                    stats_after.native_exact_tokens - stats_before.native_exact_tokens != committed_rows) {
                throw ProtocolError("llama.cpp exact pipeline ownership accounting failed");
            }

            std::uint64_t embedding_total = 0, attention_total = 0, ffn_total = 0, head_total = 0;
            if (services_before.size() != services_after.size()) throw ProtocolError("llama.cpp stage inventory changed during a draft round");
            for (std::size_t index = 0; index < services_after.size(); ++index) {
                if (services_after[index].computed < services_before[index].computed) throw ProtocolError("llama.cpp stage counter regressed");
                const auto delta = services_after[index].computed - services_before[index].computed;
                switch (services_after[index].kind) {
                    case LLAMA_CASSI_EMBED: embedding_total += delta; break;
                    case LLAMA_CASSI_ATTENTION: attention_total += delta; break;
                    case LLAMA_CASSI_FFN: ffn_total += delta; break;
                    case LLAMA_CASSI_HEAD: head_total += delta; break;
                    default: break;
                }
            }
            const auto exact_total = stats_after.native_exact_stages - stats_before.native_exact_stages;
            if (head_total != committed_rows || embedding_total == 0U || attention_total != ffn_total ||
                    exact_total != embedding_total + attention_total + ffn_total + head_total) {
                throw ProtocolError("llama.cpp exact stage trace is incomplete");
            }
            const auto ggml_total = stats_after.native_ggml_nodes_executed - stats_before.native_ggml_nodes_executed;
            const auto weight_total = stats_after.logical_weight_bytes - stats_before.logical_weight_bytes;

            auto share = [&](std::uint64_t total) -> std::pair<std::uint64_t, std::uint64_t> {
                const auto base = total / committed_rows;
                return {base, total - base * committed_rows};
            };
            const auto [exact_base, exact_rem] = share(exact_total);
            const auto [embed_base, embed_rem] = share(embedding_total);
            const auto [attn_base, attn_rem] = share(attention_total);
            const auto [ffn_base, ffn_rem] = share(ffn_total);
            const auto [head_base, head_rem] = share(head_total);
            const auto [ggml_base, ggml_rem] = share(ggml_total);
            const auto [weight_base, weight_rem] = share(weight_total);

            std::uint64_t emitted = 0;
            auto emit_row = [&](std::int32_t token, bool matched, const std::string& operation_id,
                    const llama_cassi_sampler_params& row_sampler, double row_draw) {
                const bool is_last = emitted + 1U == committed_rows;
                const std::vector<std::int32_t> history_before = running_tokens;
                std::array<char, 65> digest{};
                llama_cassi_sampler_sha256(row_sampler, digest.data());
                const auto exact_stages = exact_base + (is_last ? exact_rem : 0U);
                const auto embedding_stages = embed_base + (is_last ? embed_rem : 0U);
                const auto attention_stages = attn_base + (is_last ? attn_rem : 0U);
                const auto ffn_stages = ffn_base + (is_last ? ffn_rem : 0U);
                const auto head_stages = head_base + (is_last ? head_rem : 0U);
                const auto ggml_nodes = ggml_base + (is_last ? ggml_rem : 0U);
                const auto logical_weight_bytes = weight_base + (is_last ? weight_rem : 0U);
                ModelStepResult row{};
                row.token = token;
                row.sampled_token = token;
                row.end_of_generation = llama_vocab_is_eog(model.vocab, token);
                row.draft_matched = matched;
                row.replay_sha256 = replay_digest(source_sha256, history_before, token);
                row.stage_trace_sha256 = stage_trace_digest(history_before, sampler_mode, temperature, top_k, row_draw, token,
                    exact_stages, embedding_stages, attention_stages, ffn_stages, head_stages, ggml_nodes, logical_weight_bytes);
                row.exact_stages = exact_stages;
                row.embedding_stages = embedding_stages;
                row.attention_stages = attention_stages;
                row.ffn_stages = ffn_stages;
                row.head_stages = head_stages;
                row.ggml_nodes = ggml_nodes;
                row.logical_weight_bytes = logical_weight_bytes;
                row.native_operation_id = operation_id;
                row.sampler_sha256 = std::string(digest.data());
                row.sequence_id = sequence_id;
                row.seq_id = 0;
                row.position = static_cast<std::int32_t>(history_before.size());
                row.input_tokens_sha256 = input_tokens_sha256(history_before);
                running_tokens.push_back(token);
                task.tokens.push_back(token);
                row.token_count = task.tokens.size();
                if (row.end_of_generation) task.completed = true;
                ++emitted;
                rows.push_back(std::move(row));
            };

            emit_row(selected0.token, true, native_operation_ids[0], sampler0, draws[0]);
            for (std::uint32_t i = 0; i < receipt.accepted_count && !task.completed; ++i)
                emit_row(receipt.output_tokens[i], true, native_operation_ids[1U + i], target_samplers[i], draws[1U + i]);
            if (!task.completed)
                emit_row(receipt.output_tokens[receipt.accepted_count], false,
                    native_operation_ids[1U + receipt.accepted_count], target_samplers[receipt.accepted_count],
                    draws[1U + receipt.accepted_count]);
            if (!rows.empty()) {
                rows.front().native_predecessor_sha256 = std::string(receipt.native_predecessor_sha256);
                rows.back().native_successor_sha256 = std::string(receipt.native_successor_sha256);
            }
        } else {
            if (llama_cassi_accept(task.context.get(), selected0.token) != 0)
                throw_context_error(task.context.get(), "llama.cpp could not commit the exact pipeline token");

            llama_cassi_stats stats_after{};
            llama_cassi_get_stats(task.context.get(), &stats_after);
            const auto services_after = service_stats(task.context.get());
            if (stats_after.field_bytes != 0U || stats_after.native_exact_tokens - stats_before.native_exact_tokens != 1U)
                throw ProtocolError("llama.cpp exact pipeline ownership accounting failed");

            std::uint64_t embedding_stages = 0, attention_stages = 0, ffn_stages = 0, head_stages = 0;
            if (services_before.size() != services_after.size()) throw ProtocolError("llama.cpp stage inventory changed during a token");
            for (std::size_t index = 0; index < services_after.size(); ++index) {
                if (services_after[index].computed < services_before[index].computed) throw ProtocolError("llama.cpp stage counter regressed");
                const auto delta = services_after[index].computed - services_before[index].computed;
                switch (services_after[index].kind) {
                    case LLAMA_CASSI_EMBED: embedding_stages += delta; break;
                    case LLAMA_CASSI_ATTENTION: attention_stages += delta; break;
                    case LLAMA_CASSI_FFN: ffn_stages += delta; break;
                    case LLAMA_CASSI_HEAD: head_stages += delta; break;
                    default: break;
                }
            }
            const auto exact_stages = stats_after.native_exact_stages - stats_before.native_exact_stages;
            if (head_stages != 1U || embedding_stages == 0U || attention_stages != ffn_stages ||
                    exact_stages != embedding_stages + attention_stages + ffn_stages + head_stages) {
                throw ProtocolError("llama.cpp exact stage trace is incomplete");
            }
            const auto ggml_nodes = stats_after.native_ggml_nodes_executed - stats_before.native_ggml_nodes_executed;
            const auto logical_weight_bytes = stats_after.logical_weight_bytes - stats_before.logical_weight_bytes;

            const std::vector<std::int32_t> history_before = running_tokens;
            ModelStepResult row{};
            row.token = selected0.token;
            row.sampled_token = selected0.token;
            row.end_of_generation = llama_vocab_is_eog(model.vocab, selected0.token);
            row.draft_matched = position0_matches;
            row.replay_sha256 = replay_digest(source_sha256, history_before, selected0.token);
            row.stage_trace_sha256 = stage_trace_digest(history_before, sampler_mode, temperature, top_k, draws[0], selected0.token,
                exact_stages, embedding_stages, attention_stages, ffn_stages, head_stages, ggml_nodes, logical_weight_bytes);
            row.exact_stages = exact_stages;
            row.embedding_stages = embedding_stages;
            row.attention_stages = attention_stages;
            row.ffn_stages = ffn_stages;
            row.head_stages = head_stages;
            row.ggml_nodes = ggml_nodes;
            row.logical_weight_bytes = logical_weight_bytes;
            row.native_operation_id = native_operation_ids[0];
            std::array<char, 65> digest{};
            llama_cassi_sampler_sha256(sampler0, digest.data());
            row.sampler_sha256 = std::string(digest.data());
            row.sequence_id = sequence_id;
            row.seq_id = 0;
            row.position = static_cast<std::int32_t>(history_before.size());
            row.input_tokens_sha256 = input_tokens_sha256(history_before);
            task.tokens.push_back(selected0.token);
            row.token_count = task.tokens.size();
            if (row.end_of_generation) task.completed = true;
            rows.push_back(std::move(row));
        }
        return rows;
    }

    std::vector<std::int32_t> tokenize(const std::string& source_sha256, const std::string& text) const {
        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("model source is not registered");
        const auto& model = *model_found->second;
        std::vector<llama_token> tokens(std::max<std::size_t>(text.size() + 8U, 16U));
        const auto count = llama_tokenize(model.vocab, text.c_str(), static_cast<std::int32_t>(text.size()),
            tokens.data(), static_cast<std::int32_t>(tokens.size()), false, false);
        if (count < 0) throw ProtocolError("model tokenizer rejected the text");
        tokens.resize(static_cast<std::size_t>(count));
        return std::vector<std::int32_t>(tokens.begin(), tokens.end());
    }

    bool drop_task(const std::string& task_id) { return tasks_.erase(task_id) != 0U; }

    // Shared weight-bank group host: one native context serves `capacity`
    // sequences from the same Qwen weight bank; a group round binds every row
    // into one fused stage evaluation per pipeline stage. Rows start empty and
    // decode one accepted token per round (see ModelGroupRowRequest); the row
    // slots stay bound for the group's lifetime.
    ModelGroupId create_group(const std::string& source_sha256, std::uint32_t capacity) {
        require_hex_sha256(source_sha256, "model source_sha256");
        if (capacity < 2U) throw ProtocolError("group host requires at least two rows");
        auto model_found = models_.find(source_sha256);
        if (model_found == models_.end()) throw ProtocolError("group source is not registered");
        auto& model = *model_found->second;

        auto group = std::make_unique<GroupHost>();
        group->source_sha256 = source_sha256;
        llama_cassi_info info{};
        group->context = create_group_context(model, capacity);
        if (llama_cassi_get_info(group->context.get(), &info) == 0) {
            group->embedding_width = info.embedding_width;
            group->layer_count = info.layers;
            group->vocabulary_size = info.vocabulary_size;
        }
        if (group->embedding_width == 0U || group->layer_count == 0U) {
            group.reset();
            throw ProtocolError("llama.cpp group host did not expose its geometry");
        }
        for (std::uint32_t row = 0; row < capacity; ++row) {
            group->rows.push_back(std::make_unique<GroupRow>());
        }
        next_group_id_ += 1U;
        group->id = next_group_id_;
        const ModelGroupId id = group->id;
        groups_.emplace(id, std::move(group));
        return id;
    }

    std::vector<ModelStepResult> step_group(
        ModelGroupId group_id,
        std::span<const ModelGroupRowRequest> row_requests) {
        auto found = groups_.find(group_id);
        if (found == groups_.end()) throw ProtocolError("group identity is not registered");
        auto& group = *found->second;
        const std::size_t n_rows = group.rows.size();
        if (row_requests.size() != n_rows) {
            throw ProtocolError("group row request does not span the full group capacity");
        }
        auto& model = models_.at(group.source_sha256);
        std::vector<char> row_active(n_rows, 1);
        for (std::size_t row = 0; row < n_rows; ++row) {
            auto& row_state = *group.rows[row];
            if (!row_state.active) {
                // leave_group froze this seat: host history, completion and
                // context checks do not apply to a seat with no member.
                row_active[row] = 0;
                continue;
            }
            const auto& request = row_requests[row];
            if (row_state.completed || row_state.tokens.size() + 1U >= model->context_size) {
                throw ProtocolError("group row has already reached end of generation");
            }
            if (request.tokens != row_state.tokens || request.tokens.size() >= model->context_size) {
                throw ProtocolError("group row history diverges from its admitted record");
            }
            const auto token_id = static_cast<std::uint32_t>(request.next_token);
            if (request.next_token < 0 || token_id >= group.vocabulary_size) {
                throw ProtocolError("group row history contains an invalid token");
            }
            if (request.accept_sampled && (!row_state.has_sample ||
                    request.next_token != row_state.last_sampled)) {
                throw ProtocolError("group row did not accept its previous head sample");
            }
        }

        // Inactive seats still take part in the fused round with a synthesized
        // greedy request so every capacity row is present; their committed
        // history stays frozen while the head sample stays fresh.
        std::vector<ModelGroupRowRequest> effective_requests(
            row_requests.begin(), row_requests.end());
        for (std::size_t row = 0; row < n_rows; ++row) {
            if (row_active[row] != 0) continue;
            auto& row_state = *group.rows[row];
            // An idle seat has no member, so its placeholder always decodes
            // into a freshly wiped sequence at position 0: it holds one cell
            // however long it stays idle and never approaches the context bound.
            if (row_state.native_pos != 0U) {
                if (llama_cassi_group_row_reset(group.context.get(), static_cast<std::uint32_t>(row)) != 0) {
                    throw_context_error(group.context.get(), "llama.cpp could not wipe an idle group seat");
                }
                row_state.native_pos = 0U;
            }
            auto& synthesized = effective_requests[row];
            synthesized.sampler_mode = "greedy";
            synthesized.temperature = 0.0;
            synthesized.top_k = 0;
            synthesized.draw = 0.0;
            synthesized.tokens = row_state.tokens;
            if (row_state.has_sample) {
                synthesized.next_token = row_state.last_sampled;
                synthesized.accept_sampled = true;
            } else {
                synthesized.next_token = row_state.tokens.empty()
                    ? 0
                    : row_state.tokens.back();
                synthesized.accept_sampled = false;
            }
        }

        llama_cassi_stats stats_before{};
        llama_cassi_get_stats(group.context.get(), &stats_before);
        const auto services_before = service_stats(group.context.get());

        std::vector<llama_cassi_group_row> rows(n_rows);
        for (std::size_t row = 0; row < n_rows; ++row) {
            rows[row].token = effective_requests[row].next_token;
            // The native KV cursor: an active seat's equals its committed
            // history length, and an idle seat's is 0 after its wipe above.
            rows[row].pos = static_cast<llama_pos>(group.rows[row]->native_pos);
            rows[row].sampler = sampler_from_request(effective_requests[row].sampler_mode,
                effective_requests[row].temperature, effective_requests[row].top_k,
                effective_requests[row].draw,
                group.vocabulary_size);
        }
        const auto width = group.embedding_width;
        std::vector<float> embed(static_cast<std::size_t>(width) * n_rows);
        if (llama_cassi_group_open(group.context.get(), rows.data(), static_cast<std::uint32_t>(n_rows),
                embed.data(), width, static_cast<std::uint32_t>(embed.size())) != 0) {
            throw_context_error(group.context.get(), "llama.cpp could not open the group round");
        }
        std::vector<float> residual = std::move(embed);
        std::vector<float> stage_out(residual.size());
        for (std::uint32_t layer = 0; layer < group.layer_count; ++layer) {
            if (llama_cassi_group_stage(group.context.get(), LLAMA_CASSI_ATTENTION,
                    static_cast<std::int32_t>(layer), residual.data(), width, stage_out.data(), width,
                    static_cast<std::uint32_t>(stage_out.size())) != 0) {
                llama_cassi_group_cancel(group.context.get());
                throw_context_error(group.context.get(), "llama.cpp could not run the fused attention group stage");
            }
            add_rows_in_place(residual, stage_out, n_rows, width);
            if (llama_cassi_group_stage(group.context.get(), LLAMA_CASSI_FFN,
                    static_cast<std::int32_t>(layer), residual.data(), width, stage_out.data(), width,
                    static_cast<std::uint32_t>(stage_out.size())) != 0) {
                llama_cassi_group_cancel(group.context.get());
                throw_context_error(group.context.get(), "llama.cpp could not run the fused ffn group stage");
            }
            add_rows_in_place(residual, stage_out, n_rows, width);
        }
        std::vector<std::int32_t> sampled(n_rows, 0);
        if (llama_cassi_group_sample(group.context.get(), residual.data(), width,
                sampled.data(), static_cast<std::uint32_t>(n_rows)) != 0) {
            throw_context_error(group.context.get(), "llama.cpp could not sample the fused group head");
        }
        if (llama_cassi_group_commit(group.context.get()) != 0) {
            throw_context_error(group.context.get(), "llama.cpp could not commit the group round");
        }
        // Every seat's native sequence advanced by exactly one position this
        // round, whether the seat is host-active or an inactive placeholder.
        for (std::size_t row = 0; row < n_rows; ++row) {
            group.rows[row]->native_pos += 1U;
        }

        llama_cassi_stats stats_after{};
        llama_cassi_get_stats(group.context.get(), &stats_after);
        const auto services_after = service_stats(group.context.get());
        if (services_before.size() != services_after.size()) throw ProtocolError("llama.cpp stage inventory changed during a round");
        std::uint64_t embedding_stages = 0;
        std::uint64_t attention_stages = 0;
        std::uint64_t ffn_stages = 0;
        std::uint64_t head_stages = 0;
        for (std::size_t index = 0; index < services_after.size(); ++index) {
            if (services_after[index].computed < services_before[index].computed) throw ProtocolError("llama.cpp stage counter regressed");
            const auto delta = services_after[index].computed - services_before[index].computed;
            switch (services_after[index].kind) {
                case LLAMA_CASSI_EMBED: embedding_stages += delta; break;
                case LLAMA_CASSI_ATTENTION: attention_stages += delta; break;
                case LLAMA_CASSI_FFN: ffn_stages += delta; break;
                case LLAMA_CASSI_HEAD: head_stages += delta; break;
                default: break;
            }
        }
        const auto head_groups = stats_after.native_exact_head_groups - stats_before.native_exact_head_groups;
        if (head_groups != 1U || embedding_stages != 1U || attention_stages != ffn_stages) {
            throw ProtocolError("llama.cpp exact group stage trace is incomplete");
        }

        const auto exact_stages = stats_after.native_exact_stages - stats_before.native_exact_stages;
        if (exact_stages != embedding_stages + attention_stages + ffn_stages + head_stages) {
            throw ProtocolError("llama.cpp exact stage trace is incomplete");
        }
        const auto ggml_nodes = stats_after.native_ggml_nodes_executed - stats_before.native_ggml_nodes_executed;
        const auto logical_weight_bytes = stats_after.logical_weight_bytes - stats_before.logical_weight_bytes;
        std::vector<ModelStepResult> results;
        results.reserve(n_rows);
        for (std::size_t row = 0; row < n_rows; ++row) {
            const auto& request = effective_requests[row];
            const std::int32_t accepted = request.next_token;
            auto& row_state = *group.rows[row];
            if (row_active[row] == 0) {
                // The seat's committed history stays frozen at leave time;
                // only its head sample advances so the next synthesized
                // request can keep accepting from the same position.
                row_state.last_sampled = sampled[row];
                row_state.has_sample = true;
                results.push_back(ModelStepResult{
                    accepted,
                    false,
                    sampled[row],
                    replay_digest(group.source_sha256, row_state.tokens),
                    row_state.tokens.size(),
                    stage_trace_digest(row_state.tokens, request.sampler_mode,
                        request.temperature, request.top_k, request.draw,
                        accepted, exact_stages, embedding_stages, attention_stages, ffn_stages, head_stages,
                        ggml_nodes, logical_weight_bytes),
                    exact_stages,
                    embedding_stages,
                    attention_stages,
                    ffn_stages,
                    head_stages,
                    ggml_nodes,
                    logical_weight_bytes,
                });
                continue;
            }
            row_state.tokens.push_back(accepted);
            row_state.completed = llama_vocab_is_eog(model->vocab, accepted);
            row_state.last_sampled = sampled[row];
            row_state.has_sample = true;
            results.push_back(ModelStepResult{
                accepted,
                row_state.completed,
                sampled[row],
                replay_digest(group.source_sha256, row_state.tokens),
                row_state.tokens.size(),
                stage_trace_digest(row_state.tokens, request.sampler_mode,
                    request.temperature, request.top_k, request.draw,
                    accepted, exact_stages, embedding_stages, attention_stages, ffn_stages, head_stages,
                    ggml_nodes, logical_weight_bytes),
                exact_stages,
                embedding_stages,
                attention_stages,
                ffn_stages,
                head_stages,
                ggml_nodes,
                logical_weight_bytes,
            });
        }
        return results;
    }
    // Churn: a row leaves without dropping its seat; the first inactive seat
    // rejoins with a fresh prompt (its history replays from position 0).
    struct GroupRowIdentity {
        std::uint32_t row{};
        std::uint64_t member_generation{};
        const void* row_state{};
        const void* native_context{};
    };

    bool leave_group(ModelGroupId group_id, std::uint32_t row) {
        auto found = groups_.find(group_id);
        if (found == groups_.end()) throw ProtocolError("group identity is not registered");
        auto& group = *found->second;
        if (row >= group.rows.size()) throw ProtocolError("group row index is out of range");
        auto& row_state = *group.rows[row];
        if (!row_state.active) return false;
        row_state.active = false;
        return true;
    }

    std::int64_t join_group(ModelGroupId group_id) {
        auto found = groups_.find(group_id);
        if (found == groups_.end()) throw ProtocolError("group identity is not registered");
        auto& group = *found->second;
        for (std::size_t row = 0; row < group.rows.size(); ++row) {
            auto& row_state = *group.rows[row];
            if (row_state.active) continue;
            // Wipe the seat's native sequence and cursor so the rejoining
            // member's fresh prompt replays from position 0 instead of
            // attending over the departed member's stale KV cells.
            if (llama_cassi_group_row_reset(group.context.get(), static_cast<std::uint32_t>(row)) != 0) {
                throw_context_error(group.context.get(),
                    "llama.cpp could not reset the rejoining seat's native sequence");
            }
            row_state.tokens.clear();
            row_state.has_sample = false;
            row_state.completed = false;
            row_state.native_pos = 0U;
            ++row_state.member_generation;
            row_state.active = true;
            return static_cast<std::int64_t>(row);
        }
        return -1;
    }

    GroupRowIdentity group_row_identity(ModelGroupId group_id, std::uint32_t row) {
        auto found = groups_.find(group_id);
        if (found == groups_.end()) throw ProtocolError("group identity is not registered");
        auto& group = *found->second;
        if (row >= group.rows.size()) throw ProtocolError("group row index is out of range");
        return GroupRowIdentity{
            static_cast<std::uint32_t>(row),
            group.rows[row]->member_generation,
            group.rows[row].get(),
            group.context.get(),
        };
    }

    bool drop_group(ModelGroupId group_id) { return groups_.erase(group_id) != 0U; }
    [[nodiscard]] std::size_t group_count() const noexcept { return groups_.size(); }

private:
    struct ModelDeleter {
        void operator()(llama_model* value) const noexcept { if (value) llama_model_free(value); }
    };
    struct CassiContextDeleter {
        void operator()(llama_cassi_context* value) const noexcept {
            if (!value) return;
            llama_cassi_finish(value, true);
            llama_cassi_free(value);
        }
    };
    struct Model {
        std::string source_sha256;
        std::array<std::uint8_t, 32> source_digest{};
        std::string path;
        std::string field_device;
        std::uint32_t context_size{};
        std::int32_t gpu_layers{};
        std::unique_ptr<llama_model, ModelDeleter> model;
        const llama_vocab* vocab{};
    };
    struct Task {
        std::string task_id;
        std::string source_sha256;
        std::unique_ptr<llama_cassi_context, CassiContextDeleter> context;
        std::vector<std::int32_t> tokens;
        bool completed{};
        std::optional<GraphSitePreflightWire> pending_preflight;
        std::uint64_t replay_next_index{};
        bool replay_active{};
        std::string last_replay_owner_successor_sha256{};
        std::string pending_field_candidate_id{};
        std::string pending_ticket_id{};
        std::string pending_native_operation_id{};
        std::string pending_sequence_id{};
        std::int32_t pending_token{};
        bool pending_end_of_generation{};
        std::optional<GraphSiteReceiptWire> pending_graph_receipt;
        std::string pending_graph_receipt_wire_sha256{};
        std::optional<GraphSitePreflightWire> accepted_graph_preflight;
        std::optional<GraphSiteReceiptWire> accepted_graph_receipt;
        std::string accepted_field_candidate_id{};
        std::string accepted_ticket_id{};
        std::string accepted_native_operation_id{};
        std::string accepted_graph_receipt_wire_sha256{};
        std::string accepted_graph_receipt_sha256{};

    };
    std::uint32_t device_index_{};
    bool disabled_{};
    bool initialized_{};
    std::unordered_map<std::string, std::unique_ptr<Model>> models_;
    std::unordered_map<std::string, std::unique_ptr<Task>> tasks_;
    struct GroupRow {
        std::vector<std::int32_t> tokens;   // committed per-row history
        std::int32_t last_sampled{};
        bool has_sample{};
        bool completed{};
        bool active{true};                  // seats stay bound across churn
        std::uint64_t member_generation{};  // bumped when a seat rejoins
        // The native KV cursor for this seat's sequence: it advances once per
        // round the seat takes part in. An idle seat is wiped back to 0 before
        // each round, and join_group wipes it before a newcomer replays.
        std::uint32_t native_pos{};
    };
    struct GroupHost {
        ModelGroupId id{};
        std::string source_sha256;
        std::unique_ptr<llama_cassi_context, CassiContextDeleter> context;
        std::vector<std::unique_ptr<GroupRow>> rows;
        std::uint32_t embedding_width{};
        std::uint32_t layer_count{};
        std::uint32_t vocabulary_size{};
    };
    ModelGroupId next_group_id_{};
    std::unordered_map<ModelGroupId, std::unique_ptr<GroupHost>> groups_;

    static std::unique_ptr<llama_cassi_context, CassiContextDeleter> create_group_context(
        const Model& model, std::uint32_t capacity) {
        auto native = llama_context_default_params();
        native.n_ctx = model.context_size;
        native.n_batch = static_cast<std::uint32_t>(
            std::min<std::size_t>(std::max<std::size_t>(512U, capacity), model.context_size));
        native.n_ubatch = capacity;
        native.n_seq_max = capacity;
        native.n_outputs_max = 1;
        native.n_outputs_max_per_seq = 1;
        native.offload_kqv = true;
        native.n_rs_seq = 0;
        native.cassi_modal = false;
        native.cassi_field_step = false;
        native.cassi_qi_field = false;
        native.cassi_apprentice = false;
        native.cassi_attention_owned = nullptr;
        native.cassi_attention_owned_count = 0;
        native.samplers = nullptr;
        native.n_samplers = 0;
        native.ctx_other = nullptr;
        native.ctx_type = LLAMA_CONTEXT_TYPE_DEFAULT;
        native.embeddings = false;
        native.pooling_type = LLAMA_POOLING_TYPE_UNSPECIFIED;
        native.no_perf = false;

        auto params = llama_cassi_default_params();
        params.memory_bytes = 0;
        params.audit_interval = 0;
        params.teacher_policy = LLAMA_CASSI_NEVER;
        params.route_policy = LLAMA_CASSI_EXACT_PIPELINE;
        params.field_device = model.field_device.c_str();
        params.model_path = model.path.c_str();
        params.model_sha256 = model.source_digest.data();
        llama_cassi_context* raw_context = llama_cassi_init(model.model.get(), native, params);
        if (!raw_context) throw_context_error(nullptr, "llama.cpp could not create a shared weight-bank group host");
        return std::unique_ptr<llama_cassi_context, CassiContextDeleter>(raw_context);
    }

    static llama_cassi_sampler_params sampler_from_request(
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw,
        std::uint32_t vocabulary_size) {
        llama_cassi_sampler_params sampler{};
        if (sampler_mode == "greedy") {
            sampler.mode = LLAMA_CASSI_SAMPLER_GREEDY;
            sampler.temperature = 1.0F;
            sampler.top_k = 0;
            sampler.draw = 0.0;
        } else if (sampler_mode == "categorical") {
            if (!std::isfinite(temperature) || temperature <= 0.0 ||
                    !std::isfinite(draw) || draw < 0.0 || draw >= 1.0 ||
                    top_k > vocabulary_size) {
                throw ProtocolError("native model sampler parameters are invalid");
            }
            sampler.mode = LLAMA_CASSI_SAMPLER_CATEGORICAL;
            sampler.temperature = static_cast<float>(temperature);
            sampler.top_k = top_k;
            sampler.draw = draw;
        } else {
            throw ProtocolError("native model sampler mode is unsupported");
        }
        return sampler;
    }

    static void add_rows_in_place(
        std::span<float> residual,
        std::span<const float> delta,
        std::size_t n_rows,
        std::uint32_t width) {
        const auto count = static_cast<std::size_t>(width) * n_rows;
        if (residual.size() != count || delta.size() != count) {
            throw ProtocolError("group stage tensor shape diverged");
        }
        for (std::size_t index = 0; index < count; ++index) residual[index] += delta[index];
    }

    static ModelRegistration describe(const Model& model, std::string status) {
        std::vector<char> buffer(512, '\0');
        const auto required = llama_model_desc(model.model.get(), buffer.data(), buffer.size());
        if (required >= buffer.size()) buffer.assign(required + 1U, '\0');
        if (required >= 512U) llama_model_desc(model.model.get(), buffer.data(), buffer.size());
        return ModelRegistration{
            std::move(status),
            model.source_sha256,
            buffer.data(),
            static_cast<std::uint64_t>(llama_vocab_n_tokens(model.vocab)),
            model.context_size,
            llama_model_size(model.model.get()),
        };
    }

    static std::array<std::uint8_t, 32> parse_digest(std::string_view value) {
        std::array<std::uint8_t, 32> result{};
        const auto nibble = [](char character) -> std::uint8_t {
            if (character >= '0' && character <= '9') return static_cast<std::uint8_t>(character - '0');
            if (character >= 'a' && character <= 'f') return static_cast<std::uint8_t>(character - 'a' + 10);
            throw ProtocolError("model source_sha256 is invalid");
        };
        for (std::size_t index = 0; index < result.size(); ++index) {
            result[index] = static_cast<std::uint8_t>((nibble(value[2U * index]) << 4U) | nibble(value[2U * index + 1U]));
        }
        return result;
    }

    static std::vector<llama_cassi_service_stats> service_stats(llama_cassi_context* context) {
        const auto count = llama_cassi_service_stats_count(context);
        std::vector<llama_cassi_service_stats> result(count);
        if (count == 0U || llama_cassi_service_stats_get(context, result.data(), result.size()) != count) {
            throw_context_error(context, "llama.cpp did not expose its exact stage inventory");
        }
        return result;
    }

    static void throw_context_error(llama_cassi_context* context, std::string_view fallback) {
        const char* error = llama_cassi_last_error(context);
        throw ProtocolError(error != nullptr && error[0] != '\0' ? error : std::string(fallback));
    }

    static std::unique_ptr<Task> create_task(const Model& model, std::span<const std::int32_t> tokens) {
        auto native = llama_context_default_params();
        native.n_ctx = model.context_size;
        native.n_batch = static_cast<std::uint32_t>(std::min<std::size_t>(model.context_size, 512U));
        native.n_ubatch = LLAMA_CASSI_MAX_DRAFT_TOKENS + 1U;
        native.n_seq_max = 1;
        native.n_outputs_max = 1;
        native.n_outputs_max_per_seq = 1;
        native.offload_kqv = true;
        native.n_rs_seq = LLAMA_CASSI_MAX_DRAFT_TOKENS + 1U;
        native.cassi_modal = false;
        native.cassi_field_step = false;
        native.cassi_qi_field = false;
        native.cassi_apprentice = false;
        native.cassi_attention_owned = nullptr;
        native.cassi_attention_owned_count = 0;
        native.samplers = nullptr;
        native.n_samplers = 0;
        native.ctx_other = nullptr;
        native.ctx_type = LLAMA_CONTEXT_TYPE_DEFAULT;
        native.embeddings = false;
        native.pooling_type = LLAMA_POOLING_TYPE_UNSPECIFIED;
        native.no_perf = false;

        auto params = llama_cassi_default_params();
        params.memory_bytes = 0;
        params.audit_interval = 0;
        params.teacher_policy = LLAMA_CASSI_NEVER;
        params.route_policy = LLAMA_CASSI_EXACT_PIPELINE;
        params.field_device = model.field_device.c_str();
        params.model_path = model.path.c_str();
        params.model_sha256 = model.source_digest.data();
        auto* raw_context = llama_cassi_init(model.model.get(), native, params);
        if (!raw_context) throw_context_error(nullptr, "llama.cpp could not create an exact staged continuation");

        auto task = std::make_unique<Task>();
        task->context.reset(raw_context);
        task->tokens.assign(tokens.begin(), tokens.end());
        const auto remaining = model.context_size - static_cast<std::uint32_t>(tokens.size());
        if (llama_cassi_begin(task->context.get(), task->tokens.data(), task->tokens.size(), static_cast<std::int32_t>(remaining)) != 0) {
            throw_context_error(task->context.get(), "llama.cpp could not begin the exact staged continuation");
        }
        return task;
    }

    static void append_u64(std::vector<std::byte>& bytes, std::uint64_t value) {
        for (unsigned shift = 0; shift < 64U; shift += 8U) bytes.push_back(std::byte((value >> shift) & 0xffU));
    }

    static std::string stage_trace_digest(
        std::span<const std::int32_t> input_tokens,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw,
        std::int32_t output_token,
        std::uint64_t exact_stages,
        std::uint64_t embedding_stages,
        std::uint64_t attention_stages,
        std::uint64_t ffn_stages,
        std::uint64_t head_stages,
        std::uint64_t ggml_nodes,
        std::uint64_t logical_weight_bytes) {
        std::vector<std::byte> bytes;
        const std::string schema = "cassi.exact-model-stage-trace.v1";
        bytes.insert(bytes.end(), reinterpret_cast<const std::byte*>(schema.data()), reinterpret_cast<const std::byte*>(schema.data() + schema.size()));
        bytes.push_back(std::byte{0});
        append_u64(bytes, input_tokens.size());
        for (const auto token : input_tokens) append_u64(bytes, static_cast<std::uint32_t>(token));
        bytes.insert(bytes.end(), reinterpret_cast<const std::byte*>(sampler_mode.data()), reinterpret_cast<const std::byte*>(sampler_mode.data() + sampler_mode.size()));
        bytes.push_back(std::byte{0});
        append_u64(bytes, std::bit_cast<std::uint64_t>(temperature));
        append_u64(bytes, top_k);
        append_u64(bytes, std::bit_cast<std::uint64_t>(draw));
        append_u64(bytes, static_cast<std::uint32_t>(output_token));
        append_u64(bytes, exact_stages);
        append_u64(bytes, embedding_stages);
        append_u64(bytes, attention_stages);
        append_u64(bytes, ffn_stages);
        append_u64(bytes, head_stages);
        append_u64(bytes, ggml_nodes);
        append_u64(bytes, logical_weight_bytes);
        return hex_digest(sha256(bytes));
    }

    static std::string replay_digest(const std::string& source_sha256,
            std::span<const std::int32_t> tokens,
            std::optional<std::int32_t> trailing_token = std::nullopt) {
        const std::size_t token_count = tokens.size() + (trailing_token.has_value() ? 1U : 0U);
        std::vector<std::byte> bytes;
        bytes.reserve(source_sha256.size() + token_count * sizeof(std::uint32_t));
        for (const auto character : source_sha256) bytes.push_back(std::byte(static_cast<unsigned char>(character)));
        for (const auto value : tokens) {
            const auto token = static_cast<std::uint32_t>(value);
            for (unsigned shift = 0; shift < 32U; shift += 8U)
                bytes.push_back(std::byte((token >> shift) & 0xffU));
        }
        if (trailing_token.has_value()) {
            const auto token = static_cast<std::uint32_t>(*trailing_token);
            for (unsigned shift = 0; shift < 32U; shift += 8U)
                bytes.push_back(std::byte((token >> shift) & 0xffU));
        }
        return hex_digest(sha256(bytes));
    }
    static std::string input_tokens_sha256(std::span<const std::int32_t> tokens) {
        std::vector<std::byte> bytes;
        bytes.reserve(tokens.size() * sizeof(std::int32_t));
        for (const auto token : tokens) {
            const auto encoded = std::bit_cast<std::uint32_t>(token);
            for (unsigned shift = 0; shift < 32U; shift += 8U)
                bytes.push_back(std::byte((encoded >> shift) & 0xffU));
        }
        return hex_digest(sha256(bytes));
    }
};

#else


class LlamaBackend {
public:
    explicit LlamaBackend(std::uint32_t, bool enabled = true)
        : reason_(enabled ? "llama.cpp support was not linked" : "disabled by --cpu-only") {}
    [[nodiscard]] bool available() const noexcept { return false; }
    [[nodiscard]] std::string reason() const { return reason_; }
    [[nodiscard]] std::size_t task_count() const noexcept { return 0; }
    [[nodiscard]] std::size_t model_count() const noexcept { return 0; }
    std::string effective_sampler_sha256(const std::string&, const std::string&, double,
        std::uint32_t, double) const { throw ProtocolError(reason()); }
    ModelRegistration register_model(const std::string&, const std::string&, std::uint32_t, std::int32_t) { throw ProtocolError(reason()); }
    GraphSitePreflightWire graph_site_preflight(const std::string&, const std::string&,
        std::span<const std::int32_t>, const std::string&, double, std::uint32_t, double,
        const std::string&, const std::string&, const std::string&) {
        throw ProtocolError(reason());
    }
    ModelStepResult step(const std::string&, const std::string&, std::span<const std::int32_t>,
        const std::string&, double, std::uint32_t, double, const std::string&,
        const std::string& = {}, const std::string& = {}) { throw ProtocolError(reason()); }
    ModelStepResult step_graph_site_candidate(const std::string&, const std::string&,
        std::span<const std::int32_t>, const std::string&, const std::string&, const std::string&,
        const std::string&, const GraphSiteCandidateWire&) { throw ProtocolError(reason()); }
    ModelStepResult replay_graph_site_step(const std::string&, const std::string&,
        std::span<const std::int32_t>, const GraphSiteReplayStepWire&) { throw ProtocolError(reason()); }
    ModelStepResult confirm_graph_site_candidate(const std::string&, const std::string&,
        const std::string&, const std::string&, const std::string&, const std::string&) {
        throw ProtocolError(reason());
    }
    void rollback_accepted_graph_site_candidate(const std::string&, const std::string&,
        const std::string&, const std::string&) { throw ProtocolError(reason()); }
    bool drop_task(const std::string&) { return false; }
private:
    std::string reason_;
};

#endif

} // namespace cassifi::field_runtime
