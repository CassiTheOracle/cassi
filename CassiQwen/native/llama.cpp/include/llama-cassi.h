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
// Exact one-draw speculative sample for a deterministic proposal q = delta(d).
// Categorical mode accepts d with probability p(d), then maps the same uniform
// draw onto the filtered target law with d removed on rejection. Greedy mode
// compares against its one-hot target law. The helper uses the same top-k and
// temperature filtering as the exact native sampler.
struct llama_cassi_q_delta_result {
    bool accepted;
    llama_token token;
    double target_probability;
    uint32_t draws_consumed;
};
LLAMA_API int32_t llama_cassi_sample_q_delta(
        const float * logits,
        size_t logits_count,
        llama_token draft_token,
        struct llama_cassi_sampler_params sampler,
        struct llama_cassi_q_delta_result * out);

// Hash the canonical graph-site sampler JSON from native tuple values.
// Temperature is float32; draw retains the C API's double precision.
LLAMA_API int32_t llama_cassi_sampler_sha256(
        struct llama_cassi_sampler_params params,
        char out_sha256[65]);


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
    uint64_t native_exact_head_groups;
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
enum llama_cassi_graph_site_candidate_verb {
    LLAMA_CASSI_GRAPH_SITE_OBSERVE = 0,
    LLAMA_CASSI_GRAPH_SITE_REPLACE = 1,
    LLAMA_CASSI_GRAPH_SITE_ASSIST  = 2,
    LLAMA_CASSI_GRAPH_SITE_PROPOSE = 3,
};

struct llama_cassi_graph_site_candidate_guard {
    // Stable owner ticket identity; the context copies every pointer before returning.
    const char * candidate_id;
    uint32_t verb;
    const char * native_preflight_sha256;
    const char * native_predecessor_sha256;
    const char * owner_snapshot_sha256;
    const char * field_epoch_sha256;
    const float * input_support_anchor;
    size_t input_support_anchor_count;
    float input_support_radius;
    float input_support_anchor_norm;
    const int32_t * expected_expert_ids;
    size_t expected_expert_ids_count;
};

enum llama_cassi_graph_site_stage_kind {
    LLAMA_CASSI_GRAPH_SITE_STAGE_EMBED     = 1,
    LLAMA_CASSI_GRAPH_SITE_STAGE_HEAD      = 2,
    LLAMA_CASSI_GRAPH_SITE_STAGE_ATTENTION = 3,
    LLAMA_CASSI_GRAPH_SITE_STAGE_FFN       = 4,
};

struct llama_cassi_graph_site_stage_event {
    uint32_t kind;
    int32_t layer;
};

struct llama_cassi_graph_site_candidate_receipt {
    bool attempted;
    bool admitted;
    uint64_t owner_generation;
    uint64_t method_generation;
    uint64_t operators_omitted;
    uint64_t weights_omitted;
    uint64_t weight_bytes_omitted;
    uint64_t transfer_bytes_omitted;
    double added_flops;
    char candidate_id[65];
    char request_sha256[65];
    // True when the ticket deferred its request digest until input measurement;
    // on an attempted receipt, request_sha256 then carries that measured digest.
    bool request_sha256_pending;
    char invocation_sha256[65];
    char candidate_sha256[65];
    char input_sha256[65];
    char output_sha256[65];
    char predecessor_sha256[65];
    char successor_sha256[65];
    char native_predecessor_sha256[65];
    char native_successor_sha256[65];
    char sampler_sha256[65];
    char successor_state_json[2048];
    // Borrowed measured expert routing evidence; valid until the next graph-site
    // result mutation, a new session begin, or context destruction.
    const int32_t * actual_expert_ids;
    size_t actual_expert_ids_count;
    // Borrowed successful exact-native events in traversal order; valid until the
    // next graph-site result mutation, a new session begin, or context destruction.
    const struct llama_cassi_graph_site_stage_event * stage_events;
    size_t stage_event_count;
    char refusal[128];
};

enum llama_cassi_graph_site_descriptor_kind {
    LLAMA_CASSI_SITE_EXPERTS            = 1,
    LLAMA_CASSI_SITE_RECURRENT          = 2,
    LLAMA_CASSI_SITE_ATTENTION_MEMORY   = 3,
    LLAMA_CASSI_SITE_DEPTH              = 4,
    LLAMA_CASSI_SITE_DRAFT               = 5,
    LLAMA_CASSI_SITE_EXECUTION_CHOICE   = 6,
};

struct llama_cassi_graph_site_descriptor {
    uint32_t kind;
    bool supported;
    int32_t layer;
    uint32_t input_width;
    uint32_t output_width;
    char stage[64];
    char site[64];
    char specialist[64];
    char input_tensor[64];
    char output_tensor[64];
    char dependencies_json[1024];
    char refusal[128];
};

