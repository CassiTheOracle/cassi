#include "llama-cassi-field.h"

#include "ggml-backend.h"
#include "ggml-cpp.h"

extern "C" {
#include "sha256/sha256.h"
}

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstring>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <utility>

namespace {

constexpr float PHI = 1.618033988749895f;
constexpr float DENOMINATOR = 1.0f + PHI * PHI;
constexpr float SCALE_RATIO = 4.23606797749979f;
constexpr float DT = 0.005f;
constexpr float SENSING_GAIN = 0.25f;
constexpr float FAST_OMEGA2 = 20.0f;
constexpr float SLOW_OMEGA2 = 0.05f;
constexpr float FAST_DAMPING = 0.5f;
constexpr float SLOW_DAMPING = 0.01f;
constexpr float MODE_SLOPE = 0.25f;
constexpr float NONLINEAR_GAIN = 0.002f;
constexpr float MAX_AMPLITUDE = 4.0f;
constexpr float MAX_MEAN_ENERGY = 8.0f;
constexpr float EPSILON_TAU = 1.0f / PHI;
constexpr float EPSILON_CLIP = 64.0f;
constexpr float TEXT_RADIUS = 0.001f;
constexpr float VECTOR_RADIUS = 1.0f / 16.0f;
constexpr float EXACT_DISTANCE2 = 1.0e-10f;
constexpr float MERGE_DISTANCE2 = 1.0e-6f;
constexpr float WEIGHT_FLOOR = 1.0e-6f;
constexpr float SCATTER_CEILING = 1.0e-4f;
constexpr float BYTE_GUIDE_GAIN = 0.5f;
constexpr float VECTOR_GUIDE_GAIN = 1.0f;
constexpr float NORM_GUARD = 1.0e-6f;
constexpr float VECTOR_SUCCESS = 0.01f;
constexpr float GUIDED_VECTOR_TOLERANCE = 1.0e-4f;
constexpr float ERROR_EMA_GAIN = 0.1f;
constexpr float THRESHOLD_ABS_GUARD = 1.0e-12f;
constexpr float THRESHOLD_REL_GUARD = 0.001f;
constexpr float OCCUPANCY_FLOOR = 1.0e-6f;
constexpr uint32_t COUNT_LIMIT = 255;
constexpr uint32_t MERGE_WINDOW = 16;
constexpr uint32_t TOKEN_BYTE_COUNT = 4;
constexpr uint32_t GUIDE_ROUNDS = 8;
constexpr uint32_t MIN_OBSERVATIONS = 2;
constexpr uint32_t MIN_EXACT_SUCCESSES = 1;
constexpr uint32_t MIN_NOVEL_SUCCESSES = 2;
constexpr uint16_t END_SYMBOL = 256;
constexpr uint16_t SYSTEM_SYMBOL = 257;
constexpr uint16_t USER_SYMBOL = 258;
constexpr uint16_t ASSISTANT_SYMBOL = 259;
constexpr uint32_t ALPHABET_SIZE = 260;
constexpr size_t GRAPH_SIZE = 65536;
constexpr size_t GRAPH_CONTEXT_BYTES = 64 * 1024 * 1024;
constexpr size_t STATIC_CONTEXT_BYTES = 4 * 1024 * 1024;

constexpr std::array<uint32_t, 4> PRIMES = { 4093, 4099, 4127, 4133 };
constexpr std::array<std::array<uint32_t, 4>, 4> COEFFICIENTS = {{
    {{ 1, 1, 1, 3 }},
    {{ 3, 5, 7, 11 }},
    {{ 5, 9, 11, 17 }},
    {{ 7, 13, 17, 23 }},
}};
constexpr std::array<std::array<uint32_t, 2>, 4> PERMUTATIONS = {{
    {{ 1, 0 }},
    {{ 5, 1 }},
    {{ 7, 3 }},
    {{ 11, 5 }},
}};
constexpr std::array<const char *, 9> COMPONENT_NAMES = {
    "Y_re", "Y_im", "I_re", "I_im", "VY_re", "VY_im", "VI_re", "VI_im", "epsilon2_ema",
};

[[noreturn]] void fail(const char * code) {
    throw std::runtime_error(code);
}

uint64_t checked_add(uint64_t lhs, uint64_t rhs, const char * code) {
    if (rhs > std::numeric_limits<uint64_t>::max() - lhs) {
        fail(code);
    }
    return lhs + rhs;
}

uint64_t checked_mul(uint64_t lhs, uint64_t rhs, const char * code) {
    if (lhs != 0 && rhs > std::numeric_limits<uint64_t>::max() / lhs) {
        fail(code);
    }
    return lhs * rhs;
}

uint64_t mul_mod(uint64_t lhs, uint64_t rhs, uint64_t modulus) {
    lhs %= modulus;
    rhs %= modulus;
    uint64_t result = 0;
    while (rhs != 0) {
        if ((rhs & 1U) != 0) {
            result = result >= modulus - lhs ? result - (modulus - lhs) : result + lhs;
        }
        rhs >>= 1U;
        lhs = lhs >= modulus - lhs ? lhs - (modulus - lhs) : lhs + lhs;
    }
    return result;
}

uint64_t add_mod(uint64_t lhs, uint64_t rhs, uint64_t modulus) {
    lhs %= modulus;
    rhs %= modulus;
    return lhs >= modulus - rhs ? lhs - (modulus - rhs) : lhs + rhs;
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
    static_assert(sizeof(bits) == sizeof(value), "float32 profile serialization");
    std::memcpy(&bits, &value, sizeof(bits));
    append_u32(bytes, bits);
}

void append_string(std::vector<uint8_t> & bytes, const char * value) {
    const size_t length = std::strlen(value);
    bytes.insert(bytes.end(), value, value + length);
    bytes.push_back(0);
}

float threshold_guard(float threshold) {
    return std::max(THRESHOLD_ABS_GUARD, THRESHOLD_REL_GUARD * std::abs(threshold));
}

bool threshold_ambiguous(float value, float threshold) {
    return std::abs(value - threshold) <= threshold_guard(threshold);
}

uint32_t service_width(uint32_t embedding_width) {
    const uint64_t half = (static_cast<uint64_t>(embedding_width) + 1) / 2;
    const uint64_t minimum = std::max<uint64_t>(260, half);
    uint64_t width = 256 * ((minimum + 255) / 256);
    while (true) {
        bool coprime = true;
        for (const auto & permutation : PERMUTATIONS) {
            coprime = coprime && std::gcd(width, static_cast<uint64_t>(permutation[0])) == 1;
        }
        if (coprime) {
            break;
        }
        width = checked_add(width, 256, "apprentice_geometry_overflow");
    }
    if (width > std::numeric_limits<uint32_t>::max()) {
        fail("apprentice_geometry_overflow");
    }
    return static_cast<uint32_t>(width);
}

struct metadata_value {
    std::array<float, CASSI_APPRENTICE_SCALE_COUNT> occupancy = {};
    uint32_t teacher_observations = 0;
    uint32_t exact_successes = 0;
    uint32_t novel_successes = 0;
    float error_ema = 0.0f;
    uint32_t age = 0;
};

struct key_graph {
    // [scale][key block][real/imag]
    ggml_tensor * value[CASSI_APPRENTICE_SCALE_COUNT][2][2] = {};
};

struct encoded_graph {
    ggml_tensor * real = nullptr;
    ggml_tensor * imag = nullptr;
};

struct width_resources {
    uint32_t width = 0;
    uint32_t max_entries = 0;
    ggml_tensor * codebooks = nullptr;
    ggml_tensor * byte_codebooks = nullptr;
    ggml_tensor * omega2 = nullptr;
    std::array<ggml_tensor *, CASSI_APPRENTICE_SCALE_COUNT> inverse_permutations = {};
    ggml_tensor * probe_encoded = nullptr;
    ggml_tensor * probe_weights = nullptr;
    ggml_tensor * probe_distances = nullptr;
    ggml_tensor * byte_scores = nullptr;
};

struct graph_scope {
    ggml_context_ptr context;
    ggml_cgraph * graph = nullptr;

    graph_scope() {
        ggml_init_params params = {};
        params.mem_size = GRAPH_CONTEXT_BYTES;
        params.mem_buffer = nullptr;
        params.no_alloc = true;
        context.reset(ggml_init(params));
        if (!context) {
            fail("apprentice_graph_allocation_failed");
        }
        graph = ggml_new_graph_custom(context.get(), GRAPH_SIZE, false);
        if (graph == nullptr) {
            fail("apprentice_graph_allocation_failed");
        }
    }
};

std::vector<uint32_t> weighted_cycle(size_t page_count) {
    std::vector<uint32_t> result;
    result.insert(result.end(), 16, 0);
    result.insert(result.end(), 4, 1);
    result.push_back(2);
    for (uint32_t page = 3; page < page_count; ++page) {
        result.push_back(page);
    }
    return result;
}

} // namespace

uint64_t cassi_field_page::entry_stride() const {
    return checked_add(checked_mul(3, width, "apprentice_geometry_overflow"), 6, "apprentice_geometry_overflow");
}

uint64_t cassi_field_page::memory_offset() const {
    return checked_add(mode_offset, width, "apprentice_geometry_overflow");
}

uint64_t cassi_field_page::mode_count() const {
    return checked_add(width, checked_mul(entries, entry_stride(), "apprentice_geometry_overflow"), "apprentice_geometry_overflow");
}

struct llama_cassi_field::impl {
    cassi_field_config cfg;
    std::vector<cassi_field_page> page_descriptors;
    uint64_t mode_count = 0;
    uint64_t state_bytes = 0;
    uint64_t minimum_bytes = 0;
    uint64_t revision = 0;
    uint64_t evictions = 0;
    uint32_t maximum_width = 0;
    uint32_t maximum_entries = 0;
    uint64_t maximum_memory_modes = 0;
    uint64_t maximum_entry_stride = 0;

    ggml_backend_dev_t device = nullptr;
    ggml_backend_ptr backend;
    ggml_gallocr_ptr allocator;
    std::string selected_backend;
    ggml_context_ptr static_context;
    ggml_backend_buffer_ptr static_buffer;

    ggml_tensor * field = nullptr;
    ggml_tensor * candidate_memory = nullptr;
    ggml_tensor * sense_candidate = nullptr;
    ggml_tensor * temporary_state = nullptr;
    ggml_tensor * zero_state = nullptr;
    ggml_tensor * zero_entry = nullptr;
    ggml_tensor * input_vector = nullptr;
    ggml_tensor * target_vector = nullptr;
    ggml_tensor * probe_vector = nullptr;
    ggml_tensor * guided_vector = nullptr;
    std::array<ggml_tensor *, 2> handoff_vectors = {};
    ggml_tensor * boundary_vector = nullptr;
    ggml_tensor * metadata_physical = nullptr;
    ggml_tensor * scalar_output = nullptr;
    ggml_tensor * candidate_validation = nullptr;
    ggml_tensor * symbol_input = nullptr;
    ggml_tensor * byte_input = nullptr;
    std::map<uint32_t, width_resources> resources;
    std::vector<float> page_host;

    explicit impl(const cassi_field_config & config) : cfg(config) {
        validate_config();
        build_geometry();
        initialize_backend();
        initialize_tensors();
        initialize_immutable_inputs();
    }

    void validate_config() const {
        if (cfg.layers == 0 || cfg.embedding_width == 0 || cfg.vocabulary_size == 0) {
            fail("apprentice_model_metadata_invalid");
        }
        if (cfg.memory_bytes == 0) {
            fail("apprentice_memory_budget_too_small");
        }
        if (cfg.device != "CPU" && cfg.device != "Vulkan0") {
            fail("apprentice_backend_unsupported");
        }
    }

    void build_geometry() {
        if (cfg.fixture_entries != 0) {
            page_descriptors.push_back({ CASSI_FIELD_TEXT, -1, 512, cfg.fixture_entries, 0 });
            const uint64_t modes = page_descriptors.front().mode_count();
            minimum_bytes = checked_mul(
                checked_mul(
                    modes,
                    CASSI_APPRENTICE_SCALE_COUNT * CASSI_APPRENTICE_COMPONENT_COUNT,
                    "apprentice_geometry_overflow"),
                sizeof(float),
                "apprentice_geometry_overflow");
            if (minimum_bytes > cfg.memory_bytes) {
                fail("apprentice_memory_budget_too_small");
            }
            maximum_width = page_descriptors.front().width;
            maximum_entries = page_descriptors.front().entries;
            maximum_memory_modes = checked_mul(
                page_descriptors.front().entries,
                page_descriptors.front().entry_stride(),
                "apprentice_geometry_overflow");
            maximum_entry_stride = page_descriptors.front().entry_stride();
            mode_count = modes;
            state_bytes = minimum_bytes;
            return;
        }
        const uint32_t other_width = service_width(cfg.embedding_width);
        page_descriptors.push_back({ CASSI_FIELD_TEXT, -1, 512, 2, 0 });
        page_descriptors.push_back({ CASSI_FIELD_EMBED, -1, other_width, 2, 0 });
        page_descriptors.push_back({ CASSI_FIELD_HEAD, -1, other_width, 2, 0 });
        for (uint32_t layer = 0; layer < cfg.layers; ++layer) {
            page_descriptors.push_back({ CASSI_FIELD_ATTENTION, static_cast<int32_t>(layer), other_width, 2, 0 });
            page_descriptors.push_back({ CASSI_FIELD_FFN, static_cast<int32_t>(layer), other_width, 2, 0 });
        }
        uint64_t modes = 0;
        for (const auto & page : page_descriptors) {
            modes = checked_add(modes, page.mode_count(), "apprentice_geometry_overflow");
        }
        minimum_bytes = checked_mul(
            checked_mul(modes, CASSI_APPRENTICE_SCALE_COUNT * CASSI_APPRENTICE_COMPONENT_COUNT, "apprentice_geometry_overflow"),
            sizeof(float),
            "apprentice_geometry_overflow");
        if (minimum_bytes > cfg.memory_bytes) {
            fail("apprentice_memory_budget_too_small");
        }
        const uint64_t mode_budget = cfg.memory_bytes /
            (CASSI_APPRENTICE_SCALE_COUNT * CASSI_APPRENTICE_COMPONENT_COUNT * sizeof(float));
        const auto cycle = weighted_cycle(page_descriptors.size());
        while (true) {
            uint32_t added = 0;
            for (uint32_t page_index : cycle) {
                const uint64_t stride = page_descriptors[page_index].entry_stride();
                if (stride <= mode_budget - modes) {
                    if (page_descriptors[page_index].entries == std::numeric_limits<uint32_t>::max()) {
                        fail("apprentice_geometry_overflow");
                    }
                    page_descriptors[page_index].entries++;
                    modes += stride;
                    added++;
                }
            }
            if (added == 0) {
                break;
            }
        }
        uint64_t offset = 0;
        for (auto & page : page_descriptors) {
            page.mode_offset = offset;
            offset = checked_add(offset, page.mode_count(), "apprentice_geometry_overflow");
            maximum_width = std::max(maximum_width, page.width);
            maximum_entries = std::max(maximum_entries, page.entries);
            maximum_memory_modes = std::max(maximum_memory_modes, checked_mul(page.entries, page.entry_stride(), "apprentice_geometry_overflow"));
            maximum_entry_stride = std::max(maximum_entry_stride, page.entry_stride());
        }
        mode_count = offset;
        state_bytes = checked_mul(
            checked_mul(mode_count, CASSI_APPRENTICE_SCALE_COUNT * CASSI_APPRENTICE_COMPONENT_COUNT, "apprentice_geometry_overflow"),
            sizeof(float),
            "apprentice_geometry_overflow");
    }

