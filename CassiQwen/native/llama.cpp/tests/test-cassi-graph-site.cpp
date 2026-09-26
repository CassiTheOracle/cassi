// Graph-site candidate ABI proof against real Qwen3.5 hybrid GGUFs.
//
// usage: test-cassi-graph-site MODEL cpu|gpu [SITE]
//
// MODEL must be a real hybrid Qwen3.5 GGUF supplied on the command line: an
// MoE model (qwen35moe, e.g. Qwen3.6-35B-A3B) exercises the EXPERTS, ATTENTION_MEMORY
// (SITE=attn) and EXECUTION_CHOICE (SITE=head) sites; a dense model (qwen35,
// e.g. Qwen3.5-0.8B) exercises the RECURRENT site. SITE defaults to "experts"
// on qwen35moe and "recurrent" on qwen35; pass "attn" or "head" on qwen35moe
// to exercise the attention-memory or execution-choice sites instead. This
// test is CLI opt-in and never becomes part of the default test suite. The
// full 64-hex source SHA-256 is derived by streaming the exact file. Everything
// runs through the public LLAMA_API surface: an ordinary llama_context
// (n_ctx=64, one sequence, no apprentice-service mode), a deterministic short
// prompt, one-token decodes, and the
// llama_cassi_graph_site_candidate_set / llama_decode /
// llama_cassi_graph_site_candidate_get_result ABI:
//
//   1. an admitted candidate on a real eligible layer (EXPERTS route learned
//      from the measured-route receipt on a separate probe context; RECURRENT
//      state layout derived from ssm model metadata), asserting the true
//      native receipt (omitted operator branches, omitted weight bytes) plus
//      finite logits;
//   2. a chained successor admission on the next token (predecessor/owner
//      generation chain through the field successor state);
//   3. an exact stale-generation candidate refusal with no state admission;
//   4. an exact mismatched-sequence candidate refusal with no state admission;
//   5. a candidate-free control decode whose logits must differ from the
//      admitted-candidate logits, proving the site operators were actually
//      omitted from the graph rather than merely reported.

#include "common.h"
#include "llama.h"

extern "C" {
#include "hash/sha256/sha256.h"
}

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <random>
#include <string>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using context_ptr = std::unique_ptr<llama_context, decltype(&llama_free)>;

std::string hex_digest(const unsigned char * digest, size_t len) {
    static const char * digits = "0123456789abcdef";
    std::string out;
    out.reserve(len * 2);
    for (size_t i = 0; i < len; ++i) {
        out.push_back(digits[digest[i] >> 4]);
        out.push_back(digits[digest[i] & 0x0f]);
    }
    return out;
}

std::string sha256_bytes(const void * data, size_t len) {
    unsigned char digest[SHA256_DIGEST_SIZE];
    sha256_hash(digest, static_cast<const unsigned char *>(data), len);
    return hex_digest(digest, sizeof(digest));
}

std::string sha256_string(const std::string & text) {
    return sha256_bytes(text.data(), text.size());
}

// Streams the exact GGUF file in 1 MiB chunks: the candidate's source identity
// is the true digest of the model the decode actually ran against.
std::string sha256_file(const std::string & path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot open model for hashing: " + path);
    }
    sha256_t sha;
    sha256_init(&sha);
    std::vector<char> buffer(1 << 20);
    while (stream) {
        stream.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        sha256_update(&sha, reinterpret_cast<const unsigned char *>(buffer.data()),
            static_cast<size_t>(stream.gcount()));
    }
    if (stream.bad()) {
        throw std::runtime_error("failed while reading model for hashing: " + path);
    }
    unsigned char digest[SHA256_DIGEST_SIZE];
    sha256_final(&sha, digest);
    return hex_digest(digest, sizeof(digest));
}

struct low_rank_factors {
    uint32_t rank = 4;
    std::vector<float> a;
    std::vector<float> b;
    std::vector<float> bias;
};

low_rank_factors make_factors(uint32_t input_width, uint32_t rank, uint32_t output_width) {
    low_rank_factors factors;
    factors.rank = rank;
    std::mt19937 rng(0xC4551u);
    std::uniform_real_distribution<float> uniform(-1.0f, 1.0f);
    factors.a.reserve((size_t) input_width * rank);
    for (size_t i = 0; i < (size_t) input_width * rank; ++i) {
        factors.a.push_back(uniform(rng) * 0.05f);
    }
    factors.b.reserve((size_t) rank * output_width);
    for (size_t i = 0; i < (size_t) rank * output_width; ++i) {
        factors.b.push_back(uniform(rng) * 0.05f);
    }
    factors.bias.reserve(output_width);
    for (size_t i = 0; i < output_width; ++i) {
        factors.bias.push_back(uniform(rng) * 0.01f);
    }
    for (float value : factors.a) {
        if (!std::isfinite(value)) {
            throw std::runtime_error("non-finite A factor generated");
        }
    }
    for (float value : factors.b) {
        if (!std::isfinite(value)) {
            throw std::runtime_error("non-finite B factor generated");
        }
    }
    for (float value : factors.bias) {
        if (!std::isfinite(value)) {
            throw std::runtime_error("non-finite bias factor generated");
        }
    }
    return factors;
}

