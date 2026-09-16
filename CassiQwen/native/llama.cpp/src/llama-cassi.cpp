#include "llama-cassi.h"

#include "llama-cassi-field.h"
#include "llama-context.h"
#include "llama-model.h"
#include "llama-cpp.h"

#include "ggml-cpp.h"
#include "gguf.h"

extern "C" {
#include "sha256/sha256.h"
}

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

constexpr char CHECKPOINT_MAGIC[8] = { 'C', 'A', 'S', 'S', 'I', 'A', 'P', '1' };
constexpr uint32_t CHECKPOINT_VERSION = 1;
constexpr uint32_t CHECKPOINT_SCALES = 4;
constexpr uint32_t TOKEN_BYTES = 4;
constexpr uint16_t USER_SYMBOL = 258;
constexpr uint16_t END_SYMBOL = 256;
constexpr uint16_t ASSISTANT_SYMBOL = 259;
constexpr const char * PROFILE_ID = "cassi.qi.apprentice-engram.v1";

thread_local std::string init_error;

[[noreturn]] void fail(const char * code) {
    throw std::runtime_error(code);
}

double elapsed_ms(std::chrono::steady_clock::time_point begin) {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - begin).count();
}

struct elapsed_accumulator {
    std::chrono::steady_clock::time_point started = std::chrono::steady_clock::now();
    double & destination;

    explicit elapsed_accumulator(double & destination_value) : destination(destination_value) {
    }

    ~elapsed_accumulator() {
        destination += elapsed_ms(started);
    }
};

void hash_bytes(const uint8_t * data, size_t size, uint8_t digest[32]) {
    sha256_hash(digest, data, size);
}

std::array<uint8_t, 32> hash_file(const std::string & path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        fail("apprentice_model_hash_failed");
    }
    sha256_t state;
    sha256_init(&state);
    std::vector<uint8_t> buffer(1024 * 1024);
    while (input) {
        input.read(reinterpret_cast<char *>(buffer.data()), static_cast<std::streamsize>(buffer.size()));
        const std::streamsize count = input.gcount();
        if (count > 0) {
            sha256_update(&state, buffer.data(), static_cast<size_t>(count));
        }
    }
    if (!input.eof()) {
        fail("apprentice_model_hash_failed");
    }
    std::array<uint8_t, 32> digest = {};
    sha256_final(&state, digest.data());
    return digest;
}

struct model_metadata {
    uint32_t layers = 0;
    uint32_t embedding_width = 0;
    uint32_t vocabulary_size = 0;
    uint32_t context_length = 0;
};

int64_t checked_key(const gguf_context * context, const char * name, gguf_type type) {
    const int64_t key = gguf_find_key(context, name);
    if (key < 0 || gguf_get_kv_type(context, key) != type) {
        fail("apprentice_model_metadata_invalid");
    }
    return key;
}

model_metadata read_metadata(const std::string & path) {
    gguf_init_params params = {};
    params.no_alloc = true;
    params.ctx = nullptr;
    gguf_context_ptr context(gguf_init_from_file(path.c_str(), params));
    if (!context) {
        fail("apprentice_model_metadata_invalid");
    }
    const int64_t architecture_key = checked_key(context.get(), "general.architecture", GGUF_TYPE_STRING);
    if (std::strcmp(gguf_get_val_str(context.get(), architecture_key), "qwen35") != 0) {
        fail("apprentice_model_metadata_invalid");
    }
    model_metadata result;
    const uint32_t all_layers = gguf_get_val_u32(
        context.get(), checked_key(context.get(), "qwen35.block_count", GGUF_TYPE_UINT32));
    uint32_t nextn_layers = 0;
    const int64_t nextn_key = gguf_find_key(context.get(), "qwen35.nextn_predict_layers");
    if (nextn_key >= 0) {
        if (gguf_get_kv_type(context.get(), nextn_key) != GGUF_TYPE_UINT32) {
            fail("apprentice_model_metadata_invalid");
        }
        nextn_layers = gguf_get_val_u32(context.get(), nextn_key);
    }
    if (all_layers == 0 || nextn_layers >= all_layers) {
        fail("apprentice_model_metadata_invalid");
    }
    // NextN/MTP blocks are auxiliary draft layers outside the ordinary Qwen trunk.
    result.layers = all_layers - nextn_layers;
    result.embedding_width = gguf_get_val_u32(
        context.get(), checked_key(context.get(), "qwen35.embedding_length", GGUF_TYPE_UINT32));
    result.context_length = gguf_get_val_u32(
        context.get(), checked_key(context.get(), "qwen35.context_length", GGUF_TYPE_UINT32));
    const int64_t token_key = checked_key(context.get(), "tokenizer.ggml.tokens", GGUF_TYPE_ARRAY);
    if (gguf_get_arr_type(context.get(), token_key) != GGUF_TYPE_STRING) {
        fail("apprentice_model_metadata_invalid");
    }
    const int64_t token_count = gguf_get_arr_n(context.get(), token_key);
    if (token_count <= 0 || static_cast<uint64_t>(token_count) > std::numeric_limits<uint32_t>::max()) {
        fail("apprentice_model_metadata_invalid");
    }
    result.vocabulary_size = static_cast<uint32_t>(token_count);
    if (result.embedding_width == 0 || result.context_length == 0) {
        fail("apprentice_model_metadata_invalid");
    }
    return result;
}

size_t checked_add(size_t lhs, size_t rhs) {
    if (rhs > std::numeric_limits<size_t>::max() - lhs) {
        fail("apprentice_checkpoint_invalid");
    }
    return lhs + rhs;
}

void append_u32(std::vector<uint8_t> & bytes, uint32_t value) {
    for (unsigned shift = 0; shift < 32; shift += 8) {
        bytes.push_back(static_cast<uint8_t>(value >> shift));
    }
}

void append_i32(std::vector<uint8_t> & bytes, int32_t value) {
    append_u32(bytes, static_cast<uint32_t>(value));
}

void append_u64(std::vector<uint8_t> & bytes, uint64_t value) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
        bytes.push_back(static_cast<uint8_t>(value >> shift));
    }
}

void append_f32(std::vector<uint8_t> & bytes, float value) {
    uint32_t bits = 0;
    static_assert(sizeof(bits) == sizeof(value), "float32 checkpoint serialization");
    std::memcpy(&bits, &value, sizeof(bits));
    append_u32(bytes, bits);
}

struct byte_reader {
    const uint8_t * data;
    size_t size;
    size_t offset = 0;

    void require(size_t count) const {
        if (count > size - std::min(size, offset)) {
            fail("apprentice_checkpoint_invalid");
        }
    }

    const uint8_t * take(size_t count) {
        require(count);
        const uint8_t * result = data + offset;
        offset += count;
        return result;
    }

    uint32_t u32() {
        const uint8_t * value = take(4);
        return static_cast<uint32_t>(value[0]) |
            (static_cast<uint32_t>(value[1]) << 8) |
            (static_cast<uint32_t>(value[2]) << 16) |
            (static_cast<uint32_t>(value[3]) << 24);
    }

    int32_t i32() {
        return static_cast<int32_t>(u32());
    }

    uint64_t u64() {
        const uint8_t * value = take(8);
        uint64_t result = 0;
        for (unsigned index = 0; index < 8; ++index) {
            result |= static_cast<uint64_t>(value[index]) << (8 * index);
        }
        return result;
    }

    float f32() {
        const uint32_t bits = u32();
        float result = 0.0f;
        std::memcpy(&result, &bits, sizeof(result));
        return result;
    }
};

uint64_t loaded_tensor_bytes(const llama_model & model) {
    std::unordered_set<const ggml_tensor *> seen;
    uint64_t total = 0;
    for (const auto & item : model.tensors_by_name) {
        const ggml_tensor * tensor = item.second;
        if (tensor == nullptr || tensor->buffer == nullptr || !seen.insert(tensor).second) {
            continue;
        }
        const size_t bytes = ggml_nbytes(tensor);
        if (bytes > std::numeric_limits<uint64_t>::max() - total) {
            fail("apprentice_model_metadata_invalid");
        }
        total += bytes;
    }
    return total;
}

std::string token_piece(const llama_vocab * vocab, llama_token token) {
    std::string piece;
    piece.resize(piece.capacity());
    int32_t count = llama_token_to_piece(vocab, token, piece.data(), static_cast<int32_t>(piece.size()), 0, true);
    if (count < 0) {
        if (count == std::numeric_limits<int32_t>::min()) {
            fail("apprentice_token_invalid");
        }
        piece.resize(static_cast<size_t>(-count));
        count = llama_token_to_piece(vocab, token, piece.data(), static_cast<int32_t>(piece.size()), 0, true);
        if (count < 0 || static_cast<size_t>(count) != piece.size()) {
            fail("apprentice_token_invalid");
        }
    } else {
        piece.resize(static_cast<size_t>(count));
    }
    return piece;
}

enum class session_state {
    idle,
    ready,
    pending,
    done,
    error,
    cancelled,
};

