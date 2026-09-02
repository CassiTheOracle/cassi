#include "common.h"
#include "ggml-backend.h"
#include "ggml-cpp.h"
#include "ggml.h"
#include "llama.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr int64_t MODE_COUNT = 6144;
constexpr int64_t WAVE_MODE_COUNT = 3072;
constexpr int64_t SCALE_COUNT = 4;
constexpr int64_t STATE_STRIDE = 9 * MODE_COUNT * SCALE_COUNT;
constexpr float PHI = 1.618033988749895f;
constexpr float SCALE_RATIO = 4.2360679775f;
constexpr float READ_FLOOR = 0.05f;

struct options {
    std::string model;
    std::string state;
    std::string out_state;
    std::string mode = "coupled";
    std::string prompt = "Cassi";
    int tokens = 4;
    int gpu_layers = 99;
    int field_layer = -1;
};

options parse_options(int argc, char ** argv) {
    options result;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (i + 1 >= argc) {
            throw std::runtime_error("missing value after " + key);
        }
        const std::string value = argv[++i];
        if (key == "--model") result.model = value;
        else if (key == "--state") result.state = value;
        else if (key == "--out-state") result.out_state = value;
        else if (key == "--mode") result.mode = value;
        else if (key == "--prompt") result.prompt = value;
        else if (key == "--tokens") result.tokens = std::stoi(value);
        else if (key == "--gpu-layers") result.gpu_layers = std::stoi(value);
        else if (key == "--field-layer") result.field_layer = std::stoi(value);
        else throw std::runtime_error("unknown option: " + key);
    }
    if (result.model.empty() || result.state.empty()) {
        throw std::runtime_error("--model and --state are required");
    }
    if (result.mode != "coupled" && result.mode != "field") {
        throw std::runtime_error("--mode must be coupled or field");
    }
    if (result.tokens < 1) {
        throw std::runtime_error("--tokens must be positive");
    }
    return result;
}

std::vector<float> read_state(const std::string & path) {
    const size_t bytes = STATE_STRIDE * sizeof(float);
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream || stream.tellg() != static_cast<std::streamoff>(bytes)) {
        throw std::runtime_error("state must contain exactly 221184 raw F32 values: " + path);
    }
    stream.seekg(0);
    std::vector<float> state(STATE_STRIDE);
    stream.read(reinterpret_cast<char *>(state.data()), static_cast<std::streamsize>(bytes));
    if (!stream) {
        throw std::runtime_error("failed to read state: " + path);
    }
    return state;
}

void write_state(const std::string & path, const std::vector<float> & state) {
    if (path.empty()) return;
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    stream.write(reinterpret_cast<const char *>(state.data()),
                 static_cast<std::streamsize>(state.size() * sizeof(float)));
    if (!stream) {
        throw std::runtime_error("failed to write state: " + path);
    }
}