    void initialize_backend() {
        ggml_backend_load_all();
        device = ggml_backend_dev_by_name(cfg.device.c_str());
        if (device == nullptr) {
            fail("apprentice_backend_unsupported");
        }
        backend.reset(ggml_backend_dev_init(device, nullptr));
        if (!backend) {
            fail("apprentice_backend_unsupported");
        }
        selected_backend = ggml_backend_name(backend.get());
        ggml_backend_buffer_type_t buffer_type = ggml_backend_get_default_buffer_type(backend.get());
        allocator.reset(ggml_gallocr_new(buffer_type));
        if (!allocator) {
            fail("apprentice_backend_unsupported");
        }
    }

    void initialize_tensors() {
        ggml_init_params params = {};
        params.mem_size = STATIC_CONTEXT_BYTES;
        params.mem_buffer = nullptr;
        params.no_alloc = true;
        static_context.reset(ggml_init(params));
        if (!static_context) {
            fail("apprentice_field_allocation_failed");
        }
        ggml_context * ctx = static_context.get();
        if (mode_count > static_cast<uint64_t>(std::numeric_limits<int64_t>::max() / CASSI_APPRENTICE_COMPONENT_COUNT) ||
            maximum_memory_modes > static_cast<uint64_t>(std::numeric_limits<int64_t>::max()) ||
            maximum_entry_stride > static_cast<uint64_t>(std::numeric_limits<int64_t>::max())) {
            fail("apprentice_geometry_overflow");
        }
        field = ggml_new_tensor_2d(ctx, GGML_TYPE_F32,
            static_cast<int64_t>(mode_count * CASSI_APPRENTICE_COMPONENT_COUNT),
            CASSI_APPRENTICE_SCALE_COUNT);
        candidate_memory = ggml_new_tensor_3d(ctx, GGML_TYPE_F32,
            static_cast<int64_t>(maximum_memory_modes), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        sense_candidate = ggml_new_tensor_3d(ctx, GGML_TYPE_F32,
            maximum_width, CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        temporary_state = ggml_new_tensor_3d(ctx, GGML_TYPE_F32,
            maximum_width, CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        zero_state = ggml_new_tensor_3d(ctx, GGML_TYPE_F32,
            maximum_width, CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        zero_entry = ggml_new_tensor_3d(ctx, GGML_TYPE_F32,
            static_cast<int64_t>(maximum_entry_stride), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        input_vector = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        target_vector = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        probe_vector = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        guided_vector = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        for (ggml_tensor *& tensor : handoff_vectors) {
            tensor = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        }
        boundary_vector = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, cfg.embedding_width);
        metadata_physical = ggml_new_tensor_4d(ctx, GGML_TYPE_F32,
            6, 8, CASSI_APPRENTICE_SCALE_COUNT, maximum_entries);
        scalar_output = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 8);
        candidate_validation = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 1);
        symbol_input = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, 1);
        byte_input = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, 1);
        ggml_set_name(field, "cassi_apprentice_H");
        ggml_set_name(candidate_memory, "cassi_apprentice_candidate_memory");
        ggml_set_name(sense_candidate, "cassi_apprentice_sense_candidate");

        std::map<uint32_t, uint32_t> max_entries_by_width;
        for (const auto & page : page_descriptors) {
            max_entries_by_width[page.width] = std::max(max_entries_by_width[page.width], page.entries);
        }
        for (const auto & item : max_entries_by_width) {
            width_resources resource;
            resource.width = item.first;
            resource.max_entries = item.second;
            resource.codebooks = ggml_new_tensor_2d(ctx, GGML_TYPE_F32,
                static_cast<int64_t>(resource.width) * 2 * CASSI_APPRENTICE_SCALE_COUNT, ALPHABET_SIZE);
            resource.byte_codebooks = ggml_new_tensor_2d(ctx, GGML_TYPE_F32,
                static_cast<int64_t>(resource.width) * 2, 256);
            resource.omega2 = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, resource.width, CASSI_APPRENTICE_SCALE_COUNT);
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                resource.inverse_permutations[scale] = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, resource.width);
            }
            resource.probe_encoded = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, resource.width, 2);
            resource.probe_weights = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, resource.max_entries);
            resource.probe_distances = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, resource.max_entries);
            resource.byte_scores = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 256);
            resources.emplace(resource.width, resource);
        }

        static_buffer.reset(ggml_backend_alloc_ctx_tensors(static_context.get(), backend.get()));
        if (!static_buffer) {
            fail("apprentice_field_allocation_failed");
        }
        ggml_backend_buffer_clear(static_buffer.get(), 0);
    }

    std::complex<float> codebook_value(uint32_t scale, uint32_t width, uint32_t symbol, uint32_t position) const {
        const uint64_t prime = PRIMES[scale];
        const uint64_t a = static_cast<uint64_t>(symbol) + 1;
        const uint64_t p = static_cast<uint64_t>(position) + 1;
        const uint64_t u = ((p * PERMUTATIONS[scale][0] + PERMUTATIONS[scale][1]) % width) + 1;
        const auto & coefficients = COEFFICIENTS[scale];
        const uint64_t aa = mul_mod(a, a, prime);
        const uint64_t uu = mul_mod(u, u, prime);
        uint64_t phase_index = 0;
        phase_index = add_mod(phase_index, mul_mod(mul_mod(coefficients[0], aa, prime), u, prime), prime);
        phase_index = add_mod(phase_index, mul_mod(mul_mod(coefficients[1], a, prime), uu, prime), prime);
        phase_index = add_mod(phase_index, mul_mod(coefficients[2], uu, prime), prime);
        phase_index = add_mod(phase_index, mul_mod(coefficients[3], a, prime), prime);
        const double angle = 2.0 * 3.14159265358979323846264338327950288 * static_cast<double>(phase_index) /
            static_cast<double>(prime);
        return { static_cast<float>(std::cos(angle)), static_cast<float>(std::sin(angle)) };
    }

    void initialize_immutable_inputs() {
        for (auto & item : resources) {
            auto & resource = item.second;
            const uint32_t width = resource.width;
            const size_t codebook_row = static_cast<size_t>(width) * 2 * CASSI_APPRENTICE_SCALE_COUNT;
            std::vector<float> all_codebooks(static_cast<size_t>(ALPHABET_SIZE) * codebook_row);
            for (uint32_t symbol = 0; symbol < ALPHABET_SIZE; ++symbol) {
                for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                    for (uint32_t position = 0; position < width; ++position) {
                        const auto value = codebook_value(scale, width, symbol, position);
                        const size_t base = static_cast<size_t>(symbol) * codebook_row + static_cast<size_t>(scale) * 2 * width;
                        all_codebooks[base + position] = value.real();
                        all_codebooks[base + width + position] = value.imag();
                    }
                }
            }
            ggml_backend_tensor_set(resource.codebooks, all_codebooks.data(), 0, all_codebooks.size() * sizeof(float));

            std::vector<float> byte_codebooks(static_cast<size_t>(256) * 2 * width);
            const float normalization = 1.0f / std::sqrt(static_cast<float>(width));
            for (uint32_t byte = 0; byte < 256; ++byte) {
                for (uint32_t position = 0; position < width; ++position) {
                    const auto value = codebook_value(0, width, byte, position);
                    byte_codebooks[static_cast<size_t>(byte) * 2 * width + position] = normalization * value.real();
                    byte_codebooks[static_cast<size_t>(byte) * 2 * width + width + position] = normalization * value.imag();
                }
            }
            ggml_backend_tensor_set(resource.byte_codebooks, byte_codebooks.data(), 0, byte_codebooks.size() * sizeof(float));
            std::vector<float> omega_values(static_cast<size_t>(width) * CASSI_APPRENTICE_SCALE_COUNT);
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                const float scale_decay = std::pow(SCALE_RATIO, -0.5f * static_cast<float>(scale));
                for (uint32_t mode = 0; mode < width; ++mode) {
                    const float profile = 1.0f + MODE_SLOPE * static_cast<float>(mode) / std::max<uint32_t>(width - 1, 1);
                    omega_values[static_cast<size_t>(scale) * width + mode] =
                        std::max(SLOW_OMEGA2, FAST_OMEGA2 * scale_decay * profile);
                }
            }
            ggml_backend_tensor_set(resource.omega2, omega_values.data(), 0, omega_values.size() * sizeof(float));


            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                std::vector<int32_t> inverse(width);
                for (uint32_t source = 0; source < width; ++source) {
                    const uint32_t destination = (source * PERMUTATIONS[scale][0] + PERMUTATIONS[scale][1]) % width;
                    inverse[destination] = static_cast<int32_t>(source);
                }
                ggml_backend_tensor_set(resource.inverse_permutations[scale], inverse.data(), 0, inverse.size() * sizeof(int32_t));
            }
        }
    }

    width_resources & width_resource(uint32_t width) {
        auto found = resources.find(width);
        if (found == resources.end()) {
            fail("apprentice_geometry_invalid");
        }
        return found->second;
    }

    const cassi_field_page & checked_page(uint32_t page_index) const {
        if (page_index >= page_descriptors.size()) {
            fail("apprentice_query_invalid");
        }
        return page_descriptors[page_index];
    }

    ggml_tensor * page_view(ggml_context * ctx, const cassi_field_page & page, bool memory) const {
        const uint64_t count = memory ? checked_mul(page.entries, page.entry_stride(), "apprentice_geometry_overflow") : page.width;
        const uint64_t offset_modes = memory ? page.memory_offset() : page.mode_offset;
        return ggml_view_3d(ctx, field,
            static_cast<int64_t>(count), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT,
            mode_count * sizeof(float),
            mode_count * CASSI_APPRENTICE_COMPONENT_COUNT * sizeof(float),
            offset_modes * sizeof(float));
    }

    static ggml_tensor * static_prefix_view(
        ggml_context * ctx,
        ggml_tensor * tensor,
        int64_t ne0,
        int64_t ne1,
        int64_t ne2) {
        return ggml_view_3d(ctx, tensor, ne0, ne1, ne2, tensor->nb[1], tensor->nb[2], 0);
    }

    static ggml_tensor * plane_view(
        ggml_context * ctx,
        ggml_tensor * state,
        uint32_t width,
        uint32_t component,
        uint32_t scale) {
        return ggml_view_1d(ctx, state, width,
            static_cast<size_t>(component) * state->nb[1] + static_cast<size_t>(scale) * state->nb[2]);
    }

    static ggml_tensor * range_plane_view(
        ggml_context * ctx,
        ggml_tensor * state,
        uint64_t start,
        uint64_t count,
        uint32_t component,
        uint32_t scale) {
        return ggml_view_1d(ctx, state, static_cast<int64_t>(count),
            static_cast<size_t>(start) * state->nb[0] + static_cast<size_t>(component) * state->nb[1] +
            static_cast<size_t>(scale) * state->nb[2]);
    }

    void require_supported(const ggml_cgraph * graph) const {
        ggml_tensor ** nodes = ggml_graph_nodes(const_cast<ggml_cgraph *>(graph));
        const int node_count = ggml_graph_n_nodes(const_cast<ggml_cgraph *>(graph));
        for (int node_index = 0; node_index < node_count; ++node_index) {
            const ggml_tensor * node = nodes[node_index];
            if (node->op != GGML_OP_NONE && node->op != GGML_OP_VIEW && !ggml_backend_dev_supports_op(device, node)) {
                fail("apprentice_backend_unsupported");
            }
        }
    }

    void execute(graph_scope & scope, const std::vector<ggml_tensor *> & outputs) {
        for (ggml_tensor * output : outputs) {
            if (output == nullptr) {
                fail("apprentice_graph_invalid");
            }
            ggml_build_forward_expand(scope.graph, output);
        }
        require_supported(scope.graph);
        if (!ggml_gallocr_alloc_graph(allocator.get(), scope.graph)) {
            fail("apprentice_graph_allocation_failed");
        }
        const ggml_status status = ggml_backend_graph_compute(backend.get(), scope.graph);
        if (status != GGML_STATUS_SUCCESS) {
            fail("apprentice_graph_execution_failed");
        }
        ggml_backend_synchronize(backend.get());
    }

    static ggml_tensor * concatenate(ggml_context * ctx, const std::vector<ggml_tensor *> & tensors, int dimension) {
        if (tensors.empty()) {
            fail("apprentice_graph_invalid");
        }
        ggml_tensor * result = tensors.front();
        for (size_t index = 1; index < tensors.size(); ++index) {
            result = ggml_concat(ctx, result, tensors[index], dimension);
        }
        return result;
    }

    static ggml_tensor * safe_positive(ggml_context * ctx, ggml_tensor * value, float floor) {
        ggml_tensor * shifted = ggml_scale_bias(ctx, value, 1.0f, floor);
        ggml_tensor * one = ggml_scale_bias(ctx, shifted, 0.0f, 1.0f);
        ggml_tensor * ratio = ggml_scale(ctx, ggml_div(ctx, one, shifted), floor);
        return ggml_clamp(ctx, ratio, 0.0f, 1.0f);
    }

    static encoded_graph bound_complex(
        ggml_context * ctx,
        ggml_tensor * real,
        ggml_tensor * imag,
        float maximum) {
        ggml_tensor * magnitude2 = ggml_add(ctx, ggml_sqr(ctx, real), ggml_sqr(ctx, imag));
        ggml_tensor * magnitude = ggml_sqrt(ctx, ggml_scale_bias(ctx, magnitude2, 1.0f, 1.0e-30f));
        ggml_tensor * one = ggml_scale_bias(ctx, magnitude, 0.0f, 1.0f);
        ggml_tensor * ratio = ggml_scale(ctx, ggml_div(ctx, one, magnitude), maximum);
        ggml_tensor * factor = ggml_clamp(ctx, ratio, 0.0f, 1.0f);
        return { ggml_mul(ctx, real, factor), ggml_mul(ctx, imag, factor) };
    }

    ggml_tensor * inverse_align(ggml_context * ctx, ggml_tensor * raw, uint32_t scale, uint32_t width) {
        ggml_tensor * rows = ggml_transpose(ctx, ggml_reshape_2d(ctx, raw, width, 1));
        ggml_tensor * gathered = ggml_get_rows(ctx, rows, width_resource(width).inverse_permutations[scale]);
        return ggml_reshape_1d(ctx, gathered, width);
    }

    encoded_graph bounded_context(
        ggml_context * ctx,
        ggml_tensor * real,
        ggml_tensor * imag,
        uint32_t scale,
        uint32_t width) {
        ggml_tensor * norm2 = ggml_add(ctx, ggml_sum(ctx, ggml_sqr(ctx, real)), ggml_sum(ctx, ggml_sqr(ctx, imag)));
        ggml_tensor * norm = ggml_sqrt(ctx, norm2);
        ggml_tensor * denominator = ggml_scale_bias(ctx, norm, 1.0f, 1.0f);
        ggml_tensor * denominator_real = ggml_repeat(ctx, denominator, real);
        ggml_tensor * denominator_imag = ggml_repeat(ctx, denominator, imag);
        return {
            inverse_align(ctx, ggml_div(ctx, real, denominator_real), scale, width),
            inverse_align(ctx, ggml_div(ctx, imag, denominator_imag), scale, width),
        };
    }

    encoded_graph bounded_vector(ggml_context * ctx, ggml_tensor * vector, uint32_t width) {
        ggml_tensor * norm = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, vector)));
        ggml_tensor * denominator = ggml_repeat(ctx, ggml_scale_bias(ctx, norm, 1.0f, 1.0f), vector);
        ggml_tensor * bounded = ggml_div(ctx, vector, denominator);
        ggml_tensor * padded = ggml_pad(ctx, bounded, static_cast<int>(2 * width - cfg.embedding_width), 0, 0, 0);
        ggml_tensor * pairs = ggml_reshape_2d(ctx, padded, 2, width);
        ggml_tensor * channels = ggml_cont_2d(ctx, ggml_transpose(ctx, pairs), width, 2);
        return {
            ggml_view_1d(ctx, channels, width, 0),
            ggml_view_1d(ctx, channels, width, width * sizeof(float)),
        };
    }

    encoded_graph active_context(ggml_context * ctx, ggml_tensor * state, uint32_t scale, uint32_t width) {
        ggml_tensor * d_real = ggml_sub(ctx,
            plane_view(ctx, state, width, 0, scale),
            ggml_scale(ctx, plane_view(ctx, state, width, 2, scale), PHI));
        ggml_tensor * d_imag = ggml_sub(ctx,
            plane_view(ctx, state, width, 1, scale),
            ggml_scale(ctx, plane_view(ctx, state, width, 3, scale), PHI));
        return bounded_context(ctx, d_real, d_imag, scale, width);
    }

    ggml_tensor * build_scale_state(
        ggml_context * ctx,
        ggml_tensor * source,
        ggml_tensor * wave,
        uint32_t width,
        uint32_t scale,
        ggml_tensor ** validation) {
        const float scale_decay = std::pow(SCALE_RATIO, -0.5f * static_cast<float>(scale));
        const float gain = SENSING_GAIN * scale_decay;
        const float damping = std::max(SLOW_DAMPING, FAST_DAMPING * scale_decay);
        const float damping_factor = std::exp(-damping * DT);

        ggml_tensor * y_real = plane_view(ctx, source, width, 0, scale);
        ggml_tensor * y_imag = plane_view(ctx, source, width, 1, scale);
        ggml_tensor * i_real = plane_view(ctx, source, width, 2, scale);
        ggml_tensor * i_imag = plane_view(ctx, source, width, 3, scale);
        ggml_tensor * vy_real = plane_view(ctx, source, width, 4, scale);
        ggml_tensor * vy_imag = plane_view(ctx, source, width, 5, scale);
        ggml_tensor * vi_real = plane_view(ctx, source, width, 6, scale);
        ggml_tensor * vi_imag = plane_view(ctx, source, width, 7, scale);
        ggml_tensor * epsilon_old = plane_view(ctx, source, width, 8, scale);

        ggml_tensor * d_real = ggml_sub(ctx, y_real, ggml_scale(ctx, i_real, PHI));
        ggml_tensor * d_imag = ggml_sub(ctx, y_imag, ggml_scale(ctx, i_imag, PHI));
        ggml_tensor * vd_real = ggml_sub(ctx, vy_real, ggml_scale(ctx, vi_real, PHI));
        ggml_tensor * vd_imag = ggml_sub(ctx, vy_imag, ggml_scale(ctx, vi_imag, PHI));
        ggml_tensor * wave_real = ggml_view_1d(ctx, wave, width, static_cast<size_t>(scale) * 2 * width * sizeof(float));
        ggml_tensor * wave_imag = ggml_view_1d(ctx, wave, width, (static_cast<size_t>(scale) * 2 * width + width) * sizeof(float));
        d_real = ggml_add(ctx, ggml_scale(ctx, d_real, 1.0f - gain), ggml_scale(ctx, wave_real, gain));
        d_imag = ggml_add(ctx, ggml_scale(ctx, d_imag, 1.0f - gain), ggml_scale(ctx, wave_imag, gain));

        ggml_tensor * omega = ggml_view_1d(ctx, width_resource(width).omega2, width,
            static_cast<size_t>(scale) * width * sizeof(float));

        ggml_tensor * magnitude2 = ggml_add(ctx, ggml_sqr(ctx, d_real), ggml_sqr(ctx, d_imag));
        ggml_tensor * force_real = ggml_add(ctx,
            ggml_scale(ctx, ggml_mul(ctx, omega, d_real), -1.0f),
            ggml_scale(ctx, ggml_mul(ctx, magnitude2, d_real), -NONLINEAR_GAIN));
        ggml_tensor * force_imag = ggml_add(ctx,
            ggml_scale(ctx, ggml_mul(ctx, omega, d_imag), -1.0f),
            ggml_scale(ctx, ggml_mul(ctx, magnitude2, d_imag), -NONLINEAR_GAIN));
        vd_real = ggml_add(ctx, ggml_scale(ctx, vd_real, damping_factor), ggml_scale(ctx, force_real, DT));
        vd_imag = ggml_add(ctx, ggml_scale(ctx, vd_imag, damping_factor), ggml_scale(ctx, force_imag, DT));
        d_real = ggml_add(ctx, d_real, ggml_scale(ctx, vd_real, DT));
        d_imag = ggml_add(ctx, d_imag, ggml_scale(ctx, vd_imag, DT));

        const float differential_cap = MAX_AMPLITUDE * DENOMINATOR / PHI;
        auto bounded_d = bound_complex(ctx, d_real, d_imag, differential_cap);
        auto bounded_v = bound_complex(ctx, vd_real, vd_imag, differential_cap);
        d_real = bounded_d.real;
        d_imag = bounded_d.imag;
        vd_real = bounded_v.real;
        vd_imag = bounded_v.imag;

        ggml_tensor * energy_sum = ggml_add(ctx,
            ggml_add(ctx, ggml_sum(ctx, ggml_sqr(ctx, d_real)), ggml_sum(ctx, ggml_sqr(ctx, d_imag))),
            ggml_add(ctx, ggml_sum(ctx, ggml_sqr(ctx, vd_real)), ggml_sum(ctx, ggml_sqr(ctx, vd_imag))));
        ggml_tensor * energy = ggml_scale(ctx, energy_sum, 1.0f / (static_cast<float>(width) * DENOMINATOR));
        ggml_tensor * energy_safe = ggml_scale_bias(ctx, energy, 1.0f, 1.0e-30f);
        ggml_tensor * one = ggml_scale_bias(ctx, energy_safe, 0.0f, 1.0f);
        ggml_tensor * energy_factor = ggml_sqrt(ctx,
            ggml_scale(ctx, ggml_div(ctx, one, energy_safe), MAX_MEAN_ENERGY));
        energy_factor = ggml_clamp(ctx, energy_factor, 0.0f, 1.0f);
        d_real = ggml_mul(ctx, d_real, ggml_repeat(ctx, energy_factor, d_real));
        d_imag = ggml_mul(ctx, d_imag, ggml_repeat(ctx, energy_factor, d_imag));
        vd_real = ggml_mul(ctx, vd_real, ggml_repeat(ctx, energy_factor, vd_real));
        vd_imag = ggml_mul(ctx, vd_imag, ggml_repeat(ctx, energy_factor, vd_imag));

        ggml_tensor * out_y_real = ggml_scale(ctx, d_real, 1.0f / DENOMINATOR);
        ggml_tensor * out_y_imag = ggml_scale(ctx, d_imag, 1.0f / DENOMINATOR);
        ggml_tensor * out_i_real = ggml_scale(ctx, d_real, -PHI / DENOMINATOR);
        ggml_tensor * out_i_imag = ggml_scale(ctx, d_imag, -PHI / DENOMINATOR);
        ggml_tensor * out_vy_real = ggml_scale(ctx, vd_real, 1.0f / DENOMINATOR);
        ggml_tensor * out_vy_imag = ggml_scale(ctx, vd_imag, 1.0f / DENOMINATOR);
        ggml_tensor * out_vi_real = ggml_scale(ctx, vd_real, -PHI / DENOMINATOR);
        ggml_tensor * out_vi_imag = ggml_scale(ctx, vd_imag, -PHI / DENOMINATOR);

        ggml_tensor * imbalance = ggml_sub(ctx,
            ggml_add(ctx, ggml_sqr(ctx, out_y_real), ggml_sqr(ctx, out_y_imag)),
            ggml_scale(ctx, ggml_add(ctx, ggml_sqr(ctx, out_i_real), ggml_sqr(ctx, out_i_imag)), PHI));
        ggml_tensor * epsilon_target = ggml_clamp(ctx, ggml_sqr(ctx, imbalance), 0.0f, EPSILON_CLIP);
        ggml_tensor * epsilon = ggml_add(ctx,
            ggml_scale(ctx, epsilon_old, 1.0f - EPSILON_TAU),
            ggml_scale(ctx, epsilon_target, EPSILON_TAU));

        std::vector<ggml_tensor *> components = {
            out_y_real, out_y_imag, out_i_real, out_i_imag,
            out_vy_real, out_vy_imag, out_vi_real, out_vi_imag, epsilon,
        };
        ggml_tensor * flat = concatenate(ctx, components, 0);
        ggml_tensor * scale_state = ggml_reshape_3d(ctx, flat, width, CASSI_APPRENTICE_COMPONENT_COUNT, 1);

        ggml_tensor * violation = ggml_relu(ctx, ggml_scale_bias(ctx, energy, 1.0f, -MAX_MEAN_ENERGY));
        for (size_t component = 0; component < 8; component += 2) {
            ggml_tensor * amplitude2 = ggml_add(ctx,
                ggml_sqr(ctx, components[component]), ggml_sqr(ctx, components[component + 1]));
            violation = ggml_add(ctx, violation,
                ggml_sum(ctx, ggml_relu(ctx, ggml_scale_bias(ctx, amplitude2, 1.0f, -MAX_AMPLITUDE * MAX_AMPLITUDE))));
        }
        violation = ggml_add(ctx, violation,
            ggml_sum(ctx, ggml_relu(ctx, ggml_scale_bias(ctx, epsilon, 1.0f, -EPSILON_CLIP))));
        violation = ggml_add(ctx, violation,
            ggml_sum(ctx, ggml_relu(ctx, ggml_scale(ctx, epsilon, -1.0f))));
        *validation = violation;
        return scale_state;
    }

    void run_sense(ggml_tensor * state, uint32_t width, uint16_t symbol) {
        if (symbol >= ALPHABET_SIZE) {
            fail("apprentice_symbol_invalid");
        }
        auto & resource = width_resource(width);
        const int32_t symbol_index = symbol;
        ggml_backend_tensor_set(symbol_input, &symbol_index, 0, sizeof(symbol_index));
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * codeword = ggml_get_rows(ctx, resource.codebooks, symbol_input);
        codeword = ggml_reshape_1d(ctx, codeword,
            static_cast<int64_t>(width) * 2 * CASSI_APPRENTICE_SCALE_COUNT);
        std::vector<ggml_tensor *> scale_states;
        std::vector<ggml_tensor *> violations;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            ggml_tensor * violation = nullptr;
            scale_states.push_back(build_scale_state(ctx, state, codeword, width, scale, &violation));
            violations.push_back(violation);
        }
        ggml_tensor * updated = concatenate(ctx, scale_states, 2);
        ggml_tensor * candidate = static_prefix_view(ctx, sense_candidate, width,
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        ggml_tensor * candidate_copy = ggml_cpy(ctx, updated, candidate);
        ggml_tensor * total_violation = violations.front();
        for (size_t index = 1; index < violations.size(); ++index) {
            total_violation = ggml_add(ctx, total_violation, violations[index]);
        }
        ggml_tensor * validation_copy = ggml_cpy(ctx, total_violation,
            ggml_view_1d(ctx, candidate_validation, 1, 0));
        execute(scope, { candidate_copy, validation_copy });
        float violation = 0.0f;
        ggml_backend_tensor_get(candidate_validation, &violation, 0, sizeof(violation));
        if (!std::isfinite(violation) || violation > 1.0e-5f) {
            fail("apprentice_field_bounds_exceeded");
        }

        graph_scope commit_scope;
        ggml_context * commit_ctx = commit_scope.context.get();
        ggml_tensor * source = static_prefix_view(commit_ctx, sense_candidate, width,
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        ggml_tensor * commit = ggml_cpy(commit_ctx, source, state);
        execute(commit_scope, { commit });
    }

    void reset_context() {
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        std::vector<ggml_tensor *> outputs;
        for (const auto & page : page_descriptors) {
            ggml_tensor * zero = static_prefix_view(ctx, zero_state, page.width,
                CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
            outputs.push_back(ggml_cpy(ctx, zero, page_view(ctx, page, false)));
        }
        execute(scope, outputs);
    }

    void clear_temporary(uint32_t width) {
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * zero = static_prefix_view(ctx, zero_state, width,
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        ggml_tensor * target = static_prefix_view(ctx, temporary_state, width,
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        execute(scope, { ggml_cpy(ctx, zero, target) });
    }

    void prepare_temporary(uint32_t width, const std::vector<uint16_t> & symbols) {
        clear_temporary(width);
        for (uint16_t symbol : symbols) {
            graph_scope view_scope;
            ggml_context * ctx = view_scope.context.get();
            ggml_tensor * state = static_prefix_view(ctx, temporary_state, width,
                CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
            // run_sense constructs its own graph, so preserve only the static tensor metadata.
            run_sense(state, width, symbol);
        }
    }

    void sense_marker(uint16_t symbol) {
        if (symbol >= ALPHABET_SIZE) {
            fail("apprentice_symbol_invalid");
        }
        for (const auto & page : page_descriptors) {
            if (page.kind != CASSI_FIELD_TEXT && page.kind != CASSI_FIELD_ATTENTION) {
                continue;
            }
            graph_scope view_scope;
            ggml_tensor * active = page_view(view_scope.context.get(), page, false);
            run_sense(active, page.width, symbol);
        }
    }

    void sense_token(int32_t token, const std::string & piece, bool eog) {
        if (token < 0 || static_cast<uint32_t>(token) >= cfg.vocabulary_size) {
            fail("apprentice_token_invalid");
        }
        for (unsigned char byte : piece) {
            sense_marker(byte);
        }
        if (eog) {
            sense_marker(END_SYMBOL);
        }
    }

    void validate_query(const cassi_query & query, const cassi_field_page & page) const {
        const bool prefix_zero = std::all_of(query.id_prefix.begin(), query.id_prefix.end(), [](uint8_t value) { return value == 0; });
        switch (page.kind) {
            case CASSI_FIELD_TEXT:
                if (query.input != nullptr || query.token != -1 || query.piece != nullptr || query.piece_size != 0 ||
                    query.byte_index >= TOKEN_BYTE_COUNT) {
                    fail("apprentice_query_invalid");
                }
                for (uint32_t index = query.byte_index; index < TOKEN_BYTE_COUNT; ++index) {
                    if (query.id_prefix[index] != 0) {
                        fail("apprentice_query_invalid");
                    }
                }
                break;
            case CASSI_FIELD_EMBED:
                if (query.input != nullptr || query.token < 0 || static_cast<uint32_t>(query.token) >= cfg.vocabulary_size ||
                    (query.piece_size > 0 && query.piece == nullptr) || query.byte_index != CASSI_APPRENTICE_UNUSED_BYTE_INDEX || !prefix_zero) {
                    fail("apprentice_query_invalid");
                }
                break;
            case CASSI_FIELD_ATTENTION:
            case CASSI_FIELD_FFN:
                if (query.input == nullptr || query.token != -1 || query.piece != nullptr || query.piece_size != 0 ||
                    query.byte_index != CASSI_APPRENTICE_UNUSED_BYTE_INDEX || !prefix_zero) {
                    fail("apprentice_query_invalid");
                }
                break;
            case CASSI_FIELD_HEAD:
                if (query.input == nullptr || query.token != -1 || query.piece != nullptr || query.piece_size != 0 ||
                    query.byte_index >= TOKEN_BYTE_COUNT) {
                    fail("apprentice_query_invalid");
                }
                for (uint32_t index = query.byte_index; index < TOKEN_BYTE_COUNT; ++index) {
                    if (query.id_prefix[index] != 0) {
                        fail("apprentice_query_invalid");
                    }
                }
                break;
            default:
                fail("apprentice_query_invalid");
        }
        if (query.input != nullptr) {
            if (query.input->type != GGML_TYPE_F32 || !ggml_is_contiguous(query.input) ||
                ggml_nelements(query.input) != cfg.embedding_width || query.input->buffer == nullptr) {
                fail("apprentice_query_invalid");
            }
        }
    }

    void prepare_query(const cassi_query & query, const cassi_field_page & page) {
        validate_query(query, page);
        if (query.input != nullptr) {
            ggml_backend_tensor_copy(query.input, input_vector);
        }
        std::vector<uint16_t> symbols;
        if (page.kind == CASSI_FIELD_TEXT || page.kind == CASSI_FIELD_HEAD) {
            symbols = { SYSTEM_SYMBOL, static_cast<uint16_t>(query.byte_index), END_SYMBOL, ASSISTANT_SYMBOL };
            symbols.insert(symbols.end(), query.id_prefix.begin(), query.id_prefix.begin() + query.byte_index);
            prepare_temporary(page.width, symbols);
        } else if (page.kind == CASSI_FIELD_EMBED) {
            symbols.push_back(SYSTEM_SYMBOL);
            const uint32_t token = static_cast<uint32_t>(query.token);
            for (uint32_t index = 0; index < TOKEN_BYTE_COUNT; ++index) {
                symbols.push_back(static_cast<uint16_t>((token >> (8 * index)) & 0xffU));
            }
            symbols.push_back(END_SYMBOL);
            for (size_t index = 0; index < query.piece_size; ++index) {
                symbols.push_back(query.piece[index]);
            }
            prepare_temporary(page.width, symbols);
        }
    }

    key_graph build_query_graph(ggml_context * ctx, const cassi_field_page & page) {
        key_graph result;
        ggml_tensor * active = page_view(ctx, page, false);
        ggml_tensor * temporary = static_prefix_view(ctx, temporary_state, page.width,
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        encoded_graph vector_encoded = {};
        if (page.kind == CASSI_FIELD_ATTENTION || page.kind == CASSI_FIELD_FFN || page.kind == CASSI_FIELD_HEAD) {
            vector_encoded = bounded_vector(ctx, input_vector, page.width);
        }
        const float key_scale = 1.0f / std::sqrt(2.0f);
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            encoded_graph first = {};
            encoded_graph second = {};
            if (page.kind == CASSI_FIELD_TEXT) {
                first = active_context(ctx, active, scale, page.width);
                second = active_context(ctx, temporary, scale, page.width);
            } else if (page.kind == CASSI_FIELD_EMBED) {
                first = active_context(ctx, temporary, scale, page.width);
                second.real = ggml_scale(ctx, first.real, 0.0f);
                second.imag = ggml_scale(ctx, first.imag, 0.0f);
            } else {
                first = vector_encoded;
                if (page.kind == CASSI_FIELD_ATTENTION) {
                    second = active_context(ctx, active, scale, page.width);
                } else if (page.kind == CASSI_FIELD_HEAD) {
                    second = active_context(ctx, temporary, scale, page.width);
                } else {
                    second.real = ggml_scale(ctx, first.real, 0.0f);
                    second.imag = ggml_scale(ctx, first.imag, 0.0f);
                }
            }
            result.value[scale][0][0] = ggml_scale(ctx, first.real, key_scale);
            result.value[scale][0][1] = ggml_scale(ctx, first.imag, key_scale);
            result.value[scale][1][0] = ggml_scale(ctx, second.real, key_scale);
            result.value[scale][1][1] = ggml_scale(ctx, second.imag, key_scale);
        }
        return result;
    }

    ggml_tensor * common_plane(
        ggml_context * ctx,
        ggml_tensor * memory,
        uint64_t start,
        uint32_t count,
        uint32_t scale,
        bool imaginary) const {
        const uint32_t yang_component = imaginary ? 1 : 0;
        const uint32_t yin_component = imaginary ? 3 : 2;
        ggml_tensor * yang = range_plane_view(ctx, memory, start, count, yang_component, scale);
        ggml_tensor * yin = range_plane_view(ctx, memory, start, count, yin_component, scale);
        return ggml_scale(ctx, ggml_add(ctx, ggml_scale(ctx, yang, PHI), yin), 1.0f / DENOMINATOR);
    }

    float field_value(uint32_t scale, uint32_t component, uint64_t mode) const {
        if (scale >= CASSI_APPRENTICE_SCALE_COUNT || component >= CASSI_APPRENTICE_COMPONENT_COUNT || mode >= mode_count) {
            fail("apprentice_field_index_invalid");
        }
        float value = 0.0f;
        const uint64_t element = (static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * mode_count + mode;
        ggml_backend_tensor_get(field, &value, element * sizeof(float), sizeof(value));
        return value;
    }

    float common_value(uint32_t scale, uint64_t mode, bool imaginary = false) const {
        const float yang = field_value(scale, imaginary ? 1 : 0, mode);
        const float yin = field_value(scale, imaginary ? 3 : 2, mode);
        return (PHI * yang + yin) / DENOMINATOR;
    }

    metadata_value read_metadata(const cassi_field_page & page, uint32_t entry) const {
        if (entry >= page.entries) {
            fail("apprentice_field_index_invalid");
        }
        metadata_value result;
        const uint64_t base = page.memory_offset() + static_cast<uint64_t>(entry) * page.entry_stride() + 3ULL * page.width;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            result.occupancy[scale] = common_value(scale, base);
            for (uint32_t meta = 0; meta < 6; ++meta) {
                if (std::abs(common_value(scale, base + meta, true)) > 1.0e-5f) {
                    fail("apprentice_checkpoint_invalid");
                }
            }
        }
        const auto decode_count = [&](uint32_t meta) {
            const float encoded = common_value(0, base + meta);
            const float scaled = 255.0f * encoded;
            const long rounded = std::lround(scaled);
            if (!std::isfinite(encoded) || rounded < 0 || rounded > 255 || std::abs(scaled - rounded) > 1.0e-4f) {
                fail("apprentice_checkpoint_invalid");
            }
            return static_cast<uint32_t>(rounded);
        };
        result.teacher_observations = decode_count(1);
        result.exact_successes = decode_count(2);
        result.novel_successes = decode_count(3);
        result.error_ema = common_value(0, base + 4);
        result.age = decode_count(5);
        for (uint32_t scale = 1; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            for (uint32_t meta = 1; meta < 6; ++meta) {
                if (std::abs(common_value(scale, base + meta) - common_value(0, base + meta)) > 1.0e-4f) {
                    fail("apprentice_checkpoint_invalid");
                }
            }
        }
        if (!std::isfinite(result.error_ema) || result.error_ema < 0.0f || result.error_ema > 1.0f) {
            fail("apprentice_checkpoint_invalid");
        }
        for (float occupancy : result.occupancy) {
            if (!std::isfinite(occupancy) || occupancy < 0.0f || occupancy > 1.0f) {
                fail("apprentice_checkpoint_invalid");
            }
        }
        return result;
    }

    cassi_probe run_probe(const cassi_query & query) {
        const auto & page = checked_page(query.page);
        prepare_query(query, page);
        auto & resource = width_resource(page.width);
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * memory = page_view(ctx, page, true);
        key_graph key = build_query_graph(ctx, page);
        std::vector<ggml_tensor *> entry_weights;
        std::vector<ggml_tensor *> entry_distances;
        std::vector<encoded_graph> entry_targets;
        entry_weights.reserve(page.entries);
        entry_distances.reserve(page.entries);
        entry_targets.reserve(page.entries);
        const float radius = page.kind == CASSI_FIELD_TEXT || page.kind == CASSI_FIELD_EMBED ? TEXT_RADIUS : VECTOR_RADIUS;

        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            const uint64_t base = static_cast<uint64_t>(entry) * page.entry_stride();
            std::vector<ggml_tensor *> distance_parts;
            std::vector<ggml_tensor *> target_real_parts;
            std::vector<ggml_tensor *> target_imag_parts;
            std::vector<ggml_tensor *> occupancy_parts;
            std::vector<ggml_tensor *> availability_parts;
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                ggml_tensor * occupancy = common_plane(ctx, memory, base + 3ULL * page.width, 1, scale, false);
                ggml_tensor * availability = ggml_step(ctx, ggml_scale_bias(ctx, occupancy, 1.0f, -OCCUPANCY_FLOOR));
                ggml_tensor * safe_occupancy =
                    ggml_clamp(ctx, occupancy, OCCUPANCY_FLOOR, 1.0f);
                ggml_tensor * repeated_occupancy = nullptr;
                ggml_tensor * distance = nullptr;
                for (uint32_t block = 0; block < 2; ++block) {
                    for (uint32_t part = 0; part < 2; ++part) {
                        ggml_tensor * stored = common_plane(ctx, memory,
                            base + static_cast<uint64_t>(block) * page.width,
                            page.width, scale, part != 0);
                        repeated_occupancy = ggml_repeat(ctx, safe_occupancy, stored);
                        ggml_tensor * normalized = ggml_div(ctx, stored, repeated_occupancy);
                        ggml_tensor * difference = ggml_sub(ctx, key.value[scale][block][part], normalized);
                        ggml_tensor * component_distance = ggml_sum(ctx, ggml_sqr(ctx, difference));
                        distance = distance == nullptr ? component_distance : ggml_add(ctx, distance, component_distance);
                    }
                }
                distance_parts.push_back(ggml_mul(ctx, distance, availability));
                ggml_tensor * stored_target_real = common_plane(ctx, memory,
                    base + 2ULL * page.width, page.width, scale, false);
                ggml_tensor * stored_target_imag = common_plane(ctx, memory,
                    base + 2ULL * page.width, page.width, scale, true);
                target_real_parts.push_back(ggml_mul(ctx,
                    ggml_div(ctx, stored_target_real, ggml_repeat(ctx, safe_occupancy, stored_target_real)),
                    ggml_repeat(ctx, availability, stored_target_real)));
                target_imag_parts.push_back(ggml_mul(ctx,
                    ggml_div(ctx, stored_target_imag, ggml_repeat(ctx, safe_occupancy, stored_target_imag)),
                    ggml_repeat(ctx, availability, stored_target_imag)));
                occupancy_parts.push_back(ggml_mul(ctx, occupancy, availability));
                availability_parts.push_back(availability);
            }
            ggml_tensor * available_count = availability_parts.front();
            ggml_tensor * distance_sum = distance_parts.front();
            ggml_tensor * target_real_sum = target_real_parts.front();
            ggml_tensor * target_imag_sum = target_imag_parts.front();
            ggml_tensor * occupancy_sum = occupancy_parts.front();
            for (uint32_t scale = 1; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                available_count = ggml_add(ctx, available_count, availability_parts[scale]);
                distance_sum = ggml_add(ctx, distance_sum, distance_parts[scale]);
                target_real_sum = ggml_add(ctx, target_real_sum, target_real_parts[scale]);
                target_imag_sum = ggml_add(ctx, target_imag_sum, target_imag_parts[scale]);
                occupancy_sum = ggml_add(ctx, occupancy_sum, occupancy_parts[scale]);
            }
            ggml_tensor * safe_count = ggml_clamp(ctx,
                ggml_scale_bias(ctx, available_count, 1.0f, 1.0e-20f), 1.0f, 4.0f);
            ggml_tensor * distance = ggml_div(ctx, distance_sum, safe_count);
            ggml_tensor * target_real = ggml_div(ctx, target_real_sum, ggml_repeat(ctx, safe_count, target_real_sum));
            ggml_tensor * target_imag = ggml_div(ctx, target_imag_sum, ggml_repeat(ctx, safe_count, target_imag_sum));
            ggml_tensor * mean_occupancy = ggml_div(ctx, occupancy_sum, safe_count);
            ggml_tensor * kernel = ggml_clamp(ctx,
                ggml_scale_bias(ctx, distance, -1.0f / (radius * radius), 1.0f), 0.0f, 1.0f);
            kernel = ggml_sqr(ctx, kernel);
            ggml_tensor * error = common_plane(ctx, memory, base + 3ULL * page.width + 4, 1, 0, false);
            ggml_tensor * weight = ggml_div(ctx,
                ggml_mul(ctx, kernel, mean_occupancy),
                ggml_scale_bias(ctx, error, 1.0f, 1.0f));
            entry_distances.push_back(distance);
            entry_weights.push_back(weight);
            entry_targets.push_back({ target_real, target_imag });
        }

        ggml_tensor * weights = concatenate(ctx, entry_weights, 0);
        ggml_tensor * distances = concatenate(ctx, entry_distances, 0);
        ggml_tensor * total_weight = ggml_sum(ctx, weights);
        ggml_tensor * safe_total = ggml_clamp(ctx,
            ggml_scale_bias(ctx, total_weight, 1.0f, 1.0e-20f), WEIGHT_FLOOR, std::numeric_limits<float>::max());
        ggml_tensor * target_real_numerator = nullptr;
        ggml_tensor * target_imag_numerator = nullptr;
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            ggml_tensor * repeated_weight_real = ggml_repeat(ctx, entry_weights[entry], entry_targets[entry].real);
            ggml_tensor * repeated_weight_imag = ggml_repeat(ctx, entry_weights[entry], entry_targets[entry].imag);
            ggml_tensor * real_part = ggml_mul(ctx, entry_targets[entry].real, repeated_weight_real);
            ggml_tensor * imag_part = ggml_mul(ctx, entry_targets[entry].imag, repeated_weight_imag);
            target_real_numerator = target_real_numerator == nullptr ? real_part : ggml_add(ctx, target_real_numerator, real_part);
            target_imag_numerator = target_imag_numerator == nullptr ? imag_part : ggml_add(ctx, target_imag_numerator, imag_part);
        }
        ggml_tensor * target_real = ggml_div(ctx, target_real_numerator, ggml_repeat(ctx, safe_total, target_real_numerator));
        ggml_tensor * target_imag = ggml_div(ctx, target_imag_numerator, ggml_repeat(ctx, safe_total, target_imag_numerator));
        ggml_tensor * scatter_numerator = nullptr;
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            ggml_tensor * difference2 = ggml_add(ctx,
                ggml_sqr(ctx, ggml_sub(ctx, entry_targets[entry].real, target_real)),
                ggml_sqr(ctx, ggml_sub(ctx, entry_targets[entry].imag, target_imag)));
            ggml_tensor * contribution = ggml_mul(ctx,
                ggml_sum(ctx, difference2), entry_weights[entry]);
            scatter_numerator = scatter_numerator == nullptr ? contribution : ggml_add(ctx, scatter_numerator, contribution);
        }
        ggml_tensor * scatter = ggml_div(ctx, scatter_numerator, safe_total);
        ggml_tensor * encoded_flat = concatenate(ctx, { target_real, target_imag }, 0);
        ggml_tensor * encoded = ggml_reshape_2d(ctx, encoded_flat, page.width, 2);

        ggml_tensor * weights_out = ggml_view_1d(ctx, resource.probe_weights, page.entries, 0);
        ggml_tensor * distances_out = ggml_view_1d(ctx, resource.probe_distances, page.entries, 0);
        ggml_tensor * encoded_out = resource.probe_encoded;
        ggml_tensor * total_out = ggml_view_1d(ctx, scalar_output, 1, 0);
        ggml_tensor * scatter_out = ggml_view_1d(ctx, scalar_output, 1, sizeof(float));
        std::vector<ggml_tensor *> outputs = {
            ggml_cpy(ctx, weights, weights_out),
            ggml_cpy(ctx, distances, distances_out),
            ggml_cpy(ctx, encoded, encoded_out),
            ggml_cpy(ctx, total_weight, total_out),
            ggml_cpy(ctx, scatter, scatter_out),
        };

        ggml_tensor * encoded_norm = ggml_sqrt(ctx,
            ggml_add(ctx, ggml_sum(ctx, ggml_sqr(ctx, target_real)), ggml_sum(ctx, ggml_sqr(ctx, target_imag))));
        outputs.push_back(ggml_cpy(ctx, encoded_norm, ggml_view_1d(ctx, scalar_output, 1, 2 * sizeof(float))));
        if (page.kind == CASSI_FIELD_TEXT || page.kind == CASSI_FIELD_HEAD) {
            ggml_tensor * scores = ggml_mul_mat(ctx, resource.byte_codebooks, ggml_reshape_1d(ctx, encoded, 2LL * page.width));
            outputs.push_back(ggml_cpy(ctx, scores, resource.byte_scores));
        } else {
            ggml_tensor * channels = ggml_cont_2d(ctx, ggml_transpose(ctx, encoded), 2, page.width);
            ggml_tensor * interleaved = ggml_reshape_1d(ctx, channels, 2LL * page.width);
            ggml_tensor * vector_view = ggml_view_1d(ctx, interleaved, cfg.embedding_width, 0);
            ggml_tensor * one = ggml_scale_bias(ctx, encoded_norm, 0.0f, 1.0f);
            ggml_tensor * denominator = ggml_scale_bias(ctx, encoded_norm, -1.0f, 1.0f);
            ggml_tensor * restored = ggml_mul(ctx, vector_view,
                ggml_repeat(ctx, ggml_div(ctx, one, denominator), vector_view));
            outputs.push_back(ggml_cpy(ctx, restored, probe_vector));
        }
        execute(scope, outputs);

        cassi_probe result;
        result.weights.resize(page.entries);
        result.distances2.resize(page.entries);
        ggml_backend_tensor_get(resource.probe_weights, result.weights.data(), 0, page.entries * sizeof(float));
        ggml_backend_tensor_get(resource.probe_distances, result.distances2.data(), 0, page.entries * sizeof(float));
        std::array<float, 3> scalars = {};
        ggml_backend_tensor_get(scalar_output, scalars.data(), 0, scalars.size() * sizeof(float));
        result.total_weight = scalars[0];
        result.scatter = scalars[1];
        result.is_byte = page.kind == CASSI_FIELD_TEXT || page.kind == CASSI_FIELD_HEAD;
        result.vector_length = result.is_byte ? 0 : cfg.embedding_width;
        result.target = result.is_byte ? resource.probe_encoded : probe_vector;
        result.minimum_distance2 = std::numeric_limits<float>::infinity();

        std::vector<metadata_value> metadata(page.entries);
        std::vector<uint32_t> supporting;
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            metadata[entry] = read_metadata(page, entry);
            if (metadata[entry].occupancy[0] < OCCUPANCY_FLOOR) {
                result.distances2[entry] = std::numeric_limits<float>::infinity();
                result.weights[entry] = 0.0f;
                continue;
            }
            result.minimum_distance2 = std::min(result.minimum_distance2, result.distances2[entry]);
            if (result.weights[entry] > 0.0f) {
                supporting.push_back(entry);
            }
        }
        if (result.is_byte && !supporting.empty() && std::isfinite(scalars[2])) {
            std::array<float, 256> scores = {};
            ggml_backend_tensor_get(resource.byte_scores, scores.data(), 0, sizeof(scores));
            result.byte = static_cast<uint8_t>(std::distance(scores.begin(), std::max_element(scores.begin(), scores.end())));
        }
        const bool basic_eligible = !supporting.empty() && std::isfinite(result.total_weight) &&
            std::isfinite(result.scatter) && result.total_weight >= WEIGHT_FLOOR &&
            result.scatter <= SCATTER_CEILING &&
            !threshold_ambiguous(result.total_weight, WEIGHT_FLOOR) &&
            !threshold_ambiguous(result.scatter, SCATTER_CEILING) &&
            (result.is_byte || (std::isfinite(scalars[2]) && scalars[2] < 1.0f - NORM_GUARD));
        bool exact_support = false;
        bool novel_support = !supporting.empty();
        bool distance_boundary = false;
        for (uint32_t entry : supporting) {
            const auto & meta = metadata[entry];
            exact_support = exact_support ||
                (result.distances2[entry] <= EXACT_DISTANCE2 &&
                 meta.teacher_observations >= MIN_OBSERVATIONS &&
                 meta.exact_successes >= MIN_EXACT_SUCCESSES);
            novel_support = novel_support && meta.novel_successes >= MIN_NOVEL_SUCCESSES && meta.error_ema <= VECTOR_SUCCESS;
            distance_boundary = distance_boundary ||
                (result.distances2[entry] > 0.0f && threshold_ambiguous(result.distances2[entry], EXACT_DISTANCE2));
        }
        result.eligible = basic_eligible && !distance_boundary && (exact_support || novel_support);
        result.exact = result.eligible && exact_support;
        result.status = result.exact ? CASSI_PROBE_FIELD_EXACT :
            (result.eligible ? CASSI_PROBE_FIELD_INTERPOLATED : CASSI_PROBE_NEEDS_TEACHER);
        return result;
    }

    cassi_probe probe(const cassi_query & query) {
        return run_probe(query);
    }

    void validate_target(const cassi_field_page & page, const cassi_target & target) {
        const bool byte_page = page.kind == CASSI_FIELD_TEXT || page.kind == CASSI_FIELD_HEAD;
        if (byte_page != target.is_byte) {
            fail("apprentice_target_invalid");
        }
        if (target.is_byte) {
            if (target.vector != nullptr) {
                fail("apprentice_target_invalid");
            }
            const int32_t byte_index_value = target.byte;
            ggml_backend_tensor_set(byte_input, &byte_index_value, 0, sizeof(byte_index_value));
            return;
        }
        if (target.vector == nullptr || target.vector->type != GGML_TYPE_F32 ||
            !ggml_is_contiguous(target.vector) || ggml_nelements(target.vector) != cfg.embedding_width ||
            target.vector->buffer == nullptr) {
            fail("apprentice_target_invalid");
        }
        ggml_backend_tensor_copy(target.vector, target_vector);
    }

    encoded_graph build_target_graph(
        ggml_context * ctx,
        const cassi_field_page & page,
        const cassi_target & target) {
        if (target.is_byte) {
            ggml_tensor * row = ggml_get_rows(ctx, width_resource(page.width).byte_codebooks, byte_input);
            ggml_tensor * encoded = ggml_reshape_2d(ctx, row, page.width, 2);
            return {
                ggml_view_1d(ctx, encoded, page.width, 0),
                ggml_view_1d(ctx, encoded, page.width, page.width * sizeof(float)),
            };
        }
        return bounded_vector(ctx, target_vector, page.width);
    }

    encoded_graph build_entry_target(
        ggml_context * ctx,
        ggml_tensor * memory,
        const cassi_field_page & page,
        uint32_t entry) {
        const uint64_t base = static_cast<uint64_t>(entry) * page.entry_stride();
        std::vector<ggml_tensor *> real_parts;
        std::vector<ggml_tensor *> imag_parts;
        std::vector<ggml_tensor *> availability_parts;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            ggml_tensor * occupancy = common_plane(ctx, memory, base + 3ULL * page.width, 1, scale, false);
            ggml_tensor * availability = ggml_step(ctx, ggml_scale_bias(ctx, occupancy, 1.0f, -OCCUPANCY_FLOOR));
            ggml_tensor * safe_occupancy =
                ggml_clamp(ctx, occupancy, OCCUPANCY_FLOOR, 1.0f);
            ggml_tensor * real = common_plane(ctx, memory, base + 2ULL * page.width, page.width, scale, false);
            ggml_tensor * imag = common_plane(ctx, memory, base + 2ULL * page.width, page.width, scale, true);
            real_parts.push_back(ggml_mul(ctx,
                ggml_div(ctx, real, ggml_repeat(ctx, safe_occupancy, real)),
                ggml_repeat(ctx, availability, real)));
            imag_parts.push_back(ggml_mul(ctx,
                ggml_div(ctx, imag, ggml_repeat(ctx, safe_occupancy, imag)),
                ggml_repeat(ctx, availability, imag)));
            availability_parts.push_back(availability);
        }
        ggml_tensor * count = availability_parts.front();
        ggml_tensor * real = real_parts.front();
        ggml_tensor * imag = imag_parts.front();
        for (uint32_t scale = 1; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            count = ggml_add(ctx, count, availability_parts[scale]);
            real = ggml_add(ctx, real, real_parts[scale]);
            imag = ggml_add(ctx, imag, imag_parts[scale]);
        }
        count = ggml_clamp(ctx, ggml_scale_bias(ctx, count, 1.0f, 1.0e-20f), 1.0f, 4.0f);
        return {
            ggml_div(ctx, real, ggml_repeat(ctx, count, real)),
            ggml_div(ctx, imag, ggml_repeat(ctx, count, imag)),
        };
    }

    ggml_tensor * decode_vector_graph(
        ggml_context * ctx,
        const encoded_graph & encoded,
        uint32_t width,
        ggml_tensor ** encoded_norm) {
        *encoded_norm = ggml_sqrt(ctx, ggml_add(ctx,
            ggml_sum(ctx, ggml_sqr(ctx, encoded.real)),
            ggml_sum(ctx, ggml_sqr(ctx, encoded.imag))));
        ggml_tensor * flat = concatenate(ctx, { encoded.real, encoded.imag }, 0);
        ggml_tensor * channels = ggml_reshape_2d(ctx, flat, width, 2);
        ggml_tensor * pairs = ggml_cont_2d(ctx, ggml_transpose(ctx, channels), 2, width);
        ggml_tensor * interleaved = ggml_reshape_1d(ctx, pairs, 2LL * width);
        ggml_tensor * vector = ggml_view_1d(ctx, interleaved, cfg.embedding_width, 0);
        ggml_tensor * one = ggml_scale_bias(ctx, *encoded_norm, 0.0f, 1.0f);
        ggml_tensor * denominator = ggml_scale_bias(ctx, *encoded_norm, -1.0f, 1.0f);
        return ggml_mul(ctx, vector,
            ggml_repeat(ctx, ggml_div(ctx, one, denominator), vector));
    }

    bool entry_target_matches(
        const cassi_field_page & page,
        uint32_t entry,
        const cassi_target & target) {
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * memory = page_view(ctx, page, true);
        encoded_graph entry_target = build_entry_target(ctx, memory, page, entry);
        if (target.is_byte) {
            ggml_tensor * encoded = ggml_reshape_1d(ctx,
                concatenate(ctx, { entry_target.real, entry_target.imag }, 0), 2LL * page.width);
            ggml_tensor * scores = ggml_mul_mat(ctx, width_resource(page.width).byte_codebooks, encoded);
            execute(scope, { ggml_cpy(ctx, scores, width_resource(page.width).byte_scores) });
            std::array<float, 256> host_scores = {};
            ggml_backend_tensor_get(width_resource(page.width).byte_scores, host_scores.data(), 0, sizeof(host_scores));
            const uint8_t decoded = static_cast<uint8_t>(
                std::distance(host_scores.begin(), std::max_element(host_scores.begin(), host_scores.end())));
            return decoded == target.byte;
        }
        ggml_tensor * norm = nullptr;
        ggml_tensor * decoded = decode_vector_graph(ctx, entry_target, page.width, &norm);
        ggml_tensor * difference = ggml_sub(ctx, decoded, target_vector);
        ggml_tensor * numerator = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, difference)));
        ggml_tensor * denominator = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, target_vector)));
        denominator = ggml_clamp(ctx, denominator, 1.0e-12f, std::numeric_limits<float>::max());
        ggml_tensor * error = ggml_div(ctx, numerator, denominator);
        execute(scope, {
            ggml_cpy(ctx, error, ggml_view_1d(ctx, scalar_output, 1, 3 * sizeof(float))),
            ggml_cpy(ctx, norm, ggml_view_1d(ctx, scalar_output, 1, 4 * sizeof(float))),
        });
        std::array<float, 2> values = {};
        ggml_backend_tensor_get(scalar_output, values.data(), 3 * sizeof(float), sizeof(values));
        return std::isfinite(values[0]) && std::isfinite(values[1]) &&
            values[1] < 1.0f - NORM_GUARD && values[0] <= VECTOR_SUCCESS;
    }

    float prediction_vector_error(const cassi_probe & prediction) {
        if (prediction.target == nullptr) {
            return 1.0f;
        }
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * difference = ggml_sub(ctx, probe_vector, target_vector);
        ggml_tensor * numerator = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, difference)));
        ggml_tensor * denominator = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, target_vector)));
        denominator = ggml_clamp(ctx, denominator, 1.0e-12f, std::numeric_limits<float>::max());
        ggml_tensor * error = ggml_div(ctx, numerator, denominator);
        execute(scope, { ggml_cpy(ctx, error, ggml_view_1d(ctx, scalar_output, 1, 3 * sizeof(float))) });
        float result = 1.0f;
        ggml_backend_tensor_get(scalar_output, &result, 3 * sizeof(float), sizeof(result));
        return std::isfinite(result) ? result : 1.0f;
    }

    static uint32_t saturating_increment(uint32_t value) {
        return std::min(COUNT_LIMIT, value + 1);
    }

    static std::array<float, CASSI_APPRENTICE_SCALE_COUNT> updated_occupancy(
        const metadata_value & metadata,
        bool merged,
        uint32_t new_teacher_observations,
        std::array<float, CASSI_APPRENTICE_SCALE_COUNT> & gains,
        std::array<float, CASSI_APPRENTICE_SCALE_COUNT> & old_factors) {
        std::array<float, CASSI_APPRENTICE_SCALE_COUNT> result = {};
        gains[0] = merged ? 1.0f / static_cast<float>(std::min(new_teacher_observations, MERGE_WINDOW)) : 1.0f;
        old_factors[0] = merged ? 1.0f - gains[0] : 0.0f;
        result[0] = 1.0f;
        for (uint32_t scale = 1; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            gains[scale] = std::min(0.5f, std::pow(SCALE_RATIO, -static_cast<float>(scale))) * result[scale - 1];
            const float old_occupancy = merged ? metadata.occupancy[scale] : 0.0f;
            old_factors[scale] = 1.0f - gains[scale];
            result[scale] = old_factors[scale] * old_occupancy + gains[scale];
        }
        return result;
    }

    void upload_metadata(const std::vector<metadata_value> & metadata) {
        if (metadata.size() > maximum_entries) {
            fail("apprentice_geometry_invalid");
        }
        const size_t values_per_entry = 6 * 8 * CASSI_APPRENTICE_SCALE_COUNT;
        std::vector<float> physical(metadata.size() * values_per_entry, 0.0f);
        for (size_t entry = 0; entry < metadata.size(); ++entry) {
            const auto & value = metadata[entry];
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                const std::array<float, 6> common = {
                    value.occupancy[scale],
                    static_cast<float>(value.teacher_observations) / 255.0f,
                    static_cast<float>(value.exact_successes) / 255.0f,
                    static_cast<float>(value.novel_successes) / 255.0f,
                    value.error_ema,
                    static_cast<float>(value.age) / 255.0f,
                };
                for (uint32_t meta = 0; meta < 6; ++meta) {
                    const size_t base = (((entry * CASSI_APPRENTICE_SCALE_COUNT + scale) * 8) * 6) + meta;
                    physical[base + 0 * 6] = PHI * common[meta];
                    physical[base + 2 * 6] = common[meta];
                }
            }
        }
        ggml_backend_tensor_set(metadata_physical, physical.data(), 0, physical.size() * sizeof(float));
    }

    ggml_tensor * build_updated_engram(
        ggml_context * ctx,
        ggml_tensor * memory,
        const cassi_field_page & page,
        uint32_t selected,
        const key_graph & query,
        const encoded_graph & target,
        const std::array<float, CASSI_APPRENTICE_SCALE_COUNT> & gains,
        const std::array<float, CASSI_APPRENTICE_SCALE_COUNT> & old_factors) {
        const uint64_t base = static_cast<uint64_t>(selected) * page.entry_stride();
        std::vector<ggml_tensor *> scales;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            std::vector<ggml_tensor *> common_real;
            std::vector<ggml_tensor *> common_imag;
            for (uint32_t block = 0; block < 3; ++block) {
                const uint64_t block_offset = base + static_cast<uint64_t>(block) * page.width;
                ggml_tensor * old_real = common_plane(ctx, memory, block_offset, page.width, scale, false);
                ggml_tensor * old_imag = common_plane(ctx, memory, block_offset, page.width, scale, true);
                ggml_tensor * source_real = block < 2 ? query.value[scale][block][0] : target.real;
                ggml_tensor * source_imag = block < 2 ? query.value[scale][block][1] : target.imag;
                common_real.push_back(ggml_add(ctx,
                    ggml_scale(ctx, old_real, old_factors[scale]),
                    ggml_scale(ctx, source_real, gains[scale])));
                common_imag.push_back(ggml_add(ctx,
                    ggml_scale(ctx, old_imag, old_factors[scale]),
                    ggml_scale(ctx, source_imag, gains[scale])));
            }
            ggml_tensor * c_real = concatenate(ctx, common_real, 0);
            ggml_tensor * c_imag = concatenate(ctx, common_imag, 0);
            ggml_tensor * zero_real = ggml_scale(ctx, c_real, 0.0f);
            ggml_tensor * zero_imag = ggml_scale(ctx, c_imag, 0.0f);
            std::vector<ggml_tensor *> components = {
                ggml_scale(ctx, c_real, PHI),
                ggml_scale(ctx, c_imag, PHI),
                c_real,
                c_imag,
                zero_real,
                zero_imag,
                zero_real,
                zero_imag,
            };
            ggml_tensor * flat = concatenate(ctx, components, 0);
            scales.push_back(ggml_reshape_3d(ctx, flat, 3LL * page.width, 8, 1));
        }
        return concatenate(ctx, scales, 2);
    }

    ggml_tensor * set_candidate_metadata(
        ggml_context * ctx,
        ggml_tensor * candidate,
        const cassi_field_page & page,
        uint32_t entry) {
        const size_t metadata_block_bytes =
            6 * 8 * CASSI_APPRENTICE_SCALE_COUNT * sizeof(float);
        ggml_tensor * metadata = ggml_view_3d(ctx, metadata_physical,
            6, 8, CASSI_APPRENTICE_SCALE_COUNT,
            metadata_physical->nb[1], metadata_physical->nb[2],
            static_cast<size_t>(entry) * metadata_block_bytes);
        const uint64_t mode = static_cast<uint64_t>(entry) * page.entry_stride() + 3ULL * page.width;
        return ggml_set(ctx, candidate, metadata,
            candidate->nb[1], candidate->nb[2], candidate->nb[3],
            mode * sizeof(float));
    }

    ggml_tensor * memory_validation(
        ggml_context * ctx,
        ggml_tensor * candidate,
        uint64_t memory_modes) {
        ggml_tensor * violation = nullptr;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            ggml_tensor * energy = nullptr;
            for (uint32_t component = 0; component < 8; ++component) {
                ggml_tensor * plane = range_plane_view(ctx, candidate, 0, memory_modes, component, scale);
                ggml_tensor * squared = ggml_sqr(ctx, plane);
                energy = energy == nullptr ? ggml_sum(ctx, squared) : ggml_add(ctx, energy, ggml_sum(ctx, squared));
                if ((component % 2) == 1) {
                    ggml_tensor * previous = range_plane_view(ctx, candidate, 0, memory_modes, component - 1, scale);
                    ggml_tensor * amplitude2 = ggml_add(ctx, ggml_sqr(ctx, previous), squared);
                    ggml_tensor * excess = ggml_sum(ctx,
                        ggml_relu(ctx, ggml_scale_bias(ctx, amplitude2, 1.0f, -MAX_AMPLITUDE * MAX_AMPLITUDE)));
                    violation = violation == nullptr ? excess : ggml_add(ctx, violation, excess);
                }
            }
            energy = ggml_scale(ctx, energy, 1.0f / static_cast<float>(memory_modes));
            ggml_tensor * energy_excess = ggml_relu(ctx, ggml_scale_bias(ctx, energy, 1.0f, -MAX_MEAN_ENERGY));
            violation = violation == nullptr ? energy_excess : ggml_add(ctx, violation, energy_excess);
            ggml_tensor * epsilon = range_plane_view(ctx, candidate, 0, memory_modes, 8, scale);
            violation = ggml_add(ctx, violation,
                ggml_sum(ctx, ggml_relu(ctx, ggml_scale_bias(ctx, epsilon, 1.0f, -EPSILON_CLIP))));
            violation = ggml_add(ctx, violation,
                ggml_sum(ctx, ggml_relu(ctx, ggml_scale(ctx, epsilon, -1.0f))));
        }
        return violation;
    }

    void commit_candidate(const cassi_field_page & page) {
        const uint64_t memory_modes = static_cast<uint64_t>(page.entries) * page.entry_stride();
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * source = static_prefix_view(ctx, candidate_memory,
            static_cast<int64_t>(memory_modes), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        execute(scope, { ggml_cpy(ctx, source, page_view(ctx, page, true)) });
    }

    cassi_observation observe(const cassi_query & query, const cassi_target & target_value) {
        const auto & page = checked_page(query.page);
        if (revision >= std::numeric_limits<uint64_t>::max() - 1) {
            fail("apprentice_field_revision_overflow");
        }
        cassi_observation result;
        result.prediction = run_probe(query);
        validate_target(page, target_value);
        const bool any_support = std::any_of(
            result.prediction.weights.begin(), result.prediction.weights.end(),
            [](float weight) { return weight > 0.0f; });
        if (target_value.is_byte) {
            result.predeposit_success = any_support && result.prediction.byte == target_value.byte;
            result.predeposit_error = result.predeposit_success ? 0.0f : 1.0f;
        } else {
            result.predeposit_error = any_support ? prediction_vector_error(result.prediction) : 1.0f;
            result.predeposit_success = result.predeposit_error <= VECTOR_SUCCESS;
        }

        std::vector<metadata_value> metadata(page.entries);
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            metadata[entry] = read_metadata(page, entry);
        }
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            if (metadata[entry].occupancy[0] >= OCCUPANCY_FLOOR) {
                metadata[entry].age = saturating_increment(metadata[entry].age);
            }
            if (result.prediction.weights[entry] <= 0.0f) {
                continue;
            }
            if (result.predeposit_success) {
                if (result.prediction.distances2[entry] <= EXACT_DISTANCE2) {
                    metadata[entry].exact_successes = saturating_increment(metadata[entry].exact_successes);
                } else {
                    metadata[entry].novel_successes = saturating_increment(metadata[entry].novel_successes);
                }
            } else {
                metadata[entry].novel_successes = 0;
                metadata[entry].error_ema =
                    (1.0f - ERROR_EMA_GAIN) * metadata[entry].error_ema +
                    ERROR_EMA_GAIN * std::min(1.0f, result.predeposit_error);
            }
        }

        uint32_t selected = UINT32_MAX;
        float selected_distance = std::numeric_limits<float>::infinity();
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            if (metadata[entry].occupancy[0] < OCCUPANCY_FLOOR ||
                result.prediction.distances2[entry] > MERGE_DISTANCE2 ||
                !entry_target_matches(page, entry, target_value)) {
                continue;
            }
            if (result.prediction.distances2[entry] < selected_distance ||
                (result.prediction.distances2[entry] == selected_distance && entry < selected)) {
                selected = entry;
                selected_distance = result.prediction.distances2[entry];
            }
        }
        result.merged = selected != UINT32_MAX;
        if (!result.merged) {
            for (uint32_t entry = 0; entry < page.entries; ++entry) {
                if (metadata[entry].occupancy[0] < OCCUPANCY_FLOOR) {
                    selected = entry;
                    break;
                }
            }
            if (selected == UINT32_MAX) {
                float best_score = std::numeric_limits<float>::infinity();
                for (uint32_t entry = 0; entry < page.entries; ++entry) {
                    const auto & value = metadata[entry];
                    const float score =
                        static_cast<float>(value.exact_successes + 2 * value.novel_successes + value.teacher_observations) /
                        static_cast<float>(1 + value.age);
                    if (score < best_score) {
                        best_score = score;
                        selected = entry;
                    }
                }
                result.evicted = true;
                evictions++;
            }
            metadata[selected] = {};
        }
        result.entry = selected;
        metadata_value original_selected = read_metadata(page, selected);
        if (!result.merged) {
            original_selected = {};
        }
        metadata[selected].teacher_observations =
            result.merged ? saturating_increment(metadata[selected].teacher_observations) : 1;
        metadata[selected].age = 0;
        std::array<float, CASSI_APPRENTICE_SCALE_COUNT> gains = {};
        std::array<float, CASSI_APPRENTICE_SCALE_COUNT> old_factors = {};
        metadata[selected].occupancy = updated_occupancy(
            original_selected, result.merged, metadata[selected].teacher_observations, gains, old_factors);
        upload_metadata(metadata);

        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * memory = page_view(ctx, page, true);
        const uint64_t memory_modes = static_cast<uint64_t>(page.entries) * page.entry_stride();
        ggml_tensor * candidate = ggml_cont_3d(ctx, memory,
            static_cast<int64_t>(memory_modes), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        if (!result.merged) {
            ggml_tensor * zero = static_prefix_view(ctx, zero_entry,
                static_cast<int64_t>(page.entry_stride()), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
            candidate = ggml_set(ctx, candidate, zero,
                candidate->nb[1], candidate->nb[2], candidate->nb[3],
                static_cast<uint64_t>(selected) * page.entry_stride() * sizeof(float));
        }
        key_graph key = build_query_graph(ctx, page);
        encoded_graph target = build_target_graph(ctx, page, target_value);
        ggml_tensor * updated = build_updated_engram(
            ctx, memory, page, selected, key, target, gains, old_factors);
        candidate = ggml_set(ctx, candidate, updated,
            candidate->nb[1], candidate->nb[2], candidate->nb[3],
            static_cast<uint64_t>(selected) * page.entry_stride() * sizeof(float));
        for (uint32_t entry = 0; entry < page.entries; ++entry) {
            candidate = set_candidate_metadata(ctx, candidate, page, entry);
        }

        const uint64_t selected_base = static_cast<uint64_t>(selected) * page.entry_stride();
        ggml_tensor * yang_real = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 0, 0);
        (void) yang_real;
        std::vector<ggml_tensor *> epsilon_scales;
        for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
            ggml_tensor * y_real = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 0, scale);
            ggml_tensor * y_imag = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 1, scale);
            ggml_tensor * i_real = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 2, scale);
            ggml_tensor * i_imag = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 3, scale);
            ggml_tensor * imbalance = ggml_sub(ctx,
                ggml_add(ctx, ggml_sqr(ctx, y_real), ggml_sqr(ctx, y_imag)),
                ggml_scale(ctx, ggml_add(ctx, ggml_sqr(ctx, i_real), ggml_sqr(ctx, i_imag)), PHI));
            ggml_tensor * epsilon_target = ggml_clamp(ctx, ggml_sqr(ctx, imbalance), 0.0f, EPSILON_CLIP);
            ggml_tensor * epsilon_old = range_plane_view(ctx, candidate, selected_base, page.entry_stride(), 8, scale);
            ggml_tensor * epsilon = ggml_add(ctx,
                ggml_scale(ctx, epsilon_old, 1.0f - EPSILON_TAU),
                ggml_scale(ctx, epsilon_target, EPSILON_TAU));
            epsilon_scales.push_back(ggml_reshape_3d(ctx, epsilon, page.entry_stride(), 1, 1));
        }
        ggml_tensor * epsilon = concatenate(ctx, epsilon_scales, 2);
        candidate = ggml_set(ctx, candidate, epsilon,
            candidate->nb[1], candidate->nb[2], candidate->nb[3],
            selected_base * sizeof(float) + 8 * candidate->nb[1]);

        ggml_tensor * validation = memory_validation(ctx, candidate, memory_modes);
        ggml_tensor * candidate_out = static_prefix_view(ctx, candidate_memory,
            static_cast<int64_t>(memory_modes), CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        execute(scope, {
            ggml_cpy(ctx, candidate, candidate_out),
            ggml_cpy(ctx, validation, candidate_validation),
        });
        float violation = 0.0f;
        ggml_backend_tensor_get(candidate_validation, &violation, 0, sizeof(violation));
        if (!std::isfinite(violation) || violation > 1.0e-5f) {
            fail("apprentice_field_bounds_exceeded");
        }
        commit_candidate(page);
        revision++;
        return result;
    }

    uint8_t guide_byte(uint8_t byte) {
        auto & resource = width_resource(512);
        ggml_backend_tensor_memset(resource.probe_encoded, 0, 0, ggml_nbytes(resource.probe_encoded));
        const int32_t index = byte;
        ggml_backend_tensor_set(byte_input, &index, 0, sizeof(index));
        for (uint32_t round = 0; round < GUIDE_ROUNDS; ++round) {
            graph_scope scope;
            ggml_context * ctx = scope.context.get();
            ggml_tensor * target = ggml_reshape_2d(ctx,
                ggml_get_rows(ctx, resource.byte_codebooks, byte_input), 512, 2);
            ggml_tensor * port = ggml_add(ctx,
                ggml_scale(ctx, resource.probe_encoded, 1.0f - BYTE_GUIDE_GAIN),
                ggml_scale(ctx, target, BYTE_GUIDE_GAIN));
            ggml_tensor * scores = ggml_mul_mat(ctx, resource.byte_codebooks, ggml_reshape_1d(ctx, port, 1024));
            execute(scope, {
                ggml_cpy(ctx, port, resource.probe_encoded),
                ggml_cpy(ctx, scores, resource.byte_scores),
            });
            std::array<float, 256> host_scores = {};
            ggml_backend_tensor_get(resource.byte_scores, host_scores.data(), 0, sizeof(host_scores));
            const uint8_t emitted = static_cast<uint8_t>(
                std::distance(host_scores.begin(), std::max_element(host_scores.begin(), host_scores.end())));
            if (emitted == byte) {
                return emitted;
            }
        }
        fail("apprentice_assimilation_failed");
    }

    ggml_tensor * guide_vector_result(ggml_tensor * vector) {
        if (vector == nullptr || vector->type != GGML_TYPE_F32 || !ggml_is_contiguous(vector) ||
            ggml_nelements(vector) != cfg.embedding_width || vector->buffer == nullptr) {
            fail("apprentice_target_invalid");
        }
        ggml_backend_tensor_copy(vector, target_vector);
        const uint32_t width = service_width(cfg.embedding_width);
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        encoded_graph encoded = bounded_vector(ctx, target_vector, width);
        ggml_tensor * norm = nullptr;
        ggml_tensor * restored = decode_vector_graph(ctx, encoded, width, &norm);
        ggml_tensor * difference = ggml_sub(ctx, restored, target_vector);
        ggml_tensor * numerator = ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, difference)));
        ggml_tensor * denominator = ggml_clamp(ctx,
            ggml_sqrt(ctx, ggml_sum(ctx, ggml_sqr(ctx, target_vector))),
            1.0e-12f, std::numeric_limits<float>::max());
        ggml_tensor * error = ggml_div(ctx, numerator, denominator);
        execute(scope, {
            ggml_cpy(ctx, restored, guided_vector),
            ggml_cpy(ctx, error, ggml_view_1d(ctx, scalar_output, 1, 3 * sizeof(float))),
            ggml_cpy(ctx, norm, ggml_view_1d(ctx, scalar_output, 1, 4 * sizeof(float))),
        });
        std::array<float, 2> values = {};
        ggml_backend_tensor_get(scalar_output, values.data(), 3 * sizeof(float), sizeof(values));
        if (!std::isfinite(values[0]) || !std::isfinite(values[1]) ||
            values[1] >= 1.0f - NORM_GUARD || values[0] > GUIDED_VECTOR_TOLERANCE) {
            fail("apprentice_assimilation_failed");
        }
        return guided_vector;
    }
    ggml_tensor * add_vectors(ggml_tensor * left, ggml_tensor * right) {
        const auto valid = [&](ggml_tensor * value) {
            return value != nullptr && value->type == GGML_TYPE_F32 && ggml_is_contiguous(value) &&
                ggml_nelements(value) == cfg.embedding_width && value->buffer != nullptr;
        };
        if (!valid(left) || !valid(right)) {
            fail("apprentice_service_vector_invalid");
        }
        ggml_backend_tensor_copy(left, input_vector);
        ggml_backend_tensor_copy(right, target_vector);
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * sum = ggml_add(ctx, input_vector, target_vector);
        execute(scope, { ggml_cpy(ctx, sum, guided_vector) });
        return guided_vector;
    }
    ggml_tensor * copy_vector(ggml_tensor * source, uint32_t slot) {
        if (source == nullptr || source->type != GGML_TYPE_F32 || !ggml_is_contiguous(source) ||
                ggml_nelements(source) != cfg.embedding_width || source->buffer == nullptr ||
                slot >= handoff_vectors.size()) {
            fail("apprentice_service_vector_invalid");
        }
        ggml_backend_tensor_copy(source, handoff_vectors[slot]);
        ggml_backend_synchronize(backend.get());
        return handoff_vectors[slot];
    }

    ggml_tensor * load_vector(const float * data, size_t count) {
        if (data == nullptr || count != cfg.embedding_width) {
            fail("apprentice_service_vector_invalid");
        }
        for (size_t index = 0; index < count; ++index) {
            if (!std::isfinite(data[index])) {
                fail("apprentice_service_vector_nonfinite");
            }
        }
        ggml_backend_tensor_set(boundary_vector, data, 0, count * sizeof(float));
        return boundary_vector;
    }

    size_t context_snapshot_bytes() const {
        uint64_t modes = 0;
        for (const cassi_field_page & page : page_descriptors) {
            modes = checked_add(modes, page.width, "apprentice_geometry_overflow");
        }
        return static_cast<size_t>(checked_mul(
            checked_mul(modes, CASSI_APPRENTICE_SCALE_COUNT * CASSI_APPRENTICE_COMPONENT_COUNT,
                "apprentice_geometry_overflow"),
            sizeof(float), "apprentice_geometry_overflow"));
    }

    void context_snapshot_get(void * destination, size_t size) const {
        if (destination == nullptr || size != context_snapshot_bytes()) {
            fail("apprentice_state_buffer_invalid");
        }
        uint8_t * output = static_cast<uint8_t *>(destination);
        size_t output_offset = 0;
        ggml_backend_synchronize(backend.get());
        for (const cassi_field_page & page : page_descriptors) {
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                for (uint32_t component = 0; component < CASSI_APPRENTICE_COMPONENT_COUNT; ++component) {
                    const size_t field_offset = static_cast<size_t>(
                        (static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * mode_count +
                        page.mode_offset) * sizeof(float);
                    const size_t bytes = static_cast<size_t>(page.width) * sizeof(float);
                    ggml_backend_tensor_get(field, output + output_offset, field_offset, bytes);
                    output_offset += bytes;
                }
            }
        }
    }

    void context_snapshot_set(const void * source, size_t size) {
        if (source == nullptr || size != context_snapshot_bytes()) {
            fail("apprentice_state_buffer_invalid");
        }
        const uint8_t * input = static_cast<const uint8_t *>(source);
        size_t input_offset = 0;
        for (const cassi_field_page & page : page_descriptors) {
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                for (uint32_t component = 0; component < CASSI_APPRENTICE_COMPONENT_COUNT; ++component) {
                    const size_t field_offset = static_cast<size_t>(
                        (static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * mode_count +
                        page.mode_offset) * sizeof(float);
                    const size_t bytes = static_cast<size_t>(page.width) * sizeof(float);
                    ggml_backend_tensor_set(field, input + input_offset, field_offset, bytes);
                    input_offset += bytes;
                }
            }
        }
        ggml_backend_synchronize(backend.get());
    }


    std::vector<uint8_t> profile_serialization() const {
        std::vector<uint8_t> bytes;
        for (const char * value : {
                 "cassi.qi.apprentice-engram.v1",
                 "cassi.qi.native-linear-scale-component-mode.v2",
                 "cassi.qi.scale-prime-quadratic-chirp.v2",
                 "sense-ema-oscillator-v1",
                 "bounded-common-engram-v1",
                 "compact-kernel-audit-v1",
                 "token-u32le-four-byte-v1" }) {
            append_string(bytes, value);
        }
        for (const char * component : COMPONENT_NAMES) {
            append_string(bytes, component);
        }
        append_u32(bytes, CASSI_APPRENTICE_SCALE_COUNT);
        append_u32(bytes, 1);
        append_u32(bytes, static_cast<uint32_t>(page_descriptors.size()));
        for (const auto & page : page_descriptors) {
            append_u32(bytes, page.kind);
            append_i32(bytes, page.layer);
            append_u32(bytes, page.width);
            append_u32(bytes, page.entries);
            append_u64(bytes, page.mode_offset);
        }
        std::vector<uint32_t> widths;
        for (const auto & page : page_descriptors) {
            widths.push_back(page.width);
        }
        std::sort(widths.begin(), widths.end());
        widths.erase(std::unique(widths.begin(), widths.end()), widths.end());
        append_u32(bytes, static_cast<uint32_t>(widths.size()));
        for (uint32_t width : widths) {
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                append_u32(bytes, width);
                append_u32(bytes, scale);
                append_u32(bytes, PRIMES[scale]);
                for (uint32_t coefficient : COEFFICIENTS[scale]) {
                    append_u32(bytes, coefficient);
                }
                append_u32(bytes, PERMUTATIONS[scale][0]);
                append_u32(bytes, PERMUTATIONS[scale][1]);
            }
        }
        for (float value : {
                 PHI, SCALE_RATIO, SENSING_GAIN, DT, FAST_OMEGA2, SLOW_OMEGA2,
                 FAST_DAMPING, SLOW_DAMPING, MODE_SLOPE, NONLINEAR_GAIN,
                 MAX_AMPLITUDE, MAX_MEAN_ENERGY, EPSILON_TAU, EPSILON_CLIP,
                 TEXT_RADIUS, VECTOR_RADIUS, EXACT_DISTANCE2, MERGE_DISTANCE2,
                 WEIGHT_FLOOR, SCATTER_CEILING, BYTE_GUIDE_GAIN, VECTOR_GUIDE_GAIN,
                 NORM_GUARD, VECTOR_SUCCESS, GUIDED_VECTOR_TOLERANCE,
                 ERROR_EMA_GAIN, THRESHOLD_ABS_GUARD, THRESHOLD_REL_GUARD,
                 OCCUPANCY_FLOOR }) {
            append_f32(bytes, value);
        }
        for (uint32_t value : {
                 COUNT_LIMIT, MERGE_WINDOW, TOKEN_BYTE_COUNT, GUIDE_ROUNDS,
                 MIN_OBSERVATIONS, MIN_EXACT_SUCCESSES, MIN_NOVEL_SUCCESSES }) {
            append_u32(bytes, value);
        }
        return bytes;
    }

    void profile_hash(uint8_t digest[32]) const {
        const auto bytes = profile_serialization();
        sha256_hash(digest, bytes.data(), bytes.size());
    }

    void field_hash(uint8_t digest[32]) const {
        std::vector<uint8_t> bytes(state_bytes);
        ggml_backend_tensor_get(field, bytes.data(), 0, bytes.size());
        sha256_hash(digest, bytes.data(), bytes.size());
    }

    void validate_state(const float * values) const {
        if (values == nullptr) {
            fail("apprentice_checkpoint_invalid");
        }
        const auto at = [&](uint32_t scale, uint32_t component, uint64_t mode) -> float {
            return values[(static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * mode_count + mode];
        };
        for (uint64_t index = 0; index < state_bytes / sizeof(float); ++index) {
            if (!std::isfinite(values[index])) {
                fail("apprentice_checkpoint_invalid");
            }
        }
        for (const auto & page : page_descriptors) {
            for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                for (const auto partition : {
                         std::pair<uint64_t, uint64_t>{ page.mode_offset, page.width },
                         std::pair<uint64_t, uint64_t>{ page.memory_offset(), static_cast<uint64_t>(page.entries) * page.entry_stride() } }) {
                    double energy = 0.0;
                    for (uint64_t local = 0; local < partition.second; ++local) {
                        const uint64_t mode = partition.first + local;
                        for (uint32_t component = 0; component < 8; component += 2) {
                            const double real = at(scale, component, mode);
                            const double imag = at(scale, component + 1, mode);
                            if (real * real + imag * imag > MAX_AMPLITUDE * MAX_AMPLITUDE + 1.0e-5) {
                                fail("apprentice_checkpoint_invalid");
                            }
                            energy += real * real + imag * imag;
                        }
                        const float epsilon = at(scale, 8, mode);
                        if (epsilon < 0.0f || epsilon > EPSILON_CLIP) {
                            fail("apprentice_checkpoint_invalid");
                        }
                    }
                    if (energy / static_cast<double>(partition.second) > MAX_MEAN_ENERGY + 1.0e-5) {
                        fail("apprentice_checkpoint_invalid");
                    }
                }
            }
            for (uint32_t entry = 0; entry < page.entries; ++entry) {
                const uint64_t base = page.memory_offset() + static_cast<uint64_t>(entry) * page.entry_stride() + 3ULL * page.width;
                for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                    const auto common_at = [&](uint32_t meta, bool imaginary) {
                        const uint32_t yc = imaginary ? 1 : 0;
                        const uint32_t ic = imaginary ? 3 : 2;
                        return (PHI * at(scale, yc, base + meta) + at(scale, ic, base + meta)) / DENOMINATOR;
                    };
                    const float occupancy = common_at(0, false);
                    if (occupancy < 0.0f || occupancy > 1.0f || std::abs(common_at(0, true)) > 1.0e-5f) {
                        fail("apprentice_checkpoint_invalid");
                    }
                    for (uint32_t meta = 1; meta < 6; ++meta) {
                        const float value = common_at(meta, false);
                        if (std::abs(common_at(meta, true)) > 1.0e-5f) {
                            fail("apprentice_checkpoint_invalid");
                        }
                        if (meta != 4) {
                            const float scaled = 255.0f * value;
                            if (std::abs(scaled - std::round(scaled)) > 1.0e-4f ||
                                scaled < 0.0f || scaled > 255.0f) {
                                fail("apprentice_checkpoint_invalid");
                            }
                        } else if (value < 0.0f || value > 1.0f) {
                            fail("apprentice_checkpoint_invalid");
                        }
                    }
                    if (occupancy >= OCCUPANCY_FLOOR && page.kind != CASSI_FIELD_TEXT) {
                        const uint64_t entry_base = base - 3ULL * page.width;
                        const double norm_limit =
                            static_cast<double>(1.0f - NORM_GUARD) * (1.0f - NORM_GUARD);
                        const uint32_t vector_count = page.kind == CASSI_FIELD_HEAD ? 2 : 3;
                        for (uint32_t vector = 0; vector < vector_count; ++vector) {
                            double norm2 = 0.0;
                            for (uint32_t mode = 0; mode < page.width; ++mode) {
                                const uint64_t index = entry_base +
                                    static_cast<uint64_t>(vector) * page.width + mode;
                                const double real =
                                    (PHI * at(scale, 0, index) + at(scale, 2, index)) / DENOMINATOR;
                                const double imag =
                                    (PHI * at(scale, 1, index) + at(scale, 3, index)) / DENOMINATOR;
                                norm2 += real * real + imag * imag;
                            }
                            if (!std::isfinite(norm2) || norm2 >= norm_limit) {
                                fail("apprentice_checkpoint_invalid");
                            }
                        }
                    }
                }
            }
        }
    }

    void state_get(void * destination, size_t size) const {
        if (destination == nullptr || size != state_bytes) {
            fail("apprentice_state_buffer_invalid");
        }
        ggml_backend_tensor_get(field, destination, 0, size);
    }

    void state_set(const void * source, size_t size, uint64_t new_revision, uint64_t new_evictions) {
        if (source == nullptr || size != state_bytes) {
            fail("apprentice_checkpoint_invalid");
        }
        validate_state(static_cast<const float *>(source));
        ggml_backend_tensor_set(field, source, 0, size);
        revision = new_revision;
        evictions = new_evictions;
    }

    void download_page(const cassi_field_page & descriptor, std::vector<float> & destination_values) {
        const uint64_t memory_modes =
            static_cast<uint64_t>(descriptor.entries) * descriptor.entry_stride();
        const size_t value_count =
            static_cast<size_t>(memory_modes) * CASSI_APPRENTICE_COMPONENT_COUNT * CASSI_APPRENTICE_SCALE_COUNT;
        destination_values.resize(value_count);
        graph_scope scope;
        ggml_context * ctx = scope.context.get();
        ggml_tensor * destination = static_prefix_view(
            ctx, candidate_memory, static_cast<int64_t>(memory_modes),
            CASSI_APPRENTICE_COMPONENT_COUNT, CASSI_APPRENTICE_SCALE_COUNT);
        execute(scope, { ggml_cpy(ctx, page_view(ctx, descriptor, true), destination) });
        ggml_backend_tensor_get(candidate_memory, destination_values.data(), 0, value_count * sizeof(float));
    }


    bool page_mature(uint32_t page_index) {
        const auto & descriptor = checked_page(page_index);
        std::vector<metadata_value> metadata(descriptor.entries);
        std::vector<uint32_t> mature_entries;
        mature_entries.reserve(descriptor.entries);
        for (uint32_t entry = 0; entry < descriptor.entries; ++entry) {
            metadata[entry] = read_metadata(descriptor, entry);
            if (metadata[entry].occupancy[0] >= OCCUPANCY_FLOOR &&
                    metadata[entry].teacher_observations >= MIN_OBSERVATIONS &&
                    metadata[entry].exact_successes >= MIN_EXACT_SUCCESSES &&
                    metadata[entry].error_ema <= VECTOR_SUCCESS) {
                mature_entries.push_back(entry);
            }
        }
        if (mature_entries.size() < 2) {
            return false;
        }

        const uint64_t memory_modes =
            static_cast<uint64_t>(descriptor.entries) * descriptor.entry_stride();
        download_page(descriptor, page_host);

        const auto common = [&](uint32_t scale, uint32_t component, uint64_t mode) {
            const size_t plane = static_cast<size_t>(memory_modes);
            const float yang = page_host[(static_cast<size_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT +
                component) * plane + static_cast<size_t>(mode)];
            const float yin = page_host[(static_cast<size_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT +
                component + 2) * plane + static_cast<size_t>(mode)];
            return (PHI * yang + yin) / DENOMINATOR;
        };
        for (size_t left_index = 0; left_index < mature_entries.size(); ++left_index) {
            const uint32_t left = mature_entries[left_index];
            const uint64_t left_base = static_cast<uint64_t>(left) * descriptor.entry_stride();
            for (size_t right_index = left_index + 1; right_index < mature_entries.size(); ++right_index) {
                const uint32_t right = mature_entries[right_index];
                const uint64_t right_base = static_cast<uint64_t>(right) * descriptor.entry_stride();
                double key_distance = 0.0;
                double target_distance = 0.0;
                uint32_t available_scales = 0;
                for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
                    const float left_occupancy = metadata[left].occupancy[scale];
                    const float right_occupancy = metadata[right].occupancy[scale];
                    if (left_occupancy < OCCUPANCY_FLOOR || right_occupancy < OCCUPANCY_FLOOR) {
                        continue;
                    }
                    available_scales++;
                    for (uint32_t block = 0; block < 2; ++block) {
                        for (uint32_t part = 0; part < 2; ++part) {
                            const uint32_t component = part == 0 ? 0 : 1;
                            for (uint32_t mode = 0; mode < descriptor.width; ++mode) {
                                const float left_value = common(
                                    scale, component,
                                    left_base + static_cast<uint64_t>(block) * descriptor.width + mode) /
                                    left_occupancy;
                                const float right_value = common(
                                    scale, component,
                                    right_base + static_cast<uint64_t>(block) * descriptor.width + mode) /
                                    right_occupancy;
                                const double difference = static_cast<double>(left_value) - right_value;
                                key_distance += difference * difference;
                            }
                        }
                    }
                    for (uint32_t part = 0; part < 2; ++part) {
                        const uint32_t component = part == 0 ? 0 : 1;
                        for (uint32_t mode = 0; mode < descriptor.width; ++mode) {
                            const float left_value = common(
                                scale, component,
                                left_base + 2ULL * descriptor.width + mode) / left_occupancy;
                            const float right_value = common(
                                scale, component,
                                right_base + 2ULL * descriptor.width + mode) / right_occupancy;
                            const double difference = static_cast<double>(left_value) - right_value;
                            target_distance += difference * difference;
                        }
                    }
                }
                if (available_scales != 0 &&
                        key_distance / available_scales <= EXACT_DISTANCE2 &&
                        target_distance / available_scales > EXACT_DISTANCE2) {
                    return false;
                }
            }
        }
        return true;
    }

};

