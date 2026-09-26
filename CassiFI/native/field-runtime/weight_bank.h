#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef _WIN32
#  ifdef CASSIFI_WEIGHT_BANK_BUILD
#    define CASSIFI_WEIGHT_BANK_API __declspec(dllexport)
#  else
#    define CASSIFI_WEIGHT_BANK_API __declspec(dllimport)
#  endif
#else
#  define CASSIFI_WEIGHT_BANK_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct cassifi_weight_bank cassifi_weight_bank_t;
typedef struct cassifi_device_epoch cassifi_device_epoch_t;
typedef struct cassifi_device_tensor cassifi_device_tensor_t;


typedef struct cassifi_weight_tensor_info {
    uint32_t rank;
    int64_t dims[4];
    int32_t ggml_type;
    uint64_t element_count;
    uint64_t byte_size;
} cassifi_weight_tensor_info_t;

/* Return codes: zero is success; negative values are stable failure classes. */
enum {
    CASSIFI_WEIGHT_BANK_OK = 0,
    CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT = -1,
    CASSIFI_WEIGHT_BANK_NOT_FOUND = -2,
    CASSIFI_WEIGHT_BANK_BACKEND_ERROR = -3,
    CASSIFI_WEIGHT_BANK_SHAPE_ERROR = -4,
    CASSIFI_WEIGHT_BANK_IO_ERROR = -5,
    CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE = -6,
    CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED = -7,
    CASSIFI_WEIGHT_BANK_RESOURCE_WAIT = -8,
};

CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_load(
    const char * path, const char * backend, int32_t threads, cassifi_weight_bank_t ** out_bank);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_vulkan_memory(
    size_t * out_free_bytes, size_t * out_total_bytes);