struct pending_event {
    llama_cassi_token result = {};
    bool teach_text = false;
    bool audit = false;
    bool teach_head = false;
    bool rollback_field = false;
    bool rollback_hash_valid = false;
    uint64_t rollback_revision = 0;
    uint64_t rollback_observations = 0;
    uint64_t rollback_field_evictions = 0;
    uint64_t rollback_stats_evictions = 0;
    std::vector<uint8_t> rollback_context_snapshot;
    std::array<uint8_t, 32> rollback_hash = {};
};

struct pending_vector_admission {
    uint32_t page = 0;
    size_t position = 0;
    llama_token token = 0;
    std::string piece;
    std::vector<float> input;
    std::vector<float> target;
};

} // namespace

struct llama_cassi_context {
    llama_model * model = nullptr;
    llama_context_params native_params = {};
    llama_cassi_params public_params = {};
    std::string field_device;
    std::string model_path;
    model_metadata metadata;
    std::array<uint8_t, 32> model_hash = {};
    std::array<uint8_t, 32> profile_hash = {};
    std::array<uint8_t, 32> idle_field_hash = {};
    bool idle_field_hash_valid = false;
    bool state_loaded = false;
    bool fully_loaded = false;

    std::unique_ptr<llama_cassi_field> field;
    std::unique_ptr<llama_context, llama_context_deleter> teacher;
    size_t teacher_prefix = 0;
    llama_cassi_capture teacher_capture;
    std::unique_ptr<llama_context, llama_context_deleter> service;
    std::vector<uint8_t> attention_owned;
    size_t service_prefix = 0;
    bool service_token_active = false;
    uint64_t service_epoch = 0;
    bool service_abandoned = false;
    size_t prompt_token_count = 0;
    std::vector<pending_vector_admission> pending_vector_admissions;
    uint64_t pending_admission_payload_bytes = 0;
    std::vector<uint8_t> transaction_field_snapshot;
    pending_event accepted;
    std::vector<uint8_t> context_snapshot;

    std::vector<float> pending_head_input;
    session_state state = session_state::idle;
    std::atomic<bool> cancellation_requested{false};
    std::string error;
    std::vector<llama_token> token_log;
    int32_t prediction_limit = 0;
    pending_event pending;
    llama_cassi_stats stats = {};
    std::vector<llama_cassi_service_stats> service_stats;
    std::vector<uint64_t> service_node_baseline;
    std::vector<uint64_t> service_weight_baseline;
    std::vector<std::string> native_backends;
    std::chrono::steady_clock::time_point request_started = {};

    llama_cassi_context(
            llama_model * model_value,
            llama_context_params native_params_value,
            const llama_cassi_params & params_value) :
        model(model_value), native_params(native_params_value) {
        if (model == nullptr || params_value.model_path == nullptr || params_value.model_path[0] == '\0') {
            fail("apprentice_model_path_required");
        }
        if (params_value.field_device == nullptr || params_value.field_device[0] == '\0') {
            fail("apprentice_backend_unsupported");
        }
        if (params_value.teacher_policy < LLAMA_CASSI_ADAPTIVE || params_value.teacher_policy > LLAMA_CASSI_NEVER ||
            params_value.route_policy < LLAMA_CASSI_AUTO || params_value.route_policy > LLAMA_CASSI_PIPELINE) {
            fail("apprentice_configuration_invalid");
        }
        if (native_params.cassi_modal || native_params.cassi_field_step || native_params.cassi_qi_field ||
            native_params.cassi_apprentice || native_params.cassi_attention_owned != nullptr ||
            native_params.cassi_attention_owned_count != 0 || native_params.samplers != nullptr ||
            native_params.n_samplers != 0 || native_params.ctx_other != nullptr ||
            native_params.ctx_type != LLAMA_CONTEXT_TYPE_DEFAULT || native_params.embeddings ||
            (native_params.pooling_type != LLAMA_POOLING_TYPE_UNSPECIFIED && native_params.pooling_type != LLAMA_POOLING_TYPE_NONE) ||
            native_params.no_perf) {
            fail("apprentice_configuration_conflict");
        }
        field_device = params_value.field_device;
        model_path = params_value.model_path;
        public_params = params_value;
        public_params.field_device = field_device.c_str();
        public_params.model_path = model_path.c_str();

        metadata = read_metadata(model_path);
        model_hash = hash_file(model_path);
        if (model->arch != LLM_ARCH_QWEN35) {
            fail("apprentice_model_metadata_invalid");
        }
        fully_loaded = model->tok_embd != nullptr && model->tok_embd->buffer != nullptr;
        if (fully_loaded) {
            if (model->hparams.n_layer() != metadata.layers || model->hparams.n_embd != metadata.embedding_width ||
                model->vocab.n_tokens() != static_cast<int32_t>(metadata.vocabulary_size) ||
                model->hparams.n_ctx_train != metadata.context_length) {
                fail("apprentice_model_metadata_invalid");
            }
        } else if (public_params.teacher_policy != LLAMA_CASSI_NEVER) {
            fail("apprentice_model_weights_required");
        }
        if (native_params.n_ctx == 0 || native_params.n_ctx > metadata.context_length) {
            fail("apprentice_context_invalid");
        }
        native_params.n_seq_max = 1;
        native_params.n_rs_seq = 0;
        native_params.n_ubatch = 1;
        native_params.n_batch = std::max<uint32_t>(1, native_params.n_batch);
        native_params.n_outputs_max = 1;
        native_params.n_outputs_max_per_seq = 1;
        native_params.cassi_modal = false;
        native_params.cassi_field_step = false;
        native_params.cassi_qi_field = false;
        native_params.cassi_apprentice = false;
        native_params.cassi_attention_owned = nullptr;
        native_params.cassi_attention_owned_count = 0;
        native_params.samplers = nullptr;
        native_params.n_samplers = 0;

        cassi_field_config field_config;
        field_config.layers = metadata.layers;
        field_config.embedding_width = metadata.embedding_width;
        field_config.vocabulary_size = metadata.vocabulary_size;
        field_config.memory_bytes = public_params.memory_bytes;
        field_config.device = field_device;
        field = std::make_unique<llama_cassi_field>(field_config);
        field->profile_sha256(profile_hash.data());
        context_snapshot.resize(field->context_snapshot_size());
        attention_owned.resize(metadata.layers);
        stats.field_bytes = field->field_bytes();
        pending_head_input.resize(metadata.embedding_width);
        stats.loaded_model_tensor_bytes = loaded_tensor_bytes(*model);
        std::unordered_set<std::string> seen_backends;
        for (const auto & item : model->tensors_by_name) {
            const ggml_tensor * tensor = item.second;
            if (tensor == nullptr || tensor->buffer == nullptr) {
                continue;
            }
            const ggml_backend_buffer_type_t buft = ggml_backend_buffer_get_type(tensor->buffer);
            const ggml_backend_dev_t device = ggml_backend_buft_get_device(buft);
            const std::string name = device != nullptr
                ? ggml_backend_dev_name(device)
                : ggml_backend_buft_name(buft);
            if (seen_backends.insert(name).second) {
                native_backends.push_back(name);
            }
        }
        for (const cassi_field_page & page : field->pages()) {
            llama_cassi_service_stats value = {};
            value.kind = static_cast<uint32_t>(page.kind);
            value.layer = page.layer;
            service_stats.push_back(value);
        }
        service_node_baseline.resize(service_stats.size());
        service_weight_baseline.resize(service_stats.size());
    }

    const llama_vocab * vocab() const {
        return llama_model_get_vocab(model);
    }

    void set_error(const char * code) {
        error = code;
        state = session_state::error;
    }

    void check_cancelled() {
        if (cancellation_requested.load(std::memory_order_acquire)) {
            state = session_state::cancelled;
            fail("apprentice_cancelled");
        }
    }

    void timed_sense_marker(uint16_t symbol) {
        const auto started = std::chrono::steady_clock::now();
        field->sense_marker(symbol);
        stats.field_ms += elapsed_ms(started);
        stats.field_steps += 1 + metadata.layers;
    }

    void timed_sense_token(llama_token token) {
        const std::string piece = token_piece(vocab(), token);
        const auto started = std::chrono::steady_clock::now();
        field->sense_token(token, piece, llama_vocab_is_eog(vocab(), token));
        stats.field_ms += elapsed_ms(started);
        stats.field_steps += static_cast<uint64_t>(piece.size() + (llama_vocab_is_eog(vocab(), token) ? 1 : 0)) *
            (1 + metadata.layers);
    }

    cassi_probe timed_probe(const cassi_query & query) {
        const auto started = std::chrono::steady_clock::now();
        cassi_probe result = field->probe(query);
        stats.field_ms += elapsed_ms(started);
        return result;
    }

    cassi_observation timed_observe(const cassi_query & query, const cassi_target & target) {
        const auto started = std::chrono::steady_clock::now();
        cassi_observation result = field->observe(query, target);
        stats.field_ms += elapsed_ms(started);
        stats.field_observations++;
        if (result.evicted) {
            stats.engram_evictions++;
        }
        return result;
    }