// Reads an integer GGUF metadata value (keys like "qwen35.ssm.conv_kernel").
uint32_t model_meta_u32(const llama_model * model, const std::string & key) {
    char buffer[64] = {};
    if (llama_model_meta_val_str(model, key.c_str(), buffer, sizeof buffer) <= 0) {
        throw std::runtime_error("model metadata missing: " + key);
    }
    try {
        return (uint32_t) std::stoul(buffer);
    } catch (const std::exception &) {
        throw std::runtime_error("model metadata not an integer: " + key + "=" + buffer);
    }
}

// Site contract for the loaded model, derived from model metadata:
// EXPERTS on qwen35moe (expert route learned by probe) or RECURRENT on dense
// qwen35 (state layout from ssm metadata). Widths must match
// llama_hparams::n_embd_r()/n_embd_s(), which set() enforces.
struct site_spec {
    llama_cassi_graph_site_kind kind = LLAMA_CASSI_GRAPH_SITE_EXPERTS;
    uint32_t kv_heads = 0;
    uint32_t kv_head_width = 0;
    std::string architecture;
    std::string stage;
    std::string site;
    std::string specialist;
    std::string input_tensor;
    std::string output_tensor;
    std::string dependencies_json;
    uint32_t input_width = 0;
    uint32_t output_width = 0;
    uint32_t conv_rows = 0;
    uint32_t conv_channels = 0;
    uint32_t heads = 0;
    uint32_t value_width = 0;
    uint32_t n_expert_used = 0;
    std::vector<float> anchor; // zero anchor + wide radius: any input support
};

site_spec build_site_spec(const llama_model * model, uint32_t n_embd,
        uint32_t vocab_size, const std::string & site_name) {
    site_spec spec;
    char arch_buffer[64] = {};
    if (llama_model_meta_val_str(model, "general.architecture", arch_buffer, sizeof arch_buffer) <= 0) {
        throw std::runtime_error("model architecture metadata unavailable");
    }
    spec.architecture = arch_buffer;
    std::string requested = site_name;
    if (requested.empty()) {
        requested = spec.architecture == "qwen35moe" ? "experts" : "recurrent";
    }
    if (requested == "experts") {
        if (spec.architecture != "qwen35moe") {
            throw std::runtime_error("experts site requires qwen35moe architecture");
        }
        spec.kind = LLAMA_CASSI_GRAPH_SITE_EXPERTS;
        spec.stage = "qwen-experts";
        spec.site = "qwen-experts";
        spec.specialist = "expert-synthesis";
        spec.input_tensor = "attn_post_norm";
        spec.output_tensor = "ffn_delta";
        spec.input_width = n_embd;
        spec.output_width = n_embd;
        spec.n_expert_used = model_meta_u32(model, "qwen35moe.expert_used_count");
        spec.dependencies_json = "{\"graph\":\"qwen-experts\",\"service\":\"qwen-attention-route\"}";
    } else if (requested == "recurrent") {
        if (spec.architecture != "qwen35") {
            throw std::runtime_error("recurrent site requires qwen35 architecture");
        }
        const uint32_t conv_kernel = model_meta_u32(model, "qwen35.ssm.conv_kernel");
        const uint32_t d_inner     = model_meta_u32(model, "qwen35.ssm.inner_size");
        const uint32_t d_state     = model_meta_u32(model, "qwen35.ssm.state_size");
        const uint32_t dt_rank     = model_meta_u32(model, "qwen35.ssm.time_step_rank");
        const uint32_t n_group     = model_meta_u32(model, "qwen35.ssm.group_count");
        if (conv_kernel == 0 || d_inner == 0 || d_state == 0 || dt_rank == 0 || d_inner % dt_rank != 0) {
            throw std::runtime_error("ssm metadata inconsistent for recurrent site");
        }
        spec.kind = LLAMA_CASSI_GRAPH_SITE_RECURRENT;
        spec.stage = "qwen-attention-route";
        spec.site = "recurrent-attention";
        spec.specialist = "recurrent-dynamics";
        spec.input_tensor = "recurrent_features";
        spec.output_tensor = "recurrent_successor";
        spec.conv_rows = conv_kernel - 1; // builder uses ssm_conv1d->ne[0] - 1
        spec.conv_channels = d_inner + 2 * n_group * d_state;
        spec.heads = dt_rank;
        spec.value_width = d_inner / dt_rank;
        // n_embd_r() = (d_conv-1) * conv_channels, n_embd_s() = d_state * d_inner
        spec.input_width = n_embd + spec.conv_rows * spec.conv_channels + d_state * d_inner;
        spec.output_width = spec.input_width;
        spec.dependencies_json = "{\"graph\":\"qwen-attention-route\",\"service\":\"qwen-experts\"}";
    } else if (requested == "attn") {
        if (spec.architecture != "qwen35moe") {
            throw std::runtime_error("attn site requires qwen35moe architecture");
        }
        const uint32_t head_count_kv = model_meta_u32(model, "qwen35moe.attention.head_count_kv");
        uint32_t head_width = 0;
        try {
            head_width = model_meta_u32(model, "qwen35moe.attention.value_length");
        } catch (const std::exception &) {
            const uint32_t head_count = model_meta_u32(model, "qwen35moe.attention.head_count");
            if (head_count == 0) {
                throw std::runtime_error("cannot derive attention head width");
            }
            head_width = n_embd / head_count;
        }
        if (head_count_kv == 0 || head_width == 0) {
            throw std::runtime_error("attention kv metadata inconsistent for attn site");
        }
        spec.kind = LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY;
        spec.stage = "qwen-attention-route";
        spec.site = "attention-memory";
        spec.specialist = "attention-memory";
        spec.input_tensor = "attention_features";
        spec.output_tensor = "attention_successor";
        spec.kv_heads = head_count_kv;
        spec.kv_head_width = head_width;
        spec.input_width = n_embd;
        spec.output_width = n_embd + 2u * head_count_kv * head_width;
        spec.dependencies_json = "{\"graph\":\"qwen-attention-route\",\"service\":\"qwen-experts\","
            "\"kv_heads\":" + std::to_string(head_count_kv) +
            ",\"kv_head_width\":" + std::to_string(head_width) + "}";
    } else if (requested == "head") {
        if (spec.architecture != "qwen35moe") {
            throw std::runtime_error("head site requires qwen35moe architecture");
        }
        spec.kind = LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE;
        spec.stage = "qwen-head";
        spec.site = "execution-choice";
        spec.specialist = "execution-choice";
        spec.input_tensor = "head_input";
        spec.output_tensor = "logits";
        spec.input_width = n_embd;
        spec.output_width = vocab_size;
        spec.dependencies_json = "{\"graph\":\"qwen-head\",\"service\":\"qwen-experts\"}";
    } else {
        throw std::runtime_error("unsupported site name: " + requested);
    }
    spec.anchor.assign(spec.input_width, 0.0f);
    return spec;
}