CASSIFI_WEIGHT_BANK_API void cassifi_weight_bank_close(cassifi_weight_bank_t * bank);
CASSIFI_WEIGHT_BANK_API const char * cassifi_weight_bank_last_error(const cassifi_weight_bank_t * bank);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_tensor_info(
    const cassifi_weight_bank_t * bank, const char * name, cassifi_weight_tensor_info_t * out_info);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_read_vector(
    const cassifi_weight_bank_t * bank, const char * name, float * out, size_t capacity, size_t * out_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_read_embedding(
    const cassifi_weight_bank_t * bank, const char * name, uint64_t token, float * out, size_t capacity, size_t * out_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_matvec(
    const cassifi_weight_bank_t * bank, const char * name, const float * input, size_t input_count,
    float * output, size_t output_capacity, size_t * output_count, int32_t expert);
/* Multiply one dense or selected-expert matrix by a row-major batch of inputs.
 * Inputs and outputs are [batch, width]; output_count is batch * output_width.
 */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_matvec_batch(
    const cassifi_weight_bank_t * bank, const char * name,
    const float * inputs, size_t batch_count, size_t input_width,
    float * outputs, size_t output_capacity, size_t * output_count,
    int32_t expert);
/* Cross-expert batch: one native call for rows that name different expert
 * slices of the same tensor. experts is [batch] with -1 for dense tensors;
 * every other value must be a valid expert of an expert tensor. Inputs and
 * outputs are [batch, width]; output_count is batch * output_width. Rows are
 * grouped by expert internally so same-expert rows still share one GGML plan.
 */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_matvec_batch_experts(
    const cassifi_weight_bank_t * bank, const char * name,
    const float * inputs, size_t batch_count, size_t input_width,
    const int32_t * experts,
    float * outputs, size_t output_capacity, size_t * output_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_matvec_many(
    const cassifi_weight_bank_t * bank,
    const char * const * names, const int32_t * experts, size_t request_count,
    const float * input, size_t input_count,
    float * const * outputs, const size_t * output_capacities, size_t * output_counts);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_read_tensor_f32(
    const cassifi_weight_bank_t * bank, const char * name, float * out, size_t capacity, size_t * out_count);

/* Expert residency is explicit. matvec may demand-prefetch an absent slice. */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_prefetch(
    cassifi_weight_bank_t * bank, const char * name, int32_t expert);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_evict(
    cassifi_weight_bank_t * bank, const char * name, int32_t expert);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_residency(
    const cassifi_weight_bank_t * bank, const char * name, int32_t expert,
    int32_t * resident, uint64_t * bytes, uint64_t * hits, uint64_t * misses);

/*
 * Device-epoch lifetime:
 * - begin is supported only for a Vulkan weight bank and allocates the four
 *   plane-major F32 field planes on that bank's exact GGML backend/device.
 * - Activation tensors are opaque GGML-owned device values, not Vulkan handles.
 *   Operations require values from the same open epoch and remain device-side.
 * - Each exchange returns input/output, actual GPU F32 scale, and pre-addition
 *   delta captures as device tensors; download them together at stage end.
 * - download_many, snapshot and finish are explicit host-readback boundaries.
 *   Snapshot leaves its source epoch open and unchanged; a caller can use the
 *   returned plane copy to begin an independent candidate epoch.
 * - Call close on success or abort; close releases the candidate planes and
 *   every remaining activation buffer without publishing owner state. Closing
 *   the weight bank also invalidates and releases all of its live epochs.
 * - Returned tensor wrappers must be released. They become unusable after
 *   epoch/bank close, but may safely be released afterward.
 */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_epoch_begin(
    cassifi_weight_bank_t * bank, const float * initial_planes, size_t plane_value_count,
    size_t mode_count, int32_t gain_ppm, cassifi_device_epoch_t ** out_epoch);
/* Read a live epoch's planes without finalizing or changing that epoch. */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_epoch_snapshot(
    cassifi_device_epoch_t * epoch, float * planes, size_t plane_capacity, size_t * out_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_epoch_finish(
    cassifi_device_epoch_t * epoch, float * final_planes, size_t plane_capacity, size_t * out_count);
CASSIFI_WEIGHT_BANK_API void cassifi_weight_bank_device_epoch_close(cassifi_device_epoch_t * epoch);

CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_tensor_upload(
    cassifi_device_epoch_t * epoch, const float * values, size_t count, cassifi_device_tensor_t ** out_tensor);
/* Return a zero-copy same-epoch F32 subvector view (e.g. packed gate/up halves). */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_tensor_view(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    size_t element_offset, size_t count, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_tensor_count(
    const cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * tensor, size_t * out_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_tensor_download(
    const cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * tensor,
    float * out, size_t capacity, size_t * out_count);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_tensor_download_many(
    const cassifi_device_epoch_t * epoch,
    const cassifi_device_tensor_t * const * tensors, size_t tensor_count,
    float * out, size_t capacity, size_t * out_count,
    size_t * value_offsets, size_t * value_counts);
CASSIFI_WEIGHT_BANK_API void cassifi_weight_bank_device_tensor_release(cassifi_device_tensor_t * tensor);
CASSIFI_WEIGHT_BANK_API void cassifi_weight_bank_device_tensor_release_many(
    cassifi_device_tensor_t * const * tensors, size_t tensor_count);

CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_embedding(
    cassifi_device_epoch_t * epoch, const char * name, uint64_t token,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_matvec(
    cassifi_device_epoch_t * epoch, const char * name, const cassifi_device_tensor_t * input,
    int32_t expert, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_matvec_many(
    cassifi_device_epoch_t * epoch,
    const char * const * names, const int32_t * experts, size_t request_count,
    const cassifi_device_tensor_t * input, cassifi_device_tensor_t ** out_tensors);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_exchange(
    cassifi_device_epoch_t * epoch, const char * site, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_input_capture, cassifi_device_tensor_t ** out_tensor,
    cassifi_device_tensor_t ** out_scale, cassifi_device_tensor_t ** out_delta);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_silu(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_sigmoid(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_scale(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input, float scale,
    cassifi_device_tensor_t ** out_tensor);
/* Multiplication also accepts a one-element right operand; addition requires equal widths. */
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_mul(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_add(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_low_rank_affine(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    const char * method_id, const float * a, size_t input_width, size_t rank,
    const float * b, size_t output_width, const float * bias,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_concat(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_norm_rows(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input, size_t row_width,
    float epsilon, int32_t sum_squares, const char * weight_name,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_mul_rows(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    const cassifi_device_tensor_t * row_scales, size_t row_width,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_exp_clipped(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    float lower, float upper, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_softplus(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_softmax(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_positive_normalize(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_recurrent_conv(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * history,
    const char * kernel_name, size_t channels, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_recurrent_predict(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * keys, size_t value_heads, size_t key_heads,
    size_t value_dim, size_t key_dim, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_recurrent_update(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * keys, const cassifi_device_tensor_t * deltas,
    size_t value_heads, size_t key_heads, size_t value_dim, size_t key_dim,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_recurrent_readout(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * queries, size_t value_heads, size_t key_heads,
    size_t value_dim, size_t key_dim, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_rope(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    int64_t position, const int32_t * sections, size_t section_count, double base,
    cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_attention_scores(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * query,
    const cassifi_device_tensor_t * key_cache, size_t kv_head, size_t kv_heads,
    size_t head_dim, float scale, cassifi_device_tensor_t ** out_tensor);
CASSIFI_WEIGHT_BANK_API int cassifi_weight_bank_device_attention_context(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * probabilities,
    const cassifi_device_tensor_t * value_cache, size_t kv_head, size_t kv_heads,
    size_t value_dim, cassifi_device_tensor_t ** out_tensor);

#ifdef __cplusplus
}
#endif
