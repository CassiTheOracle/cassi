#include "arg.h"
#include "common.h"
#include "cassi.h"
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
    std::string out_context;
    std::string in_context;
    std::string mode = "coupled";
    std::string prompt = "Cassi";
    int tokens = 4;
    int gpu_layers = 0;
    int field_layer = -1;
    float injection_scale = 1.0f;
    int displacement = 0;
    float energy_floor = 1.0e-6f;
    float read_floor = 0.05f;
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
        else if (key == "--out-context") result.out_context = value;
        else if (key == "--in-context") result.in_context = value;
        else if (key == "--mode") result.mode = value;
        else if (key == "--prompt") result.prompt = value;
        else if (key == "--tokens") result.tokens = std::stoi(value);
        else if (key == "--gpu-layers") result.gpu_layers = std::stoi(value);
        else if (key == "--field-layer") result.field_layer = std::stoi(value);
        else if (key == "--injection-scale") result.injection_scale = std::stof(value);
        else if (key == "--displacement") result.displacement = std::stoi(value);
        else if (key == "--energy-floor") result.energy_floor = std::stof(value);
        else if (key == "--read-floor") result.read_floor = std::stof(value);
        else throw std::runtime_error("unknown option: " + key);
    }
    if (result.model.empty()) {
        throw std::runtime_error("--model is required");
    }
    if (result.mode == "count") {
        return result;
    }
    if (result.state.empty()) {
        throw std::runtime_error("--state is required");
    }
    if (result.mode != "coupled" && result.mode != "field") {
        throw std::runtime_error("--mode must be coupled, field, or count");
    }
    if (result.tokens < 1) {
        throw std::runtime_error("--tokens must be positive");
    }
    if (result.mode == "field" && (!result.out_context.empty() || !result.in_context.empty())) {
        throw std::runtime_error("field mode emits no native context; context options apply to coupled mode");
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

std::vector<uint8_t> read_context(const std::string & path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("failed to open input context: " + path);
    }
    const std::streamoff size = stream.tellg();
    if (size <= 0) {
        throw std::runtime_error("input context is empty: " + path);
    }
    stream.seekg(0);
    std::vector<uint8_t> data(static_cast<size_t>(size));
    stream.read(reinterpret_cast<char *>(data.data()), size);
    if (!stream) {
        throw std::runtime_error("failed to read input context: " + path);
    }
    return data;
}

size_t write_context(const std::string & path, llama_context * context) {
    if (path.empty()) return 0;
    const size_t size = llama_state_get_size(context);
    if (size == 0) {
        throw std::runtime_error("native context state is empty");
    }
    std::vector<uint8_t> data(size);
    const size_t written = llama_state_get_data(context, data.data(), size);
    if (written != size) {
        throw std::runtime_error("native context snapshot is incomplete");
    }
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    stream.write(reinterpret_cast<const char *>(data.data()), static_cast<std::streamsize>(size));
    if (!stream) {
        throw std::runtime_error("failed to write context: " + path);
    }
    return size;
}