// One owner-held candidate for the site described by spec. Canonical C-order
// buffers: A[input_width, rank] row-major, B[rank, output_width] row-major,
// bias[output_width]. Every pointer is copied synchronously by
// llama_cassi_graph_site_candidate_set, so the caller-owned strings and
// vectors only need to live until set() returns.
llama_cassi_graph_site_candidate make_candidate(
        const site_spec & spec,
        const std::string & sequence_id,
        const std::string & source_sha256,
        const std::string & backend,
        uint32_t rank,
        int32_t layer,
        llama_seq_id seq_id,
        int32_t position,
        uint64_t owner_generation,
        uint64_t predecessor_generation,
        uint64_t method_generation,
        const low_rank_factors & factors,
        const std::vector<float> & a,
        const std::vector<float> & b,
        const std::vector<float> & bias,
        const std::string & predecessor_sha256,
        const std::string & request_sha256,
        const std::string & invocation_sha256,
        const std::string & candidate_sha256,
        const std::string & dependencies_json,
        const std::vector<int32_t> & expected_expert_ids) {
    llama_cassi_graph_site_candidate candidate = {};
    candidate.kind = spec.kind;
    candidate.seq_id = seq_id;
    candidate.position = position;
    candidate.layer = layer;
    candidate.owner_generation = owner_generation;
    candidate.predecessor_generation = predecessor_generation;
    candidate.sequence_id = sequence_id.c_str();
    candidate.source_sha256 = source_sha256.c_str();
    candidate.architecture = spec.architecture.c_str();
    candidate.backend = backend.c_str();
    candidate.input_tensor = spec.input_tensor.c_str();
    candidate.output_tensor = spec.output_tensor.c_str();
    candidate.tensor_dtype = "f32";
    candidate.stage = spec.stage.c_str();
    candidate.site = spec.site.c_str();
    candidate.specialist = spec.specialist.c_str();
    candidate.predecessor_sha256 = predecessor_sha256.c_str();
    candidate.request_sha256 = request_sha256.c_str();
    candidate.invocation_sha256 = invocation_sha256.c_str();
    candidate.candidate_sha256 = candidate_sha256.c_str();
    candidate.intervention_order = "field-successor";
    candidate.dependencies_json = dependencies_json.c_str();
    candidate.method_key = "cassifi.graph-site-low-rank-affine.v1";
    candidate.method_generation = method_generation;
    candidate.input_width = spec.input_width;
    candidate.rank = rank;
    candidate.output_width = spec.output_width;
    candidate.a = a.data();
    candidate.a_count = a.size();
    candidate.b = b.data();
    candidate.b_count = b.size();
    candidate.bias = bias.data();
    candidate.bias_count = bias.size();
    candidate.conv_history_rows = spec.conv_rows;
    candidate.conv_history_channels = spec.conv_channels;
    candidate.recurrent_state_heads = spec.heads;
    candidate.recurrent_state_value_width = spec.value_width;
    candidate.recurrent_state_key_width = spec.value_width;
    candidate.input_support_anchor = spec.anchor.data();
    candidate.input_support_anchor_count = spec.anchor.size();
    candidate.input_support_radius = 1e30f;
    candidate.input_support_anchor_norm = 0.0f;
    candidate.attn_kv_heads = spec.kv_heads;
    candidate.attn_kv_head_width = spec.kv_head_width;
    if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS && !expected_expert_ids.empty()) {
        candidate.expected_expert_ids = expected_expert_ids.data();
        candidate.expected_expert_ids_count = expected_expert_ids.size();
    }
    return candidate;
}

std::vector<float> get_logits(const llama_context * ctx, int32_t vocab_size) {
    const float * logits = llama_get_logits_ith(const_cast<llama_context *>(ctx), -1);
    if (logits == nullptr) {
        throw std::runtime_error("logits unavailable for last token");
    }
    std::vector<float> values((size_t) vocab_size);
    std::copy(logits, logits + vocab_size, values.begin());
    for (float value : values) {
        if (!std::isfinite(value)) {
            throw std::runtime_error("non-finite logits");
        }
    }
    return values;
}

