#include "llama-context.h"

#include "ggml.h"
#include "llama-arch.h"
#include "llama-graph.h"
#include "llama-impl.h"
#include "llama-batch.h"
#include "llama-io.h"
#include "llama-memory.h"
#include "llama-memory-hybrid.h"

#include "llama-mmap.h"
#include "llama-model.h"
#include "llama-ext.h"

#include "llama-sampler.h"
#include "llama.h"

extern "C" {
#include "sha256/sha256.h"
}


#include <vector>

#include <algorithm>
#include <cinttypes>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_set>

static bool graph_site_tensor_i32_values(
        ggml_backend_sched_t sched,
        ggml_tensor * tensor,
        size_t expected_elements,
        std::vector<int32_t> & values) {
    if (sched == nullptr || tensor == nullptr || tensor->type != GGML_TYPE_I32 ||
            tensor->buffer == nullptr || !ggml_is_contiguous(tensor) ||
            (size_t) ggml_nelements(tensor) != expected_elements ||
            expected_elements > SIZE_MAX / sizeof(int32_t) ||
            ggml_nbytes(tensor) != expected_elements * sizeof(int32_t) ||
            expected_elements == 0) {
        return false;
    }
    ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched, tensor);
    if (backend == nullptr) {
        return false;
    }
    values.resize(expected_elements);
    ggml_backend_tensor_get(tensor, values.data(), 0, ggml_nbytes(tensor));
    return true;
}

static bool graph_site_tensor_vector_shape(const ggml_tensor * tensor, uint32_t width) {
    return tensor != nullptr && width > 0 &&
        tensor->ne[0] == (int64_t) width && tensor->ne[1] == 1 &&
        tensor->ne[2] == 1 && tensor->ne[3] == 1;
}

static bool graph_site_valid_sha256(const char * value) {
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
template <size_t N>
static void graph_site_copy_c_string(char (&destination)[N], const std::string & source) {
    const size_t size = std::min(source.size(), N - 1);
    if (size != 0) {
        std::memcpy(destination, source.data(), size);
    }
    destination[size] = '\0';
}

static std::string graph_site_sha256_hex(const uint8_t digest[32]) {
    static constexpr char HEX[] = "0123456789abcdef";
    std::string result(64, '0');
    for (size_t i = 0; i < 32; ++i) {
        result[2 * i] = HEX[digest[i] >> 4];
        result[2 * i + 1] = HEX[digest[i] & 0x0f];
    }
    return result;
}

static bool graph_site_sha256_bytes(const void * data, size_t size, std::string & digest) {
    if (data == nullptr || size == 0) {
        return false;
    }
    uint8_t hash[32];
    sha256_hash(hash, reinterpret_cast<const unsigned char *>(data), size);
    digest = graph_site_sha256_hex(hash);
    return true;
}

static bool graph_site_tensor_sha256(
        ggml_backend_sched_t sched,
        ggml_tensor * tensor,
        size_t expected_elements,
        std::vector<uint8_t> & bytes,
        std::string & digest) {
    if (sched == nullptr || tensor == nullptr || tensor->type != GGML_TYPE_F32 ||
            tensor->buffer == nullptr || !ggml_is_contiguous(tensor) ||
            (size_t) ggml_nelements(tensor) != expected_elements ||
            expected_elements > SIZE_MAX / sizeof(float) ||
            ggml_nbytes(tensor) != expected_elements * sizeof(float) ||
            ggml_nbytes(tensor) == 0) {
        return false;
    }
    ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched, tensor);
    if (backend == nullptr) {
        return false;
    }
    bytes.resize(ggml_nbytes(tensor));
    ggml_backend_tensor_get(tensor, bytes.data(), 0, bytes.size());
    return graph_site_sha256_bytes(bytes.data(), bytes.size(), digest);
}

static std::string graph_site_json_quote(const char * text) {
    static constexpr char HEX[] = "0123456789abcdef";
    std::string result = "\"";
    for (const unsigned char * p = reinterpret_cast<const unsigned char *>(text); *p != 0; ++p) {
        switch (*p) {
            case '\"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default:
                if (*p < 0x20) {
                    result += "\\u00";
                    result += HEX[*p >> 4];
                    result += HEX[*p & 0x0f];
                } else {
                    result += (char) *p;
                }
        }
    }
    result += '\"';
    return result;
}

static std::string graph_site_f32_descriptor_json(
        const std::string & digest,
        const std::string & shape_json) {
    return "{\"dtype\":\"<f4\",\"order\":\"C\",\"sha256\":\"" + digest +
        "\",\"shape\":" + shape_json + "}";
}

static std::string graph_site_i32_descriptor_json(
        const std::string & digest,
        const std::string & shape_json,
        const std::vector<int32_t> & values) {
    std::string json = "{\"dtype\":\"<i4\",\"order\":\"C\",\"sha256\":\"" + digest +
        "\",\"shape\":" + shape_json + ",\"values\":[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            json += ',';
        }
        json += std::to_string(values[i]);
    }
    json += "]}";
    return json;
}

static std::string graph_site_tensor_descriptor_json(
        const std::string & digest,
        uint32_t width) {
    return graph_site_f32_descriptor_json(digest, "[" + std::to_string(width) + "]");
}

static bool graph_site_sampler_cloneable(const llama_sampler * sampler) {
    if (sampler == nullptr) {
        return true;
    }
    if (sampler->iface == nullptr) {
        return false;
    }
    auto * mutable_sampler = const_cast<llama_sampler *>(sampler);
    if (llama_sampler_chain_get(mutable_sampler, -1) != nullptr) {
        const int n_samplers = llama_sampler_chain_n(sampler);
        for (int i = 0; i < n_samplers; ++i) {
            const llama_sampler * child = llama_sampler_chain_get(mutable_sampler, i);
            if (!graph_site_sampler_cloneable(child)) {
                return false;
            }
        }
        return true;
    }
    return sampler->iface->clone != nullptr || sampler->ctx == nullptr;
}

static std::string graph_site_successor_json_digest(const std::string & json) {
    std::string digest;
    if (!graph_site_sha256_bytes(json.data(), json.size(), digest)) {
        return {};
    }
    return digest;
}

static std::string graph_site_successor_state_json(
        const std::string & semantic_name,
        const std::string & digest,
        const std::string & shape_json) {
    return "{" + graph_site_json_quote(semantic_name.c_str()) + ":" +
        graph_site_f32_descriptor_json(digest, shape_json) + "}";
}
static std::string graph_site_successor_map_json(
        const std::vector<std::pair<std::string, std::string>> & descriptors) {
    std::vector<std::pair<std::string, std::string>> ordered = descriptors;
    std::sort(ordered.begin(), ordered.end(), [](const auto & lhs, const auto & rhs) {
        return lhs.first < rhs.first;
    });
    std::string json = "{";
    for (size_t i = 0; i < ordered.size(); ++i) {
        if (i != 0) {
            json += ',';
        }
        json += graph_site_json_quote(ordered[i].first.c_str());
        json += ':';
        json += ordered[i].second;
    }
    json += '}';
    return json;
}


//
// llama_context
//

static llm_graph_type ctx_type_to_graph_type(llama_context_type ctx_type) {
    switch (ctx_type) {
        case LLAMA_CONTEXT_TYPE_DEFAULT: return LLM_GRAPH_TYPE_DEFAULT;
        case LLAMA_CONTEXT_TYPE_MTP    : return LLM_GRAPH_TYPE_DECODER_MTP;
    }
    throw std::runtime_error("Unsupported ctx type");
}

struct llm_fused_op_probe {
    llm_fused_op op;
    const char * name;
    uint32_t n_tokens_per_seq;
};

static const llm_fused_op_probe llm_fused_op_flash_attn_probe = {
    /*.op               =*/ LLM_FUSED_OP_FLASH_ATTN,
    /*.name             =*/ "Flash Attention",
    /*.n_tokens_per_seq =*/ 1,
};

static const llm_fused_op_probe llm_fused_op_gdn_ar_probe = {
    /*.op               =*/ LLM_FUSED_OP_GDN_AR,
    /*.name             =*/ "fused Gated Delta Net (autoregressive)",
    /*.n_tokens_per_seq =*/ 1,
};

static const llm_fused_op_probe llm_fused_op_gdn_ch_probe = {
    /*.op               =*/ LLM_FUSED_OP_GDN_CH,
    /*.name             =*/ "fused Gated Delta Net (chunked)",
    /*.n_tokens_per_seq =*/ 16,
};

static const llm_fused_op_probe llm_fused_op_lid_probe = {
    /*.op               =*/ LLM_FUSED_OP_LIGHTNING_INDEXER,
    /*.name             =*/ "Lightning Indexer",
    /*.n_tokens_per_seq =*/ 1,
};

static const llm_fused_op_probe llm_fused_op_dsv4_hc_pre_probe = {
    /*.op               =*/ LLM_FUSED_OP_DSV4_HC_PRE,
    /*.name             =*/ "fused DeepSeek V4 HC pre",
    /*.n_tokens_per_seq =*/ 1,
};

static const llm_fused_op_probe llm_fused_op_dsv4_hc_comb_probe = {
    /*.op               =*/ LLM_FUSED_OP_DSV4_HC_COMB,
    /*.name             =*/ "fused DeepSeek V4 HC comb",
    /*.n_tokens_per_seq =*/ 1,
};

static const llm_fused_op_probe llm_fused_op_dsv4_hc_post_probe = {
    /*.op               =*/ LLM_FUSED_OP_DSV4_HC_POST,
    /*.name             =*/ "fused DeepSeek V4 HC post",
    /*.n_tokens_per_seq =*/ 1,
};

llama_context::llama_context(
        const llama_model & model,
              llama_context_params params,
              bool exact_n_ctx) :
    model(model),
    cvec(std::make_unique<llama_adapter_cvec>()),
    loras(std::make_unique<llama_adapter_loras>()),
    balloc(std::make_unique<llama_batch_allocr>(model.hparams.n_pos_per_embd())) {
    // TODO warning when creating llama_context with awkward ctx size that is not a power of 2,
    //     may need to be backend-dependent
    LLAMA_LOG_INFO("%s: constructing llama_context\n", __func__);

    t_start_us = model.t_start_us;
    t_load_us  = model.t_load_us;

    const auto & hparams = model.hparams;

    cparams.n_seq_max = std::max(1u, params.n_seq_max);
    if (cparams.n_seq_max > LLAMA_MAX_SEQ) {
        throw std::runtime_error("n_seq_max must be <= " + std::to_string(LLAMA_MAX_SEQ));
    }

    cparams.n_rs_seq = params.n_rs_seq;
    if (cparams.n_rs_seq > 0 && !llm_arch_supports_rs_rollback(model.arch)) {
        LLAMA_LOG_DEBUG("%s: n_rs_seq=%u requested but model does not support recurrent partial rollback; clamping to 0\n",
                        __func__, cparams.n_rs_seq);
        cparams.n_rs_seq = 0;
    }

    cparams.n_threads               = params.n_threads;
    cparams.n_threads_batch         = params.n_threads_batch;
    cparams.yarn_ext_factor         = params.yarn_ext_factor  >= 0.0f ? params.yarn_ext_factor  : hparams.yarn_ext_factor;
    cparams.yarn_attn_factor        = params.yarn_attn_factor >= 0.0f ? params.yarn_attn_factor : hparams.yarn_attn_factor;
    cparams.yarn_beta_fast          = params.yarn_beta_fast   >= 0.0f ? params.yarn_beta_fast   : hparams.yarn_beta_fast;
    cparams.yarn_beta_slow          = params.yarn_beta_slow   >= 0.0f ? params.yarn_beta_slow   : hparams.yarn_beta_slow;
    cparams.embeddings              = params.embeddings;
    cparams.embeddings_nextn        = false;
    cparams.embeddings_nextn_masked = false;
    cparams.offload_kqv             = params.offload_kqv;
    cparams.no_perf                 = params.no_perf;
    cparams.warmup                  = false;

    // Cassi injection paths are Qwen35-only and mutually exclusive.
    cparams.cassi_modal = params.cassi_modal && model.arch == LLM_ARCH_QWEN35;
    cparams.cassi_field_step = params.cassi_field_step && model.arch == LLM_ARCH_QWEN35;
    cparams.cassi_qi_field = params.cassi_qi_field && model.arch == LLM_ARCH_QWEN35;
    cparams.cassi_field_layer = params.cassi_field_layer;
    cparams.cassi_qi_field_layer = params.cassi_qi_field_layer;
    cparams.cassi_qi_field_scales = params.cassi_qi_field_scales;
    cparams.cassi_qi_field_wave_modes = params.cassi_qi_field_wave_modes;
    cparams.cassi_qi_field_fill_modes = params.cassi_qi_field_fill_modes;
    cparams.cassi_qi_field_memory_fill = params.cassi_qi_field_memory_fill;
    cparams.cassi_qi_field_row_width = params.cassi_qi_field_row_width;
    cparams.cassi_qi_displacement = params.cassi_qi_displacement;
    cparams.cassi_qi_intervention = params.cassi_qi_intervention;
    cparams.cassi_qi_field_steps = params.cassi_qi_field_steps;
    cparams.cassi_qi_injection_scale = params.cassi_qi_injection_scale;
    cparams.cassi_qi_field_dt = params.cassi_qi_field_dt;
    cparams.cassi_qi_substitute = params.cassi_qi_substitute;
    cparams.cassi_qi_energy_floor = params.cassi_qi_energy_floor;
    cparams.cassi_qi_read_floor = params.cassi_qi_read_floor;
    cparams.cassi_qi_scale_read_taper = params.cassi_qi_scale_read_taper;
    cparams.cassi_qi_read_absolute = params.cassi_qi_read_absolute;
    cparams.cassi_qi_modulate = params.cassi_qi_modulate;
    cparams.cassi_qi_modulate_gain = params.cassi_qi_modulate_gain;
    cparams.cassi_qi_attention_history = params.cassi_qi_attention_history;
    cparams.cassi_qi_unwritten_latch = params.cassi_qi_unwritten_latch;
    cparams.cassi_modal_retained_weight = params.cassi_modal_retained_weight;
    cparams.cassi_modal_phi             = params.cassi_modal_phi;
    cparams.cassi_modal_dt              = params.cassi_modal_dt;
    cparams.cassi_modal_omega2          = params.cassi_modal_omega2;
    cparams.cassi_modal_coupling        = params.cassi_modal_coupling;
    cparams.cassi_modal_steps_per_layer = params.cassi_modal_steps_per_layer;
    cparams.cassi_apprentice = params.cassi_apprentice;
    cparams.cassi_capture = false;
    if (cparams.cassi_apprentice) {
        if (model.arch != LLM_ARCH_QWEN35 || params.cassi_attention_owned == nullptr ||
                params.cassi_attention_owned_count != hparams.n_layer()) {
            throw std::runtime_error("invalid Cassi apprenticeship service configuration");
        }
        cparams.cassi_attention_owned.assign(
            params.cassi_attention_owned,
            params.cassi_attention_owned + params.cassi_attention_owned_count);
        if (std::any_of(
                cparams.cassi_attention_owned.begin(),
                cparams.cassi_attention_owned.end(),
                [](uint8_t value) { return value > 1; })) {
            throw std::runtime_error("invalid Cassi apprenticeship attention mask");
        }
    } else if (params.cassi_attention_owned != nullptr || params.cassi_attention_owned_count != 0) {
        throw std::runtime_error("Cassi apprenticeship attention mask requires its service context");
    }

    const int enabled_paths = int(cparams.cassi_modal) + int(cparams.cassi_field_step) +
        int(cparams.cassi_qi_field) + int(cparams.cassi_apprentice);
    if (enabled_paths > 1) {
        throw std::runtime_error("Cassi execution paths are mutually exclusive");
    }

    cassi_modal.enabled        = cparams.cassi_modal;
    cassi_modal.n_seq_max      = cparams.n_seq_max;
    cassi_modal.mode_count     = hparams.n_embd / 2;
    cassi_modal.layer_count    = hparams.n_layer();
    cassi_modal.steps_per_layer = cparams.cassi_modal_steps_per_layer;
    cassi_modal.state_stride   = 8 * cassi_modal.mode_count;
    cassi_modal.retained_weight = cparams.cassi_modal_retained_weight;
    cassi_modal.phi             = cparams.cassi_modal_phi;
    cassi_modal.dt              = cparams.cassi_modal_dt;
    cassi_modal.omega2          = cparams.cassi_modal_omega2;
    cassi_modal.coupling        = cparams.cassi_modal_coupling;

    cassi_field.enabled         = cparams.cassi_field_step;
    cassi_field.n_seq_max       = cparams.n_seq_max;
    cassi_field.mode_count      = hparams.n_embd / 2;
    cassi_field.layer_count     = 0;
    cassi_field.steps_per_layer = cparams.cassi_modal_steps_per_layer;
    cassi_field.state_stride    = 8 * cassi_field.mode_count;
    cassi_field.layer_index     = cparams.cassi_field_layer;
    cassi_field.retained_weight = cparams.cassi_modal_retained_weight;
    cassi_field.phi             = cparams.cassi_modal_phi;
    cassi_field.dt              = cparams.cassi_modal_dt;
    cassi_field.omega2          = cparams.cassi_modal_omega2;
    cassi_field.coupling        = cparams.cassi_modal_coupling;

    cassi_qi.enabled          = cparams.cassi_qi_field;
    cassi_qi.n_seq_max        = cparams.n_seq_max;
    cassi_qi.n_embd           = hparams.n_embd;
    cassi_qi.mode_count       = 6144;
    cassi_qi.wave_mode_count  = cparams.cassi_qi_field_wave_modes > 0
        ? cparams.cassi_qi_field_wave_modes : 3072;
    cassi_qi.fill_modes       = cparams.cassi_qi_field_fill_modes;
    cassi_qi.memory_fill      = cparams.cassi_qi_field_memory_fill;
    cassi_qi.row_width        = cparams.cassi_qi_field_row_width;
    cassi_qi.layer_index      = cparams.cassi_qi_field_layer;
    cassi_qi.scale_count      = cparams.cassi_qi_field_scales;
    cassi_qi.profile_id       = 2;
    cassi_qi.displacement_level = cparams.cassi_qi_displacement;
    cassi_qi.steps            = cparams.cassi_qi_field_steps;
    cassi_qi.intervention     = cparams.cassi_qi_intervention;
    cassi_qi.injection_scale  = cparams.cassi_qi_injection_scale;
    cassi_qi.state_stride     = 9 * cassi_qi.mode_count * cassi_qi.scale_count;
    cassi_qi.phi              = 1.618033988749895f;
    cassi_qi.dt               = cparams.cassi_qi_field_dt;
    cassi_qi.coupling         = 0.5f;
    cassi_qi.damping_min      = 0.01f;
    cassi_qi.damping_max      = 0.5f;
    cassi_qi.epsilon_tau      = 0.618033988749895f;
    cassi_qi.scale_ratio      = 4.2360679775f;
    cassi_qi.energy_floor     = params.cassi_qi_energy_floor;
    cassi_qi.read_floor       = params.cassi_qi_read_floor;
    cassi_qi.scale_read_taper = params.cassi_qi_scale_read_taper;
    cassi_qi.read_absolute    = params.cassi_qi_read_absolute;
    cassi_qi.modulate         = params.cassi_qi_modulate;
    cassi_qi.modulate_gain    = params.cassi_qi_modulate_gain;
    cassi_qi.attention_history = cparams.cassi_qi_attention_history;
    cassi_qi.unwritten_latch  = cparams.cassi_qi_unwritten_latch;
    cassi_qi.mode_param_min   = cassi_qi.damping_min;
    cassi_qi.mode_param_max   = cassi_qi.damping_max;

    if (cassi_field.enabled && (cassi_field.layer_index >= hparams.n_layer() ||
            (hparams.n_embd & 1) != 0 || cassi_field.mode_count == 0 ||
            cassi_field.steps_per_layer == 0 ||
            !std::isfinite(cassi_field.retained_weight) ||
            cassi_field.retained_weight < 0.0f || cassi_field.retained_weight > 1.0f ||
            !std::isfinite(cassi_field.phi) || !std::isfinite(cassi_field.dt) ||
            cassi_field.dt <= 0.0f || !std::isfinite(cassi_field.omega2) ||
            cassi_field.omega2 <= 0.0f || !std::isfinite(cassi_field.coupling) ||
            cassi_field.coupling <= 0.0f)) {
        throw std::runtime_error("invalid Cassi field-step configuration");
    }
    if (cassi_modal.enabled && ((hparams.n_embd & 1) != 0 || cassi_modal.mode_count == 0 ||
            cassi_modal.steps_per_layer == 0 || !std::isfinite(cassi_modal.retained_weight) ||
            cassi_modal.retained_weight < 0.0f || cassi_modal.retained_weight > 1.0f ||
            !std::isfinite(cassi_modal.phi) || !std::isfinite(cassi_modal.dt) || cassi_modal.dt <= 0.0f ||
            !std::isfinite(cassi_modal.omega2) || cassi_modal.omega2 <= 0.0f ||
            !std::isfinite(cassi_modal.coupling) || cassi_modal.coupling <= 0.0f)) {
        throw std::runtime_error("invalid Cassi modal configuration");
    }
    if (cassi_qi.enabled && (cassi_qi.mode_count == 0 || cassi_qi.wave_mode_count == 0 ||
            cassi_qi.displacement_level > 6 || cassi_qi.intervention > 1 || cassi_qi.steps == 0 ||
            // the substitution fills a state write the displacement suppressed, so a
            // positive share below level 3 would run the field with a dead seam
            (cparams.cassi_qi_substitute > 0.0f && cassi_qi.displacement_level < 3) ||
            !std::isfinite(cparams.cassi_qi_substitute) ||
            cparams.cassi_qi_substitute < 0.0f || cparams.cassi_qi_substitute > 1.0f ||
            // modulation adds to the write it reads, so a displaced write would leave nothing
            // to modulate; that also keeps it exclusive with a positive substitution share
            (cparams.cassi_qi_modulate && cassi_qi.displacement_level >= 3) ||
            !std::isfinite(cparams.cassi_qi_modulate_gain) || cparams.cassi_qi_modulate_gain < 0.0f ||
            2 * cassi_qi.wave_mode_count < hparams.n_embd || cassi_qi.wave_mode_count > cassi_qi.mode_count ||
            cassi_qi.layer_index >= hparams.n_layer() || cassi_qi.scale_count < 1 || cassi_qi.scale_count > 4 ||
            !std::isfinite(cassi_qi.injection_scale) || cassi_qi.injection_scale < 0.0f ||
            !std::isfinite(cassi_qi.phi) || cassi_qi.phi <= 0.0f ||
            !std::isfinite(cassi_qi.dt) || cassi_qi.dt <= 0.0f ||
            !std::isfinite(cassi_qi.coupling) || cassi_qi.coupling < 0.0f ||
            !std::isfinite(cassi_qi.epsilon_tau) || cassi_qi.epsilon_tau <= 0.0f || cassi_qi.epsilon_tau > 1.0f ||
            !std::isfinite(cassi_qi.scale_ratio) || cassi_qi.scale_ratio <= 0.0f ||
            !std::isfinite(cassi_qi.energy_floor) || cassi_qi.energy_floor < 0.0f ||
            !std::isfinite(cassi_qi.read_floor) || cassi_qi.read_floor < 0.0f)) {
        throw std::runtime_error("invalid Cassi Qi field configuration");
    }

    if (cassi_modal.enabled) {
        cassi_modal_state.resize((size_t) cassi_modal.n_seq_max * cassi_modal.state_stride, 0.0f);
        cassi_modal.state = cassi_modal_state.data();
    }
    if (cassi_field.enabled) {
        cassi_field_state.resize((size_t) cassi_field.n_seq_max * cassi_field.state_stride, 0.0f);
        cassi_field.state = cassi_field_state.data();
    }
    if (cassi_qi.enabled) {
        cassi_qi_state.resize((size_t) cassi_qi.n_seq_max * cassi_qi.state_stride, 0.0f);
        cassi_qi.state = cassi_qi_state.data();
    }
    // +1: id n_layer() taps the output of the last layer ("input" of the head)
    cparams.embeddings_layer_inp.resize(hparams.n_layer() + 1, false);
    embd_layer_inp.resize(hparams.n_layer() + 1);

    cparams.ctx_type     = params.ctx_type;
    cparams.pooling_type = params.pooling_type;

    cparams.n_ctx            = params.n_ctx           == 0    ? hparams.n_ctx_train           : params.n_ctx;
    cparams.rope_freq_base   = params.rope_freq_base  == 0.0f ? hparams.rope_freq_base_train  : params.rope_freq_base;
    cparams.rope_freq_scale  = params.rope_freq_scale == 0.0f ? hparams.rope_freq_scale_train : params.rope_freq_scale;

    cparams.n_ctx_orig_yarn  = params.yarn_orig_ctx    != 0 ? params.yarn_orig_ctx    :
                               hparams.n_ctx_orig_yarn != 0 ? hparams.n_ctx_orig_yarn :
                                                              hparams.n_ctx_train;

    cparams.cb_eval           = params.cb_eval;
    cparams.cb_eval_user_data = params.cb_eval_user_data;

    cparams.ctx_other = nullptr;

    // TODO: more generic
    if (model.arch == LLM_ARCH_GEMMA4_ASSISTANT) {
        if (params.ctx_other == nullptr) {
            // TODO: change from runtime_error to llama_exception to avoid printing error message
            throw std::runtime_error("Gemma4Assistant requires ctx_other to be set (this warning is normal during memory fitting)");
        }

        cparams.ctx_other = params.ctx_other;
    }

    if (model.arch == LLM_ARCH_EAGLE3 || model.arch == LLM_ARCH_DFLASH) {
        if (model.tok_embd == nullptr || model.output == nullptr) {
            if (params.ctx_other == nullptr) {
                throw std::runtime_error(model.arch_name() + " requires ctx_other to be set (this warning is normal during memory fitting)");
            }
            cparams.ctx_other = params.ctx_other;
        }
    }

    auto rope_scaling_type = params.rope_scaling_type;
    if (rope_scaling_type == LLAMA_ROPE_SCALING_TYPE_UNSPECIFIED) {
        rope_scaling_type = hparams.rope_scaling_type_train;
    }

    if (rope_scaling_type == LLAMA_ROPE_SCALING_TYPE_NONE) {
        cparams.rope_freq_scale = 1.0f; // never scale if scaling type is none
    }

    if (cparams.yarn_ext_factor < 0.0f) { // negative indicates 'not set'
        cparams.yarn_ext_factor = rope_scaling_type == LLAMA_ROPE_SCALING_TYPE_YARN ? 1.0f : 0.0f;
    }

    if (cparams.yarn_ext_factor != 0) {
        static auto get_mscale = [](float scale, float mscale) {
            return scale <= 1.0f ? 1.0f : (0.1f * mscale * logf(scale) + 1.0f);
        };

        const float factor = 1.0f / cparams.rope_freq_scale;

        // ref: https://github.com/huggingface/transformers/blob/6d00f6b0a5679c36510f203e4226e36f517c3032/src/transformers/modeling_rope_utils.py#L336-L348
        if (hparams.rope_yarn_log_mul != 0.0f) {
            // note: here we assume `mscale == 1.0f`
            // TODO: start reading the actual value of mscale and handle the case where it is not 1.0f
                  float mscale          = 1.0f;
            const float mscale_all_dims = hparams.rope_yarn_log_mul;

            // [TAG_DEEPSEEK2_YARN_LOG_MUL_FIX]
            // special-case DEEPSEEK v2:
            // https://huggingface.co/deepseek-ai/DeepSeek-V2-Lite-Chat/blob/main/config.json#L42-L43
            if (model.arch == LLM_ARCH_DEEPSEEK2 && mscale_all_dims != 1.0f) {
                mscale = mscale_all_dims;
            }

            cparams.yarn_attn_factor = get_mscale(factor, mscale) / get_mscale(factor, mscale_all_dims);

            LLAMA_LOG_WARN("%s: setting new yarn_attn_factor = %.4f (mscale == %.1f, mscale_all_dim = %.1f)\n",
                    __func__, cparams.yarn_attn_factor, mscale, mscale_all_dims);
        } else {
            cparams.yarn_attn_factor = get_mscale(factor, 1.0f);
        }

        // when YARN is applied with yarn_ext_factor != 0.0f, we need to cancel this factor:
        // https://github.com/ggml-org/llama.cpp/blob/a81a569577cc38b32558958b048228150be63eae/ggml/src/ggml-cpu/ops.cpp#L5541-L5544
        //
        // ref: https://github.com/ggml-org/llama.cpp/discussions/7416
        //      https://github.com/ggml-org/llama.cpp/pull/17945
        cparams.yarn_attn_factor *= 1.0f / (1.0f + 0.1f * logf(factor));
    }

    cparams.yarn_attn_factor *= hparams.rope_attn_factor;

    if (cparams.pooling_type == LLAMA_POOLING_TYPE_UNSPECIFIED) {
        if (hparams.pooling_type == LLAMA_POOLING_TYPE_UNSPECIFIED) {
            cparams.pooling_type = LLAMA_POOLING_TYPE_NONE;
        } else {
            cparams.pooling_type = hparams.pooling_type;
        }
    }

    if (params.attention_type == LLAMA_ATTENTION_TYPE_UNSPECIFIED) {
        cparams.causal_attn = hparams.causal_attn;
    } else {
        cparams.causal_attn = params.attention_type == LLAMA_ATTENTION_TYPE_CAUSAL;
    }

    cparams.flash_attn = params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_DISABLED;
    cparams.auto_fa    = params.flash_attn_type == LLAMA_FLASH_ATTN_TYPE_AUTO;

    cparams.fused_gdn_ar = true;
    cparams.fused_gdn_ch = true;
    cparams.auto_fgdn    = true;

    cparams.fused_lid    = true;
    cparams.auto_flid    = true;

    cparams.fused_dsv4_hc_pre  = true;
    cparams.fused_dsv4_hc_comb = true;
    cparams.fused_dsv4_hc_post = true;
    cparams.auto_fhc           = true;

    // with causal attention, the batch size is limited by the context size
    cparams.n_batch = cparams.causal_attn ? std::min(cparams.n_ctx, params.n_batch) : params.n_batch;

    cparams.n_ubatch = std::min(cparams.n_batch, params.n_ubatch == 0 ? params.n_batch : params.n_ubatch);

    cparams.n_outputs_max = params.n_outputs_max == 0 || llama_model_has_encoder(&model) ? cparams.n_batch : params.n_outputs_max;
    cparams.n_outputs_max_per_seq = params.n_outputs_max_per_seq == 0 ?
            cparams.n_outputs_max : std::min(params.n_outputs_max_per_seq, cparams.n_outputs_max);

    // Initialize backend samplers here so they are part of the sampling graph
    // before the reserve passes run later in this function. This avoids a later
    // re-reserve when graph nodes change.
    if (params.samplers != nullptr && params.n_samplers > 0) {
        for (size_t i = 0; i < params.n_samplers; ++i) {
            const auto & config = params.samplers[i];

            if (llama_sampler_chain_get(config.sampler, -1) == nullptr) {
                throw std::runtime_error("the backend samplers must be of type llama_sampler_chain");
            }

            if (set_sampler(config.seq_id, config.sampler)) {
                const int n_samplers = llama_sampler_chain_n(config.sampler);

                LLAMA_LOG_INFO("%s: setting backend sampler for seq_id %d (n = %d)\n", __func__, config.seq_id, n_samplers);
            }
        }
    }

    cparams.op_offload = params.op_offload;
    cparams.kv_unified = params.kv_unified;

    // initialized later
    cparams.pipeline_parallel = false;

    {
        const char * LLAMA_GRAPH_REUSE_DISABLE = getenv("LLAMA_GRAPH_REUSE_DISABLE");
        graph_reuse_disable = LLAMA_GRAPH_REUSE_DISABLE ? (atoi(LLAMA_GRAPH_REUSE_DISABLE) != 0) : graph_reuse_disable;

        if (graph_reuse_disable) {
            LLAMA_LOG_WARN("%s: graph reuse disabled\n", __func__);
        }
    }

    // Ordinary contexts retain the backend-friendly cache padding. The apprenticeship
    // protocol uses the caller's exact one-sequence position limit.
    if (!cparams.cassi_apprentice && !exact_n_ctx) {
        cparams.n_ctx = GGML_PAD(cparams.n_ctx, 256);
    }

    if (cparams.kv_unified) {
        cparams.n_ctx_seq = cparams.n_ctx;
    } else {
        cparams.n_ctx_seq = cparams.n_ctx / cparams.n_seq_max;
        if (!cparams.cassi_apprentice && !exact_n_ctx) {
            cparams.n_ctx_seq = GGML_PAD(cparams.n_ctx_seq, 256);
        }

        if (cparams.n_ctx_seq == 0) {
            throw std::runtime_error("n_ctx_seq == 0");
        }

        if (cparams.n_ctx != cparams.n_ctx_seq * cparams.n_seq_max) {
            cparams.n_ctx =  cparams.n_ctx_seq * cparams.n_seq_max;
            LLAMA_LOG_WARN("%s: n_ctx is not divisible by n_seq_max - rounding down to %u\n", __func__, cparams.n_ctx);
        }
    }

    LLAMA_LOG_INFO("%s: n_seq_max             = %u\n",   __func__, cparams.n_seq_max);
    LLAMA_LOG_INFO("%s: n_ctx                 = %u\n",   __func__, cparams.n_ctx);
    LLAMA_LOG_INFO("%s: n_ctx_seq             = %u\n",   __func__, cparams.n_ctx_seq);
    LLAMA_LOG_INFO("%s: n_batch               = %u\n",   __func__, cparams.n_batch);
    LLAMA_LOG_INFO("%s: n_ubatch              = %u\n",   __func__, cparams.n_ubatch);
    LLAMA_LOG_INFO("%s: causal_attn           = %d\n",   __func__, cparams.causal_attn);
    LLAMA_LOG_INFO("%s: flash_attn            = %s\n",   __func__, llama_flash_attn_type_name(params.flash_attn_type));
    LLAMA_LOG_INFO("%s: kv_unified            = %s\n",   __func__, cparams.kv_unified ? "true" : "false");
    LLAMA_LOG_INFO("%s: freq_base             = %.1f\n", __func__, cparams.rope_freq_base);
    LLAMA_LOG_INFO("%s: freq_scale            = %g\n",   __func__, cparams.rope_freq_scale);
    LLAMA_LOG_INFO("%s: n_rs_seq              = %u\n",   __func__, cparams.n_rs_seq);
    LLAMA_LOG_INFO("%s: n_outputs_max         = %u\n",   __func__, cparams.n_outputs_max);
    LLAMA_LOG_INFO("%s: n_outputs_max_per_seq = %u\n",   __func__, cparams.n_outputs_max_per_seq);

    if (cparams.n_ctx_seq < hparams.n_ctx_train) {
        LLAMA_LOG_INFO("%s: n_ctx_seq (%u) < n_ctx_train (%u) -- the full capacity of the model will not be utilized\n",
                __func__, cparams.n_ctx_seq, hparams.n_ctx_train);
    }

    if (cparams.n_ctx_seq > hparams.n_ctx_train) {
        LLAMA_LOG_WARN("%s: n_ctx_seq (%u) > n_ctx_train (%u) -- possible training context overflow\n",
                __func__, cparams.n_ctx_seq, hparams.n_ctx_train);
    }

    if (!hparams.vocab_only) {
        // GPU backends
        for (const auto & dev : model.devices) {
            ggml_backend_t backend = ggml_backend_dev_init(dev.dev, nullptr);
            if (backend == nullptr) {
                throw std::runtime_error(format("failed to initialize %s backend", ggml_backend_dev_name(dev.dev)));
            }
            backends.emplace_back(backend);
        }

        // add ACCEL backends (such as BLAS)
        for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
            ggml_backend_dev_t dev = ggml_backend_dev_get(i);
            if (ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_ACCEL) {
                ggml_backend_t backend = ggml_backend_dev_init(dev, nullptr);
                if (backend == nullptr) {
                    throw std::runtime_error(format("failed to initialize %s backend", ggml_backend_dev_name(dev)));
                }
                backends.emplace_back(backend);
            }
        }

        // add CPU backend
        backend_cpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
        if (backend_cpu == nullptr) {
            throw std::runtime_error("failed to initialize CPU backend");
        }
        backends.emplace_back(backend_cpu);

        // create a list of the set_n_threads functions in the backends
        for (auto & backend : backends) {
            ggml_backend_dev_t dev = ggml_backend_get_device(backend.get());
            ggml_backend_reg_t reg = dev ? ggml_backend_dev_backend_reg(dev) : nullptr;
            if (reg) {
                auto ggml_backend_set_n_threads_fn = (ggml_backend_set_n_threads_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_n_threads");
                if (ggml_backend_set_n_threads_fn) {
                    set_n_threads_fns.emplace_back(backend.get(), ggml_backend_set_n_threads_fn);
                }
            }
        }

        llama_set_abort_callback(this, params.abort_callback, params.abort_callback_data);

        if (!cparams.cassi_apprentice) {
            if (output_reserve(params.n_seq_max) < params.n_seq_max) {
                throw std::runtime_error("failed to reserve initial output buffer");
            }
            LLAMA_LOG_INFO("%s: %10s  output buffer size = %8.2f MiB\n", __func__,
                    ggml_backend_buffer_name    (buf_output.get()),
                    ggml_backend_buffer_get_size(buf_output.get()) / 1024.0 / 1024.0);
        }
    }

    // init the memory module
    if (!hparams.vocab_only) {
        llama_memory_params params_mem = {
            /*.type_k    =*/ params.type_k,
            /*.type_v    =*/ params.type_v,
            /*.swa_full  =*/ params.swa_full,
            /*.ctx_type  =*/ cparams.ctx_type,
            /*.mem_other =*/ llama_get_memory(cparams.ctx_other),
        };

        memory.reset(model.create_memory(params_mem, cparams));
    }

    // init backends
    if (!hparams.vocab_only) {
        LLAMA_LOG_DEBUG("%s: enumerating backends\n", __func__);

        backend_buft.clear();
        backend_ptrs.clear();
        backend_buf_exp_size.clear();

        for (auto & backend : backends) {
            auto * buft = ggml_backend_get_default_buffer_type(backend.get());
            auto backend_type = ggml_backend_dev_type(ggml_backend_get_device(backend.get()));

            if (backend_type == GGML_BACKEND_DEVICE_TYPE_CPU && !model.devices.empty()) {
                // use the host buffer of the first device CPU for faster transfer of the intermediate state
                const auto & dev = model.devices[0];
                auto * host_buft = ggml_backend_dev_host_buffer_type(dev.dev);
                if (host_buft) {
                    buft = host_buft;
                }
            }

            backend_buft.push_back(buft);
            backend_ptrs.push_back(backend.get());
            backend_buf_exp_size.push_back(0);
        }

        LLAMA_LOG_DEBUG("%s: backend_ptrs.size() = %zu\n", __func__, backend_ptrs.size());

        // TODO: move these checks to ggml_backend_sched
        // enabling pipeline parallelism in the scheduler increases memory usage, so it is only done when necessary
        bool pipeline_parallel =
            model.n_devices() > 1 &&
            model.n_gpu_layers() > model.hparams.n_layer_all &&
            model.split_mode() == LLAMA_SPLIT_MODE_LAYER &&
            cparams.offload_kqv &&
            !model.has_tensor_overrides();

        // pipeline parallelism requires support for async compute and events in all devices
        if (pipeline_parallel) {
            for (auto & backend : backends) {
                auto dev_type = ggml_backend_dev_type(ggml_backend_get_device(backend.get()));
                if (dev_type == GGML_BACKEND_DEVICE_TYPE_CPU) {
                    // ignore CPU backend
                    // TODO: should we ignore ACCEL types too?
                    continue;
                }
                auto * dev = ggml_backend_get_device(backend.get());
                ggml_backend_dev_props props;
                ggml_backend_dev_get_props(dev, &props);
                if (!props.caps.async || !props.caps.events) {
                    // device does not support async compute or events
                    pipeline_parallel = false;
                    break;
                }
            }
        }

        cparams.pipeline_parallel = pipeline_parallel;

        if (cparams.pipeline_parallel) {
            LLAMA_LOG_INFO("%s: pipeline parallelism enabled\n", __func__);
        }

        sched_reserve();

        if (!cparams.flash_attn) {
            if (ggml_is_quantized(params.type_v)) {
                throw std::runtime_error("quantized V cache was requested, but this requires Flash Attention");
            }
        }
    }

    // Initialize the full vocabulary token ids for backend samplers.
    {
        const int n_vocab = model.vocab.n_tokens();

        sampling.token_ids_full_vocab.resize(n_vocab);
        for (int i = 0; i < n_vocab; ++i) {
            sampling.token_ids_full_vocab[i] = i;
        }
    }
}