size_t install_context(const std::string & path, llama_context * context) {
    if (path.empty()) return 0;
    const std::vector<uint8_t> data = read_context(path);
    if (llama_state_set_data(context, data.data(), data.size()) != data.size()) {
        throw std::runtime_error("native context restoration was rejected: " + path);
    }
    return data.size();
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
    context_params.cassi_qi_displacement = static_cast<uint32_t>(opt.displacement);
    context_params.cassi_qi_injection_scale = opt.injection_scale;
    context_params.cassi_qi_energy_floor = opt.energy_floor;
    context_params.cassi_qi_read_floor = opt.read_floor;
    context_ptr context(llama_init_from_model(model.get(), context_params), llama_free);
    if (!context) throw std::runtime_error("failed to create context");
    if (llama_cassi_qi_state_size(context.get()) != state.size() ||
            !llama_cassi_qi_state_set(context.get(), 0, state.data(), state.size())) {
        throw std::runtime_error("failed to install field state");
    }
    const size_t installed_context = install_context(opt.in_context, context.get());

    std::vector<llama_token> prompt = common_tokenize(context.get(), opt.prompt, true, false);
    if (prompt.empty()) {
        throw std::runtime_error("prompt tokenized to nothing");
    }
    // The context has a fixed number of cells; refuse with numbers rather than
    // letting the runtime fail once generation runs past the end of the context.
    if (static_cast<int32_t>(prompt.size()) + opt.tokens > context_params.n_ctx) {
        throw std::runtime_error(
            "frame exceeds the emitter context: " + std::to_string(prompt.size()) +
            " prompt tokens + " + std::to_string(opt.tokens) + " generated tokens > " +
            std::to_string(context_params.n_ctx) + " context tokens");
    }
    const int64_t prompt_decode_passes = (
        (static_cast<int64_t>(prompt.size()) + context_params.n_batch - 1) /
        context_params.n_batch
    );
    // A batch may hold at most n_batch tokens, so decode the frame in slices.
    for (int32_t offset = 0; offset < static_cast<int32_t>(prompt.size()); offset += context_params.n_batch) {
        const int32_t count = std::min<int32_t>(
            context_params.n_batch, static_cast<int32_t>(prompt.size()) - offset);
        if (llama_decode(context.get(), llama_batch_get_one(prompt.data() + offset, count)) != 0) {
            throw std::runtime_error("prompt decode failed");
        }
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
    const size_t snapshot_bytes = write_context(opt.out_context, context.get());
    const bool field_logit_path = opt.displacement >= 6;
    // Each decode requests logits for its last token only.
    const int64_t lm_head_rows = field_logit_path ? 0 : prompt_decode_passes + opt.tokens;
    const int64_t field_logits_read = field_logit_path ? opt.tokens : 0;
    const int64_t model_logits_read = field_logit_path ? 0 : opt.tokens;
    const char * sampler_name = field_logit_path
        ? "llama_sampler_greedy_over_field_logits"
        : "llama_sampler_greedy_over_model_logits";
    const char * logit_owner = field_logit_path ? "field" : "model";
    std::cout << output << "\n";
    std::cout << "{\"schema\":\"cassi.qi.native-runtime.v1\",\"verdict\":\"PASS\","
              << "\"mode\":\"coupled\",\"vocab_only\":false,"
              << "\"sampler\":\"" << sampler_name << "\","
              << "\"sampler_owner\":\"native-llama\","
              << "\"logit_owner\":\"" << logit_owner << "\","
              << "\"lm_head_owner\":\"" << logit_owner << "\","
              << "\"field_layer\":" << field_layer << ","
              << "\"displacement\":" << opt.displacement << ","
              << "\"injection_scale\":" << opt.injection_scale << ","
              << "\"energy_floor\":" << opt.energy_floor << ","
              << "\"read_floor\":" << opt.read_floor << ","
              << "\"qwen_forward_passes\":"
              << (prompt_decode_passes + opt.tokens) << ","
              << "\"model_logits_read\":" << model_logits_read << ","
              << "\"field_logits_read\":" << field_logits_read << ","
              << "\"lm_head_rows_computed\":" << lm_head_rows << ","
              << "\"lm_head_rows_skipped\":"
              << (field_logit_path
                  ? prompt_decode_passes + opt.tokens
                  : 0) << ","
              << "\"sampler_steps\":" << opt.tokens << ","
              << "\"qwen_tensor_bytes_loaded\":" << llama_model_size(model.get()) << ","
              << "\"state_before_fnv1a\":" << fnv1a(state) << ","
              << "\"state_after_fnv1a\":" << fnv1a(final_state) << ","
              << "\"context_restored_bytes\":" << installed_context << ","
              << "\"context_snapshot_bytes\":" << snapshot_bytes << ","
              << "\"prompt_tokens\":" << static_cast<int64_t>(prompt.size()) << ","
              << "\"generated_tokens\":" << opt.tokens << ","
              << "\"decoded_tokens\":" << (static_cast<int64_t>(prompt.size()) + opt.tokens) << ","
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
    const std::vector<llama_token> sense = common_tokenize(vocab, opt.prompt, true, false);
    for (llama_token token : sense) {
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
              << "\"sampler\":\"field_argmax_over_field_logits\","
              << "\"sampler_owner\":\"field\","
              << "\"logit_owner\":\"field\",\"lm_head_owner\":\"none\","
              << "\"qwen_forward_passes\":0,\"model_logits_read\":0,"
              << "\"field_logits_read\":" << opt.tokens << ","
              << "\"lm_head_rows_computed\":0,\"lm_head_rows_skipped\":0,"
              << "\"sampler_steps\":" << opt.tokens << ","
              << "\"qwen_tensor_bytes_loaded\":0,"
              << "\"gguf_tensor_bytes_declared\":" << llama_model_size(model.get()) << ","
              << "\"prompt_bytes\":" << opt.prompt.size() << ","
              << "\"prompt_tokens\":" << static_cast<int64_t>(sense.size()) << ","
              << "\"generated_tokens\":" << opt.tokens << ","
              << "\"state_before_fnv1a\":" << initial_hash << ","
              << "\"state_after_fnv1a\":" << fnv1a(state) << ","
              << "\"output_bytes\":" << output.size() << "}\n";
    return 0;
}

bool apprentice_mode_requested(int argc, char ** argv) {
    for (int index = 1; index + 1 < argc; ++index) {
        if (std::string(argv[index]) == "--mode" && std::string(argv[index + 1]) == "apprentice") {
            return true;
        }
    }
    return false;
}

int run_apprentice(int argc, char ** argv) {
    std::vector<std::string> translated;
    translated.reserve(static_cast<size_t>(argc) + 1);
    translated.emplace_back(argv[0]);
    translated.emplace_back("--cassi-apprentice");
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--mode" && index + 1 < argc && std::string(argv[index + 1]) == "apprentice") {
            ++index;
            continue;
        }
        if (argument == "--model") {
            translated.emplace_back("-m");
        } else if (argument == "--prompt") {
            translated.emplace_back("-p");
        } else if (argument == "--tokens") {
            translated.emplace_back("-n");
        } else if (argument == "--gpu-layers") {
            translated.emplace_back("-ngl");
        } else {
            translated.push_back(argument);
        }
    }
    std::vector<char *> translated_argv;
    translated_argv.reserve(translated.size());
    for (std::string & argument : translated) {
        translated_argv.push_back(argument.data());
    }

    common_params params;
    params.prompt = "Cassi";
    params.n_predict = 4;
    if (!common_params_parse(
            static_cast<int>(translated_argv.size()), translated_argv.data(), params, LLAMA_EXAMPLE_COMMON)) {
        throw std::runtime_error("apprentice_configuration_conflict");
    }
    common_cassi_validate_params(params);

    std::unique_ptr<common_cassi_owner> owner = std::make_unique<common_cassi_owner>(
        params.cassi_apprentice_state,
        params.cassi_apprentice_init,
        params.cassi_apprentice_teacher == LLAMA_CASSI_NEVER,
        params.cassi_apprentice_receipt);
    common_init_result_ptr initialized = common_init_from_params(params, true);
    if (!initialized || initialized->model() == nullptr) {
        throw std::runtime_error("apprentice_model_load_failed");
    }
    llama_cassi_params apprentice = llama_cassi_default_params();
    apprentice.memory_bytes = static_cast<uint64_t>(params.cassi_apprentice_memory_mib) * 1024ULL * 1024ULL;
    apprentice.audit_interval = params.cassi_apprentice_audit_interval;
    apprentice.teacher_policy = params.cassi_apprentice_teacher;
    apprentice.route_policy = params.cassi_apprentice_route;
    apprentice.field_device = params.cassi_apprentice_device.c_str();
    apprentice.model_path = params.model.path.c_str();
    if (!owner->load(initialized->model(), common_context_params_to_llama(params), apprentice)) {
        const std::string error = owner->error();
        owner->write_receipt(owner->receipt("error", error.c_str(), {}));
        owner.reset();
        initialized.reset();
        throw std::runtime_error(error);
    }

    llama_cassi_context * session = owner->context();
    const llama_vocab * vocab = llama_model_get_vocab(initialized->model());
    const std::vector<llama_token> prompt = common_tokenize(vocab, params.prompt, true, true);
    const int32_t n_predict = params.n_predict < 0
        ? std::max<int32_t>(0, params.n_ctx - static_cast<int32_t>(prompt.size()))
        : params.n_predict;
    std::vector<llama_token> emitted;
    std::string error_code;
    bool cancelled = false;
    try {
        if (prompt.empty() ||
                llama_cassi_begin(session, prompt.data(), prompt.size(), n_predict) != 0) {
            throw std::runtime_error(llama_cassi_last_error(session));
        }
        while (true) {
            llama_cassi_token result = {};
            const llama_cassi_status status = llama_cassi_next(session, &result);
            if (status == LLAMA_CASSI_DONE) {
                break;
            }
            if (status == LLAMA_CASSI_CANCELLED) {
                cancelled = true;
                break;
            }
            if (status != LLAMA_CASSI_TOKEN) {
                throw std::runtime_error(llama_cassi_last_error(session));
            }
            if (llama_cassi_accept(session, result.token) != 0) {
                throw std::runtime_error(llama_cassi_last_error(session));
            }
            if (!owner->publish()) {
                throw std::runtime_error(owner->error());
            }
            emitted.push_back(result.token);
            std::cout << common_token_to_piece(vocab, result.token, true);
            std::cout.flush();
            if (llama_vocab_is_eog(vocab, result.token)) {
                break;
            }
        }
        if (llama_cassi_finish(session, cancelled) != 0) {
            throw std::runtime_error(llama_cassi_last_error(session));
        }
        if (!owner->publish()) {
            throw std::runtime_error(owner->error());
        }
        const char * status = cancelled ? "cancelled" : "complete";
        if (!owner->write_receipt(owner->receipt(status, nullptr, emitted))) {
            throw std::runtime_error(owner->error());
        }
        std::cout << '\n';
    } catch (const std::exception & error) {
        error_code = error.what();
        const bool publication_failed = owner->write_failed();
        llama_cassi_finish(session, true);
        if (!publication_failed) {
            owner->publish();
        }
        owner->write_receipt(owner->receipt("error", error_code.c_str(), emitted));
        owner.reset();
        initialized.reset();
        throw;
    }
    owner.reset();
    initialized.reset();
    return 0;
}

