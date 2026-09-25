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
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <system_error>
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
void hash_u64(sha256_t & state, uint64_t value) {
    uint8_t bytes[sizeof(value)];
    for (size_t i = 0; i < sizeof(value); ++i) {
        bytes[i] = static_cast<uint8_t>(value >> (i * 8));
    }
    sha256_update(&state, bytes, sizeof(bytes));
}
void hash_f32(sha256_t & state, float value) {
    uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    hash_u64(state, bits);
}

void hash_f64(sha256_t & state, double value) {
    uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    hash_u64(state, bits);
}

std::array<uint8_t, 32> hash_native_sampler_tuple(const llama_cassi_sampler_params & sampler) {
    sha256_t state;
    sha256_init(&state);
    static constexpr char domain[] = "cassi.sampler-tuple.v1";
    sha256_update(&state, reinterpret_cast<const unsigned char *>(domain), sizeof(domain) - 1);
    hash_u64(state, static_cast<uint64_t>(sampler.mode));
    hash_f32(state, sampler.temperature);
    hash_u64(state, sampler.top_k);
    hash_f64(state, sampler.draw);
    std::array<uint8_t, 32> digest = {};
    sha256_final(&state, digest.data());
    return digest;
}

bool sampler_tuple_valid(const llama_cassi_sampler_params & sampler) {
    if (sampler.mode == LLAMA_CASSI_SAMPLER_GREEDY) {
        return sampler.temperature == 1.0f && sampler.top_k == 0 && sampler.draw == 0.0;
    }
    return sampler.mode == LLAMA_CASSI_SAMPLER_CATEGORICAL &&
        std::isfinite(sampler.temperature) && sampler.temperature > 0.0f &&
        std::isfinite(sampler.draw) && sampler.draw >= 0.0 && sampler.draw < 1.0;
}

void validate_exact_logits(const float * logits, size_t count) {
    if (logits == nullptr || count == 0 || count > UINT32_MAX) {
        fail("apprentice_native_head_shape_invalid");
    }
    for (size_t index = 0; index < count; ++index) {
        if (!std::isfinite(logits[index])) {
            fail("apprentice_native_service_nonfinite");
        }
    }
}

void exact_categorical_distribution(
        const float * logits,
        size_t count,
        const llama_cassi_sampler_params & sampler,
        std::vector<uint32_t> & candidates,
        std::vector<double> & weights,
        double & total) {
    validate_exact_logits(logits, count);
    if (!sampler_tuple_valid(sampler) ||
            sampler.mode != LLAMA_CASSI_SAMPLER_CATEGORICAL ||
            sampler.top_k > count) {
        fail("apprentice_sampler_invalid");
    }
    candidates.resize(count);
    std::iota(candidates.begin(), candidates.end(), 0U);
    const auto ranked_before = [&](uint32_t left, uint32_t right) {
        if (logits[left] != logits[right]) {
            return logits[left] > logits[right];
        }
        return left < right;
    };
    const size_t keep = sampler.top_k == 0
        ? candidates.size()
        : std::min<size_t>(sampler.top_k, candidates.size());
    if (keep < candidates.size()) {
        std::nth_element(
            candidates.begin(),
            candidates.begin() + static_cast<std::ptrdiff_t>(keep),
            candidates.end(),
            ranked_before);
        candidates.resize(keep);
    }
    std::sort(candidates.begin(), candidates.end(), ranked_before);
    const double inverse_temperature = 1.0 / static_cast<double>(sampler.temperature);
    const double maximum =
        static_cast<double>(logits[candidates.front()]) * inverse_temperature;
    weights.resize(candidates.size());
    total = 0.0;
    for (size_t index = 0; index < candidates.size(); ++index) {
        const double weight = std::exp(
            static_cast<double>(logits[candidates[index]]) * inverse_temperature - maximum);
        weights[index] = weight;
        total += weight;
    }
    if (!std::isfinite(total) || total <= 0.0) {
        fail("apprentice_native_sampler_normalization_failed");
    }
}

llama_cassi_q_delta_result sample_exact_q_delta(
        const float * logits,
        size_t count,
        llama_token draft_token,
        const llama_cassi_sampler_params & sampler) {
    if (draft_token < 0 || static_cast<size_t>(draft_token) >= count ||
            !sampler_tuple_valid(sampler)) {
        fail("apprentice_sampler_invalid");
    }
    llama_cassi_q_delta_result result = {};
    if (sampler.mode == LLAMA_CASSI_SAMPLER_GREEDY) {
        validate_exact_logits(logits, count);
        const float * best = std::max_element(logits, logits + count);
        result.token = static_cast<llama_token>(best - logits);
        result.accepted = result.token == draft_token;
        result.target_probability = result.accepted ? 1.0 : 0.0;
        return result;
    }

    std::vector<uint32_t> candidates;
    std::vector<double> weights;
    double total = 0.0;
    exact_categorical_distribution(logits, count, sampler, candidates, weights, total);
    double draft_weight = 0.0;
    for (size_t index = 0; index < candidates.size(); ++index) {
        if (candidates[index] == static_cast<uint32_t>(draft_token)) {
            draft_weight = weights[index];
            break;
        }
    }
    const double target_probability = draft_weight / total;
    result.target_probability = target_probability;
    result.draws_consumed = 1;
    if (sampler.draw < target_probability) {
        result.accepted = true;
        result.token = draft_token;
        return result;
    }

    double residual_total = 0.0;
    for (size_t index = 0; index < candidates.size(); ++index) {
        if (candidates[index] != static_cast<uint32_t>(draft_token)) {
            residual_total += weights[index];
        }
    }
    if (residual_total <= 0.0 || !std::isfinite(residual_total)) {
        fail("apprentice_native_sampler_residual_empty");
    }
    const double residual_draw = std::min(
        std::nextafter(1.0, 0.0),
        (sampler.draw - target_probability) / (1.0 - target_probability));
    const double threshold = residual_draw * residual_total;
    double cumulative = 0.0;
    llama_token last = -1;
    for (size_t index = 0; index < candidates.size(); ++index) {
        if (candidates[index] == static_cast<uint32_t>(draft_token)) {
            continue;
        }
        last = static_cast<llama_token>(candidates[index]);
        cumulative += weights[index];
        if (threshold < cumulative) {
            result.token = last;
            return result;
        }
    }
    if (last < 0) {
        fail("apprentice_native_sampler_residual_empty");
    }
    result.token = last;
    return result;
}

bool append_sampler_bytes(
        char *& cursor, const char * end, const char * value, size_t size) {
    if (size > static_cast<size_t>(end - cursor)) {
        return false;
    }
    std::memcpy(cursor, value, size);
    cursor += size;
    return true;
}

bool append_sampler_char(char *& cursor, const char * end, char value) {
    return append_sampler_bytes(cursor, end, &value, 1);
}

bool append_python_json_float(char *& cursor, const char * end, double value) {
    if (!std::isfinite(value)) {
        return false;
    }
    char scientific[64];
    const auto converted = std::to_chars(
        scientific, scientific + sizeof(scientific), value, std::chars_format::scientific);
    if (converted.ec != std::errc{}) {
        return false;
    }

    const char * p = scientific;
    const char * const repr_end = converted.ptr;
    const bool negative = p != repr_end && *p == '-';
    if (negative) {
        ++p;
    }
    char digits[32];
    size_t digit_count = 0;
    while (p != repr_end && *p != 'e' && *p != 'E') {
        if (*p >= '0' && *p <= '9') {
            if (digit_count == sizeof(digits)) {
                return false;
            }
            digits[digit_count++] = *p;
        } else if (*p != '.') {
            return false;
        }
        ++p;
    }
    if (p == repr_end || digit_count == 0) {
        return false;
    }
    ++p;
    int exponent_sign = 1;
    if (p != repr_end && (*p == '+' || *p == '-')) {
        exponent_sign = *p == '-' ? -1 : 1;
        ++p;
    }
    int exponent_magnitude = 0;
    while (p != repr_end) {
        if (*p < '0' || *p > '9' || exponent_magnitude > 1000) {
            return false;
        }
        exponent_magnitude = exponent_magnitude * 10 + (*p - '0');
        ++p;
    }
    const int exponent = exponent_sign * exponent_magnitude;
    if (negative && !append_sampler_char(cursor, end, '-')) {
        return false;
    }

    if (exponent >= -4 && exponent < 16) {
        const int decimal_position = exponent + 1;
        if (decimal_position <= 0) {
            if (!append_sampler_bytes(cursor, end, "0.", 2)) {
                return false;
            }
            for (int zero = 0; zero < -decimal_position; ++zero) {
                if (!append_sampler_char(cursor, end, '0')) {
                    return false;
                }
            }
            return append_sampler_bytes(cursor, end, digits, digit_count);
        }
        if (static_cast<size_t>(decimal_position) >= digit_count) {
            if (!append_sampler_bytes(cursor, end, digits, digit_count)) {
                return false;
            }
            for (size_t zero = digit_count; zero < static_cast<size_t>(decimal_position); ++zero) {
                if (!append_sampler_char(cursor, end, '0')) {
                    return false;
                }
            }
            return append_sampler_bytes(cursor, end, ".0", 2);
        }
        return append_sampler_bytes(cursor, end, digits, static_cast<size_t>(decimal_position)) &&
            append_sampler_char(cursor, end, '.') &&
            append_sampler_bytes(
                cursor, end, digits + decimal_position, digit_count - decimal_position);
    }

    if (!append_sampler_char(cursor, end, digits[0])) {
        return false;
    }
    if (digit_count > 1 &&
            (!append_sampler_char(cursor, end, '.') ||
             !append_sampler_bytes(cursor, end, digits + 1, digit_count - 1))) {
        return false;
    }
    if (!append_sampler_char(cursor, end, 'e') ||
            !append_sampler_char(cursor, end, exponent < 0 ? '-' : '+')) {
        return false;
    }
    char exponent_digits[16];
    const unsigned magnitude = static_cast<unsigned>(
        exponent < 0 ? -exponent : exponent);
    const auto exponent_text = std::to_chars(
        exponent_digits, exponent_digits + sizeof(exponent_digits), magnitude);
    if (exponent_text.ec != std::errc{}) {
        return false;
    }
    const size_t exponent_size = static_cast<size_t>(exponent_text.ptr - exponent_digits);
    if (exponent_size < 2 && !append_sampler_char(cursor, end, '0')) {
        return false;
    }
    return append_sampler_bytes(cursor, end, exponent_digits, exponent_size);
}

bool canonical_sampler_sha256(
        const llama_cassi_sampler_params & sampler,
        std::array<uint8_t, 32> & digest) {
    if (!sampler_tuple_valid(sampler)) {
        return false;
    }
    char json[256];
    char * cursor = json;
    const char * const end = json + sizeof(json);
    const char * const mode = sampler.mode == LLAMA_CASSI_SAMPLER_GREEDY
        ? "greedy" : "categorical";
    const size_t mode_size = sampler.mode == LLAMA_CASSI_SAMPLER_GREEDY ? 6 : 11;
    char top_k[16];
    const auto top_k_text = std::to_chars(top_k, top_k + sizeof(top_k), sampler.top_k);
    if (top_k_text.ec != std::errc{} ||
            !append_sampler_bytes(cursor, end, "{\"draw\":", 8) ||
            !append_python_json_float(cursor, end, sampler.draw) ||
            !append_sampler_bytes(cursor, end, ",\"mode\":\"", 9) ||
            !append_sampler_bytes(cursor, end, mode, mode_size) ||
            !append_sampler_bytes(cursor, end, "\",\"temperature\":", 16) ||
            !append_python_json_float(cursor, end, static_cast<double>(sampler.temperature)) ||
            !append_sampler_bytes(cursor, end, ",\"top_k\":", 9) ||
            !append_sampler_bytes(
                cursor, end, top_k, static_cast<size_t>(top_k_text.ptr - top_k)) ||
            !append_sampler_char(cursor, end, '}')) {
        return false;
    }
    sha256_hash(
        digest.data(), reinterpret_cast<const uint8_t *>(json),
        static_cast<size_t>(cursor - json));
    return true;
}
std::array<uint8_t, 32> hash_graph_site_sampler_tuple(
        const llama_cassi_sampler_params & sampler) {
    std::array<uint8_t, 32> digest = {};
    if (!canonical_sampler_sha256(sampler, digest)) {
        fail("apprentice_sampler_invalid");
    }
    return digest;
}

void hash_text(sha256_t & state, const char * text, size_t size) {
    hash_u64(state, size);
    if (size != 0) {
        sha256_update(&state, reinterpret_cast<const unsigned char *>(text), size);
    }
}

size_t gguf_scalar_size(gguf_type type) {
    switch (type) {
        case GGUF_TYPE_UINT8:
        case GGUF_TYPE_INT8:
        case GGUF_TYPE_BOOL:
            return 1;
        case GGUF_TYPE_UINT16:
        case GGUF_TYPE_INT16:
            return 2;
        case GGUF_TYPE_UINT32:
        case GGUF_TYPE_INT32:
        case GGUF_TYPE_FLOAT32:
            return 4;
        case GGUF_TYPE_UINT64:
        case GGUF_TYPE_INT64:
        case GGUF_TYPE_FLOAT64:
            return 8;
        default:
            return 0;
    }
}

std::array<uint8_t, 32> hash_tokenizer_metadata(const gguf_context * context) {
    sha256_t state;
    sha256_init(&state);
    static constexpr char domain[] = "cassi.tokenizer-metadata.v1";
    sha256_update(&state, reinterpret_cast<const unsigned char *>(domain), sizeof(domain) - 1);
    const int64_t n_kv = gguf_get_n_kv(context);
    for (int64_t i = 0; i < n_kv; ++i) {
        const char * key = gguf_get_key(context, i);
        if (key == nullptr || std::strncmp(key, "tokenizer.", 10) != 0) {
            continue;
        }
        hash_text(state, key, std::strlen(key));
        const gguf_type type = gguf_get_kv_type(context, i);
        hash_u64(state, static_cast<uint64_t>(type));
        if (type == GGUF_TYPE_STRING) {
            const char * value = gguf_get_val_str(context, i);
            hash_text(state, value, std::strlen(value));
        } else if (type == GGUF_TYPE_ARRAY) {
            const gguf_type element_type = gguf_get_arr_type(context, i);
            const size_t count = gguf_get_arr_n(context, i);
            hash_u64(state, static_cast<uint64_t>(element_type));
            hash_u64(state, count);
            if (element_type == GGUF_TYPE_STRING) {
                for (size_t item = 0; item < count; ++item) {
                    const char * value = gguf_get_arr_str(context, i, item);
                    if (value == nullptr) {
                        fail("apprentice_model_metadata_invalid");
                    }
                    hash_text(state, value, std::strlen(value));
                }
            } else {
                const size_t element_size = gguf_scalar_size(element_type);
                const void * values = gguf_get_arr_data(context, i);
                if (element_size == 0 || (count != 0 && values == nullptr) ||
                    count > std::numeric_limits<size_t>::max() / element_size) {
                    fail("apprentice_model_metadata_invalid");
                }
                sha256_update(&state, static_cast<const unsigned char *>(values), count * element_size);
            }
        } else {
            const size_t size = gguf_scalar_size(type);
            const void * value = gguf_get_val_data(context, i);
            if (size == 0 || value == nullptr) {
                fail("apprentice_model_metadata_invalid");
            }
            sha256_update(&state, static_cast<const unsigned char *>(value), size);
        }
    }
    std::array<uint8_t, 32> digest = {};
    sha256_final(&state, digest.data());
    return digest;
}