llama_context::~llama_context() {
    cassi_token_snapshot_clear();
    // wait for any pending asynchronous copies into the output buffers before they are freed
    synchronize();

    if (!model.hparams.no_alloc) {
        for (size_t i = 0; i < backend_ptrs.size(); ++i) {
            ggml_backend_t             backend = backend_ptrs[i];
            ggml_backend_buffer_type_t buft    = backend_buft[i];

            const size_t size_exp = backend_buf_exp_size[i];
            const size_t size_act = ggml_backend_sched_get_buffer_size(sched.get(), backend);
            if (size_exp == size_act) {
                LLAMA_LOG_DEBUG("%s: %10s compute buffer size is %8.4f MiB, matches expectation of %8.4f MiB\n",
                    __func__, ggml_backend_buft_name(buft), size_act / (1024.0*1024.0), size_exp / (1024.0*1024.0));
            } else {
                LLAMA_LOG_WARN("%s: %10s compute buffer size of %8.4f MiB, does not match expectation of %8.4f MiB\n",
                    __func__, ggml_backend_buft_name(buft), size_act / (1024.0*1024.0), size_exp / (1024.0*1024.0));
            }
        }
    }
    ggml_opt_free(opt_ctx);
}

void llama_context::resolve_fused_ops(const llama_memory_context_i * mctx, uint32_t n_seqs) {
    const char * func = __func__;
    auto resolve = [&](const llm_fused_op_probe & probe, bool & enabled) {
        if (!enabled) {
            return;
        }

        const uint32_t n_tokens_probe = probe.n_tokens_per_seq*n_seqs;

        auto * gf = graph_reserve(n_tokens_probe, n_seqs, n_tokens_probe, mctx, true);
        if (!gf) {
            throw std::runtime_error(std::string("failed to reserve graph for ") + probe.name + " check");
        }

        bool device_mismatch = false;
        for (const auto & node : get_gf_res_reserve()->get_fused_nodes()) {
            if (node.op != probe.op) {
                continue;
            }

            GGML_ASSERT(node.il >= 0);

            ggml_backend_t backend_fused = ggml_backend_sched_get_tensor_backend(sched.get(), node.tensor);
            ggml_backend_dev_t device_fused = backend_fused ? ggml_backend_get_device(backend_fused) : nullptr;

            // TODO: make this descriptor-specific; model.dev_layer() preserves the current behavior,
            // but is still wrong for cases like --no-kv-offload.
            ggml_backend_dev_t device_layer = model.dev_layer(node.il);

            if (device_fused != device_layer) {
                LLAMA_LOG_WARN("%s: layer %d is assigned to device %s but %s "
                        "is assigned to device %s (usually due to missing support)\n",
                        func, node.il,
                        device_layer ? ggml_backend_dev_name(device_layer) : "none",
                        probe.name,
                        device_fused ? ggml_backend_dev_name(device_fused) : "none");
                device_mismatch = true;
                break;
            }
        }

        if (device_mismatch) {
            enabled = false;
            LLAMA_LOG_WARN("%s: %s not supported, set to disabled\n", func, probe.name);
        } else {
            enabled = true;
            LLAMA_LOG_INFO("%s: %s enabled\n", func, probe.name);
        }
    };

    if (cparams.auto_fa) {
        resolve(llm_fused_op_flash_attn_probe, cparams.flash_attn);
        cparams.auto_fa = false;
    }

    if (cparams.auto_fgdn) {
        LLAMA_LOG_INFO("%s: resolving fused Gated Delta Net support:\n", func);
        resolve(llm_fused_op_gdn_ar_probe, cparams.fused_gdn_ar);
        resolve(llm_fused_op_gdn_ch_probe, cparams.fused_gdn_ch);
        cparams.auto_fgdn = false;
    }

    if (cparams.auto_flid) {
        LLAMA_LOG_INFO("%s: resolving fused Lightning Indexer support:\n", func);
        resolve(llm_fused_op_lid_probe, cparams.fused_lid);
        cparams.auto_flid = false;
    }

    if (cparams.auto_fhc) {
        LLAMA_LOG_INFO("%s: resolving fused DeepSeek V4 HC support:\n", func);
        resolve(llm_fused_op_dsv4_hc_pre_probe,  cparams.fused_dsv4_hc_pre);
        resolve(llm_fused_op_dsv4_hc_comb_probe, cparams.fused_dsv4_hc_comb);
        resolve(llm_fused_op_dsv4_hc_post_probe, cparams.fused_dsv4_hc_post);
        cparams.auto_fhc = false;
    }
}

void llama_context::sched_reserve() {
    if (!sched_need_reserve) {
        return;
    }

    sched_need_reserve = false;

    LLAMA_LOG_INFO("%s: reserving ...\n", __func__);

    synchronize();

    const int64_t t_start_us = ggml_time_us();

    const uint32_t n_seqs = cparams.n_seq_max;
    const uint32_t n_tokens = std::min(cparams.n_ctx, cparams.n_ubatch);

    const size_t max_nodes = this->graph_max_nodes(n_tokens);

    LLAMA_LOG_DEBUG("%s: max_nodes = %zu\n", __func__, max_nodes);

    gf_res_prev.reset(new llm_graph_result(max_nodes));
    gf_res_reserve.reset(new llm_graph_result(max_nodes));

    sched.reset(ggml_backend_sched_new(backend_ptrs.data(), backend_buft.data(), backend_ptrs.size(), max_nodes, cparams.pipeline_parallel, cparams.op_offload));
    if (cparams.cassi_apprentice) {
        return;
    }

    llama_memory_context_ptr mctx;
    if (memory) {
        LLAMA_LOG_DEBUG("%s: reserving full memory module\n", __func__);
        mctx = memory->init_full();
        if (!mctx) {
            throw std::runtime_error("failed to initialize memory module");
        }
    }

    // avoid reserving graphs with zero outputs - assume one output per sequence
    const int n_outputs = n_seqs;

    LLAMA_LOG_DEBUG("%s: worst-case: n_tokens = %d, n_seqs = %d, n_outputs = %d\n", __func__, n_tokens, n_seqs, n_outputs);

    resolve_fused_ops(mctx.get(), n_seqs);

    // reserve worst-case graph
    int n_splits_pp = -1;
    int n_nodes_pp  = -1;

    int n_splits_tg = -1;
    int n_nodes_tg  = -1;

    const uint32_t n_outputs_pp = std::min(n_tokens, cparams.n_outputs_max);

    // reserve pp (prompt processing) graph first so that buffers are only allocated once
    {
        auto * gf = graph_reserve(n_tokens, n_seqs, n_outputs_pp, mctx.get(),
                model.hparams.no_alloc, model.hparams.no_alloc ? backend_buf_exp_size.data() : nullptr);
        if (!gf) {
            if (cparams.pipeline_parallel) {
                LLAMA_LOG_WARN("%s: compute buffer allocation failed, retrying without pipeline parallelism\n", __func__);
                cparams.pipeline_parallel = false;
                sched.reset(ggml_backend_sched_new(backend_ptrs.data(), backend_buft.data(), backend_ptrs.size(), max_nodes, false, cparams.op_offload));
                gf = graph_reserve(n_tokens, n_seqs, n_outputs_pp, mctx.get());
            }
            if (!gf) {
                throw std::runtime_error("failed to allocate compute pp buffers");
            }
        }

        n_splits_pp = ggml_backend_sched_get_n_splits(sched.get());
        n_nodes_pp  = ggml_graph_n_nodes(gf);
    }

    // reserve with tg (token generation) graph to get the number of splits and nodes
    {
        auto * gf = graph_reserve(n_seqs, n_seqs, n_seqs, mctx.get(), model.hparams.no_alloc);
        if (!gf) {
            throw std::runtime_error("failed to allocate compute tg buffers");
        }

        n_splits_tg = ggml_backend_sched_get_n_splits(sched.get());
        n_nodes_tg  = ggml_graph_n_nodes(gf);
        cassi_qi_graph_nodes_tg = cassi_qi.enabled ? n_nodes_tg : -1;
    }

    // reserve again with pp graph to avoid ggml-alloc reallocations during inference
    {
        // TODO: not sure if the following graph would be worst case for multi-stream KV caches:
        //
        // auto * gf = graph_reserve(n_tokens, 1, n_tokens, mctx.get());
        //
        auto * gf = graph_reserve(n_tokens, n_seqs, n_outputs_pp, mctx.get(), model.hparams.no_alloc);
        if (!gf) {
            throw std::runtime_error("failed to allocate compute pp buffers");
        }
    }

    for (size_t i = 0; i < backend_ptrs.size(); ++i) {
        ggml_backend_t             backend = backend_ptrs[i];
        ggml_backend_buffer_type_t buft    = backend_buft[i];
        if (!model.hparams.no_alloc) {
            backend_buf_exp_size[i] = ggml_backend_sched_get_buffer_size(sched.get(), backend);
        }
        if (backend_buf_exp_size[i] > 1) {
            LLAMA_LOG_INFO("%s: %10s compute buffer size = %8.2f MiB\n", __func__,
                    ggml_backend_buft_name(buft),
                    backend_buf_exp_size[i] / 1024.0 / 1024.0);
        }
    }

    if (n_nodes_pp == n_nodes_tg) {
        LLAMA_LOG_INFO("%s: graph nodes  = %d\n", __func__, n_nodes_pp);
    } else {
        LLAMA_LOG_INFO("%s: graph nodes  = %d (with bs=%d), %d (with bs=1)\n", __func__, n_nodes_pp, n_tokens, n_nodes_tg);
    }

    if (n_splits_pp == n_splits_tg) {
        LLAMA_LOG_INFO("%s: graph splits = %d\n", __func__, n_splits_pp);
    } else {
        LLAMA_LOG_INFO("%s: graph splits = %d (with bs=%d), %d (with bs=1)\n", __func__, n_splits_pp, n_tokens, n_splits_tg);
    }

    const int64_t t_end_us = ggml_time_us();

    LLAMA_LOG_INFO("%s: reserve took %.2f ms, sched copies = %d\n",
            __func__, (t_end_us - t_start_us)/1000.0, ggml_backend_sched_get_n_copies(sched.get()));
}

void llama_context::synchronize() {
    if (!sched) {
        return;
    }

    ggml_backend_sched_synchronize(sched.get());
    complete_cassi_modal_state();
    complete_cassi_field_state();
    complete_cassi_qi_field_state();

    // FIXME: if multiple single tokens are evaluated without a synchronization,
    // the stats will be added to the prompt evaluation stats
    // this should only happen when using batch size 1 to evaluate a batch

    // add the evaluation to the stats
    if (n_queued_tokens == 1) {
        if (!cparams.no_perf) {
            t_eval_us += ggml_time_us() - t_compute_start_us;
        }
        n_eval++;
    } else if (n_queued_tokens > 1) {
        if (!cparams.no_perf) {
            t_p_eval_us += ggml_time_us() - t_compute_start_us;
        }
        n_p_eval += n_queued_tokens;
    }

    // get a more accurate load time, upon first eval
    if (n_queued_tokens > 0 && !has_evaluated_once) {
        t_load_us = ggml_time_us() - t_start_us;
        has_evaluated_once = true;
    }

    n_queued_tokens = 0;
    t_compute_start_us = 0;
}

void llama_context::queue_cassi_modal_state(const llm_graph_result * res, const llama_ubatch & ubatch) {
    if (!cassi_modal.enabled || cassi_modal_pending.valid) {
        return;
    }

    ggml_tensor * t_cassi = res != nullptr ? res->get_cassi() : nullptr;
    if (t_cassi == nullptr || ubatch.seq_id_unq == nullptr || ubatch.n_seqs_unq == 0) {
        return;
    }

    const uint32_t n_seqs = ubatch.n_seqs_unq;
    const size_t state_bytes = (size_t) cassi_modal.state_stride * sizeof(float);
    const size_t correction_count = (size_t) 2 * cassi_modal.mode_count * ubatch.n_tokens;
    const size_t state_count = (size_t) n_seqs * cassi_modal.state_stride;
    GGML_ASSERT(t_cassi->type == GGML_TYPE_F32);
    GGML_ASSERT(t_cassi->ne[0] == (int64_t) (correction_count + state_count));
    GGML_ASSERT(t_cassi->ne[1] == 1);
    GGML_ASSERT(t_cassi->ne[2] == 1 && t_cassi->ne[3] == 1);

    const ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched.get(), t_cassi);
    GGML_ASSERT(backend != nullptr);

    cassi_modal_pending.seq_ids.assign(ubatch.seq_id_unq, ubatch.seq_id_unq + n_seqs);
    cassi_modal_pending.state.resize((size_t) n_seqs * cassi_modal.state_stride);

    // The output is [correction (2*M,T), state (8*M,S)]. Queue one async
    // copy per sequence so the copied state remains keyed by unique sequence
    // order, independent of token order in the batch.
    const size_t state_offset = correction_count * sizeof(float);
    for (uint32_t s = 0; s < n_seqs; ++s) {
        ggml_backend_tensor_get_async(
            backend, t_cassi,
            cassi_modal_pending.state.data() + (size_t) s * cassi_modal.state_stride,
            state_offset + (size_t) s * state_bytes,
            state_bytes);
    }

    cassi_modal_pending.valid = true;
}

void llama_context::complete_cassi_modal_state() {
    if (!cassi_modal_pending.valid) {
        return;
    }

    for (size_t s = 0; s < cassi_modal_pending.seq_ids.size(); ++s) {
        const llama_seq_id seq_id = cassi_modal_pending.seq_ids[s];
        if (seq_id < 0 || (uint32_t) seq_id >= cassi_modal.n_seq_max) {
            continue;
        }

        std::memcpy(
            cassi_modal.state + (size_t) seq_id * cassi_modal.state_stride,
            cassi_modal_pending.state.data() + s * cassi_modal.state_stride,
            (size_t) cassi_modal.state_stride * sizeof(float));
    }

    cassi_modal_pending.valid = false;
    cassi_modal_pending.seq_ids.clear();
    cassi_modal_pending.state.clear();
}
void llama_context::queue_cassi_field_state(const llm_graph_result * res, const llama_ubatch & ubatch) {
    if (!cassi_field.enabled || cassi_field_pending.valid) {
        return;
    }

    ggml_tensor * t_field = res != nullptr ? res->get_cassi_field() : nullptr;
    if (t_field == nullptr || ubatch.seq_id_unq == nullptr || ubatch.n_seqs_unq == 0) {
        return;
    }

    const uint32_t n_seqs = ubatch.n_seqs_unq;
    const size_t state_bytes = (size_t) cassi_field.state_stride * sizeof(float);
    const size_t correction_count = (size_t) 2 * cassi_field.mode_count * ubatch.n_tokens;
    const size_t state_count = (size_t) n_seqs * cassi_field.state_stride;
    GGML_ASSERT(t_field->type == GGML_TYPE_F32);
    GGML_ASSERT(t_field->ne[0] == (int64_t) (correction_count + state_count));
    GGML_ASSERT(t_field->ne[1] == 1);
    GGML_ASSERT(t_field->ne[2] == 1 && t_field->ne[3] == 1);

    const ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched.get(), t_field);
    GGML_ASSERT(backend != nullptr);

    cassi_field_pending.seq_ids.assign(ubatch.seq_id_unq, ubatch.seq_id_unq + n_seqs);
    cassi_field_pending.state.resize((size_t) n_seqs * cassi_field.state_stride);
    const size_t state_offset = correction_count * sizeof(float);
    for (uint32_t s = 0; s < n_seqs; ++s) {
        ggml_backend_tensor_get_async(
            backend, t_field,
            cassi_field_pending.state.data() + (size_t) s * cassi_field.state_stride,
            state_offset + (size_t) s * state_bytes,
            state_bytes);
    }
    cassi_field_pending.valid = true;
}

void llama_context::complete_cassi_field_state() {
    if (!cassi_field_pending.valid) {
        return;
    }

    for (size_t s = 0; s < cassi_field_pending.seq_ids.size(); ++s) {
        const llama_seq_id seq_id = cassi_field_pending.seq_ids[s];
        if (seq_id < 0 || (uint32_t) seq_id >= cassi_field.n_seq_max) {
            continue;
        }
        std::memcpy(
            cassi_field.state + (size_t) seq_id * cassi_field.state_stride,
            cassi_field_pending.state.data() + s * cassi_field.state_stride,
            (size_t) cassi_field.state_stride * sizeof(float));
    }

    cassi_field_pending.valid = false;
    cassi_field_pending.seq_ids.clear();
    cassi_field_pending.state.clear();
}

void llama_context::queue_cassi_qi_field_state(const llm_graph_result * res, const llama_ubatch & ubatch) {
    if (res != nullptr) {
        cassi_qi_seam_field_width = res->get_cassi_qi_state_field_width();
        cassi_qi_seam_row_width = res->get_cassi_qi_state_row_width();
    }
    if (!cassi_qi.enabled || cassi_qi_pending.valid) {
        return;
    }
    ggml_tensor * t_qi = res != nullptr ? res->get_cassi_qi() : nullptr;
    if (t_qi == nullptr || ubatch.seq_id_unq == nullptr || ubatch.n_seqs_unq == 0) {
        return;
    }
    const uint32_t n_seqs = ubatch.n_seqs_unq;
    const size_t state_bytes = (size_t) cassi_qi.state_stride * sizeof(float);
    const size_t flux_count = (size_t) 2 * cassi_qi.wave_mode_count * ubatch.n_tokens;
    const size_t state_count = (size_t) n_seqs * cassi_qi.state_stride;
    const size_t diag_count = (size_t) 10 * cassi_qi.scale_count * n_seqs;
    GGML_ASSERT(t_qi->type == GGML_TYPE_F32);
    GGML_ASSERT(t_qi->ne[0] == (int64_t) (flux_count + state_count + diag_count));
    GGML_ASSERT(t_qi->ne[1] == 1 && t_qi->ne[2] == 1 && t_qi->ne[3] == 1);
    const ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched.get(), t_qi);
    GGML_ASSERT(backend != nullptr);
    cassi_qi_pending.seq_ids.assign(ubatch.seq_id_unq, ubatch.seq_id_unq + n_seqs);
    cassi_qi_pending.state.resize((size_t) n_seqs * cassi_qi.state_stride);
    // The seam reads the flux region, so the newest token's block is kept for inspection.
    const size_t flux_block = (size_t) 2 * cassi_qi.wave_mode_count;
    cassi_qi_pending.flux.resize(flux_block);
    ggml_backend_tensor_get_async(backend, t_qi, cassi_qi_pending.flux.data(),
        (ubatch.n_tokens - 1) * flux_block * sizeof(float), flux_block * sizeof(float));
    const size_t state_offset = flux_count * sizeof(float);
    for (uint32_t s = 0; s < n_seqs; ++s) {
        ggml_backend_tensor_get_async(
            backend, t_qi,
            cassi_qi_pending.state.data() + (size_t) s * cassi_qi.state_stride,
            state_offset + (size_t) s * state_bytes,
            state_bytes);
    }
    cassi_qi_pending.valid = true;
    // The modulation seam's two scalars, when this build carried the seam.
    ggml_tensor * seam_budget = res->get_cassi_qi_seam_budget();
    ggml_tensor * seam_scale  = res->get_cassi_qi_seam_scale();
    cassi_qi_pending.seam_valid = false;
    if (seam_budget != nullptr && seam_scale != nullptr) {
        const ggml_backend_t seam_backend = ggml_backend_sched_get_tensor_backend(sched.get(), seam_budget);
        GGML_ASSERT(ggml_backend_sched_get_tensor_backend(sched.get(), seam_scale) == seam_backend);
        if (seam_backend != nullptr) {
            cassi_qi_pending.seam_budget = 0.0f;
            cassi_qi_pending.seam_scale  = 0.0f;
            ggml_backend_tensor_get_async(seam_backend, seam_budget, &cassi_qi_pending.seam_budget, 0, sizeof(float));
            ggml_backend_tensor_get_async(seam_backend, seam_scale, &cassi_qi_pending.seam_scale, 0, sizeof(float));
            cassi_qi_pending.seam_valid = true;
        }
    }
}

void llama_context::complete_cassi_qi_field_state() {
    if (!cassi_qi_pending.valid) {
        return;
    }
    for (size_t s = 0; s < cassi_qi_pending.seq_ids.size(); ++s) {
        const llama_seq_id seq_id = cassi_qi_pending.seq_ids[s];
        if (seq_id < 0 || (uint32_t) seq_id >= cassi_qi.n_seq_max) {
            continue;
        }
        std::memcpy(
            cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
            cassi_qi_pending.state.data() + s * cassi_qi.state_stride,
            (size_t) cassi_qi.state_stride * sizeof(float));
    }
    cassi_qi_flux_last = cassi_qi_pending.flux;
    if (cassi_qi_pending.seam_valid) {
        cassi_qi_seam_budget_last = cassi_qi_pending.seam_budget;
        cassi_qi_seam_scale_last  = cassi_qi_pending.seam_scale;
    }
    cassi_qi_pending.valid = false;
    cassi_qi_pending.seam_valid = false;
    cassi_qi_pending.seq_ids.clear();
    cassi_qi_pending.state.clear();
    cassi_qi_pending.flux.clear();
}

const llama_model & llama_context::get_model() const {
    return model;
}

const llama_cparams & llama_context::get_cparams() const {
    return cparams;
}

ggml_backend_sched_t llama_context::get_sched() const {
    return sched.get();
}

uint32_t llama_context::n_ctx() const {
    return cparams.n_ctx;
}

uint32_t llama_context::n_ctx_seq() const {
    return cparams.n_ctx_seq;
}

uint32_t llama_context::n_batch() const {
    return cparams.n_batch;
}

uint32_t llama_context::n_ubatch() const {
    return cparams.n_ubatch;
}

uint32_t llama_context::n_seq_max() const {
    return cparams.n_seq_max;
}

uint32_t llama_context::n_threads() const {
    return cparams.n_threads;
}

uint32_t llama_context::n_threads_batch() const {
    return cparams.n_threads_batch;
}

llama_memory_t llama_context::get_memory() const {
    return memory.get();
}

bool llama_context::memory_update(bool optimize) {
    if (!memory) {
        return false;
    }

    {
        const auto mctx = memory->init_update(this, optimize);
        switch (mctx->get_status()) {
            case LLAMA_MEMORY_STATUS_SUCCESS:
                {
                    // noop
                } break;
            case LLAMA_MEMORY_STATUS_NO_UPDATE:
                {
                    // no updates need to be performed
                    return false;
                }
            case LLAMA_MEMORY_STATUS_FAILED_PREPARE:
            case LLAMA_MEMORY_STATUS_FAILED_COMPUTE:
                {
                    LLAMA_LOG_ERROR("%s: failed to prepare memory update\n", __func__);
                    return false;
                }
        }

        // reset the previous graph result to make sure that it won't be reused
        // TODO: change the mctx->apply() to return information if a graph reserve is needed
        //       reset the graph result only if the memory module did reset the scheduler
        gf_res_prev->reset();

        if (!mctx->apply()) {
            LLAMA_LOG_ERROR("%s: failed to apply memory update\n", __func__);
        }
    }

    // if the memory module did any computation, we have to reserve a new worst-case graph
    {
        const auto mctx = memory->init_full();
        if (!mctx) {
            throw std::runtime_error("failed to initialize memory context");
        }

        const uint32_t n_seqs = cparams.n_seq_max;
        const uint32_t n_tokens = std::min(cparams.n_ctx, cparams.n_ubatch);

        const uint32_t n_outputs_max = std::min(n_tokens, cparams.n_outputs_max);

        auto * gf = graph_reserve(n_tokens, n_seqs, n_outputs_max, mctx.get());
        if (!gf) {
            LLAMA_LOG_ERROR("%s: failed to reserve graph after the memory update\n", __func__);
        }
    }

    return true;
}

enum llama_pooling_type llama_context::pooling_type() const {
    return cparams.pooling_type;
}

float * llama_context::get_logits() {
    output_reorder();

    return logits.data;
}

int64_t llama_context::output_resolve_row(int32_t i) const {
    int64_t j = -1;

    // support negative indices (last output row)
    if (i < 0) {
        j = n_outputs + i;
        if (j < 0) {
            throw std::runtime_error(format("negative index out of range [0, %d)", n_outputs));
        }
    } else if ((size_t) i >= output_ids.size()) {
        throw std::runtime_error(format("out of range [0, %zu)", output_ids.size()));
    } else {
        // use output_ids to translate the batch token index into a row number
        // that holds this token's data.
        j = output_ids[i];
    }

    if (j < 0) {
        // the batch token was not configured to output anything
        throw std::runtime_error(format("batch.logits[%d] != true", i));
    }

    if (j >= n_outputs) {
        throw std::runtime_error(format("corrupt output buffer (j=%" PRId64 ", n_outputs=%d)", j, n_outputs));
    }

    return j;
}

float * llama_context::get_logits_ith(int32_t i) {
    output_reorder();

    try {
        if (logits.data == nullptr) {
            throw std::runtime_error("no logits");
        }

        const int64_t j = output_resolve_row(i);
        return logits.data + j*model.vocab.n_tokens();
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid logits id %d, reason: %s\n", __func__, i, err.what());
#ifndef NDEBUG
        GGML_ABORT("fatal error");
#else
        return nullptr;
#endif
    }
}

float * llama_context::get_embeddings() {
    output_reorder();

    return embd.data;
}

llama_token * llama_context::get_sampled_tokens()  const{
    return sampling.sampled.data;
}

float * llama_context::get_embeddings_ith(int32_t i) {
    output_reorder();

    try {
        if (embd.data == nullptr) {
            throw std::runtime_error("no embeddings");
        }

        const int64_t j = output_resolve_row(i);
        const uint32_t n_embd_out = model.hparams.n_embd_out();
        return embd.data + j*n_embd_out;
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid embeddings id %d, reason: %s\n", __func__, i, err.what());
#ifndef NDEBUG
        GGML_ABORT("fatal error");
#else
        return nullptr;
#endif
    }
}

float * llama_context::get_embeddings_seq(llama_seq_id seq_id) {
    auto it = embd_seq.find(seq_id);
    if (it == embd_seq.end()) {
        return nullptr;
    }

    return it->second.data();
}

float * llama_context::get_embeddings_nextn() {
    output_reorder();

    return embd_nextn.data;
}

float * llama_context::get_embeddings_nextn_ith(int32_t i) {
    output_reorder();

    try {
        if (embd_nextn.data == nullptr) {
            throw std::runtime_error("no nextn embeddings");
        }

        const uint32_t n_embd = model.hparams.n_embd_out();

        if (!cparams.embeddings_nextn_masked) {
            // unmasked: nextn rows are stored densely, indexed by raw token position.
            if (i < 0 || (size_t)(i + 1) * n_embd > embd_nextn.size) {
                throw std::runtime_error(format("out of range [0, %zu)", embd_nextn.size / n_embd));
            }
            return embd_nextn.data + (size_t) i * n_embd;
        }

        const int64_t j = output_resolve_row(i);
        return embd_nextn.data + j*n_embd;
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid nextn embeddings id %d, reason: %s\n", __func__, i, err.what());
#ifndef NDEBUG
        GGML_ABORT("fatal error");
#else
        return nullptr;
#endif
    }
}

float * llama_context::get_embeddings_layer_inp(uint32_t lid) {
    output_reorder();

    GGML_ASSERT(lid < embd_layer_inp.size() && embd_layer_inp[lid].has_data());

    return embd_layer_inp[lid].data;
}

llama_token llama_context::get_sampled_token_ith(int32_t idx) {
    output_reorder();

    if (!sampling.sampled.has_data()) {
        return LLAMA_TOKEN_NULL;
    }

    try {
        const int64_t row = output_resolve_row(idx);
        GGML_ASSERT(row < (int64_t) sampling.sampled.size);
        return sampling.sampled.data[row];
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled token id %d, reason: %s\n", __func__, idx, err.what());
        return LLAMA_TOKEN_NULL;
    }
}

float * llama_context::get_sampled_probs_ith(int32_t idx) {
    output_reorder();

    if (!sampling.probs.has_data()) {
        return nullptr;
    }

    try {
        const int64_t row = output_resolve_row(idx);
        if ((size_t) row >= sampling.probs_count.size() || sampling.probs_count[row] == 0) {
            return nullptr;
        }
        return sampling.probs.data + row*model.vocab.n_tokens();
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled probs id %d, reason: %s\n", __func__, idx, err.what());
        return nullptr;
    }
}

float * llama_context::get_sampled_logits_ith(int32_t idx) {
    output_reorder();

    if (!sampling.logits.has_data()) {
        return nullptr;
    }

    try {
        const int64_t row = output_resolve_row(idx);
        if ((size_t) row >= sampling.logits_count.size() || sampling.logits_count[row] == 0) {
            return nullptr;
        }
        return sampling.logits.data + row*model.vocab.n_tokens();
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled logits id %d, reason: %s\n", __func__, idx, err.what());
        return nullptr;
    }
}

const llama_token * llama_context::get_sampled_candidates_ith(int32_t idx) {
    output_reorder();

    try {
        const int64_t row = output_resolve_row(idx);
        if (sampling.candidates.has_data() &&
            (size_t) row < sampling.candidates_count.size() &&
            sampling.candidates_count[row] > 0) {
            return sampling.candidates.data + row*model.vocab.n_tokens();
        }
    } catch (const std::exception & err) {
        // fallback to full vocab list
        GGML_UNUSED(err);
    }

    return sampling.token_ids_full_vocab.data();
}

size_t llama_context::get_sampled_candidates_count(int32_t idx) {
    output_reorder();

    if (!sampling.candidates.has_data()) {
        return 0;
    }

    try {
        const int64_t row = output_resolve_row(idx);
        if ((size_t) row >= sampling.candidates_count.size()) {
            return 0;
        }
        return sampling.candidates_count[row];
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled candidates count id %d, reason: %s\n", __func__, idx, err.what());
        return 0;
    }
}

size_t llama_context::get_sampled_logits_count(int32_t idx) {
    output_reorder();

    if (!sampling.logits.has_data()) {
        return model.vocab.n_tokens();
    }

    try {
        const int64_t row = output_resolve_row(idx);
        if ((size_t) row >= sampling.logits_count.size()) {
            return 0;
        }
        return sampling.logits_count[row];
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled logits count id %d, reason: %s\n", __func__, idx, err.what());
        return 0;
    }
}

size_t llama_context::get_sampled_probs_count(int32_t idx) {
    output_reorder();

    if (!sampling.probs.has_data()) {
        return 0;
    }

    try {
        const int64_t row = output_resolve_row(idx);
        if ((size_t) row >= sampling.probs_count.size()) {
            return 0;
        }
        return sampling.probs_count[row];
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: invalid backend sampled probs count id %d, reason: %s\n", __func__, idx, err.what());
        return 0;
    }
}


void llama_context::attach_threadpool(
           ggml_threadpool_t threadpool,
           ggml_threadpool_t threadpool_batch) {
    LLAMA_LOG_DEBUG("%s: call\n", __func__);

    this->threadpool       = threadpool;
    this->threadpool_batch = threadpool_batch ? threadpool_batch : threadpool;
}

void llama_context::detach_threadpool() {
    LLAMA_LOG_DEBUG("%s: call\n", __func__);

    this->threadpool       = nullptr;
    this->threadpool_batch = nullptr;
}

void llama_context::set_n_threads(int32_t n_threads, int32_t n_threads_batch) {
    LLAMA_LOG_DEBUG("%s: n_threads = %d, n_threads_batch = %d\n", __func__, n_threads, n_threads_batch);

    cparams.n_threads       = n_threads;
    cparams.n_threads_batch = n_threads_batch;
}