int run_count_tokens(const options & opt) {
    llama_model_params model_params = llama_model_default_params();
    model_params.vocab_only = true;
    model_ptr model(llama_model_load_from_file(opt.model.c_str(), model_params), llama_model_free);
    if (!model) throw std::runtime_error("failed to load vocabulary");
    const llama_vocab * vocab = llama_model_get_vocab(model.get());
    const std::vector<llama_token> tokens = common_tokenize(vocab, opt.prompt, true, false);
    std::cout << "{\"schema\":\"cassi.qi.native-runtime.v1\",\"verdict\":\"PASS\","
              << "\"mode\":\"count\",\"vocab_only\":true,"
              << "\"prompt_tokens\":" << static_cast<int64_t>(tokens.size()) << ","
              << "\"prompt_bytes\":" << opt.prompt.size() << "}\n";
    return 0;
}

} // namespace

int main(int argc, char ** argv) {
    try {
        ggml_backend_load_all();
        if (apprentice_mode_requested(argc, argv)) {
            return run_apprentice(argc, argv);
        }
        const options opt = parse_options(argc, argv);
        if (opt.mode == "count") {
            return run_count_tokens(opt);
        }
        std::vector<float> state = read_state(opt.state);
        return opt.mode == "coupled" ? run_coupled(opt, std::move(state)) : run_field_only(opt, std::move(state));
    } catch (const std::exception & error) {
        std::cerr << "FAIL: " << error.what() << "\n";
        return 1;
    }
}