std::string digest_hex(const uint8_t digest[32]) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string result(64, '0');
    for (size_t i = 0; i < 32; ++i) {
        result[i * 2] = digits[digest[i] >> 4];
        result[i * 2 + 1] = digits[digest[i] & 0x0f];
    }
    return result;
}
void digest_hex_into(char out[65], const uint8_t digest[32]) {
    static constexpr char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < 32; ++i) {
        out[i * 2] = digits[digest[i] >> 4];
        out[i * 2 + 1] = digits[digest[i] & 0x0f];
    }
    out[64] = '\0';
}

template <size_t N>
void copy_c_string(char (&out)[N], const std::string & value) {
    const size_t size = std::min(value.size(), N - 1);
    if (size != 0) {
        std::memcpy(out, value.data(), size);
    }
    out[size] = '\0';
}
void hash_fixed_text(sha256_t & state, const char * text, size_t capacity) {
    size_t size = 0;
    while (size < capacity && text[size] != '\0') {
        ++size;
    }
    hash_text(state, text, size);
}

std::array<uint8_t, 32> hash_graph_site_preflight(
        const llama_cassi_graph_site_preflight_result & result,
        const std::vector<llama_cassi_graph_site_descriptor> & sites) {
    sha256_t state;
    sha256_init(&state);
    static constexpr char domain[] = "cassi.native-graph-site-preflight.v1";
    sha256_update(&state, reinterpret_cast<const unsigned char *>(domain), sizeof(domain) - 1);
    hash_u64(state, result.version);
    hash_u64(state, result.ready);
    hash_u64(state, static_cast<uint64_t>(result.native_seq_id));
    hash_u64(state, static_cast<uint64_t>(result.next_position));
    hash_u64(state, static_cast<uint64_t>(result.sampler_mode));
    hash_f32(state, result.sampler_temperature);
    hash_u64(state, result.sampler_top_k);
    hash_f64(state, result.sampler_draw);
    hash_fixed_text(state, result.sampler_sha256, sizeof(result.sampler_sha256));
    hash_u64(state, sites.size());
    hash_fixed_text(state, result.task_id, sizeof(result.task_id));
    hash_fixed_text(state, result.sequence_id, sizeof(result.sequence_id));
    hash_fixed_text(state, result.source_sha256, sizeof(result.source_sha256));
    hash_fixed_text(state, result.model_sha256, sizeof(result.model_sha256));
    hash_fixed_text(state, result.tokenizer_sha256, sizeof(result.tokenizer_sha256));
    hash_fixed_text(state, result.predecessor_sha256, sizeof(result.predecessor_sha256));
    hash_fixed_text(state, result.native_field_epoch_sha256, sizeof(result.native_field_epoch_sha256));
    for (const llama_cassi_graph_site_descriptor & site : sites) {
        hash_u64(state, site.kind);
        hash_u64(state, site.supported);
        hash_u64(state, static_cast<uint64_t>(site.layer));
        hash_u64(state, site.input_width);
        hash_u64(state, site.output_width);
        hash_fixed_text(state, site.stage, sizeof(site.stage));
        hash_fixed_text(state, site.site, sizeof(site.site));
        hash_fixed_text(state, site.specialist, sizeof(site.specialist));
        hash_fixed_text(state, site.input_tensor, sizeof(site.input_tensor));
        hash_fixed_text(state, site.output_tensor, sizeof(site.output_tensor));
        hash_fixed_text(state, site.dependencies_json, sizeof(site.dependencies_json));
        hash_fixed_text(state, site.refusal, sizeof(site.refusal));
    }
    std::array<uint8_t, 32> digest = {};
    sha256_final(&state, digest.data());
    return digest;
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
    std::array<uint8_t, 32> tokenizer_sha256 = {};
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
    const char * architecture = gguf_get_val_str(context.get(), architecture_key);
    const bool is_moe = std::strcmp(architecture, "qwen35moe") == 0;
    if (!is_moe && std::strcmp(architecture, "qwen35") != 0) {
        fail("apprentice_model_metadata_invalid");
    }
    const std::string key_prefix = is_moe ? "qwen35moe" : "qwen35";
    model_metadata result;
    const uint32_t all_layers = gguf_get_val_u32(
        context.get(), checked_key(context.get(), (key_prefix + ".block_count").c_str(), GGUF_TYPE_UINT32));
    uint32_t nextn_layers = 0;
    const int64_t nextn_key = gguf_find_key(context.get(), (key_prefix + ".nextn_predict_layers").c_str());
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
        context.get(), checked_key(context.get(), (key_prefix + ".embedding_length").c_str(), GGUF_TYPE_UINT32));
    result.context_length = gguf_get_val_u32(
        context.get(), checked_key(context.get(), (key_prefix + ".context_length").c_str(), GGUF_TYPE_UINT32));
    const int64_t token_key = checked_key(context.get(), "tokenizer.ggml.tokens", GGUF_TYPE_ARRAY);
    if (gguf_get_arr_type(context.get(), token_key) != GGUF_TYPE_STRING) {
        fail("apprentice_model_metadata_invalid");
    }
    const int64_t token_count = gguf_get_arr_n(context.get(), token_key);
    if (token_count <= 0 || static_cast<uint64_t>(token_count) > std::numeric_limits<uint32_t>::max()) {
        fail("apprentice_model_metadata_invalid");
    }
    result.vocabulary_size = static_cast<uint32_t>(token_count);
    result.tokenizer_sha256 = hash_tokenizer_metadata(context.get());
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
    draft_pending,
    done,
    error,
    cancelled,
};

struct pending_event {
    llama_cassi_token result = {};
    llama_cassi_sampler_params sampler_before = {};
    llama_cassi_sampler_params sampler_used = {};
    bool sampler_was_pending = false;
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

// Shared weight-bank group host: rows are aligned to per-sequence slots of one
// native service context (n_seq_max > 1). One round carries every row through
// the pipeline stage by stage; row order is stable across the whole round.
struct llama_cassi_group_host {
    enum class phase { idle, staged, sampled };
    phase state = phase::idle;
    uint32_t capacity = 0;                     // native_params.n_seq_max (0 = legacy-only context)
    std::vector<llama_cassi_group_row> rows;   // active round rows

    // Fused-stage scratch: batch arrays backed across a round; each row maps
    // one token row to one sequence slot (row index == sequence id).
    std::vector<int32_t> row_seq_counts;
    std::vector<llama_seq_id> row_seq_ids;
    std::vector<llama_seq_id *> row_seq_ptrs;
    std::vector<int8_t> row_logits;
    std::vector<llama_token> row_tokens;     // tokens applied at the embed stage
    std::vector<llama_pos> row_positions;    // shared-service positions per row
};

struct pending_vector_admission {
    uint32_t page = 0;
    size_t position = 0;
    llama_token token = 0;
    std::string piece;
    std::vector<float> input;
    std::vector<float> target;
};
struct graph_site_retry_token {};
struct retained_graph_site_candidate {
    bool valid = false;
    llama_cassi_graph_site_candidate candidate = {};
    llama_cassi_graph_site_candidate_guard guard = {};
    std::string candidate_id;
    std::string sequence_id;
    std::string source_sha256;
    std::string architecture;
    std::string backend;
    std::string input_tensor;
    std::string output_tensor;
    std::string tensor_dtype;
    std::string stage;
    std::string site;
    std::string specialist;
    std::string predecessor_sha256;
    std::string request_sha256;
    std::string invocation_sha256;
    std::string candidate_sha256;
    std::string intervention_order;
    std::string dependencies_json;
    std::string method_key;
    std::string native_preflight_sha256;
    std::string native_predecessor_sha256;
    std::string owner_snapshot_sha256;
    std::string field_epoch_sha256;
    std::vector<float> a;
    std::vector<float> b;
    std::vector<float> bias;
    std::vector<float> input_support_anchor;
    std::vector<int32_t> expected_expert_ids;

    void rebind() {
        candidate.sequence_id = sequence_id.c_str();
        candidate.source_sha256 = source_sha256.c_str();
        candidate.architecture = architecture.c_str();
        candidate.backend = backend.c_str();
        candidate.input_tensor = input_tensor.c_str();
        candidate.output_tensor = output_tensor.c_str();
        candidate.tensor_dtype = tensor_dtype.c_str();
        candidate.stage = stage.c_str();
        candidate.site = site.c_str();
        candidate.specialist = specialist.c_str();
        candidate.predecessor_sha256 = predecessor_sha256.c_str();
        candidate.request_sha256 = request_sha256.c_str();
        candidate.invocation_sha256 = invocation_sha256.c_str();
        candidate.candidate_sha256 = candidate_sha256.c_str();
        candidate.intervention_order = intervention_order.c_str();
        candidate.dependencies_json = dependencies_json.c_str();
        candidate.method_key = method_key.c_str();
        candidate.a = a.data();
        candidate.a_count = a.size();
        candidate.b = b.data();
        candidate.b_count = b.size();
        candidate.bias = bias.data();
        candidate.bias_count = bias.size();
        candidate.input_support_anchor =
            input_support_anchor.empty() ? nullptr : input_support_anchor.data();
        candidate.input_support_anchor_count = input_support_anchor.size();
        candidate.input_support_radius = guard.input_support_radius;
        candidate.input_support_anchor_norm = guard.input_support_anchor_norm;
        candidate.expected_expert_ids =
            expected_expert_ids.empty() ? nullptr : expected_expert_ids.data();
        candidate.expected_expert_ids_count = expected_expert_ids.size();
        guard.candidate_id = candidate_id.c_str();
        guard.native_preflight_sha256 = native_preflight_sha256.c_str();
        guard.native_predecessor_sha256 = native_predecessor_sha256.c_str();
        guard.owner_snapshot_sha256 = owner_snapshot_sha256.c_str();
        guard.field_epoch_sha256 = field_epoch_sha256.c_str();
        guard.input_support_anchor = input_support_anchor.empty() ? nullptr : input_support_anchor.data();
        guard.input_support_anchor_count = input_support_anchor.size();
        guard.expected_expert_ids =
            expected_expert_ids.empty() ? nullptr : expected_expert_ids.data();
        guard.expected_expert_ids_count = expected_expert_ids.size();
    }
};

} // namespace

struct llama_cassi_context {
    static constexpr size_t GRAPH_SITE_STAGE_EVENT_LIMIT = 4096;
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
    bool graph_site_preflight_valid = false;
    llama_cassi_graph_site_preflight_result last_graph_site_preflight = {};
    std::vector<llama_cassi_graph_site_descriptor> last_graph_site_sites;
    retained_graph_site_candidate graph_site_candidate;
    llama_cassi_graph_site_candidate_receipt graph_site_candidate_result = {};
    std::vector<int32_t> graph_site_candidate_actual_expert_ids;
    std::vector<llama_cassi_graph_site_stage_event> graph_site_candidate_stage_trace;
    bool graph_site_candidate_observed = false;
    bool graph_site_candidate_result_valid = false;
    size_t prompt_token_count = 0;
    std::vector<pending_vector_admission> pending_vector_admissions;
    uint64_t pending_admission_payload_bytes = 0;
    std::vector<uint8_t> transaction_field_snapshot;
    pending_event accepted;
    std::vector<uint8_t> context_snapshot;
    bool draft_pending_valid = false;
    llama_token draft_extra_token = 0;
    size_t draft_predecessor_prefix = 0;
    uint32_t draft_accepted_count = 0;
    llama_cassi_sampler_params draft_final_sampler = {};
    char draft_receipt_sha256[65] = {};