    uint8_t timed_guide_byte(uint8_t byte) {
        const auto started = std::chrono::steady_clock::now();
        const uint8_t result = field->guide_byte(byte);
        stats.field_ms += elapsed_ms(started);
        return result;
    }

    cassi_query text_query(uint32_t byte_index, const std::array<uint8_t, TOKEN_BYTES> & prefix) const {
        cassi_query query;
        query.page = 0;
        query.byte_index = byte_index;
        query.id_prefix = prefix;
        return query;
    }
    uint32_t service_page(llama_cassi_service_kind kind, int32_t layer) const {
        switch (kind) {
            case LLAMA_CASSI_TEXT: return 0;
            case LLAMA_CASSI_EMBED: return 1;
            case LLAMA_CASSI_HEAD: return 2;
            case LLAMA_CASSI_ATTENTION:
                if (layer >= 0 && static_cast<uint32_t>(layer) < metadata.layers) {
                    return 3 + 2 * static_cast<uint32_t>(layer);
                }
                break;
            case LLAMA_CASSI_FFN:
                if (layer >= 0 && static_cast<uint32_t>(layer) < metadata.layers) {
                    return 4 + 2 * static_cast<uint32_t>(layer);
                }
                break;
        }
        fail("apprentice_service_invalid");
    }

    void record_service_skip(uint32_t page_index, uint64_t output_rows) {
        service_stats[page_index].skipped++;
        stats.native_output_rows_skipped += output_rows;
        if (service_node_baseline[page_index] == 0) {
            stats.native_nodes_skipped_known = false;
        } else {
            stats.native_ggml_nodes_skipped += service_node_baseline[page_index];
        }
    }

    ggml_tensor * timed_guide_vector(ggml_tensor * vector) {
        const auto started = std::chrono::steady_clock::now();
        ggml_tensor * result = field->guide_vector(vector);
        stats.field_ms += elapsed_ms(started);
        return result;
    }

    ggml_tensor * timed_add_vectors(ggml_tensor * left, ggml_tensor * right) {
        const auto started = std::chrono::steady_clock::now();
        ggml_tensor * result = field->add_vectors(left, right);
        stats.field_ms += elapsed_ms(started);
        return result;
    }
    ggml_tensor * timed_copy_vector(ggml_tensor * source, uint32_t slot) {
        const auto started = std::chrono::steady_clock::now();
        ggml_tensor * result = field->copy_vector(source, slot);
        stats.field_ms += elapsed_ms(started);
        return result;
    }

    void stage_vector_observation(
            const cassi_query & query,
            ggml_tensor * target,
            size_t position) {
        const auto valid_vector = [&](ggml_tensor * tensor) {
            return tensor != nullptr && tensor->type == GGML_TYPE_F32 &&
                ggml_is_contiguous(tensor) &&
                ggml_nelements(tensor) == metadata.embedding_width &&
                (tensor->buffer != nullptr ||
                    (tensor->view_src != nullptr && tensor->view_src->buffer != nullptr));
        };
        if (!valid_vector(target) || (query.input != nullptr && !valid_vector(query.input)) ||
                (query.piece_size != 0 && query.piece == nullptr)) {
            fail("apprentice_service_vector_invalid");
        }
        const uint64_t vector_payload_bytes =
            static_cast<uint64_t>(metadata.embedding_width) * sizeof(float);
        uint64_t additional_payload_bytes =
            sizeof(pending_vector_admission) + vector_payload_bytes;
        if (query.input != nullptr) {
            additional_payload_bytes += vector_payload_bytes;
        }
        if (query.piece_size > std::numeric_limits<uint64_t>::max() - additional_payload_bytes) {
            fail("apprentice_pending_admission_limit");
        }
        additional_payload_bytes += static_cast<uint64_t>(query.piece_size);
        const uint64_t payload_limit = field->state_size();
        if (additional_payload_bytes > payload_limit ||
                pending_admission_payload_bytes > payload_limit - additional_payload_bytes) {
            fail("apprentice_pending_admission_limit");
        }
        pending_vector_admission admission;
        admission.page = query.page;
        admission.position = position;
        admission.token = query.token;
        if (query.piece_size != 0) {
            admission.piece.assign(
                reinterpret_cast<const char *>(query.piece),
                query.piece_size);
        }
        if (query.input != nullptr) {
            admission.input.resize(metadata.embedding_width);
            ggml_backend_tensor_get(
                query.input, admission.input.data(), 0,
                admission.input.size() * sizeof(float));
        }
        admission.target.resize(metadata.embedding_width);
        ggml_backend_tensor_get(
            target, admission.target.data(), 0,
            admission.target.size() * sizeof(float));
        pending_vector_admissions.push_back(std::move(admission));
        pending_admission_payload_bytes += additional_payload_bytes;
        stats.pending_admission_payload_bytes_peak =
            std::max(stats.pending_admission_payload_bytes_peak, pending_admission_payload_bytes);
    }

    void clear_pending_admissions() {
        pending_vector_admissions.clear();
        pending_admission_payload_bytes = 0;
    }

    void replay_vector_observations() {
        if (pending_vector_admissions.empty()) {
            return;
        }
        size_t position = std::numeric_limits<size_t>::max();
        try {
            for (const pending_vector_admission & admission : pending_vector_admissions) {
                check_cancelled();
                if (admission.position != position) {
                    set_reconstructed_context(admission.position);
                    position = admission.position;
                }
                ggml_tensor * input = nullptr;
                if (!admission.input.empty()) {
                    input = timed_copy_vector(
                        field->load_vector(admission.input.data(), admission.input.size()), 0);
                }
                ggml_tensor * target_vector =
                    field->load_vector(admission.target.data(), admission.target.size());
                cassi_query query;
                query.page = admission.page;
                query.input = input;
                query.token = admission.token;
                if (!admission.piece.empty()) {
                    query.piece =
                        reinterpret_cast<const uint8_t *>(admission.piece.data());
                    query.piece_size = admission.piece.size();
                }
                cassi_target target;
                target.vector = target_vector;
                timed_observe(query, target);
            }
            field->context_snapshot_set(
                pending.rollback_context_snapshot.data(),
                pending.rollback_context_snapshot.size());
        } catch (...) {
            field->context_snapshot_set(
                pending.rollback_context_snapshot.data(),
                pending.rollback_context_snapshot.size());
            throw;
        }
        idle_field_hash_valid = false;
    }


    void set_reconstructed_context(size_t position) {
        if (position >= token_log.size() || prompt_token_count == 0) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        field->reset_context();
        timed_sense_marker(USER_SYMBOL);
        const size_t prompt_end = std::min(position + 1, prompt_token_count);
        for (size_t index = 0; index < prompt_end; ++index) {
            const std::string piece = token_piece(vocab(), token_log[index]);
            const auto started = std::chrono::steady_clock::now();
            field->sense_token(token_log[index], piece, false);
            stats.field_ms += elapsed_ms(started);
            stats.field_steps += static_cast<uint64_t>(piece.size()) * (1 + metadata.layers);
        }
        if (position + 1 >= prompt_token_count) {
            timed_sense_marker(END_SYMBOL);
            timed_sense_marker(ASSISTANT_SYMBOL);
            for (size_t index = prompt_token_count; index <= position; ++index) {
                timed_sense_token(token_log[index]);
            }
        }
    }

    void reconstruct_context(size_t position) {
        field->context_snapshot_get(context_snapshot.data(), context_snapshot.size());
        set_reconstructed_context(position);
    }

    void restore_context() {
        field->context_snapshot_set(context_snapshot.data(), context_snapshot.size());
    }

