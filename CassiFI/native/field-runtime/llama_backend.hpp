#pragma once

#include "protocol.hpp"
#include <algorithm>

#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
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
};

#ifdef CASSIFI_HAVE_LLAMA


class LlamaBackend {
public:
    explicit LlamaBackend(std::uint32_t device_index) : device_index_(device_index) {
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

    [[nodiscard]] bool available() const noexcept { return true; }
    [[nodiscard]] std::string reason() const { return {}; }
    [[nodiscard]] std::size_t task_count() const noexcept { return tasks_.size(); }
    [[nodiscard]] std::size_t model_count() const noexcept { return models_.size(); }

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

    ModelStepResult step(
        const std::string& task_id,
        const std::string& source_sha256,
        std::span<const std::int32_t> tokens,
        const std::string& sampler_mode,
        double temperature,
        std::uint32_t top_k,
        double draw) {
        if (task_id.empty() || task_id.size() > 512U) throw ProtocolError("model task identity is invalid");
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
        return ModelStepResult{
            selected.token,
            end_of_generation,
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
    }

    bool drop_task(const std::string& task_id) { return tasks_.erase(task_id) != 0U; }

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
    };

    std::uint32_t device_index_{};
    bool initialized_{};
    std::unordered_map<std::string, std::unique_ptr<Model>> models_;
    std::unordered_map<std::string, std::unique_ptr<Task>> tasks_;

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
        native.n_ubatch = 1;
        native.n_seq_max = 1;
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

    static std::string replay_digest(const std::string& source_sha256, std::span<const std::int32_t> tokens) {
        std::vector<std::byte> bytes;
        bytes.reserve(source_sha256.size() + tokens.size() * sizeof(std::uint32_t));
        for (const auto character : source_sha256) bytes.push_back(std::byte(static_cast<unsigned char>(character)));
        for (const auto value : tokens) {
            const auto token = static_cast<std::uint32_t>(value);
            for (unsigned shift = 0; shift < 32U; shift += 8U) bytes.push_back(std::byte((token >> shift) & 0xffU));
        }
        return hex_digest(sha256(bytes));
    }
};

#else


class LlamaBackend {
public:
    explicit LlamaBackend(std::uint32_t) {}
    [[nodiscard]] bool available() const noexcept { return false; }
    [[nodiscard]] std::string reason() const { return "llama.cpp support was not linked"; }
    [[nodiscard]] std::size_t task_count() const noexcept { return 0; }
    [[nodiscard]] std::size_t model_count() const noexcept { return 0; }
    ModelRegistration register_model(const std::string&, const std::string&, std::uint32_t, std::int32_t) { throw ProtocolError(reason()); }
    ModelStepResult step(const std::string&, const std::string&, std::span<const std::int32_t>, const std::string&, double, std::uint32_t, double) { throw ProtocolError(reason()); }
    bool drop_task(const std::string&) { return false; }
};

#endif

} // namespace cassifi::field_runtime