llama_cassi_field::llama_cassi_field(const cassi_field_config & config) : pimpl(new impl(config)) {}
llama_cassi_field::~llama_cassi_field() = default;

void llama_cassi_field::reset_context() { pimpl->reset_context(); }
void llama_cassi_field::sense_marker(uint16_t symbol) { pimpl->sense_marker(symbol); }
void llama_cassi_field::sense_token(int32_t token, const std::string & piece, bool eog) { pimpl->sense_token(token, piece, eog); }
cassi_probe llama_cassi_field::probe(const cassi_query & query) { return pimpl->probe(query); }
cassi_observation llama_cassi_field::observe(const cassi_query & query, const cassi_target & target) {
    return pimpl->observe(query, target);
}
uint8_t llama_cassi_field::guide_byte(uint8_t byte) { return pimpl->guide_byte(byte); }
ggml_tensor * llama_cassi_field::guide_vector(ggml_tensor * vector) {
    return pimpl->guide_vector_result(vector);
}
ggml_tensor * llama_cassi_field::add_vectors(ggml_tensor * left, ggml_tensor * right) {
    return pimpl->add_vectors(left, right);
}
ggml_tensor * llama_cassi_field::copy_vector(ggml_tensor * source, uint32_t slot) {
    return pimpl->copy_vector(source, slot);
}
ggml_tensor * llama_cassi_field::load_vector(const float * data, size_t count) {
    return pimpl->load_vector(data, count);
}
size_t llama_cassi_field::context_snapshot_size() const { return pimpl->context_snapshot_bytes(); }
void llama_cassi_field::context_snapshot_get(void * destination, size_t size) const {
    pimpl->context_snapshot_get(destination, size);
}
void llama_cassi_field::context_snapshot_set(const void * source, size_t size) {
    pimpl->context_snapshot_set(source, size);
}