uint64_t fnv1a(const std::vector<float> & values) {
    uint64_t hash = UINT64_C(1469598103934665603);
    const auto * bytes = reinterpret_cast<const uint8_t *>(values.data());
    for (size_t i = 0; i < values.size() * sizeof(float); ++i) {
        hash ^= bytes[i];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

float score_token(const std::vector<float> & state, llama_token token) {
    uint32_t mixed = (uint32_t) token * 2654435761u + 2246822519u;
    const float phase = 6.2831853071795864769f * float(mixed & 0x00ffffffu) / 16777216.0f;
    const float phase_re = std::cos(phase);
    const float phase_im = std::sin(phase);
    float score = 0.0f;
    float scale_weight = 1.0f;
    for (int64_t scale = 0; scale < SCALE_COUNT; ++scale) {
        const int64_t active_mode = mixed % WAVE_MODE_COUNT;
        const float * active = state.data() + (scale * MODE_COUNT + active_mode) * 9;
        const float context_re = active[0] - PHI * active[2];
        const float context_im = active[1] - PHI * active[3];
        const float context_norm = std::sqrt(context_re * context_re + context_im * context_im);
        score += scale_weight * (context_re * phase_re + context_im * phase_im)
            / std::max(READ_FLOOR, context_norm);
        const int64_t memory_mode = WAVE_MODE_COUNT
            + ((mixed ^ (mixed >> 16)) % (MODE_COUNT - WAVE_MODE_COUNT));
        const float * memory = state.data() + (scale * MODE_COUNT + memory_mode) * 9;
        const float memory_re = PHI * memory[0] + memory[2];
        const float memory_im = PHI * memory[1] + memory[3];
        const float memory_norm = std::sqrt(memory_re * memory_re + memory_im * memory_im);
        score += 0.5f * scale_weight * (memory_re * phase_re + memory_im * phase_im)
            / std::max(READ_FLOOR, memory_norm);
        scale_weight /= SCALE_RATIO;
        mixed = mixed * 1664525u + 1013904223u;
    }
    return std::isfinite(score) ? score : -INFINITY;
}

llama_token field_argmax(const std::vector<float> & state, int32_t vocab_size) {
    llama_token best_token = 0;
    float best_score = -INFINITY;
    for (llama_token token = 0; token < vocab_size; ++token) {
        const float score = score_token(state, token);
        if (score > best_score) {
            best_score = score;
            best_token = token;
        }
    }
    return best_token;
}

class field_stepper {
public:
    field_stepper() {
        backend = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
        if (backend == nullptr) {
            throw std::runtime_error("CPU backend is unavailable");
        }
        mode_params.resize(MODE_COUNT);
        for (int64_t m = 0; m < MODE_COUNT; ++m) {
            mode_params[m] = 0.01f + float(m) / float(MODE_COUNT - 1) * 0.49f;
        }
    }

    ~field_stepper() {
        if (backend != nullptr) ggml_backend_free(backend);
    }

    void advance(std::vector<float> & state, llama_token token) {
        std::vector<float> sense(2 * WAVE_MODE_COUNT, 0.0f);
        uint32_t mixed = (uint32_t) token * 2654435761u + 2246822519u;
        constexpr int source_count = 64;
        constexpr float amplitude = 0.125f;
        for (int i = 0; i < source_count; ++i) {
            mixed = mixed * 1664525u + 1013904223u;
            const int64_t mode = mixed % WAVE_MODE_COUNT;
            const float phase = 6.2831853071795864769f * float(mixed & 0x00ffffffu) / 16777216.0f;
            sense[2 * mode + 0] += amplitude * std::cos(phase);
            sense[2 * mode + 1] += amplitude * std::sin(phase);
        }
        const int32_t sequence_id = 0;
        ggml_init_params init_params = {
            /*.mem_size   =*/ 16 * 1024 * 1024,
            /*.mem_buffer =*/ nullptr,
            /*.no_alloc   =*/ true,
        };
        ggml_context_ptr context(ggml_init(init_params));
        if (!context) throw std::runtime_error("failed to initialize GGML context");
        ggml_tensor * sense_tensor = ggml_new_tensor_2d(
            context.get(), GGML_TYPE_F32, 2 * WAVE_MODE_COUNT, 1);
        ggml_tensor * state_tensor = ggml_new_tensor_2d(
            context.get(), GGML_TYPE_F32, STATE_STRIDE, 1);
        ggml_tensor * mode_tensor = ggml_new_tensor_1d(context.get(), GGML_TYPE_F32, MODE_COUNT);
        ggml_tensor * sequence_tensor = ggml_new_tensor_1d(context.get(), GGML_TYPE_I32, 1);
        ggml_tensor * output = ggml_cassi_qi_field_step(
            context.get(), sense_tensor, state_tensor, mode_tensor, sequence_tensor,
            SCALE_COUNT, PHI, 0.005f, 0.5f, 0.01f, 0.5f,
            0.618033988749895f, SCALE_RATIO, 1.0e-6f, READ_FLOOR, 1);
        ggml_cgraph * graph = ggml_new_graph_custom(context.get(), GGML_DEFAULT_GRAPH_SIZE, false);
        ggml_build_forward_expand(graph, output);
        ggml_backend_buffer_ptr buffer(ggml_backend_alloc_ctx_tensors(context.get(), backend));
        if (!buffer) throw std::runtime_error("failed to allocate field graph");
        ggml_backend_tensor_set(sense_tensor, sense.data(), 0, sense.size() * sizeof(float));
        ggml_backend_tensor_set(state_tensor, state.data(), 0, state.size() * sizeof(float));
        ggml_backend_tensor_set(mode_tensor, mode_params.data(), 0, mode_params.size() * sizeof(float));
        ggml_backend_tensor_set(sequence_tensor, &sequence_id, 0, sizeof(sequence_id));
        if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS) {
            throw std::runtime_error("field transition failed");
        }
        const size_t state_offset = 2 * WAVE_MODE_COUNT * sizeof(float);
        ggml_backend_tensor_get(output, state.data(), state_offset, state.size() * sizeof(float));
    }

private:
    ggml_backend_t backend = nullptr;
    std::vector<float> mode_params;
};

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;
using sampler_ptr = std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)>;

