#include "common.h"
#include "llama.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <numeric>
#include <string>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;

std::vector<float> read_state(const std::string & path, size_t count) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    const size_t bytes = count * sizeof(float);
    if (!stream || stream.tellg() != static_cast<std::streamoff>(bytes)) {
        throw std::runtime_error("state fixture has the wrong byte length: " + path);
    }
    stream.seekg(0);
    std::vector<float> state(count);
    stream.read(reinterpret_cast<char *>(state.data()), static_cast<std::streamsize>(bytes));
    if (!stream) {
        throw std::runtime_error("failed to read state fixture: " + path);
    }
    return state;
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

} // namespace

int main(int argc, char ** argv) {
    if (argc != 6) {
        std::cerr << "usage: " << argv[0] << " MODEL STATE cpu|gpu FIELD_LAYER DISPLACEMENT\n";
        return 2;
    }

    try {
        const bool use_gpu = std::string(argv[3]) == "gpu";
        if (!use_gpu && std::string(argv[3]) != "cpu") {
            throw std::runtime_error("backend must be cpu or gpu");
        }
        const int field_layer = std::stoi(argv[4]);
        const int displacement = std::stoi(argv[5]);
        if (displacement < 0 || displacement > 6) {
            throw std::runtime_error("displacement must be in [0,6]");
        }

        ggml_backend_load_all();

        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = use_gpu ? 99 : 0;
        model_ptr model(llama_model_load_from_file(argv[1], model_params), llama_model_free);
        if (!model) {
            throw std::runtime_error("failed to load model");
        }
        const bool null_graph_nodes_fail_closed = llama_cassi_qi_graph_nodes(nullptr) == -1;
        if (!null_graph_nodes_fail_closed) {
            throw std::runtime_error("null Qi graph-node query did not fail closed");
        }


        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = 64;
        context_params.n_batch = 32;
        context_params.n_ubatch = 32;
        context_params.cassi_modal = false;
        context_params.cassi_field_step = false;
        context_params.cassi_qi_field = true;
        context_params.cassi_qi_field_layer = field_layer;
        context_params.cassi_qi_field_scales = 4;
        context_params.cassi_qi_displacement = displacement;
        context_ptr context(llama_init_from_model(model.get(), context_params), llama_free);
        if (!context) {
            throw std::runtime_error("failed to create context");
        }
        const int32_t graph_nodes = llama_cassi_qi_graph_nodes(context.get());
        if (graph_nodes <= 0) {
            throw std::runtime_error("Qi graph-node count is unavailable");
        }

        const size_t state_count = llama_cassi_qi_state_size(context.get());
        std::vector<float> before = read_state(argv[2], state_count);
        if (!llama_cassi_qi_state_set(context.get(), 0, before.data(), before.size())) {
            throw std::runtime_error("failed to load bridge state");
        }

        std::vector<llama_token> tokens = common_tokenize(context.get(), "Qi isolated smoke", true, false);
        if (tokens.empty() || llama_decode(context.get(), llama_batch_get_one(tokens.data(), static_cast<int32_t>(tokens.size()))) != 0) {
            throw std::runtime_error("decode failed");
        }

        std::vector<float> after(state_count);
        if (!llama_cassi_qi_state_get(context.get(), 0, after.data(), after.size())) {
            throw std::runtime_error("failed to retrieve bridge state");
        }
        float state_max_abs_delta = 0.0f;
        for (size_t i = 0; i < state_count; ++i) {
            state_max_abs_delta = std::max(state_max_abs_delta, std::abs(after[i] - before[i]));
        }
        if (!(state_max_abs_delta > 0.0f) || !std::isfinite(state_max_abs_delta)) {
            throw std::runtime_error("field state did not advance finitely");
        }

        const float * logits = llama_get_logits_ith(context.get(), -1);
        const int32_t vocab_size = llama_vocab_n_tokens(llama_model_get_vocab(model.get()));
        if (logits == nullptr || vocab_size <= 0) {
            throw std::runtime_error("logits unavailable");
        }
        float logit_max_abs = 0.0f;
        std::vector<llama_token> candidate_ids(vocab_size);
        std::iota(candidate_ids.begin(), candidate_ids.end(), 0);
        for (int32_t i = 0; i < vocab_size; ++i) {
            if (!std::isfinite(logits[i])) {
                throw std::runtime_error("non-finite logits");
            }
            logit_max_abs = std::max(logit_max_abs, std::abs(logits[i]));
        }
        const llama_token qwen_top1 = *std::max_element(
            candidate_ids.begin(), candidate_ids.end(),
            [logits](llama_token lhs, llama_token rhs) { return logits[lhs] < logits[rhs]; });
        const size_t candidate_count = std::min<size_t>(64, candidate_ids.size());
        std::partial_sort(
            candidate_ids.begin(), candidate_ids.begin() + candidate_count, candidate_ids.end(),
            [logits](llama_token lhs, llama_token rhs) { return logits[lhs] > logits[rhs]; });

        std::vector<llama_token> all_tokens(vocab_size);
        std::iota(all_tokens.begin(), all_tokens.end(), 0);
        std::vector<float> field_scores(vocab_size);
        if (!llama_cassi_qi_score_tokens(
                context.get(), 0, all_tokens.data(), field_scores.data(), field_scores.size())) {
            throw std::runtime_error("field token scoring failed");
        }
        const llama_token field_full = *std::max_element(
            all_tokens.begin(), all_tokens.end(),
            [&field_scores](llama_token lhs, llama_token rhs) {
                return field_scores[lhs] < field_scores[rhs];
            });
        const llama_token field_candidate = *std::max_element(
            candidate_ids.begin(), candidate_ids.begin() + candidate_count,
            [&field_scores](llama_token lhs, llama_token rhs) {
                return field_scores[lhs] < field_scores[rhs];
            });
        float field_logit_max_abs_error = 0.0f;
        if (displacement >= 6) {
            for (int32_t i = 0; i < vocab_size; ++i) {
                field_logit_max_abs_error = std::max(
                    field_logit_max_abs_error, std::abs(logits[i] - field_scores[i]));
            }
            if (qwen_top1 != field_full || field_logit_max_abs_error > 1.0e-5f) {
                throw std::runtime_error("field logits do not own the LM-head output");
            }
        }
        llama_token selected = displacement == 0
            ? qwen_top1
            : (displacement == 1 ? field_candidate : field_full);
        if (llama_decode(context.get(), llama_batch_get_one(&selected, 1)) != 0) {
            throw std::runtime_error("continuation decode failed");
        }
        std::vector<float> after_continuation(state_count);
        if (!llama_cassi_qi_state_get(
                context.get(), 0, after_continuation.data(), after_continuation.size())) {
            throw std::runtime_error("failed to retrieve continuation state");
        }
        std::cout << "{\"schema\":\"cassi.qi.qwen-displacement.v1\","
                  << "\"verdict\":\"PASS\","
                  << "\"null_graph_nodes_fail_closed\":"
                  << (null_graph_nodes_fail_closed ? "true" : "false") << ","
                  << "\"backend\":\"" << (use_gpu ? "gpu" : "cpu") << "\","
                  << "\"displacement\":" << displacement << ","
                  << "\"graph_nodes\":" << graph_nodes << ","
                  << "\"state_floats\":" << state_count << ","
                  << "\"state_before_fnv1a\":" << fnv1a(before) << ","
                  << "\"state_after_fnv1a\":" << fnv1a(after) << ","
                  << "\"state_continuation_fnv1a\":" << fnv1a(after_continuation) << ","
                  << "\"state_max_abs_delta\":" << state_max_abs_delta << ","
                  << "\"logit_max_abs\":" << logit_max_abs << ","
                  << "\"qwen_top1\":" << qwen_top1 << ","
                  << "\"field_candidate\":" << field_candidate << ","
                  << "\"field_full\":" << field_full << ","
                  << "\"selected\":" << selected << ","
                  << "\"candidate_changed\":" << (field_candidate != qwen_top1 ? "true" : "false") << ","
                  << "\"field_logit_max_abs_error\":" << field_logit_max_abs_error << "}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL: " << error.what() << "\n";
        return 1;
    }
}