size_t llama_cassi_field::state_size() const { return static_cast<size_t>(pimpl->state_bytes); }
void llama_cassi_field::state_get(void * destination, size_t size) const { pimpl->state_get(destination, size); }
void llama_cassi_field::state_set(
        const void * source, size_t size, uint64_t revision, uint64_t evictions) {
    pimpl->state_set(source, size, revision, evictions);
}
void llama_cassi_field::field_sha256(uint8_t digest[32]) const { pimpl->field_hash(digest); }
void llama_cassi_field::profile_sha256(uint8_t digest[32]) const { pimpl->profile_hash(digest); }
bool llama_cassi_field::page_mature(uint32_t page_index) { return pimpl->page_mature(page_index); }

const cassi_field_config & llama_cassi_field::config() const { return pimpl->cfg; }
const std::vector<cassi_field_page> & llama_cassi_field::pages() const { return pimpl->page_descriptors; }
const cassi_field_page & llama_cassi_field::page(uint32_t index) const { return pimpl->checked_page(index); }
uint64_t llama_cassi_field::modes() const { return pimpl->mode_count; }
uint64_t llama_cassi_field::field_bytes() const { return pimpl->state_bytes; }
uint64_t llama_cassi_field::minimum_field_bytes() const { return pimpl->minimum_bytes; }
uint64_t llama_cassi_field::field_revision() const { return pimpl->revision; }
uint64_t llama_cassi_field::engram_evictions() const { return pimpl->evictions; }
const std::string & llama_cassi_field::backend_name() const { return pimpl->selected_backend; }
uint64_t llama_cassi_field::backend_allocation_bytes() const {
    return pimpl->static_buffer ? ggml_backend_buffer_get_size(pimpl->static_buffer.get()) : 0;
}