    std::vector<float> pending_head_input;
    session_state state = session_state::idle;
    std::atomic<bool> cancellation_requested{false};
    std::string error;
    std::vector<llama_token> token_log;
    int32_t prediction_limit = 0;
    pending_event pending;
    llama_cassi_stats stats = {};
    llama_cassi_sampler_params sampler = {
        LLAMA_CASSI_SAMPLER_GREEDY,
        1.0f,
        0,
        0.0,
    };
    llama_cassi_sampler_params pending_sampler = {};
    bool pending_sampler_valid = false;
    std::vector<llama_cassi_service_stats> service_stats;
    std::vector<uint64_t> service_node_baseline;
    std::vector<uint64_t> service_weight_baseline;
    llama_cassi_group_host group_host;
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
            params_value.route_policy < LLAMA_CASSI_AUTO || params_value.route_policy > LLAMA_CASSI_EXACT_PIPELINE) {
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
        if (params_value.model_sha256 != nullptr) {
            std::memcpy(model_hash.data(), params_value.model_sha256, model_hash.size());
        } else {
            model_hash = hash_file(model_path);
        }
        public_params.model_sha256 = nullptr;
        if (model->arch != LLM_ARCH_QWEN35 && model->arch != LLM_ARCH_QWEN35MOE) {
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
        if (public_params.route_policy == LLAMA_CASSI_EXACT_PIPELINE &&
                (!fully_loaded || public_params.teacher_policy != LLAMA_CASSI_NEVER)) {
            fail("apprentice_exact_pipeline_requires_native_model");
        }
        if (native_params.n_ctx == 0 || native_params.n_ctx > metadata.context_length) {
            fail("apprentice_context_invalid");
        }
        // Legacy single-sequence contexts stay clamped; a caller that asks for
        // n_seq_max > 1 turns this context into a shared weight-bank group host
        // (exact pipeline only): one KV/GDN slot per row, stages bind n_rows.
        group_host.capacity =
            native_params.n_seq_max > 1 && public_params.route_policy == LLAMA_CASSI_EXACT_PIPELINE
                ? native_params.n_seq_max
                : 0;
        if (group_host.capacity > 0) {
            // Homogeneous multi-row ubatches with arbitrary distinct sequence
            // ids require a unified KV cache (the hybrid sequential split only
            // accepts strictly consecutive increasing sequence ids).
            native_params.kv_unified = true;
            native_params.n_batch = std::max<uint32_t>(group_host.capacity, native_params.n_batch);
            native_params.n_ubatch = std::max<uint32_t>(group_host.capacity, native_params.n_ubatch);
        } else {
            native_params.n_seq_max = 1;
        }
        if (public_params.route_policy != LLAMA_CASSI_EXACT_PIPELINE) {
            native_params.n_rs_seq = 0;
        }
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
        field_config.scratch_only = public_params.route_policy == LLAMA_CASSI_EXACT_PIPELINE;
        if (group_host.capacity > 0) {
            // Group stages hand host rows through the shared matrix scratch.
            field_config.group_rows = group_host.capacity;
        }
        field = std::make_unique<llama_cassi_field>(field_config);
        if (!field_config.scratch_only) {
            field->profile_sha256(profile_hash.data());
            context_snapshot.resize(field->context_snapshot_size());
        }
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
        if (public_params.route_policy == LLAMA_CASSI_EXACT_PIPELINE) {
            const auto add_service = [&](uint32_t kind, int32_t layer) {
                llama_cassi_service_stats value = {};
                value.kind = kind;
                value.layer = layer;
                service_stats.push_back(value);
            };
            add_service(LLAMA_CASSI_TEXT, -1);
            add_service(LLAMA_CASSI_EMBED, -1);
            add_service(LLAMA_CASSI_HEAD, -1);
            for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
                add_service(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer));
                add_service(LLAMA_CASSI_FFN, static_cast<int32_t>(layer));
            }
        } else {
            for (const cassi_field_page & page : field->pages()) {
                llama_cassi_service_stats value = {};
                value.kind = static_cast<uint32_t>(page.kind);
                value.layer = page.layer;
                service_stats.push_back(value);
            }
        }
        service_node_baseline.resize(service_stats.size());
        service_weight_baseline.resize(service_stats.size());
    }

    const llama_vocab * vocab() const {
        return llama_model_get_vocab(model);
    }
    bool exact_pipeline() const {
        return public_params.route_policy == LLAMA_CASSI_EXACT_PIPELINE;
    }
    const llama_cassi_sampler_params & effective_sampler() const {
        return pending_sampler_valid ? pending_sampler : sampler;
    }
    bool sampler_valid(const llama_cassi_sampler_params & value) const {
        return sampler_tuple_valid(value) &&
            (value.mode != LLAMA_CASSI_SAMPLER_CATEGORICAL ||
                value.top_k <= metadata.vocabulary_size);
    }
    int32_t set_sampler(const llama_cassi_sampler_params & value) {
        if (!exact_pipeline() || (state != session_state::idle && state != session_state::ready)) {
            fail("apprentice_invalid_transition");
        }
        if (!sampler_valid(value)) {
            fail("apprentice_sampler_invalid");
        }
        if (graph_site_candidate.valid &&
                (!graph_site_preflight_valid ||
                 digest_hex(hash_graph_site_sampler_tuple(value).data()) !=
                    std::string(last_graph_site_preflight.sampler_sha256))) {
            fail("apprentice_graph_site_sampler_mismatch");
        }
        pending_sampler = value;
        pending_sampler_valid = true;
        if (graph_site_preflight_valid &&
                digest_hex(hash_graph_site_sampler_tuple(value).data()) !=
                    std::string(last_graph_site_preflight.sampler_sha256)) {
            graph_site_preflight_valid = false;
        }
        return 0;
    }
    int32_t discard_sampler() {
        if (!exact_pipeline() || (state != session_state::idle && state != session_state::ready) ||
                graph_site_candidate.valid) {
            fail("apprentice_invalid_transition");
        }
        pending_sampler = {};
        pending_sampler_valid = false;
        if (graph_site_preflight_valid &&
                digest_hex(hash_graph_site_sampler_tuple(sampler).data()) !=
                    std::string(last_graph_site_preflight.sampler_sha256)) {
            graph_site_preflight_valid = false;
        }
        return 0;
    }

    int32_t discard_pending() {
        if (!exact_pipeline() || state != session_state::pending) {
            fail("apprentice_invalid_transition");
        }
        if (service == nullptr || service_abandoned || service_token_active ||
                service_prefix == 0 || service_prefix != token_log.size()) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (service->cassi_cancel_token() != 0) {
            service.reset();
            service_abandoned = true;
            fail("apprentice_native_rollback_failed");
        }
        --service_prefix;
        ++service_epoch;
        pending = {};
        pending_sampler = {};
        pending_sampler_valid = false;
        graph_site_preflight_valid = false;
        state = session_state::ready;
        refresh_cache_gauges();
        return 0;
    }
    int32_t verify_draft(
            const llama_cassi_draft_verify_request & request,
            llama_cassi_draft_verify_receipt & receipt) {
        if (!exact_pipeline() || state != session_state::pending) {
            fail("apprentice_invalid_transition");
        }
        check_cancelled();
        if (service == nullptr || service_abandoned || service_token_active ||
                service_prefix == 0 || service_prefix != token_log.size()) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (request.draft_count == 0 || request.draft_count > LLAMA_CASSI_MAX_DRAFT_TOKENS ||
                request.draft_tokens == nullptr || request.proposal_probabilities == nullptr ||
                request.target_samplers == nullptr ||
                request.target_sampler_count != static_cast<size_t>(request.draft_count) + 1) {
            fail("apprentice_draft_request_invalid");
        }
        for (uint32_t i = 0; i < request.draft_count; ++i) {
            if (request.proposal_probabilities[i] != 1.0) {
                fail("apprentice_draft_proposal_not_deterministic");
            }
            if (request.draft_tokens[i] < 0 ||
                    static_cast<uint32_t>(request.draft_tokens[i]) >= metadata.vocabulary_size) {
                fail("apprentice_token_invalid");
            }
        }
        for (size_t i = 0; i < request.target_sampler_count; ++i) {
            if (!sampler_valid(request.target_samplers[i])) {
                fail("apprentice_sampler_invalid");
            }
        }
        if (native_params.n_ubatch < request.draft_count + 1 ||
                native_params.n_rs_seq < request.draft_count + 1) {
            fail("apprentice_draft_verify_capacity_insufficient");
        }

        const uint64_t stages_before = stats.native_exact_stages;
        const uint64_t attention_before = stats.native_exact_attention_stages;
        const uint64_t ffn_before = stats.native_exact_ffn_stages;
        const uint64_t head_groups_before = stats.native_exact_head_groups;
        const uint64_t draws_before = stats.native_sampler_draws;

        const std::array<uint8_t, 32> native_predecessor =
            native_sequence_predecessor_hash(0, request.target_samplers[0]);

        const size_t old_prefix = token_log.size();
        token_log.push_back(pending.result.token);
        std::vector<float> logits;
        process_pipeline_token(old_prefix, true, &logits);

        uint32_t accepted_count = 0;
        bool rejected = false;
        bool bonus = false;
        std::array<llama_token, LLAMA_CASSI_MAX_DRAFT_TOKENS + 1> output_tokens = {};

        for (uint32_t i = 0; i < request.draft_count; ++i) {
            const llama_cassi_q_delta_result step = sample_exact_q_delta(
                logits.data(), logits.size(), request.draft_tokens[i], request.target_samplers[i]);
            if (step.draws_consumed != 0) {
                stats.native_sampler_draws++;
            }
            if (!step.accepted) {
                output_tokens[accepted_count] = step.token;
                rejected = true;
                break;
            }
            output_tokens[accepted_count] = request.draft_tokens[i];
            ++accepted_count;
            token_log.push_back(request.draft_tokens[i]);
            process_pipeline_token(old_prefix + accepted_count, true, &logits);
        }
        if (!rejected) {
            output_tokens[accepted_count] = sample_exact_logit_row(
                logits, request.target_samplers[request.draft_count]);
            bonus = true;
        }

        const llama_cassi_sampler_params & final_sampler =
            request.target_samplers[bonus ? request.draft_count : accepted_count];
        const std::array<uint8_t, 32> native_successor =
            native_sequence_predecessor_hash(0, final_sampler);

        llama_cassi_draft_verify_receipt out = {};
        out.version = 1;
        out.draft_count = request.draft_count;
        out.accepted_count = accepted_count;
        out.output_count = accepted_count + 1;
        out.retained_input_count = accepted_count + 1;
        out.sampler_draws_consumed = static_cast<uint32_t>(stats.native_sampler_draws - draws_before);
        out.rejected = rejected;
        out.bonus = bonus;
        for (uint32_t i = 0; i < out.output_count; ++i) {
            out.output_tokens[i] = output_tokens[i];
        }
        copy_c_string(out.task_id, request.task_id == nullptr ? std::string() : std::string(request.task_id));
        copy_c_string(out.sequence_id, request.sequence_id == nullptr ? std::string() : std::string(request.sequence_id));
        copy_c_string(out.native_operation_id,
            request.native_operation_id == nullptr ? std::string() : std::string(request.native_operation_id));
        copy_c_string(out.proposal_sha256,
            request.proposal_sha256 == nullptr ? std::string() : std::string(request.proposal_sha256));
        copy_c_string(out.owner_predecessor_sha256,
            request.owner_predecessor_sha256 == nullptr ? std::string() : std::string(request.owner_predecessor_sha256));
        copy_c_string(out.model_sha256, digest_hex(model_hash.data()));
        copy_c_string(out.sampler_sha256,
            request.sampler_sha256 == nullptr ? std::string() : std::string(request.sampler_sha256));
        copy_c_string(out.native_predecessor_sha256, digest_hex(native_predecessor.data()));
        copy_c_string(out.native_successor_sha256, digest_hex(native_successor.data()));
        out.native_exact_stages = stats.native_exact_stages - stages_before;
        out.native_exact_attention_stages = stats.native_exact_attention_stages - attention_before;
        out.native_exact_ffn_stages = stats.native_exact_ffn_stages - ffn_before;
        out.native_exact_head_groups = stats.native_exact_head_groups - head_groups_before;

        sha256_t receipt_state;
        sha256_init(&receipt_state);
        static constexpr char domain[] = "cassi.draft-verify-receipt.v1";
        sha256_update(&receipt_state, reinterpret_cast<const unsigned char *>(domain), sizeof(domain) - 1);
        sha256_update(&receipt_state, native_predecessor.data(), native_predecessor.size());
        sha256_update(&receipt_state, native_successor.data(), native_successor.size());
        hash_u64(receipt_state, out.output_count);
        for (uint32_t i = 0; i < out.output_count; ++i) {
            hash_u64(receipt_state, static_cast<uint64_t>(static_cast<uint32_t>(out.output_tokens[i])));
        }
        sha256_update(&receipt_state, reinterpret_cast<const unsigned char *>(out.task_id), std::strlen(out.task_id));
        sha256_update(&receipt_state, reinterpret_cast<const unsigned char *>(out.sequence_id), std::strlen(out.sequence_id));
        sha256_update(&receipt_state,
            reinterpret_cast<const unsigned char *>(out.native_operation_id), std::strlen(out.native_operation_id));
        std::array<uint8_t, 32> receipt_digest = {};
        sha256_final(&receipt_state, receipt_digest.data());
        const std::string receipt_hex = digest_hex(receipt_digest.data());
        copy_c_string(out.receipt_sha256, receipt_hex);
        copy_c_string(draft_receipt_sha256, receipt_hex);

        draft_extra_token = output_tokens[accepted_count];
        draft_predecessor_prefix = old_prefix;
        draft_accepted_count = accepted_count;
        draft_final_sampler = final_sampler;
        draft_pending_valid = true;
        state = session_state::draft_pending;
        receipt = out;
        return 0;
    }
    int32_t verify_commit(const char * receipt_sha256) {
        if (state != session_state::draft_pending || !draft_pending_valid) {
            fail("apprentice_draft_no_pending_transaction");
        }
        if (receipt_sha256 == nullptr || std::strcmp(receipt_sha256, draft_receipt_sha256) != 0) {
            fail("apprentice_draft_receipt_mismatch");
        }
        check_cancelled();
        token_log.push_back(draft_extra_token);
        const uint64_t committed = static_cast<uint64_t>(draft_accepted_count) + 2;
        stats.committed_tokens += committed;
        stats.native_exact_tokens += committed;
        sampler = draft_final_sampler;
        pending_sampler = {};
        pending_sampler_valid = false;
        pending = {};
        draft_pending_valid = false;
        graph_site_preflight_valid = false;
        state = stats.committed_tokens >= static_cast<uint64_t>(prediction_limit) ||
            llama_vocab_is_eog(vocab(), draft_extra_token) ? session_state::done : session_state::ready;
        refresh_cache_gauges();
        return 0;
    }
    int32_t verify_discard(const char * receipt_sha256) {
        if (state != session_state::draft_pending || !draft_pending_valid) {
            fail("apprentice_draft_no_pending_transaction");
        }
        if (receipt_sha256 == nullptr || std::strcmp(receipt_sha256, draft_receipt_sha256) != 0) {
            fail("apprentice_draft_receipt_mismatch");
        }
        // verify_draft's exact-pipeline evaluations (the pending token's own
        // forward pass plus each accepted draft token) ran through the plain
        // single-token service API outside the graph-site-candidate rollback
        // window, so cassi_end_token already made their KV writes permanent.
        // Discarding therefore truncates the native context back to the
        // predecessor position instead of cancelling an in-flight transaction.
        if (service->cassi_service_rewind(static_cast<llama_pos>(draft_predecessor_prefix)) != 0) {
            service.reset();
            service_abandoned = true;
            fail("apprentice_native_rollback_failed");
        }
        service_prefix = draft_predecessor_prefix;
        ++service_epoch;
        token_log.resize(draft_predecessor_prefix);
        draft_pending_valid = false;
        graph_site_preflight_valid = false;
        state = session_state::pending;
        refresh_cache_gauges();
        return 0;
    }
    llama_cassi_sampler_params preflight_sampler() const {
        return {
            last_graph_site_preflight.sampler_mode,
            last_graph_site_preflight.sampler_temperature,
            last_graph_site_preflight.sampler_top_k,
            last_graph_site_preflight.sampler_draw,
        };
    }
    bool graph_site_preflight_matches_native() const {
        if (!graph_site_preflight_valid || !exact_pipeline() || service_token_active ||
                state != session_state::ready || !service) {
            return false;
        }
        const llama_cassi_sampler_params tuple = preflight_sampler();
        if (!sampler_valid(tuple) ||
                digest_hex(hash_graph_site_sampler_tuple(tuple).data()) !=
                    std::string(last_graph_site_preflight.sampler_sha256)) {
            return false;
        }
        const std::array<uint8_t, 32> predecessor = native_sequence_predecessor_hash(0, tuple);
        return digest_hex(predecessor.data()) ==
            std::string(last_graph_site_preflight.predecessor_sha256);
    }
    bool graph_site_preflight_matches_effective_sampler() const {
        return graph_site_preflight_valid && sampler_valid(effective_sampler()) &&
            digest_hex(hash_graph_site_sampler_tuple(effective_sampler()).data()) ==
                std::string(last_graph_site_preflight.sampler_sha256);
    }



    void set_error(const char * code) {
        error = code;
        state = session_state::error;
    }

    void check_cancelled() {
        if (cancellation_requested.load(std::memory_order_acquire)) {
            graph_site_candidate_clear_stage_trace();
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
        if (exact_pipeline()) {
            if (state != session_state::ready && state != session_state::done) {
                fail("apprentice_invalid_transition");
            }
            if (stats.committed_tokens == 0 || token_log.size() <= prompt_token_count ||
                    token_log.back() != accepted.result.token) {
                fail("apprentice_invalid_transition");
            }
            if (service == nullptr || service_abandoned || service_token_active ||
                    service_prefix == 0 || service_prefix != token_log.size() - 1) {
                fail("apprentice_native_service_prefix_unavailable");
            }
            if (service->cassi_cancel_token() != 0) {
                service.reset();
                service_abandoned = true;
                fail("apprentice_native_rollback_failed");
            }
            --service_prefix;
            ++service_epoch;
            stats.committed_tokens--;
            stats.native_exact_tokens--;
            token_log.pop_back();
            sampler = accepted.sampler_before;
            if (!pending_sampler_valid && accepted.sampler_was_pending) {
                pending_sampler = accepted.sampler_used;
                pending_sampler_valid = true;
            }
            graph_site_preflight_valid = false;
            refresh_cache_gauges();
            clear_accepted_transaction();
            state = session_state::ready;
            return;
        }
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
    std::array<uint8_t, 32> native_sequence_predecessor_hash(
            uint64_t native_seq_id, const llama_cassi_sampler_params & sampler_value) const {
        if (!service) {
            fail("apprentice_native_service_context_unavailable");
        }
        const size_t size = llama_state_get_size(service.get());
        if (size == 0) {
            fail("apprentice_native_sequence_state_unavailable");
        }
        std::vector<uint8_t> serialized(size);
        const size_t written = llama_state_get_data(service.get(), serialized.data(), serialized.size());
        if (written != size) {
            fail("apprentice_native_sequence_state_unavailable");
        }
        sha256_t state;
        sha256_init(&state);
        static constexpr char domain[] = "cassi.native-sequence-predecessor.v1";
        sha256_update(&state, reinterpret_cast<const unsigned char *>(domain), sizeof(domain) - 1);
        sha256_update(&state, model_hash.data(), model_hash.size());
        hash_u64(state, native_seq_id);
        hash_u64(state, service_prefix);
        const std::array<uint8_t, 32> sampler_digest = hash_native_sampler_tuple(sampler_value);
        sha256_update(&state, sampler_digest.data(), sampler_digest.size());
        hash_u64(state, serialized.size());
        sha256_update(&state, serialized.data(), serialized.size());
        std::array<uint8_t, 32> digest = {};
        sha256_final(&state, digest.data());
        return digest;
    }
    int32_t provisional_state_sha256(char * out_sha256) const {
        if (out_sha256 == nullptr || state != session_state::pending || !exact_pipeline()) {
            fail("apprentice_provisional_state_unavailable");
        }
        const std::array<uint8_t, 32> digest =
            native_sequence_predecessor_hash(0, effective_sampler());
        const std::string encoded = digest_hex(digest.data());
        std::memcpy(out_sha256, encoded.c_str(), encoded.size() + 1);
        return 0;
    }

    std::vector<llama_cassi_graph_site_descriptor> graph_site_descriptors() const {
        std::vector<llama_cassi_graph_site_descriptor> sites;
        const bool single_sequence = native_params.n_seq_max <= 1;
        const bool candidate_runtime = exact_pipeline() && single_sequence;
        const auto append = [&](uint32_t kind, bool supported, int32_t layer,
                uint32_t input_width, uint32_t output_width,
                const char * stage, const char * site, const char * specialist,
                const char * input_tensor, const char * output_tensor,
                const std::string & dependencies, const char * refusal) {
            llama_cassi_graph_site_descriptor descriptor = {};
            descriptor.kind = kind;
            descriptor.supported = supported;
            descriptor.layer = layer;
            descriptor.input_width = input_width;
            descriptor.output_width = output_width;
            copy_c_string(descriptor.stage, stage);
            copy_c_string(descriptor.site, site);
            copy_c_string(descriptor.specialist, specialist);
            copy_c_string(descriptor.input_tensor, input_tensor);
            copy_c_string(descriptor.output_tensor, output_tensor);
            copy_c_string(descriptor.dependencies_json, dependencies);
            copy_c_string(descriptor.refusal, refusal);
            sites.push_back(descriptor);
        };
        for (uint32_t layer_index = 0; layer_index < metadata.layers; ++layer_index) {
            const int32_t layer_id = static_cast<int32_t>(layer_index);
            const auto & layer = model->layers[layer_index];
            if (model->hparams.is_recr(layer_index)) {
                const uint64_t conv_rows = layer.ssm_conv1d == nullptr || layer.ssm_conv1d->ne[0] <= 1
                    ? 0 : static_cast<uint64_t>(layer.ssm_conv1d->ne[0] - 1);
                const uint64_t conv_channels =
                    model->hparams.ssm_d_inner + 2ULL * model->hparams.ssm_n_group * model->hparams.ssm_d_state;
                const uint64_t state_heads = model->hparams.ssm_dt_rank;
                const uint64_t state_head_width = state_heads == 0 ? 0 :
                    model->hparams.ssm_d_inner / state_heads;
                const uint64_t state_width = state_heads * state_head_width * state_head_width;
                const uint64_t input_width = metadata.embedding_width +
                    model->hparams.n_embd_r() + model->hparams.n_embd_s();
                const bool supported = candidate_runtime && layer.ssm_conv1d != nullptr && conv_rows != 0 &&
                    conv_channels != 0 && state_heads != 0 && state_head_width != 0 &&
                    state_width != 0 && input_width <= UINT32_MAX;
                const std::string dependencies =
                    "{\"architecture\":\"qwen35moe\",\"layer\":" + std::to_string(layer_index) +
                    ",\"operators\":[\"gdn-convolution\",\"gdn-recurrent-state-update\"]" +
                    ",\"state_effects\":[\"conv_history\",\"recurrent_state\"]" +
                    ",\"conv_history_rows\":" + std::to_string(conv_rows) +
                    ",\"conv_history_channels\":" + std::to_string(conv_channels) +
                    ",\"recurrent_state_heads\":" + std::to_string(state_heads) +
                    ",\"recurrent_state_value_width\":" + std::to_string(state_head_width) +
                    ",\"recurrent_state_key_width\":" + std::to_string(state_head_width) + "}";
                append(LLAMA_CASSI_SITE_RECURRENT, supported, layer_id,
                    supported ? static_cast<uint32_t>(input_width) : 0,
                    supported ? static_cast<uint32_t>(input_width) : 0,
                    "qwen-attention-route", "recurrent-attention", "recurrent-dynamics",
                    "recurrent_features", "recurrent_successor", dependencies,
                    supported ? "" : "recurrent_successor_unsupported");
            } else {
                const uint64_t kv_heads = model->hparams.n_head_kv(layer_index);
                const uint64_t kv_head_width = model->hparams.n_embd_head_v(layer_index);
                const uint64_t output_width64 = metadata.embedding_width + 2ULL * kv_heads * kv_head_width;
                const bool supported = candidate_runtime && layer.wo != nullptr &&
                    kv_heads != 0 && kv_head_width != 0 &&
                    kv_head_width == model->hparams.n_embd_head_k(layer_index) &&
                    output_width64 <= UINT32_MAX;
                const std::string dependencies =
                    "{\"architecture\":\"qwen35moe\",\"layer\":" + std::to_string(layer_index) +
                    ",\"operators\":[\"attention-qkv\",\"attention-memory-read\",\"attention-memory-write\"]" +
                    ",\"state_effects\":[\"attention_memory\"]" +
                    ",\"kv_heads\":" + std::to_string(kv_heads) +
                    ",\"kv_head_width\":" + std::to_string(kv_head_width) + "}";
                append(LLAMA_CASSI_SITE_ATTENTION_MEMORY, supported, layer_id,
                    supported ? metadata.embedding_width : 0,
                    supported ? static_cast<uint32_t>(output_width64) : 0,
                    "qwen-attention-route", "attention-memory", "attention-memory",
                    "attention_features", "attention_successor", dependencies,
                    supported ? "" : "attention_memory_successor_unsupported");
            }
            if (layer.ffn_gate_inp != nullptr) {
                const bool routed_experts = layer.ffn_down_exps != nullptr &&
                    (layer.ffn_gate_up_exps != nullptr ||
                     (layer.ffn_gate_exps != nullptr && layer.ffn_up_exps != nullptr));
                const bool any_shared = layer.ffn_gate_inp_shexp != nullptr ||
                    layer.ffn_gate_shexp != nullptr || layer.ffn_up_shexp != nullptr ||
                    layer.ffn_down_shexp != nullptr;
                const bool full_shared = !any_shared ||
                    (layer.ffn_gate_inp_shexp != nullptr && layer.ffn_gate_shexp != nullptr &&
                     layer.ffn_up_shexp != nullptr && layer.ffn_down_shexp != nullptr);
                const bool supported = candidate_runtime && routed_experts && full_shared;
                const std::string dependencies =
                    "{\"architecture\":\"qwen35moe\",\"layer\":" + std::to_string(layer_index) +
                    ",\"operators\":[\"moe-router\",\"routed-expert-gate-up\",\"routed-expert-down\"" +
                    (any_shared ? ",\"shared-expert-gate-up\",\"shared-expert-down\"" : "") +
                    "],\"state_effects\":[],\"expert_count\":" + std::to_string(model->hparams.n_expert) +
                    ",\"experts_per_token\":" + std::to_string(model->hparams.n_expert_used) + "}";
                append(LLAMA_CASSI_SITE_EXPERTS, supported, layer_id,
                    metadata.embedding_width, metadata.embedding_width,
                    "qwen-experts", "qwen-experts", "expert-synthesis",
                    "attn_post_norm", "ffn_delta", dependencies,
                    supported ? "" : "expert_synthesis_unsupported");
            }
        }
        {
            const bool execution_choice_supported = candidate_runtime;
            append(LLAMA_CASSI_SITE_EXECUTION_CHOICE, execution_choice_supported, -1,
                execution_choice_supported ? metadata.embedding_width : 0,
                execution_choice_supported ? metadata.vocabulary_size : 0,
                "qwen-head", "execution-choice", "execution-choice",
                "head_input", "logits", "{\"architecture\":\"qwen35moe\",\"layer\":-1,\"operators\":[\"lm-head\",\"sampler\"]}",
                execution_choice_supported ? "" : "execution_choice_requires_owner_publication");
        }
        if (model->hparams.n_layer_nextn > 0) {
            append(LLAMA_CASSI_SITE_DEPTH, false, static_cast<int32_t>(metadata.layers),
                metadata.embedding_width, metadata.embedding_width,
                "qwen-mtp", "depth", "depth-prediction",
                "mtp_input", "mtp_successor",
                "{\"architecture\":\"qwen35moe\",\"operators\":[\"mtp-decoder\"],\"state_effects\":[\"mtp_hidden\",\"attention_memory\"]}",
                "depth_successor_unsupported");
            append(LLAMA_CASSI_SITE_DRAFT, false, static_cast<int32_t>(metadata.layers),
                metadata.embedding_width, metadata.vocabulary_size,
                "qwen-mtp", "draft", "draft-verification",
                "mtp_input", "draft_logits",
                "{\"architecture\":\"qwen35moe\",\"operators\":[\"mtp-decoder\",\"draft-verification\"]}",
                "draft_acceptance_unsupported");
        }
        return sites;
    }

    size_t graph_site_preflight(
            const char * task_id,
            const char * sequence_id,
            const llama_cassi_sampler_params * upcoming_sampler,
            llama_cassi_graph_site_preflight_result * out,
            llama_cassi_graph_site_descriptor * sites,
            size_t site_capacity) {
        if (out == nullptr) {
            fail("apprentice_graph_site_preflight_output_required");
        }
        *out = {};
        if (graph_site_candidate.valid) {
            copy_c_string(out->refusal, "graph_site_candidate_already_pending");
            return 0;
        }
        graph_site_preflight_valid = false;
        const llama_cassi_sampler_params & sampler_value =
            upcoming_sampler == nullptr ? effective_sampler() : *upcoming_sampler;
        if (!sampler_valid(sampler_value)) {
            copy_c_string(out->refusal, "invalid_sampler_tuple");
            return 0;
        }
        out->version = 1;
        if (task_id == nullptr || task_id[0] == '\0' ||
                sequence_id == nullptr || sequence_id[0] == '\0' ||
                std::strlen(task_id) >= sizeof(out->task_id) ||
                std::strlen(sequence_id) >= sizeof(out->sequence_id)) {
            copy_c_string(out->refusal, "invalid_task_or_sequence_id");
            return 0;
        }
        copy_c_string(out->task_id, task_id);
        copy_c_string(out->sequence_id, sequence_id);
        if (site_capacity != 0 && sites == nullptr) {
            copy_c_string(out->refusal, "site_buffer_required");
            return 0;
        }
        if (!exact_pipeline()) {
            copy_c_string(out->refusal, "exact_pipeline_required");
            return 0;
        }
        if (state != session_state::ready || service_token_active || group_host.capacity > 1) {
            copy_c_string(out->refusal, "native_sequence_not_ready");
            return 0;
        }
        if (service_prefix >= token_log.size() ||
                token_log.size() - service_prefix != 1) {
            copy_c_string(out->refusal, "native_sequence_not_at_single_token_boundary");
            return 0;
        }
        try {
            ensure_service_context(service_prefix);
            out->native_seq_id = 0;
            if (service_prefix > static_cast<size_t>(std::numeric_limits<llama_pos>::max())) {
                copy_c_string(out->refusal, "native_position_out_of_range");
                return 0;
            }
            out->next_position = static_cast<llama_pos>(service_prefix);
            copy_c_string(out->source_sha256, digest_hex(model_hash.data()));
            copy_c_string(out->model_sha256, digest_hex(model_hash.data()));
            copy_c_string(out->tokenizer_sha256, digest_hex(metadata.tokenizer_sha256.data()));
            out->sampler_mode = sampler_value.mode;
            out->sampler_temperature = sampler_value.temperature;
            out->sampler_top_k = sampler_value.top_k;
            out->sampler_draw = sampler_value.draw;
            const std::array<uint8_t, 32> sampler_digest =
                hash_graph_site_sampler_tuple(sampler_value);
            copy_c_string(out->sampler_sha256, digest_hex(sampler_digest.data()));
            const std::array<uint8_t, 32> predecessor = native_sequence_predecessor_hash(0, sampler_value);
            copy_c_string(out->predecessor_sha256, digest_hex(predecessor.data()));
            std::array<uint8_t, 32> native_field_epoch = {};
            if (!exact_pipeline()) {
                field->field_sha256(native_field_epoch.data());
            }
            copy_c_string(out->native_field_epoch_sha256, digest_hex(native_field_epoch.data()));
            std::vector<llama_cassi_graph_site_descriptor> planned = graph_site_descriptors();
            if (planned.size() > UINT32_MAX) {
                fail("apprentice_graph_site_descriptor_overflow");
            }
            out->site_count = static_cast<uint32_t>(planned.size());
            out->ready = true;
            const std::array<uint8_t, 32> preflight_sha = hash_graph_site_preflight(*out, planned);
            copy_c_string(out->native_preflight_sha256, digest_hex(preflight_sha.data()));
            const size_t copied = std::min(site_capacity, planned.size());
            for (size_t i = 0; i < copied; ++i) {
                sites[i] = planned[i];
            }
            const size_t total = planned.size();
            last_graph_site_preflight = *out;
            last_graph_site_sites = std::move(planned);
            graph_site_preflight_valid = true;
            return total;
        } catch (const std::exception & exception) {
            *out = {};
            out->version = 1;
            copy_c_string(out->task_id, task_id);
            copy_c_string(out->sequence_id, sequence_id);
            copy_c_string(out->refusal, exception.what());
            return 0;
        } catch (...) {
            *out = {};
            out->version = 1;
            copy_c_string(out->task_id, task_id);
            copy_c_string(out->sequence_id, sequence_id);
            copy_c_string(out->refusal, "native_graph_site_preflight_failed");
            return 0;
        }
    }
    static bool valid_graph_site_sha256(const char * value) {
        if (value == nullptr || std::strlen(value) != 64) {
            return false;
        }
        for (size_t i = 0; i < 64; ++i) {
            const char c = value[i];
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
                return false;
            }
        }
        return true;
    }

    static bool bounded_graph_site_text(const char * value, size_t maximum) {
        if (value == nullptr || value[0] == '\0') {
            return false;
        }
        size_t size = 0;
        while (size <= maximum && value[size] != '\0') {
            ++size;
        }
        return size != 0 && size <= maximum;
    }

    void graph_site_receipt_binding(
            llama_cassi_graph_site_candidate_receipt & receipt) const {
        if (!graph_site_candidate.candidate_sha256.empty()) {
            copy_c_string(receipt.candidate_sha256, graph_site_candidate.candidate_sha256);
            copy_c_string(receipt.request_sha256, graph_site_candidate.request_sha256);
            copy_c_string(receipt.invocation_sha256, graph_site_candidate.invocation_sha256);
            receipt.request_sha256_pending =
                graph_site_candidate.candidate.request_sha256_pending;
            copy_c_string(receipt.predecessor_sha256, graph_site_candidate.predecessor_sha256);
            copy_c_string(receipt.candidate_id, graph_site_candidate.candidate_id);
            copy_c_string(receipt.native_predecessor_sha256,
                graph_site_candidate.native_predecessor_sha256);
            if (graph_site_preflight_valid) {
                copy_c_string(receipt.sampler_sha256, last_graph_site_preflight.sampler_sha256);
            }
        }
        receipt.owner_generation = graph_site_candidate.candidate.owner_generation;
        receipt.method_generation = graph_site_candidate.candidate.method_generation;
    }
    void graph_site_candidate_clear_stage_trace() {
        if (graph_site_candidate_result_valid) {
            return;
        }
        graph_site_candidate_result.stage_events = nullptr;
        graph_site_candidate_result.stage_event_count = 0;
        graph_site_candidate_stage_trace.clear();
    }

    void graph_site_candidate_refuse(const char * reason) {
        graph_site_candidate_result = {};
        graph_site_candidate_actual_expert_ids.clear();
        graph_site_receipt_binding(graph_site_candidate_result);
        graph_site_candidate_result.attempted = true;
        graph_site_candidate_result.admitted = false;
        copy_c_string(graph_site_candidate_result.refusal,
            reason == nullptr ? "graph_site_candidate_refused" : reason);
        graph_site_candidate_result.stage_events =
            graph_site_candidate_stage_trace.empty()
                ? nullptr
                : graph_site_candidate_stage_trace.data();
        graph_site_candidate_result.stage_event_count =
            graph_site_candidate_stage_trace.size();
        graph_site_candidate_result_valid = true;
    }
    void graph_site_candidate_record_stage(llama_cassi_service_kind kind, int32_t layer) {
        if (!graph_site_candidate.valid) {
            return;
        }
        uint32_t event_kind = 0;
        switch (kind) {
            case LLAMA_CASSI_EMBED:
                event_kind = LLAMA_CASSI_GRAPH_SITE_STAGE_EMBED;
                if (layer != -1) {
                    fail("apprentice_graph_site_stage_layer_invalid");
                }
                break;
            case LLAMA_CASSI_HEAD:
                event_kind = LLAMA_CASSI_GRAPH_SITE_STAGE_HEAD;
                if (layer != -1) {
                    fail("apprentice_graph_site_stage_layer_invalid");
                }
                break;
            case LLAMA_CASSI_ATTENTION:
                event_kind = LLAMA_CASSI_GRAPH_SITE_STAGE_ATTENTION;
                if (layer < 0 || static_cast<uint32_t>(layer) >= metadata.layers) {
                    fail("apprentice_graph_site_stage_layer_invalid");
                }
                break;
            case LLAMA_CASSI_FFN:
                event_kind = LLAMA_CASSI_GRAPH_SITE_STAGE_FFN;
                if (layer < 0 || static_cast<uint32_t>(layer) >= metadata.layers) {
                    fail("apprentice_graph_site_stage_layer_invalid");
                }
                break;
            default:
                fail("apprentice_graph_site_stage_kind_invalid");
        }
        if (graph_site_candidate_stage_trace.size() >= GRAPH_SITE_STAGE_EVENT_LIMIT) {
            fail("apprentice_graph_site_stage_trace_overflow");
        }
        graph_site_candidate_stage_trace.push_back({event_kind, layer});
    }


    void capture_graph_site_candidate_result(
            const llama_cassi_graph_site_candidate_result & native_result) {
        graph_site_candidate_result = {};
        graph_site_receipt_binding(graph_site_candidate_result);
        const bool candidate_binding_matches = !native_result.admitted ||
            (valid_graph_site_sha256(native_result.invocation_sha256) &&
             valid_graph_site_sha256(native_result.predecessor_sha256) &&
             valid_graph_site_sha256(native_result.candidate_sha256) &&
             std::strcmp(
                 native_result.invocation_sha256,
                 graph_site_candidate.invocation_sha256.c_str()) == 0 &&
             std::strcmp(
                 native_result.predecessor_sha256,
                 graph_site_candidate.predecessor_sha256.c_str()) == 0 &&
             std::strcmp(
                 native_result.candidate_sha256,
                 graph_site_candidate.candidate_sha256.c_str()) == 0);
        const bool request_sha_matches = !native_result.admitted ||
            (native_result.request_sha256_pending ==
                    graph_site_candidate.candidate.request_sha256_pending &&
             (graph_site_candidate.candidate.request_sha256_pending
                ? (valid_graph_site_sha256(native_result.input_sha256) &&
                   valid_graph_site_sha256(native_result.request_sha256) &&
                   std::strcmp(native_result.input_sha256, native_result.request_sha256) == 0)
                : (valid_graph_site_sha256(graph_site_candidate.candidate.request_sha256) &&
                   std::strcmp(
                       graph_site_candidate.candidate.request_sha256,
                       native_result.request_sha256) == 0)));
        const size_t actual_expert_count = native_result.actual_expert_ids_count;
        bool actual_expert_route_valid =
            actual_expert_count <= 4096 &&
            (actual_expert_count == 0 || native_result.actual_expert_ids != nullptr);
        const bool actual_stage_trace_valid = !native_result.admitted ||
            (!graph_site_candidate_stage_trace.empty() &&
             graph_site_candidate_stage_trace.size() <= GRAPH_SITE_STAGE_EVENT_LIMIT);
        for (size_t index = 0; actual_expert_route_valid && index < actual_expert_count; ++index) {
            actual_expert_route_valid = native_result.actual_expert_ids[index] >= 0;
        }
        bool actual_expert_route_matches = true;
        if (actual_expert_route_valid &&
                graph_site_candidate.candidate.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS &&
                native_result.admitted) {
            actual_expert_route_matches =
                actual_expert_count == graph_site_candidate.expected_expert_ids.size();
            for (size_t index = 0;
                    actual_expert_route_matches && index < actual_expert_count;
                    ++index) {
                actual_expert_route_matches =
                    native_result.actual_expert_ids[index] ==
                    graph_site_candidate.expected_expert_ids[index];
            }
        } else if (actual_expert_route_valid &&
                (graph_site_candidate.candidate.kind == LLAMA_CASSI_GRAPH_SITE_RECURRENT ||
                 graph_site_candidate.candidate.kind == LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY ||
                 graph_site_candidate.candidate.kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE)) {
            actual_expert_route_valid = actual_expert_count == 0;
        }
        graph_site_candidate_actual_expert_ids.clear();
        if (actual_expert_route_valid && actual_expert_count != 0) {
            graph_site_candidate_actual_expert_ids.assign(
                native_result.actual_expert_ids,
                native_result.actual_expert_ids + actual_expert_count);
        }
        const bool actual_expert_receipt_valid =
            actual_expert_route_valid && actual_expert_route_matches;
        graph_site_candidate_result.admitted =
            native_result.admitted && candidate_binding_matches && request_sha_matches &&
            actual_expert_receipt_valid && actual_stage_trace_valid;
        graph_site_candidate_result.attempted = native_result.attempted;
        graph_site_candidate_result.operators_omitted =
            graph_site_candidate_result.admitted ? native_result.operators_omitted : 0;
        graph_site_candidate_result.weights_omitted =
            graph_site_candidate_result.admitted ? native_result.weights_omitted : 0;
        graph_site_candidate_result.weight_bytes_omitted =
            graph_site_candidate_result.admitted ? native_result.weight_bytes_omitted : 0;
        graph_site_candidate_result.transfer_bytes_omitted =
            graph_site_candidate_result.admitted ? native_result.transfer_bytes_omitted : 0;
        copy_c_string(graph_site_candidate_result.refusal,
            !candidate_binding_matches ? "graph_site_candidate_receipt_mismatch" :
            !request_sha_matches ? "graph_site_request_sha256_mismatch" :
            !actual_expert_route_valid ? "graph_site_actual_expert_route_invalid" :
            !actual_expert_route_matches ? "graph_site_actual_expert_route_mismatch" :
            !actual_stage_trace_valid ? "graph_site_stage_trace_missing" :
                native_result.refusal);
        copy_c_string(graph_site_candidate_result.input_sha256, native_result.input_sha256);
        copy_c_string(graph_site_candidate_result.output_sha256, native_result.output_sha256);
        copy_c_string(graph_site_candidate_result.request_sha256, native_result.request_sha256);
        copy_c_string(graph_site_candidate_result.invocation_sha256, native_result.invocation_sha256);
        copy_c_string(graph_site_candidate_result.candidate_sha256, native_result.candidate_sha256);
        copy_c_string(graph_site_candidate_result.predecessor_sha256, native_result.predecessor_sha256);
        copy_c_string(graph_site_candidate_result.successor_sha256, native_result.successor_sha256);
        copy_c_string(graph_site_candidate_result.successor_state_json, native_result.successor_state_json);
        copy_c_string(graph_site_candidate_result.native_successor_sha256,
            native_result.native_successor_sha256);
        graph_site_candidate_result.actual_expert_ids =
            graph_site_candidate_actual_expert_ids.empty()
                ? nullptr
                : graph_site_candidate_actual_expert_ids.data();
        graph_site_candidate_result.actual_expert_ids_count =
            graph_site_candidate_actual_expert_ids.size();
        graph_site_candidate_result.stage_events =
            graph_site_candidate_stage_trace.empty()
                ? nullptr
                : graph_site_candidate_stage_trace.data();
        graph_site_candidate_result.stage_event_count =
            graph_site_candidate_stage_trace.size();
        graph_site_candidate_result_valid = native_result.attempted;
    }

    bool graph_site_candidate_set(
            const llama_cassi_graph_site_candidate * candidate,
            const llama_cassi_graph_site_candidate_guard * guard) {
        graph_site_candidate_result = {};
        graph_site_candidate_result_valid = false;
        graph_site_candidate_clear_stage_trace();
        const auto reject = [&](const char * reason) {
            graph_site_candidate_refuse(reason);
            return false;
        };
        if (candidate == nullptr || guard == nullptr) {
            return reject("graph_site_candidate_and_guard_required");
        }
        if (graph_site_candidate.valid) {
            return reject("graph_site_candidate_already_pending");
        }
        if (!exact_pipeline() || state != session_state::ready || service_token_active ||
                !graph_site_preflight_matches_native() ||
                !graph_site_preflight_matches_effective_sampler()) {
            return reject("native_graph_site_preflight_stale");
        }
        if (guard->verb != LLAMA_CASSI_GRAPH_SITE_REPLACE ||
                !bounded_graph_site_text(guard->candidate_id, 64) ||
                !valid_graph_site_sha256(guard->native_preflight_sha256) ||
                !valid_graph_site_sha256(guard->native_predecessor_sha256) ||
                !valid_graph_site_sha256(guard->owner_snapshot_sha256) ||
                !valid_graph_site_sha256(guard->field_epoch_sha256) ||
                std::strcmp(guard->native_preflight_sha256,
                    last_graph_site_preflight.native_preflight_sha256) != 0 ||
                std::strcmp(guard->native_predecessor_sha256,
                    last_graph_site_preflight.predecessor_sha256) != 0 ||
                std::strcmp(guard->field_epoch_sha256,
                    last_graph_site_preflight.native_field_epoch_sha256) != 0) {
            return reject("graph_site_guard_stale_or_invalid");
        }
        if (!bounded_graph_site_text(candidate->sequence_id, 127) ||
                !valid_graph_site_sha256(candidate->source_sha256) ||
                !valid_graph_site_sha256(candidate->predecessor_sha256) ||
                (candidate->request_sha256_pending
                    ? (candidate->request_sha256 == nullptr || candidate->request_sha256[0] != '\0')
                    : !valid_graph_site_sha256(candidate->request_sha256)) ||
                !valid_graph_site_sha256(candidate->invocation_sha256) ||
                !valid_graph_site_sha256(candidate->candidate_sha256) ||
                std::strcmp(candidate->sequence_id, last_graph_site_preflight.sequence_id) != 0 ||
                std::strcmp(candidate->source_sha256, last_graph_site_preflight.source_sha256) != 0 ||
                std::strcmp(candidate->predecessor_sha256, guard->owner_snapshot_sha256) != 0 ||
                candidate->seq_id != last_graph_site_preflight.native_seq_id ||
                candidate->position != last_graph_site_preflight.next_position ||
                candidate->owner_generation == 0 ||
                (candidate->kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE
                    ? candidate->layer != -1
                    : candidate->layer < 0)) {
            return reject("graph_site_candidate_identity_mismatch");
        }
        if (!bounded_graph_site_text(candidate->architecture, 64) ||
                std::strcmp(candidate->architecture, "qwen35moe") != 0 ||
                !bounded_graph_site_text(candidate->backend, 64) ||
                std::find(native_backends.begin(), native_backends.end(), candidate->backend) ==
                    native_backends.end() ||
                !bounded_graph_site_text(candidate->input_tensor, 63) ||
                !bounded_graph_site_text(candidate->output_tensor, 63) ||
                !bounded_graph_site_text(candidate->tensor_dtype, 8) ||
                !bounded_graph_site_text(candidate->stage, 63) ||
                !bounded_graph_site_text(candidate->site, 63) ||
                !bounded_graph_site_text(candidate->specialist, 63) ||
                !bounded_graph_site_text(candidate->intervention_order, 127) ||
                !bounded_graph_site_text(candidate->dependencies_json, 1023) ||
                !bounded_graph_site_text(candidate->method_key, 128) ||
                std::strcmp(candidate->tensor_dtype, "f32") != 0 ||
                std::strcmp(candidate->method_key, "cassifi.graph-site-low-rank-affine.v1") != 0) {
            return reject("graph_site_candidate_metadata_invalid");
        }
        const llama_cassi_graph_site_descriptor * descriptor = nullptr;
        for (const llama_cassi_graph_site_descriptor & site : last_graph_site_sites) {
            if (site.kind == static_cast<uint32_t>(candidate->kind) &&
                    site.layer == candidate->layer) {
                descriptor = &site;
                break;
            }
        }
        if (descriptor == nullptr || !descriptor->supported ||
                candidate->input_width != descriptor->input_width ||
                candidate->output_width != descriptor->output_width ||
                std::strcmp(candidate->stage, descriptor->stage) != 0 ||
                std::strcmp(candidate->site, descriptor->site) != 0 ||
                std::strcmp(candidate->specialist, descriptor->specialist) != 0 ||
                std::strcmp(candidate->input_tensor, descriptor->input_tensor) != 0 ||
                std::strcmp(candidate->output_tensor, descriptor->output_tensor) != 0 ||
                std::strcmp(candidate->dependencies_json, descriptor->dependencies_json) != 0) {
            return reject("graph_site_candidate_site_mismatch");
        }
        if (candidate->rank == 0 || candidate->rank > 16 ||
                candidate->input_width == 0 || candidate->output_width == 0 ||
                candidate->a == nullptr || candidate->b == nullptr || candidate->bias == nullptr ||
                candidate->a_count != static_cast<size_t>(candidate->input_width) * candidate->rank ||
                candidate->b_count != static_cast<size_t>(candidate->rank) * candidate->output_width ||
                candidate->bias_count != candidate->output_width ||
                !std::isfinite(guard->input_support_radius) || guard->input_support_radius < 0.0f ||
                !std::isfinite(guard->input_support_anchor_norm) ||
                guard->input_support_anchor_norm < 0.0f) {
            return reject("graph_site_candidate_method_or_support_invalid");
        }
        retained_graph_site_candidate staged;
        staged.candidate = *candidate;
        staged.guard = *guard;
        staged.candidate_id = guard->candidate_id;
        staged.sequence_id = candidate->sequence_id;
        staged.source_sha256 = candidate->source_sha256;
        staged.architecture = candidate->architecture;
        staged.backend = candidate->backend;
        staged.input_tensor = candidate->input_tensor;
        staged.output_tensor = candidate->output_tensor;
        staged.tensor_dtype = candidate->tensor_dtype;
        staged.stage = candidate->stage;
        staged.site = candidate->site;
        staged.specialist = candidate->specialist;
        staged.predecessor_sha256 = candidate->predecessor_sha256;
        staged.request_sha256 = candidate->request_sha256;
        staged.invocation_sha256 = candidate->invocation_sha256;
        staged.candidate_sha256 = candidate->candidate_sha256;
        staged.intervention_order = candidate->intervention_order;
        staged.dependencies_json = candidate->dependencies_json;
        staged.method_key = candidate->method_key;
        staged.native_preflight_sha256 = guard->native_preflight_sha256;
        staged.native_predecessor_sha256 = guard->native_predecessor_sha256;
        staged.owner_snapshot_sha256 = guard->owner_snapshot_sha256;
        staged.field_epoch_sha256 = guard->field_epoch_sha256;
        staged.a.assign(candidate->a, candidate->a + candidate->a_count);
        staged.b.assign(candidate->b, candidate->b + candidate->b_count);
        staged.bias.assign(candidate->bias, candidate->bias + candidate->bias_count);
        if (guard->input_support_anchor_count != 0) {
            if (guard->input_support_anchor == nullptr ||
                    guard->input_support_anchor_count != candidate->input_width) {
                return reject("graph_site_input_support_anchor_invalid");
            }
            staged.input_support_anchor.assign(
                guard->input_support_anchor,
                guard->input_support_anchor + guard->input_support_anchor_count);
        } else if (candidate->rank == 1 &&
                candidate->kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS &&
                std::isfinite(guard->input_support_anchor_norm)) {
            staged.input_support_anchor.resize(candidate->input_width);
            for (size_t i = 0; i < staged.input_support_anchor.size(); ++i) {
                staged.input_support_anchor[i] =
                    staged.a[i] * guard->input_support_anchor_norm;
            }
        } else {
            return reject("graph_site_input_support_anchor_required");
        }
        if (candidate->kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
            if (guard->expected_expert_ids == nullptr ||
                    guard->expected_expert_ids_count != model->hparams.n_expert_used) {
                return reject("graph_site_expected_expert_route_required");
            }
            staged.expected_expert_ids.assign(
                guard->expected_expert_ids,
                guard->expected_expert_ids + guard->expected_expert_ids_count);
            std::vector<uint8_t> seen(model->hparams.n_expert, 0);
            for (int32_t expert : staged.expected_expert_ids) {
                if (expert < 0 || static_cast<uint32_t>(expert) >= model->hparams.n_expert ||
                        seen[expert] != 0) {
                    return reject("graph_site_expected_expert_route_invalid");
                }
                seen[expert] = 1;
            }
        } else if (candidate->kind == LLAMA_CASSI_GRAPH_SITE_RECURRENT ||
                candidate->kind == LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY ||
                candidate->kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE) {
            if (guard->expected_expert_ids_count != 0 || guard->expected_expert_ids != nullptr) {
                return reject("unexpected_graph_site_expert_route");
            }
        } else {
            return reject("graph_site_kind_unsupported");
        }
        if (metadata.layers > (GRAPH_SITE_STAGE_EVENT_LIMIT - 2) / 2) {
            return reject("graph_site_stage_trace_capacity_exceeded");
        }
        graph_site_candidate_stage_trace.reserve(
            static_cast<size_t>(metadata.layers) * 2U + 2U);
        staged.rebind();
        graph_site_candidate = std::move(staged);
        graph_site_candidate_result = {};
        graph_site_candidate_actual_expert_ids.clear();
        graph_site_candidate_result_valid = false;
        graph_site_candidate_observed = false;
        if (!llama_cassi_graph_site_candidate_set(service.get(), &graph_site_candidate.candidate)) {
            llama_cassi_graph_site_candidate_result native_result = {};
            if (llama_cassi_graph_site_candidate_get_result(service.get(), &native_result) &&
                    native_result.attempted) {
                capture_graph_site_candidate_result(native_result);
            } else {
                graph_site_candidate_refuse("graph_site_native_candidate_rejected");
            }
            llama_cassi_graph_site_candidate_clear(
                service.get(), graph_site_candidate.sequence_id.c_str(),
                graph_site_candidate.candidate.owner_generation);
            graph_site_candidate.valid = false;
            return false;
        }
        graph_site_candidate.valid = true;
        return true;
    }

    void graph_site_candidate_clear(const char * candidate_id) {
        if (candidate_id == nullptr || !graph_site_candidate.valid ||
                graph_site_candidate.candidate_id != candidate_id) {
            return;
        }
        if (service != nullptr) {
            llama_cassi_graph_site_candidate_clear(
                service.get(), graph_site_candidate.sequence_id.c_str(),
                graph_site_candidate.candidate.owner_generation);
        }
        graph_site_candidate.valid = false;
        graph_site_candidate_observed = false;
        graph_site_preflight_valid = false;
        graph_site_candidate_clear_stage_trace();
    }

    bool graph_site_candidate_get_result(
            llama_cassi_graph_site_candidate_receipt * result) const {
        if (result == nullptr || !graph_site_candidate_result_valid) {
            return false;
        }
        *result = graph_site_candidate_result;
        return true;
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
                if (graph_site_candidate.valid) {
                    llama_cassi_graph_site_candidate_result native_result = {};
                    if (!llama_cassi_graph_site_candidate_get_result(service.get(), &native_result) ||
                            !native_result.attempted || native_result.admitted) {
                        service.reset();
                        service_token_active = false;
                        service_abandoned = true;
                        graph_site_candidate.valid = false;
                        graph_site_candidate_refuse("native_candidate_rollback_receipt_unavailable");
                        fail("apprentice_graph_site_candidate_receipt_unavailable");
                    }
                    capture_graph_site_candidate_result(native_result);
                    graph_site_candidate_observed = true;
                    llama_cassi_graph_site_candidate_clear(
                        service.get(), graph_site_candidate.sequence_id.c_str(),
                        graph_site_candidate.candidate.owner_generation);
                    graph_site_candidate.valid = false;
                    graph_site_preflight_valid = false;
                    throw graph_site_retry_token{};
                }
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
        if (graph_site_candidate.valid) {
            llama_cassi_graph_site_candidate_result native_result = {};
            if (llama_cassi_graph_site_candidate_get_result(service.get(), &native_result) &&
                    native_result.attempted) {
                capture_graph_site_candidate_result(native_result);
                graph_site_candidate_observed = true;
                if (!graph_site_candidate_result.admitted) {
                    if (graph_site_candidate_result.refusal[0] == '\0') {
                        copy_c_string(
                            graph_site_candidate_result.refusal,
                            "graph_site_candidate_refused");
                    }
                    if (service->cassi_cancel_token() != 0) {
                        service.reset();
                        service_token_active = false;
                        service_abandoned = true;
                        graph_site_candidate.valid = false;
                        fail("apprentice_graph_site_candidate_rollback_failed");
                    }
                    service_token_active = false;
                    service_epoch++;
                    llama_cassi_graph_site_candidate_clear(
                        service.get(), graph_site_candidate.sequence_id.c_str(),
                        graph_site_candidate.candidate.owner_generation);
                    graph_site_candidate.valid = false;
                    graph_site_preflight_valid = false;
                    throw graph_site_retry_token{};
                }
            }
        }
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
        if (exact_pipeline()) {
            stats.native_exact_stages++;
            if (kind == LLAMA_CASSI_ATTENTION) {
                stats.native_exact_attention_stages++;
            } else if (kind == LLAMA_CASSI_FFN) {
                stats.native_exact_ffn_stages++;
            }
            ggml_tensor * output = call_native_service(kind, layer, input, token, position);
            graph_site_candidate_record_stage(kind, layer);
            return output;
        }
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

    llama_token sample_exact_logit_row(
            const std::vector<float> & logits,
            const llama_cassi_sampler_params & row_sampler) {
        if (!sampler_tuple_valid(row_sampler)) {
            fail("apprentice_sampler_invalid");
        }
        if (row_sampler.mode == LLAMA_CASSI_SAMPLER_GREEDY) {
            validate_exact_logits(logits.data(), logits.size());
            return static_cast<llama_token>(
                std::distance(logits.begin(), std::max_element(logits.begin(), logits.end())));
        }
        std::vector<uint32_t> candidates;
        std::vector<double> weights;
        double total = 0.0;
        exact_categorical_distribution(
            logits.data(), logits.size(), row_sampler, candidates, weights, total);
        stats.native_sampler_draws++;
        const double target = row_sampler.draw * total;
        double cumulative = 0.0;
        for (size_t index = 0; index < candidates.size(); ++index) {
            cumulative += weights[index];
            if (target < cumulative) {
                return static_cast<llama_token>(candidates[index]);
            }
        }
        return static_cast<llama_token>(candidates.back());
    }

    llama_token select_exact_logits(ggml_tensor * logits_tensor) {
        const int64_t logits_count = ggml_nelements(logits_tensor);
        if (logits_count != metadata.vocabulary_size) {
            throw std::runtime_error(
                "apprentice_native_head_shape_invalid:expected=" +
                std::to_string(metadata.vocabulary_size) +
                ":actual=" + std::to_string(logits_count));
        }
        std::vector<float> logits(metadata.vocabulary_size);
        ggml_backend_tensor_get(logits_tensor, logits.data(), 0, logits.size() * sizeof(float));
        stats.native_logits_reads++;
        return sample_exact_logit_row(logits, effective_sampler());
    }
    std::vector<float> exact_head_logits(ggml_tensor * input, llama_token token, size_t position) {
        stats.native_exact_stages++;
        ggml_tensor * logits_tensor = call_native_service(LLAMA_CASSI_HEAD, -1, input, token, position);
        const int64_t logits_count = ggml_nelements(logits_tensor);
        if (logits_count != metadata.vocabulary_size) {
            throw std::runtime_error(
                "apprentice_native_head_shape_invalid:expected=" +
                std::to_string(metadata.vocabulary_size) +
                ":actual=" + std::to_string(logits_count));
        }
        std::vector<float> logits(metadata.vocabulary_size);
        ggml_backend_tensor_get(logits_tensor, logits.data(), 0, logits.size() * sizeof(float));
        stats.native_logits_reads++;
        graph_site_candidate_record_stage(LLAMA_CASSI_HEAD, -1);
        return logits;
    }

    llama_cassi_token resolve_exact_head(ggml_tensor * input, llama_token token, size_t position) {
        stats.native_exact_stages++;
        ggml_tensor * logits = call_native_service(LLAMA_CASSI_HEAD, -1, input, token, position);
        llama_cassi_token result = {};
        result.token = select_exact_logits(logits);
        graph_site_candidate_record_stage(LLAMA_CASSI_HEAD, -1);
        result.decision_source = 2;
        result.native_dependency = 1;
        result.readout_kind = 3;
        return result;
    }

    llama_cassi_token resolve_head(ggml_tensor * input, llama_token token, size_t position) {
        if (exact_pipeline()) {
            return resolve_exact_head(input, token, position);
        }
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

    void ensure_group_context() {
        if (service_abandoned || !fully_loaded) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (service) {
            return;
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
        stats.native_context_creations++;
        refresh_cache_gauges();
    }

    void group_validate(bool require_exact_pipeline = false) const {
        if (group_host.capacity == 0) {
            fail("apprentice_group_requires_rows");
        }
        if (require_exact_pipeline && !exact_pipeline()) {
            fail("apprentice_exact_pipeline_requires_native_model");
        }
    }

    // One fused stage application for the whole active round; returns the row
    // tensor [out_width, n_rows] copied into `out` (row-major host layout).
    void group_apply_stage(
            llama_cassi_service_kind kind,
            int32_t layer,
            llm_cassi_service_config & config,
            uint32_t out_width,
            float * out,
            uint32_t out_capacity) {
        const uint32_t row_count = static_cast<uint32_t>(group_host.rows.size());
        if (service == nullptr) {
            fail("apprentice_group_stage_without_open");
        }
        config.kind = kind;
        config.layer = layer;
        config.request_epoch = service_epoch;
        config.n_rows = row_count;
        config.batch_tokens = group_host.row_tokens.data();
        config.batch_pos = group_host.row_positions.data();
        config.batch_seq_ids = group_host.row_seq_ids.data();
        config.stage_width = 0;
        const auto started = std::chrono::steady_clock::now();
        ggml_tensor * result = service->cassi_service(config);
        stats.native_service_ms += elapsed_ms(started);
        if (result == nullptr) {
            group_host.state = llama_cassi_group_host::phase::idle;
            service.reset();
            fail("apprentice_native_service_failed");
        }
        stats.native_service_calls++;
        if (ggml_nelements(result) != static_cast<int64_t>(out_width) * row_count) {
            group_host.state = llama_cassi_group_host::phase::idle;
            service.reset();
            fail("apprentice_group_service_shape_invalid");
        }
        stats.native_exact_stages++;
        if (out == nullptr ||
            out_capacity < out_width * row_count) {
            group_host.state = llama_cassi_group_host::phase::idle;
            service.reset();
            fail("apprentice_group_output_capacity_invalid");
        }
        ggml_backend_tensor_get(result, out, 0, out_width * row_count * sizeof(float));
        const uint32_t page_index = service_page(kind, layer);
        const uint64_t graph_nodes = static_cast<uint64_t>(service->cassi_service_graph_nodes());
        const uint64_t logical_weight_bytes = service->cassi_last_graph_weight_bytes();
        stats.native_ggml_nodes_executed += graph_nodes;
        stats.logical_weight_bytes += logical_weight_bytes;
        service_stats[page_index].computed++;
        service_stats[page_index].logical_weight_bytes += logical_weight_bytes;
        service_node_baseline[page_index] = graph_nodes;
        service_weight_baseline[page_index] = logical_weight_bytes;
        if (kind == LLAMA_CASSI_HEAD) {
            stats.native_output_rows_computed += metadata.vocabulary_size;
            stats.native_exact_head_groups++;
        } else {
            stats.native_output_rows_computed += row_count;
        }
        if (kind == LLAMA_CASSI_ATTENTION) {
            stats.native_exact_attention_stages += 1;
        } else if (kind == LLAMA_CASSI_FFN) {
            stats.native_exact_ffn_stages += 1;
        }
    }

    llama_cassi_group_state group_state_get() const {
        using phase = llama_cassi_group_host::phase;
        if (group_host.state == phase::sampled) {
            return LLAMA_CASSI_GROUP_SAMPLED;
        }
        if (group_host.state == phase::staged) {
            return LLAMA_CASSI_GROUP_STAGED;
        }
        if (state == session_state::error || state == session_state::cancelled) {
            return LLAMA_CASSI_GROUP_FAILED;
        }
        return LLAMA_CASSI_GROUP_IDLE;
    }

    uint32_t group_row_count() const {
        return static_cast<uint32_t>(group_host.rows.size());
    }

    int32_t group_open(
            const llama_cassi_group_row * rows,
            uint32_t n_rows,
            float * embed_out,
            uint32_t embed_width,
            uint32_t embed_capacity) {
        check_cancelled();
        group_validate(true);
        if (group_host.state != llama_cassi_group_host::phase::idle) {
            fail("apprentice_group_stage_active");
        }
        if (rows == nullptr || n_rows == 0 || n_rows > group_host.capacity) {
            fail("apprentice_group_rows_invalid");
        }
        if (!fully_loaded) {
            fail("apprentice_native_service_prefix_unavailable");
        }
        if (embed_width != 0 && embed_width != metadata.embedding_width) {
            fail("apprentice_group_output_width_invalid");
        }
        if (embed_out == nullptr || embed_capacity < metadata.embedding_width * n_rows) {
            fail("apprentice_group_output_capacity_invalid");
        }
        ensure_group_context();

        // Per-sequence cursors must be untouched: rows replay only at the fence.
        for (uint32_t row = 0; row < n_rows; ++row) {
            const llama_pos cursor = service->cassi_service_next_pos_seq(static_cast<llama_seq_id>(row));
            if (cursor < 0 || rows[row].pos != cursor) {
                fail("apprentice_group_row_position_mismatch");
            }
            const llama_token token = rows[row].token;
            if (token < 0 || static_cast<uint32_t>(token) >= metadata.vocabulary_size) {
                fail("apprentice_token_invalid");
            }
        }

        group_host.rows.assign(rows, rows + n_rows);
        group_host.row_tokens.resize(n_rows);
        group_host.row_positions.resize(n_rows);
        group_host.row_seq_counts.assign(n_rows, 1);
        group_host.row_seq_ids.resize(n_rows);
        group_host.row_seq_ptrs.resize(n_rows);
        group_host.row_logits.assign(n_rows, 1);
        for (uint32_t row = 0; row < n_rows; ++row) {
            group_host.row_tokens[row] = rows[row].token;
            group_host.row_positions[row] = rows[row].pos;
            group_host.row_seq_ids[row] = static_cast<llama_seq_id>(row);
            group_host.row_seq_ptrs[row] = &group_host.row_seq_ids[row];
        }

        llama_batch batch = {};
        batch.n_tokens = static_cast<int32_t>(n_rows);
        batch.token = group_host.row_tokens.data();
        batch.pos = group_host.row_positions.data();
        batch.n_seq_id = group_host.row_seq_counts.data();
        batch.seq_id = group_host.row_seq_ptrs.data();
        batch.logits = group_host.row_logits.data();
        if (service->cassi_begin_tokens(batch, n_rows) != 0) {
            group_host.rows.clear();
            group_host.row_tokens.clear();
            group_host.row_positions.clear();
            fail("apprentice_group_open_failed");
        }
        service_epoch++;

        llm_cassi_service_config config;
        group_apply_stage(LLAMA_CASSI_EMBED, -1, config, metadata.embedding_width, embed_out,
            embed_capacity);
        group_host.state = llama_cassi_group_host::phase::staged;
        return 0;
    }

    int32_t group_sample(const float * residual, uint32_t width, llama_token * tokens_out, uint32_t n_rows) {
        check_cancelled();
        group_validate(true);
        const uint32_t row_count = static_cast<uint32_t>(group_host.rows.size());
        if (group_host.state != llama_cassi_group_host::phase::staged || row_count != n_rows) {
            fail("apprentice_group_sample_transition_invalid");
        }
        if (tokens_out == nullptr || residual == nullptr || width != metadata.embedding_width) {
            fail("apprentice_group_sample_input_invalid");
        }
        std::vector<float> logits(static_cast<size_t>(metadata.vocabulary_size) * n_rows);
        llm_cassi_service_config config{};
        config.input = field->load_matrix(residual, static_cast<size_t>(width) * n_rows);
        group_apply_stage(LLAMA_CASSI_HEAD, -1, config, metadata.vocabulary_size,
            logits.data(), static_cast<uint32_t>(logits.size()));
        stats.native_logits_reads++;
        for (uint32_t row = 0; row < n_rows; ++row) {
            const float * row_logits = logits.data() + static_cast<size_t>(row) * metadata.vocabulary_size;
            std::vector<float> slice(row_logits, row_logits + metadata.vocabulary_size);
            tokens_out[row] = sample_exact_logit_row(slice, group_host.rows[row].sampler);
            // Exact pipeline readout identity, identical to the single-row path.
            stats.native_exact_tokens++;
        }
        group_host.state = llama_cassi_group_host::phase::sampled;
        return 0;
    }

    int32_t group_stage(
            llama_cassi_service_kind kind,
            int32_t layer,
            const float * input,
            uint32_t width,
            float * out,
            uint32_t out_width,
            uint32_t out_capacity) {
        check_cancelled();
        group_validate(true);
        const uint32_t row_count = static_cast<uint32_t>(group_host.rows.size());
        if (group_host.state != llama_cassi_group_host::phase::staged) {
            fail("apprentice_group_stage_transition_invalid");
        }
        if (kind != LLAMA_CASSI_ATTENTION && kind != LLAMA_CASSI_FFN) {
            fail("apprentice_group_stage_kind_invalid");
        }
        if (layer < 0 || static_cast<uint32_t>(layer) >= metadata.layers) {
            fail("apprentice_group_stage_layer_invalid");
        }
        if (input == nullptr || width != metadata.embedding_width) {
            fail("apprentice_group_stage_input_invalid");
        }
        if (out == nullptr || out_capacity < metadata.embedding_width * row_count ||
                (out_width != 0 && out_width != metadata.embedding_width)) {
            fail("apprentice_group_output_capacity_invalid");
        }
        llm_cassi_service_config config;
        config.input = field->load_matrix(
            input, static_cast<size_t>(metadata.embedding_width) * row_count);
        group_apply_stage(kind, layer, config, metadata.embedding_width, out, out_capacity);
        return 0;
    }

    int32_t group_commit() {
        check_cancelled();
        group_validate(true);
        const uint32_t row_count = static_cast<uint32_t>(group_host.rows.size());
        if (group_host.state != llama_cassi_group_host::phase::sampled) {
            fail("apprentice_group_commit_transition_invalid");
        }
        if (service == nullptr || service->cassi_end_tokens() != 0) {
            service.reset();
            group_host.state = llama_cassi_group_host::phase::idle;
            group_host.rows.clear();
            group_host.row_tokens.clear();
            group_host.row_positions.clear();
            fail("apprentice_group_commit_failed");
        }
        stats.committed_tokens += row_count;
        group_host.state = llama_cassi_group_host::phase::idle;
        group_host.rows.clear();
        group_host.row_tokens.clear();
        group_host.row_positions.clear();
        return 0;
    }

    int32_t group_cancel() {
        group_validate(true);
        if (group_host.state == llama_cassi_group_host::phase::idle) {
            fail("apprentice_group_stage_inactive");
        }
        const int32_t result = service != nullptr && service->cassi_cancel_tokens() == 0
            ? 0
            : -1;
        // Fence: no per-sequence cursor advanced; the epoch bump invalidates
        // every in-flight stage config so the round replays from group_open.
        service_epoch++;
        group_host.state = llama_cassi_group_host::phase::idle;
        group_host.rows.clear();
        group_host.row_tokens.clear();
        group_host.row_positions.clear();
        return result;
    }

    // Group churn: reset a seat's native sequence for a rejoining member.
    // Only valid at a round boundary (idle); no per-sequence cursor may be
    // in flight, matching the group_cancel fence discipline.
    int32_t group_row_reset(uint32_t row) {
        group_validate(true);
        if (group_host.state != llama_cassi_group_host::phase::idle) {
            fail("apprentice_group_stage_active");
        }
        if (row >= group_host.capacity) {
            fail("apprentice_group_rows_invalid");
        }
        if (service == nullptr) {
            fail("apprentice_group_stage_without_open");
        }
        if (service->cassi_group_row_reset(static_cast<llama_seq_id>(row)) != 0) {
            fail("apprentice_group_row_reset_failed");
        }
        return 0;
    }

    llama_cassi_token process_pipeline_token(size_t position, bool emit_head, std::vector<float> * out_exact_logits = nullptr) {
        check_cancelled();
        if (!exact_pipeline()) {
            reconstruct_context(position);
        }
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
                if (out_exact_logits != nullptr) {
                    *out_exact_logits = exact_head_logits(residual, token, position);
                } else {
                    result = resolve_head(residual, token, position);
                }
            }
            if (graph_site_candidate.valid && !graph_site_candidate_observed) {
                if (!service_token_active || service->cassi_cancel_token() != 0) {
                    service.reset();
                    service_token_active = false;
                    service_abandoned = true;
                    graph_site_candidate.valid = false;
                    graph_site_candidate_refuse("graph_site_target_not_observed_rollback_failed");
                    fail("apprentice_graph_site_candidate_rollback_failed");
                }
                service_token_active = false;
                service_epoch++;
                llama_cassi_graph_site_candidate_clear(
                    service.get(), graph_site_candidate.sequence_id.c_str(),
                    graph_site_candidate.candidate.owner_generation);
                graph_site_candidate.valid = false;
                graph_site_preflight_valid = false;
                graph_site_candidate_refuse("graph_site_target_not_observed");
                throw graph_site_retry_token{};
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
            if (graph_site_candidate.valid) {
                const std::string native_successor =
                    digest_hex(native_sequence_predecessor_hash(0, effective_sampler()).data());
                if (!valid_graph_site_sha256(graph_site_candidate.candidate_sha256.c_str()) ||
                        !valid_graph_site_sha256(graph_site_candidate.invocation_sha256.c_str()) ||
                        !llama_cassi_graph_site_candidate_set_native_successor_sha256(
                            service.get(), graph_site_candidate.candidate_sha256.c_str(),
                            graph_site_candidate.invocation_sha256.c_str(), native_successor.c_str())) {
                    graph_site_candidate_refuse("native_successor_receipt_unavailable");
                    service.reset();
                    service_prefix = 0;
                    service_token_active = false;
                    service_abandoned = true;
                    fail("apprentice_graph_site_successor_receipt_failed");
                }
                llama_cassi_graph_site_candidate_result native_result = {};
                if (!llama_cassi_graph_site_candidate_get_result(service.get(), &native_result) ||
                        !native_result.attempted || !native_result.admitted ||
                        std::strcmp(native_result.native_successor_sha256, native_successor.c_str()) != 0) {
                    graph_site_candidate_refuse("native_successor_receipt_mismatch");
                    service.reset();
                    service_prefix = 0;
                    service_token_active = false;
                    service_abandoned = true;
                    fail("apprentice_graph_site_successor_receipt_failed");
                }
                capture_graph_site_candidate_result(native_result);
                graph_site_preflight_valid = false;
            }
            if (!exact_pipeline()) {
                restore_context();
            }
            return result;
        } catch (const graph_site_retry_token &) {
            if (!exact_pipeline()) {
                restore_context();
            }
            return process_pipeline_token(position, emit_head, out_exact_logits);
        } catch (...) {
            if (graph_site_candidate.valid) {
                graph_site_candidate_clear_stage_trace();
            }
            service.reset();
            service_token_active = false;
            if (!exact_pipeline()) {
                restore_context();
            }
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
        if (!exact_pipeline() && public_params.teacher_policy == LLAMA_CASSI_NEVER && !state_loaded) {
            fail("apprentice_checkpoint_missing");
        }
        if (native_params.n_seq_max > 1) {
            // Shared weight-bank group host: single-sequence service with the
            // legacy API family is out of contract on this context.
            fail("apprentice_group_requires_rows");
        }
        for (size_t index = 0; index < n_prompt; ++index) {
            if (prompt[index] < 0 || static_cast<uint32_t>(prompt[index]) >= metadata.vocabulary_size) {
                fail("apprentice_token_invalid");
            }
        }

        cancellation_requested.store(false, std::memory_order_release);
        error.clear();
        graph_site_candidate = {};
        graph_site_candidate_result = {};
        graph_site_candidate_actual_expert_ids.clear();
        graph_site_candidate_result_valid = false;
        graph_site_candidate_clear_stage_trace();
        graph_site_candidate_observed = false;
        graph_site_preflight_valid = false;
        last_graph_site_preflight = {};
        last_graph_site_sites.clear();
        teacher.reset();
        teacher_prefix = 0;
        service.reset();
        service_prefix = 0;
        service_token_active = false;
        service_epoch = 0;
        service_abandoned = false;
        prompt_token_count = n_prompt;
        if (!exact_pipeline()) {
            for (uint32_t layer = 0; layer < metadata.layers; ++layer) {
                attention_owned[layer] = public_params.teacher_policy == LLAMA_CASSI_NEVER ||
                    field->page_mature(service_page(LLAMA_CASSI_ATTENTION, static_cast<int32_t>(layer))) ? 1 : 0;
            }
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
        if (!exact_pipeline()) {
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
        }
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
            graph_site_candidate_clear_stage_trace();
            state = session_state::cancelled;
            return LLAMA_CASSI_CANCELLED;
        }
        if (stats.committed_tokens >= static_cast<uint64_t>(prediction_limit)) {
            state = session_state::done;
            return LLAMA_CASSI_DONE;
        }
        if (exact_pipeline()) {
            pending = {};
            pending.sampler_before = sampler;
            pending.sampler_used = effective_sampler();
            pending.sampler_was_pending = pending_sampler_valid;
            pending.result = run_pipeline();
            if (pending.result.token < 0 ||
                    static_cast<uint32_t>(pending.result.token) >= metadata.vocabulary_size) {
                fail("apprentice_token_invalid");
            }
            *result = pending.result;
            state = session_state::pending;
            return LLAMA_CASSI_TOKEN;
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
        if (exact_pipeline()) {
            token_log.push_back(token);
            stats.committed_tokens++;
            stats.native_exact_tokens++;
            sampler = pending.sampler_used;
            pending_sampler = {};
            pending_sampler_valid = false;
            accepted = std::move(pending);
            pending = {};
            state = stats.committed_tokens >= static_cast<uint64_t>(prediction_limit) ||
                llama_vocab_is_eog(vocab(), token) ? session_state::done : session_state::ready;
            return 0;
        }
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
        if (!exact_pipeline()) {
            restore_pending_field_rollback();
        }
        pending = {};
        clear_pending_admissions();
        teacher.reset();
        teacher_prefix = 0;
        if (service != nullptr && graph_site_candidate.valid) {
            llama_cassi_graph_site_candidate_clear(
                service.get(), graph_site_candidate.sequence_id.c_str(),
                graph_site_candidate.candidate.owner_generation);
        }
        graph_site_candidate.valid = false;
        graph_site_candidate_observed = false;
        graph_site_candidate_clear_stage_trace();
        graph_site_preflight_valid = false;
        service.reset();
        service_prefix = 0;
        service_token_active = false;
        token_log.clear();
        if (!exact_pipeline()) {
            field->reset_context();
        }
        stats.native_cache_bytes_remaining = 0;
        clear_accepted_transaction();
        if (!exact_pipeline()) {
            stats.engram_evictions = field->engram_evictions();
            idle_field_hash_valid = false;
        }
        stats.wall_ms = elapsed_ms(request_started);
        state = session_state::idle;
        return 0;
    }

    bool idle() const {
        return state == session_state::idle;
    }

    bool checkpointable() const {
        return state == session_state::idle || state == session_state::ready ||
            state == session_state::done || state == session_state::pending;
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
        if (exact_pipeline()) {
            info = {};
            info.layers = metadata.layers;
            info.embedding_width = metadata.embedding_width;
            info.vocabulary_size = metadata.vocabulary_size;
            info.context_limit = native_params.n_ctx;
            info.training_context_limit = metadata.context_length;
            std::memcpy(info.model_sha256, model_hash.data(), model_hash.size());
            return;
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
    result.model_sha256 = nullptr;
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

size_t llama_cassi_graph_site_preflight(
        llama_cassi_context * ctx,
        const char * task_id,
        const char * sequence_id,
        llama_cassi_graph_site_preflight_result * out,
        llama_cassi_graph_site_descriptor * sites,
        size_t site_capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    try {
        return ctx->graph_site_preflight(task_id, sequence_id, nullptr, out, sites, site_capacity);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return 0;
    } catch (...) {
        init_error = "native_graph_site_preflight_failed";
        return 0;
    }
}

size_t llama_cassi_graph_site_preflight_with_sampler(
        llama_cassi_context * ctx,
        const char * task_id,
        const char * sequence_id,
        llama_cassi_sampler_params upcoming_sampler,
        llama_cassi_graph_site_preflight_result * out,
        llama_cassi_graph_site_descriptor * sites,
        size_t site_capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return 0;
    }
    try {
        return ctx->graph_site_preflight(
            task_id, sequence_id, &upcoming_sampler, out, sites, site_capacity);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return 0;
    } catch (...) {
        init_error = "native_graph_site_preflight_failed";
        return 0;
    }
}

bool llama_cassi_context_graph_site_candidate_set(
        llama_cassi_context * ctx,
        const llama_cassi_graph_site_candidate * candidate,
        const llama_cassi_graph_site_candidate_guard * guard) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return false;
    }
    try {
        return ctx->graph_site_candidate_set(candidate, guard);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return false;
    } catch (...) {
        init_error = "apprentice_graph_site_candidate_set_failed";
        return false;
    }
}

void llama_cassi_context_graph_site_candidate_clear(
        llama_cassi_context * ctx,
        const char * candidate_id) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return;
    }
    try {
        ctx->graph_site_candidate_clear(candidate_id);
    } catch (const std::exception & exception) {
        init_error = exception.what();
    } catch (...) {
        init_error = "apprentice_graph_site_candidate_clear_failed";
    }
}

bool llama_cassi_context_graph_site_candidate_get_result(
        const llama_cassi_context * ctx,
        llama_cassi_graph_site_candidate_receipt * result) {
    if (ctx == nullptr || result == nullptr) {
        init_error = "apprentice_context_required";
        return false;
    }
    try {
        return ctx->graph_site_candidate_get_result(result);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return false;
    } catch (...) {
        init_error = "apprentice_graph_site_candidate_receipt_unavailable";
        return false;
    }
}

int32_t llama_cassi_context_provisional_state_sha256(
        const llama_cassi_context * ctx, char out_sha256[65]) {
    if (ctx == nullptr || out_sha256 == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->provisional_state_sha256(out_sha256);
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return -1;
    } catch (...) {
        init_error = "apprentice_provisional_state_unavailable";
        return -1;
    }
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
int32_t llama_cassi_sampler_sha256(
        llama_cassi_sampler_params params,
        char out_sha256[65]) {
    if (out_sha256 == nullptr) {
        init_error = "apprentice_sampler_hash_output_required";
        return -1;
    }
    out_sha256[0] = '\0';
    std::array<uint8_t, 32> digest = {};
    if (!canonical_sampler_sha256(params, digest)) {
        init_error = "apprentice_sampler_invalid";
        return -1;
    }
    digest_hex_into(out_sha256, digest.data());
    init_error.clear();
    return 0;
}
int32_t llama_cassi_sample_q_delta(
        const float * logits,
        size_t logits_count,
        llama_token draft_token,
        llama_cassi_sampler_params sampler,
        llama_cassi_q_delta_result * out) {
    if (out != nullptr) {
        *out = {};
    }
    if (out == nullptr || logits == nullptr) {
        init_error = out == nullptr
            ? "apprentice_result_required"
            : "apprentice_logits_required";
        return -1;
    }
    try {
        *out = sample_exact_q_delta(logits, logits_count, draft_token, sampler);
        init_error.clear();
        return 0;
    } catch (const std::exception & exception) {
        init_error = exception.what();
        return -1;
    } catch (...) {
        init_error = "apprentice_unknown_error";
        return -1;
    }
}
int32_t llama_cassi_set_sampler(
        llama_cassi_context * ctx,
        llama_cassi_sampler_params params) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->set_sampler(params);
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return -1;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return -1;
    }
}
int32_t llama_cassi_sampler_discard(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->discard_sampler();
    } catch (const std::exception & exception) {
        ctx->error = exception.what();
        return -1;
    } catch (...) {
        ctx->error = "apprentice_unknown_error";
        return -1;
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
int32_t llama_cassi_discard_pending(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->discard_pending();
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}
int32_t llama_cassi_verify_draft(
        llama_cassi_context * ctx,
        const llama_cassi_draft_verify_request * request,
        llama_cassi_draft_verify_receipt * receipt) {
    if (ctx == nullptr || request == nullptr || receipt == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->verify_draft(*request, *receipt);
    } catch (const std::exception & exception) {
        const std::string what = exception.what();
        if (what == "apprentice_cancelled") {
            ctx->state = session_state::cancelled;
            ctx->error.clear();
        } else if (what == "apprentice_invalid_transition" || what.rfind("apprentice_draft_", 0) == 0 ||
                what == "apprentice_native_service_prefix_unavailable" ||
                what == "apprentice_sampler_invalid" || what == "apprentice_token_invalid") {
            ctx->error = exception.what();
        } else {
            ctx->set_error(exception.what());
        }
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}
int32_t llama_cassi_verify_commit(llama_cassi_context * ctx, const char receipt_sha256[65]) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->verify_commit(receipt_sha256);
    } catch (const std::exception & exception) {
        const std::string what = exception.what();
        if (what == "apprentice_invalid_transition" || what.rfind("apprentice_draft_", 0) == 0) {
            ctx->error = exception.what();
        } else {
            ctx->set_error(exception.what());
        }
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}
int32_t llama_cassi_verify_discard(llama_cassi_context * ctx, const char receipt_sha256[65]) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->verify_discard(receipt_sha256);
    } catch (const std::exception & exception) {
        const std::string what = exception.what();
        if (what == "apprentice_invalid_transition" || what.rfind("apprentice_draft_", 0) == 0) {
            ctx->error = exception.what();
        } else {
            ctx->set_error(exception.what());
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

int32_t llama_cassi_group_open(
        llama_cassi_context * ctx,
        const llama_cassi_group_row * rows,
        uint32_t n_rows,
        float * embed_out,
        uint32_t embed_width,
        uint32_t embed_capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_open(rows, n_rows, embed_out, embed_width, embed_capacity);
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

enum llama_cassi_group_state llama_cassi_group_state_get(const llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        return LLAMA_CASSI_GROUP_FAILED;
    }
    return ctx->group_state_get();
}

uint32_t llama_cassi_group_rows(const llama_cassi_context * ctx) {
    return ctx == nullptr ? 0 : ctx->group_row_count();
}

uint32_t llama_cassi_group_capacity(const llama_cassi_context * ctx) {
    return ctx == nullptr ? 0 : ctx->group_host.capacity;
}

int32_t llama_cassi_group_stage(
        llama_cassi_context * ctx,
        llama_cassi_service_kind kind,
        int32_t layer,
        const float * input,
        uint32_t width,
        float * out,
        uint32_t out_width,
        uint32_t out_capacity) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_stage(kind, layer, input, width, out, out_width, out_capacity);
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

int32_t llama_cassi_group_sample(
        llama_cassi_context * ctx,
        const float * residual,
        uint32_t width,
        llama_token * tokens_out,
        uint32_t n_rows) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_sample(residual, width, tokens_out, n_rows);
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

int32_t llama_cassi_group_commit(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_commit();
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

int32_t llama_cassi_group_cancel(llama_cassi_context * ctx) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_cancel();
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
    }
}

int32_t llama_cassi_group_row_reset(llama_cassi_context * ctx, uint32_t row) {
    if (ctx == nullptr) {
        init_error = "apprentice_context_required";
        return -1;
    }
    try {
        return ctx->group_row_reset(row);
    } catch (const std::exception & exception) {
        ctx->set_error(exception.what());
        return -1;
    } catch (...) {
        ctx->set_error("apprentice_unknown_error");
        return -1;
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