    void record_teacher_footprint(bool head_computed) {
        const auto record = [&](llama_cassi_service_kind kind,
                                int32_t layer,
                                ggml_tensor * output,
                                ggml_tensor * boundary,
                                bool embedding_row) {
            const uint32_t page_index = service_page(kind, layer);
            const uint64_t nodes = static_cast<uint64_t>(
                teacher->cassi_graph_nodes_between(output, boundary));
            const uint64_t bytes =
                teacher->cassi_graph_weight_bytes_between(output, boundary, embedding_row);
            service_stats[page_index].logical_weight_bytes += bytes;
            service_node_baseline[page_index] = nodes;
            service_weight_baseline[page_index] = bytes;
        };
        record(LLAMA_CASSI_EMBED, -1, teacher_capture.embedding, nullptr, true);
        for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
            record(
                LLAMA_CASSI_ATTENTION,
                static_cast<int32_t>(layer),
                teacher_capture.attention_delta[layer],
                teacher_capture.attention_input[layer],
                false);
            record(
                LLAMA_CASSI_FFN,
                static_cast<int32_t>(layer),
                teacher_capture.ffn_delta[layer],
                teacher_capture.ffn_input[layer],
                false);
        }
        if (head_computed) {
            record(
                LLAMA_CASSI_HEAD,
                -1,
                teacher_capture.head_output,
                teacher_capture.head_input,
                false);
        }
    }

    void teach_teacher_capture(size_t position, llama_token token) {
        if (!teacher->cassi_capture_get(teacher_capture)) {
            fail("apprentice_teacher_capture_failed");
        }
        record_teacher_footprint(position + 1 == token_log.size());
        reconstruct_context(position);
        try {
            const auto observe_vector = [&](uint32_t page, ggml_tensor * input, ggml_tensor * target_vector) {
                check_cancelled();
                stage_vector_observation(
                    vector_query(page, input, token, nullptr),
                    target_vector,
                    position);
            };

            const std::string piece = token_piece(vocab(), token);
            stage_vector_observation(
                vector_query(service_page(LLAMA_CASSI_EMBED, -1), nullptr, token, &piece),
                teacher_capture.embedding,
                position);
            for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
                observe_vector(
                    service_page(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer)),
                    teacher_capture.attention_input[layer],
                    teacher_capture.attention_delta[layer]);
                observe_vector(
                    service_page(LLAMA_CASSI_FFN, static_cast<int32_t>(layer)),
                    teacher_capture.ffn_input[layer],
                    teacher_capture.ffn_delta[layer]);
            }
            restore_context();
        } catch (...) {
            restore_context();
            throw;
        }
    }

    void stage_pending_field_rollback() {
        if (pending.rollback_field) {
            return;
        }
        transaction_field_snapshot.resize(field->state_size());
        field->state_get(
            transaction_field_snapshot.data(),
            transaction_field_snapshot.size());
        stats.pending_rollback_bytes_peak =
            std::max<uint64_t>(
                stats.pending_rollback_bytes_peak,
                transaction_field_snapshot.size());
        pending.rollback_field = true;
        pending.rollback_hash_valid = idle_field_hash_valid;
        pending.rollback_revision = field->field_revision();
        pending.rollback_observations = stats.field_observations;
        pending.rollback_field_evictions = field->engram_evictions();
        pending.rollback_stats_evictions = stats.engram_evictions;
        pending.rollback_hash = idle_field_hash;
    }

    void clear_accepted_transaction() {
        accepted = {};
        transaction_field_snapshot.clear();
    }

    void rollback_accepted_transaction() {
        if (token_log.size() <= prompt_token_count) {
            return;
        }
        if (state != session_state::ready && state != session_state::done) {
            fail("apprentice_invalid_transition");
        }
        if (accepted.rollback_field) {
            field->state_set(
                transaction_field_snapshot.data(),
                transaction_field_snapshot.size(),
                accepted.rollback_revision,
                accepted.rollback_field_evictions);
        }
        field->context_snapshot_set(
            accepted.rollback_context_snapshot.data(),
            accepted.rollback_context_snapshot.size());
        stats.field_observations = accepted.rollback_observations;
        stats.engram_evictions = accepted.rollback_stats_evictions;
        idle_field_hash_valid = accepted.rollback_hash_valid;
        idle_field_hash = accepted.rollback_hash;
        if (stats.committed_tokens == 0 || token_log.size() <= prompt_token_count ||
                token_log.back() != accepted.result.token) {
            fail("apprentice_invalid_transition");
        }
        stats.committed_tokens--;
        if (accepted.result.readout_kind == 0) {
            stats.field_exact_tokens--;
        } else if (accepted.result.readout_kind == 1) {
            stats.field_interpolated_tokens--;
        } else {
            stats.teacher_guided_tokens--;
        }
        token_log.pop_back();
        teacher.reset();
        teacher_prefix = 0;
        service.reset();
        service_prefix = 0;
        service_token_active = false;
        service_epoch = 0;
        service_abandoned = false;
        refresh_cache_gauges();
        clear_accepted_transaction();
        state = session_state::ready;
    }

    void restore_pending_field_rollback() {
        if (!pending.rollback_field) {
            return;
        }
        field->state_set(
            transaction_field_snapshot.data(),
            transaction_field_snapshot.size(),
            pending.rollback_revision,
            pending.rollback_field_evictions);
        field->context_snapshot_set(
            pending.rollback_context_snapshot.data(),
            pending.rollback_context_snapshot.size());
        stats.field_observations = pending.rollback_observations;
        stats.engram_evictions = pending.rollback_stats_evictions;
        idle_field_hash_valid = pending.rollback_hash_valid;
        idle_field_hash = pending.rollback_hash;
        transaction_field_snapshot.clear();
        pending.rollback_field = false;
    }

    void stage_pending_head(ggml_tensor * input) {
        if (input == nullptr || input->type != GGML_TYPE_F32 ||
                ggml_nelements(input) != metadata.embedding_width ||
                (input->buffer == nullptr && (input->view_src == nullptr || input->view_src->buffer == nullptr))) {
            fail("apprentice_native_head_input_invalid");
        }
        ggml_backend_tensor_get(
            input,
            pending_head_input.data(),
            0,
            pending_head_input.size() * sizeof(float));
        pending.teach_head = true;
    }

    void teach_pending_head(llama_token token) {
        const auto load_started = std::chrono::steady_clock::now();
        ggml_tensor * input = field->load_vector(pending_head_input.data(), pending_head_input.size());
        stats.field_ms += elapsed_ms(load_started);
        const uint32_t value = static_cast<uint32_t>(token);
        const uint32_t page_index = service_page(LLAMA_CASSI_HEAD, -1);
        std::array<uint8_t, TOKEN_BYTES> prefix = {};
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            check_cancelled();
            const uint8_t byte = static_cast<uint8_t>((value >> (8 * index)) & 0xffU);
            cassi_query query;
            query.page = page_index;
            query.input = input;
            query.byte_index = index;
            query.id_prefix = prefix;
            cassi_target target;
            target.is_byte = true;
            target.byte = byte;
            timed_observe(query, target);
            prefix[index] = byte;
        }
        idle_field_hash_valid = false;
    }


    void ensure_service_context(size_t position) {
        if (service_abandoned || !fully_loaded || position != service_prefix) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (service) {
            return;
        }
        if (position != 0) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        llama_context_params params = native_params;
        params.cassi_apprentice = true;
        params.cassi_attention_owned = attention_owned.data();
        params.cassi_attention_owned_count = static_cast<uint32_t>(attention_owned.size());
        llama_context * raw = llama_init_from_model(model, params);
        if (raw == nullptr) {
            fail("apprentice_native_service_initialization_failed");
        }
        service.reset(raw);
        service_epoch = 0;
        service_token_active = false;
        stats.native_context_creations++;
        refresh_cache_gauges();
    }

    ggml_tensor * call_native_service(
            llama_cassi_service_kind kind,
            int32_t layer,
            ggml_tensor * input,
            llama_token token,
            size_t position) {
        ensure_service_context(position);
        if (!service_token_active) {
            if (service->cassi_begin_token(token, static_cast<llama_pos>(position)) != 0) {
                service.reset();
                fail("apprentice_native_service_failed");
            }
            service_token_active = true;
            service_epoch++;
        }
        llm_cassi_service_config config;
        config.kind = kind;
        config.layer = layer;
        config.input = input;
        config.request_epoch = service_epoch;
        const auto started = std::chrono::steady_clock::now();
        ggml_tensor * result = service->cassi_service(config);
        stats.native_service_ms += elapsed_ms(started);
        if (result == nullptr) {
            service.reset();
            service_token_active = false;
            fail("apprentice_native_service_failed");
        }
        stats.native_service_calls++;
        const uint32_t page_index = service_page(kind, layer);
        const uint64_t graph_nodes = static_cast<uint64_t>(service->cassi_service_graph_nodes());
        const uint64_t logical_weight_bytes = service->cassi_last_graph_weight_bytes();
        stats.native_ggml_nodes_executed += graph_nodes;
        stats.logical_weight_bytes += logical_weight_bytes;
        service_stats[page_index].computed++;
        service_stats[page_index].logical_weight_bytes += logical_weight_bytes;
        service_node_baseline[page_index] = graph_nodes;
        service_weight_baseline[page_index] = logical_weight_bytes;
        stats.native_output_rows_computed += kind == LLAMA_CASSI_HEAD ? metadata.vocabulary_size : 1;
        return result;
    }

    cassi_query vector_query(
            uint32_t page_index,
            ggml_tensor * input,
            llama_token token,
            const std::string * piece) const {
        cassi_query query;
        query.page = page_index;
        if (field->page(page_index).kind == CASSI_FIELD_EMBED) {
            query.token = token;
            if (piece != nullptr) {
                query.piece = reinterpret_cast<const uint8_t *>(piece->data());
                query.piece_size = piece->size();
            }
        } else {
            query.input = input;
        }
        return query;
    }

    ggml_tensor * resolve_vector_service(
            llama_cassi_service_kind kind,
            int32_t layer,
            ggml_tensor * input,
            llama_token token,
            const std::string * piece,
            size_t position) {
        const uint32_t page_index = service_page(kind, layer);
        const cassi_query query = vector_query(page_index, input, token, piece);
        const cassi_probe proposal = timed_probe(query);
        const bool sticky_native = kind == LLAMA_CASSI_ATTENTION && attention_owned[layer] == 0;
        if (proposal.eligible && !sticky_native) {
            record_service_skip(page_index, 1);
            return proposal.target;
        }
        if (kind == LLAMA_CASSI_ATTENTION && attention_owned[layer] != 0) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (public_params.teacher_policy == LLAMA_CASSI_NEVER) {
            fail("apprentice_teacher_required");
        }
        ggml_tensor * native = call_native_service(kind, layer, input, token, position);
        stage_vector_observation(query, native, position);
        return timed_guide_vector(native);
    }

    llama_cassi_token resolve_head(ggml_tensor * input, llama_token token, size_t position) {
        std::array<uint8_t, TOKEN_BYTES> decoded = {};
        bool available = true;
        bool interpolated = false;
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            cassi_query query;
            query.page = service_page(LLAMA_CASSI_HEAD, -1);
            query.input = input;
            query.byte_index = index;
            query.id_prefix = decoded;
            const cassi_probe proposal = timed_probe(query);
            if (!proposal.eligible || !proposal.is_byte) {
                available = false;
                break;
            }
            decoded[index] = proposal.byte;
            interpolated = interpolated || proposal.status == CASSI_PROBE_FIELD_INTERPOLATED;
        }
        uint32_t selected = 0;
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            selected |= static_cast<uint32_t>(decoded[index]) << (8 * index);
        }
        const uint32_t page_index = service_page(LLAMA_CASSI_HEAD, -1);
        if (available && selected < metadata.vocabulary_size) {
            record_service_skip(page_index, metadata.vocabulary_size);
            llama_cassi_token result = {};
            result.token = static_cast<llama_token>(selected);
            result.decision_source = 0;
            result.native_dependency = 0;
            result.readout_kind = interpolated ? 1 : 0;
            return result;
        }
        if (public_params.teacher_policy == LLAMA_CASSI_NEVER) {
            fail(available ? "apprentice_token_invalid" : "apprentice_teacher_required");
        }
        ggml_tensor * logits_tensor =
            call_native_service(LLAMA_CASSI_HEAD, -1, input, token, position);
        const int64_t logits_count = ggml_nelements(logits_tensor);
        if (logits_count != metadata.vocabulary_size) {
            throw std::runtime_error(
                "apprentice_native_head_shape_invalid:expected=" +
                std::to_string(metadata.vocabulary_size) +
                ":actual=" + std::to_string(logits_count));
        }
        std::vector<float> logits(metadata.vocabulary_size);
        ggml_backend_tensor_get(logits_tensor, logits.data(), 0, logits.size() * sizeof(float));
        selected = 0;
        float best = -std::numeric_limits<float>::infinity();
        for (uint32_t candidate = 0; candidate < metadata.vocabulary_size; ++candidate) {
            if (!std::isfinite(logits[candidate])) {
                fail("apprentice_native_service_nonfinite");
            }
            if (logits[candidate] > best) {
                best = logits[candidate];
                selected = candidate;
            }
        }
        stats.native_logits_reads++;
        stage_pending_head(input);
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            const uint8_t byte = static_cast<uint8_t>((selected >> (8 * index)) & 0xffU);
            if (timed_guide_byte(byte) != byte) {
                fail("apprentice_assimilation_failed");
            }
        }
        llama_cassi_token result = {};
        result.token = static_cast<llama_token>(selected);
        result.decision_source = 1;
        result.native_dependency = 1;
        result.readout_kind = 2;
        return result;
    }

    llama_cassi_token process_pipeline_token(size_t position, bool emit_head) {
        check_cancelled();
        reconstruct_context(position);
        try {
            const llama_token token = token_log[position];
            const std::string piece = token_piece(vocab(), token);
            uint32_t residual_slot = 0;
            ggml_tensor * residual = timed_copy_vector(
                resolve_vector_service(LLAMA_CASSI_EMBED, -1, nullptr, token, &piece, position),
                residual_slot);
            for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
                ggml_tensor * attention =
                    resolve_vector_service(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer),
                        residual, token, nullptr, position);
                residual = timed_add_vectors(residual, attention);
                residual_slot ^= 1;
                residual = timed_copy_vector(residual, residual_slot);
                ggml_tensor * ffn =
                    resolve_vector_service(LLAMA_CASSI_FFN, static_cast<int32_t>(layer),
                        residual, token, nullptr, position);
                residual = timed_add_vectors(residual, ffn);
                residual_slot ^= 1;
                residual = timed_copy_vector(residual, residual_slot);
            }
            llama_cassi_token result = {};
            if (emit_head) {
                result = resolve_head(residual, token, position);
            }
            if (service_token_active) {
                if (service->cassi_end_token() != 0) {
                    fail("apprentice_native_service_failed");
                }
                service_token_active = false;
                if (position < prompt_token_count) {
                    stats.native_prefill_tokens++;
                } else {
                    stats.native_decode_tokens++;
                }
            }
            service_prefix = position + 1;
            restore_context();
            return result;
        } catch (...) {
            service.reset();
            service_token_active = false;
            restore_context();
            throw;
        }
    }

    llama_cassi_token run_pipeline() {
        if (service_abandoned || token_log.empty()) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        llama_cassi_token result = {};
        while (service_prefix < token_log.size()) {
            check_cancelled();
            result = process_pipeline_token(service_prefix, service_prefix + 1 == token_log.size());
        }
        return result;
    }


    void teach_pending_text(llama_token token) {
        const uint32_t value = static_cast<uint32_t>(token);
        std::array<uint8_t, TOKEN_BYTES> prefix = {};
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            check_cancelled();
            const uint8_t byte = static_cast<uint8_t>((value >> (8 * index)) & 0xffU);
            cassi_target target;
            target.is_byte = true;
            target.byte = byte;
            timed_observe(text_query(index, prefix), target);
            prefix[index] = byte;
        }
        idle_field_hash_valid = false;
    }

    llama_token consult_teacher() {
        check_cancelled();
        elapsed_accumulator teacher_timer(stats.teacher_ms);
        stats.full_teacher_queries++;
        if (!teacher) {
            llama_context * raw = llama_init_from_model_exact(model, native_params);
            if (raw == nullptr) {
                stats.teacher_failures++;
                fail("apprentice_teacher_initialization_failed");
            }
            teacher.reset(raw);
            try {
                teacher->enable_cassi_capture();
            } catch (...) {
                teacher.reset();
                stats.teacher_failures++;
                fail("apprentice_teacher_initialization_failed");
            }
            teacher_prefix = 0;
            stats.native_context_creations++;
        }
        if (token_log.empty() || token_log.size() > native_params.n_ctx || teacher_prefix > token_log.size()) {
            stats.teacher_failures++;
            fail("apprentice_context_exhausted");
        }
        const bool reconstructing = teacher_prefix == 0;
        while (teacher_prefix < token_log.size()) {
            check_cancelled();
            llama_token token = token_log[teacher_prefix];
            llama_pos position = static_cast<llama_pos>(teacher_prefix);
            int32_t n_seq_id = 1;
            llama_seq_id seq = 0;
            llama_seq_id * seq_ptr = &seq;
            int8_t logits = teacher_prefix + 1 == token_log.size() ? 1 : 0;
            llama_batch batch = {};
            batch.n_tokens = 1;
            batch.token = &token;
            batch.pos = &position;
            batch.n_seq_id = &n_seq_id;
            batch.seq_id = &seq_ptr;
            batch.logits = &logits;
            const auto replay_started = std::chrono::steady_clock::now();
            const int32_t status = llama_decode(teacher.get(), batch);
            stats.replay_ms += elapsed_ms(replay_started);
            if (status != 0) {
                stats.teacher_failures++;
                teacher.reset();
                teacher_prefix = 0;
                stats.native_cache_bytes_remaining = 0;
                fail("apprentice_teacher_decode_failed");
            }
            if (teacher_prefix < prompt_token_count) {
                stats.native_prefill_tokens++;
            } else if (reconstructing) {
                stats.native_replay_tokens++;
            } else {
                stats.native_decode_tokens++;
            }
            stats.native_ggml_nodes_executed += static_cast<uint64_t>(teacher->cassi_last_graph_nodes());
            stats.logical_weight_bytes += teacher->cassi_last_graph_weight_bytes();
            service_stats[service_page(LLAMA_CASSI_EMBED, -1)].computed++;
            stats.native_output_rows_computed++;
            for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
                service_stats[service_page(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer))].computed++;
                service_stats[service_page(LLAMA_CASSI_FFN, static_cast<int32_t>(layer))].computed++;
                stats.native_output_rows_computed += 2;
            }
            if (logits != 0) {
                service_stats[service_page(LLAMA_CASSI_HEAD, -1)].computed++;
                stats.native_output_rows_computed += metadata.vocabulary_size;
            }
            try {
                teach_teacher_capture(teacher_prefix, token);
            } catch (const std::runtime_error & exception) {
                if (std::strcmp(exception.what(), "apprentice_teacher_capture_failed") == 0) {
                    stats.teacher_failures++;
                }
                teacher.reset();
                teacher_prefix = 0;
                stats.native_cache_bytes_remaining = 0;
                throw;
            }
            teacher_prefix++;
        }
        float * logits = llama_get_logits_ith(teacher.get(), -1);
        if (logits == nullptr) {
            stats.teacher_failures++;
            fail("apprentice_teacher_logits_unavailable");
        }
        stats.native_logits_reads++;
        llama_token selected = 0;
        float best = -std::numeric_limits<float>::infinity();
        for (uint32_t token = 0; token < metadata.vocabulary_size; ++token) {
            const float value = logits[token];
            if (!std::isfinite(value)) {
                stats.teacher_failures++;
                fail("apprentice_teacher_nonfinite");
            }
            if (value > best) {
                best = value;
                selected = static_cast<llama_token>(token);
            }
        }
        stage_pending_head(teacher_capture.head_input);
        refresh_cache_gauges();
        return selected;
    }

    void refresh_cache_gauges() {
        uint64_t current = 0;
        const auto add_context = [&](const std::unique_ptr<llama_context, llama_context_deleter> & context) {
            if (!context) {
                return;
            }
            for (const auto & item : context->memory_breakdown()) {
                const size_t bytes = item.second.context;
                if (bytes > std::numeric_limits<uint64_t>::max() - current) {
                    current = std::numeric_limits<uint64_t>::max();
                    return;
                }
                current += bytes;
            }
        };
        add_context(teacher);
        add_context(service);
        stats.native_cache_bytes_remaining = current;
        stats.native_cache_bytes_peak = std::max(stats.native_cache_bytes_peak, current);
    }

    int32_t begin(const llama_token * prompt, size_t n_prompt, int32_t n_predict) {
        if (state != session_state::idle) {
            fail("apprentice_invalid_transition");
        }
        if (prompt == nullptr || n_prompt == 0 || n_prompt > native_params.n_ctx || n_predict < 0) {
            fail("apprentice_request_invalid");
        }
        if (public_params.teacher_policy == LLAMA_CASSI_NEVER && !state_loaded) {
            fail("apprentice_checkpoint_missing");
        }
        for (size_t index = 0; index < n_prompt; ++index) {
            if (prompt[index] < 0 || static_cast<uint32_t>(prompt[index]) >= metadata.vocabulary_size) {
                fail("apprentice_token_invalid");
            }
        }

        cancellation_requested.store(false, std::memory_order_release);
        error.clear();
        teacher.reset();
        teacher_prefix = 0;
        service.reset();
        service_prefix = 0;
        service_token_active = false;
        service_epoch = 0;
        service_abandoned = false;
        prompt_token_count = n_prompt;
        for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
            attention_owned[layer] = public_params.teacher_policy == LLAMA_CASSI_NEVER ||
                field->page_mature(service_page(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer))) ? 1 : 0;
        }
        pending = {};
        clear_accepted_transaction();
        clear_pending_admissions();
        token_log.assign(prompt, prompt + n_prompt);
        prediction_limit = n_predict;
        stats = {};
        stats.native_nodes_skipped_known = true;
        stats.prompt_tokens = n_prompt;
        stats.field_bytes = field->field_bytes();
        stats.loaded_model_tensor_bytes = loaded_tensor_bytes(*model);
        for (auto & value : service_stats) {
            value.computed = 0;
            value.skipped = 0;
            value.logical_weight_bytes = 0;
        }
        request_started = std::chrono::steady_clock::now();
        field->reset_context();
        timed_sense_marker(USER_SYMBOL);
        for (llama_token token : token_log) {
            const std::string piece = token_piece(vocab(), token);
            const auto started = std::chrono::steady_clock::now();
            field->sense_token(token, piece, false);
            stats.field_ms += elapsed_ms(started);
            stats.field_steps += static_cast<uint64_t>(piece.size()) * (1 + metadata.layers);
        }
        timed_sense_marker(END_SYMBOL);
        timed_sense_marker(ASSISTANT_SYMBOL);
        idle_field_hash_valid = false;
        state = n_predict == 0 ? session_state::done : session_state::ready;
        return 0;
    }

    llama_cassi_status next(llama_cassi_token * result) {
        if (result == nullptr) {
            fail("apprentice_result_required");
        }
        *result = {};
        if (state == session_state::pending || state == session_state::idle) {
            fail("apprentice_invalid_transition");
        }
        if (state == session_state::done) {
            return LLAMA_CASSI_DONE;
        }
        if (state == session_state::cancelled) {
            return LLAMA_CASSI_CANCELLED;
        }
        if (state == session_state::error) {
            return LLAMA_CASSI_ERROR;
        }
        clear_accepted_transaction();
        clear_pending_admissions();
        if (cancellation_requested.load(std::memory_order_acquire)) {
            state = session_state::cancelled;
            return LLAMA_CASSI_CANCELLED;
        }
        if (stats.committed_tokens >= static_cast<uint64_t>(prediction_limit)) {
            state = session_state::done;
            return LLAMA_CASSI_DONE;
        }

        std::array<uint8_t, TOKEN_BYTES> decoded = {};
        bool field_available = public_params.teacher_policy != LLAMA_CASSI_ALWAYS &&
            public_params.route_policy != LLAMA_CASSI_PIPELINE;
        bool interpolated = false;
        if (field_available) {
            for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
                check_cancelled();
                const cassi_probe proposal = timed_probe(text_query(index, decoded));
                if (!proposal.eligible || !proposal.is_byte) {
                    field_available = false;
                    break;
                }
                decoded[index] = proposal.byte;
                interpolated = interpolated || proposal.status == CASSI_PROBE_FIELD_INTERPOLATED;
            }
        }
        uint32_t decoded_token = 0;
        for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
            decoded_token |= static_cast<uint32_t>(decoded[index]) << (8 * index);
        }
        if (field_available && decoded_token >= metadata.vocabulary_size) {
            field_available = false;
            if (public_params.teacher_policy == LLAMA_CASSI_NEVER) {
                fail("apprentice_token_invalid");
            }
        }

        const uint64_t event_index = stats.committed_tokens + 1;
        const bool audit = field_available && public_params.teacher_policy == LLAMA_CASSI_ADAPTIVE &&
            public_params.audit_interval != 0 && event_index % public_params.audit_interval == 0;
        bool pending_ready = false;
        if (field_available && !audit) {
            pending.result.token = static_cast<llama_token>(decoded_token);
            pending.result.decision_source = 0;
            pending.result.native_dependency = 0;
            pending.result.readout_kind = interpolated ? 1 : 0;
            pending.teach_text = false;
            pending.audit = false;
            pending_ready = true;
        }

        const bool non_text_mature = std::any_of(
            field->pages().begin() + 1,
            field->pages().end(),
            [&](const cassi_field_page & page) {
                return field->page_mature(static_cast<uint32_t>(&page - field->pages().data()));
            });
        if (!pending_ready && !field_available && public_params.teacher_policy != LLAMA_CASSI_ALWAYS &&
                !service_abandoned &&
                (public_params.route_policy == LLAMA_CASSI_PIPELINE || non_text_mature)) {
            try {
                const uint64_t calls_before = stats.native_service_calls;
                pending.result = run_pipeline();
                if (pending.result.native_dependency == 0 && stats.native_service_calls != calls_before) {
                    pending.result.native_dependency = 1;
                }
                pending.teach_text = false;
                pending.audit = false;
                pending_ready = true;
            } catch (const std::runtime_error & exception) {
                if (std::strcmp(exception.what(), "apprentice_native_service_prefix_unavailable") != 0) {
                    throw;
                }
                service_abandoned = true;
                clear_pending_admissions();
                if (public_params.teacher_policy == LLAMA_CASSI_NEVER) {
                    throw;
                }
            }
        }

        if (!pending_ready) {
            if (public_params.teacher_policy == LLAMA_CASSI_NEVER) {
                fail("apprentice_teacher_required");
            }
            const llama_token teacher_token = consult_teacher();
            if (audit) {
                stats.teacher_audits++;
            }
            const bool mismatch = field_available && static_cast<uint32_t>(teacher_token) != decoded_token;
            if (mismatch) {
                stats.audit_mismatches++;
            }
            const uint32_t teacher_value = static_cast<uint32_t>(teacher_token);
            for (uint32_t index = 0; index < TOKEN_BYTES; ++index) {
                check_cancelled();
                const uint8_t byte = static_cast<uint8_t>((teacher_value >> (8 * index)) & 0xffU);
                if (timed_guide_byte(byte) != byte) {
                    fail("apprentice_assimilation_failed");
                }
            }
            pending.result.token = teacher_token;
            pending.result.decision_source = field_available && !mismatch ? 0 : 1;
            pending.result.native_dependency = 2;
            pending.result.readout_kind = field_available && !mismatch ? (interpolated ? 1 : 0) : 2;
            pending.teach_text = true;
            pending.audit = audit;
        }
        *result = pending.result;
        state = session_state::pending;
        return LLAMA_CASSI_TOKEN;
    }

    int32_t accept(llama_token token) {
        if (state != session_state::pending || token != pending.result.token) {
            fail("apprentice_invalid_transition");
        }
        check_cancelled();
        const uint64_t observations_before = stats.field_observations;
        const uint64_t evictions_before = stats.engram_evictions;
        const bool hash_valid_before = idle_field_hash_valid;
        const bool has_learning =
            !pending_vector_admissions.empty() || pending.teach_head || pending.teach_text;
        const uint64_t pending_observation_count =
            static_cast<uint64_t>(pending_vector_admissions.size()) +
            (pending.teach_head ? TOKEN_BYTES : 0) +
            (pending.teach_text ? TOKEN_BYTES : 0);
        if (pending_observation_count >
                std::numeric_limits<uint64_t>::max() - 1 - field->field_revision()) {
            fail("apprentice_field_revision_overflow");
        }
        pending.rollback_context_snapshot.resize(field->context_snapshot_size());
        field->context_snapshot_get(
            pending.rollback_context_snapshot.data(),
            pending.rollback_context_snapshot.size());
        if (has_learning) {
            stage_pending_field_rollback();
        } else {
            pending.rollback_hash_valid = hash_valid_before;
            pending.rollback_revision = field->field_revision();
            pending.rollback_observations = observations_before;
            pending.rollback_field_evictions = field->engram_evictions();
            pending.rollback_stats_evictions = evictions_before;
            pending.rollback_hash = idle_field_hash;
        }
        const bool rollback_field = pending.rollback_field;
        try {
            replay_vector_observations();
            if (pending.teach_head) {
                teach_pending_head(token);
            }
            if (pending.teach_text) {
                teach_pending_text(token);
            }
            check_cancelled();
            timed_sense_token(token);
            token_log.push_back(token);
        } catch (...) {
            if (rollback_field) {
                restore_pending_field_rollback();
            } else {
                stats.field_observations = observations_before;
                stats.engram_evictions = evictions_before;
                idle_field_hash_valid = hash_valid_before;
                field->context_snapshot_set(
                    pending.rollback_context_snapshot.data(),
                    pending.rollback_context_snapshot.size());
            }
            clear_pending_admissions();
            throw;
        }
        stats.committed_tokens++;
        if (pending.result.readout_kind == 0) {
            stats.field_exact_tokens++;
        } else if (pending.result.readout_kind == 1) {
            stats.field_interpolated_tokens++;
        } else {
            stats.teacher_guided_tokens++;
        }
        accepted = std::move(pending);
        pending = {};
        clear_pending_admissions();
        idle_field_hash_valid = false;
        state = stats.committed_tokens >= static_cast<uint64_t>(prediction_limit) ||
            llama_vocab_is_eog(vocab(), token) ? session_state::done : session_state::ready;
        return 0;
    }

    int32_t finish(bool cancelled) {
        if (state == session_state::idle) {
            clear_accepted_transaction();
            return 0;
        }
        if (cancelled) {
            cancellation_requested.store(true, std::memory_order_release);
        }
        restore_pending_field_rollback();
        pending = {};
        clear_pending_admissions();
        teacher.reset();
        teacher_prefix = 0;
        service.reset();
        service_prefix = 0;
        service_token_active = false;
        token_log.clear();
        field->reset_context();
        stats.native_cache_bytes_remaining = 0;
        clear_accepted_transaction();
        stats.engram_evictions = field->engram_evictions();
        stats.wall_ms = elapsed_ms(request_started);
        idle_field_hash_valid = false;
        state = session_state::idle;
        return 0;
    }

    bool idle() const {
        return state == session_state::idle;
    }

    bool checkpointable() const {
        return state == session_state::idle || state == session_state::ready || state == session_state::done;
    }

    size_t state_size() const {
        const size_t pages = field->pages().size();
        size_t size = 120;
        size = checked_add(size, pages * 24);
        size = checked_add(size, field->state_size());
        size = checked_add(size, 64);
        return size;
    }

    std::vector<uint8_t> make_state_image() {
        if (!checkpointable()) {
            fail("apprentice_state_busy");
        }
        const bool normalize_context = !idle();
        if (normalize_context) {
            field->context_snapshot_get(context_snapshot.data(), context_snapshot.size());
            field->reset_context();
        }
        std::vector<float> payload(field->state_size() / sizeof(float));
        try {
            field->state_get(payload.data(), field->state_size());
        } catch (...) {
            if (normalize_context) {
                field->context_snapshot_set(context_snapshot.data(), context_snapshot.size());
            }
            throw;
        }
        if (normalize_context) {
            field->context_snapshot_set(context_snapshot.data(), context_snapshot.size());
        }
        std::vector<uint8_t> bytes;
        bytes.reserve(state_size());
        bytes.insert(bytes.end(), CHECKPOINT_MAGIC, CHECKPOINT_MAGIC + sizeof(CHECKPOINT_MAGIC));
        append_u32(bytes, CHECKPOINT_VERSION);
        append_u32(bytes, CHECKPOINT_SCALES);
        append_u64(bytes, field->modes());
        append_u32(bytes, metadata.layers);
        append_u32(bytes, metadata.embedding_width);
        append_u32(bytes, metadata.vocabulary_size);
        append_u32(bytes, static_cast<uint32_t>(field->pages().size()));
        append_u64(bytes, field->state_size());
        append_u64(bytes, field->field_revision());
        bytes.insert(bytes.end(), model_hash.begin(), model_hash.end());
        bytes.insert(bytes.end(), profile_hash.begin(), profile_hash.end());
        for (const cassi_field_page & page : field->pages()) {
            append_u32(bytes, static_cast<uint32_t>(page.kind));
            append_i32(bytes, page.layer);
            append_u32(bytes, page.width);
            append_u32(bytes, page.entries);
            append_u64(bytes, page.mode_offset);
        }
        const size_t payload_offset = bytes.size();
        for (float value : payload) {
            append_f32(bytes, value);
        }
        std::array<uint8_t, 32> payload_hash = {};
        hash_bytes(bytes.data() + payload_offset, field->state_size(), payload_hash.data());
        bytes.insert(bytes.end(), payload_hash.begin(), payload_hash.end());
        std::array<uint8_t, 32> image_hash = {};
        hash_bytes(bytes.data(), bytes.size(), image_hash.data());
        bytes.insert(bytes.end(), image_hash.begin(), image_hash.end());
        if (bytes.size() != state_size()) {
            fail("apprentice_checkpoint_invalid");
        }
        if (normalize_context) {
            idle_field_hash_valid = false;
        } else {
            idle_field_hash = payload_hash;
            idle_field_hash_valid = true;
        }
        return bytes;
    }

    void set_state_image(const uint8_t * source, size_t size) {
        if (!idle()) {
            fail("apprentice_state_busy");
        }
        if (source == nullptr || size != state_size()) {
            fail("apprentice_checkpoint_invalid");
        }
        byte_reader reader{ source, size };
        if (std::memcmp(reader.take(sizeof(CHECKPOINT_MAGIC)), CHECKPOINT_MAGIC, sizeof(CHECKPOINT_MAGIC)) != 0 ||
            reader.u32() != CHECKPOINT_VERSION || reader.u32() != CHECKPOINT_SCALES ||
            reader.u64() != field->modes() || reader.u32() != metadata.layers ||
            reader.u32() != metadata.embedding_width || reader.u32() != metadata.vocabulary_size ||
            reader.u32() != field->pages().size() || reader.u64() != field->state_size()) {
            fail("apprentice_checkpoint_invalid");
        }
        const uint64_t revision = reader.u64();
        if (revision == std::numeric_limits<uint64_t>::max()) {
            fail("apprentice_checkpoint_invalid");
        }
        if (std::memcmp(reader.take(32), model_hash.data(), model_hash.size()) != 0 ||
            std::memcmp(reader.take(32), profile_hash.data(), profile_hash.size()) != 0) {
            fail("apprentice_checkpoint_invalid");
        }
        for (const cassi_field_page & page : field->pages()) {
            if (reader.u32() != static_cast<uint32_t>(page.kind) || reader.i32() != page.layer ||
                reader.u32() != page.width || reader.u32() != page.entries || reader.u64() != page.mode_offset) {
                fail("apprentice_checkpoint_invalid");
            }
        }
        const size_t payload_offset = reader.offset;
        std::vector<float> payload(field->state_size() / sizeof(float));
        for (float & value : payload) {
            value = reader.f32();
        }
        const uint8_t * expected_payload_hash = reader.take(32);
        const uint8_t * expected_image_hash = reader.take(32);
        if (reader.offset != size) {
            fail("apprentice_checkpoint_invalid");
        }
        std::array<uint8_t, 32> actual_payload_hash = {};
        hash_bytes(source + payload_offset, field->state_size(), actual_payload_hash.data());
        if (std::memcmp(expected_payload_hash, actual_payload_hash.data(), actual_payload_hash.size()) != 0) {
            fail("apprentice_checkpoint_invalid");
        }
        std::array<uint8_t, 32> actual_image_hash = {};
        hash_bytes(source, size - 32, actual_image_hash.data());
        if (std::memcmp(expected_image_hash, actual_image_hash.data(), actual_image_hash.size()) != 0) {
            fail("apprentice_checkpoint_invalid");
        }
        const uint64_t modes = field->modes();
        for (const cassi_field_page & page : field->pages()) {
            for (uint32_t scale = 0; scale < CHECKPOINT_SCALES; ++scale) {
                for (uint32_t component = 0; component < CASSI_APPRENTICE_COMPONENT_COUNT; ++component) {
                    const uint64_t plane = (static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * modes;
                    for (uint32_t mode = 0; mode < page.width; ++mode) {
                        if (payload[plane + page.mode_offset + mode] != 0.0f) {
                            fail("apprentice_checkpoint_invalid");
                        }
                    }
                }
            }
        }
        field->state_set(payload.data(), field->state_size(), revision);
        idle_field_hash = actual_payload_hash;
        idle_field_hash_valid = true;
        state_loaded = true;
    }

    void fill_info(llama_cassi_info & info) {
        if (!checkpointable()) {
            fail("apprentice_state_busy");
        }
        if (!idle_field_hash_valid) {
            field->field_sha256(idle_field_hash.data());
            idle_field_hash_valid = true;
        }
        info = {};
        info.scales = CHECKPOINT_SCALES;
        info.layers = metadata.layers;
        info.embedding_width = metadata.embedding_width;
        info.vocabulary_size = metadata.vocabulary_size;
        info.context_limit = native_params.n_ctx;
        info.training_context_limit = metadata.context_length;
        info.modes = field->modes();
        info.field_bytes = field->field_bytes();
        info.field_revision = field->field_revision();
        std::memcpy(info.model_sha256, model_hash.data(), model_hash.size());
        std::memcpy(info.profile_sha256, profile_hash.data(), profile_hash.size());
        std::memcpy(info.field_sha256, idle_field_hash.data(), idle_field_hash.size());
    }

    llama_cassi_stats stats_copy() const {
        llama_cassi_stats result = stats;
        result.field_bytes = field->field_bytes();
        result.engram_evictions = field->engram_evictions();
        if (state != session_state::idle && request_started != std::chrono::steady_clock::time_point{}) {
            result.wall_ms = elapsed_ms(request_started);
        }
        return result;
    }
};