struct llama_cassi_graph_site_preflight_result {
    uint32_t version;
    bool ready;
    int32_t native_seq_id;
    llama_pos next_position;
    uint32_t site_count;
    enum llama_cassi_sampler_mode sampler_mode;
    float sampler_temperature;
    uint32_t sampler_top_k;
    double sampler_draw;
    char sampler_sha256[65];
    char task_id[128];
    char sequence_id[128];
    char model_sha256[65];
    char source_sha256[65];
    char tokenizer_sha256[65];
    char predecessor_sha256[65];
    char native_field_epoch_sha256[65];
    char native_preflight_sha256[65];
    char refusal[128];
};

// Preflight is called after llama_cassi_begin and before llama_cassi_next.
// It initializes (but does not advance) the native service context, reports
// the exact next sequence position and hashes its serialized native state.
// `ready` is true only at a one-token service boundary; candidate admission
// additionally requires a supported graph-site descriptor.
// `sites` receives the planned Qwen graph-site descriptors for that position.
// The return value is the full descriptor count, even if capacity is smaller.
LLAMA_API size_t llama_cassi_graph_site_preflight(
        struct llama_cassi_context * ctx,
        const char * task_id,
        const char * sequence_id,
        struct llama_cassi_graph_site_preflight_result * out,
        struct llama_cassi_graph_site_descriptor * sites,
        size_t site_capacity);
// Explicit upcoming sampler variant: binds the supplied tuple without changing
// the accepted sampler state.
LLAMA_API size_t llama_cassi_graph_site_preflight_with_sampler(
        struct llama_cassi_context * ctx,
        const char * task_id,
        const char * sequence_id,
        struct llama_cassi_sampler_params upcoming_sampler,
        struct llama_cassi_graph_site_preflight_result * out,
        struct llama_cassi_graph_site_descriptor * sites,
        size_t site_capacity);

LLAMA_API bool llama_cassi_context_graph_site_candidate_set(
        struct llama_cassi_context * ctx,
        const llama_cassi_graph_site_candidate * candidate,
        const struct llama_cassi_graph_site_candidate_guard * guard);
LLAMA_API void llama_cassi_context_graph_site_candidate_clear(
        struct llama_cassi_context * ctx,
        const char * candidate_id);
LLAMA_API bool llama_cassi_context_graph_site_candidate_get_result(
        const struct llama_cassi_context * ctx,
        struct llama_cassi_graph_site_candidate_receipt * result);
// Read the post-next, pre-accept native sequence state and staged sampler hash.
// This is read-only and is valid only while a token transaction is pending.
LLAMA_API int32_t llama_cassi_context_provisional_state_sha256(
        const struct llama_cassi_context * ctx,
        char out_sha256[65]);


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
// Discard the staged upcoming sampler tuple without changing the accepted tuple.
// Only valid while the exact pipeline is idle or ready and no candidate is pending.
LLAMA_API int32_t llama_cassi_sampler_discard(struct llama_cassi_context * ctx);
LLAMA_API int32_t llama_cassi_accept(struct llama_cassi_context * ctx, llama_token token);
// Discard an unaccepted exact-pipeline prediction and restore its native
// pre-input state. The staged sampler is discarded; candidate clearing remains
// an independent operation.
LLAMA_API int32_t llama_cassi_discard_pending(struct llama_cassi_context * ctx);
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

// Group graph-site candidates are not accepted by this ABI. Each service stage
// currently has one graph candidate slot and one whole-token rollback boundary.
// ---------------------------------------------------------------------------
// Multi-row group execution (exact pipeline only).
//
// One llama_cassi_context created with native_params.n_seq_max > 1 becomes a
// shared weight-bank resident group host: the native service context holds one
// KV/GDN slot per sequence and group stages bind n_rows token rows at once in a
// single ubatch. Rows identify themselves by sequence id 0..n_rows-1; row order
// in every stage tensor is the row order given at llama_cassi_group_open.
// The legacy single-token API above stays byte-identical on contexts created
// with n_seq_max == 1; the two API families must not be mixed on one context.
//
// A group stage round walks the pipeline stage by stage (caller-driven):
//   group_open     -> opens the round and the native batch transaction, then
//                     applies the fused embedding stage per row
//   group_stage    -> applies one stage (ATTENTION/FFN) to all rows at once;
//                     `input` is [width, n_rows] row-major F32 host data
//                     (row-major: element(row * width + col)), `out` receives
//                     [out_width, n_rows] in the same order
//   group_sample   -> consumes the final [width, n_rows] residual, applies
//                     the fused HEAD stage, and samples one token per row
//                     with that row's sampler (each row carries its own
//                     llama_cassi_sampler_params); per-row exact result
//   group_commit   -> advances every row by one step (per-sequence cursors
//                     and statistics); the round is complete
//   group_cancel   -> group-boundary fence: discards the active transaction
//                     WITHOUT advancing any sequence, so the whole round can
//                     be replayed identically
// Caller responsibilities: per-view token history/rollback are external (the
// caller owns view state); llama-cassi tracks only shared native per-sequence
// position cursors and stages. group_open with n_rows == 0, row counts other
// than the context capacity, or repeating a sequence within a round fails
// cleanly with the context error set; the legacy single-token pipeline of a
// group host uses sequence 0 and is legal between group rounds.

