#ifndef LLAMA_CASSI_H
#define LLAMA_CASSI_H

#include "llama.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct llama_cassi_context;

enum llama_cassi_teacher_policy {
    LLAMA_CASSI_ADAPTIVE = 0,
    LLAMA_CASSI_ALWAYS   = 1,
    LLAMA_CASSI_NEVER    = 2,
};

enum llama_cassi_route_policy {
    LLAMA_CASSI_AUTO           = 0,
    LLAMA_CASSI_PIPELINE       = 1,
    LLAMA_CASSI_EXACT_PIPELINE = 2,
};

enum llama_cassi_status {
    LLAMA_CASSI_TOKEN     = 0,
    LLAMA_CASSI_DONE      = 1,
    LLAMA_CASSI_CANCELLED = 2,
    LLAMA_CASSI_ERROR     = -1,
};

enum llama_cassi_service_kind {
    LLAMA_CASSI_TEXT      = 0,
    LLAMA_CASSI_EMBED     = 1,
    LLAMA_CASSI_HEAD      = 2,
    LLAMA_CASSI_ATTENTION = 3,
    LLAMA_CASSI_FFN       = 4,
};
enum llama_cassi_sampler_mode {
    LLAMA_CASSI_SAMPLER_GREEDY      = 0,
    LLAMA_CASSI_SAMPLER_CATEGORICAL = 1,
};

struct llama_cassi_sampler_params {
    enum llama_cassi_sampler_mode mode;
    float temperature;
    uint32_t top_k;
    double draw;
};


struct llama_cassi_params {
    uint64_t memory_bytes;
    uint32_t audit_interval;
    enum llama_cassi_teacher_policy teacher_policy;
    enum llama_cassi_route_policy route_policy;
    const char * field_device;
    const char * model_path;
    // Optional caller-verified raw GGUF digest. Read only during llama_cassi_init.
    const uint8_t * model_sha256;
};

struct llama_cassi_token {
    llama_token token;
    uint32_t decision_source;   // 0 field, 1 teacher-guided, 2 exact native pipeline
    uint32_t native_dependency; // 0 none, 1 native services, 2 full teacher
    uint32_t readout_kind;      // 0 exact field, 1 interpolated, 2 guided, 3 exact native
};

struct llama_cassi_stats {
    uint64_t prompt_tokens;
    uint64_t committed_tokens;
    uint64_t field_exact_tokens;
    uint64_t field_interpolated_tokens;
    uint64_t teacher_guided_tokens;
    uint64_t native_service_calls;
    uint64_t full_teacher_queries;
    uint64_t teacher_failures;
    uint64_t teacher_audits;
    uint64_t audit_mismatches;
    uint64_t native_prefill_tokens;
    uint64_t native_context_creations;
    uint64_t native_logits_reads;
    uint64_t native_replay_tokens;
    uint64_t native_decode_tokens;
    uint64_t native_exact_tokens;
    uint64_t native_exact_stages;
    uint64_t native_exact_attention_stages;
    uint64_t native_exact_ffn_stages;
    uint64_t native_sampler_draws;
    uint64_t field_observations;
    uint64_t pending_admission_payload_bytes_peak;
    uint64_t pending_rollback_bytes_peak;
    uint64_t native_ggml_nodes_executed;
    uint64_t native_ggml_nodes_skipped;
    uint64_t native_output_rows_computed;
    uint64_t native_output_rows_skipped;
    uint64_t logical_weight_bytes;
    uint64_t field_steps;
    uint64_t engram_evictions;
    uint64_t field_bytes;
    uint64_t loaded_model_tensor_bytes;
    uint64_t native_cache_bytes_peak;
    uint64_t native_cache_bytes_remaining;
    bool native_nodes_skipped_known;
    double field_ms;
    double native_service_ms;
    double teacher_ms;
    double replay_ms;
    double checkpoint_ms;
    double wall_ms;
};

struct llama_cassi_service_stats {
    uint32_t kind;
    int32_t layer;
    uint64_t computed;
    uint64_t skipped;
    uint64_t logical_weight_bytes;
};

struct llama_cassi_info {
    uint32_t scales;
    uint32_t layers;
    uint32_t embedding_width;
    uint32_t vocabulary_size;
    uint32_t context_limit;
    uint32_t training_context_limit;
    uint64_t modes;
    uint64_t field_bytes;
    uint64_t field_revision;
    uint8_t model_sha256[32];
    uint8_t profile_sha256[32];
    uint8_t field_sha256[32];
};

LLAMA_API struct llama_cassi_params llama_cassi_default_params(void);
LLAMA_API struct llama_cassi_context * llama_cassi_init(
        struct llama_model * model,
        struct llama_context_params native_params,
        struct llama_cassi_params params);
LLAMA_API void llama_cassi_free(struct llama_cassi_context * ctx);

LLAMA_API int32_t llama_cassi_begin(
        struct llama_cassi_context * ctx,
        const llama_token * prompt,
        size_t n_prompt,
        int32_t n_predict);
LLAMA_API enum llama_cassi_status llama_cassi_next(
        struct llama_cassi_context * ctx,
        struct llama_cassi_token * result);
LLAMA_API int32_t llama_cassi_set_sampler(
        struct llama_cassi_context * ctx,
        struct llama_cassi_sampler_params params);
LLAMA_API int32_t llama_cassi_accept(struct llama_cassi_context * ctx, llama_token token);
LLAMA_API int32_t llama_cassi_rollback_accepted(struct llama_cassi_context * ctx);
LLAMA_API int32_t llama_cassi_finish(struct llama_cassi_context * ctx, bool cancelled);
LLAMA_API void llama_cassi_cancel(struct llama_cassi_context * ctx);

LLAMA_API const char * llama_cassi_last_error(const struct llama_cassi_context * ctx);
LLAMA_API void llama_cassi_get_stats(const struct llama_cassi_context * ctx, struct llama_cassi_stats * out);
LLAMA_API int32_t llama_cassi_get_info(struct llama_cassi_context * ctx, struct llama_cassi_info * out);
LLAMA_API size_t llama_cassi_service_stats_count(const struct llama_cassi_context * ctx);
LLAMA_API size_t llama_cassi_service_stats_get(
        const struct llama_cassi_context * ctx,
        struct llama_cassi_service_stats * dst,
        size_t capacity);
LLAMA_API size_t llama_cassi_native_backend_count(const struct llama_cassi_context * ctx);
LLAMA_API size_t llama_cassi_native_backend_name(
        const struct llama_cassi_context * ctx,
        size_t index,
        char * dst,
        size_t capacity);
LLAMA_API size_t llama_cassi_attention_mask_get(
        const struct llama_cassi_context * ctx,
        uint8_t * dst,
        size_t capacity);

LLAMA_API size_t llama_cassi_state_size(struct llama_cassi_context * ctx);
LLAMA_API size_t llama_cassi_state_get(struct llama_cassi_context * ctx, uint8_t * dst, size_t size);
LLAMA_API int32_t llama_cassi_state_set(struct llama_cassi_context * ctx, const uint8_t * src, size_t size);

#ifdef __cplusplus
}
#endif

#endif // LLAMA_CASSI_H