extern "C" {

llama_cassi_params llama_cassi_default_params(void) {
    llama_cassi_params result = {};
    result.memory_bytes = UINT64_C(1) << 30;
    result.audit_interval = 8;
    result.teacher_policy = LLAMA_CASSI_ADAPTIVE;
    result.route_policy = LLAMA_CASSI_AUTO;
    result.field_device = "Vulkan0";
    result.model_path = nullptr;
    return result;
}

llama_cassi_context * llama_cassi_init(
        llama_model * model,
        llama_context_params native_params,
        llama_cassi_params params) {
    try {
        init_error.clear();
        return new llama_cassi_context(model, native_params, params);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return nullptr;
    } catch (...) {
        init_error = "apprentice_unknown_error";
        return nullptr;
    }
}

void llama_cassi_free(llama_cassi_context * ctx) {
    delete ctx;
}

int32_t llama_cassi_begin(llama_cassi_context * ctx, const llama_token * prompt, size_t n_prompt, int32_t n_predict) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->begin(prompt, n_prompt, n_predict);
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

llama_cassi_status llama_cassi_next(llama_cassi_context * ctx, llama_cassi_token * result) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        if (result != nullptr) {
            *result = {};
        }
        return LLAMA_CASSI_ERROR;
    }
    try {
        return ctx->next(result);
    } catch (const std::exception & exception) {
        if (std::strcmp(exception.what(), "apprentice_cancelled") == 0) {
            ctx->state = session_state::cancelled;
            ctx->error.clear();
            return LLAMA_CASSI_CANCELLED;
        }
        if (std::strcmp(exception.what(), "apprentice_invalid_transition") == 0) {
            ctx->error = exception.what();
            return LLAMA_CASSI_ERROR;
        }
        ctx->set_error(exception.what());
        return LLAMA_CASSI_ERROR;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return LLAMA_CASSI_ERROR;
    }
}