llama_token greedy_token(const std::vector<float> & logits) {
    llama_token best = 0;
    for (size_t i = 1; i < logits.size(); ++i) {
        if (logits[i] > logits[(size_t) best]) {
            best = (llama_token) i;
        }
    }
    return best;
}

llama_cassi_graph_site_candidate_result decode_with_candidate(
        llama_context * ctx,
        const llama_cassi_graph_site_candidate & candidate,
        llama_token token) {
    if (!llama_cassi_graph_site_candidate_set(ctx, &candidate)) {
        throw std::runtime_error("candidate was not staged for decode");
    }
    if (llama_decode(ctx, llama_batch_get_one(&token, 1)) != 0) {
        throw std::runtime_error("candidate decode failed");
    }
    llama_cassi_graph_site_candidate_result result = {};
    if (!llama_cassi_graph_site_candidate_get_result(ctx, &result)) {
        throw std::runtime_error("candidate result unavailable after decode");
    }
    return result;
}

void expect_admitted(const llama_cassi_graph_site_candidate_result & result,
        uint64_t owner_generation, uint64_t operators_omitted, uint64_t min_weights_omitted,
        const std::vector<int32_t> * expected_route = nullptr,
        const char * stage = nullptr) {
    if (!result.attempted) {
        throw std::runtime_error("admission was never attempted");
    }
    if (!result.admitted) {
        std::string detail = result.refusal[0] ? result.refusal : "<empty>";
        detail += " stage=" + std::string(stage != nullptr ? stage : "?");
        detail += " attempted=" + std::string(result.attempted ? "1" : "0");
        if (expected_route != nullptr) {
            detail += " expected=[";
            for (int32_t id : *expected_route) {
                detail += std::to_string(id) + " ";
            }
            detail += "]";
        }
        if (result.actual_expert_ids != nullptr) {
            detail += " actual=[";
            for (size_t i = 0; i < result.actual_expert_ids_count; ++i) {
                detail += std::to_string(result.actual_expert_ids[i]) + " ";
            }
            detail += "]";
        } else {
            detail += " actual=nullptr";
        }
        throw std::runtime_error("candidate refused: " + detail);
    }
    if (result.owner_generation != owner_generation) {
        throw std::runtime_error("admitted owner generation mismatch");
    }
    // The qwen35moe EXPERTS site replaces exactly two native operator
    // branches (routed experts + shared expert); the qwen35 RECURRENT site
    // replaces exactly one (the delta-net attention/projection path).
    if (result.operators_omitted != operators_omitted) {
        throw std::runtime_error("unexpected omitted operator branch count");
    }
    if (result.weights_omitted < min_weights_omitted || result.weight_bytes_omitted == 0) {
        throw std::runtime_error("site weights were not actually omitted");
    }
}

// A refusal must not carry any admission state: zero omitted work and no
// successful owner generation.
void expect_refused(const llama_cassi_graph_site_candidate_result & result,
        uint64_t owner_generation, const char * refusal) {
    if (!result.attempted) {
        throw std::runtime_error("refusal receipt was never attempted");
    }
    if (result.admitted) {
        throw std::runtime_error(std::string("stale/mismatched candidate was admitted: ") + refusal);
    }
    if (std::string(result.refusal) != refusal) {
        throw std::runtime_error(std::string("expected refusal '") + refusal + "' but got '" +
            result.refusal + "'");
    }
    if (result.owner_generation != owner_generation) {
        throw std::runtime_error("refused owner generation mismatch");
    }
    if (result.operators_omitted != 0 || result.weights_omitted != 0 ||
            result.weight_bytes_omitted != 0) {
        throw std::runtime_error("refused candidate reported omitted state");
    }
}

} // namespace