int run_coupled(const options & opt, std::vector<float> state) {
    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = opt.gpu_layers;
    model_ptr model(llama_model_load_from_file(opt.model.c_str(), model_params), llama_model_free);
    if (!model) throw std::runtime_error("failed to load model");
    const int n_layers = llama_model_n_layer(model.get());
    const int field_layer = opt.field_layer >= 0 ? opt.field_layer : n_layers / 2;

    llama_context_params context_params = llama_context_default_params();
    context_params.n_ctx = 256;
    context_params.n_batch = 128;
    context_params.n_ubatch = 128;
    context_params.cassi_modal = false;
    context_params.cassi_field_step = false;
    context_params.cassi_qi_field = true;
    context_params.cassi_qi_field_layer = field_layer;
    context_params.cassi_qi_field_scales = SCALE_COUNT;
    context_params.cassi_qi_displacement = 6;
    context_ptr context(llama_init_from_model(model.get(), context_params), llama_free);
    if (!context) throw std::runtime_error("failed to create context");
    if (llama_cassi_qi_state_size(context.get()) != state.size() ||
            !llama_cassi_qi_state_set(context.get(), 0, state.data(), state.size())) {
        throw std::runtime_error("failed to install field state");
    }

    std::vector<llama_token> prompt = common_tokenize(context.get(), opt.prompt, true, false);
    if (prompt.empty() || llama_decode(
            context.get(), llama_batch_get_one(prompt.data(), static_cast<int32_t>(prompt.size()))) != 0) {
        throw std::runtime_error("prompt decode failed");
    }
    sampler_ptr sampler(llama_sampler_init_greedy(), llama_sampler_free);
    std::string output;
    for (int i = 0; i < opt.tokens; ++i) {
        const llama_token token = llama_sampler_sample(sampler.get(), context.get(), -1);
        llama_sampler_accept(sampler.get(), token);
        output += common_token_to_piece(context.get(), token, true);
        llama_token mutable_token = token;
        if (llama_decode(context.get(), llama_batch_get_one(&mutable_token, 1)) != 0) {
            throw std::runtime_error("generation decode failed");
        }
    }
    std::vector<float> final_state(state.size());
    if (!llama_cassi_qi_state_get(context.get(), 0, final_state.data(), final_state.size())) {
        throw std::runtime_error("failed to retrieve final field state");
    }
    write_state(opt.out_state, final_state);
    std::cout << output << "\n";
    std::cout << "{\"schema\":\"cassi.qi.native-runtime.v1\",\"verdict\":\"PASS\","
              << "\"mode\":\"coupled\",\"sampler\":\"llama_sampler_greedy_over_field_logits\","
              << "\"qwen_forward_passes\":" << (opt.tokens + 1) << ","
              << "\"state_before_fnv1a\":" << fnv1a(state) << ","
              << "\"state_after_fnv1a\":" << fnv1a(final_state) << ","
              << "\"output_bytes\":" << output.size() << "}\n";
    return 0;
}

int run_field_only(const options & opt, std::vector<float> state) {
    llama_model_params model_params = llama_model_default_params();
    model_params.vocab_only = true;
    model_ptr model(llama_model_load_from_file(opt.model.c_str(), model_params), llama_model_free);
    if (!model) throw std::runtime_error("failed to load vocabulary");
    const llama_vocab * vocab = llama_model_get_vocab(model.get());
    const int32_t vocab_size = llama_vocab_n_tokens(vocab);
    field_stepper stepper;
    const uint64_t initial_hash = fnv1a(state);
    for (llama_token token : common_tokenize(vocab, opt.prompt, true, false)) {
        stepper.advance(state, token);
    }
    std::string output;
    for (int i = 0; i < opt.tokens; ++i) {
        const llama_token token = field_argmax(state, vocab_size);
        output += common_token_to_piece(vocab, token, true);
        stepper.advance(state, token);
    }
    write_state(opt.out_state, state);
    std::cout << output << "\n";
    std::cout << "{\"schema\":\"cassi.qi.native-runtime.v1\",\"verdict\":\"PASS\","
              << "\"mode\":\"field\",\"vocab_only\":true,"
              << "\"token_sense\":\"fixed_64_mode_hash_v1\","
              << "\"qwen_forward_passes\":0,\"model_logits_read\":0,"
              << "\"qwen_tensor_bytes_loaded\":0,"
              << "\"gguf_tensor_bytes_declared\":" << llama_model_size(model.get()) << ","
              << "\"state_before_fnv1a\":" << initial_hash << ","
              << "\"state_after_fnv1a\":" << fnv1a(state) << ","
              << "\"output_bytes\":" << output.size() << "}\n";
    return 0;
}

} // namespace

int main(int argc, char ** argv) {
    try {
        const options opt = parse_options(argc, argv);
        ggml_backend_load_all();
        std::vector<float> state = read_state(opt.state);
        return opt.mode == "coupled" ? run_coupled(opt, std::move(state)) : run_field_only(opt, std::move(state));
    } catch (const std::exception & error) {
        std::cerr << "FAIL: " << error.what() << "\n";
        return 1;
    }
}