void llama_context::set_abort_callback(bool (*abort_callback)(void * data), void * abort_callback_data) {
    LLAMA_LOG_DEBUG("%s: call\n", __func__);

    this->abort_callback      = abort_callback;
    this->abort_callback_data = abort_callback_data;

    for (auto & backend : backends) {
        auto * reg = ggml_backend_dev_backend_reg(ggml_backend_get_device(backend.get()));
        if (reg) {
            auto * set_abort_callback_fn = (ggml_backend_set_abort_callback_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_abort_callback");
            if (set_abort_callback_fn) {
                set_abort_callback_fn(backend.get(), this->abort_callback, this->abort_callback_data);
            }
        }
    }
}

void llama_context::set_embeddings(bool value) {
    LLAMA_LOG_DEBUG("%s: value = %d\n", __func__, value);

    cparams.embeddings = value;

    // TODO: not sure yet if we want to reserve here
    //sched_need_reserve = true;
}

void llama_context::set_embeddings_nextn(bool value, bool masked) {
    LLAMA_LOG_DEBUG("%s: value = %d, masked = %d\n", __func__, value, masked);

    cparams.embeddings_nextn        = value;
    cparams.embeddings_nextn_masked = masked;
}

void llama_context::set_embeddings_layer_inp(uint32_t lid, bool enable) {
    LLAMA_LOG_DEBUG("%s: lid = %d, enable = %d\n", __func__, lid, enable);

    GGML_ASSERT(lid <= model.hparams.n_layer());

    cparams.embeddings_layer_inp[lid] = enable;

    // note: without this reserve, the draft acceptance drops to zero. not sure why - this is unexpected
    sched_need_reserve = true;
}

void llama_context::set_nextn_layer_offset(int32_t offset) {
    cparams.nextn_layer_offset = offset;
}

void llama_context::set_causal_attn(bool value) {
    LLAMA_LOG_DEBUG("%s: value = %d\n", __func__, value);

    if (cparams.causal_attn == value) {
        return;
    }

    cparams.causal_attn = value;

    sched_need_reserve = true;
}

void llama_context::set_warmup(bool value) {
    LLAMA_LOG_DEBUG("%s: value = %d\n", __func__, value);

    if (cparams.warmup == value) {
        return;
    }

    cparams.warmup = value;

    // warmups are usually with small batches, so no need to reserve
    //sched_need_reserve = true;
}

bool llama_context::set_sampler(llama_seq_id seq_id, llama_sampler * sampler) {
    if (!sampler && sampling.samplers.count(seq_id) == 0) {
        return true;
    }

    LLAMA_LOG_DEBUG("%s: seq_id = %d, sampler = %p\n", __func__, (int) seq_id, (void *) sampler);

    if (sampler && model.split_mode() == LLAMA_SPLIT_MODE_TENSOR) {
        static bool warned = false;
        if (!warned) {
            LLAMA_LOG_WARN("%s: backend sampling not supported with SPLIT_MODE_TENSOR; using CPU\n", __func__);
            warned = true;
        }
        if (sampling.samplers.count(seq_id) > 0) {
            sched_need_reserve = true;
        }
        sampling.samplers.erase(seq_id);
        return false;
    }

    const bool can_offload =
        sampler &&
        sampler->iface->backend_init &&
        sampler->iface->backend_apply &&
        llama_sampler_chain_n(sampler) > 0;

    if (sampler && can_offload) {
        auto * buft = ggml_backend_dev_buffer_type(model.dev_output());

        sampler->iface->backend_init(sampler, buft, cparams.n_outputs_max_per_seq);

        sampling.samplers[seq_id] = sampler;

        sched_need_reserve = true;

        return true;
    }

    if (sampler && !can_offload) {
        LLAMA_LOG_WARN("%s: sampler '%s' for seq_id = %d, cannot be offloaded to the backend\n", __func__, llama_sampler_name(sampler), seq_id);

        if (sampling.samplers.count(seq_id) > 0) {
            sched_need_reserve = true;
        }

        sampling.samplers.erase(seq_id);

        return false;
    }

    sampling.samplers.erase(seq_id);

    sched_need_reserve = true;

    return true;
}

void llama_context::set_adapters_lora(llama_adapter_lora ** adapters, size_t n_adapters, float * scales) {
    LLAMA_LOG_DEBUG("%s: adapters = %p\n", __func__, (void *) adapters);

    if (adapters_lora_are_same(adapters, n_adapters, scales)) {
        return;
    }

    loras.reset(new llama_adapter_loras());

    for (size_t i = 0; i < n_adapters; i ++) {
        if (scales[i] != 0.0f) {
            loras->insert({adapters[i], scales[i]});
        }
    }

    sched_need_reserve = true;
}

bool llama_context::adapters_lora_are_same(llama_adapter_lora ** adapters, size_t n_adapters, float * scales) {
    LLAMA_LOG_DEBUG("%s: adapters = %p\n", __func__, (void *) adapters);

    // Adapters with a zero scale are never added to `loras`, so also ignore them for the comparison.
    size_t n_non_zero = 0;

    for (size_t i = 0; i < n_adapters; i ++) {
        if (scales[i] == 0.0f) {
            continue;
        }
        n_non_zero++;

        auto it = loras->find(adapters[i]);

        if (it == loras->end() || it->second != scales[i]) {
            return false;
        }
    }

    if (n_non_zero != loras->size()) {
        return false;
    }

    return true;
}

bool llama_context::set_adapter_cvec(
            const float * data,
                 size_t   len,
                int32_t   n_embd,
                int32_t   il_start,
                int32_t   il_end) {
    LLAMA_LOG_DEBUG("%s: il_start = %d, il_end = %d\n", __func__, il_start, il_end);

    bool res = cvec->apply(model, data, len, n_embd, il_start, il_end);

    sched_need_reserve = true;

    return res;
}

int64_t llama_context::cassi_qi_flux_size() const {
    return (int64_t) cassi_qi_flux_last.size();
}

const float * llama_context::cassi_qi_flux_data() const {
    return cassi_qi_flux_last.empty() ? nullptr : cassi_qi_flux_last.data();
}

size_t llama_context::cassi_qi_state_size() const {
    return cassi_qi.enabled ? cassi_qi.state_stride : 0;
}

size_t llama_context::cassi_qi_mode_count() const {
    return cassi_qi.enabled ? cassi_qi.mode_count : 0;
}

int32_t llama_context::cassi_qi_graph_node_count() const {
    return cassi_qi.enabled ? cassi_qi_graph_nodes_tg : -1;
}

int64_t llama_context::cassi_qi_state_field_width() const {
    return cassi_qi_seam_field_width;
}

int64_t llama_context::cassi_qi_state_row_width() const {
    return cassi_qi_seam_row_width;
}

float llama_context::cassi_qi_seam_budget() const {
    return cassi_qi_seam_budget_last;
}

float llama_context::cassi_qi_seam_scale() const {
    return cassi_qi_seam_scale_last;
}

bool llama_context::set_cassi_qi_coupling(uint32_t steps, float injection_scale) {
    if (!cassi_qi.enabled || steps == 0 || !std::isfinite(injection_scale) ||
            injection_scale < 0.0f) {
        return false;
    }
    if (cassi_qi.steps == steps && cassi_qi.injection_scale == injection_scale) {
        return true;
    }
    complete_cassi_qi_field_state();
    cassi_qi.steps = steps;
    cassi_qi.injection_scale = injection_scale;
    cparams.cassi_qi_field_steps = steps;
    cparams.cassi_qi_injection_scale = injection_scale;
    // The reserved graph count described the coupling held at construction time.
    // the reserved node count described the construction-time coupling
    cassi_qi_graph_nodes_tg = -1;
    return true;
}

bool llama_context::set_cassi_qi_state(llama_seq_id seq_id, const float * data, size_t count) {
    if (!cassi_qi.enabled || data == nullptr || seq_id < 0 ||
            (uint32_t) seq_id >= cassi_qi.n_seq_max || count != cassi_qi.state_stride) {
        return false;
    }
    complete_cassi_qi_field_state();
    std::memcpy(
        cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
        data,
        count * sizeof(float));
    return true;
}

bool llama_context::set_cassi_qi_mode_bank(const float * data, size_t count) {
    if (!cassi_qi.enabled || data == nullptr || count != cassi_qi.mode_count) {
        return false;
    }
    // A mode cannot forget faster than it can be written: the per-token energy decay is
    // gamma * dt, so the bank has to stay inside (0, 4] or the mode is a reset, not a memory.
    const float limit = 4.0f / std::max(cassi_qi.dt, 1.0e-6f);
    for (size_t i = 0; i < count; ++i) {
        if (!std::isfinite(data[i]) || data[i] <= 0.0f || data[i] > limit) {
            return false;
        }
    }
    cassi_qi_mode_bank.assign(data, data + count);
    cassi_qi.mode_bank = cassi_qi_mode_bank.data();
    // The bank's own range becomes the integrator clamp, so a learned local rate is not
    // clipped back into the generated profile's band.
    const float lo = *std::min_element(cassi_qi_mode_bank.begin(), cassi_qi_mode_bank.end());
    const float hi = *std::max_element(cassi_qi_mode_bank.begin(), cassi_qi_mode_bank.end());
    cassi_qi.damping_min    = lo;
    cassi_qi.damping_max    = hi;
    cassi_qi.mode_param_min = lo;
    cassi_qi.mode_param_max = hi;
    return true;
}

bool llama_context::get_cassi_qi_state(llama_seq_id seq_id, float * data, size_t count) {
    if (!cassi_qi.enabled || data == nullptr || seq_id < 0 ||
            (uint32_t) seq_id >= cassi_qi.n_seq_max || count != cassi_qi.state_stride) {
        return false;
    }
    complete_cassi_qi_field_state();
    std::memcpy(
        data,
        cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
        count * sizeof(float));
    return true;
}

float llama_context::score_cassi_qi_token(llama_seq_id seq_id, llama_token token) {
    if (!cassi_qi.enabled || seq_id < 0 || (uint32_t) seq_id >= cassi_qi.n_seq_max || token < 0) {
        return -INFINITY;
    }
    complete_cassi_qi_field_state();
    const uint32_t M = cassi_qi.mode_count;
    const uint32_t W = cassi_qi.wave_mode_count;
    const size_t seq_base = (size_t) seq_id * cassi_qi.state_stride;
    uint32_t mixed = (uint32_t) token * 2654435761u + 2246822519u;
    const float phase = 6.2831853071795864769f * (float) (mixed & 0x00ffffffu) / 16777216.0f;
    const float phase_re = std::cos(phase);
    const float phase_im = std::sin(phase);
    float score = 0.0f;
    float scale_weight = 1.0f;
    for (uint32_t s = 0; s < cassi_qi.scale_count; ++s) {
        const uint32_t active_mode = mixed % W;
        const size_t active = seq_base + ((size_t) s * M + active_mode) * 9;
        const float context_re = cassi_qi.state[active + 0] - cassi_qi.phi * cassi_qi.state[active + 2];
        const float context_im = cassi_qi.state[active + 1] - cassi_qi.phi * cassi_qi.state[active + 3];
        const float context_norm = std::sqrt(context_re * context_re + context_im * context_im);
        score += scale_weight * (context_re * phase_re + context_im * phase_im)
            / std::max(cassi_qi.read_floor, context_norm);
        if (M > W) {
            const uint32_t memory_mode = W + ((mixed ^ (mixed >> 16)) % (M - W));
            const size_t memory = seq_base + ((size_t) s * M + memory_mode) * 9;
            const float memory_re = cassi_qi.phi * cassi_qi.state[memory + 0] + cassi_qi.state[memory + 2];
            const float memory_im = cassi_qi.phi * cassi_qi.state[memory + 1] + cassi_qi.state[memory + 3];
            const float memory_norm = std::sqrt(memory_re * memory_re + memory_im * memory_im);
            score += 0.5f * scale_weight * (memory_re * phase_re + memory_im * phase_im)
                / std::max(cassi_qi.read_floor, memory_norm);
        }
        scale_weight /= cassi_qi.scale_ratio;
        mixed = mixed * 1664525u + 1013904223u;
    }
    return std::isfinite(score) ? score : -INFINITY;
}

static void graph_site_candidate_bind_identity(
        const llm_graph_site_candidate_config & candidate,
        llm_graph_site_candidate_result & result) {
    result.owner_generation = candidate.owner_generation;
    result.request_sha256 = candidate.request_sha256;
    result.request_sha256_pending = candidate.request_sha256_pending;
    result.invocation_sha256 = candidate.invocation_sha256;
    result.predecessor_sha256 = candidate.predecessor_sha256;
    result.candidate_sha256 = candidate.candidate_sha256;
}

void llama_context::cassi_token_snapshot_clear() {
    if (cassi_service_sampler_snapshot != nullptr) {
        llama_sampler_free(cassi_service_sampler_snapshot);
        cassi_service_sampler_snapshot = nullptr;
    }
    cassi_service_sampler_target = nullptr;
    cassi_service_state_snapshot.clear();
    cassi_service_snapshot_seq = -1;
    cassi_service_snapshot_next_pos = -1;
    cassi_service_snapshot_committed = false;
    cassi_service_snapshot_valid = false;
    cassi_service_snapshot_graph_sequence_id.clear();
    cassi_service_snapshot_graph_sequence_state = {};
    cassi_service_snapshot_graph_sequence_exists = false;
}

bool llama_context::cassi_token_snapshot_capture(llama_seq_id seq_id) {
    cassi_token_snapshot_clear();
    if (!graph_site_candidate_pending || seq_id < 0) {
        return false;
    }
    const auto sampler_it = sampling.samplers.find(seq_id);
    llama_sampler * sampler = sampler_it == sampling.samplers.end() ? nullptr : sampler_it->second;
    if (!graph_site_sampler_cloneable(sampler)) {
        return false;
    }
    try {
        const size_t state_size = state_seq_get_size(seq_id, LLAMA_STATE_SEQ_FLAGS_NONE);
        if (state_size == 0) {
            return false;
        }
        cassi_service_state_snapshot.resize(state_size);
        if (state_seq_get_data(
                seq_id, cassi_service_state_snapshot.data(), state_size,
                LLAMA_STATE_SEQ_FLAGS_NONE) != state_size) {
            cassi_token_snapshot_clear();
            return false;
        }
        cassi_service_sampler_target = sampler;
        if (cassi_service_sampler_target != nullptr) {
            cassi_service_sampler_snapshot =
                llama_sampler_clone(cassi_service_sampler_target);
            if (cassi_service_sampler_snapshot == nullptr) {
                cassi_token_snapshot_clear();
                return false;
            }
        }
        cassi_service_snapshot_seq = seq_id;
        cassi_service_snapshot_next_pos = cassi_service_next_pos;
        cassi_service_snapshot_graph_sequence_id = graph_site_candidate.sequence_id;
        const auto graph_state = graph_site_sequence_states.find(
            cassi_service_snapshot_graph_sequence_id);
        if (graph_state != graph_site_sequence_states.end()) {
            cassi_service_snapshot_graph_sequence_state = graph_state->second;
            cassi_service_snapshot_graph_sequence_exists = true;
        }
        cassi_service_snapshot_valid = true;
        return true;
    } catch (...) {
        cassi_token_snapshot_clear();
        return false;
    }
}

bool llama_context::cassi_token_snapshot_restore() {
    if (!cassi_service_snapshot_valid || cassi_service_snapshot_seq < 0 ||
            cassi_service_state_snapshot.empty()) {
        return false;
    }
    bool restored = false;
    try {
        const size_t bytes = state_seq_set_data(
            cassi_service_snapshot_seq,
            cassi_service_state_snapshot.data(),
            cassi_service_state_snapshot.size(),
            0);
        restored = bytes == cassi_service_state_snapshot.size();
        if (restored) {
            const llama_seq_id seq_id = cassi_service_snapshot_seq;
            const auto sampler_it = sampling.samplers.find(seq_id);
            llama_sampler * current_sampler =
                sampler_it == sampling.samplers.end() ? nullptr : sampler_it->second;
            if (cassi_service_sampler_target != nullptr) {
                restored = current_sampler == cassi_service_sampler_target &&
                    cassi_service_sampler_snapshot != nullptr;
                if (restored) {
                    llama_sampler_copy(cassi_service_sampler_snapshot, current_sampler);
                }
            } else {
                restored = current_sampler == nullptr &&
                    cassi_service_sampler_snapshot == nullptr;
            }
        }
        if (restored) {
            cassi_service_next_pos = cassi_service_snapshot_next_pos;
            if (cassi_service_snapshot_graph_sequence_exists) {
                graph_site_sequence_states[cassi_service_snapshot_graph_sequence_id] =
                    cassi_service_snapshot_graph_sequence_state;
            } else {
                graph_site_sequence_states.erase(
                    cassi_service_snapshot_graph_sequence_id);
            }
        }
    } catch (...) {
        restored = false;
    }
    if (!restored) {
        cassi_service_poisoned = true;
    }
    cassi_service_active = false;
    cassi_service_mctx.reset();
    cassi_service_ubatch = {};
    cassi_service_mctx_applied = false;
    cassi_service_nodes = 0;
    cassi_service_epoch++;
    cassi_token_snapshot_clear();
    return restored;
}

bool llama_context::cassi_group_snapshot_capture(const llama_batch & batch, uint32_t n_rows) {
    cassi_group_snapshot_clear();
    if (n_rows == 0 || batch.n_tokens != static_cast<int32_t>(n_rows) ||
            batch.token == nullptr || batch.pos == nullptr ||
            cassi_service_row_next_pos.size() < cparams.n_seq_max) {
        return false;
    }
    try {
        cassi_service_group_snapshot.reserve(n_rows);
        for (uint32_t r = 0; r < n_rows; ++r) {
            const llama_seq_id seq_id =
                batch.seq_id && batch.seq_id[r] ? batch.seq_id[r][0] : 0;
            if (seq_id < 0 || static_cast<uint32_t>(seq_id) >= cparams.n_seq_max) {
                cassi_group_snapshot_clear();
                return false;
            }
            cassi_service_row_snapshot snapshot;
            snapshot.seq_id = seq_id;
            snapshot.next_pos = cassi_service_row_next_pos[seq_id];
            const size_t state_size = state_seq_get_size(seq_id, LLAMA_STATE_SEQ_FLAGS_NONE);
            if (state_size == 0) {
                cassi_group_snapshot_clear();
                return false;
            }
            snapshot.state.resize(state_size);
            if (state_seq_get_data(seq_id, snapshot.state.data(), state_size,
                    LLAMA_STATE_SEQ_FLAGS_NONE) != state_size) {
                cassi_group_snapshot_clear();
                return false;
            }
            cassi_service_group_snapshot.push_back(std::move(snapshot));
        }
    } catch (...) {
        cassi_group_snapshot_clear();
        return false;
    }
    return cassi_service_group_snapshot.size() == n_rows;
}

bool llama_context::cassi_group_snapshot_restore(uint32_t n_rows) {
    if (n_rows == 0 || cassi_service_group_snapshot.size() != n_rows) {
        cassi_group_snapshot_clear();
        cassi_service_poisoned = true;
        return false;
    }
    bool restored = true;
    for (const auto & snapshot : cassi_service_group_snapshot) {
        if (snapshot.seq_id < 0 ||
                static_cast<uint32_t>(snapshot.seq_id) >= cparams.n_seq_max ||
                snapshot.state.empty()) {
            restored = false;
            continue;
        }
        try {
            const size_t bytes = state_seq_set_data(
                snapshot.seq_id, snapshot.state.data(), snapshot.state.size(), 0);
            restored = bytes == snapshot.state.size() && restored;
            if (static_cast<size_t>(snapshot.seq_id) >= cassi_service_row_next_pos.size()) {
                restored = false;
            } else {
                cassi_service_row_next_pos[snapshot.seq_id] = snapshot.next_pos;
            }
        } catch (...) {
            restored = false;
        }
    }
    cassi_group_snapshot_clear();
    if (!restored) {
        cassi_service_poisoned = true;
    }
    return restored;
}

void llama_context::cassi_group_snapshot_clear() {
    cassi_service_group_snapshot.clear();
}

int32_t llama_context::cassi_begin_token(llama_token token, llama_pos pos) {
    if (!cparams.cassi_apprentice || cassi_service_active || cassi_service_batch ||
            cassi_service_poisoned || cassi_service_snapshot_valid ||
            !cassi_service_group_snapshot.empty() ||
            pos != cassi_service_next_pos || pos < 0 ||
            static_cast<uint32_t>(pos) >= cparams.n_ctx ||
            token < 0 || token >= model.vocab.n_tokens()) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship token transaction\n", __func__);
        return -1;
    }

    cassi_token_snapshot_clear();
    if (!graph_site_candidate_pending) {
        graph_site_candidate_result = {};
    }
    const auto reject_candidate = [&](const char * reason, bool restore_snapshot) {
        if (restore_snapshot && cassi_service_snapshot_valid) {
            if (!cassi_token_snapshot_restore()) {
                reason = "rollback_restore_failed";
            }
        }
        if (graph_site_candidate_pending) {
            graph_site_candidate_result = {};
            graph_site_candidate_bind_identity(
                graph_site_candidate, graph_site_candidate_result);
            graph_site_candidate_result.attempted = true;
            graph_site_candidate_result.admitted = false;
            graph_site_candidate_result.refusal = reason;
            graph_site_candidate_pending = false;
        }
        cassi_service_mctx.reset();
        cassi_service_ubatch = {};
        cassi_service_active = false;
        cassi_token_snapshot_clear();
        return -1;
    };

    int32_t n_seq_id = 1;
    llama_seq_id seq = 0;
    llama_seq_id * seq_ptr = &seq;
    int8_t logits = 0;
    llama_batch batch = {};
    batch.n_tokens = 1;
    batch.token = &token;
    batch.pos = &pos;
    batch.n_seq_id = &n_seq_id;
    batch.seq_id = &seq_ptr;
    batch.logits = &logits;
    if (!balloc->init(batch, model.vocab, memory.get(), model.hparams.n_embd, 1, false)) {
        LLAMA_LOG_ERROR("%s: failed to initialize apprenticeship batch\n", __func__);
        return reject_candidate("native_batch_unavailable", false);
    }
    balloc->split_reset();
    cassi_service_mctx.reset();
    if (graph_site_candidate_pending && !cassi_token_snapshot_capture(seq)) {
        return reject_candidate("rollback_snapshot_unavailable", false);
    }
    if (memory != nullptr) {
        // False also means that the memory module had no pending update.
        memory_update(false);
        cassi_service_mctx = memory->init_batch(*balloc, std::max<uint32_t>(1, cparams.n_rs_seq + 2), false);
        if (!cassi_service_mctx || llama_memory_status_is_fail(cassi_service_mctx->get_status())) {
            LLAMA_LOG_ERROR("%s: failed to prepare apprenticeship memory transaction\n", __func__);
            return reject_candidate("native_memory_transaction_unavailable", true);
        }
        cassi_service_ubatch = cassi_service_mctx->get_ubatch();
    } else {
        cassi_service_ubatch = balloc->split_simple(1);
    }
    if (cassi_service_ubatch.n_tokens != 1 || cassi_service_ubatch.n_seq_tokens != 1 ||
            cassi_service_ubatch.n_seqs != 1 || cassi_service_ubatch.n_seqs_unq != 1 ||
            cassi_service_ubatch.pos == nullptr || cassi_service_ubatch.pos[0] != pos) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship microbatch\n", __func__);
        return reject_candidate("native_microbatch_invalid", true);
    }
    cassi_service_active = true;
    cassi_service_mctx_applied = false;
    cassi_service_batch = false;
    cassi_service_epoch++;
    cassi_service_nodes = 0;
    return 0;
}

ggml_tensor * llama_context::cassi_service(const llm_cassi_service_config & config) {
    if (!cparams.cassi_apprentice || !cassi_service_active ||
            config.request_epoch != cassi_service_epoch || config.kind == LLAMA_CASSI_TEXT) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship service transition\n", __func__);
        return nullptr;
    }
    if (config.n_rows > 1) {
        // Multi-row homogeneous stage: the row descriptors must identify exactly the
        // rows of the active transaction, and the handoff tensor must carry one
        // column per row ([width, n_rows], column i belonging to row i).
        if (config.n_rows != cassi_service_row_count) {
            LLAMA_LOG_ERROR("%s: service row count %u does not match the active transaction (%u rows)\n",
                    __func__, config.n_rows, cassi_service_row_count);
            return nullptr;
        }
        if (config.batch_pos == nullptr || config.batch_seq_ids == nullptr ||
                (config.kind == LLAMA_CASSI_EMBED && config.batch_tokens == nullptr)) {
            LLAMA_LOG_ERROR("%s: missing apprenticeship row descriptors\n", __func__);
            return nullptr;
        }
        if (config.input != nullptr &&
                (config.input->type != GGML_TYPE_F32 ||
                 config.input->ne[1] != (int64_t) config.n_rows ||
                 (config.stage_width != 0 && config.input->ne[0] != (int64_t) config.stage_width) ||
                 (config.stage_width == 0 && config.input->ne[0] != model.hparams.n_embd))) {
            LLAMA_LOG_ERROR("%s: invalid apprenticeship service input shape (expected [%s%u] F32)\n",
                    __func__,
                    config.stage_width != 0 ? "" : format("n_embd = %u, ", model.hparams.n_embd).c_str(),
                    config.n_rows);
            return nullptr;
        }
        for (uint32_t r = 0; r < config.n_rows; ++r) {
            const bool row_matches = config.batch_pos[r] == cassi_service_ubatch.pos[r] &&
                config.batch_seq_ids[r] == cassi_service_ubatch.seq_id[r][0] &&
                (config.batch_tokens == nullptr ||
                    (config.kind != LLAMA_CASSI_EMBED ||
                        config.batch_tokens[r] == cassi_service_ubatch.token[r]));
            if (!row_matches) {
                LLAMA_LOG_ERROR("%s: service row %u does not match the active transaction\n",
                        __func__, r);
                return nullptr;
            }
        }
    }
    if (config.kind == LLAMA_CASSI_ATTENTION) {
        if (config.layer < 0 || static_cast<uint32_t>(config.layer) >= cparams.cassi_attention_owned.size() ||
                cparams.cassi_attention_owned[config.layer] != 0 || cassi_service_mctx == nullptr) {
            LLAMA_LOG_ERROR("%s: invalid native attention service\n", __func__);
            return nullptr;
        }
    }
    cassi_service_config = config;
    ggml_status status = GGML_STATUS_FAILED;
    llama_memory_context_i * mctx =
        config.kind == LLAMA_CASSI_ATTENTION ? cassi_service_mctx.get() : nullptr;
    llm_graph_result * result =
        process_ubatch(cassi_service_ubatch, LLM_GRAPH_TYPE_CASSI_SERVICE, mctx, status);
    LLAMA_LOG_DEBUG("%s: group eval done status=%d out=%p\n", __func__, (int)status, result ? (void*)result->get_cassi_service() : nullptr);
    if (result == nullptr || status != GGML_STATUS_SUCCESS || result->get_cassi_service() == nullptr) {
        LLAMA_LOG_ERROR("%s: apprenticeship service graph failed\n", __func__);
        return nullptr;
    }
    ggml_backend_sched_synchronize(sched.get());
    cassi_service_nodes = ggml_graph_n_nodes(result->get_gf());
    return result->get_cassi_service();
}

int32_t llama_context::cassi_end_token() {
    if (!cparams.cassi_apprentice || !cassi_service_active || cassi_service_batch) {
        LLAMA_LOG_ERROR("%s: no apprenticeship token transaction\n", __func__);
        return -1;
    }
    if (cassi_service_mctx_applied && cassi_service_mctx != nullptr && cassi_service_mctx->next()) {
        LLAMA_LOG_ERROR("%s: apprenticeship transaction produced more than one microbatch\n", __func__);
        return -1;
    }
    const bool candidate_admitted =
        graph_site_candidate_result.attempted && graph_site_candidate_result.admitted;
    if (candidate_admitted && !cassi_service_snapshot_valid) {
        cassi_service_poisoned = true;
        graph_site_candidate_result.admitted = false;
        graph_site_candidate_result.refusal = "rollback_snapshot_unavailable";
        return -1;
    }
    cassi_service_mctx.reset();
    cassi_service_ubatch = {};
    cassi_service_active = false;
    cassi_service_mctx_applied = false;
    cassi_service_next_pos++;
    if (candidate_admitted) {
        cassi_service_snapshot_committed = true;
    } else {
        cassi_token_snapshot_clear();
    }
    return 0;
}

llama_cassi_cancel_status llama_context::cassi_cancel_token() {
    if (cassi_service_batch) {
        return LLAMA_CASSI_CANCEL_NO_ACTIVE_TRANSACTION;
    }
    if (!cassi_service_active &&
            !(cassi_service_snapshot_valid && cassi_service_snapshot_committed)) {
        return LLAMA_CASSI_CANCEL_NO_ACTIVE_TRANSACTION;
    }
    if (!cassi_service_snapshot_valid) {
        cassi_service_poisoned = true;
        cassi_service_active = false;
        cassi_service_mctx.reset();
        cassi_service_ubatch = {};
        cassi_service_mctx_applied = false;
        cassi_service_epoch++;
        cassi_token_snapshot_clear();
        return LLAMA_CASSI_CANCEL_ROLLBACK_UNAVAILABLE;
    }
    if (!cassi_token_snapshot_restore()) {
        return LLAMA_CASSI_CANCEL_RESTORE_FAILED;
    }
    if (graph_site_candidate_result.attempted &&
            graph_site_candidate_result.admitted) {
        graph_site_candidate_result.admitted = false;
        graph_site_candidate_result.native_successor_sha256.clear();
        graph_site_candidate_result.refusal = "candidate_cancelled";
    }
    return LLAMA_CASSI_CANCEL_OK;
}

int32_t llama_context::cassi_begin_tokens(const llama_batch & batch_req, uint32_t n_rows) {
    if (!cparams.cassi_apprentice || cassi_service_active || cassi_service_batch ||
            cassi_service_poisoned || cassi_service_snapshot_valid ||
            !cassi_service_group_snapshot.empty() || graph_site_candidate_pending) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship token transaction\n", __func__);
        return -1;
    }
    if (n_rows == 0 || batch_req.n_tokens != static_cast<int32_t>(n_rows) ||
            batch_req.token == nullptr || batch_req.pos == nullptr) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship token rows (n_rows = %u, n_tokens = %d)\n",
                __func__, n_rows, batch_req.n_tokens);
        return -1;
    }
    cassi_token_snapshot_clear();
    graph_site_candidate_result = {};
    // Bounded stage: one homogeneous ubatch must carry every row, and each row
    // maps to one KV/SSM sequence slot.
    const uint32_t row_cap = std::min(std::min(cparams.n_seq_max, cparams.n_batch), cparams.n_ubatch);
    if (n_rows > row_cap) {
        LLAMA_LOG_ERROR("%s: n_rows = %u exceeds the bounded stage capacity %u (n_seq_max = %u, n_batch = %u, n_ubatch = %u)\n",
                __func__, n_rows, row_cap, cparams.n_seq_max, cparams.n_batch, cparams.n_ubatch);
        return -1;
    }

    std::unordered_set<llama_seq_id> row_seqs;
    for (uint32_t r = 0; r < n_rows; ++r) {
        const llama_token   token = batch_req.token[r];
        const llama_pos     pos   = batch_req.pos[r];
        const int32_t       n_seq = batch_req.n_seq_id ? batch_req.n_seq_id[r] : 1;
        const llama_seq_id  seq   = batch_req.seq_id && batch_req.seq_id[r] ? batch_req.seq_id[r][0] : 0;
        if (token < 0 || token >= model.vocab.n_tokens()) {
            LLAMA_LOG_ERROR("%s: invalid token[%u] = %d\n", __func__, r, token);
            return -1;
        }
        if (n_seq != 1) {
            LLAMA_LOG_ERROR("%s: row %u maps to %d sequences - each row must identify exactly one sequence\n",
                    __func__, r, n_seq);
            return -1;
        }
        if (seq < 0 || static_cast<uint32_t>(seq) >= cparams.n_seq_max) {
            LLAMA_LOG_ERROR("%s: invalid seq_id[%u] = %d (n_seq_max = %u)\n",
                    __func__, r, seq, cparams.n_seq_max);
            return -1;
        }
        if (pos < 0 || static_cast<uint32_t>(pos) >= cparams.n_ctx ||
                (!cparams.kv_unified && static_cast<uint32_t>(pos) >= cparams.n_ctx_seq)) {
            LLAMA_LOG_ERROR("%s: invalid pos[%u] = %d (n_ctx = %u, n_ctx_seq = %u)\n",
                    __func__, r, pos, cparams.n_ctx, cparams.n_ctx_seq);
            return -1;
        }
        if (!row_seqs.insert(seq).second) {
            LLAMA_LOG_ERROR("%s: duplicate seq_id %d at row %u - a homogeneous stage must not repeat a sequence\n",
                    __func__, seq, r);
            return -1;
        }
    }
    // Per-row protocol fence: every row lands on its sequence's next service position.
    if (cassi_service_row_next_pos.size() < cparams.n_seq_max) {
        cassi_service_row_next_pos.resize(cparams.n_seq_max, 0);
    }
    for (uint32_t r = 0; r < n_rows; ++r) {
        const llama_seq_id seq = batch_req.seq_id && batch_req.seq_id[r] ? batch_req.seq_id[r][0] : 0;
        if (batch_req.pos[r] != cassi_service_row_next_pos[seq]) {
            LLAMA_LOG_ERROR("%s: pos[%u] = %d is not the next service position for seq_id %d (expected %d)\n",
                    __func__, r, batch_req.pos[r], seq, cassi_service_row_next_pos[seq]);
            return -1;
        }
    }

    if (!cassi_group_snapshot_capture(batch_req, n_rows)) {
        LLAMA_LOG_ERROR("%s: failed to snapshot apprenticeship group state\n", __func__);
        return -1;
    }
    const auto abort_group = [&](const std::string & reason) {
        cassi_service_mctx.reset();
        cassi_service_ubatch = {};
        cassi_service_active = false;
        cassi_service_batch = false;
        cassi_service_row_count = 0;
        cassi_service_mctx_applied = false;
        cassi_service_epoch++;
        const bool restored = cassi_group_snapshot_restore(n_rows);
        LLAMA_LOG_ERROR("%s: %s%s\n", __func__, reason.c_str(),
                restored ? "" : " (group state restore failed; context poisoned)");
        return -1;
    };

    llama_batch batch = batch_req;
    if (!balloc->init(batch, model.vocab, memory.get(), model.hparams.n_embd,
                cparams.kv_unified ? LLAMA_MAX_SEQ : cparams.n_seq_max, false)) {
        return abort_group("failed to initialize apprenticeship batch");
    }
    balloc->split_reset();
    cassi_service_mctx.reset();
    if (memory != nullptr) {
        // False also means that the memory module had no pending update.
        memory_update(false);
        cassi_service_mctx = memory->init_batch(*balloc, std::max<uint32_t>(n_rows, cparams.n_rs_seq + 2), false);
        if (!cassi_service_mctx || llama_memory_status_is_fail(cassi_service_mctx->get_status())) {
            return abort_group("failed to prepare apprenticeship memory transaction");
        }
        cassi_service_ubatch = cassi_service_mctx->get_ubatch();
    } else {
        cassi_service_ubatch = balloc->split_simple(n_rows);
    }
    // The whole homogeneous stage must execute as one ubatch in one graph run.
    if (cassi_service_ubatch.n_tokens != n_rows || cassi_service_ubatch.n_seq_tokens != 1 ||
            cassi_service_ubatch.n_seqs != n_rows || cassi_service_ubatch.n_seqs_unq != n_rows ||
            cassi_service_ubatch.token == nullptr || cassi_service_ubatch.pos == nullptr ||
            cassi_service_ubatch.seq_id == nullptr || cassi_service_ubatch.n_seq_id == nullptr) {
        return abort_group("invalid apprenticeship microbatch - one homogeneous stage requires a single ubatch"
                " (use kv_unified or strictly consecutive increasing seq ids for the group)");
    }
    for (uint32_t r = 0; r < n_rows; ++r) {
        const llama_seq_id seq = batch_req.seq_id && batch_req.seq_id[r] ? batch_req.seq_id[r][0] : 0;
        if (cassi_service_ubatch.n_seq_id[r] != 1 || cassi_service_ubatch.seq_id[r] == nullptr ||
                cassi_service_ubatch.seq_id[r][0] != seq ||
                cassi_service_ubatch.pos[r] != batch_req.pos[r] ||
                cassi_service_ubatch.token[r] != batch_req.token[r]) {
            return abort_group(format(
                "apprenticeship microbatch row %u does not match its request row", r));
        }
    }
    cassi_service_active = true;
    cassi_service_mctx_applied = false;
    cassi_service_batch = true;
    cassi_service_row_count = n_rows;
    cassi_service_epoch++;
    cassi_service_nodes = 0;
    return 0;
}

int32_t llama_context::cassi_end_tokens() {
    if (!cparams.cassi_apprentice || !cassi_service_active || !cassi_service_batch) {
        LLAMA_LOG_ERROR("%s: no apprenticeship token transaction\n", __func__);
        return -1;
    }
    if (cassi_service_mctx_applied && cassi_service_mctx != nullptr && cassi_service_mctx->next()) {
        LLAMA_LOG_ERROR("%s: apprenticeship transaction produced more than one microbatch\n", __func__);
        return -1;
    }
    // Commit: advance each row's sequence to the next service position.
    if (cassi_service_ubatch.pos != nullptr && cassi_service_ubatch.seq_id != nullptr) {
        for (uint32_t r = 0; r < cassi_service_row_count; ++r) {
            const llama_seq_id seq = cassi_service_ubatch.seq_id[r][0];
            if (seq >= 0 && static_cast<uint32_t>(seq) < cassi_service_row_next_pos.size()) {
                cassi_service_row_next_pos[seq] = cassi_service_ubatch.pos[r] + 1;
            }
        }
    }
    cassi_service_mctx.reset();
    cassi_service_ubatch = {};
    cassi_service_active = false;
    cassi_service_batch = false;
    cassi_service_row_count = 0;
    cassi_service_mctx_applied = false;
    cassi_group_snapshot_clear();
    return 0;
}