int main(int argc, char ** argv) {
    if (argc != 3 && argc != 4) {
        std::cerr << "usage: " << argv[0] << " MODEL cpu|gpu [SITE]\n"
                  << "  MODEL  real hybrid Qwen3.5 GGUF, qwen35moe (EXPERTS/attn/head) or qwen35 (RECURRENT);\n"
                  << "         source SHA-256 is derived from this exact file\n"
                  << "  cpu|gpu  backend selection (gpu offloads all layers)\n"
                  << "  SITE     optional: experts|recurrent|attn|head (default: per-architecture)\n";
        return 2;
    }

    try {
        const std::string model_path = argv[1];
        const std::string backend_arg = argv[2];
        const std::string site_name = argc >= 4 ? argv[3] : std::string();
        const bool use_gpu = backend_arg == "gpu";
        if (!use_gpu && backend_arg != "cpu") {
            throw std::runtime_error("backend must be cpu or gpu");
        }

        ggml_backend_load_all();

        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = use_gpu ? 99 : 0;
        model_ptr model(llama_model_load_from_file(model_path.c_str(), model_params), llama_model_free);
        if (!model) {
            throw std::runtime_error("failed to load model: " + model_path);
        }

        const int32_t n_embd = llama_model_n_embd(model.get());
        const int32_t n_layer = llama_model_n_layer(model.get());
        const int32_t vocab_size = llama_vocab_n_tokens(llama_model_get_vocab(model.get()));
        if (n_embd <= 0 || n_layer <= 0 || vocab_size <= 0) {
            throw std::runtime_error("model reports invalid dimensions");
        }
        const site_spec spec = build_site_spec(model.get(), (uint32_t) n_embd, (uint32_t) vocab_size, site_name);
        const uint64_t expected_omitted_ops =
            spec.kind == LLAMA_CASSI_GRAPH_SITE_RECURRENT ? 1 :
            spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS ? 2 :
            spec.kind == LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY ? 4 : 1;
        const uint64_t expected_min_weights_omitted =
            spec.kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE ? 1 : 2;

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = 64;
        context_params.n_batch = 32;
        context_params.n_ubatch = 32;
        context_params.cassi_modal = false;
        context_params.cassi_field_step = false;
        context_params.cassi_qi_field = false;
        context_params.cassi_apprentice = false;
        context_ptr control_context(llama_init_from_model(model.get(), context_params), llama_free);
        if (!control_context) {
            throw std::runtime_error("failed to create control context");
        }
        context_ptr context(llama_init_from_model(model.get(), context_params), llama_free);
        if (!context) {
            throw std::runtime_error("failed to create candidate context");
        }
        // Discovery runs on its own context so a successful set() (which leaves
        // a pending candidate) and the measured-route decode never touch the
        // scenario context's sequence state.
        context_ptr probe_context(llama_init_from_model(model.get(), context_params), llama_free);
        if (!probe_context) {
            throw std::runtime_error("failed to create probe context");
        }

        const std::string source_sha256 = sha256_file(model_path);
        const std::string sequence_id = "cassi-graph-site-test";
        const std::string backend = backend_arg;

        const uint32_t rank = 4;
        const low_rank_factors factors = make_factors(spec.input_width, rank, spec.output_width);
        // set() requires one well-formed 64-hex digest per sha field: hash the
        // concatenated factor digests into a single identity.
        const std::string candidate_sha256 = sha256_string(
            sha256_bytes(factors.a.data(), factors.a.size() * sizeof(float)) +
            sha256_bytes(factors.b.data(), factors.b.size() * sizeof(float)) +
            sha256_bytes(factors.bias.data(), factors.bias.size() * sizeof(float)));
        const std::string dependencies_json =
            "{\"gguf_sha256\":\"" + source_sha256 + "\",\"rank\":" + std::to_string(rank) +
            ",\"stage\":\"" + spec.stage + "\",\"intervention\":\"low-rank-affine\"}";

        // Deterministic short prompt; the candidate ABI only applies to
        // one-token decodes, so the prompt is a plain candidate-free prefill.
        std::vector<llama_token> prompt = common_tokenize(
            context.get(),
            "The quick brown fox jumps over the lazy dog while the field keeps the graph site honest.",
            true, false);
        if (prompt.size() > 28) {
            prompt.resize(28);
        }
        if (prompt.empty()) {
            throw std::runtime_error("prompt tokenized to nothing");
        }
        if (llama_decode(context.get(), llama_batch_get_one(prompt.data(), (int32_t) prompt.size())) != 0) {
            throw std::runtime_error("prompt prefill failed");
        }
        const std::vector<float> prefill_logits = get_logits(context.get(), vocab_size);
        if (llama_decode(control_context.get(), llama_batch_get_one(prompt.data(), (int32_t) prompt.size())) != 0) {
            throw std::runtime_error("control prompt prefill failed");
        }
        const std::vector<float> control_prefill_logits = get_logits(control_context.get(), vocab_size);
        float prefill_control_max_abs_error = 0.0f;
        for (size_t i = 0; i < prefill_logits.size(); ++i) {
            prefill_control_max_abs_error = std::max(prefill_control_max_abs_error,
                std::fabs(prefill_logits[i] - control_prefill_logits[i]));
        }
        if (prefill_control_max_abs_error > 1.0e-2f) {
            throw std::runtime_error("identical prefills diverged between contexts");
        }

        llama_token token_first = greedy_token(prefill_logits);
        const int32_t position_first = (int32_t) prompt.size();
        const std::string request_sha256 = sha256_string(
            spec.architecture + "|cassifi.graph-site-low-rank-affine.v1|" + source_sha256);
        const std::string invocation_sha256 = sha256_string(
            request_sha256 + "|" + sequence_id + "|" + std::to_string(position_first));

        // Discovery on the probe context: the context validates the site
        // against the exact loaded layer weights, so a successful set() is
        // itself the layer-eligibility proof (set() is refused while a
        // candidate is pending, so each attempt must fail before the next).
        if (llama_decode(probe_context.get(), llama_batch_get_one(prompt.data(), (int32_t) prompt.size())) != 0) {
            throw std::runtime_error("probe prompt prefill failed");
        }
        std::vector<int32_t> dummy_route; // structurally valid, route-agnostic
        if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
            dummy_route.resize(spec.n_expert_used);
            for (uint32_t i = 0; i < spec.n_expert_used; ++i) {
                dummy_route[i] = (int32_t) i;
            }
        }
        int32_t site_layer = 0;
        bool site_found = false;
        std::string probe_refusal;
        const int32_t layer_begin =
            spec.kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE ? -1 : 0;
        const int32_t layer_end =
            spec.kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE ? 0 : n_layer;
        for (int32_t il = layer_begin; il < layer_end; ++il) {
            const low_rank_factors & f = factors;
            const std::string predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:predecessor:none");
            const llama_cassi_graph_site_candidate candidate = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                il, 0, position_first,
                /*owner_generation=*/1, /*predecessor_generation=*/0,
                /*method_generation=*/1, f, f.a, f.b, f.bias,
                predecessor_sha256, request_sha256, invocation_sha256,
                candidate_sha256, dependencies_json, dummy_route);
            if (llama_cassi_graph_site_candidate_set(probe_context.get(), &candidate)) {
                site_layer = il;
                site_found = true;
                break;
            }
            llama_cassi_graph_site_candidate_result refused = {};
            llama_cassi_graph_site_candidate_get_result(probe_context.get(), &refused);
            probe_refusal = refused.refusal;
        }
        if (!site_found) {
            throw std::runtime_error("no eligible graph-site layer found (last refusal: " +
                probe_refusal + ")");
        }

        // The expert route is row-specific and set() needs it before the
        // decode, so every candidate decode is first mirrored on the probe
        // context with dummy_route: the receipt carries the measured route
        // whether it admitted or refused with expert_route_mismatch. The probe
        // mirrors every decode (candidate and plain) so both histories stay
        // row-identical; a probe refusal never advances its sequence state, so
        // its generation chain only advances when a mirror actually admits.
        uint64_t probe_owner = 1;
        uint64_t probe_pred = 0;
        uint64_t probe_method = 1;
        std::vector<int32_t> expected_route; // learned route for the next main decode
        auto probe_mirror = [&](int32_t position, llama_token token, bool with_candidate)
                -> std::vector<int32_t> {
            if (spec.kind != LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                return {}; // the recurrent site has no route contract
            }
            if (with_candidate) {
                const std::string probe_predecessor_sha256 = sha256_string(
                    "cassi-graph-site-test:probe:" + std::to_string(probe_owner));
                const std::string probe_invocation_sha256 = sha256_string(
                    request_sha256 + "|" + sequence_id + "|probe|" + std::to_string(position));
                const llama_cassi_graph_site_candidate candidate = make_candidate(
                    spec, sequence_id, source_sha256, backend, rank,
                    site_layer, 0, position,
                    probe_owner, probe_pred, probe_method,
                    factors, factors.a, factors.b, factors.bias,
                    probe_predecessor_sha256, request_sha256, probe_invocation_sha256,
                    candidate_sha256, dependencies_json, dummy_route);
                if (!llama_cassi_graph_site_candidate_set(probe_context.get(), &candidate)) {
                    throw std::runtime_error("probe mirror candidate was not staged");
                }
                probe_method++;
            }
            if (llama_decode(probe_context.get(), llama_batch_get_one(&token, 1)) != 0) {
                throw std::runtime_error("probe mirror decode failed");
            }
            if (!with_candidate) {
                return {};
            }
            llama_cassi_graph_site_candidate_result receipt = {};
            if (!llama_cassi_graph_site_candidate_get_result(probe_context.get(), &receipt)) {
                throw std::runtime_error("probe mirror receipt unavailable");
            }
            if (receipt.actual_expert_ids == nullptr ||
                    receipt.actual_expert_ids_count != dummy_route.size()) {
                throw std::runtime_error(std::string("probe mirror route unavailable: ") +
                    (receipt.refusal[0] ? receipt.refusal : "<empty>"));
            }
            if (receipt.admitted) {
                probe_pred = probe_owner;
                probe_owner++;
            }
            return std::vector<int32_t>(receipt.actual_expert_ids,
                receipt.actual_expert_ids + receipt.actual_expert_ids_count);
        };

        if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
            // The staged discovery candidate doubles as the first row's route
            // mirror: its decode fills actual_expert_ids from the graph's
            // measured route tensor whether it admitted or refused.
            if (llama_decode(probe_context.get(), llama_batch_get_one(&token_first, 1)) != 0) {
                throw std::runtime_error("probe route decode failed");
            }
            llama_cassi_graph_site_candidate_result probe = {};
            if (!llama_cassi_graph_site_candidate_get_result(probe_context.get(), &probe)) {
                throw std::runtime_error("probe route receipt unavailable");
            }
            if (probe.actual_expert_ids == nullptr || probe.actual_expert_ids_count == 0) {
                throw std::runtime_error(std::string("measured expert route unavailable: ") +
                    (probe.refusal[0] ? probe.refusal : "<empty>"));
            }
            if (probe.actual_expert_ids_count != spec.n_expert_used) {
                throw std::runtime_error("measured expert route count mismatch");
            }
            expected_route.assign(probe.actual_expert_ids,
                probe.actual_expert_ids + probe.actual_expert_ids_count);
            if (probe.admitted) {
                probe_pred = probe_owner;
                probe_owner++;
            }
            // stderr evidence line for the learned route (PASS json is stdout).
            std::cerr << "{\"probe_admitted\":" << (probe.admitted ? "true" : "false")
                      << ",\"probe_refusal\":\"" << probe.refusal << "\",\"probe_route\":[";
            for (size_t i = 0; i < expected_route.size(); ++i) {
                std::cerr << (i ? "," : "") << expected_route[i];
            }
            std::cerr << "]}\n";
        }

        // 1. First admission: the low-rank field candidate replaces the site's
        //    native branches at the admitted layer for this exact one-token decode.
        uint64_t admitted_owner = 1;
        uint64_t admitted_method = 1;
        std::vector<float> admitted_logits;
        {
            const low_rank_factors & f = factors;
            const std::string predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:predecessor:none");
            const std::string invocation_first = sha256_string(
                request_sha256 + "|" + sequence_id + "|" + std::to_string(position_first));
            const llama_cassi_graph_site_candidate candidate = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, 0, position_first,
                admitted_owner, /*predecessor_generation=*/0, admitted_method,
                f, f.a, f.b, f.bias,
                predecessor_sha256, request_sha256, invocation_first, candidate_sha256,
                dependencies_json, expected_route);
            const llama_cassi_graph_site_candidate_result result =
                decode_with_candidate(context.get(), candidate, token_first);
            expect_admitted(result, admitted_owner, expected_omitted_ops, expected_min_weights_omitted, &expected_route, "scenario1");
            admitted_logits = get_logits(context.get(), vocab_size);
        }

        // Control decode of the same token without any candidate: identical
        // context, same prompt, same row - the only difference is that the
        // site's native branches were omitted from the candidate graph, so
        // the logits must actually differ.
        float control_max_abs_diff = 0.0f;
        {
            if (llama_decode(control_context.get(), llama_batch_get_one(&token_first, 1)) != 0) {
                throw std::runtime_error("control decode failed");
            }
            const std::vector<float> control_logits = get_logits(control_context.get(), vocab_size);
            for (size_t i = 0; i < control_logits.size(); ++i) {
                control_max_abs_diff = std::max(control_max_abs_diff,
                    std::fabs(control_logits[i] - admitted_logits[i]));
            }
            if (!(control_max_abs_diff > 0.0f)) {
                throw std::runtime_error("admitted logits match the full native decode: "
                    "the site branches were not really omitted");
            }
        }

        // 2. Field successor state: the next token's candidate chains from the
        //    admitted owner generation and re-uses the same source identity.
        llama_token token_successor = greedy_token(admitted_logits);
        const int32_t position_successor = position_first + 1;
        const uint64_t successor_owner = admitted_owner + 1;
        const uint64_t successor_method = admitted_method + 1;
        std::vector<float> successor_logits;
        {
            if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                expected_route = probe_mirror(position_successor, token_successor, true);
            }
            const low_rank_factors & f = factors;
            const std::string predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:admitted:" + std::to_string(admitted_owner));
            const std::string invocation_successor = sha256_string(
                request_sha256 + "|" + sequence_id + "|" + std::to_string(position_successor));
            const llama_cassi_graph_site_candidate candidate = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, 0, position_successor,
                successor_owner, admitted_owner, successor_method,
                f, f.a, f.b, f.bias,
                predecessor_sha256, request_sha256, invocation_successor, candidate_sha256,
                dependencies_json, expected_route);
            const llama_cassi_graph_site_candidate_result result =
                decode_with_candidate(context.get(), candidate, token_successor);
            expect_admitted(result, successor_owner, expected_omitted_ops, expected_min_weights_omitted, &expected_route, "scenario2");
            successor_logits = get_logits(context.get(), vocab_size);
        }

        // 3. Exact stale-generation refusal: owner_generation equal to the
        //    last admitted generation must be rejected at set() time, the
        //    decode that follows must not admit anything, and the sequence
        //    state must not advance (the later chained successor below still
        //    admits with the true owner as predecessor).
        {
            const low_rank_factors & f = factors;
            const std::string stale_predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:stale:" + std::to_string(successor_owner));
            const std::string invocation_stale = sha256_string(
                request_sha256 + "|" + sequence_id + "|stale");
            const llama_cassi_graph_site_candidate stale = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, 0, position_successor + 1,
                successor_owner, /*predecessor_generation=*/successor_owner, successor_method + 1,
                f, f.a, f.b, f.bias,
                stale_predecessor_sha256, request_sha256, invocation_stale, candidate_sha256,
                dependencies_json, expected_route);
            if (llama_cassi_graph_site_candidate_set(context.get(), &stale)) {
                throw std::runtime_error("stale candidate was staged");
            }
            llama_cassi_graph_site_candidate_result refusal = {};
            if (!llama_cassi_graph_site_candidate_get_result(context.get(), &refusal)) {
                throw std::runtime_error("stale refusal receipt unavailable");
            }
            expect_refused(refusal, successor_owner, "stale_predecessor_or_generation");

            // The refused candidate is not pending: this decode runs the full
            // native graph and must not flip the refusal into an admission.
            llama_token token_after_stale = greedy_token(successor_logits);
            if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                probe_mirror(position_successor + 1, token_after_stale, false);
            }
            if (llama_decode(context.get(), llama_batch_get_one(&token_after_stale, 1)) != 0) {
                throw std::runtime_error("decode after stale refusal failed");
            }
            const std::vector<float> after_stale_logits = get_logits(context.get(), vocab_size);
            llama_cassi_graph_site_candidate_result after_stale = {};
            if (!llama_cassi_graph_site_candidate_get_result(context.get(), &after_stale)) {
                throw std::runtime_error("post-stale receipt unavailable");
            }
            expect_refused(after_stale, successor_owner, "stale_predecessor_or_generation");

            // Prove the stale attempt did not advance the field state: a
            // correctly chained successor still admits.
            const low_rank_factors & f2 = factors;
            const std::string predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:admitted:" + std::to_string(successor_owner));
            const std::string invocation_next = sha256_string(
                request_sha256 + "|" + sequence_id + "|" + std::to_string(position_successor + 2));
            if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                expected_route = probe_mirror(position_successor + 2, token_after_stale, true);
            }
            const llama_cassi_graph_site_candidate successor_next = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, 0, position_successor + 2,
                successor_owner + 1, successor_owner, successor_method + 2,
                f2, f2.a, f2.b, f2.bias,
                predecessor_sha256, request_sha256, invocation_next, candidate_sha256,
                dependencies_json, expected_route);
            const llama_cassi_graph_site_candidate_result admitted =
                decode_with_candidate(context.get(), successor_next, token_after_stale);
            expect_admitted(admitted, successor_owner + 1, expected_omitted_ops, expected_min_weights_omitted, &expected_route, "chained-after-stale");
            successor_logits = get_logits(context.get(), vocab_size);
        }

        // 4. Exact mismatched-sequence refusal: a valid candidate naming
        //    sequence 1 is staged fine, but the one-token decode runs on
        //    sequence 0, so the row cannot match and nothing is admitted.
        float final_logit_max_abs = 0.0f;
        {
            const low_rank_factors & f = factors;
            const std::string predecessor_sha256 = sha256_string(
                "cassi-graph-site-test:admitted:" + std::to_string(successor_owner + 1));
            const std::string invocation_mismatch = sha256_string(
                request_sha256 + "|" + sequence_id + "|mismatch");
            const llama_cassi_graph_site_candidate mismatched = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, /*seq_id=*/1, position_successor + 3,
                successor_owner + 2, /*predecessor_generation=*/successor_owner + 1,
                successor_method + 3,
                f, f.a, f.b, f.bias,
                predecessor_sha256, request_sha256, invocation_mismatch, candidate_sha256,
                dependencies_json, expected_route);
            if (!llama_cassi_graph_site_candidate_set(context.get(), &mismatched)) {
                throw std::runtime_error("mismatched-sequence candidate failed at set");
            }
            llama_token token_mismatch = greedy_token(successor_logits);
            if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                probe_mirror(position_successor + 3, token_mismatch, false);
            }
            if (llama_decode(context.get(), llama_batch_get_one(&token_mismatch, 1)) != 0) {
                throw std::runtime_error("mismatched-sequence decode failed");
            }
            const std::vector<float> mismatch_logits = get_logits(context.get(), vocab_size);
            llama_cassi_graph_site_candidate_result refusal = {};
            if (!llama_cassi_graph_site_candidate_get_result(context.get(), &refusal)) {
                throw std::runtime_error("mismatch refusal receipt unavailable");
            }
            expect_refused(refusal, successor_owner + 2, "sequence_or_position_mismatch");

            // The mismatch left no admission residue: the true chain still
            // admits on the correct sequence.
            const std::string invocation_final = sha256_string(
                request_sha256 + "|" + sequence_id + "|" + std::to_string(position_successor + 4));
            const llama_token token_final = greedy_token(mismatch_logits);
            if (spec.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
                expected_route = probe_mirror(position_successor + 4, token_final, true);
            }
            const llama_cassi_graph_site_candidate final_candidate = make_candidate(
                spec, sequence_id, source_sha256, backend, rank,
                site_layer, 0, position_successor + 4,
                successor_owner + 3, /*predecessor_generation=*/successor_owner + 1,
                successor_method + 4,
                f, f.a, f.b, f.bias,
                predecessor_sha256, request_sha256, invocation_final, candidate_sha256,
                dependencies_json, expected_route);
            const llama_cassi_graph_site_candidate_result admitted =
                decode_with_candidate(context.get(), final_candidate, token_final);
            expect_admitted(admitted, successor_owner + 3, expected_omitted_ops, expected_min_weights_omitted, &expected_route, "final");
            const std::vector<float> final_logits = get_logits(context.get(), vocab_size);
            for (float value : final_logits) {
                final_logit_max_abs = std::max(final_logit_max_abs, std::fabs(value));
            }
        }

        std::cout << "{\"schema\":\"cassi.graph-site.qwen.v1\","
                  << "\"verdict\":\"PASS\","
                  << "\"backend\":\"" << backend_arg << "\","
                  << "\"model\":\"" << model_path << "\","
                  << "\"source_sha256\":\"" << source_sha256 << "\","
                  << "\"site\":\"" << spec.site << "\","
                  << "\"architecture\":\"" << spec.architecture << "\","
                  << "\"n_embd\":" << n_embd << ","
                  << "\"n_layer\":" << n_layer << ","
                  << "\"vocab_size\":" << vocab_size << ","
                  << "\"rank\":" << rank << ","
                  << "\"site_layer\":" << site_layer << ","
                  << "\"n_expert_used\":" << spec.n_expert_used << ","
                  << "\"operators_omitted\":" << expected_omitted_ops << ","
                  << "\"weight_bytes_omitted\":true,"
                  << "\"admitted_owner_generations\":[1,2,3,5],"
                  << "\"control_max_abs_diff\":" << control_max_abs_diff << ","
                  << "\"prefill_control_max_abs_error\":" << prefill_control_max_abs_error << ","
                  << "\"final_logit_max_abs\":" << final_logit_max_abs << ","
                  << "\"refusals\":[\"stale_predecessor_or_generation\","
                  << "\"sequence_or_position_mismatch\"]}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL: " << error.what() << "\n";
        return 1;
    }
}