int32_t llama_cassi_accept(llama_cassi_context * ctx, llama_token token) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->accept(token);
    } catch (const std::exception & exception) {
        if (std::strcmp(exception.what(), "apprentice_cancelled") == 0) {
            ctx->state = session_state::cancelled;
            ctx->error.clear();
        } else if (std::strcmp(exception.what(), "apprentice_invalid_transition") != 0) {
            ctx->set_error(exception.what());
        } else {
            ctx->error = exception.what();
        }
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

int32_t llama_cassi_rollback_accepted(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        ctx->rollback_accepted_transaction();
        return 0;
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

int32_t llama_cassi_finish(llama_cassi_context * ctx, bool cancelled) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->finish(cancelled);
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

void llama_cassi_cancel(llama_cassi_context * ctx) {
    if (ctx != nullptr) {
        ctx->cancellation_requested.store(true, std::memory_order_release);
    }
}

const char * llama_cassi_last_error(const llama_cassi_context * ctx) {
    return ctx == nullptr ? init_error.c_str() : ctx->error.c_str();
}

void llama_cassi_get_stats(const llama_cassi_context * ctx, llama_cassi_stats * out) {
    if (out == nullptr) {
        if (ctx == nullptr) {
            init_error = "apprentice_context_required";
        } else {
            const_cast<llama_cassi_context *>(ctx)->error = "apprentice_result_required";
        }
        return;
    }
    *out = {};
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return;
    }
    *out = ctx->stats_copy();
}

int32_t llama_cassi_get_info(llama_cassi_context * ctx, llama_cassi_info * out) {
    if (out != nullptr) {
        *out = {};
    }
    if (ctx == nullptr || out == nullptr) {
        if (ctx == nullptr) {
            init_error = "apprentice_context_required";
        } else {
            ctx->error = "apprentice_result_required";
        }
        return -1;
    }
    try {
        ctx->fill_info(*out);
        return 0;
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return -1;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return -1;
    }
}

size_t llama_cassi_native_backend_count(const llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    return ctx->native_backends.size();
}

size_t llama_cassi_native_backend_name(
        const llama_cassi_context * ctx,
        size_t index,
        char * dst,
        size_t capacity) {
    if (ctx == nullptr || index >= ctx->native_backends.size()) {
        if (ctx == nullptr) {
            init_error = "apprentice_context_required";
        } else {
            const_cast<llama_cassi_context *>(ctx)->error = "apprentice_backend_index_invalid";
        }
        return 0;
    }
    const std::string & name = ctx->native_backends[index];
    if (dst != nullptr && capacity > name.size()) {
        std::memcpy(dst, name.data(), name.size());
        dst[name.size()] = '\0';
    }
    return name.size();
}

size_t llama_cassi_attention_mask_get(
        const llama_cassi_context * ctx,
        uint8_t * dst,
        size_t capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    const size_t required = ctx->attention_owned.size();
    if (dst != nullptr) {
        if (capacity < required) {
            const_cast<llama_cassi_context *>(ctx)->error = "apprentice_buffer_too_small";
            return 0;
        }
        std::memcpy(dst, ctx->attention_owned.data(), required);
    }
    return required;
}

size_t llama_cassi_service_stats_count(const llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    return ctx->service_stats.size();
}

size_t llama_cassi_service_stats_get(
        const llama_cassi_context * ctx,
        llama_cassi_service_stats * dst,
        size_t capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    const size_t count = ctx->service_stats.size();
    if (dst == nullptr || capacity < count) {
        const_cast<llama_cassi_context *>(ctx)->error =
            dst == nullptr ? "apprentice_result_required" : "apprentice_buffer_too_small";
        return 0;
    }
    std::copy(ctx->service_stats.begin(), ctx->service_stats.end(), dst);
    return count;
}

size_t llama_cassi_state_size(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    try {
        if (!ctx->checkpointable()) {
            fail("apprentice_state_busy");
        }
        return ctx->state_size();
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return 0;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return 0;
    }
}

size_t llama_cassi_state_get(llama_cassi_context * ctx, uint8_t * dst, size_t size) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    try {
        const size_t required = ctx->state_size();
        if (!ctx->checkpointable()) {
            fail("apprentice_state_busy");
        }
        if (dst == nullptr || size < required) {
            ctx->error = dst == nullptr ? "apprentice_result_required" : "apprentice_buffer_too_small";
            return 0;
        }
        std::vector<uint8_t> image = ctx->make_state_image();
        std::memcpy(dst, image.data(), image.size());
        return image.size();
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return 0;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return 0;
    }
}

int32_t llama_cassi_state_set(llama_cassi_context * ctx, const uint8_t * src, size_t size) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        ctx->set_state_image(src, size);
        return 0;
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return -1;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return -1;
    }
}

} // extern "C"