int32_t llama_context::cassi_cancel_tokens() {
    if (!cparams.cassi_apprentice || !cassi_service_active || !cassi_service_batch) {
        LLAMA_LOG_ERROR("%s: no apprenticeship token transaction\n", __func__);
        return -1;
    }
    const uint32_t row_count = cassi_service_row_count;
    cassi_service_mctx.reset();
    cassi_service_ubatch = {};
    cassi_service_active = false;
    cassi_service_batch = false;
    cassi_service_row_count = 0;
    cassi_service_mctx_applied = false;
    cassi_service_epoch++;
    if (!cassi_group_snapshot_restore(row_count)) {
        LLAMA_LOG_ERROR("%s: apprenticeship group state restore failed; context poisoned\n", __func__);
        return -1;
    }
    return 0;

}
uint32_t llama_context::cassi_service_rows() const {
    return cassi_service_active ? cassi_service_row_count : 0;
}

llama_pos llama_context::cassi_service_next_pos_seq(llama_seq_id seq_id) const {
    if (seq_id < 0 || static_cast<uint32_t>(seq_id) >= cparams.n_seq_max) {
        return -1;
    }
    return seq_id < static_cast<llama_seq_id>(cassi_service_row_next_pos.size()) ?
        cassi_service_row_next_pos[seq_id] : 0;
}

int32_t llama_context::cassi_group_row_reset(llama_seq_id seq_id) {
    if (!cparams.cassi_apprentice || cassi_service_active || cassi_service_batch) {
        LLAMA_LOG_ERROR("%s: no apprenticeship group at a round boundary\n", __func__);
        return -1;
    }
    if (seq_id < 0 || static_cast<uint32_t>(seq_id) >= cparams.n_seq_max) {
        LLAMA_LOG_ERROR("%s: invalid seq_id %d\n", __func__, seq_id);
        return -1;
    }
    if (!memory) {
        LLAMA_LOG_ERROR("%s: no memory module\n", __func__);
        return -1;
    }
    memory->seq_rm(seq_id, -1, -1);
    if (cassi_service_row_next_pos.size() < cparams.n_seq_max) {
        cassi_service_row_next_pos.resize(cparams.n_seq_max, 0);
    }
    cassi_service_row_next_pos[seq_id] = 0;
    return 0;
}

int32_t llama_context::cassi_service_rewind(llama_pos pos) {
    if (!cparams.cassi_apprentice || cassi_service_active || cassi_service_batch ||
            pos < 0 || pos > cassi_service_next_pos) {
        LLAMA_LOG_ERROR("%s: invalid apprenticeship rewind request\n", __func__);
        return -1;
    }
    if (pos < cassi_service_next_pos) {
        if (!memory) {
            LLAMA_LOG_ERROR("%s: no memory module\n", __func__);
            return -1;
        }
        memory->seq_rm(0, pos, -1);
    }
    cassi_service_next_pos = pos;
    cassi_service_poisoned = false;
    cassi_token_snapshot_clear();
    return 0;
}

int32_t llama_context::cassi_service_graph_nodes() const {
    return cassi_service_nodes;
}

int32_t llama_context::cassi_last_graph_nodes() const {
    return gf_res_prev == nullptr ? 0 : ggml_graph_n_nodes(gf_res_prev->get_gf());
}

uint64_t llama_context::cassi_last_graph_weight_bytes() const {
    if (gf_res_prev == nullptr) {
        return 0;
    }
    std::unordered_set<const ggml_tensor *> model_tensors;
    model_tensors.reserve(model.tensors_by_name.size());
    for (const auto & item : model.tensors_by_name) {
        model_tensors.insert(item.second);
    }
    std::unordered_set<const ggml_tensor *> visited;
    std::unordered_set<const ggml_tensor *> used_weights;
    std::vector<const ggml_tensor *> stack;
    ggml_cgraph * graph = gf_res_prev->get_gf();
    stack.reserve(static_cast<size_t>(ggml_graph_n_nodes(graph)));
    for (int node = 0; node < ggml_graph_n_nodes(graph); ++node) {
        stack.push_back(ggml_graph_node(graph, node));
    }
    while (!stack.empty()) {
        const ggml_tensor * tensor = stack.back();
        stack.pop_back();
        if (tensor == nullptr || !visited.insert(tensor).second) {
            continue;
        }
        if (model_tensors.count(tensor) != 0) {
            used_weights.insert(tensor);
            continue;
        }
        if (tensor->view_src != nullptr) {
            stack.push_back(tensor->view_src);
        }
        for (const ggml_tensor * source : tensor->src) {
            if (source != nullptr) {
                stack.push_back(source);
            }
        }
    }
    uint64_t total = 0;
    for (const ggml_tensor * weight : used_weights) {
        const uint64_t bytes = weight == model.tok_embd && weight != model.output
            ? static_cast<uint64_t>(ggml_row_size(weight->type, weight->ne[0]))
            : static_cast<uint64_t>(ggml_nbytes(weight));
        total = bytes > UINT64_MAX - total ? UINT64_MAX : total + bytes;
    }
    return total;
}

int32_t llama_context::cassi_graph_nodes_between(
        const ggml_tensor * output,
        const ggml_tensor * boundary) const {
    if (output == nullptr) {
        return 0;
    }
    std::unordered_set<const ggml_tensor *> model_tensors;
    model_tensors.reserve(model.tensors_by_name.size());
    for (const auto & item : model.tensors_by_name) {
        model_tensors.insert(item.second);
    }
    std::unordered_set<const ggml_tensor *> visited;
    std::vector<const ggml_tensor *> stack = { output };
    int32_t nodes = 0;
    while (!stack.empty()) {
        const ggml_tensor * tensor = stack.back();
        stack.pop_back();
        if (tensor == nullptr || tensor == boundary || !visited.insert(tensor).second) {
            continue;
        }
        if (model_tensors.count(tensor) != 0) {
            continue;
        }
        if (tensor->op != GGML_OP_NONE) {
            nodes++;
        }
        if (tensor->view_src != nullptr) {
            stack.push_back(tensor->view_src);
        }
        for (const ggml_tensor * source : tensor->src) {
            if (source != nullptr) {
                stack.push_back(source);
            }
        }
    }
    return nodes;
}

uint64_t llama_context::cassi_graph_weight_bytes_between(
        const ggml_tensor * output,
        const ggml_tensor * boundary,
        bool embedding_row) const {
    if (output == nullptr) {
        return 0;
    }
    std::unordered_set<const ggml_tensor *> model_tensors;
    model_tensors.reserve(model.tensors_by_name.size());
    for (const auto & item : model.tensors_by_name) {
        model_tensors.insert(item.second);
    }
    std::unordered_set<const ggml_tensor *> visited;
    std::unordered_set<const ggml_tensor *> used_weights;
    std::vector<const ggml_tensor *> stack = { output };
    while (!stack.empty()) {
        const ggml_tensor * tensor = stack.back();
        stack.pop_back();
        if (tensor == nullptr || tensor == boundary || !visited.insert(tensor).second) {
            continue;
        }
        if (model_tensors.count(tensor) != 0) {
            used_weights.insert(tensor);
            continue;
        }
        if (tensor->view_src != nullptr) {
            stack.push_back(tensor->view_src);
        }
        for (const ggml_tensor * source : tensor->src) {
            if (source != nullptr) {
                stack.push_back(source);
            }
        }
    }
    uint64_t total = 0;
    for (const ggml_tensor * weight : used_weights) {
        const uint64_t bytes = embedding_row && weight == model.tok_embd
            ? static_cast<uint64_t>(ggml_row_size(weight->type, weight->ne[0]))
            : static_cast<uint64_t>(ggml_nbytes(weight));
        total = bytes > UINT64_MAX - total ? UINT64_MAX : total + bytes;
    }
    return total;
}

void llama_context::enable_cassi_capture() {
    if (cparams.cassi_apprentice) {
        throw std::runtime_error("apprentice_capture_requires_teacher");
    }
    if (cparams.cassi_capture) {
        return;
    }
    cparams.cassi_capture = true;
    graph_reuse_disable = true;
    sched_need_reserve = true;
    sched_reserve();
}

bool llama_context::cassi_capture_get(llama_cassi_capture & capture) {
    if (!cparams.cassi_capture || gf_res_prev == nullptr) {
        return false;
    }
    synchronize();
    llm_graph_result * result = gf_res_prev.get();
    const uint32_t layers = model.hparams.n_layer();
    const auto valid_vector = [&](ggml_tensor * tensor) {
        return tensor != nullptr && tensor->type == GGML_TYPE_F32 &&
            ggml_nelements(tensor) == model.hparams.n_embd &&
            (tensor->buffer != nullptr || (tensor->view_src != nullptr && tensor->view_src->buffer != nullptr));
    };
    capture.embedding = result->get_cassi_capture_embed();
    capture.head_input = result->get_cassi_capture_head_input();
    capture.head_output = result->get_logits();
    capture.attention_input.resize(layers);
    capture.attention_delta.resize(layers);
    capture.ffn_input.resize(layers);
    capture.ffn_delta.resize(layers);
    if (!valid_vector(capture.embedding) || !valid_vector(capture.head_input) ||
            capture.head_output == nullptr || capture.head_output->type != GGML_TYPE_F32) {
        return false;
    }
    for (uint32_t layer = 0; layer < layers; ++layer) {
        capture.attention_input[layer] = result->get_cassi_capture_attention_input(layer);
        capture.attention_delta[layer] = result->get_cassi_capture_attention_delta(layer);
        capture.ffn_input[layer] = result->get_cassi_capture_ffn_input(layer);
        capture.ffn_delta[layer] = result->get_cassi_capture_ffn_delta(layer);
        if (!valid_vector(capture.attention_input[layer]) ||
                !valid_vector(capture.attention_delta[layer]) ||
                !valid_vector(capture.ffn_input[layer]) ||
                !valid_vector(capture.ffn_delta[layer])) {
            return false;
        }
    }
    return true;
}

ggml_tensor * llama_context::cassi_capture_tensor(int32_t kind, uint32_t layer) const {
    if (!cparams.cassi_capture || gf_res_prev == nullptr) {
        return nullptr;
    }
    llm_graph_result * result = gf_res_prev.get();
    switch (kind) {
        case LLAMA_CASSI_CAPTURE_HEAD_INPUT:
            return result->get_cassi_capture_head_input();
        case LLAMA_CASSI_CAPTURE_HEAD_OUTPUT:
            return result->get_logits();
        case LLAMA_CASSI_CAPTURE_EMBEDDING:
            return result->get_cassi_capture_embed();
        default:
            break;
    }
    if (layer >= static_cast<uint32_t>(model.hparams.n_layer())) {
        return nullptr;
    }
    switch (kind) {
        case LLAMA_CASSI_CAPTURE_LAYER_INPUT:
            return result->get_cassi_capture_attention_input(layer);
        case LLAMA_CASSI_CAPTURE_ATTENTION_OUTPUT:
            return result->get_cassi_capture_attention_delta(layer);
        case LLAMA_CASSI_CAPTURE_ATTENTION_PROBS:
            return result->get_cassi_capture_attention_probs(layer);
        case LLAMA_CASSI_CAPTURE_FFN_INPUT:
            return result->get_cassi_capture_ffn_input(layer);
        case LLAMA_CASSI_CAPTURE_FFN_OUTPUT:
            return result->get_cassi_capture_ffn_delta(layer);
        default:
            return nullptr;
    }
}

int32_t llama_context::cassi_capture_shape(int32_t kind, uint32_t layer, int64_t * shape) const {
    ggml_tensor * tensor = cassi_capture_tensor(kind, layer);
    if (tensor == nullptr) {
        return 0;
    }
    const int32_t rank = ggml_n_dims(tensor);
    if (rank < 1 || rank > 4) {
        return 0;
    }
    for (int32_t index = 0; index < 4; ++index) {
        shape[index] = index < rank ? tensor->ne[index] : 1;
    }
    return rank;
}


bool llama_context::cassi_capture_copy(int32_t kind, uint32_t layer, float * data, size_t count) {
    ggml_tensor * tensor = cassi_capture_tensor(kind, layer);
    if (tensor == nullptr || tensor->type != GGML_TYPE_F32 || tensor->buffer == nullptr) {
        return false;
    }
    if (static_cast<size_t>(ggml_nelements(tensor)) != count) {
        return false;
    }
    if (!ggml_is_contiguous(tensor)) {
        // a strided view cannot be read back as one flat block
        return false;
    }
    synchronize();
    ggml_backend_tensor_get(tensor, data, 0, count * sizeof(float));
    return true;
}

llm_graph_result * llama_context::process_ubatch(const llama_ubatch & ubatch, llm_graph_type gtype, llama_memory_context_i * mctx, ggml_status & ret) {
    const bool apply_memory = mctx != nullptr &&
        (gtype != LLM_GRAPH_TYPE_CASSI_SERVICE || !cassi_service_mctx_applied);
    if (apply_memory && !mctx->apply()) {
        LLAMA_LOG_ERROR("%s: failed to apply memory context\n", __func__);
        ret = GGML_STATUS_FAILED;
        return nullptr;
    }
    if (apply_memory && gtype == LLM_GRAPH_TYPE_CASSI_SERVICE) {
        cassi_service_mctx_applied = true;
    }

    auto * res = gf_res_prev.get();
    auto * gf  = res->get_gf();
    LLAMA_LOG_DEBUG("%s: enter gtype=%d n_tokens=%d\n", __func__, (int)gtype, ubatch.n_tokens);

    // the new graph parameters
    // in order to correctly reuse a graph, it's full topology has to be uniquely determined by these parameters
    const auto gparams = graph_params(res, ubatch, mctx, gtype);

    if (!graph_reuse_disable && res->can_reuse(gparams)) {
        //LLAMA_LOG_DEBUG("%s: reusing previous graph\n", __func__);

        // with pipeline parallelism, the previous graph_compute_async may still be running
        // on the GPU. we must synchronize before set_inputs to avoid overwriting input tensors
        // that the previous compute is still reading.
        if (cparams.pipeline_parallel) {
            ggml_backend_sched_synchronize(sched.get());
        }

        n_reused++;
    } else {
        res->reset();

        ggml_backend_sched_reset(sched.get());
        ggml_backend_sched_set_eval_callback(sched.get(), cparams.cb_eval, cparams.cb_eval_user_data);

        //const auto t_start_us = ggml_time_us();

        gf = model.build_graph(gparams);

        //LLAMA_LOG_INFO("graph build time: %.3f ms\n", (ggml_time_us() - t_start_us)/1000.0);

        if (!gf) {
            LLAMA_LOG_ERROR("%s: failed to initialize graph\n", __func__);
            ret = GGML_STATUS_FAILED;
            return nullptr;
        }

        if (!ggml_backend_sched_alloc_graph(sched.get(), gf)) {
            LLAMA_LOG_ERROR("%s: failed to allocate graph\n", __func__);
            ret = GGML_STATUS_ALLOC_FAILED;
            return nullptr;
        }
    }
    if (cassi_modal_pending.valid || cassi_field_pending.valid || cassi_qi_pending.valid) {
        synchronize();
    }

    // set the input data for the input tensors
    {
        //const auto t_start_us = ggml_time_us();

        // FIXME this call causes a crash if any model inputs were not used in the graph and were therefore not allocated
        res->set_inputs(&ubatch);
        //LLAMA_LOG_INFO("graph set inputs time: %.3f ms\n", (ggml_time_us() - t_start_us)/1000.0);
    }

    const auto status = graph_compute(res->get_gf(), ubatch.n_tokens > 1);
    if (status != GGML_STATUS_SUCCESS) {
        LLAMA_LOG_ERROR("%s: failed to compute graph, compute status: %d\n", __func__, status);
        if (graph_site_candidate_pending) {
            graph_site_candidate_bind_identity(
                graph_site_candidate, graph_site_candidate_result);
            if (!graph_site_candidate_result.attempted) {
                graph_site_candidate_result.attempted = true;
                graph_site_candidate_result.admitted = false;
                graph_site_candidate_result.refusal = "graph_compute_failed";
            }
            graph_site_candidate_pending = false;
        }
        ret = status;
        return nullptr;
    }
    queue_cassi_modal_state(res, ubatch);
    queue_cassi_field_state(res, ubatch);
    queue_cassi_qi_field_state(res, ubatch);

    if (graph_site_candidate_pending) {
        const auto & receipt = res->get_graph_site_candidate_result();
        if (receipt.attempted) {
            graph_site_candidate_result = receipt;
            graph_site_candidate_bind_identity(
                graph_site_candidate, graph_site_candidate_result);
            if (graph_site_candidate_result.admitted) {
                graph_site_candidate_measure_result();
            }
            if (graph_site_candidate_result.admitted) {
                auto & sequence = graph_site_sequence_states[graph_site_candidate.sequence_id];
                const std::string method_identity = std::to_string(graph_site_candidate.layer) + ":" +
                    std::to_string((uint32_t) graph_site_candidate.kind) + ":" +
                    graph_site_candidate.method_key;
                sequence.source_sha256 = graph_site_candidate.source_sha256;
                sequence.owner_generation = graph_site_candidate.owner_generation;
                sequence.method_generations[method_identity] = graph_site_candidate.method_generation;
            }
        } else if (!graph_site_candidate_result.attempted) {
            graph_site_candidate_bind_identity(
                graph_site_candidate, graph_site_candidate_result);
            graph_site_candidate_result.attempted = true;
            graph_site_candidate_result.admitted = false;
            graph_site_candidate_result.refusal = "candidate_not_admitted";
        }
        graph_site_candidate_pending = false;
    }
    ret = GGML_STATUS_SUCCESS;

    return res;
}

int llama_context::encode(const llama_batch & batch_inp) {
    if (cparams.cassi_apprentice) {
        LLAMA_LOG_ERROR("%s: apprentice_use_session_api\n", __func__);
        return -1;
    }
    // MTP hook batches carry both token (next-token id) and embd (h_nextn row),
    // so accept either present rather than requiring exactly one.
    GGML_ASSERT(batch_inp.token || batch_inp.embd);

    if (batch_inp.n_tokens == 0) {
        LLAMA_LOG_ERROR("%s: n_tokens == 0\n", __func__);
        return -1;
    }

    const auto & hparams = model.hparams;

    // eagle3/DFlash: features as encoder input, and non-draft paths fall back to model's input dim
    const int64_t n_embd = hparams.n_embd_inp_enc();
    const int64_t n_vocab = model.vocab.n_tokens();

    // note: during encode, we always pass the full sequence starting from pos = 0
    if (!balloc->init(batch_inp, model.vocab, nullptr, n_embd, cparams.kv_unified ? LLAMA_MAX_SEQ : cparams.n_seq_max, true)) {
        LLAMA_LOG_ERROR("%s: failed to initialize batch\n", __func__);
        return -1;
    }

    const uint32_t n_tokens = balloc->get_n_tokens();

    // [TAG_NO_CACHE_PAD]
    // TODO: add new split mode where we pad the input sequences so that ubatch.equal_seqs == true
    const llama_ubatch ubatch = balloc->split_simple(n_tokens);

    // micro-batching is not possible for non-causal encoding, so we process the batch in a single shot
    GGML_ASSERT(cparams.n_ubatch >= n_tokens && "encoder requires n_ubatch >= n_tokens");

    // TODO: this clear of the buffer can easily be forgotten - need something better
    // sync first so any in-flight async copies into embd_seq complete before it is freed
    if (!embd_seq.empty()) {
        synchronize();
    }
    embd_seq.clear();

    if (t_compute_start_us == 0) {
        t_compute_start_us = ggml_time_us();
    }

    sched_reserve();

    n_queued_tokens += n_tokens;

    // reserve output buffer
    if (output_reserve(n_tokens) < n_tokens) {
        LLAMA_LOG_ERROR("%s: could not reserve space for batch with %u outputs\n", __func__, n_tokens);
        return -2;
    };

    for (uint32_t i = 0; i < n_tokens; ++i) {
        output_ids[i] = i;
    }

    n_outputs = n_tokens;

    const auto causal_attn_org = cparams.causal_attn;

    // always use non-causal attention for encoder graphs
    // TODO: this is a tmp solution until we have a proper way to support enc-dec models
    //       ref: https://github.com/ggml-org/llama.cpp/pull/12181#issuecomment-2730451223
    cparams.causal_attn = false;

    ggml_status status;
    const auto * res = process_ubatch(ubatch, LLM_GRAPH_TYPE_ENCODER, nullptr, status);

    cparams.causal_attn = causal_attn_org;

    if (!res) {
        switch (status) {
            case GGML_STATUS_ABORTED:      return  2;
            case GGML_STATUS_ALLOC_FAILED: return -2;
            case GGML_STATUS_FAILED:       return -3;
            case GGML_STATUS_SUCCESS:      GGML_ABORT("should not happen");
        }
    }

    auto * t_logits  = res->get_logits();
    auto * t_embd    = res->get_embd_pooled() ? res->get_embd_pooled() : res->get_embd();
    auto * t_h_nextn = cparams.embeddings_nextn ? res->get_h_nextn() : nullptr;

    // extract logits
    if (logits.data && t_logits) {
        ggml_backend_t backend_res = ggml_backend_sched_get_tensor_backend(sched.get(), t_logits);
        GGML_ASSERT(backend_res != nullptr);
        GGML_ASSERT(logits.data != nullptr);

        ggml_backend_tensor_get_async(backend_res, t_logits, logits.data, 0, n_tokens*n_vocab*sizeof(float));
    }

    // extract embeddings
    if (embd.data && t_embd) {
        ggml_backend_t backend_embd = ggml_backend_sched_get_tensor_backend(sched.get(), t_embd);
        GGML_ASSERT(backend_embd != nullptr);

        switch (cparams.pooling_type) {
            case LLAMA_POOLING_TYPE_NONE:
                {
                    // extract token embeddings
                    GGML_ASSERT(embd.data != nullptr);
                    const uint32_t n_embd_out = hparams.n_embd_out();

                    GGML_ASSERT(n_tokens*n_embd_out <= (int64_t) embd.size);
                    ggml_backend_tensor_get_async(backend_embd, t_embd, embd.data, 0, n_tokens*n_embd_out*sizeof(float));
                } break;
            case LLAMA_POOLING_TYPE_MEAN:
            case LLAMA_POOLING_TYPE_CLS:
            case LLAMA_POOLING_TYPE_LAST:
                {
                    // extract sequence embeddings
                    auto & embd_seq_out = embd_seq;

                    for (uint32_t s = 0; s < ubatch.n_seqs_unq; ++s) {
                        const llama_seq_id seq_id  = ubatch.seq_id_unq[s];
                        const int32_t      seq_idx = ubatch.seq_idx[seq_id];

                        // use n_embd_out (not n_embd_inp) - the pooled embedding has the model's
                        // output dimension, which differs from input dimension for deepstack models (e.g. qwen3vl)
                        const uint32_t n_embd_out = hparams.n_embd_out();
                        embd_seq_out[seq_id].resize(n_embd_out);
                        ggml_backend_tensor_get_async(backend_embd, t_embd, embd_seq_out[seq_id].data(), (n_embd_out*seq_idx)*sizeof(float), n_embd_out*sizeof(float));
                    }
                } break;
            case LLAMA_POOLING_TYPE_RANK:
                {
                    // extract the rerank score - n_cls_out floats per sequence
                    auto & embd_seq_out = embd_seq;

                    const uint32_t n_cls_out = hparams.n_cls_out;

                    for (uint32_t s = 0; s < ubatch.n_seqs_unq; ++s) {
                        const llama_seq_id seq_id  = ubatch.seq_id_unq[s];
                        const int32_t      seq_idx = ubatch.seq_idx[seq_id];

                        embd_seq_out[seq_id].resize(n_cls_out);
                        ggml_backend_tensor_get_async(backend_embd, t_embd, embd_seq_out[seq_id].data(), (n_cls_out*seq_idx)*sizeof(float), n_cls_out*sizeof(float));
                    }
                } break;
            case LLAMA_POOLING_TYPE_UNSPECIFIED:
                {
                    GGML_ABORT("unknown pooling type");
                }
        }
    }

    // extract nextn embeddings (hidden state before the final output norm)
    if (embd_nextn.data && t_h_nextn && cparams.pooling_type == LLAMA_POOLING_TYPE_NONE) {
        ggml_backend_t backend_h = ggml_backend_sched_get_tensor_backend(sched.get(), t_h_nextn);
        GGML_ASSERT(backend_h != nullptr);

        const uint32_t n_embd = hparams.n_embd_out();
        GGML_ASSERT(n_tokens*n_embd <= (int64_t) embd_nextn.size);
        ggml_backend_tensor_get_async(backend_h, t_h_nextn, embd_nextn.data, 0, n_tokens*n_embd*sizeof(float));
    }

    // TODO: hacky solution
    if (model.arch == LLM_ARCH_T5 && t_embd) {
        //cross.t_embd = t_embd;

        synchronize();

        cross.n_embd = t_embd->ne[0];
        cross.n_enc  = t_embd->ne[1];
        cross.v_embd.resize(cross.n_embd*cross.n_enc);
        memcpy(cross.v_embd.data(), embd.data, ggml_nbytes(t_embd));

        const auto & batch = balloc->get_batch();

        // remember the sequence ids used during the encoding - needed for cross attention later
        cross.seq_ids_enc.resize(n_tokens);
        for (uint32_t i = 0; i < n_tokens; i++) {
            cross.seq_ids_enc[i].clear();

            for (int s = 0; s < batch.n_seq_id[i]; s++) {
                const llama_seq_id seq_id = batch.seq_id[i][s];

                cross.seq_ids_enc[i].insert(seq_id);
            }
        }
    }

    return 0;
}

template<typename T>
static void copy_tensor_async_rows(
    const std::vector<ggml_tensor *> & tensors,
    const buffer_view<T> & dst,
    size_t stride,
    uint32_t row_offset,
    ggml_backend_sched_t sched,
    std::vector<uint32_t> * counts = nullptr) {
    if (!dst.has_data()) {
        return;
    }

    for (size_t i = 0; i < tensors.size(); ++i) {
        auto * tensor = tensors[i];
        if (tensor == nullptr) {
            continue;
        }

        const uint32_t row = row_offset + i;
        const size_t n_elements = ggml_nelements(tensor);
        GGML_ASSERT(ggml_is_contiguous(tensor) && "sampling tensor must be contiguous for async copy");
        GGML_ASSERT(n_elements <= stride);
        GGML_ASSERT((size_t) row * stride + n_elements <= dst.size);

        ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched, tensor);
        T * row_ptr = dst.data + (size_t) row * stride;
        ggml_backend_tensor_get_async(backend, tensor, row_ptr, 0, ggml_nbytes(tensor));

        if (counts) {
            GGML_ASSERT(row < counts->size());
            (*counts)[row] = n_elements;
        }
    }
}

static bool needs_raw_logits(const llama_ubatch & ubatch, const std::map<llama_seq_id, llama_sampler *> & samplers) {
    for (uint32_t i = 0; i < ubatch.n_tokens; i++) {
        if (!ubatch.output[i]) {
            continue;
        }

        // Check if the output token has at least one sequence without a backend sampler.
        for (int32_t j = 0; j < ubatch.n_seq_id[i]; ++j) {
            llama_seq_id seq_id = ubatch.seq_id[i][j];
            if (samplers.find(seq_id) == samplers.end()) {
                return true;
            }
        }
    }
    return false; // all sequences use backend sampling
}

int llama_context::decode(const llama_batch & batch_inp) {
    if (cparams.cassi_apprentice) {
        LLAMA_LOG_ERROR("%s: apprentice_use_session_api\n", __func__);
        return -1;
    }
    // MTP hook batches carry both token (next-token id) and embd (h_nextn row),
    // so accept either present rather than requiring exactly one.
    GGML_ASSERT(batch_inp.token || batch_inp.embd);

    if (!memory) {
        LLAMA_LOG_DEBUG("%s: cannot decode batches with this context (calling encode() instead)\n", __func__);
        return encode(batch_inp);
    }

    if (batch_inp.n_tokens == 0) {
        LLAMA_LOG_ERROR("%s: n_tokens == 0\n", __func__);
        return -1;
    }

    const auto & vocab   = model.vocab;
    const auto & hparams = model.hparams;

    const int64_t n_vocab = vocab.n_tokens();
    const bool    mtp_embd = cparams.ctx_type == LLAMA_CONTEXT_TYPE_MTP && batch_inp.embd;
    const int64_t n_embd  = mtp_embd ? hparams.n_embd_out() : hparams.n_embd_inp();

    // when computing embeddings, all tokens are output
    const bool output_all   = cparams.embeddings;
    const bool has_samplers = !sampling.samplers.empty();

    const uint32_t n_seq_max = cparams.kv_unified ? LLAMA_MAX_SEQ : cparams.n_seq_max;

    // embedding contexts output every token even when batch.logits is not set
    if (has_samplers && (output_all || batch_inp.logits)) {
        std::vector<int32_t> seq_output_count(n_seq_max, 0);

        for (int32_t i = 0; i < batch_inp.n_tokens; ++i) {
            if (!output_all && batch_inp.logits[i] == 0) {
                continue;
            }

            const int ns = batch_inp.n_seq_id ? batch_inp.n_seq_id[i] : 1;

            for (int32_t s = 0; s < ns; ++s) {
                const llama_seq_id seq_id = batch_inp.seq_id ? batch_inp.seq_id[i][s] : 0;

                if (seq_id < 0 || (uint32_t) seq_id >= n_seq_max) {
                    continue;
                }

                seq_output_count[seq_id]++;
                auto sampler = sampling.samplers.find(seq_id);
                if (sampler != sampling.samplers.end() &&
                        seq_output_count[seq_id] > (int32_t) cparams.n_outputs_max_per_seq) {
                    LLAMA_LOG_ERROR("%s: backend sampling supports at most %u outputs per sequence "
                            "(seq_id %d had %d)\n", __func__, cparams.n_outputs_max_per_seq,
                            seq_id, seq_output_count[seq_id]);
                    return -1;
                }
            }
        }
    }

    if (!balloc->init(batch_inp, vocab, memory.get(), n_embd, n_seq_max, output_all)) {
        LLAMA_LOG_ERROR("%s: failed to initialize batch\n", __func__);
        return -1;
    }

    const uint32_t n_tokens_all  = balloc->get_n_tokens();
    const uint32_t n_outputs_all = balloc->get_n_outputs();

    if (output_all) {
        // require that all tokens are output
        if (n_outputs_all != n_tokens_all) {
            LLAMA_LOG_ERROR("%s: pooled embedding requires that all tokens are output (n_outputs_all = %d, n_tokens_all = %d)\n",
                    __func__, n_outputs_all, n_tokens_all);
            return -1;
        }
    }

    GGML_ASSERT(n_tokens_all <= cparams.n_batch);

    GGML_ASSERT((cparams.causal_attn || cparams.n_ubatch >= n_tokens_all) && "non-causal attention requires n_ubatch >= n_tokens");

    // TODO: this clear of the buffer can easily be forgotten - need something better
    // sync first so any in-flight async copies into embd_seq complete before it is freed
    if (!embd_seq.empty()) {
        synchronize();
    }
    embd_seq.clear();

    if (t_compute_start_us == 0) {
        t_compute_start_us = ggml_time_us();
    }
    n_queued_tokens += n_tokens_all;

    output_swaps.clear();

    sched_reserve();

    bool did_optimize = false;

    // handle any pending shifts/copies
    memory_update(false);

    llama_memory_context_ptr mctx;

    while (true) {
        mctx = memory->init_batch(*balloc, cparams.n_ubatch, output_all);
        if (!mctx) {
            return -2;
        }

        switch (mctx->get_status()) {
            case LLAMA_MEMORY_STATUS_SUCCESS:
                {
                } break;
            case LLAMA_MEMORY_STATUS_NO_UPDATE:
                {
                    LLAMA_LOG_ERROR("%s: unexpected memory context status: %d\n", __func__, mctx->get_status());

                    return -2;
                }
            case LLAMA_MEMORY_STATUS_FAILED_PREPARE:
                {
                    if (!did_optimize) {
                        did_optimize = true;

                        if (memory_update(true)) {
                            LLAMA_LOG_DEBUG("%s: retrying batch size %d after cache optimization\n", __func__, balloc->get_n_tokens());

                            continue;
                        }
                    }

                    LLAMA_LOG_WARN("%s: failed to find a memory slot for batch of size %d\n", __func__, balloc->get_n_tokens());

                    return 1;
                }
            case LLAMA_MEMORY_STATUS_FAILED_COMPUTE:
                {
                    LLAMA_LOG_ERROR("%s: compute failed while preparing batch of size %d\n", __func__, balloc->get_n_tokens());

                    return -2;
                }
        }

        break;
    }

    // reserve output buffer
    if (output_reserve(n_outputs_all) < n_outputs_all) {
        LLAMA_LOG_ERROR("%s: could not reserve space for batch with %d outputs\n", __func__, n_outputs_all);
        return -2;
    };

    // start a new sampling transaction for this logical batch
    for (const auto & entry : sampling.samplers) {
        llama_sampler_backend_begin(entry.second);
    }

    int64_t n_outputs_prev = 0;
    int64_t n_tokens_prev  = 0;

    do {
        const auto & ubatch = mctx->get_ubatch();

        // count the outputs in this ubatch
        {
            int32_t n_outputs_new = 0;

            if (n_outputs_all == n_tokens_all) {
                n_outputs_new = ubatch.n_tokens;
            } else {
                for (uint32_t i = 0; i < ubatch.n_tokens; i++) {
                    n_outputs_new += (int32_t) (ubatch.output[i] != 0);
                }
            }

            // needs to happen before the graph is built
            n_outputs = n_outputs_new;
        }

        ggml_status status;

        const auto * res = process_ubatch(ubatch, ctx_type_to_graph_type(cparams.ctx_type), mctx.get(), status);

        if (!res) {
            // the last ubatch failed or was aborted -> remove all positions of that ubatch from the memory module
            llama_pos pos_min[LLAMA_MAX_SEQ];
            for (int s = 0; s < LLAMA_MAX_SEQ; ++s) {
                pos_min[s] = std::numeric_limits<llama_pos>::max();
            }

            for (uint32_t i = 0; i < ubatch.n_tokens; ++i) {
                const auto & seq_id = ubatch.seq_id[i][0];

                pos_min[seq_id] = std::min(pos_min[seq_id], ubatch.pos[i]);
            }

            for (int s = 0; s < LLAMA_MAX_SEQ; ++s) {
                if (pos_min[s] == std::numeric_limits<llama_pos>::max()) {
                    continue;
                }

                LLAMA_LOG_WARN("%s: removing memory module entries for seq_id = %d, pos = [%d, +inf)\n", __func__, s, pos_min[s]);

                memory->seq_rm(s, pos_min[s], -1);
            }

            switch (status) {
                case GGML_STATUS_ABORTED:      return  2;
                case GGML_STATUS_ALLOC_FAILED: return -2;
                case GGML_STATUS_FAILED:       return -3;
                case GGML_STATUS_SUCCESS:      GGML_ABORT("should not happen");
            }
        }

        // plot the computation graph in dot format (for debugging purposes)
        //if (n_past%100 == 0) {
        //    ggml_graph_dump_dot(gf, NULL, "llama.dot");
        //}

        auto * t_logits  = res->get_logits();
        auto * t_embd    = cparams.embeddings       ? res->get_embd()     : nullptr;
        auto * t_h_nextn = cparams.embeddings_nextn ? res->get_h_nextn()  : nullptr;

        if (t_embd && res->get_embd_pooled()) {
            t_embd = res->get_embd_pooled();
        }

        // extract logits
        if (logits.data && t_logits && n_outputs > 0 && needs_raw_logits(ubatch, sampling.samplers)) {
            ggml_backend_t backend_res = ggml_backend_sched_get_tensor_backend(sched.get(), t_logits);
            GGML_ASSERT(backend_res != nullptr);
            GGML_ASSERT(logits.data != nullptr);

            float * logits_out = logits.data + n_outputs_prev*n_vocab;

            if (n_outputs) {
                GGML_ASSERT( n_outputs_prev + n_outputs <= n_outputs_all);
                GGML_ASSERT((n_outputs_prev + n_outputs)*n_vocab <= (int64_t) logits.size);
                ggml_backend_tensor_get_async(backend_res, t_logits, logits_out, 0, n_outputs*n_vocab*sizeof(float));
            }
        }

        // extract embeddings
        if (embd.data && t_embd && n_outputs > 0) {
            ggml_backend_t backend_embd = ggml_backend_sched_get_tensor_backend(sched.get(), t_embd);
            GGML_ASSERT(backend_embd != nullptr);

            switch (cparams.pooling_type) {
                case LLAMA_POOLING_TYPE_NONE:
                    {
                        // extract token embeddings
                        GGML_ASSERT(embd.data != nullptr);
                        const uint32_t n_embd_out = hparams.n_embd_out();
                        float * embd_out = embd.data + n_outputs_prev*n_embd_out;

                        if (n_outputs) {
                            GGML_ASSERT( n_outputs_prev + n_outputs <= n_outputs_all);
                            GGML_ASSERT((n_outputs_prev + n_outputs)*n_embd_out <= (int64_t) embd.size);
                            ggml_backend_tensor_get_async(backend_embd, t_embd, embd_out, 0, n_outputs*n_embd_out*sizeof(float));
                        }
                    } break;
                case LLAMA_POOLING_TYPE_MEAN:
                case LLAMA_POOLING_TYPE_CLS:
                case LLAMA_POOLING_TYPE_LAST:
                    {
                        // extract sequence embeddings (cleared before processing each batch)
                        auto & embd_seq_out = embd_seq;

                        // use n_embd_out (not n_embd_inp) - the pooled embedding has the model's
                        // output dimension, which differs from input dimension for deepstack models (e.g. qwen3vl)
                        const uint32_t n_embd_out = hparams.n_embd_out();

                        for (uint32_t s = 0; s < ubatch.n_seqs_unq; ++s) {
                            const llama_seq_id seq_id  = ubatch.seq_id_unq[s];
                            const int32_t      seq_idx = ubatch.seq_idx[seq_id];

                            embd_seq_out[seq_id].resize(n_embd_out);
                            ggml_backend_tensor_get_async(backend_embd, t_embd, embd_seq_out[seq_id].data(), (n_embd_out*seq_idx)*sizeof(float), n_embd_out*sizeof(float));
                        }
                    } break;
                case LLAMA_POOLING_TYPE_RANK:
                    {
                        // extract the rerank score - n_cls_out floats per sequence
                        auto & embd_seq_out = embd_seq;

                        const uint32_t n_cls_out = hparams.n_cls_out;

                        for (uint32_t s = 0; s < ubatch.n_seqs_unq; ++s) {
                            const llama_seq_id seq_id  = ubatch.seq_id_unq[s];
                            const int32_t      seq_idx = ubatch.seq_idx[seq_id];

                            embd_seq_out[seq_id].resize(n_cls_out);
                            ggml_backend_tensor_get_async(backend_embd, t_embd, embd_seq_out[seq_id].data(), (n_cls_out*seq_idx)*sizeof(float), n_cls_out*sizeof(float));
                        }
                    } break;
                case LLAMA_POOLING_TYPE_UNSPECIFIED:
                    {
                        GGML_ABORT("unknown pooling type");
                    }
            }
        }

        extract_layer_inputs(res, n_tokens_prev, ubatch.n_tokens);

        // extract nextn embeddings before
        // only meaningful in LLAMA_POOLING_TYPE_NONE (per-token); other pooling modes are ignored.
        {
            const bool masked    = cparams.embeddings_nextn_masked;
            const int64_t n_rows = masked ? n_outputs       : (int64_t) ubatch.n_tokens;
            const int64_t offset = masked ? n_outputs_prev  : n_tokens_prev;

            if (embd_nextn.data && t_h_nextn && n_rows > 0 && cparams.pooling_type == LLAMA_POOLING_TYPE_NONE) {
                ggml_backend_t backend_h = ggml_backend_sched_get_tensor_backend(sched.get(), t_h_nextn);
                GGML_ASSERT(backend_h != nullptr);

                const uint32_t n_embd  = hparams.n_embd_out();
                float * embd_nextn_out = embd_nextn.data + offset*n_embd;

                GGML_ASSERT((offset + n_rows)*n_embd <= (int64_t) embd_nextn.size);
                ggml_backend_tensor_get_async(backend_h, t_h_nextn, embd_nextn_out, 0, n_rows*n_embd*sizeof(float));
            }
        }

        if (has_samplers) {
            const auto stride = n_vocab;

            // async copy the sampling data from the backend to the host
            copy_tensor_async_rows(res->t_sampled,        sampling.sampled,    1,      n_outputs_prev, sched.get());
            copy_tensor_async_rows(res->t_sampled_logits, sampling.logits,     stride, n_outputs_prev, sched.get(), &sampling.logits_count);
            copy_tensor_async_rows(res->t_sampled_probs,  sampling.probs,      stride, n_outputs_prev, sched.get(), &sampling.probs_count);
            copy_tensor_async_rows(res->t_candidates,     sampling.candidates, stride, n_outputs_prev, sched.get(), &sampling.candidates_count);
        }

        n_outputs_prev += n_outputs;
        n_tokens_prev  += ubatch.n_tokens;
    } while (mctx->next());

    // set to total number of outputs in the batch, for use in llama_get_logits_ith
    n_outputs = n_outputs_all;

    // set output mappings
    if (n_outputs > 0) {
        bool sorted_output = true;

        auto & out_ids = balloc->get_out_ids();

        GGML_ASSERT(out_ids.size() == (size_t) n_outputs);

        for (int64_t i = 0; i < n_outputs; ++i) {
            int64_t out_id = out_ids[i];
            output_ids[out_id] = i;
            if (out_id != i) {
                sorted_output = false;
            }
        }

        // make the outputs have the same order they had in the user-provided batch
        // note: this is mostly relevant for recurrent models atm
        if (!sorted_output && n_outputs > 1) {
            GGML_ASSERT((size_t) n_outputs == out_ids.size());

            // TODO: is there something more efficient which also minimizes swaps?
            // selection sort, to minimize swaps (from https://en.wikipedia.org/wiki/Selection_sort)
            for (uint32_t i = 0; i < n_outputs - 1; ++i) {
                uint32_t j_min = i;
                for (uint32_t j = i + 1; j < n_outputs; ++j) {
                    if (out_ids[j] < out_ids[j_min]) {
                        j_min = j;
                    }
                }
                if (j_min == i) {
                    continue;
                }
                std::swap(out_ids[i], out_ids[j_min]);

                // remember the swaps and apply them lazily upon logits/embeddings access
                output_swaps.push_back({ i, j_min });
            }

            std::fill(output_ids.begin(), output_ids.end(), -1);

            for (uint32_t i = 0; i < n_outputs; ++i) {
                output_ids[out_ids[i]] = i;
            }
        }
    }

    // wait for the computation to finish (automatically done when obtaining the model output)
    //synchronize();

    return 0;
}