enum llama_cassi_group_state {
    LLAMA_CASSI_GROUP_IDLE    = 0,
    LLAMA_CASSI_GROUP_STAGED  = 1, // rows are in the pipeline after embedding
    LLAMA_CASSI_GROUP_SAMPLED = 2, // head logits applied, tokens decided
    LLAMA_CASSI_GROUP_FAILED  = 3,
};

struct llama_cassi_group_row {
    llama_token token;   // next token of this row for the round (prompt or caller-decoded)
    llama_pos   pos;     // shared-model service position for this row's sequence
    struct llama_cassi_sampler_params sampler; // per-row sampling identity at group_sample
};

LLAMA_API int32_t llama_cassi_group_open(
        struct llama_cassi_context * ctx,
        const struct llama_cassi_group_row * rows,
        uint32_t n_rows,
        float * embed_out,
        uint32_t embed_width,
        uint32_t embed_capacity);
LLAMA_API enum llama_cassi_group_state llama_cassi_group_state_get(
        const struct llama_cassi_context * ctx);
LLAMA_API uint32_t llama_cassi_group_rows(const struct llama_cassi_context * ctx);
LLAMA_API uint32_t llama_cassi_group_capacity(const struct llama_cassi_context * ctx);
LLAMA_API int32_t llama_cassi_group_stage(
        struct llama_cassi_context * ctx,
        enum llama_cassi_service_kind kind,
        int32_t layer,
        const float * input,
        uint32_t width,
        float * out,
        uint32_t out_width,
        uint32_t out_capacity);
LLAMA_API int32_t llama_cassi_group_sample(
        struct llama_cassi_context * ctx,
        const float * residual,
        uint32_t width,
        llama_token * tokens_out,
        uint32_t n_rows);
LLAMA_API int32_t llama_cassi_group_commit(struct llama_cassi_context * ctx);
LLAMA_API int32_t llama_cassi_group_cancel(struct llama_cassi_context * ctx);
// Group churn: wipe row's sequence KV and reset its next service position to
// 0 so a rejoining seat member replays from position 0. Valid only while the
// group round is idle (between llama_cassi_group_commit/cancel and the next
// llama_cassi_group_open).
LLAMA_API int32_t llama_cassi_group_row_reset(struct llama_cassi_context * ctx, uint32_t row);

#define LLAMA_CASSI_MAX_DRAFT_TOKENS 8u

struct llama_cassi_draft_verify_request {
    const llama_token * draft_tokens;
    const double * proposal_probabilities; // q_i(d_i); deterministic proposals require exactly 1
    uint32_t draft_count;
    const struct llama_cassi_sampler_params * target_samplers; // one tuple for p_0..p_K
    size_t target_sampler_count;
    const char * task_id;
    const char * sequence_id;
    const char * native_operation_id;
    const char * proposal_sha256;
    const char * owner_predecessor_sha256;
    const char * sampler_sha256; // canonical digest of the complete p_0..p_K sampler sequence
};

struct llama_cassi_draft_verify_receipt {
    uint32_t version;
    uint32_t draft_count;
    uint32_t accepted_count;
    uint32_t output_count;
    uint32_t retained_input_count;
    uint32_t sampler_draws_consumed;
    bool rejected;
    bool bonus;
    llama_token output_tokens[LLAMA_CASSI_MAX_DRAFT_TOKENS + 1];
    char task_id[128];
    char sequence_id[128];
    char native_operation_id[513];
    char proposal_sha256[65];
    char owner_predecessor_sha256[65];
    char model_sha256[65];
    char sampler_sha256[65];
    char native_predecessor_sha256[65];
    char native_successor_sha256[65];
    char receipt_sha256[65];
    uint64_t native_exact_stages;
    uint64_t native_exact_attention_stages;
    uint64_t native_exact_ffn_stages;
    uint64_t native_exact_head_groups;
};

// Exact single-sequence speculative verification. The context must be in the
// opt-in verifier mode with enough native ubatch and recurrent prefix rollback
// capacity; the legacy one-token API and graph-site candidate flow stay
// unchanged. Each q_i is the deterministic point mass at draft_tokens[i].
// Success leaves a provisional accepted-prefix state: commit or discard it
// exactly once with the returned receipt hash.
LLAMA_API int32_t llama_cassi_verify_draft(
        struct llama_cassi_context * ctx,
        const struct llama_cassi_draft_verify_request * request,
        struct llama_cassi_draft_verify_receipt * receipt);
LLAMA_API int32_t llama_cassi_verify_commit(
        struct llama_cassi_context * ctx,
        const char receipt_sha256[65]);
LLAMA_API int32_t llama_cassi_verify_discard(
        struct llama_cassi_context * ctx,
        const char receipt_sha256[65]);

LLAMA_API size_t llama_cassi_state_size(struct llama_cassi_context * ctx);
LLAMA_API size_t llama_cassi_state_get(struct llama_cassi_context * ctx, uint8_t * dst, size_t size);
LLAMA_API int32_t llama_cassi_state_set(struct llama_cassi_context * ctx, const uint8_t * src, size_t size);

#ifdef __cplusplus
}
#endif

#endif // LLAMA_CASSI_H