//
// output
//

uint32_t llama_context::output_reserve(int32_t n_outputs) {
    const auto & hparams = model.hparams;
    const auto & vocab   = model.vocab;

    const int64_t n_outputs_max = std::max<int64_t>(n_outputs, n_seq_max());

    const auto n_batch    = cparams.n_batch;
    const auto n_vocab    = vocab.n_tokens();
    const auto n_embd     = hparams.n_embd;
    const auto n_embd_out = hparams.n_embd_out();

    bool has_logits     = true;
    bool has_embd       = cparams.embeddings;
    bool has_embd_nextn = cparams.embeddings_nextn;

    // TODO: hacky enc-dec support
    if (model.arch == LLM_ARCH_T5) {
        has_logits = true;
        has_embd   = true;
    }

    size_t backend_float_count = 0;
    size_t backend_token_count = 0;
    size_t embd_layer_inp_float_count = 0;

    logits.size     = has_logits     ? n_vocab*n_outputs_max     : 0;
    embd.size       = has_embd       ? n_embd_out*n_outputs_max  : 0;
    embd_nextn.size = has_embd_nextn ? n_embd_out*n_outputs_max  : 0;

    if (has_embd_nextn && !cparams.embeddings_nextn_masked) {
        // unmasked: nextn row exists for every token in the batch, not just
        // those flagged via batch.logits[i] -> size by token count instead.
        embd_nextn.size = (size_t) n_embd_out * n_batch;
    }

    for (bool enabled : cparams.embeddings_layer_inp) {
        if (enabled) {
            embd_layer_inp_float_count += (size_t) n_embd * n_batch;
        }
    }

    // Allocate backend sampling output buffers if there are backend samplers configured.
    const bool has_sampling = !sampling.samplers.empty();
    if (has_sampling) {
        backend_float_count = 2 * n_vocab * n_outputs_max;      // logits + probs
        backend_token_count = (1 + n_vocab) * n_outputs_max;    // sampled + candidates
    }

    if (output_ids.empty()) {
        // init, never resized afterwards
        output_ids.resize(n_batch);
    }

    const size_t prev_size = buf_output ? ggml_backend_buffer_get_size(buf_output.get()) : 0;
    const size_t new_size  =
        (logits.size + embd.size + embd_nextn.size + embd_layer_inp_float_count + backend_float_count) * sizeof(float) +
        (                                                                         backend_token_count) * sizeof(llama_token);

    // alloc only when more than the current capacity is required
    // TODO: also consider shrinking the buffer
    if (!buf_output || prev_size < new_size) {
        if (buf_output) {
#ifndef NDEBUG
            // This doesn't happen often, but may be annoying in some cases (like the HellaSwag benchmark)
            LLAMA_LOG_DEBUG("%s: reallocating output buffer from size %.02f MiB to %.02f MiB\n", __func__, prev_size / 1024.0 / 1024.0, new_size / 1024.0 / 1024.0);
#endif
            synchronize();

            // TODO: not needed?
            buf_output = nullptr;
            logits.data = nullptr;
            embd.data = nullptr;
            embd_nextn.data = nullptr;
            for (auto & layer_inp : embd_layer_inp) {
                layer_inp = {nullptr, 0};
            }
        }

        auto * buft = ggml_backend_cpu_buffer_type();
        // try to use the host buffer of the device where the output tensor is allocated for faster transfer to system memory
        auto * output_dev = model.dev_output();
        auto * output_dev_host_buft = output_dev ? ggml_backend_dev_host_buffer_type(output_dev) : nullptr;
        if (output_dev_host_buft) {
            buft = output_dev_host_buft;
        }
        buf_output.reset(ggml_backend_buft_alloc_buffer(buft, new_size));
        if (buf_output == nullptr) {
            LLAMA_LOG_ERROR("%s: failed to allocate output buffer of size %.2f MiB\n", __func__, new_size / (1024.0 * 1024.0));
            return 0;
        }
        ggml_backend_buffer_clear(buf_output.get(), 0);
    }

    float * output_base = (float *) ggml_backend_buffer_get_base(buf_output.get());

    size_t offset = 0;
    uint8_t * base = (uint8_t *) output_base;

    logits = has_logits ? buffer_view<float>{output_base, logits.size} : buffer_view<float>{nullptr, 0};
    offset += logits.size * sizeof(float);

    embd = has_embd ? buffer_view<float>{(float *) (base + offset), embd.size} : buffer_view<float>{nullptr, 0};
    offset += embd.size * sizeof(float);

    embd_nextn = has_embd_nextn ? buffer_view<float>{(float *) (base + offset), embd_nextn.size} : buffer_view<float>{nullptr, 0};
    offset += embd_nextn.size * sizeof(float);

    for (uint32_t il = 0; il < embd_layer_inp.size(); ++il) {
        if (cparams.embeddings_layer_inp[il]) {
            embd_layer_inp[il] = buffer_view<float>{(float *) (base + offset), (size_t) n_embd * n_batch};
            offset += embd_layer_inp[il].size * sizeof(float);
        } else {
            embd_layer_inp[il] = buffer_view<float>{nullptr, 0};
        }
    }

    if (has_sampling) {
        sampling.logits = {(float *) (base + offset), (size_t)(n_vocab*n_outputs_max)};
        offset += sampling.logits.size * sizeof(float);

        sampling.probs = {(float *) (base + offset), (size_t)(n_vocab*n_outputs_max)};
        offset += sampling.probs.size * sizeof(float);

        sampling.sampled = {(llama_token *) (base + offset), (size_t)n_outputs_max};
        offset += sampling.sampled.size * sizeof(llama_token);

        sampling.candidates = {(llama_token *) (base + offset), (size_t)(n_vocab*n_outputs_max)};
        offset += sampling.candidates.size * sizeof(llama_token);

        // The count vectors keep track of the actual number of logits/probs/candidates
        // copied from the backend for each output row.

        sampling.logits_count.resize(n_outputs_max);
        sampling.probs_count.resize(n_outputs_max);
        sampling.candidates_count.resize(n_outputs_max);

        std::fill(sampling.logits_count.begin(),     sampling.logits_count.end(),     0);
        std::fill(sampling.probs_count.begin(),      sampling.probs_count.end(),      0);
        std::fill(sampling.candidates_count.begin(), sampling.candidates_count.end(), 0);

        std::fill_n(sampling.sampled.data, sampling.sampled.size, LLAMA_TOKEN_NULL);
    } else {
        sampling.logits     = {nullptr, 0};
        sampling.probs      = {nullptr, 0};
        sampling.sampled    = {nullptr, 0};
        sampling.candidates = {nullptr, 0};

        sampling.logits_count.clear();
        sampling.probs_count.clear();
        sampling.candidates_count.clear();
    }

    // set all ids as invalid (negative)
    std::fill(output_ids.begin(), output_ids.end(), -1);

    this->n_outputs = 0;

    GGML_ASSERT(n_outputs_max <= cparams.n_outputs_max);

    return n_outputs_max;
}

void llama_context::extract_layer_inputs(const llm_graph_result * res, size_t token_offset, size_t n_tokens) {
    for (uint32_t il = 0; il < cparams.embeddings_layer_inp.size(); ++il) {
        if (!cparams.embeddings_layer_inp[il]) {
            continue;
        }
        if (!embd_layer_inp[il].has_data()) {
            GGML_ABORT("output layer input buffer not allocated");
        }
        ggml_tensor * t = res->get_layer_inp((int) il);
        if (!t) {
            GGML_ABORT("layer input tensor not found");
        }

        const size_t nbytes = ggml_nbytes(t);
        const size_t nfloats = nbytes / sizeof(float);
        GGML_ASSERT(n_tokens > 0);
        GGML_ASSERT(nfloats % n_tokens == 0);

        const size_t row_floats = nfloats / n_tokens;
        const size_t dst_offset = token_offset * row_floats;
        GGML_ASSERT(dst_offset + nfloats <= embd_layer_inp[il].size);

        ggml_backend_t backend = ggml_backend_sched_get_tensor_backend(sched.get(), t);
        GGML_ASSERT(backend != nullptr);
        ggml_backend_tensor_get_async(backend, t, embd_layer_inp[il].data + dst_offset, 0, nbytes);
    }
}

void llama_context::output_reorder() {
    const uint64_t n_vocab     = model.vocab.n_tokens();
    const uint64_t n_embd      = model.hparams.n_embd;
    const uint64_t n_embd_out  = model.hparams.n_embd_out();

    for (size_t s = 0; s < output_swaps.size(); ++s) {
        const uint64_t i0 = output_swaps[s].i0;
        const uint64_t i1 = output_swaps[s].i1;

        if (logits.size > 0) {
            for (uint64_t k = 0; k < n_vocab; k++) {
                std::swap(logits.data[i0*n_vocab + k], logits.data[i1*n_vocab + k]);
            }
        }

        if (embd.size > 0) {
            for (uint64_t k = 0; k < n_embd_out; k++) {
                std::swap(embd.data[i0*n_embd_out + k], embd.data[i1*n_embd_out + k]);
            }
        }

        if (embd_nextn.size > 0) {
            for (uint64_t k = 0; k < n_embd_out; k++) {
                std::swap(embd_nextn.data[i0*n_embd_out + k], embd_nextn.data[i1*n_embd_out + k]);
            }
        }

        if (embd_layer_inp.size() > 0) {
            for (int lid = 0; lid < (int) embd_layer_inp.size(); ++lid) {
                if (embd_layer_inp[lid].size > 0) {
                    for (uint64_t k = 0; k < n_embd; ++k) {
                        std::swap(embd_layer_inp[lid].data[i0*n_embd + k], embd_layer_inp[lid].data[i1*n_embd + k]);
                    }
                }
            }
        }

        if (!sampling.samplers.empty()) {
            assert(sampling.logits.size > 0);
            assert(sampling.probs.size > 0);
            assert(sampling.candidates.size > 0);
            assert(sampling.sampled.size > 0);
            assert(sampling.logits_count.size() > 0);
            assert(sampling.probs_count.size() > 0);
            assert(sampling.candidates_count.size() > 0);

            for (uint64_t k = 0; k < n_vocab; ++k) {
                std::swap(sampling.logits.data[i0*n_vocab + k], sampling.logits.data[i1*n_vocab + k]);
            }

            for (uint64_t k = 0; k < n_vocab; ++k) {
                std::swap(sampling.probs.data[i0*n_vocab + k], sampling.probs.data[i1*n_vocab + k]);
            }

            for (uint64_t k = 0; k < n_vocab; ++k) {
                std::swap(sampling.candidates.data[i0*n_vocab + k], sampling.candidates.data[i1*n_vocab + k]);
            }

            std::swap(sampling.sampled.data[i0],     sampling.sampled.data[i1]);
            std::swap(sampling.logits_count[i0],     sampling.logits_count[i1]);
            std::swap(sampling.probs_count[i0],      sampling.probs_count[i1]);
            std::swap(sampling.candidates_count[i0], sampling.candidates_count[i1]);
        }
    }

    output_swaps.clear();
}

//
// graph
//

uint32_t llama_context::graph_max_nodes(uint32_t n_tokens) const {
    uint32_t res;
    if (model.arch == LLM_ARCH_KIMI_K3) {
        // the n_tokens*40 budget below is exhausted at ubatch 3840
        res = std::max<uint32_t>(n_tokens * 160, 64u * model.n_tensors());
    } else if (model.arch == LLM_ARCH_QWEN3NEXT ||
        model.arch == LLM_ARCH_KIMI_LINEAR ||
        model.arch == LLM_ARCH_BAILINGMOE3 ||
        model.arch == LLM_ARCH_QWEN35 ||
        model.arch == LLM_ARCH_QWEN35MOE ||
        model.arch == LLM_ARCH_DEEPSEEK4 ||
        (model.arch == LLM_ARCH_DFLASH && model.hparams.dsv4_hc_mult > 0) ||
        model.arch == LLM_ARCH_NANBEIGE ||
        model.arch == LLM_ARCH_MINIMAX_01 ||
        model.arch == LLM_ARCH_MINIMAX_M3) {
        res = std::max<uint32_t>(n_tokens * 40, 32u * model.n_tensors());
    } else {
        res = std::max<uint32_t>(1024u, 8u*model.n_tensors());
        for (const auto & lora : model.loras) {
            res += lora->get_n_nodes();
        }
    }

    uint32_t n_sampling_nodes = 0;
    uint32_t n_sampling_nodes_max = 0;
    for (const auto & [seq_id, sampler] : sampling.samplers) {
        const uint32_t n_nodes = llama_sampler_backend_n_nodes(sampler);
        n_sampling_nodes += n_nodes;
        if (cparams.n_outputs_max_per_seq > 1) {
            n_sampling_nodes_max = std::max(n_sampling_nodes_max, n_nodes);
        }
    }

    const uint32_t n_sampling_outputs_max = std::min<uint64_t>(
            std::min(n_tokens, cparams.n_outputs_max),
            (uint64_t) cparams.n_seq_max * cparams.n_outputs_max_per_seq);

    res += n_sampling_nodes;
    if (n_sampling_outputs_max > 1) {
        res += (n_sampling_outputs_max - 1) * n_sampling_nodes_max;
    }
    return res;
}

llm_graph_result * llama_context::get_gf_res_reserve() const {
    return static_cast<llm_graph_result *>(gf_res_reserve.get());
}

// pack sampler outputs into as few sequences as possible before using sequences without samplers
static void ubatch_prepare_reserve(
              llama_ubatch                            & ubatch,
              uint32_t                                  n_outputs,
        const std::map<llama_seq_id, llama_sampler *> & samplers,
              uint32_t                                  n_outputs_max_per_seq) {
    const uint32_t n_seqs       = ubatch.n_seqs;
    const uint32_t n_seq_tokens = ubatch.n_seq_tokens;

    for (uint32_t s = 0; s < n_seqs; ++s) {
        for (uint32_t t = 0; t < n_seq_tokens; ++t) {
            const uint32_t i = s * n_seq_tokens + t;
            ubatch.n_seq_id[i] = 1;
            ubatch.seq_id[i] = &ubatch.seq_id_unq[s];
        }
    }

    // sequences with a sampler that fit in this ubatch
    std::vector<uint32_t> sampler_seqs;
    std::vector<bool> has_sampler(n_seqs, false);
    for (const auto & entry : samplers) {
        const llama_seq_id seq_id = entry.first;
        if (seq_id < 0 || (uint32_t) seq_id >= n_seqs) {
            continue;
        }

        sampler_seqs.push_back(seq_id);
        has_sampler[seq_id] = true;
    }

    uint32_t n_outputs_set = 0;

    const uint32_t n_outputs_per_seq = std::min(n_seq_tokens, n_outputs_max_per_seq);
    for (uint32_t s : sampler_seqs) {
        if (n_outputs_set >= n_outputs) {
            break;
        }

        for (uint32_t t = 0; t < n_outputs_per_seq && n_outputs_set < n_outputs; ++t) {
            ubatch.output[s * n_seq_tokens + t] = true;
            ++n_outputs_set;
        }
    }

    // use sequences without samplers for any remaining outputs
    for (uint32_t t = 0; t < n_seq_tokens && n_outputs_set < n_outputs; ++t) {
        for (uint32_t s = 0; s < n_seqs && n_outputs_set < n_outputs; ++s) {
            if (has_sampler[s]) {
                continue;
            }

            ubatch.output[s * n_seq_tokens + t] = true;
            ++n_outputs_set;
        }
    }
}

ggml_cgraph * llama_context::graph_reserve(
        uint32_t n_tokens, uint32_t n_seqs, uint32_t n_outputs, const llama_memory_context_i * mctx, bool split_only, size_t * sizes) {
    LLAMA_LOG_DEBUG("%s: reserving a graph for ubatch with n_tokens = %4u, n_seqs = %2u, n_outputs = %4u\n", __func__, n_tokens, n_seqs, n_outputs);
    GGML_ASSERT(n_outputs >= 1);

    if (n_tokens % n_seqs != 0) {
        n_tokens = ((n_tokens + (n_seqs - 1)) / n_seqs) * n_seqs; // round to next multiple of n_seqs
        LLAMA_LOG_DEBUG("%s: making n_tokens a multiple of n_seqs - n_tokens = %u, n_seqs = %u, n_outputs = %u\n", __func__, n_tokens, n_seqs, n_outputs);
    }

    ggml_backend_sched_reset(sched.get());

    // when the scheduler is reset, we cannot reuse the old graph, so we reset the previous graph result to prevent that
    gf_res_prev->reset();

    // store the n_outputs as it is, and restore it afterwards
    // TODO: not sure if needed, might simplify in the future by removing this
    const auto save_n_outputs = this->n_outputs;

    this->n_outputs = n_outputs;

    llama_batch_allocr balloc(model.hparams.n_pos_per_embd());
    llama_ubatch ubatch = balloc.ubatch_reserve(n_tokens/n_seqs, n_seqs);

    ubatch_prepare_reserve(ubatch, n_outputs, sampling.samplers, cparams.n_outputs_max_per_seq);

    auto * res = gf_res_reserve.get();

    const auto gparams = graph_params(res, ubatch, mctx, ctx_type_to_graph_type(cparams.ctx_type));

    res->reset();

    auto * gf = model.build_graph(gparams);

    this->n_outputs = save_n_outputs;

    // initialize scheduler with the specified graph
    if (split_only) {
        if (sizes) {
            ggml_backend_sched_reserve_size(sched.get(), gf, sizes);
        } else {
            ggml_backend_sched_split_graph(sched.get(), gf);
        }
    } else if (!ggml_backend_sched_reserve(sched.get(), gf)) {
        GGML_ASSERT(!sizes);
        LLAMA_LOG_ERROR("%s: failed to allocate compute buffers\n", __func__);
        return nullptr;
    }

    return gf;
}
bool llama_context::graph_site_candidate_set(const llama_cassi_graph_site_candidate & c) {
    if (cassi_service_active || cassi_service_snapshot_valid ||
            !cassi_service_group_snapshot.empty() || graph_site_candidate_pending ||
            cassi_service_poisoned) {
        return false;
    }
    const auto reject = [&](const char * reason) {
        graph_site_candidate = {};
        graph_site_candidate_pending = false;
        graph_site_candidate_result = {};
        graph_site_candidate_result.attempted = true;
        graph_site_candidate_result.owner_generation = c.owner_generation;
        graph_site_candidate_result.refusal = reason;
        return false;
    };
    const auto valid_sha256 = [](const char * value) {
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
    };
    if ((c.kind != LLAMA_CASSI_GRAPH_SITE_EXPERTS && c.kind != LLAMA_CASSI_GRAPH_SITE_RECURRENT &&
                c.kind != LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY &&
                c.kind != LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE) ||
            c.architecture == nullptr ||
            std::strcmp(c.architecture, llm_arch_name(model.arch)) != 0 ||
            c.source_sha256 == nullptr || c.sequence_id == nullptr || c.sequence_id[0] == '\0' ||
            c.backend == nullptr || c.backend[0] == '\0' ||
            c.input_tensor == nullptr || c.output_tensor == nullptr ||
            c.tensor_dtype == nullptr || std::strcmp(c.tensor_dtype, "f32") != 0 ||
            c.stage == nullptr || c.site == nullptr || c.specialist == nullptr || c.specialist[0] == '\0' ||
            c.predecessor_sha256 == nullptr || c.request_sha256 == nullptr ||
            c.invocation_sha256 == nullptr || c.candidate_sha256 == nullptr ||
            c.intervention_order == nullptr || c.intervention_order[0] == '\0' ||
            c.dependencies_json == nullptr || c.dependencies_json[0] == '\0' ||
            c.method_key == nullptr || std::strcmp(c.method_key, "cassifi.graph-site-low-rank-affine.v1") != 0 ||
            c.method_generation == 0 || c.a == nullptr || c.b == nullptr || c.bias == nullptr ||
            c.input_width == 0 || c.output_width == 0 || c.rank == 0 || c.rank > 16 ||
            c.position < 0 ||
            (c.kind == LLAMA_CASSI_GRAPH_SITE_EXECUTION_CHOICE
                ? c.layer != -1
                : (c.layer < 0 || c.layer >= (int32_t) model.hparams.n_layer())) ||
            c.seq_id < 0 || c.seq_id >= LLAMA_MAX_SEQ || c.owner_generation == 0 ||
            !valid_sha256(c.source_sha256) || !valid_sha256(c.predecessor_sha256) ||
            (c.request_sha256_pending
                ? c.request_sha256[0] != '\0'
                : !valid_sha256(c.request_sha256)) ||
            !valid_sha256(c.invocation_sha256) || !valid_sha256(c.candidate_sha256)) {
        return reject("invalid_candidate");
    }

    uint64_t expected_input = 0;
    uint64_t expected_output = 0;
    if (c.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
        const auto & layer = model.layers[c.layer];
        if (std::strcmp(c.stage, "qwen-experts") != 0 ||
                std::strcmp(c.site, "qwen-experts") != 0 ||
                std::strcmp(c.specialist, "expert-synthesis") != 0 ||
                std::strcmp(c.input_tensor, "attn_post_norm") != 0 ||
                std::strcmp(c.output_tensor, "ffn_delta") != 0 ||
                layer.ffn_gate_inp == nullptr || layer.ffn_down_exps == nullptr ||
                (layer.ffn_gate_up_exps == nullptr &&
                 (layer.ffn_up_exps == nullptr || layer.ffn_gate_exps == nullptr)) ||
                ((layer.ffn_gate_inp_shexp != nullptr || layer.ffn_gate_shexp != nullptr ||
                  layer.ffn_up_shexp != nullptr || layer.ffn_down_shexp != nullptr) &&
                 (layer.ffn_gate_inp_shexp == nullptr || layer.ffn_gate_shexp == nullptr ||
                  layer.ffn_up_shexp == nullptr || layer.ffn_down_shexp == nullptr))) {
            return reject("expert_site_unsupported");
        }
        expected_input = model.hparams.n_embd;
        expected_output = model.hparams.n_embd;
        if (c.conv_history_rows != 0 || c.conv_history_channels != 0 ||
                c.recurrent_state_heads != 0 || c.recurrent_state_value_width != 0 ||
                c.recurrent_state_key_width != 0 ||
                c.attn_kv_heads != 0 || c.attn_kv_head_width != 0) {
            return reject("unexpected_recurrent_shape");
        }
    } else if (c.kind == LLAMA_CASSI_GRAPH_SITE_RECURRENT) {
        const auto & layer = model.layers[c.layer];
        if (std::strcmp(c.stage, "qwen-attention-route") != 0 ||
                std::strcmp(c.site, "recurrent-attention") != 0 ||
                std::strcmp(c.specialist, "recurrent-dynamics") != 0 ||
                std::strcmp(c.input_tensor, "recurrent_features") != 0 ||
                std::strcmp(c.output_tensor, "recurrent_successor") != 0 ||
                !model.hparams.is_recr(c.layer) || layer.ssm_conv1d == nullptr) {
            return reject("recurrent_site_unsupported");
        }
        const uint64_t conv_rows = (uint64_t) layer.ssm_conv1d->ne[0] - 1;
        const uint64_t conv_channels = model.hparams.ssm_d_inner +
            2ULL * model.hparams.ssm_n_group * model.hparams.ssm_d_state;
        const uint64_t state_heads = model.hparams.ssm_dt_rank;
        const uint64_t state_head_width = state_heads == 0 ? 0 :
            model.hparams.ssm_d_inner / state_heads;
        const uint64_t conv_width = conv_rows * conv_channels;
        const uint64_t state_width = model.hparams.n_embd_s();
        const uint64_t state_element_count =
            state_heads * state_head_width * state_head_width;
        const uint64_t total_width = model.hparams.n_embd + conv_width + state_width;
        if (conv_rows == 0 || conv_channels == 0 || state_heads == 0 ||
                state_head_width == 0 || total_width > UINT32_MAX ||
                conv_width != (uint64_t) model.hparams.n_embd_r() ||
                state_width != (uint64_t) model.hparams.n_embd_s() ||
                state_element_count != state_width ||
                c.conv_history_rows != conv_rows ||
                c.conv_history_channels != conv_channels ||
                c.recurrent_state_heads != state_heads ||
                c.recurrent_state_value_width != state_head_width ||
                c.recurrent_state_key_width != state_head_width ||
                c.attn_kv_heads != 0 || c.attn_kv_head_width != 0) {
            return reject("recurrent_state_shape_mismatch");
        }
        expected_input = total_width;
        expected_output = total_width;
    } else if (c.kind == LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY) {
        const auto & layer = model.layers[c.layer];
        if (std::strcmp(c.stage, "qwen-attention-route") != 0 ||
                std::strcmp(c.site, "attention-memory") != 0 ||
                std::strcmp(c.specialist, "attention-memory") != 0 ||
                std::strcmp(c.input_tensor, "attention_features") != 0 ||
                std::strcmp(c.output_tensor, "attention_successor") != 0 ||
                model.hparams.is_recr(c.layer) || layer.wo == nullptr) {
            return reject("attention_memory_site_unsupported");
        }
        const uint64_t kv_heads = model.hparams.n_head_kv(c.layer);
        const uint64_t kv_head_width = model.hparams.n_embd_head_v(c.layer);
        if (kv_heads == 0 || kv_head_width == 0 ||
                kv_head_width != model.hparams.n_embd_head_k(c.layer) ||
                c.attn_kv_heads != kv_heads || c.attn_kv_head_width != kv_head_width ||
                c.conv_history_rows != 0 || c.conv_history_channels != 0 ||
                c.recurrent_state_heads != 0 || c.recurrent_state_value_width != 0 ||
                c.recurrent_state_key_width != 0) {
            return reject("attention_memory_state_shape_mismatch");
        }
        const uint64_t kv_width = kv_heads * kv_head_width;
        if (kv_width > UINT32_MAX ||
                (uint64_t) model.hparams.n_embd + 2ULL * kv_width > UINT32_MAX) {
            return reject("method_shape_mismatch");
        }
        expected_input = model.hparams.n_embd;
        expected_output = model.hparams.n_embd + 2ULL * kv_width;
    } else {
        if (std::strcmp(c.stage, "qwen-head") != 0 ||
                std::strcmp(c.site, "execution-choice") != 0 ||
                std::strcmp(c.specialist, "execution-choice") != 0 ||
                std::strcmp(c.input_tensor, "head_input") != 0 ||
                std::strcmp(c.output_tensor, "logits") != 0) {
            return reject("execution_choice_site_unsupported");
        }
        if (c.conv_history_rows != 0 || c.conv_history_channels != 0 ||
                c.recurrent_state_heads != 0 || c.recurrent_state_value_width != 0 ||
                c.recurrent_state_key_width != 0 ||
                c.attn_kv_heads != 0 || c.attn_kv_head_width != 0) {
            return reject("unexpected_recurrent_shape");
        }
        const uint64_t vocab_size = (uint64_t) model.vocab.n_tokens();
        if (vocab_size == 0 || vocab_size > UINT32_MAX) {
            return reject("method_shape_mismatch");
        }
        expected_input = model.hparams.n_embd;
        expected_output = vocab_size;
    }
    if (expected_input > UINT32_MAX || expected_output > UINT32_MAX) {
        return reject("method_shape_mismatch");
    }
    const uint64_t expected_a_count = expected_input * c.rank;
    const uint64_t expected_b_count = (uint64_t) c.rank * expected_output;
    if (c.input_width != expected_input || c.output_width != expected_output ||
            c.a_count != expected_a_count || c.b_count != expected_b_count ||
            c.bias_count != expected_output) {
        return reject("method_shape_mismatch");
    }
    if (c.input_support_anchor == nullptr ||
            c.input_support_anchor_count != expected_input ||
            !std::isfinite(c.input_support_radius) || c.input_support_radius < 0.0f ||
            !std::isfinite(c.input_support_anchor_norm) ||
            c.input_support_anchor_norm < 0.0f) {
        return reject("input_support_guard_invalid");
    }
    for (size_t i = 0; i < c.input_support_anchor_count; ++i) {
        if (!std::isfinite(c.input_support_anchor[i])) {
            return reject("input_support_anchor_nonfinite");
        }
    }
    if (c.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS) {
        if (c.expected_expert_ids == nullptr ||
                c.expected_expert_ids_count != model.hparams.n_expert_used) {
            return reject("expected_expert_route_required");
        }
        std::vector<uint8_t> seen(model.hparams.n_expert, 0);
        for (size_t i = 0; i < c.expected_expert_ids_count; ++i) {
            const int32_t expert_id = c.expected_expert_ids[i];
            if (expert_id < 0 || (uint32_t) expert_id >= model.hparams.n_expert ||
                    seen[expert_id] != 0) {
                return reject("expected_expert_route_invalid");
            }
            seen[expert_id] = 1;
        }
    } else if (c.expected_expert_ids != nullptr || c.expected_expert_ids_count != 0) {
        return reject("unexpected_expert_route");
    }

    auto & sequence = graph_site_sequence_states[c.sequence_id];
    const std::string method_identity = std::to_string(c.layer) + ":" +
        std::to_string((uint32_t) c.kind) + ":" + c.method_key;
    const auto previous_method = sequence.method_generations.find(method_identity);
    if ((!sequence.source_sha256.empty() && sequence.source_sha256 != c.source_sha256) ||
            c.predecessor_generation != sequence.owner_generation ||
            c.owner_generation <= sequence.generation_floor ||
            c.owner_generation <= sequence.owner_generation ||
            (previous_method != sequence.method_generations.end() &&
             c.method_generation < previous_method->second)) {
        return reject("stale_predecessor_or_generation");
    }

    graph_site_candidate = {};
    graph_site_candidate.kind = c.kind == LLAMA_CASSI_GRAPH_SITE_EXPERTS ? llm_graph_site_candidate_kind::EXPERTS
        : c.kind == LLAMA_CASSI_GRAPH_SITE_RECURRENT ? llm_graph_site_candidate_kind::RECURRENT
        : c.kind == LLAMA_CASSI_GRAPH_SITE_ATTENTION_MEMORY ? llm_graph_site_candidate_kind::ATTENTION_MEMORY
        : llm_graph_site_candidate_kind::EXECUTION_CHOICE;
    graph_site_candidate.seq_id = c.seq_id;
    graph_site_candidate.position = c.position;
    graph_site_candidate.layer = c.layer;
    graph_site_candidate.owner_generation = c.owner_generation;
    graph_site_candidate.predecessor_generation = c.predecessor_generation;
    graph_site_candidate.sequence_id = c.sequence_id;
    graph_site_candidate.source_sha256 = c.source_sha256;
    graph_site_candidate.architecture = c.architecture;
    graph_site_candidate.backend = c.backend;
    graph_site_candidate.input_tensor = c.input_tensor;
    graph_site_candidate.output_tensor = c.output_tensor;
    graph_site_candidate.tensor_dtype = c.tensor_dtype;
    graph_site_candidate.stage = c.stage;
    graph_site_candidate.site = c.site;
    graph_site_candidate.specialist = c.specialist;
    graph_site_candidate.predecessor_sha256 = c.predecessor_sha256;
    graph_site_candidate.request_sha256 = c.request_sha256;
    graph_site_candidate.request_sha256_pending = c.request_sha256_pending;
    graph_site_candidate.invocation_sha256 = c.invocation_sha256;
    graph_site_candidate.candidate_sha256 = c.candidate_sha256;
    graph_site_candidate.intervention_order = c.intervention_order;
    graph_site_candidate.dependencies_json = c.dependencies_json;
    graph_site_candidate.method_key = c.method_key;
    graph_site_candidate.method_generation = c.method_generation;
    graph_site_candidate.input_width = c.input_width;
    graph_site_candidate.input_support_radius = c.input_support_radius;
    graph_site_candidate.input_support_anchor_norm = c.input_support_anchor_norm;
    if (c.expected_expert_ids_count != 0) {
        graph_site_candidate.expected_expert_ids.assign(
            c.expected_expert_ids,
            c.expected_expert_ids + c.expected_expert_ids_count);
    }
    graph_site_candidate.rank = c.rank;
    graph_site_candidate.output_width = c.output_width;
    graph_site_candidate.conv_history_rows = c.conv_history_rows;
    graph_site_candidate.conv_history_channels = c.conv_history_channels;
    graph_site_candidate.recurrent_state_heads = c.recurrent_state_heads;
    graph_site_candidate.recurrent_state_value_width = c.recurrent_state_value_width;
    graph_site_candidate.recurrent_state_key_width = c.recurrent_state_key_width;
    graph_site_candidate.attn_kv_heads = c.attn_kv_heads;
    graph_site_candidate.attn_kv_head_width = c.attn_kv_head_width;
    graph_site_candidate.a.resize(c.a_count);
    graph_site_candidate.b.resize(c.b_count);
    graph_site_candidate.bias.resize(c.bias_count);
    const auto canonical_to_native = [&](uint32_t canonical_index) -> uint32_t {
        if (c.kind != LLAMA_CASSI_GRAPH_SITE_RECURRENT ||
                canonical_index < (uint32_t) model.hparams.n_embd) {
            return canonical_index;
        }
        const uint64_t hidden = model.hparams.n_embd;
        const uint64_t conv_width = (uint64_t) c.conv_history_rows * c.conv_history_channels;
        if (canonical_index < hidden + conv_width) {
            const uint64_t conv_index = canonical_index - hidden;
            const uint64_t row = conv_index / c.conv_history_channels;
            const uint64_t channel = conv_index % c.conv_history_channels;
            return (uint32_t) (hidden + channel * c.conv_history_rows + row);
        }
        const uint64_t state_index = canonical_index - hidden - conv_width;
        const uint64_t value_width = c.recurrent_state_value_width;
        const uint64_t key_width = c.recurrent_state_key_width;
        const uint64_t state_head_width = value_width * key_width;
        const uint64_t head = state_index / state_head_width;
        const uint64_t value = (state_index / key_width) % value_width;
        const uint64_t key = state_index % key_width;
        const uint64_t native_state_index =
            head * state_head_width + key * value_width + value;
        return (uint32_t) (hidden + conv_width + native_state_index);
    };
    graph_site_candidate.input_support_anchor.resize(c.input_support_anchor_count);
    for (uint32_t canonical_i = 0; canonical_i < c.input_width; ++canonical_i) {
        graph_site_candidate.input_support_anchor[canonical_to_native(canonical_i)] =
            c.input_support_anchor[canonical_i];
    }
    for (uint32_t canonical_i = 0; canonical_i < c.input_width; ++canonical_i) {
        const uint32_t native_i = canonical_to_native(canonical_i);
        for (uint32_t r = 0; r < c.rank; ++r) {
            graph_site_candidate.a[(size_t) r * c.input_width + native_i] =
                c.a[(size_t) canonical_i * c.rank + r];
        }
    }
    for (uint32_t canonical_o = 0; canonical_o < c.output_width; ++canonical_o) {
        const uint32_t native_o = canonical_to_native(canonical_o);
        graph_site_candidate.bias[native_o] = c.bias[canonical_o];
        for (uint32_t r = 0; r < c.rank; ++r) {
            graph_site_candidate.b[(size_t) native_o * c.rank + r] =
                c.b[(size_t) r * c.output_width + canonical_o];
        }
    }
    const auto finite = [](const std::vector<float> & values) {
        return std::all_of(values.begin(), values.end(), [](float value) { return std::isfinite(value); });
    };
    if (!finite(graph_site_candidate.a) || !finite(graph_site_candidate.b) ||
            !finite(graph_site_candidate.bias)) {
        return reject("nonfinite_coefficients");
    }
    graph_site_candidate_result = {};
    graph_site_candidate_pending = true;
    return true;
}

void llama_context::graph_site_candidate_clear(const std::string & sequence_id, uint64_t owner_generation) {
    if (!sequence_id.empty()) {
        auto & sequence = graph_site_sequence_states[sequence_id];
        sequence.generation_floor = std::max(sequence.generation_floor, owner_generation);
    }
    const bool has_candidate = !graph_site_candidate.sequence_id.empty();
    const bool sequence_matches =
        sequence_id.empty() || graph_site_candidate.sequence_id == sequence_id;
    const bool generation_matches =
        !has_candidate || owner_generation >= graph_site_candidate.owner_generation;
    if (sequence_matches && generation_matches) {
        graph_site_candidate = {};
        graph_site_candidate_pending = false;
        graph_site_candidate_result = {};
        graph_site_candidate_result.attempted = !sequence_id.empty();
        graph_site_candidate_result.owner_generation = owner_generation;
        graph_site_candidate_result.refusal = sequence_id.empty() ? "" : "candidate_cancelled";
    }
}

const llm_graph_site_candidate_result & llama_context::graph_site_candidate_get_result() const {
    return graph_site_candidate_result;
}

bool llama_context::graph_site_candidate_set_native_successor_sha256(
        const std::string & candidate_sha256,
        const std::string & invocation_sha256,
        const std::string & native_successor_sha256) {
    if (!graph_site_valid_sha256(candidate_sha256.c_str()) ||
            !graph_site_valid_sha256(invocation_sha256.c_str()) ||
            !graph_site_valid_sha256(native_successor_sha256.c_str()) ||
            graph_site_candidate_pending || cassi_service_active ||
            !cassi_service_snapshot_valid || !cassi_service_snapshot_committed ||
            !graph_site_candidate_result.attempted || !graph_site_candidate_result.admitted ||
            !graph_site_candidate_result.native_successor_sha256.empty() ||
            graph_site_candidate_result.candidate_sha256 != candidate_sha256 ||
            graph_site_candidate_result.invocation_sha256 != invocation_sha256 ||
            graph_site_candidate.candidate_sha256 != candidate_sha256 ||
            graph_site_candidate.invocation_sha256 != invocation_sha256) {
        return false;
    }
    graph_site_candidate_result.native_successor_sha256 = native_successor_sha256;
    return true;
}

bool llama_context::graph_site_candidate_target_stage(llm_graph_type gtype) const {
    const auto & candidate = graph_site_candidate;
    if (!cassi_service_active) {
        // No apprenticeship service token: the candidate rides the ordinary
        // one-token decode graph (a default context maps to
        // LLM_GRAPH_TYPE_DEFAULT, an explicit decode context to
        // LLM_GRAPH_TYPE_DECODER; the service-only gating below would
        // otherwise make a staged candidate unreachable and it would be
        // reported as candidate_not_admitted).
        return (gtype == LLM_GRAPH_TYPE_DEFAULT || gtype == LLM_GRAPH_TYPE_DECODER) &&
            !cassi_service_batch;
    }
    if (gtype != LLM_GRAPH_TYPE_CASSI_SERVICE ||
            cassi_service_batch || cassi_service_config.n_rows != 1 ||
            cassi_service_config.layer != candidate.layer) {
        return false;
    }
    if (candidate.kind == llm_graph_site_candidate_kind::EXPERTS) {
        return cassi_service_config.kind == LLAMA_CASSI_FFN &&
            candidate.stage == "qwen-experts" && candidate.site == "qwen-experts" &&
            candidate.specialist == "expert-synthesis" &&
            candidate.input_tensor == "attn_post_norm" &&
            candidate.output_tensor == "ffn_delta";
    }
    if (candidate.kind == llm_graph_site_candidate_kind::RECURRENT) {
        return cassi_service_config.kind == LLAMA_CASSI_ATTENTION &&
            candidate.stage == "qwen-attention-route" &&
            candidate.site == "recurrent-attention" &&
            candidate.specialist == "recurrent-dynamics" &&
            candidate.input_tensor == "recurrent_features" &&
            candidate.output_tensor == "recurrent_successor";
    }
    return false;
}
void llama_context::graph_site_candidate_measure_result() {
    auto & result = graph_site_candidate_result;
    const auto & candidate = graph_site_candidate;
    const auto refuse = [&](const char * reason) {
        result.admitted = false;
        result.refusal = reason;
        result.output_sha256.clear();
        result.native_successor_sha256.clear();
        result.successor_sha256.clear();
        result.successor_state_json.clear();
        result.input_tensor = nullptr;
        result.output_tensor = nullptr;
        result.expert_ids_tensor = nullptr;
    };
    if (!result.attempted || !result.admitted || result.input_tensor == nullptr ||
            result.output_tensor == nullptr || candidate.input_width == 0 ||
            candidate.output_width == 0 || sched == nullptr) {
        refuse("graph_site_measurement_unavailable");
        return;
    }

    // graph_compute is asynchronous.  Complete it before reading any graph or
    // recurrent tensor so the receipt never hashes an in-flight or stale buffer.
    synchronize();

    const auto valid_vector_tensor = [](const ggml_tensor * tensor, uint32_t width) {
        return tensor != nullptr && width != 0 && tensor->type == GGML_TYPE_F32 &&
            tensor->buffer != nullptr && ggml_is_contiguous(tensor) &&
            tensor->ne[0] == (int64_t) width && tensor->ne[1] == 1 &&
            tensor->ne[2] == 1 && tensor->ne[3] == 1;
    };
    if (!valid_vector_tensor(result.input_tensor, candidate.input_width) ||
            !valid_vector_tensor(result.output_tensor, candidate.output_width)) {
        refuse("graph_site_tensor_layout_unsupported");
        return;
    }

    std::vector<uint8_t> input_bytes;
    std::vector<uint8_t> output_bytes;
    std::string input_digest;
    std::string output_digest;
    if (!graph_site_tensor_sha256(
                sched.get(), result.input_tensor, candidate.input_width,
                input_bytes, input_digest) ||
            !graph_site_tensor_sha256(
                sched.get(), result.output_tensor, candidate.output_width,
                output_bytes, output_digest)) {
        refuse("graph_site_tensor_readback_failed");
        return;
    }
    result.input_sha256 = input_digest;
    if (candidate.request_sha256_pending) {
        result.request_sha256 = input_digest;
        result.request_sha256_pending = true;
    } else {
        result.request_sha256 = candidate.request_sha256;
        result.request_sha256_pending = false;
    }

    // Support is evaluated against the native feature order consumed by the
    // graph.  Candidate anchors are remapped at admission from canonical C
    // order, so this comparison cannot silently label a native permutation C.
    if (candidate.input_support_anchor.size() != candidate.input_width) {
        refuse("input_support_anchor_unavailable");
        return;
    }
    double distance_squared = 0.0;
    for (uint32_t i = 0; i < candidate.input_width; ++i) {
        float observed = 0.0f;
        std::memcpy(&observed, input_bytes.data() + (size_t) i * sizeof(float), sizeof(float));
        if (!std::isfinite(observed)) {
            refuse("graph_site_input_nonfinite");
            return;
        }
        const double delta = static_cast<double>(observed) -
            static_cast<double>(candidate.input_support_anchor[i]);
        distance_squared += delta * delta;
        if (!std::isfinite(distance_squared)) {
            refuse("input_support_distance_invalid");
            return;
        }
    }
    const double distance = std::sqrt(distance_squared);
    const double support_limit = static_cast<double>(candidate.input_support_radius) +
        1.0e-5 * std::max(1.0, static_cast<double>(candidate.input_support_anchor_norm));
    if (!std::isfinite(distance) || !std::isfinite(support_limit) || distance > support_limit) {
        refuse("input_support_mismatch");
        return;
    }

    for (size_t offset = 0; offset < output_bytes.size(); offset += sizeof(float)) {
        float observed = 0.0f;
        std::memcpy(&observed, output_bytes.data() + offset, sizeof(float));
        if (!std::isfinite(observed)) {
            refuse("graph_site_output_nonfinite");
            return;
        }
    }

    if (candidate.kind == llm_graph_site_candidate_kind::EXPERTS) {
        if (result.expert_ids_tensor == nullptr ||
                result.expert_ids_tensor->ne[0] != (int64_t) candidate.expected_expert_ids.size() ||
                result.expert_ids_tensor->ne[1] != 1 || result.expert_ids_tensor->ne[2] != 1 ||
                result.expert_ids_tensor->ne[3] != 1) {
            refuse("expert_route_tensor_layout_unsupported");
            return;
        }
        std::vector<int32_t> actual_route;
        if (!graph_site_tensor_i32_values(
                    sched.get(), result.expert_ids_tensor,
                    candidate.expected_expert_ids.size(), actual_route)) {
            refuse("expert_route_readback_failed");
            return;
        }
        const bool route_matches = actual_route == candidate.expected_expert_ids;
        result.actual_expert_ids = std::move(actual_route);
        if (!route_matches) {
            refuse("expert_route_mismatch");
            return;
        }
        result.output_sha256 = output_digest;
        result.successor_state_json = graph_site_successor_state_json(
            "expert_output", output_digest,
            "[" + std::to_string(candidate.output_width) + "]");
        result.successor_sha256 = graph_site_successor_json_digest(result.successor_state_json);
        if (result.successor_sha256.empty()) {
            refuse("graph_site_successor_digest_failed");
            return;
        }
    } else if (candidate.kind == llm_graph_site_candidate_kind::RECURRENT) {
        const uint64_t hidden_width = model.hparams.n_embd;
        const uint64_t conv_rows = candidate.conv_history_rows;
        const uint64_t conv_channels = candidate.conv_history_channels;
        const uint64_t state_heads = candidate.recurrent_state_heads;
        const uint64_t value_width = candidate.recurrent_state_value_width;
        const uint64_t key_width = candidate.recurrent_state_key_width;
        const uint64_t conv_width = conv_rows * conv_channels;
        const uint64_t state_width = state_heads * value_width * key_width;
        const uint64_t total_width = hidden_width + conv_width + state_width;
        if (hidden_width == 0 || conv_rows == 0 || conv_channels == 0 || state_heads == 0 ||
                value_width == 0 || key_width == 0 || conv_width > SIZE_MAX ||
                state_width > SIZE_MAX || total_width != candidate.output_width ||
                total_width > SIZE_MAX / sizeof(float) || output_bytes.size() != total_width * sizeof(float)) {
            refuse("recurrent_successor_shape_unsupported");
            return;
        }

        // The native recurrent buffer stores convolution history as
        // [channel,row] and state as [head,key,value].  Hash each descriptor's
        // actual values in its declared logical C-order shape instead of
        // exposing that physical permutation as if it were C-order.
        const auto direct_digest = [&](size_t byte_offset, size_t byte_count,
                                       std::string & digest) {
            return byte_count != 0 && byte_offset <= output_bytes.size() &&
                byte_count <= output_bytes.size() - byte_offset &&
                graph_site_sha256_bytes(output_bytes.data() + byte_offset, byte_count, digest);
        };
        std::string hidden_digest;
        if (!direct_digest(0, (size_t) hidden_width * sizeof(float), hidden_digest)) {
            refuse("recurrent_hidden_readback_failed");
            return;
        }
        sha256_t conv_hash;
        sha256_t state_hash;
        sha256_init(&conv_hash);
        sha256_init(&state_hash);
        for (uint64_t row = 0; row < conv_rows; ++row) {
            for (uint64_t channel = 0; channel < conv_channels; ++channel) {
                const size_t native_index = (size_t) hidden_width +
                    (size_t) channel * (size_t) conv_rows + (size_t) row;
                sha256_update(&conv_hash,
                    output_bytes.data() + native_index * sizeof(float), sizeof(float));
            }
        }
        for (uint64_t head = 0; head < state_heads; ++head) {
            for (uint64_t value = 0; value < value_width; ++value) {
                for (uint64_t key = 0; key < key_width; ++key) {
                    const size_t native_index = (size_t) hidden_width + (size_t) conv_width +
                        (size_t) head * (size_t) value_width * (size_t) key_width +
                        (size_t) key * (size_t) value_width + (size_t) value;
                    sha256_update(&state_hash,
                        output_bytes.data() + native_index * sizeof(float), sizeof(float));
                }
            }
        }
        uint8_t conv_digest_bytes[SHA256_DIGEST_SIZE];
        uint8_t state_digest_bytes[SHA256_DIGEST_SIZE];
        sha256_final(&conv_hash, conv_digest_bytes);
        sha256_final(&state_hash, state_digest_bytes);
        const std::string conv_digest = graph_site_sha256_hex(conv_digest_bytes);
        const std::string state_digest = graph_site_sha256_hex(state_digest_bytes);
        result.output_sha256 = output_digest;
        const std::string conv_name = "conv_history." + std::to_string(candidate.layer);
        const std::string state_name = "recurrent_state." + std::to_string(candidate.layer);
        result.successor_state_json = graph_site_successor_map_json({
            {"hidden", graph_site_f32_descriptor_json(
                hidden_digest, "[" + std::to_string(hidden_width) + "]")},
            {conv_name, graph_site_f32_descriptor_json(
                conv_digest, "[" + std::to_string(conv_rows) + "," +
                    std::to_string(conv_channels) + "]")},
            {state_name, graph_site_f32_descriptor_json(
                state_digest, "[" + std::to_string(state_heads) + "," +
                    std::to_string(value_width) + "," + std::to_string(key_width) + "]")},
        });
        result.successor_sha256 = graph_site_successor_json_digest(result.successor_state_json);
        if (result.successor_sha256.empty()) {
            refuse("graph_site_successor_digest_failed");
            return;
        }
    } else if (candidate.kind == llm_graph_site_candidate_kind::ATTENTION_MEMORY) {
        const uint64_t hidden_width = model.hparams.n_embd;
        const uint64_t kv_heads = candidate.attn_kv_heads;
        const uint64_t kv_head_width = candidate.attn_kv_head_width;
        const uint64_t kv_width = kv_heads * kv_head_width;
        const uint64_t total_width = hidden_width + 2ULL * kv_width;
        if (hidden_width == 0 || kv_heads == 0 || kv_head_width == 0 ||
                kv_width > SIZE_MAX / sizeof(float) ||
                total_width != candidate.output_width ||
                total_width > SIZE_MAX / sizeof(float) ||
                output_bytes.size() != total_width * sizeof(float)) {
            refuse("attention_memory_successor_shape_unsupported");
            return;
        }
        // The successor vector is already flat C-order (hidden, then k row,
        // then v row, each head-major) with no native permutation to undo.
        const auto direct_digest = [&](size_t byte_offset, size_t byte_count,
                                       std::string & digest) {
            return byte_count != 0 && byte_offset <= output_bytes.size() &&
                byte_count <= output_bytes.size() - byte_offset &&
                graph_site_sha256_bytes(output_bytes.data() + byte_offset, byte_count, digest);
        };
        std::string hidden_digest;
        std::string k_digest;
        std::string v_digest;
        if (!direct_digest(0, (size_t) hidden_width * sizeof(float), hidden_digest) ||
                !direct_digest((size_t) hidden_width * sizeof(float),
                    (size_t) kv_width * sizeof(float), k_digest) ||
                !direct_digest(((size_t) hidden_width + (size_t) kv_width) * sizeof(float),
                    (size_t) kv_width * sizeof(float), v_digest)) {
            refuse("attention_memory_readback_failed");
            return;
        }
        result.output_sha256 = output_digest;
        const std::string k_name = "kv_k." + std::to_string(candidate.layer);
        const std::string v_name = "kv_v." + std::to_string(candidate.layer);
        result.successor_state_json = graph_site_successor_map_json({
            {"hidden", graph_site_f32_descriptor_json(
                hidden_digest, "[" + std::to_string(hidden_width) + "]")},
            {k_name, graph_site_f32_descriptor_json(
                k_digest, "[" + std::to_string(kv_heads) + "," +
                    std::to_string(kv_head_width) + "]")},
            {v_name, graph_site_f32_descriptor_json(
                v_digest, "[" + std::to_string(kv_heads) + "," +
                    std::to_string(kv_head_width) + "]")},
        });
        result.successor_sha256 = graph_site_successor_json_digest(result.successor_state_json);
        if (result.successor_sha256.empty()) {
            refuse("graph_site_successor_digest_failed");
            return;
        }
    } else if (candidate.kind == llm_graph_site_candidate_kind::EXECUTION_CHOICE) {
        if (candidate.output_width == 0 ||
                output_bytes.size() != (size_t) candidate.output_width * sizeof(float)) {
            refuse("execution_choice_successor_shape_unsupported");
            return;
        }
        result.output_sha256 = output_digest;
        result.successor_state_json = graph_site_successor_state_json(
            "logits", output_digest,
            "[" + std::to_string(candidate.output_width) + "]");
        result.successor_sha256 = graph_site_successor_json_digest(result.successor_state_json);
        if (result.successor_sha256.empty()) {
            refuse("graph_site_successor_digest_failed");
            return;
        }
    } else {
        refuse("graph_site_kind_unsupported");
        return;
    }
    result.input_tensor = nullptr;
    result.output_tensor = nullptr;
    result.expert_ids_tensor = nullptr;
}


llm_graph_params llama_context::graph_params(
                        llm_graph_result * res,
                      const llama_ubatch & ubatch,
            const llama_memory_context_i * mctx,
                          llm_graph_type   gtype) const {
    const llm_graph_site_candidate_config * candidate = nullptr;
    if (graph_site_candidate_pending) {
        const auto & c = graph_site_candidate;
        const bool rows_known = ubatch.n_tokens > 0 && ubatch.seq_id != nullptr &&
            ubatch.n_seq_id != nullptr && ubatch.pos != nullptr;
        // A candidate intervention is admitted only when every token row of the
        // ubatch is exactly the admitted (seq_id, position). A multi-row ubatch
        // where only some rows match would apply the substituted site to rows
        // that were never admitted - an unsupported mixed intervention, refused
        // with a dedicated receipt so per-row receipts stay intact.
        bool candidate_row_found = false;
        bool rows_all_match = rows_known;
        for (uint32_t i = 0; rows_known && i < ubatch.n_tokens; ++i) {
            const bool row_match = ubatch.n_seq_id[i] == 1 && ubatch.seq_id[i] != nullptr &&
                ubatch.seq_id[i][0] == c.seq_id && ubatch.pos[i] == c.position;
            candidate_row_found = candidate_row_found || row_match;
            rows_all_match = rows_all_match && row_match;
        }
        const bool token_matches = rows_all_match &&
            ubatch.n_tokens == 1 && ubatch.n_seqs_unq == 1;
        if (graph_site_candidate_target_stage(gtype)) {
            const bool model_matches =
                (model.arch == LLM_ARCH_QWEN35MOE || model.arch == LLM_ARCH_QWEN35) &&
                c.architecture == llm_arch_name(model.arch) &&
                c.method_key == "cassifi.graph-site-low-rank-affine.v1" &&
                c.tensor_dtype == "f32" &&
                (c.kind == llm_graph_site_candidate_kind::EXECUTION_CHOICE
                    ? c.layer == -1
                    : (c.layer >= 0 && c.layer < (int32_t) model.hparams.n_layer()));
            bool site_matches = false;
            if (model_matches && c.kind == llm_graph_site_candidate_kind::EXPERTS) {
                const auto & layer = model.layers[c.layer];
                const bool has_expert_weights = layer.ffn_gate_inp != nullptr &&
                    layer.ffn_down_exps != nullptr &&
                    (layer.ffn_gate_up_exps != nullptr ||
                     (layer.ffn_up_exps != nullptr && layer.ffn_gate_exps != nullptr));
                site_matches = c.input_width == model.hparams.n_embd &&
                    c.output_width == model.hparams.n_embd && has_expert_weights;
            } else if (model_matches && c.kind == llm_graph_site_candidate_kind::RECURRENT) {
                const bool recurrent_state_available = mctx != nullptr &&
                    cparams.n_rs_seq == 0 && model.hparams.is_recr(c.layer);
                site_matches = recurrent_state_available;
            } else if (model_matches && c.kind == llm_graph_site_candidate_kind::ATTENTION_MEMORY) {
                const auto & layer = model.layers[c.layer];
                const uint32_t kv_heads = model.hparams.n_head_kv(c.layer);
                const uint32_t kv_head_width = model.hparams.n_embd_head_v(c.layer);
                site_matches = layer.wo != nullptr && !model.hparams.is_recr(c.layer) &&
                    kv_heads != 0 && kv_head_width != 0 &&
                    kv_head_width == model.hparams.n_embd_head_k(c.layer) &&
                    c.attn_kv_heads == kv_heads && c.attn_kv_head_width == kv_head_width &&
                    c.input_width == model.hparams.n_embd &&
                    c.output_width == model.hparams.n_embd + 2u * kv_heads * kv_head_width;
            } else if (model_matches && c.kind == llm_graph_site_candidate_kind::EXECUTION_CHOICE) {
                site_matches = c.input_width == model.hparams.n_embd &&
                    c.output_width == (uint32_t) model.vocab.n_tokens();
            }
            if (token_matches && site_matches) {
                candidate = &graph_site_candidate;
            } else {
                graph_site_candidate_result = {};
                graph_site_candidate_bind_identity(c, graph_site_candidate_result);
                graph_site_candidate_result.attempted = true;
                graph_site_candidate_result.admitted = false;
                graph_site_candidate_result.refusal = !token_matches
                    ? (candidate_row_found && rows_known
                        ? "multirow_candidate_unsupported"
                        : "sequence_or_position_mismatch")
                    : !model_matches ? "model_or_layer_mismatch"
                    : "graph_site_unsupported";
            }
        }
    }
    return {
        /*.arch        =*/ model.arch,
        /*.hparams     =*/ model.hparams,
        /*.cparams     =*/ cparams,
        /*.ubatch      =*/ ubatch,
        /*.gtype       =*/ gtype,
        /*.sched       =*/ sched.get(),
        /*.backend_cpu =*/ backend_cpu,
        /*.cvec        =*/ cvec.get(),
        /*.loras       =*/ loras.get(),
        /*.mctx        =*/ mctx,
        /*.cross       =*/ &cross,
        /*.cassi       =*/ &cassi_modal,
        /*.cassi_field =*/ &cassi_field,
        /*.cassi_qi    =*/ &cassi_qi,
        /*.cassi_service =*/ gtype == LLM_GRAPH_TYPE_CASSI_SERVICE ? &cassi_service_config : nullptr,
        /*.cassi_graph_site_candidate =*/ candidate,
        /*.samplers    =*/ sampling.samplers,
        /*.n_outputs   =*/ n_outputs,
        /*.cb          =*/ graph_get_cb(),
        /*.res         =*/ res,
    };

}

ggml_status llama_context::graph_compute(
            ggml_cgraph * gf,
                   bool   batched) {
    int n_threads        = batched ? cparams.n_threads_batch : cparams.n_threads;
    ggml_threadpool_t tp = batched ? threadpool_batch        : threadpool;

    if (backend_cpu != nullptr) {
        auto * reg = ggml_backend_dev_backend_reg(ggml_backend_get_device(backend_cpu));
        auto * set_threadpool_fn = (decltype(ggml_backend_cpu_set_threadpool) *) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_set_threadpool");
        if (set_threadpool_fn) {
            set_threadpool_fn(backend_cpu, tp);
        }
    }

    // set the number of threads for all the backends
    for (const auto & set_n_threads_fn : set_n_threads_fns) {
        set_n_threads_fn.second(set_n_threads_fn.first, n_threads);
    }

    auto status = ggml_backend_sched_graph_compute_async(sched.get(), gf);
    if (status != GGML_STATUS_SUCCESS) {
        LLAMA_LOG_ERROR("%s: ggml_backend_sched_graph_compute_async failed with error %d\n", __func__, status);
    }

    // fprintf(stderr, "splits: %d\n", ggml_backend_sched_get_n_splits(sched));

    return status;
}

llm_graph_cb llama_context::graph_get_cb() const {
    return [&](const llama_ubatch & ubatch, ggml_tensor * cur, const char * name, int il) {
        if (il >= 0) {
            ggml_format_name(cur, "%s-%d", name, il);
        } else {
            ggml_set_name(cur, name);
        }

        // - norm may be automatically assigned to the backend of the previous layer, increasing data transfer between backends
        // - force the last op of the layer on the specified backend to avoid running it on the backend of the next layer due to scheduling
        // FIXME: fix in ggml_backend_sched
        const bool full_offload = model.n_gpu_layers() > model.hparams.n_layer_all;
        if (ubatch.n_tokens < 32 || full_offload) {
            if (il != -1 && (strcmp(name, "norm") == 0 || strcmp(name, "l_last") == 0)) {
                const auto & dev_layer = model.dev_layer(il);
                for (const auto & backend : backends) {
                    if (ggml_backend_get_device(backend.get()) == dev_layer) {
                        if (ggml_backend_supports_op(backend.get(), cur)) {
                            ggml_backend_sched_set_tensor_backend(sched.get(), cur, backend.get());
                        }
                    }
                }
            }
        }
    };
}

//
// state save/load
//

class llama_io_write_dummy : public llama_io_write_i {
public:
    llama_io_write_dummy(bool skip_tensors) : skip_tensors(skip_tensors) {}

    void write(const void * /* src */, size_t size) override {
        size_written += size;
    }

    void write_tensor(ggml_tensor * /* tensor */, size_t /* offset */, size_t size) override {
        if (skip_tensors) {
            return;
        }

        size_written += size;
    }

    size_t n_bytes() override {
        return size_written;
    }

private:
    const bool skip_tensors;

    size_t size_written = 0;
};

class llama_io_write_host : public llama_io_write_i {
public:
    llama_io_write_host(
            uint8_t * p, size_t len) : ptr(p), buf_size(len) {}

    ~llama_io_write_host() {
        // TODO: add backend support to batch tensor_get? or some other way to speed this up
        for (const auto & winfo : winfos) {
            ggml_backend_tensor_get(winfo.tensor, winfo.ptr, winfo.offset, winfo.size);
        }
    }

    void write(const void * src, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }
        memcpy(ptr, src, size);
        ptr += size;
        size_written += size;
        buf_size -= size;
    }

    void write_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }

        // save the write for later during destruction
        winfos.push_back({tensor, ptr, size, offset});

        ptr += size;
        size_written += size;
        buf_size -= size;
    }

    size_t n_bytes() override {
        return size_written;
    }

private:
    uint8_t * ptr;
    size_t buf_size = 0;
    size_t size_written = 0;

    struct write_info {
        ggml_tensor * tensor;
        uint8_t * ptr;
        size_t size;
        size_t offset;
    };
    std::vector<write_info> winfos;
};

class llama_io_read_host : public llama_io_read_i {
public:
    llama_io_read_host(const uint8_t * p, size_t len) : ptr(p), buf_size(len) {}

    ~llama_io_read_host() {
        // flush the reads
        for (const auto & rinfo : rinfos) {
            ggml_backend_tensor_set(rinfo.tensor, rinfo.ptr, rinfo.offset, rinfo.size);
        }
    }

    void read(void * dst, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }
        memcpy(dst, ptr, size);
        ptr += size;
        size_read += size;
        buf_size -= size;
    }

    void read_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }

        // save for later during destruction
        rinfos.push_back({tensor, ptr, size, offset});

        ptr += size;
        size_read += size;
        buf_size -= size;
    }

    size_t n_bytes() override {
        return size_read;
    }

private:
    const uint8_t * ptr;
    size_t buf_size = 0;
    size_t size_read = 0;

    struct read_info {
        ggml_tensor * tensor;
        const uint8_t * ptr;
        size_t size;
        size_t offset;
    };
    std::vector<read_info> rinfos;
};

class llama_io_write_file : public llama_io_write_i {
public:
    llama_io_write_file(llama_file * f) : file(f) {}

    void write(const void * src, size_t size) override {
        file->write_raw(src, size);
        size_written += size;
    }

    void write_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        temp_buffer.resize(size);
        ggml_backend_tensor_get(tensor, temp_buffer.data(), offset, size);
        write(temp_buffer.data(), temp_buffer.size());
    }

    size_t n_bytes() override {
        return size_written;
    }

private:
    llama_file * file;
    size_t size_written = 0;
    std::vector<uint8_t> temp_buffer;
};

class llama_io_read_file : public llama_io_read_i {
public:
    llama_io_read_file(llama_file * f) : file(f) {}

    void read(void * dst, size_t size) override {
        file->read_raw(dst, size);
        size_read += size;
    }

    void read_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        temp_buffer.resize(size);
        read(temp_buffer.data(), size);
        ggml_backend_tensor_set(tensor, temp_buffer.data(), offset, size);
    }

    size_t n_bytes() override {
        return size_read;
    }

private:
    llama_file * file;
    size_t size_read = 0;
    std::vector<uint8_t> temp_buffer;
};

class llama_io_write_device : public llama_io_write_i {
public:
    llama_io_write_device(uint8_t * p, size_t len, llama_memory_buffers & mbufs) : ptr(p), buf_size(len), mbufs(mbufs)  {
    }

    ~llama_io_write_device() {
        llama_memory_buffers mbufs_new;

        for (const auto & winfo : winfos) {
            auto * buft = ggml_backend_buffer_get_type(winfo.tensor->buffer);

            mbufs_new[buft].n_tensors++;
            mbufs_new[buft].total_size += winfo.size;
        }

        for (auto & [buft, mbuf] : mbufs_new) {
            ggml_init_params params = {
                /*.mem_size   =*/ 2*mbuf.n_tensors*ggml_tensor_overhead(),
                /*.mem_buffer =*/ NULL,
                /*.no_alloc   =*/ true,
            };

            mbuf.ctx.reset(ggml_init(params));

            mbuf.org.reserve(mbuf.n_tensors);
            mbuf.cpy.reserve(mbuf.n_tensors);
        }

        for (const auto & winfo : winfos) {
            auto * buft = ggml_backend_buffer_get_type(winfo.tensor->buffer);

            const int64_t n = winfo.size/ggml_element_size(winfo.tensor);

            auto & mbuf = mbufs_new[buft];

            mbuf.org.push_back(ggml_view_1d      (mbuf.ctx.get(), winfo.tensor, n, winfo.offset));
            mbuf.cpy.push_back(ggml_new_tensor_1d(mbuf.ctx.get(), winfo.tensor->type, n));
        }

        for (auto & [buft, mbuf] : mbufs_new) {
            auto & mbuf_cur = mbufs[buft];

            bool need_alloc = false;

            need_alloc = need_alloc || (!mbuf_cur.buf);
            need_alloc = need_alloc || (mbuf_cur.org.size() != mbuf.org.size());
            need_alloc = need_alloc || (mbuf_cur.total_size != mbuf.total_size);

            if (!need_alloc) {
                for (size_t i = 0; i < mbuf_cur.org.size(); ++i) {
                    auto * org0 = mbuf_cur.org[i];
                    auto * org1 = mbuf.org[i];

                    if (!ggml_are_same_shape(org0, org1)) {
                        need_alloc = true;
                        break;
                    }

                    if (org0->view_src != org1->view_src || org0->view_offs != org1->view_offs) {
                        need_alloc = true;
                        break;
                    }
                }
            }

            if (need_alloc) {
                if (!mbuf_cur.buf || mbuf_cur.total_size != mbuf.total_size) {
                    mbuf_cur = std::move(mbuf);

                    mbuf_cur.buf.reset(ggml_backend_alloc_ctx_tensors_from_buft(mbuf_cur.ctx.get(), buft));

                    LLAMA_LOG_INFO("%s: allocated '%s' buffer %.3f MiB\n", __func__, ggml_backend_buft_name(buft), mbuf.total_size/1024.0/1024.0);
                } else {
                    //LLAMA_LOG_INFO("%s: reallocating tensors in '%s' buffer %.3f MiB\n", __func__, ggml_backend_buft_name(buft), mbuf.total_size/1024.0/1024.0);

                    // save the old buffer and allocate the new tensors in it
                    auto buf = std::move(mbuf_cur.buf);

                    mbuf_cur = std::move(mbuf);

                    ggml_tallocr talloc = ggml_tallocr_new(buf.get());

                    for (size_t i = 0; i < mbuf_cur.org.size(); ++i) {
                        ggml_backend_view_init(mbuf_cur.org[i]);
                        ggml_tallocr_alloc(&talloc, mbuf_cur.cpy[i]);
                    }

                    mbuf_cur.buf = std::move(buf);
                }
            }

            for (size_t i = 0; i < mbuf_cur.org.size(); ++i) {
                ggml_backend_tensor_copy(mbuf_cur.org[i], mbuf_cur.cpy[i]);
            }
        }
    }

    void write(const void * src, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }
        memcpy(ptr, src, size);
        ptr += size;
        size_written += size;
        buf_size -= size;
    }

    void write_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        // save the write for later during destruction
        winfos.push_back({tensor, ptr, size, offset});
    }

    size_t n_bytes() override {
        return size_written;
    }

private:
    uint8_t * ptr;
    size_t buf_size = 0;
    size_t size_written = 0;

    struct write_info {
        ggml_tensor * tensor;
        uint8_t * ptr;
        size_t size;
        size_t offset;
    };
    std::vector<write_info> winfos;

    llama_memory_buffers & mbufs;
};

class llama_io_read_device : public llama_io_read_i {
public:
    llama_io_read_device(const uint8_t * p, size_t len, const llama_memory_buffers & mbufs) : ptr(p), buf_size(len), mbufs(mbufs) {
    }

    ~llama_io_read_device() {
        llama_memory_buffers mbufs_new;

        for (const auto & rinfo : rinfos) {
            auto * buft = ggml_backend_buffer_get_type(rinfo.tensor->buffer);

            mbufs_new[buft].n_tensors++;
            mbufs_new[buft].total_size += rinfo.size;
        }

        for (auto & [buft, mbuf] : mbufs_new) {
            ggml_init_params params = {
                /*.mem_size   =*/ mbuf.n_tensors*ggml_tensor_overhead(),
                /*.mem_buffer =*/ NULL,
                /*.no_alloc   =*/ true,
            };

            mbuf.ctx.reset(ggml_init(params));

            mbuf.org.reserve(mbuf.n_tensors);
        }

        for (const auto & rinfo : rinfos) {
            auto * buft = ggml_backend_buffer_get_type(rinfo.tensor->buffer);

            const int64_t n = rinfo.size/ggml_element_size(rinfo.tensor);

            auto & mbuf = mbufs_new[buft];

            mbuf.org.push_back(ggml_view_1d(mbuf.ctx.get(), rinfo.tensor, n, rinfo.offset));

            ggml_backend_view_init(mbuf.org.back());
        }

        for (auto & [buft, mbuf] : mbufs_new) {
            const auto & mbuf_cur = mbufs.at(buft);

            if (!mbuf_cur.buf || mbuf_cur.n_tensors != mbuf.n_tensors || mbuf_cur.total_size != mbuf.total_size) {
                GGML_ABORT("%s: memory buffer mismatch\n", __func__);
            }

            for (size_t i = 0; i < mbuf_cur.org.size(); ++i) {
                ggml_backend_tensor_copy(mbuf_cur.cpy[i], mbuf.org[i]);
            }
        }

        GGML_ASSERT(buf_size == 0);
    }

    void read(void * dst, size_t size) override {
        if (size > buf_size) {
            throw std::runtime_error("unexpectedly reached end of buffer");
        }
        memcpy(dst, ptr, size);
        ptr += size;
        size_read += size;
        buf_size -= size;
    }

    void read_tensor(ggml_tensor * tensor, size_t offset, size_t size) override {
        // save for later during destruction
        rinfos.push_back({tensor, ptr, size, offset});
    }

    size_t n_bytes() override {
        return size_read;
    }

private:
    const uint8_t * ptr;
    size_t buf_size = 0;
    size_t size_read = 0;

    struct read_info {
        ggml_tensor * tensor;
        const uint8_t * ptr;
        size_t size;
        size_t offset;
    };
    std::vector<read_info> rinfos;

    const llama_memory_buffers & mbufs;
};

size_t llama_context::state_get_size() {
    synchronize();
    llama_io_write_dummy io(false);
    try {
        return state_write_data(io);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error getting state size: %s\n", __func__, err.what());
        return 0;
    }
}

size_t llama_context::state_get_data(uint8_t * dst, size_t size) {
    synchronize();
    llama_io_write_host io(dst, size);
    try {
        return state_write_data(io);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error saving state: %s\n", __func__, err.what());
        return 0;
    }
}

size_t llama_context::state_set_data(const uint8_t * src, size_t size) {
    synchronize();
    llama_io_read_host io(src, size);
    try {
        return state_read_data(io);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error loading state: %s\n", __func__, err.what());
        return 0;
    }
}

static constexpr uint32_t io_magic = 0xaf143cd8;
static constexpr uint32_t cassi_modal_state_magic = 0x434d4f44; // "CMOD"
static constexpr uint32_t cassi_modal_state_version = 1;
static constexpr uint32_t cassi_field_state_magic = 0x43464945; // "CFIE"
static constexpr uint32_t cassi_field_state_version = 1;
static constexpr uint32_t cassi_qi_state_magic = 0x43514946; // "CQIF"
static constexpr uint32_t cassi_qi_state_version = 3; // header carries the readout scale taper

static void cassi_modal_write_header(
        llama_io_write_i & io,
        const llm_cassi_modal_config & config,
        uint32_t sequence_count) {
    const uint32_t magic = cassi_modal_state_magic;
    const uint32_t version = cassi_modal_state_version;
    io.write(&magic, sizeof(magic));
    io.write(&version, sizeof(version));
    io.write(&config.mode_count, sizeof(config.mode_count));
    io.write(&config.layer_count, sizeof(config.layer_count));
    io.write(&config.steps_per_layer, sizeof(config.steps_per_layer));
    io.write(&config.state_stride, sizeof(config.state_stride));
    io.write(&config.retained_weight, sizeof(config.retained_weight));
    io.write(&config.phi, sizeof(config.phi));
    io.write(&config.dt, sizeof(config.dt));
    io.write(&config.omega2, sizeof(config.omega2));
    io.write(&config.coupling, sizeof(config.coupling));
    io.write(&sequence_count, sizeof(sequence_count));
}
static void cassi_modal_read_header(
        llama_io_read_i & io,
        const llm_cassi_modal_config & config,
        uint32_t expected_sequence_count) {
    uint32_t magic = 0;
    uint32_t version = 0;
    uint32_t mode_count = 0;
    uint32_t layer_count = 0;
    uint32_t steps_per_layer = 0;
    uint32_t state_stride = 0;
    float retained_weight = 0.0f;
    float phi = 0.0f;
    float dt = 0.0f;
    float omega2 = 0.0f;
    float coupling = 0.0f;
    uint32_t sequence_count = 0;

    io.read(&magic, sizeof(magic));
    io.read(&version, sizeof(version));
    io.read(&mode_count, sizeof(mode_count));
    io.read(&layer_count, sizeof(layer_count));
    io.read(&steps_per_layer, sizeof(steps_per_layer));
    io.read(&state_stride, sizeof(state_stride));
    io.read(&retained_weight, sizeof(retained_weight));
    io.read(&phi, sizeof(phi));
    io.read(&dt, sizeof(dt));
    io.read(&omega2, sizeof(omega2));
    io.read(&coupling, sizeof(coupling));
    io.read(&sequence_count, sizeof(sequence_count));

    if (magic != cassi_modal_state_magic || version != cassi_modal_state_version ||
            mode_count != config.mode_count || layer_count != config.layer_count ||
            steps_per_layer != config.steps_per_layer || state_stride != config.state_stride ||
            sequence_count != expected_sequence_count ||
            retained_weight != config.retained_weight || phi != config.phi ||
            dt != config.dt || omega2 != config.omega2 || coupling != config.coupling ||
            !std::isfinite(retained_weight) || !std::isfinite(phi) ||
            !std::isfinite(dt) || !std::isfinite(omega2) || !std::isfinite(coupling)) {
        throw std::runtime_error("invalid Cassi modal state header");
    }
}
static void cassi_field_write_header(
        llama_io_write_i & io,
        const llm_cassi_field_config & config,
        uint32_t sequence_count) {
    const uint32_t magic = cassi_field_state_magic;
    const uint32_t version = cassi_field_state_version;
    io.write(&magic, sizeof(magic));
    io.write(&version, sizeof(version));
    io.write(&config.mode_count, sizeof(config.mode_count));
    io.write(&config.state_stride, sizeof(config.state_stride));
    io.write(&config.layer_index, sizeof(config.layer_index));
    io.write(&config.retained_weight, sizeof(config.retained_weight));
    io.write(&config.phi, sizeof(config.phi));
    io.write(&config.dt, sizeof(config.dt));
    io.write(&config.omega2, sizeof(config.omega2));
    io.write(&config.coupling, sizeof(config.coupling));
    io.write(&sequence_count, sizeof(sequence_count));
}

static void cassi_field_read_header(
        llama_io_read_i & io,
        const llm_cassi_field_config & config,
        uint32_t expected_sequence_count) {
    uint32_t magic = 0;
    uint32_t version = 0;
    uint32_t mode_count = 0;
    uint32_t state_stride = 0;
    uint32_t layer_index = 0;
    float retained_weight = 0.0f;
    float phi = 0.0f;
    float dt = 0.0f;
    float omega2 = 0.0f;
    float coupling = 0.0f;
    uint32_t sequence_count = 0;
    io.read(&magic, sizeof(magic));
    io.read(&version, sizeof(version));
    io.read(&mode_count, sizeof(mode_count));
    io.read(&state_stride, sizeof(state_stride));
    io.read(&layer_index, sizeof(layer_index));
    io.read(&retained_weight, sizeof(retained_weight));
    io.read(&phi, sizeof(phi));
    io.read(&dt, sizeof(dt));
    io.read(&omega2, sizeof(omega2));
    io.read(&coupling, sizeof(coupling));
    io.read(&sequence_count, sizeof(sequence_count));
    if (magic != cassi_field_state_magic || version != cassi_field_state_version ||
            mode_count != config.mode_count || state_stride != config.state_stride ||
            layer_index != config.layer_index || sequence_count != expected_sequence_count ||
            retained_weight != config.retained_weight || phi != config.phi ||
            dt != config.dt || omega2 != config.omega2 || coupling != config.coupling ||
            !std::isfinite(retained_weight) || !std::isfinite(phi) ||
            !std::isfinite(dt) || !std::isfinite(omega2) || !std::isfinite(coupling)) {
        throw std::runtime_error("invalid Cassi field-step state header");
    }
}

static void cassi_qi_write_header(
        llama_io_write_i & io,
        const llm_cassi_qi_field_config & config,
        uint32_t sequence_count) {
    const uint32_t magic = cassi_qi_state_magic;
    const uint32_t version = cassi_qi_state_version;
    io.write(&magic, sizeof(magic));
    io.write(&version, sizeof(version));
    io.write(&config.n_embd, sizeof(config.n_embd));
    io.write(&config.mode_count, sizeof(config.mode_count));
    io.write(&config.scale_count, sizeof(config.scale_count));
    io.write(&config.layer_index, sizeof(config.layer_index));
    io.write(&config.profile_id, sizeof(config.profile_id));
    io.write(&config.state_stride, sizeof(config.state_stride));
    io.write(&config.steps, sizeof(config.steps));
    io.write(&config.phi, sizeof(config.phi));
    io.write(&config.dt, sizeof(config.dt));
    io.write(&config.coupling, sizeof(config.coupling));
    io.write(&config.damping_min, sizeof(config.damping_min));
    io.write(&config.damping_max, sizeof(config.damping_max));
    io.write(&config.epsilon_tau, sizeof(config.epsilon_tau));
    io.write(&config.scale_ratio, sizeof(config.scale_ratio));
    io.write(&config.energy_floor, sizeof(config.energy_floor));
    io.write(&config.read_floor, sizeof(config.read_floor));
    io.write(&config.scale_read_taper, sizeof(config.scale_read_taper));
    const uint32_t read_absolute = config.read_absolute ? 1u : 0u;
    io.write(&read_absolute, sizeof(read_absolute));
    io.write(&sequence_count, sizeof(sequence_count));
}

static uint32_t cassi_qi_read_header(
        llama_io_read_i & io,
        const llm_cassi_qi_field_config & config,
        uint32_t maximum_sequence_count) {
    uint32_t magic = 0, version = 0, n_embd = 0, mode_count = 0, scale_count = 0;
    uint32_t layer_index = 0, profile_id = 0, state_stride = 0, steps = 0, sequence_count = 0;
    uint32_t read_absolute = 0;
    float phi = 0.0f, dt = 0.0f, coupling = 0.0f, damping_min = 0.0f, damping_max = 0.0f;
    float epsilon_tau = 0.0f, scale_ratio = 0.0f, energy_floor = 0.0f, read_floor = 0.0f;
    float scale_read_taper = 0.0f;
    io.read(&magic, sizeof(magic)); io.read(&version, sizeof(version));
    io.read(&n_embd, sizeof(n_embd)); io.read(&mode_count, sizeof(mode_count));
    io.read(&scale_count, sizeof(scale_count)); io.read(&layer_index, sizeof(layer_index));
    io.read(&profile_id, sizeof(profile_id)); io.read(&state_stride, sizeof(state_stride));
    io.read(&steps, sizeof(steps)); io.read(&phi, sizeof(phi)); io.read(&dt, sizeof(dt));
    io.read(&coupling, sizeof(coupling)); io.read(&damping_min, sizeof(damping_min));
    io.read(&damping_max, sizeof(damping_max)); io.read(&epsilon_tau, sizeof(epsilon_tau));
    io.read(&scale_ratio, sizeof(scale_ratio)); io.read(&energy_floor, sizeof(energy_floor));
    io.read(&read_floor, sizeof(read_floor));
    io.read(&scale_read_taper, sizeof(scale_read_taper));
    io.read(&read_absolute, sizeof(read_absolute));
    io.read(&sequence_count, sizeof(sequence_count));
    if (magic != cassi_qi_state_magic || version != cassi_qi_state_version ||
            n_embd != config.n_embd || mode_count != config.mode_count ||
            scale_count != config.scale_count || layer_index != config.layer_index ||
            profile_id != config.profile_id || state_stride != config.state_stride ||
            steps != config.steps || sequence_count == 0 || sequence_count > maximum_sequence_count ||
            phi != config.phi || dt != config.dt || coupling != config.coupling ||
            damping_min != config.damping_min || damping_max != config.damping_max ||
            epsilon_tau != config.epsilon_tau || scale_ratio != config.scale_ratio ||
            energy_floor != config.energy_floor || read_floor != config.read_floor ||
            scale_read_taper != config.scale_read_taper ||
            read_absolute != (config.read_absolute ? 1u : 0u) ||
            !std::isfinite(phi) || !std::isfinite(dt) || !std::isfinite(coupling) ||
            !std::isfinite(epsilon_tau) || !std::isfinite(scale_ratio) ||
            !std::isfinite(energy_floor) || !std::isfinite(read_floor) ||
            !std::isfinite(scale_read_taper)) {
        throw std::runtime_error("invalid Cassi Qi field state header");
    }
    return sequence_count;
}

size_t llama_context::state_seq_get_size(llama_seq_id seq_id, llama_state_seq_flags flags) {
    synchronize();
    llama_io_write_dummy io(flags & LLAMA_STATE_SEQ_FLAGS_ON_DEVICE);
    try {
        io.write(&io_magic, sizeof(io_magic));
        io.write(&seq_id, sizeof(seq_id));

        return state_seq_write_data(io, seq_id, flags);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error getting state size: %s\n", __func__, err.what());
        return 0;
    }
}

size_t llama_context::state_seq_get_data(llama_seq_id seq_id, uint8_t * dst, size_t size, llama_state_seq_flags flags) {
    std::unique_ptr<llama_io_write_i> io;
    synchronize();
    if (flags & LLAMA_STATE_SEQ_FLAGS_ON_DEVICE) {
        io = std::make_unique<llama_io_write_device>(dst, size, mem_storage[seq_id]);
    } else {
        io = std::make_unique<llama_io_write_host>(dst, size);
    }

    try {
        io->write(&io_magic, sizeof(io_magic));
        io->write(&seq_id, sizeof(seq_id));

        return state_seq_write_data(*io, seq_id, flags);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error saving state: %s\n", __func__, err.what());
        return 0;
    }
}

size_t llama_context::state_seq_set_data(llama_seq_id seq_id, const uint8_t * src, size_t size, llama_state_seq_flags flags) {
    std::unique_ptr<llama_io_read_i> io;
    synchronize();
    if (flags & LLAMA_STATE_SEQ_FLAGS_ON_DEVICE) {
        // create a temporary io to read the magic and the src seq_id
        io = std::make_unique<llama_io_read_host>(src, size);

        uint32_t magic_read;
        io->read(&magic_read, sizeof(magic_read));
        if (io_magic != magic_read) {
            throw std::runtime_error("wrong sequence state magic");
        }

        llama_seq_id seq_id_read;
        io->read(&seq_id_read, sizeof(seq_id_read));
        if (seq_id_read < 0) {
            throw std::runtime_error("invalid source sequence state id");
        }

        GGML_ASSERT(mem_storage.find(seq_id_read) != mem_storage.end());

        io = std::make_unique<llama_io_read_device>(src, size, mem_storage[seq_id_read]);
    } else {
        io = std::make_unique<llama_io_read_host>(src, size);
    }

    try {
        uint32_t magic_read;
        io->read(&magic_read, sizeof(magic_read));
        if (io_magic != magic_read) {
            throw std::runtime_error("wrong sequence state magic");
        }

        llama_seq_id seq_id_read;
        io->read(&seq_id_read, sizeof(seq_id_read));
        if (seq_id_read < 0) {
            throw std::runtime_error("invalid source sequence state id");
        }

        return state_seq_read_data(*io, seq_id, flags);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error loading state: %s\n", __func__, err.what());
        return 0;
    }
}

bool llama_context::state_load_file(const char * filepath, llama_token * tokens_out, size_t n_token_capacity, size_t * n_token_count_out) {
    llama_file file(filepath, "rb");

    // sanity checks
    {
        const uint32_t magic   = file.read_u32();
        const uint32_t version = file.read_u32();

        if (magic != LLAMA_SESSION_MAGIC || version != LLAMA_SESSION_VERSION) {
            LLAMA_LOG_ERROR("%s: unknown (magic, version) for session file: %08x, %08x\n", __func__, magic, version);
            return false;
        }
    }

    // load the prompt
    {
        const uint32_t n_token_count = file.read_u32();

        if (n_token_count > n_token_capacity) {
            LLAMA_LOG_ERROR("%s: token count in session file exceeded capacity! %u > %zu\n", __func__, n_token_count, n_token_capacity);
            return false;
        }

        file.read_raw(tokens_out, sizeof(llama_token) * n_token_count);
        *n_token_count_out = n_token_count;
    }

    // restore the context state
    {
        const size_t n_state_size_cur = file.size() - file.tell();

        llama_io_read_file io( &file);
        const size_t n_read = state_read_data(io);

        if (n_read != n_state_size_cur) {
            LLAMA_LOG_ERROR("%s: did not read all of the session file data! size %zu, got %zu\n", __func__, n_state_size_cur, n_read);
            return false;
        }
    }

    return true;
}

bool llama_context::state_save_file(const char * filepath, const llama_token * tokens, size_t n_token_count) {
    llama_file file(filepath, "wb");

    file.write_u32(LLAMA_SESSION_MAGIC);
    file.write_u32(LLAMA_SESSION_VERSION);

    // save the prompt
    file.write_u32((uint32_t) n_token_count);
    file.write_raw(tokens, sizeof(llama_token) * n_token_count);

    // save the context state using stream saving
    llama_io_write_file io(&file);
    state_write_data(io);

    return true;
}

size_t llama_context::state_seq_load_file(llama_seq_id seq_id, const char * filepath, llama_token * tokens_out, size_t n_token_capacity, size_t * n_token_count_out) {
    llama_file file(filepath, "rb");

    // version checks
    {
        const uint32_t magic   = file.read_u32();
        const uint32_t version = file.read_u32();

        if (magic != LLAMA_STATE_SEQ_MAGIC || version != LLAMA_STATE_SEQ_VERSION) {
            LLAMA_LOG_ERROR("%s: unknown (magic, version) for sequence state file: %08x, %08x\n", __func__, magic, version);
            return 0;
        }
    }

    // load the prompt
    {
        const uint32_t n_token_count = file.read_u32();

        if (tokens_out == nullptr) {
            const size_t n_token_max = (file.size() - file.tell()) / sizeof(llama_token);
            if (n_token_count > n_token_max) {
                LLAMA_LOG_ERROR("%s: token count in sequence state file exceeds the file size! %u > %zu\n", __func__, n_token_count, n_token_max);
                return 0;
            }

            *n_token_count_out = n_token_count;
            return file.tell();
        }

        if (n_token_count > n_token_capacity) {
            LLAMA_LOG_ERROR("%s: token count in sequence state file exceeded capacity! %u > %zu\n", __func__, n_token_count, n_token_capacity);
            return 0;
        }

        file.read_raw(tokens_out, sizeof(llama_token) * n_token_count);
        *n_token_count_out = n_token_count;
    }

    // restore the context state
    {
        const size_t state_size = file.size() - file.tell();
        llama_io_read_file io(&file);
        const size_t nread = state_seq_read_data(io, seq_id, 0);
        if (!nread) {
            LLAMA_LOG_ERROR("%s: failed to restore sequence state\n", __func__);
            return 0;
        }
        GGML_ASSERT(nread <= state_size);
        GGML_ASSERT(nread + sizeof(uint32_t) * 3 + sizeof(llama_token) * *n_token_count_out == file.tell());
    }

    return file.tell();
}

size_t llama_context::state_seq_save_file(llama_seq_id seq_id, const char * filepath, const llama_token * tokens, size_t n_token_count) {
    llama_file file(filepath, "wb");

    file.write_u32(LLAMA_STATE_SEQ_MAGIC);
    file.write_u32(LLAMA_STATE_SEQ_VERSION);

    // save the prompt
    file.write_u32((uint32_t) n_token_count);
    file.write_raw(tokens, sizeof(llama_token) * n_token_count);

    // save the context state using stream saving
    llama_io_write_file io(&file);
    state_seq_write_data(io, seq_id, 0);

    const size_t res = file.tell();
    GGML_ASSERT(res == sizeof(uint32_t) * 3 + sizeof(llama_token) * n_token_count + io.n_bytes());

    return res;
}

size_t llama_context::state_write_data(llama_io_write_i & io) {
    LLAMA_LOG_DEBUG("%s: writing state\n", __func__);
    synchronize();

    // write model info
    {
        LLAMA_LOG_DEBUG("%s: - writing model info\n", __func__);

        const std::string arch_str = llm_arch_name(model.arch);
        io.write_string(arch_str);
        // TODO: add more model-specific info which should prevent loading the session file if not identical
    }

    if (memory != nullptr) {
        LLAMA_LOG_DEBUG("%s: - writing memory module\n", __func__);
        memory->state_write(io);
    }

    if (cassi_modal.enabled) {
        cassi_modal_write_header(io, cassi_modal, cassi_modal.n_seq_max);
        for (uint32_t seq_id = 0; seq_id < cassi_modal.n_seq_max; ++seq_id) {
            const llama_seq_id id = (llama_seq_id) seq_id;
            io.write(&id, sizeof(id));
            io.write(
                cassi_modal.state + (size_t) seq_id * cassi_modal.state_stride,
                (size_t) cassi_modal.state_stride * sizeof(float));
        }
    }
    if (cassi_field.enabled) {
        cassi_field_write_header(io, cassi_field, cassi_field.n_seq_max);
        for (uint32_t seq_id = 0; seq_id < cassi_field.n_seq_max; ++seq_id) {
            const llama_seq_id id = (llama_seq_id) seq_id;
            io.write(&id, sizeof(id));
            io.write(
                cassi_field.state + (size_t) seq_id * cassi_field.state_stride,
                (size_t) cassi_field.state_stride * sizeof(float));
        }
    }
    if (cassi_qi.enabled) {
        cassi_qi_write_header(io, cassi_qi, cassi_qi.n_seq_max);
        for (uint32_t seq_id = 0; seq_id < cassi_qi.n_seq_max; ++seq_id) {
            const llama_seq_id id = (llama_seq_id) seq_id;
            io.write(&id, sizeof(id));
            io.write(cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
                (size_t) cassi_qi.state_stride * sizeof(float));
        }
    }

    return io.n_bytes();
}

size_t llama_context::state_read_data(llama_io_read_i & io) {
    LLAMA_LOG_DEBUG("%s: reading state\n", __func__);
    synchronize();

    // read model info
    {
        LLAMA_LOG_DEBUG("%s: - reading model info\n", __func__);

        const std::string cur_arch_str = llm_arch_name(model.arch);

        std::string arch_str;
        io.read_string(arch_str);
        if (cur_arch_str != arch_str) {
            throw std::runtime_error(format("wrong model arch: '%s' instead of '%s'", arch_str.c_str(), cur_arch_str.c_str()));
        }
        // TODO: add more info which needs to be identical but which is not verified otherwise
    }

    if (memory) {
        LLAMA_LOG_DEBUG("%s: - reading memory module\n", __func__);
        memory->state_read(io);
    }

    if (cassi_modal.enabled) {
        cassi_modal_read_header(io, cassi_modal, cassi_modal.n_seq_max);
        for (uint32_t seq_id = 0; seq_id < cassi_modal.n_seq_max; ++seq_id) {
            llama_seq_id id = -1;
            io.read(&id, sizeof(id));
            if (id < 0 || (uint32_t) id != seq_id || (uint32_t) id >= cassi_modal.n_seq_max) {
                throw std::runtime_error("invalid Cassi modal context sequence id");
            }
            io.read(
                cassi_modal.state + (size_t) seq_id * cassi_modal.state_stride,
                (size_t) cassi_modal.state_stride * sizeof(float));
        }
    }

    if (cassi_field.enabled) {
        cassi_field_read_header(io, cassi_field, cassi_field.n_seq_max);
        for (uint32_t seq_id = 0; seq_id < cassi_field.n_seq_max; ++seq_id) {
            llama_seq_id id = -1;
            io.read(&id, sizeof(id));
            if (id < 0 || (uint32_t) id != seq_id || (uint32_t) id >= cassi_field.n_seq_max) {
                throw std::runtime_error("invalid Cassi field-step context sequence id");
            }
            io.read(
                cassi_field.state + (size_t) seq_id * cassi_field.state_stride,
                (size_t) cassi_field.state_stride * sizeof(float));
        }
    }
    if (cassi_qi.enabled) {
        const uint32_t stored_sequence_count = cassi_qi_read_header(io, cassi_qi, cassi_qi.n_seq_max);
        std::memset(
            cassi_qi.state,
            0,
            (size_t) cassi_qi.n_seq_max * cassi_qi.state_stride * sizeof(float));
        for (uint32_t seq_id = 0; seq_id < stored_sequence_count; ++seq_id) {
            llama_seq_id id = -1;
            io.read(&id, sizeof(id));
            if (id < 0 || (uint32_t) id != seq_id) {
                throw std::runtime_error("invalid Cassi Qi field context sequence id");
            }
            io.read(cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
                (size_t) cassi_qi.state_stride * sizeof(float));
        }
    }
    return io.n_bytes();
}

size_t llama_context::state_seq_write_data(llama_io_write_i & io, llama_seq_id seq_id, llama_state_seq_flags flags) {
    if (seq_id < 0 || (uint32_t) seq_id >= cparams.n_seq_max) {
        throw std::runtime_error("Cassi modal sequence id out of range");
    }
    synchronize();

    if (memory) {
        memory->state_write(io, seq_id, flags);
    }

    if (cassi_modal.enabled) {
        cassi_modal_write_header(io, cassi_modal, 1);
        io.write(&seq_id, sizeof(seq_id));
        io.write(
            cassi_modal.state + (size_t) seq_id * cassi_modal.state_stride,
            (size_t) cassi_modal.state_stride * sizeof(float));
    }
    if (cassi_field.enabled) {
        cassi_field_write_header(io, cassi_field, 1);
        io.write(&seq_id, sizeof(seq_id));
        io.write(
            cassi_field.state + (size_t) seq_id * cassi_field.state_stride,
            (size_t) cassi_field.state_stride * sizeof(float));
    }
    if (cassi_qi.enabled) {
        cassi_qi_write_header(io, cassi_qi, 1);
        io.write(&seq_id, sizeof(seq_id));
        io.write(cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
            (size_t) cassi_qi.state_stride * sizeof(float));
    }

    return io.n_bytes();
}

size_t llama_context::state_seq_read_data(llama_io_read_i & io, llama_seq_id seq_id, llama_state_seq_flags flags) {
    if (seq_id < 0 || (uint32_t) seq_id >= cparams.n_seq_max) {
        throw std::runtime_error("Cassi modal sequence id out of range");
    }
    synchronize();

    if (memory) {
        memory->state_read(io, seq_id, flags);
    }

    if (cassi_modal.enabled) {
        cassi_modal_read_header(io, cassi_modal, 1);
        llama_seq_id id = -1;
        io.read(&id, sizeof(id));
        if (id != seq_id || id < 0 || (uint32_t) id >= cassi_modal.n_seq_max) {
            throw std::runtime_error("invalid Cassi modal sequence id");
        }
        io.read(
            cassi_modal.state + (size_t) seq_id * cassi_modal.state_stride,
            (size_t) cassi_modal.state_stride * sizeof(float));
    }
    if (cassi_field.enabled) {
        cassi_field_read_header(io, cassi_field, 1);
        llama_seq_id id = -1;
        io.read(&id, sizeof(id));
        if (id != seq_id || id < 0 || (uint32_t) id >= cassi_field.n_seq_max) {
            throw std::runtime_error("invalid Cassi field-step sequence id");
        }
        io.read(
            cassi_field.state + (size_t) seq_id * cassi_field.state_stride,
            (size_t) cassi_field.state_stride * sizeof(float));
    }
    if (cassi_qi.enabled) {
        cassi_qi_read_header(io, cassi_qi, 1);
        llama_seq_id stored_seq_id = -1;
        io.read(&stored_seq_id, sizeof(stored_seq_id));
        if (stored_seq_id < 0) {
            throw std::runtime_error("invalid Cassi Qi field sequence id");
        }
        io.read(cassi_qi.state + (size_t) seq_id * cassi_qi.state_stride,
            (size_t) cassi_qi.state_stride * sizeof(float));
    }

    return io.n_bytes();
}

//
// perf
//

llama_perf_context_data llama_context::perf_get_data() const {
    llama_perf_context_data data = {};

    data.t_start_ms  = 1e-3 * t_start_us;
    data.t_load_ms   = 1e-3 * t_load_us;
    data.t_p_eval_ms = 1e-3 * t_p_eval_us;
    data.t_eval_ms   = 1e-3 * t_eval_us;
    data.n_p_eval    = std::max(1, n_p_eval);
    data.n_eval      = std::max(1, n_eval);
    data.n_reused    = std::max(0, n_reused);

    return data;
}

void llama_context::perf_reset() {
    t_start_us  = ggml_time_us();
    t_eval_us   = n_eval = 0;
    t_p_eval_us = n_p_eval = 0;
    n_reused    = 0;
}

llama_memory_breakdown llama_context::memory_breakdown() const {
    std::map<ggml_backend_buffer_type_t, llama_memory_breakdown_data> ret;
    for (const auto & [buft, size] : model.memory_breakdown()) {
        ret[buft].model += size;
    }
    if (memory) {
        for (const auto & [buft, size] : memory->memory_breakdown()) {
            ret[buft].context += size;
        }
    }
    if (model.hparams.no_alloc) {
        for (size_t i = 0; i < backends.size(); ++i) {
            ggml_backend_t             backend = backends[i].get();
            ggml_backend_buffer_type_t buft    = ggml_backend_sched_get_buffer_type(sched.get(), backend);
            ret[buft].compute += backend_buf_exp_size[i];
        }
    } else {
        for (const auto & backend_ptr : backends) {
            ggml_backend_t             backend = backend_ptr.get();
            ggml_backend_buffer_type_t buft    = ggml_backend_sched_get_buffer_type(sched.get(), backend);
            ret[buft].compute += ggml_backend_sched_get_buffer_size(sched.get(), backend);
        }
    }
    return ret;
}

//
// training
//

static void llama_set_param(struct ggml_tensor * tensor, llama_opt_param_filter param_filter, void * userdata) {
    if (!tensor || tensor->type != GGML_TYPE_F32) {
        return;
    }
    if (!param_filter(tensor, userdata)) {
        return;
    }
    if (strcmp(tensor->name, "token_embd.weight") == 0) {
        return; // FIXME
    }
    if (strcmp(tensor->name, "rope_freqs.weight") == 0) {
        return; // FIXME
    }
    ggml_set_param(tensor);
}

void llama_context::opt_init(struct llama_model * model, struct llama_opt_params lopt_params) {
    GGML_ASSERT(!opt_ctx);
    model->hparams.n_ctx_train = lopt_params.n_ctx_train > 0 ? lopt_params.n_ctx_train : n_ctx();
    const uint32_t n_batch     = std::min(this->n_batch(),  model->hparams.n_ctx_train);
    const uint32_t n_ubatch    = std::min(this->n_ubatch(), n_batch);
    GGML_ASSERT(model->hparams.n_ctx_train % n_batch  == 0);
    GGML_ASSERT(n_batch                    % n_ubatch == 0);

    ggml_opt_params opt_params = ggml_opt_default_params(sched.get(), GGML_OPT_LOSS_TYPE_CROSS_ENTROPY);
    opt_params.opt_period      = n_batch / n_ubatch;
    opt_params.get_opt_pars    = lopt_params.get_opt_pars;
    opt_params.get_opt_pars_ud = lopt_params.get_opt_pars_ud;
    opt_params.optimizer       = lopt_params.optimizer_type;
    opt_ctx = ggml_opt_init(opt_params);

    llama_opt_param_filter param_filter = lopt_params.param_filter;
    void * param_filter_ud              = lopt_params.param_filter_ud;

  //llama_set_param(model->tok_embd,        param_filter, param_filter_ud); // FIXME
    llama_set_param(model->type_embd,       param_filter, param_filter_ud);
    llama_set_param(model->pos_embd,        param_filter, param_filter_ud);
    llama_set_param(model->tok_norm,        param_filter, param_filter_ud);
    llama_set_param(model->tok_norm_b,      param_filter, param_filter_ud);
    llama_set_param(model->output_norm,     param_filter, param_filter_ud);
    llama_set_param(model->output_norm_b,   param_filter, param_filter_ud);
    llama_set_param(model->output,          param_filter, param_filter_ud);
    llama_set_param(model->output_b,        param_filter, param_filter_ud);
    llama_set_param(model->output_norm_enc, param_filter, param_filter_ud);
    llama_set_param(model->cls,             param_filter, param_filter_ud);
    llama_set_param(model->cls_b,           param_filter, param_filter_ud);
    llama_set_param(model->cls_out,         param_filter, param_filter_ud);
    llama_set_param(model->cls_out_b,       param_filter, param_filter_ud);
    llama_set_param(model->cls_norm,        param_filter, param_filter_ud);

    for (struct llama_layer & layer : model->layers) {
        for (size_t i = 0; i < sizeof(layer)/sizeof(struct ggml_tensor *); ++i) {
            llama_set_param(reinterpret_cast<struct ggml_tensor **>(&layer)[i], param_filter, param_filter_ud);
        }
    }
}

void llama_context::opt_epoch_iter(
        ggml_opt_dataset_t               dataset,
        ggml_opt_result_t                result,
        const std::vector<llama_token> & tokens,
        const std::vector<llama_token> & labels_sparse,
        llama_batch                    & batch,
        ggml_opt_epoch_callback          callback,
        bool                             train,
        int64_t                          idata_in_loop,
        int64_t                          ndata_in_loop,
        int64_t                          t_loop_start) {
    GGML_ASSERT(opt_ctx);
    const uint32_t n_ctx    = llama_model_n_ctx_train(&model);
    const uint32_t n_batch  = std::min(this->n_batch(),  n_ctx);
    const uint32_t n_ubatch = std::min(this->n_ubatch(), n_batch);

    memory->clear(true);

    for (uint32_t pos_ctx = 0; pos_ctx < n_ctx; pos_ctx += n_batch) {
        batch.n_tokens = n_batch;
        for (uint32_t pos_batch = 0; pos_batch < n_batch; ++pos_batch) {
            batch.token   [pos_batch]    = tokens[pos_ctx + pos_batch];
            batch.pos     [pos_batch]    = pos_ctx + pos_batch;
            batch.n_seq_id[pos_batch]    = 1;
            batch.seq_id  [pos_batch][0] = 0;
            batch.logits  [pos_batch]    = true;
        }

        if (!balloc->init(batch, model.vocab, nullptr, model.hparams.n_embd_inp(), cparams.kv_unified ? LLAMA_MAX_SEQ : cparams.n_seq_max, true)) {
            LLAMA_LOG_ERROR("%s: failed to initialize batch\n", __func__);
            return;
        }

        const uint32_t n_tokens_all = balloc->get_n_tokens();

        n_queued_tokens += n_tokens_all;

        embd_seq.clear();

        uint32_t n_outputs_all = n_tokens_all;

        auto mctx = memory->init_batch(*balloc, cparams.n_ubatch, true);
        if (!mctx || mctx->get_status() != LLAMA_MEMORY_STATUS_SUCCESS) {
            LLAMA_LOG_ERROR("%s: could not initialize batch\n", __func__);
            break;
        }

        // reserve output buffer
        if (output_reserve(n_outputs_all) < n_outputs_all) {
            LLAMA_LOG_ERROR("%s: could not reserve space for batch with %d outputs\n", __func__, n_outputs_all);
            GGML_ABORT("TODO: handle this error");
        };

        uint32_t pos_batch = 0;
        do {
            const auto & ubatch = mctx->get_ubatch();

            n_outputs = ubatch.n_tokens;

            if (!mctx->apply()) {
                LLAMA_LOG_ERROR("%s: failed to update the memory context\n", __func__);
                break;
            }

            auto * res = gf_res_prev.get();

            const auto gparams = graph_params(res, ubatch, mctx.get(), ctx_type_to_graph_type(cparams.ctx_type));

            res->reset();

            auto * gf = model.build_graph(gparams);

            struct ggml_context * ctx_compute_opt;
            {
                const size_t size_gf = ggml_graph_size(gf);
                const size_t size_meta = 4*size_gf*ggml_tensor_overhead() + 2*ggml_graph_overhead_custom(size_gf, /*grads = */ true);
                struct ggml_init_params params = {
                    /*.mem_size   =*/ size_meta,
                    /*.mem_buffer =*/ nullptr,
                    /*.no_alloc   =*/ true,
                };
                ctx_compute_opt = ggml_init(params);
            }
            ggml_opt_prepare_alloc(opt_ctx, ctx_compute_opt, gf, res->get_inp_tokens(), res->get_logits());
            ggml_opt_alloc(opt_ctx, train);

            res->set_inputs(&ubatch);
            {
                struct ggml_tensor * labels = ggml_opt_labels(opt_ctx);
                GGML_ASSERT(labels->ne[1] == n_ubatch);
                ggml_set_zero(labels);
                const float onef = 1.0f;
                for (uint32_t pos_ubatch = 0; pos_ubatch < n_ubatch; ++pos_ubatch) {
                    const uint32_t ilabel = pos_ctx + pos_batch + pos_ubatch;
                    GGML_ASSERT(labels_sparse[ilabel] < labels->ne[0]);
                    ggml_backend_tensor_set(labels, &onef, (pos_ubatch*labels->ne[0] + labels_sparse[ilabel])*sizeof(float), sizeof(float));
                }
            }
            ggml_opt_eval(opt_ctx, result);
            if (callback) {
                callback(train, opt_ctx, dataset, result, idata_in_loop + (pos_ctx + pos_batch)/n_ubatch + 1, ndata_in_loop, t_loop_start);
            }
            ggml_free(ctx_compute_opt);

            pos_batch += ubatch.n_tokens;
        } while (mctx->next());
    }
}

void llama_context::opt_epoch(
        ggml_opt_dataset_t        dataset,
        ggml_opt_result_t         result_train,
        ggml_opt_result_t         result_eval,
        int64_t                   idata_split,
        ggml_opt_epoch_callback   callback_train,
        ggml_opt_epoch_callback   callback_eval) {
    const uint32_t n_ctx    = this->n_ctx();
    const uint32_t n_batch  = std::min(cparams.n_batch,  n_ctx);
    const uint32_t n_ubatch = std::min(cparams.n_ubatch, n_batch);
    const  int64_t ndata    = ggml_opt_dataset_ndata(dataset);

    GGML_ASSERT(idata_split >= 0);
    GGML_ASSERT(idata_split <= ndata);

    const uint32_t ubatch_per_ctx = n_ctx / n_ubatch;

    struct llama_batch batch = llama_batch_init(n_batch, 0, 1);
    std::vector<llama_token>        tokens(n_ctx);
    std::vector<llama_token> labels_sparse(n_ctx);

    int64_t idata = 0;

    int64_t t_loop_start = ggml_time_us();
    int64_t ndata_in_loop = idata_split*ubatch_per_ctx;
    for (; idata < idata_split; ++idata) {
        constexpr bool train = true;
        const int64_t idata_in_loop = idata*ubatch_per_ctx;

        ggml_opt_dataset_get_batch_host(dataset, tokens.data(), n_ctx*sizeof(llama_token), labels_sparse.data(), idata);
        opt_epoch_iter(dataset, result_train, tokens, labels_sparse, batch,
            callback_train, train, idata_in_loop, ndata_in_loop, t_loop_start);
    }

    t_loop_start = ggml_time_us();
    ndata_in_loop = (ndata - idata_split)*ubatch_per_ctx;
    for (; idata < ndata; ++idata) {
        constexpr bool train = false;
        const int64_t idata_in_loop = (idata - idata_split)*ubatch_per_ctx;

        ggml_opt_dataset_get_batch_host(dataset, tokens.data(), n_ctx*sizeof(llama_token), labels_sparse.data(), idata);
        opt_epoch_iter(dataset, result_eval, tokens, labels_sparse, batch,
            callback_eval, train, idata_in_loop, ndata_in_loop, t_loop_start);
    }

    llama_batch_free(batch);
}

//
// interface implementation
//

llama_context_params llama_context_default_params() {
    llama_context_params result = {
        /*.n_ctx                       =*/ 512,
        /*.n_batch                     =*/ 2048,
        /*.n_ubatch                    =*/ 512,
        /*.n_seq_max                   =*/ 1,
        /*.n_rs_seq                    =*/ 0,
        /*.n_outputs_max               =*/ 0,
        /*.n_outputs_max_per_seq       =*/ 1,
        /*.n_threads                   =*/ GGML_DEFAULT_N_THREADS, // TODO: better default
        /*.n_threads_batch             =*/ GGML_DEFAULT_N_THREADS,
        /*.ctx_type                    =*/ LLAMA_CONTEXT_TYPE_DEFAULT,
        /*.rope_scaling_type           =*/ LLAMA_ROPE_SCALING_TYPE_UNSPECIFIED,
        /*.pooling_type                =*/ LLAMA_POOLING_TYPE_UNSPECIFIED,
        /*.attention_type              =*/ LLAMA_ATTENTION_TYPE_UNSPECIFIED,
        /*.flash_attn_type             =*/ LLAMA_FLASH_ATTN_TYPE_AUTO,
        /*.rope_freq_base              =*/ 0.0f,
        /*.rope_freq_scale             =*/ 0.0f,
        /*.yarn_ext_factor             =*/ -1.0f,
        /*.yarn_attn_factor            =*/ -1.0f,
        /*.yarn_beta_fast              =*/ -1.0f,
        /*.yarn_beta_slow              =*/ -1.0f,
        /*.yarn_orig_ctx               =*/ 0,
        /*.defrag_thold                =*/ -1.0f,
        /*.cb_eval                     =*/ nullptr,
        /*.cb_eval_user_data           =*/ nullptr,
        /*.type_k                      =*/ GGML_TYPE_F16,
        /*.type_v                      =*/ GGML_TYPE_F16,
        /*.abort_callback              =*/ nullptr,
        /*.abort_callback_data         =*/ nullptr,
        /*.embeddings                  =*/ false,
        /*.offload_kqv                 =*/ true,
        /*.no_perf                     =*/ true,
        /*.op_offload                  =*/ true,
        /*.swa_full                    =*/ true,
        /*.kv_unified                  =*/ false,
        /*.cassi_modal                 =*/ true,
        /*.cassi_field_step            =*/ false,
        /*.cassi_qi_field              =*/ false,
        /*.cassi_apprentice            =*/ false,
        /*.cassi_field_layer           =*/ 32,
        /*.cassi_qi_field_layer        =*/ 32,
        /*.cassi_qi_field_scales       =*/ 4,
        /*.cassi_qi_field_wave_modes   =*/ 3072,
        /*.cassi_qi_field_fill_modes   =*/ false,
        /*.cassi_qi_field_memory_fill =*/ false,
        /*.cassi_qi_field_row_width    =*/ 0,
        /*.cassi_qi_displacement        =*/ 0,
        /*.cassi_qi_intervention        =*/ 0,
        /*.cassi_qi_field_steps         =*/ 1,
        /*.cassi_qi_injection_scale     =*/ 1.0f,
        /*.cassi_qi_field_dt            =*/ 0.005f,
        /*.cassi_qi_substitute          =*/ 0.0f,
        /*.cassi_qi_energy_floor        =*/ 1.0e-6f,
        /*.cassi_qi_read_floor          =*/ 0.05f,
        /*.cassi_qi_scale_read_taper    =*/ 0.0f,
        /*.cassi_qi_read_absolute       =*/ false,
        /*.cassi_qi_modulate            =*/ false,
        /*.cassi_qi_modulate_gain       =*/ 0.0f,
        /*.cassi_qi_attention_history  =*/ false,
        /*.cassi_qi_unwritten_latch    =*/ false,
        /*.cassi_attention_owned       =*/ nullptr,
        /*.cassi_attention_owned_count =*/ 0,
        /*.samplers                    =*/ nullptr,
        /*.n_samplers                  =*/ 0,
        /*.ctx_other                   =*/ nullptr,
        /*.cassi_modal_retained_weight =*/ 0.9f,
        /*.cassi_modal_phi             =*/ 1.618033988749895f,
        /*.cassi_modal_dt              =*/ 0.005f,
        /*.cassi_modal_omega2          =*/ 20.0f,
        /*.cassi_modal_coupling        =*/ 1.0f,
        /*.cassi_modal_steps_per_layer =*/ 4,
    };

    return result;
}

static llama_context * llama_init_from_model_impl(
                 llama_model * model,
        llama_context_params   params,
                         bool exact_n_ctx) {
    if (!model) {
        LLAMA_LOG_ERROR("%s: model cannot be NULL\n", __func__);
        return nullptr;
    }

    if (params.n_batch == 0 && params.n_ubatch == 0) {
        LLAMA_LOG_ERROR("%s: n_batch and n_ubatch cannot both be zero\n", __func__);
        return nullptr;
    }

    if (params.n_ctx == 0 && model->hparams.n_ctx_train == 0) {
        LLAMA_LOG_ERROR("%s: n_ctx and model->hparams.n_ctx_train cannot both be zero\n", __func__);
        return nullptr;
    }

    if (params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_DISABLED && model->arch == LLM_ARCH_GROK) {
        LLAMA_LOG_WARN("%s: flash_attn is not compatible with Grok - forcing off\n", __func__);
        params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
    }

    if (model->split_mode() == LLAMA_SPLIT_MODE_TENSOR) {
        if (params.flash_attn_type == LLAMA_FLASH_ATTN_TYPE_AUTO) {
            LLAMA_LOG_INFO("%s: enabling flash_attn since it is required for SPLIT_MODE_TENSOR\n", __func__);
            params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
        }
        if (params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_ENABLED) {
            LLAMA_LOG_ERROR("%s: SPLIT_MODE_TENSOR requires flash_attn to be enabled\n", __func__);
            return nullptr;
        }
    }

    if ((model->hparams.is_mla() || model->arch == LLM_ARCH_DEEPSEEK4) && params.type_k != params.type_v) {
        LLAMA_LOG_ERROR("%s: model does not support different K (%s) and V (%s) cache types\n", __func__, ggml_type_name(params.type_k), ggml_type_name(params.type_v));
        return nullptr;
    }

    if (ggml_is_quantized(params.type_v) && params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_ENABLED) {
        if (params.flash_attn_type == LLAMA_FLASH_ATTN_TYPE_AUTO) {
            LLAMA_LOG_INFO("%s: enabling flash_attn since it is required for quantized V cache\n", __func__);
            params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
        }
        if (params.flash_attn_type == LLAMA_FLASH_ATTN_TYPE_DISABLED) {
            LLAMA_LOG_ERROR("%s: quantized V cache requires flash_attn to be enabled\n", __func__);
            return nullptr;
        }
    }

    if (params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_DISABLED && ggml_is_quantized(params.type_k)) {
        const uint32_t blck_size = ggml_blck_size(params.type_k);
        for (uint32_t il = 0; il < model->hparams.n_layer(); ++il) {
            if (model->hparams.n_embd_head_k(il) % blck_size != 0) {
                LLAMA_LOG_ERROR("%s: K cache type %s with block size %u does not divide n_embd_head_k=%u\n",
                    __func__, ggml_type_name(params.type_k), blck_size, model->hparams.n_embd_head_k(il));
                return nullptr;
            }
        }
    }

    if (params.flash_attn_type != LLAMA_FLASH_ATTN_TYPE_DISABLED && ggml_is_quantized(params.type_v)) {
        const uint32_t blck_size = ggml_blck_size(params.type_v);
        for (uint32_t il = 0; il < model->hparams.n_layer(); ++il) {
            if (model->hparams.n_embd_head_v(il) % blck_size != 0) {
                LLAMA_LOG_ERROR("%s: V cache type %s with block size %u does not divide n_embd_head_v=%u\n",
                    __func__, ggml_type_name(params.type_v), blck_size, model->hparams.n_embd_head_v(il));
                return nullptr;
            }
        }
    }

    if (params.pooling_type != LLAMA_POOLING_TYPE_UNSPECIFIED &&
        params.pooling_type != model->hparams.pooling_type) {
        //user-specified pooling-type is different from the model default
        LLAMA_LOG_WARN("%s: model default pooling_type is [%d], but [%d] was specified\n", __func__,
                       model->hparams.pooling_type, params.pooling_type);
    }

    // router_layer >= 0 means n_layer_nextn is repurposed for a router layer, not real MTP
    if (params.ctx_type == LLAMA_CONTEXT_TYPE_MTP &&
        (model->hparams.n_layer_nextn == 0 || model->hparams.router_layer >= 0)) {
        LLAMA_LOG_WARN("%s: context type MTP requested but model doesn't contain MTP layers\n", __func__);
        return nullptr;
    }

    try {
        auto * ctx = new llama_context(*model, params, exact_n_ctx);
        return ctx;
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: failed to initialize the context: %s\n", __func__, err.what());
    }

    return nullptr;
}

llama_context * llama_init_from_model(
                 llama_model * model,
        llama_context_params   params) {
    return llama_init_from_model_impl(model, params, false);
}

llama_context * llama_init_from_model_exact(
                 llama_model * model,
        llama_context_params   params) {
    return llama_init_from_model_impl(model, params, true);
}

// deprecated
llama_context * llama_new_context_with_model(
                 llama_model * model,
        llama_context_params   params) {
    return llama_init_from_model(model, params);
}

void llama_free(llama_context * ctx) {
    delete ctx;
}

uint32_t llama_n_ctx(const llama_context * ctx) {
    return ctx->n_ctx();
}

uint32_t llama_n_ctx_seq(const llama_context * ctx) {
    return ctx->n_ctx_seq();
}

uint32_t llama_n_batch(const llama_context * ctx) {
    return ctx->n_batch();
}

uint32_t llama_n_ubatch(const llama_context * ctx) {
    return ctx->n_ubatch();
}

uint32_t llama_n_seq_max(const llama_context * ctx) {
    return ctx->n_seq_max();
}

uint32_t llama_n_rs_seq(const llama_context * ctx) {
    return ctx->get_cparams().n_rs_seq;
}

const llama_model * llama_get_model(const llama_context * ctx) {
    return &ctx->get_model();
}

enum llama_pooling_type llama_pooling_type(const llama_context * ctx) {
    return ctx->pooling_type();
}

void llama_attach_threadpool(
            llama_context * ctx,
        ggml_threadpool_t   threadpool,
        ggml_threadpool_t   threadpool_batch) {
    ctx->attach_threadpool(threadpool, threadpool_batch);
}

void llama_detach_threadpool(llama_context * ctx) {
    ctx->detach_threadpool();
}

void llama_set_n_threads(llama_context * ctx, int32_t n_threads, int32_t n_threads_batch) {
    ctx->set_n_threads(n_threads, n_threads_batch);
}

int32_t llama_n_threads(llama_context * ctx) {
    return ctx->n_threads();
}

int32_t llama_n_threads_batch(llama_context * ctx) {
    return ctx->n_threads_batch();
}

void llama_set_abort_callback(llama_context * ctx, bool (*abort_callback)(void * data), void * abort_callback_data) {
    ctx->set_abort_callback(abort_callback, abort_callback_data);
}

void llama_set_embeddings(llama_context * ctx, bool embeddings) {
    ctx->set_embeddings(embeddings);
}

void llama_set_causal_attn(llama_context * ctx, bool causal_attn) {
    ctx->set_causal_attn(causal_attn);
}

void llama_set_warmup(llama_context * ctx, bool warmup) {
    ctx->set_warmup(warmup);
}

void llama_synchronize(llama_context * ctx) {
    ctx->synchronize();
}

float * llama_get_logits(llama_context * ctx) {
    ctx->synchronize();

    return ctx->get_logits();
}

float * llama_get_logits_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    float * res = nullptr;

    res = ctx->get_sampled_logits_ith(i);

    if (!res) {
        res = ctx->get_logits_ith(i);
    }

    return res;
}

float * llama_get_embeddings(llama_context * ctx) {
    ctx->synchronize();

    return ctx->get_embeddings();
}

float * llama_get_embeddings_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return ctx->get_embeddings_ith(i);
}

float * llama_get_embeddings_seq(llama_context * ctx, llama_seq_id seq_id) {
    ctx->synchronize();

    return ctx->get_embeddings_seq(seq_id);
}

void llama_set_embeddings_nextn(llama_context * ctx, bool value, bool masked) {
    ctx->set_embeddings_nextn(value, masked);
}

void llama_set_embeddings_layer_inp(llama_context * ctx, uint32_t lid, bool value) {
    ctx->set_embeddings_layer_inp(lid, value);
}

void llama_set_nextn_layer_offset(llama_context * ctx, int32_t offset) {
    ctx->set_nextn_layer_offset(offset);
}

llama_memory_t llama_get_memory(const struct llama_context * ctx) {
    if (!ctx) {
        return nullptr;
    }

    return ctx->get_memory();
}

void llama_qwen35_footprint(
        const struct llama_model * model,
        struct llama_context * ctx,
        struct llama_qwen35_footprint * out) {
    if (!out) {
        return;
    }
    *out = {};
    if (!model && !ctx) {
        return;
    }
    if (model) {
        out->model_size_bytes = llama_model_size(model);
        out->model_params = llama_model_n_params(model);
        out->n_layer_full_attn = llama_model_n_layer_attn(model);
        out->n_layer_recurrent = llama_model_n_layer_recurrent(model);
        out->n_layer_mtp = llama_model_n_layer_nextn(model);
        out->n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
        out->gguf_open_count = 1;
    }
    if (ctx) {
        out->serialized_state_bytes = llama_state_get_size(ctx);
        llama_memory_t mem = llama_get_memory(ctx);
        if (mem) {
            llama_memory_hybrid * hybrid = dynamic_cast<llama_memory_hybrid *>(mem);
            if (hybrid) {
                const llama_kv_cache * attn = hybrid->get_mem_attn();
                const llama_memory_recurrent * recr = hybrid->get_mem_recr();
                if (attn) {
                    out->kv_bytes = attn->size_k_bytes() + attn->size_v_bytes();
                }
                if (recr) {
                    out->recurrent_bytes = recr->size_r_bytes() + recr->size_s_bytes();
                }
            }
        }
    }
}

float * llama_get_embeddings_nextn(llama_context * ctx) {
    ctx->synchronize();

    return ctx->get_embeddings_nextn();
}

float * llama_get_embeddings_nextn_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return ctx->get_embeddings_nextn_ith(i);
}

float * llama_get_embeddings_layer_inp(llama_context * ctx, uint32_t lid) {
    ctx->synchronize();

    return ctx->get_embeddings_layer_inp(lid);
}

bool llama_set_sampler(llama_context * ctx, llama_seq_id seq_id, llama_sampler * smpl) {
    return ctx->set_sampler(seq_id, smpl);
}

llama_token llama_get_sampled_token_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return ctx->get_sampled_token_ith(i);
}

float * llama_get_sampled_probs_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return ctx->get_sampled_probs_ith(i);
}

float * llama_get_sampled_logits_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return ctx->get_sampled_logits_ith(i);
}

llama_token * llama_get_sampled_candidates_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return const_cast<llama_token *>(ctx->get_sampled_candidates_ith(i));
}

uint32_t llama_get_sampled_candidates_count_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return static_cast<uint32_t>(ctx->get_sampled_candidates_count(i));
}

uint32_t llama_get_sampled_logits_count_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return static_cast<uint32_t>(ctx->get_sampled_logits_count(i));
}

uint32_t llama_get_sampled_probs_count_ith(llama_context * ctx, int32_t i) {
    ctx->synchronize();

    return static_cast<uint32_t>(ctx->get_sampled_probs_count(i));
}

struct ggml_cgraph * llama_graph_reserve(
        struct llama_context * ctx,
        uint32_t n_tokens,
        uint32_t n_seqs,
        uint32_t n_outputs) {
    auto memory = ctx->get_memory();
    llama_memory_context_ptr mctx;
    if (memory) {
        mctx = memory->init_full();
    }
    return ctx->graph_reserve(n_tokens, n_seqs, n_outputs, mctx.get());
}

// llama adapter API

int32_t llama_set_adapters_lora(
            llama_context * ctx,
            llama_adapter_lora ** adapters,
            size_t n_adapters,
            float * scales) {
    if (adapters == nullptr || scales == nullptr) {
        GGML_ASSERT(n_adapters == 0 && "invalid llama_set_adapters_lora call");
    }

    ctx->set_adapters_lora(adapters, n_adapters, scales);

    return 0;
}

int32_t llama_set_adapter_cvec(
        llama_context * ctx,
          const float * data,
               size_t   len,
              int32_t   n_embd,
              int32_t   il_start,
              int32_t   il_end) {
    bool res = ctx->set_adapter_cvec(data, len, n_embd, il_start, il_end);

    return res ? 0 : -1;
}
bool llama_cassi_graph_site_candidate_set(
        llama_context * ctx,
        const llama_cassi_graph_site_candidate * candidate) {
    return ctx != nullptr && candidate != nullptr && ctx->graph_site_candidate_set(*candidate);
}

void llama_cassi_graph_site_candidate_clear(
        llama_context * ctx,
        const char * sequence_id,
        uint64_t owner_generation) {
    if (ctx != nullptr) {
        ctx->graph_site_candidate_clear(sequence_id != nullptr ? sequence_id : "", owner_generation);
    }
}

bool llama_cassi_graph_site_candidate_get_result(
        const llama_context * ctx,
        llama_cassi_graph_site_candidate_result * result) {
    if (ctx == nullptr || result == nullptr) {
        return false;
    }
    const auto & source = ctx->graph_site_candidate_get_result();
    *result = {};
    result->attempted = source.attempted;
    result->admitted = source.admitted;
    result->owner_generation = source.owner_generation;
    result->operators_omitted = source.operators_omitted;
    result->weights_omitted = source.weights_omitted;
    result->weight_bytes_omitted = source.weight_bytes_omitted;
    // The graph receipt has no measured transfer-byte counter.
    graph_site_copy_c_string(result->refusal, source.refusal);
    graph_site_copy_c_string(result->input_sha256, source.input_sha256);
    graph_site_copy_c_string(result->output_sha256, source.output_sha256);
    graph_site_copy_c_string(result->native_successor_sha256, source.native_successor_sha256);
    graph_site_copy_c_string(result->request_sha256, source.request_sha256);
    result->request_sha256_pending = source.request_sha256_pending;
    graph_site_copy_c_string(result->invocation_sha256, source.invocation_sha256);
    graph_site_copy_c_string(result->predecessor_sha256, source.predecessor_sha256);
    graph_site_copy_c_string(result->successor_sha256, source.successor_sha256);
    graph_site_copy_c_string(result->successor_state_json, source.successor_state_json);
    result->actual_expert_ids = source.actual_expert_ids.empty()
        ? nullptr
        : source.actual_expert_ids.data();
    result->actual_expert_ids_count = source.actual_expert_ids.size();
    graph_site_copy_c_string(result->candidate_sha256, source.candidate_sha256);
    return true;
}

bool llama_cassi_graph_site_candidate_set_native_successor_sha256(
        llama_context * ctx,
        const char * candidate_sha256,
        const char * invocation_sha256,
        const char * native_successor_sha256) {
    return ctx != nullptr && candidate_sha256 != nullptr && invocation_sha256 != nullptr &&
        native_successor_sha256 != nullptr &&
        ctx->graph_site_candidate_set_native_successor_sha256(
            candidate_sha256, invocation_sha256, native_successor_sha256);
}


size_t llama_cassi_qi_state_size(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_state_size() : 0;
}

int64_t llama_cassi_qi_flux_size(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_flux_size() : 0;
}

const float * llama_cassi_qi_flux_data(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_flux_data() : nullptr;
}

int64_t llama_cassi_qi_state_field_width(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_state_field_width() : 0;
}

int64_t llama_cassi_qi_state_row_width(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_state_row_width() : 0;
}

float llama_cassi_qi_seam_budget(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_seam_budget() : 0.0f;
}

float llama_cassi_qi_seam_scale(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_seam_scale() : 0.0f;
}

int32_t llama_cassi_qi_graph_nodes(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_graph_node_count() : -1;
}

bool llama_cassi_qi_coupling_set(
        llama_context * ctx,
        uint32_t steps,
        float injection_scale) {
    if (ctx == nullptr) {
        return false;
    }
    ctx->synchronize();
    return ctx->set_cassi_qi_coupling(steps, injection_scale);
}

bool llama_cassi_qi_state_set(
        llama_context * ctx,
        llama_seq_id seq_id,
        const float * data,
        size_t count) {
    if (ctx == nullptr) {
        return false;
    }
    ctx->synchronize();
    return ctx->set_cassi_qi_state(seq_id, data, count);
}

size_t llama_cassi_qi_mode_count(const llama_context * ctx) {
    return ctx != nullptr ? ctx->cassi_qi_mode_count() : 0;
}

bool llama_cassi_qi_mode_bank_set(
        llama_context * ctx,
        const float * data,
        size_t count) {
    if (ctx == nullptr) {
        return false;
    }
    ctx->synchronize();
    return ctx->set_cassi_qi_mode_bank(data, count);
}

bool llama_cassi_qi_state_get(
        llama_context * ctx,
        llama_seq_id seq_id,
        float * data,
        size_t count) {
    if (ctx == nullptr) {
        return false;
    }
    ctx->synchronize();
    return ctx->get_cassi_qi_state(seq_id, data, count);
}

bool llama_cassi_capture_enable(llama_context * ctx) {
    if (ctx == nullptr) {
        return false;
    }
    try {
        ctx->enable_cassi_capture();
    } catch (const std::exception &) {
        return false;
    }
    return ctx->get_cparams().cassi_capture;
}

int32_t llama_cassi_capture_shape(
        const llama_context * ctx,
        int32_t kind,
        uint32_t layer,
        int64_t * shape) {
    if (ctx == nullptr || shape == nullptr) {
        return 0;
    }
    return ctx->cassi_capture_shape(kind, layer, shape);
}

bool llama_cassi_capture_copy(
        llama_context * ctx,
        int32_t kind,
        uint32_t layer,
        float * data,
        size_t count) {
    if (ctx == nullptr || data == nullptr) {
        return false;
    }
    return ctx->cassi_capture_copy(kind, layer, data, count);
}

float llama_cassi_qi_score_token(
        llama_context * ctx,
        llama_seq_id seq_id,
        llama_token token) {
    if (ctx == nullptr) {
        return -INFINITY;
    }
    ctx->synchronize();
    return ctx->score_cassi_qi_token(seq_id, token);
}

bool llama_cassi_qi_score_tokens(
        llama_context * ctx,
        llama_seq_id seq_id,
        const llama_token * tokens,
        float * scores,
        size_t count) {
    if (ctx == nullptr || tokens == nullptr || scores == nullptr) {
        return false;
    }
    ctx->synchronize();
    for (size_t i = 0; i < count; ++i) {
        scores[i] = ctx->score_cassi_qi_token(seq_id, tokens[i]);
    }
    return true;
}

//
// memory
//

void llama_memory_clear(llama_memory_t mem, bool data) {
    if (!mem) {
        return;
    }

    mem->clear(data);
}

bool llama_memory_seq_rm(
        llama_memory_t mem,
          llama_seq_id seq_id,
             llama_pos p0,
             llama_pos p1) {
    if (!mem) {
        return true;
    }

    return mem->seq_rm(seq_id, p0, p1);
}

void llama_memory_seq_cp(
        llama_memory_t mem,
          llama_seq_id seq_id_src,
          llama_seq_id seq_id_dst,
             llama_pos p0,
             llama_pos p1) {
    if (!mem) {
        return;
    }

    mem->seq_cp(seq_id_src, seq_id_dst, p0, p1);
}

void llama_memory_seq_keep(
        llama_memory_t mem,
          llama_seq_id seq_id) {
    if (!mem) {
        return;
    }

    mem->seq_keep(seq_id);
}

void llama_memory_seq_add(
        llama_memory_t mem,
          llama_seq_id seq_id,
             llama_pos p0,
             llama_pos p1,
             llama_pos delta) {
    if (!mem) {
        return;
    }

    mem->seq_add(seq_id, p0, p1, delta);
}

void llama_memory_seq_div(
        llama_memory_t mem,
          llama_seq_id seq_id,
             llama_pos p0,
             llama_pos p1,
                   int d) {
    if (!mem) {
        return;
    }

    mem->seq_div(seq_id, p0, p1, d);
}

llama_pos llama_memory_seq_pos_min(
        llama_memory_t mem,
          llama_seq_id seq_id) {
    if (!mem) {
        return -1;
    }

    return mem->seq_pos_min(seq_id);
}

llama_pos llama_memory_seq_pos_max(
        llama_memory_t mem,
          llama_seq_id seq_id) {
    if (!mem) {
        return -1;
    }

    return mem->seq_pos_max(seq_id);
}

bool llama_memory_can_shift(llama_memory_t mem) {
    if (!mem) {
        return false;
    }

    return mem->get_can_shift();
}

// llama state API

// deprecated
size_t llama_get_state_size(llama_context * ctx) {
    return llama_state_get_size(ctx);
}

// deprecated
size_t llama_copy_state_data(llama_context * ctx, uint8_t * dst) {
    return llama_state_get_data(ctx, dst, -1);
}

// deprecated
size_t llama_set_state_data(llama_context * ctx, const uint8_t * src) {
    return llama_state_set_data(ctx, src, -1);
}

// deprecated
bool llama_load_session_file(llama_context * ctx, const char * path_session, llama_token * tokens_out, size_t n_token_capacity, size_t * n_token_count_out) {
    return llama_state_load_file(ctx, path_session, tokens_out, n_token_capacity, n_token_count_out);
}

// deprecated
bool llama_save_session_file(llama_context * ctx, const char * path_session, const llama_token * tokens, size_t n_token_count) {
    return llama_state_save_file(ctx, path_session, tokens, n_token_count);
}

// Returns the *actual* size of the state.
// Intended to be used when saving to state to a buffer.
size_t llama_state_get_size(llama_context * ctx) {
    return ctx->state_get_size();
}

size_t llama_state_get_data(llama_context * ctx, uint8_t * dst, size_t size) {
    ctx->synchronize();

    return ctx->state_get_data(dst, size);
}

// Sets the state reading from the specified source address
size_t llama_state_set_data(llama_context * ctx, const uint8_t * src, size_t size) {
    ctx->synchronize();

    return ctx->state_set_data(src, size);
}

bool llama_state_load_file(llama_context * ctx, const char * path_session, llama_token * tokens_out, size_t n_token_capacity, size_t * n_token_count_out) {
    ctx->synchronize();

    try {
        return ctx->state_load_file(path_session, tokens_out, n_token_capacity, n_token_count_out);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error loading session file: %s\n", __func__, err.what());
        return false;
    }
}

bool llama_state_save_file(llama_context * ctx, const char * path_session, const llama_token * tokens, size_t n_token_count) {
    ctx->synchronize();

    try {
        return ctx->state_save_file(path_session, tokens, n_token_count);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error saving session file: %s\n", __func__, err.what());
        return false;
    }
}

size_t llama_state_seq_get_size(llama_context * ctx, llama_seq_id seq_id) {
    return llama_state_seq_get_size_ext(ctx, seq_id, 0);
}

size_t llama_state_seq_get_data(llama_context * ctx, uint8_t * dst, size_t size, llama_seq_id seq_id) {
    return llama_state_seq_get_data_ext(ctx, dst, size, seq_id, 0);
}

size_t llama_state_seq_set_data(llama_context * ctx, const uint8_t * src, size_t size, llama_seq_id seq_id) {
    return llama_state_seq_set_data_ext(ctx, src, size, seq_id, 0);
}

size_t llama_state_seq_get_size_ext(llama_context * ctx, llama_seq_id seq_id, llama_state_seq_flags flags) {
    return ctx->state_seq_get_size(seq_id, flags);
}

size_t llama_state_seq_get_data_ext(llama_context * ctx, uint8_t * dst, size_t size, llama_seq_id seq_id, llama_state_seq_flags flags) {
    ctx->synchronize();

    return ctx->state_seq_get_data(seq_id, dst, size, flags);
}
size_t llama_state_seq_set_data_ext(llama_context * ctx, const uint8_t * src, size_t size, llama_seq_id seq_id, llama_state_seq_flags flags) {
    ctx->synchronize();

    return ctx->state_seq_set_data(seq_id, src, size, flags);
}

size_t llama_state_seq_save_file(llama_context * ctx, const char * filepath, llama_seq_id seq_id, const llama_token * tokens, size_t n_token_count) {
    ctx->synchronize();

    try {
        return ctx->state_seq_save_file(seq_id, filepath, tokens, n_token_count);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error saving sequence state file: %s\n", __func__, err.what());
        return 0;
    }
}

size_t llama_state_seq_load_file(llama_context * ctx, const char * filepath, llama_seq_id dest_seq_id, llama_token * tokens_out, size_t n_token_capacity, size_t * n_token_count_out) {
    ctx->synchronize();

    try {
        return ctx->state_seq_load_file(dest_seq_id, filepath, tokens_out, n_token_capacity, n_token_count_out);
    } catch (const std::exception & err) {
        LLAMA_LOG_ERROR("%s: error loading sequence state file: %s\n", __func__, err.what());
        return 0;
    }
}

///

int32_t llama_encode(
        llama_context * ctx,
          llama_batch   batch) {
    const int ret = ctx->encode(batch);
    if (ret != 0) {
        LLAMA_LOG_ERROR("%s: failed to encode, ret = %d\n", __func__, ret);
    }

    return ret;
}

int32_t llama_decode(
        llama_context * ctx,
          llama_batch   batch) {
    const int ret = ctx->decode(batch);
    if (ret != 0 && ret != 1) {
        LLAMA_LOG_ERROR("%s: failed to decode, ret = %d\n", __func__, ret);
    }

    return ret;
}

//
// perf
//

llama_perf_context_data llama_perf_context(const llama_context * ctx) {
    llama_perf_context_data data = {};

    if (ctx == nullptr) {
        return data;
    }

    data = ctx->perf_get_data();

    return data;
}

void llama_perf_context_print(const llama_context * ctx) {
    const auto data = llama_perf_context(ctx);

    const double t_end_ms = 1e-3 * ggml_time_us();

    LLAMA_LOG_INFO("%s:        load time = %10.2f ms\n", __func__, data.t_load_ms);
    LLAMA_LOG_INFO("%s: prompt eval time = %10.2f ms / %5d tokens (%8.2f ms per token, %8.2f tokens per second)\n",
            __func__, data.t_p_eval_ms, data.n_p_eval, data.t_p_eval_ms / data.n_p_eval, 1e3 / data.t_p_eval_ms * data.n_p_eval);
    LLAMA_LOG_INFO("%s:        eval time = %10.2f ms / %5d runs   (%8.2f ms per token, %8.2f tokens per second)\n",
            __func__, data.t_eval_ms, data.n_eval, data.t_eval_ms / data.n_eval, 1e3 / data.t_eval_ms * data.n_eval);
    LLAMA_LOG_INFO("%s:       total time = %10.2f ms / %5d tokens\n", __func__, (t_end_ms - data.t_start_ms), (data.n_p_eval + data.n_eval));
    LLAMA_LOG_INFO("%s:    graphs reused = %10d\n", __func__, data.n_reused);
}

void llama_perf_context_reset(llama_context * ctx) {
    ctx->perf_reset();
}

//
// training
//

bool llama_opt_param_filter_all(const struct ggml_tensor * tensor, void * userdata) {
    GGML_UNUSED(tensor);
    GGML_UNUSED(userdata);
    return true;
}

void llama_opt_init(struct llama_context * ctx, struct llama_model * model, struct llama_opt_params lopt_params) {
    ctx->opt_init(model, lopt_params);
}

void llama_opt_epoch(
        struct llama_context    * ctx,
        ggml_opt_dataset_t        dataset,
        ggml_opt_result_t         result_train,
        ggml_opt_result_t         result_eval,
        int64_t                   idata_split,
        ggml_opt_epoch_callback   callback_train,
        ggml_opt_epoch_callback   callback_eval) {
    ctx->opt_epoch(
        dataset,
        result_train,
        result_eval,
        idata_split,
        callback_train,
        callback_eval);
}

//
// ext
//

llama_memory_breakdown llama_get_memory_breakdown(const struct llama_context * ctx) {
    return ctx->memory_breakdown();
}

llama_context * llama_get_ctx_other(struct llama_context * ctx) {
    return ctx->get_cparams().ctx_other;
}
