#include "weight_bank.h"

#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml.h"
#include "gguf.h"
#ifdef CASSIFI_WEIGHT_BANK_HAS_VULKAN
#include "ggml-vulkan.h"
#endif

#include <algorithm>
#include <array>
#include <charconv>
#include <cmath>
#include <cstring>
#include <exception>
#include <fstream>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <filesystem>
 

#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr size_t kContextBytes = 64U * 1024U;

bool checked_add(size_t a, size_t b, size_t & out) {
    if (b > std::numeric_limits<size_t>::max() - a) return false;
    out = a + b;
    return true;
}

// Multiply-accumulate work one more CPU thread must receive before it saves
// more arithmetic than its wake-up and barrier synchronization cost.
constexpr double kCpuWorkPerThread = 16.0 * 1024.0 * 1024.0;

// Runs `graph` on `backend`. A CPU backend gets only as many of its
// `max_threads` as the graph's arithmetic can use: a decode-step projection
// finishes on one thread before eight threads could all be scheduled, while
// the vocabulary head spreads across all of them. Each output element is
// computed by exactly one thread, so the result is identical for any count.
ggml_status compute_graph(ggml_backend_t backend, ggml_cgraph * graph, int32_t max_threads) {
    if (ggml_backend_is_cpu(backend)) {
        double work = 0.0;
        const int nodes = ggml_graph_n_nodes(graph);
        for (int i = 0; i < nodes; ++i) {
            const ggml_tensor * node = ggml_graph_node(graph, i);
            const double elements = static_cast<double>(ggml_nelements(node));
            const bool product = node->op == GGML_OP_MUL_MAT || node->op == GGML_OP_MUL_MAT_ID;
            work += product ? elements * static_cast<double>(node->src[0]->ne[0]) : elements;
        }
        const double limit = static_cast<double>(std::max<int32_t>(max_threads, 1));
        const double wanted = std::clamp(std::ceil(work / kCpuWorkPerThread), 1.0, limit);
        ggml_backend_cpu_set_n_threads(backend, static_cast<int>(wanted));
    }
    return ggml_backend_graph_compute(backend, graph);
}

bool checked_mul(size_t a, size_t b, size_t & out) {
    if (a != 0 && b > std::numeric_limits<size_t>::max() / a) return false;
    out = a * b;
    return true;
}

class FileBacking {
public:
    ~FileBacking() { reset(); }
    FileBacking() = default;
    FileBacking(const FileBacking &) = delete;
    FileBacking & operator=(const FileBacking &) = delete;

    bool load(const char * path) {
        reset();
#ifdef _WIN32
        handle_ = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (handle_ != INVALID_HANDLE_VALUE) {
            LARGE_INTEGER length{};
            if (GetFileSizeEx(handle_, &length) && length.QuadPart > 0 &&
                static_cast<unsigned long long>(length.QuadPart) <= std::numeric_limits<size_t>::max()) {
                size_ = static_cast<size_t>(length.QuadPart);
                mapping_ = CreateFileMappingA(handle_, nullptr, PAGE_READONLY, 0, 0, nullptr);
                if (mapping_ != nullptr) {
                    data_ = static_cast<const uint8_t *>(MapViewOfFile(mapping_, FILE_MAP_READ, 0, 0, 0));
                    if (data_ != nullptr) return true;
                }
            }
            reset();
        }
#else
        const int fd = open(path, O_RDONLY);
        if (fd >= 0) {
            struct stat st{};
            if (fstat(fd, &st) == 0 && st.st_size > 0 && static_cast<uint64_t>(st.st_size) <= std::numeric_limits<size_t>::max()) {
                size_ = static_cast<size_t>(st.st_size);
                data_ = static_cast<const uint8_t *>(mmap(nullptr, size_, PROT_READ, MAP_PRIVATE, fd, 0));
                close(fd);
                if (data_ != MAP_FAILED) {
                    mapped_ = true;
                    return true;
                }
                data_ = nullptr;
            } else {
                close(fd);
            }
        }
#endif
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file) return false;
        const std::streamoff end = file.tellg();
        if (end <= 0 || static_cast<uint64_t>(end) > std::numeric_limits<size_t>::max()) return false;
        fallback_.resize(static_cast<size_t>(end));
        file.seekg(0, std::ios::beg);
        if (!file.read(reinterpret_cast<char *>(fallback_.data()), end)) {
            fallback_.clear();
            return false;
        }
        data_ = fallback_.data();
        size_ = fallback_.size();
        return true;
    }

    const uint8_t * data() const noexcept { return data_; }
    size_t size() const noexcept { return size_; }

private:
    void reset() noexcept {
#ifdef _WIN32
        if (data_ != nullptr && mapping_ != nullptr) UnmapViewOfFile(data_);
        if (mapping_ != nullptr) CloseHandle(mapping_);
        if (handle_ != INVALID_HANDLE_VALUE) CloseHandle(handle_);
        mapping_ = nullptr;
        handle_ = INVALID_HANDLE_VALUE;
#else
        if (mapped_ && data_ != nullptr) munmap(const_cast<uint8_t *>(data_), size_);
        mapped_ = false;
#endif
        data_ = nullptr;
        size_ = 0;
        fallback_.clear();
    }

    const uint8_t * data_ = nullptr;
    size_t size_ = 0;
    std::vector<uint8_t> fallback_;
#ifdef _WIN32
    HANDLE handle_ = INVALID_HANDLE_VALUE;
    HANDLE mapping_ = nullptr;
#else
    bool mapped_ = false;
#endif
};

struct MatvecPlan {

    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_tensor * input = nullptr;
    ggml_tensor * result = nullptr;
    ggml_cgraph * graph = nullptr;
    ggml_tensor * matrix = nullptr;
    size_t cols = 0;
    size_t rows = 0;
    size_t batch_count = 0;

    MatvecPlan() = default;
    MatvecPlan(const MatvecPlan &) = delete;
    MatvecPlan & operator=(const MatvecPlan &) = delete;
    ~MatvecPlan() { reset(); }

    void reset() noexcept {
        if (buffer != nullptr) {
            ggml_backend_buffer_free(buffer);
            buffer = nullptr;
        }
        if (context != nullptr) {
            ggml_free(context);
            context = nullptr;
        }
        input = nullptr;
        result = nullptr;
        graph = nullptr;
        matrix = nullptr;
        cols = 0;
        rows = 0;
        batch_count = 0;
    }
};

struct GroupedMatvecPlan {
    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_tensor * input = nullptr;
    ggml_cgraph * graph = nullptr;
    std::vector<ggml_tensor *> results;

    GroupedMatvecPlan() = default;
    GroupedMatvecPlan(const GroupedMatvecPlan &) = delete;
    GroupedMatvecPlan & operator=(const GroupedMatvecPlan &) = delete;
    ~GroupedMatvecPlan() { reset(); }

    void reset() noexcept {
        if (buffer != nullptr) {
            ggml_backend_buffer_free(buffer);
            buffer = nullptr;
        }
        if (context != nullptr) {
            ggml_free(context);
            context = nullptr;
        }
        input = nullptr;
        graph = nullptr;
        results.clear();
    }
};


struct ExpertSlice {
    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_tensor * tensor = nullptr;
    std::unordered_map<size_t, std::unique_ptr<MatvecPlan>> batch_plans;
    std::unique_ptr<MatvecPlan> plan;

    ExpertSlice() = default;
    ExpertSlice(const ExpertSlice &) = delete;
    ExpertSlice & operator=(const ExpertSlice &) = delete;
    ExpertSlice(ExpertSlice && other) noexcept
        : context(other.context),
          buffer(other.buffer),
          tensor(other.tensor),
          batch_plans(std::move(other.batch_plans)),
          plan(std::move(other.plan)) {
        other.context = nullptr;
        other.buffer = nullptr;
        other.tensor = nullptr;
    }
    ExpertSlice & operator=(ExpertSlice && other) noexcept {
        if (this != &other) {
            reset();
            context = other.context;
            buffer = other.buffer;
            tensor = other.tensor;
            batch_plans = std::move(other.batch_plans);
            plan = std::move(other.plan);
            other.context = nullptr;
            other.buffer = nullptr;
            other.tensor = nullptr;
        }
        return *this;
    }
    ~ExpertSlice() { reset(); }

    void reset() noexcept {
        batch_plans.clear();
        plan.reset();
        if (buffer != nullptr) {
            ggml_backend_buffer_free(buffer);
            buffer = nullptr;
        }
        if (context != nullptr) {
            ggml_free(context);
            context = nullptr;
        }
        tensor = nullptr;
    }
};

struct TensorEntry {
    ggml_tensor * tensor = nullptr;
    size_t source_offset = 0;
    size_t source_size = 0;
    bool expert = false;
    cassifi_weight_tensor_info_t info{};
    std::unordered_map<int32_t, ExpertSlice> slices;
    std::unordered_map<size_t, std::unique_ptr<MatvecPlan>> dense_batch_plans;
    std::unique_ptr<MatvecPlan> dense_plan;
    std::unordered_map<int32_t, uint64_t> hits;
    std::unordered_map<int32_t, uint64_t> misses;
};

class WeightBank;
struct DeviceEpochState;

struct DeviceTensorValue {
    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_tensor * tensor = nullptr;
    size_t count = 0;
    std::shared_ptr<DeviceTensorValue> parent;
    std::weak_ptr<DeviceEpochState> epoch;

    DeviceTensorValue() = default;
    DeviceTensorValue(const DeviceTensorValue &) = delete;
    DeviceTensorValue & operator=(const DeviceTensorValue &) = delete;
    ~DeviceTensorValue();
    void reset() noexcept;
};

struct AffineCoefficients {
    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_tensor * a = nullptr;
    ggml_tensor * b = nullptr;
    ggml_tensor * bias = nullptr;
    std::vector<float> a_values;
    std::vector<float> b_values;
    std::vector<float> bias_values;
    size_t input_width = 0;
    size_t rank = 0;
    size_t output_width = 0;

    AffineCoefficients() = default;
    AffineCoefficients(const AffineCoefficients &) = delete;
    AffineCoefficients & operator=(const AffineCoefficients &) = delete;
    ~AffineCoefficients() { reset(); }
    void reset() noexcept {
        if (buffer != nullptr) ggml_backend_buffer_free(std::exchange(buffer, nullptr));
        if (context != nullptr) ggml_free(std::exchange(context, nullptr));
        a = b = bias = nullptr;
    }
};

struct DeviceEpochState {
    WeightBank * owner = nullptr;
    ggml_backend_t backend = nullptr;
    int32_t threads = 1;
    ggml_context * field_context = nullptr;
    ggml_backend_buffer_t field_buffer = nullptr;
    std::unordered_map<std::string, std::unique_ptr<AffineCoefficients>> affine_coefficients;
    std::array<ggml_tensor *, 4> planes{};
    std::vector<std::weak_ptr<DeviceTensorValue>> values;
    std::unordered_map<size_t, std::vector<ggml_backend_buffer_t>> spare_buffers;
    size_t spare_bytes = 0;
    size_t mode_count = 0;
    int32_t gain_ppm = 0;
    bool open = true;
    bool finished = false;

    DeviceEpochState() = default;
    DeviceEpochState(const DeviceEpochState &) = delete;
    DeviceEpochState & operator=(const DeviceEpochState &) = delete;
    ~DeviceEpochState() { close(); }
    void recycle(size_t count, ggml_backend_buffer_t buffer) noexcept {
        const size_t bytes = ggml_backend_buffer_get_size(buffer);
        constexpr size_t kMaxSpareBytes = 64U * 1024U * 1024U;
        if (open && bytes <= 1024U * 1024U && bytes <= kMaxSpareBytes - spare_bytes) {
            try {
                spare_buffers[count].push_back(buffer);
                spare_bytes += bytes;
                return;
            } catch (const std::exception &) {
                // Resource pressure must never make a tensor release throw.
            }
        }
        ggml_backend_buffer_free(buffer);
    }


    void close() noexcept {
        if (!open && owner == nullptr) return;
        open = false;
        finished = true;
        for (auto it = values.rbegin(); it != values.rend(); ++it) {
            if (auto value = it->lock()) value->reset();
        }
        affine_coefficients.clear();
        values.clear();
        for (auto & [count, buffers] : spare_buffers) {
            for (auto * buffer : buffers) ggml_backend_buffer_free(buffer);
        }
        spare_buffers.clear();
        spare_bytes = 0;
        if (field_buffer != nullptr) {
            ggml_backend_buffer_free(field_buffer);
            field_buffer = nullptr;
        }
        if (field_context != nullptr) {
            ggml_free(field_context);
            field_context = nullptr;
        }
        planes.fill(nullptr);
        backend = nullptr;
        owner = nullptr;
        mode_count = 0;
    }
};

DeviceTensorValue::~DeviceTensorValue() { reset(); }

void DeviceTensorValue::reset() noexcept {
    if (buffer != nullptr) {
        auto * released = std::exchange(buffer, nullptr);
        if (auto owner = epoch.lock()) owner->recycle(count, released);
        else ggml_backend_buffer_free(released);
    }
    if (context != nullptr) {
        ggml_free(context);
        context = nullptr;
    }
    tensor = nullptr;
    count = 0;
    parent.reset();
}

class WeightBank {
public:
    static int load(const char * path, const char * backend_name, int32_t threads, WeightBank ** out);

    int tensor_info(const char * name, cassifi_weight_tensor_info_t * out) const;
    int read_vector(const char * name, float * out, size_t capacity, size_t * out_count) const;
    int read_tensor_f32(const char * name, float * out, size_t capacity, size_t * out_count) const;
    int read_embedding(const char * name, uint64_t token, float * out, size_t capacity, size_t * out_count) const;
    int matvec(const char * name, const float * input, size_t input_count,
               float * output, size_t output_capacity, size_t * output_count,
               int32_t expert);
    int matvec_batch(const char * name, const float * inputs, size_t batch_count,
                     size_t input_width, float * outputs, size_t output_capacity,
                     size_t * output_count, int32_t expert);
    int matvec_batch_experts(const char * name, const float * inputs, size_t batch_count,
                             size_t input_width, const int32_t * experts,
                             float * outputs, size_t output_capacity, size_t * output_count);
    int matvec_many(
        const char * const * names, const int32_t * experts, size_t request_count,
        const float * input, size_t input_count, float * const * outputs,
        const size_t * output_capacities, size_t * output_counts
    );
    int prefetch(const char * name, int32_t expert);
    int evict(const char * name, int32_t expert);
    int residency(const char * name, int32_t expert, int32_t * resident, uint64_t * bytes,
                  uint64_t * hits, uint64_t * misses) const;

    const char * last_error() const noexcept { return error_.c_str(); }

    ~WeightBank() {
        for (auto & weak : device_epochs_) {
            if (auto epoch = weak.lock()) epoch->close();
        }
        device_epochs_.clear();
        for (auto & item : tensors_) {
            item.second.dense_plan.reset();
            item.second.slices.clear();
        }
        if (weight_buffer_ != nullptr) ggml_backend_buffer_free(weight_buffer_);
        if (weight_context_ != nullptr) ggml_free(weight_context_);
        if (backend_ != nullptr) ggml_backend_free(backend_);
    }

    int device_epoch_begin(
        const float * initial_planes, size_t plane_value_count, size_t mode_count, int32_t gain_ppm,
        std::shared_ptr<DeviceEpochState> * out_epoch
    );
    int device_epoch_upload(
        const std::shared_ptr<DeviceEpochState> & epoch, const float * values, size_t count,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_tensor_view(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, size_t element_offset, size_t count,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_tensor_count(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & value, size_t * out_count
    ) const;
    int device_tensor_download(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & value, float * out, size_t capacity, size_t * out_count
    ) const;
    int device_tensor_download_many(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::vector<std::shared_ptr<DeviceTensorValue>> & values,
        float * out, size_t capacity, size_t * out_count,
        size_t * value_offsets, size_t * value_counts
    ) const;
    int device_embedding(
        const std::shared_ptr<DeviceEpochState> & epoch, const char * name, uint64_t token,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_matvec(
        const std::shared_ptr<DeviceEpochState> & epoch, const char * name,
        const std::shared_ptr<DeviceTensorValue> & input, int32_t expert,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_low_rank_affine(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, const char * method_id,
        const float * a, size_t input_width, size_t rank, const float * b,
        size_t output_width, const float * bias,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_matvec_many(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const char * const * names, const int32_t * experts, size_t request_count,
        const std::shared_ptr<DeviceTensorValue> & input,
        std::vector<std::shared_ptr<DeviceTensorValue>> * out_values
    );
    int device_exchange(
        const std::shared_ptr<DeviceEpochState> & epoch, const char * site,
        const std::shared_ptr<DeviceTensorValue> & input,
        std::shared_ptr<DeviceTensorValue> * out_value,
        std::shared_ptr<DeviceTensorValue> * out_scale,
        std::shared_ptr<DeviceTensorValue> * out_delta
    );
    int device_unary(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, int operation,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_scale(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, float scale,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_binary(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & left,
        const std::shared_ptr<DeviceTensorValue> & right, bool multiply,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_concat(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & left,
        const std::shared_ptr<DeviceTensorValue> & right,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_norm_rows(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, size_t row_width,
        float epsilon, bool sum_squares, const char * weight_name,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_mul_rows(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input,
        const std::shared_ptr<DeviceTensorValue> & row_scales, size_t row_width,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_exp_clipped(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, float lower, float upper,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_softplus(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_probability(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, bool positive_normalize,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_recurrent_conv(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & history, const char * kernel_name,
        size_t channels, std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_recurrent_state_op(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & state,
        const std::shared_ptr<DeviceTensorValue> & keys_or_queries,
        const std::shared_ptr<DeviceTensorValue> & deltas, int operation,
        size_t value_heads, size_t key_heads, size_t value_dim, size_t key_dim,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_rope(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & input, int64_t position,
        const int32_t * sections, size_t section_count, double base,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_attention_scores(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & query,
        const std::shared_ptr<DeviceTensorValue> & key_cache,
        size_t kv_head, size_t kv_heads, size_t head_dim, float scale,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_attention_context(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & probabilities,
        const std::shared_ptr<DeviceTensorValue> & value_cache,
        size_t kv_head, size_t kv_heads, size_t value_dim,
        std::shared_ptr<DeviceTensorValue> * out_value
    );
    int device_epoch_snapshot(
        const std::shared_ptr<DeviceEpochState> & epoch,
        float * planes, size_t plane_capacity, size_t * out_count
    );
    int device_epoch_finish(
        const std::shared_ptr<DeviceEpochState> & epoch,
        float * final_planes, size_t plane_capacity, size_t * out_count
    );
    int device_epoch_close(const std::shared_ptr<DeviceEpochState> & epoch);

private:
    WeightBank() = default;

    int fail(int code, std::string message) const {
        error_ = std::move(message);
        return code;
    }
    TensorEntry * find(const char * name);
    const TensorEntry * find(const char * name) const;
    bool validate_expert(const TensorEntry & entry, int32_t expert, std::string & reason) const;
    int prefetch_locked(TensorEntry & entry, int32_t expert);
    int raw_bytes(const TensorEntry & entry, size_t offset, void * out, size_t size) const;
    int dequant_row(const TensorEntry & entry, size_t row_offset, float * out, size_t count) const;
    int ensure_matvec_plan(
        ggml_tensor * matrix, size_t cols, size_t rows, size_t batch_count,
        std::unique_ptr<MatvecPlan> & plan
    );
    // Shared body of matvec_batch / matvec_batch_experts. Caller holds mutex_
    // and has resolved `entry`; computes rows [batch_count, width] of one
    // tensor/expert slice into `outputs` and writes *output_count.
    int matvec_batch_core(
        TensorEntry & entry, const float * inputs, size_t batch_count, size_t input_width,
        float * outputs, size_t output_capacity, size_t * output_count, int32_t expert
    );
    int validate_device_epoch(const std::shared_ptr<DeviceEpochState> & epoch, bool mutate) const;
    int validate_device_value(
        const std::shared_ptr<DeviceEpochState> & epoch,
        const std::shared_ptr<DeviceTensorValue> & value
    ) const;
    int make_device_value(
        const std::shared_ptr<DeviceEpochState> & epoch, size_t count,
        std::shared_ptr<DeviceTensorValue> * out_value
    );

    mutable std::mutex mutex_;
    mutable std::string error_;
    FileBacking file_;
    std::unordered_map<std::string, TensorEntry> tensors_;
    ggml_context * weight_context_ = nullptr;
    ggml_backend_buffer_t weight_buffer_ = nullptr;
    ggml_backend_t backend_ = nullptr;
    int resource_wait(size_t requested_bytes, const char * operation) const;
    std::string backend_name_;
    int32_t threads_ = 1;
    std::vector<std::weak_ptr<DeviceEpochState>> device_epochs_;
};

struct DeviceGraphWorkspace {
    ggml_context * context = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    ggml_cgraph * graph = nullptr;

    DeviceGraphWorkspace() = default;
    DeviceGraphWorkspace(const DeviceGraphWorkspace &) = delete;
    DeviceGraphWorkspace & operator=(const DeviceGraphWorkspace &) = delete;
    ~DeviceGraphWorkspace() { reset(); }

    void reset() noexcept {
        if (buffer != nullptr) {
            ggml_backend_buffer_free(buffer);
            buffer = nullptr;
        }
        if (context != nullptr) {
            ggml_free(context);
            context = nullptr;
        }
        graph = nullptr;
    }

    bool init(size_t extra_bytes = 0) {
        size_t bytes = 0;
        if (!checked_add(kContextBytes, extra_bytes, bytes)) return false;
        ggml_init_params params{};
        params.mem_size = bytes;
        params.no_alloc = true;
        context = ggml_init(params);
        return context != nullptr;
    }

    bool build(const std::vector<ggml_tensor *> & roots, size_t node_capacity) {
        if (context == nullptr || roots.empty() || node_capacity == 0 ||
            node_capacity > static_cast<size_t>(std::numeric_limits<int>::max())) {
            return false;
        }
        graph = ggml_new_graph_custom(context, static_cast<int>(node_capacity), false);
        if (graph == nullptr) return false;
        for (ggml_tensor * root : roots) {
            if (root == nullptr) return false;
            ggml_build_forward_expand(graph, root);
        }
        return true;
    }

    bool allocate(ggml_backend_t backend) {
        if (context == nullptr || backend == nullptr) return false;
        buffer = ggml_backend_alloc_ctx_tensors(context, backend);
        return buffer != nullptr;
    }

    bool compute(ggml_backend_t backend, int32_t max_threads) const {
        return graph != nullptr && backend != nullptr &&
            compute_graph(backend, graph, max_threads) == GGML_STATUS_SUCCESS;
    }
};

size_t device_context_bytes(const ggml_context * context) {
    size_t bytes = 0;
    for (ggml_tensor * tensor = ggml_get_first_tensor(context);
         tensor != nullptr;
         tensor = ggml_get_next_tensor(context, tensor)) {
        if (tensor->view_src != nullptr || tensor->buffer != nullptr) continue;
        if (!checked_add(bytes, ggml_nbytes_pad(tensor), bytes)) {
            return std::numeric_limits<size_t>::max();
        }
    }
    return bytes;
}

uint32_t rotate_right(uint32_t value, unsigned shift) {
    return (value >> shift) | (value << (32U - shift));
}

std::array<uint8_t, 32> sha256_bytes(const uint8_t * input, size_t length) {
    static constexpr uint32_t k[64] = {
        0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
        0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
        0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU, 0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
        0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
        0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
        0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
        0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
        0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U, 0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
    };
    uint32_t state[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    };
    auto transform = [&](const uint8_t * block) {
        uint32_t words[64]{};
        for (size_t i = 0; i < 16; ++i) {
            words[i] = (static_cast<uint32_t>(block[i * 4]) << 24U)
                | (static_cast<uint32_t>(block[i * 4 + 1]) << 16U)
                | (static_cast<uint32_t>(block[i * 4 + 2]) << 8U)
                | static_cast<uint32_t>(block[i * 4 + 3]);
        }
        for (size_t i = 16; i < 64; ++i) {
            const uint32_t s0 = rotate_right(words[i - 15], 7) ^ rotate_right(words[i - 15], 18) ^ (words[i - 15] >> 3U);
            const uint32_t s1 = rotate_right(words[i - 2], 17) ^ rotate_right(words[i - 2], 19) ^ (words[i - 2] >> 10U);
            words[i] = words[i - 16] + s0 + words[i - 7] + s1;
        }
        uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
        uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
        for (size_t i = 0; i < 64; ++i) {
            const uint32_t sum1 = rotate_right(e, 6) ^ rotate_right(e, 11) ^ rotate_right(e, 25);
            const uint32_t choice = (e & f) ^ (~e & g);
            const uint32_t t1 = h + sum1 + choice + k[i] + words[i];
            const uint32_t sum0 = rotate_right(a, 2) ^ rotate_right(a, 13) ^ rotate_right(a, 22);
            const uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
            const uint32_t t2 = sum0 + majority;
            h = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }
        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
        state[4] += e; state[5] += f; state[6] += g; state[7] += h;
    };
    size_t offset = 0;
    while (length - offset >= 64) {
        transform(input + offset);
        offset += 64;
    }
    uint8_t tail[128]{};
    const size_t remainder = length - offset;
    if (remainder != 0) std::memcpy(tail, input + offset, remainder);
    tail[remainder] = 0x80U;
    const size_t padded = remainder < 56 ? 64 : 128;
    const uint64_t bit_length = static_cast<uint64_t>(length) * 8U;
    for (size_t i = 0; i < 8; ++i) {
        tail[padded - 1 - i] = static_cast<uint8_t>(bit_length >> (i * 8U));
    }
    transform(tail);
    if (padded == 128) transform(tail + 64);
    std::array<uint8_t, 32> digest{};
    for (size_t i = 0; i < 8; ++i) {
        digest[i * 4] = static_cast<uint8_t>(state[i] >> 24U);
        digest[i * 4 + 1] = static_cast<uint8_t>(state[i] >> 16U);
        digest[i * 4 + 2] = static_cast<uint8_t>(state[i] >> 8U);
        digest[i * 4 + 3] = static_cast<uint8_t>(state[i]);
    }
    return digest;
}

bool site_mode_offset(const char * site, size_t site_length, size_t chunk_index, size_t mode_count, size_t * out_offset) {
    if (site == nullptr || out_offset == nullptr || mode_count == 0) return false;
    std::array<uint8_t, 576> message{};
    if (site_length + 1 >= message.size()) return false;
    std::memcpy(message.data(), site, site_length);
    message[site_length] = 0;
    char chunk_text[32]{};
    const auto converted = std::to_chars(chunk_text, chunk_text + sizeof(chunk_text), chunk_index);
    if (converted.ec != std::errc{}) return false;
    const size_t text_length = static_cast<size_t>(converted.ptr - chunk_text);
    std::memcpy(message.data() + site_length + 1, chunk_text, text_length);
    const auto digest = sha256_bytes(message.data(), site_length + 1 + text_length);
    uint64_t prefix = 0;
    for (size_t i = 0; i < 8; ++i) prefix = (prefix << 8U) | digest[i];
    *out_offset = static_cast<size_t>(prefix % mode_count);
    return true;
}

TensorEntry * WeightBank::find(const char * name) {
    if (name == nullptr) return nullptr;
    auto it = tensors_.find(name);
    return it == tensors_.end() ? nullptr : &it->second;
}

const TensorEntry * WeightBank::find(const char * name) const {
    if (name == nullptr) return nullptr;
    auto it = tensors_.find(name);
    return it == tensors_.end() ? nullptr : &it->second;
}

bool WeightBank::validate_expert(const TensorEntry & entry, int32_t expert, std::string & reason) const {
    if (!entry.expert) {
        reason = "tensor is not an expert bank";
        return false;
    }
    if (expert < 0 || static_cast<int64_t>(expert) >= entry.tensor->ne[2]) {
        reason = "expert index is outside tensor dimensions";
        return false;
    }
    return true;
}

int WeightBank::raw_bytes(const TensorEntry & entry, size_t offset, void * out, size_t size) const {
    if (offset > entry.source_size || size > entry.source_size - offset) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "raw tensor read is outside GGUF tensor bytes");
    }
    if (backend_name_ == "cpu" || entry.tensor->buffer == nullptr) {
        std::memcpy(out, file_.data() + entry.source_offset + offset, size);
        return CASSIFI_WEIGHT_BANK_OK;
    }
    ggml_backend_tensor_get(entry.tensor, out, offset, size);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::dequant_row(const TensorEntry & entry, size_t row_offset, float * out, size_t count) const {
    const size_t row_bytes = ggml_row_size(entry.tensor->type, entry.tensor->ne[0]);
    std::vector<uint8_t> raw(row_bytes);
    const int rc = raw_bytes(entry, row_offset, raw.data(), raw.size());
    if (rc != 0) return rc;
    const auto * traits = ggml_get_type_traits(entry.tensor->type);
    if (entry.tensor->type == GGML_TYPE_F32) {
        std::memcpy(out, raw.data(), count * sizeof(float));
        return CASSIFI_WEIGHT_BANK_OK;
    }
    if (traits == nullptr || traits->to_float == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML type has no dequantization primitive");
    }
    traits->to_float(raw.data(), out, static_cast<int64_t>(count));
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::prefetch_locked(TensorEntry & entry, int32_t expert) {
    std::string reason;
    if (!validate_expert(entry, expert, reason)) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, std::move(reason));
    auto hit = entry.slices.find(expert);
    if (hit != entry.slices.end()) {
        ++entry.hits[expert];
        return CASSIFI_WEIGHT_BANK_OK;
    }

    const size_t slice_bytes = ggml_row_size(entry.tensor->type, entry.tensor->ne[0]) * static_cast<size_t>(entry.tensor->ne[1]);
    const size_t source_offset = static_cast<size_t>(expert) * entry.tensor->nb[2];
    if (source_offset > entry.source_size || slice_bytes > entry.source_size - source_offset) {
        ++entry.misses[expert];
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert slice exceeds GGUF tensor bytes");
    }

    ggml_init_params params{};
    params.mem_size = kContextBytes;
    params.no_alloc = true;
    ggml_context * context = ggml_init(params);
    if (context == nullptr) {
        ++entry.misses[expert];
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate expert slice context");
    }
    const int64_t ne0 = entry.tensor->ne[0];
    const int64_t ne1 = entry.tensor->ne[1];
    ggml_tensor * slice = ggml_new_tensor_2d(context, entry.tensor->type, ne0, ne1);
    if (slice == nullptr) {
        ggml_free(context);
        ++entry.misses[expert];
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate expert slice tensor");
    }
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(context, backend_);
    if (buffer == nullptr) {
        ggml_free(context);
        ++entry.misses[expert];
        return backend_name_ == "vulkan"
            ? resource_wait(slice_bytes, "selected expert slice prefetch")
            : fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate backend expert slice buffer");
    }
    ggml_backend_tensor_set(slice, file_.data() + entry.source_offset + source_offset, 0, slice_bytes);
    ExpertSlice resident;
    resident.context = context;
    resident.buffer = buffer;
    resident.tensor = slice;
    entry.slices.emplace(expert, std::move(resident));
    ++entry.misses[expert];
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::tensor_info(const char * name, cassifi_weight_tensor_info_t * out) const {
    if (name == nullptr || out == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "tensor_info requires name and output");
    std::lock_guard<std::mutex> lock(mutex_);
    const TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    *out = entry->info;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::read_vector(const char * name, float * out, size_t capacity, size_t * out_count) const {
    if (name == nullptr || out == nullptr || out_count == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "read_vector requires name, output and count");
    std::lock_guard<std::mutex> lock(mutex_);
    const TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    if (entry->info.rank > 1) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "read_vector requires a one-dimensional tensor");
    const size_t count = static_cast<size_t>(entry->info.element_count);
    if (capacity < count) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "read_vector output capacity is too small");
    const int rc = dequant_row(*entry, 0, out, count);
    if (rc == 0) *out_count = count;
    return rc;
}

int WeightBank::read_tensor_f32(const char * name, float * out, size_t capacity, size_t * out_count) const {
    if (name == nullptr || out == nullptr || out_count == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "read_tensor_f32 requires name, output and count");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    if (entry->expert) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "read_tensor_f32 rejects expert tensors; read an expert slice explicitly");
    const size_t count = static_cast<size_t>(entry->info.element_count);
    if (capacity < count) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "read_tensor_f32 output capacity is too small");
    const size_t row_width = static_cast<size_t>(entry->tensor->ne[0]);
    if (row_width == 0 || count % row_width != 0) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "tensor dimensions are not row-contiguous");
    const size_t rows = count / row_width;
    for (size_t row = 0; row < rows; ++row) {
        const int rc = dequant_row(*entry, row * entry->tensor->nb[1], out + row * row_width, row_width);
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    }
    *out_count = count;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::read_embedding(const char * name, uint64_t token, float * out, size_t capacity, size_t * out_count) const {
    if (name == nullptr || out == nullptr || out_count == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "read_embedding requires name, output and count");
    std::lock_guard<std::mutex> lock(mutex_);
    const TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    if (entry->info.rank < 2 || entry->expert || token >= static_cast<uint64_t>(entry->tensor->ne[1])) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "embedding token is outside a dense rank-2 tensor");
    }
    const size_t count = static_cast<size_t>(entry->tensor->ne[0]);
    if (capacity < count) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "embedding output capacity is too small");
    const int rc = dequant_row(*entry, static_cast<size_t>(token) * entry->tensor->nb[1], out, count);
    if (rc == 0) *out_count = count;
    return rc;
}

int WeightBank::ensure_matvec_plan(
    ggml_tensor * matrix,
    size_t cols,
    size_t rows,
    size_t batch_count,
    std::unique_ptr<MatvecPlan> & plan
) {
    if (
        plan != nullptr
        && plan->matrix == matrix
        && plan->cols == cols
        && plan->rows == rows
        && plan->batch_count == batch_count
    ) {
        return CASSIFI_WEIGHT_BANK_OK;
    }

    std::unique_ptr<MatvecPlan> created(new (std::nothrow) MatvecPlan());
    if (created == nullptr) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate reusable matvec plan"
        );
    }
    ggml_init_params params{};
    params.mem_size = kContextBytes;
    params.no_alloc = true;
    created->context = ggml_init(params);
    if (created->context == nullptr) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate matvec context"
        );
    }
    if (batch_count == 1) {
        created->input = ggml_new_tensor_1d(
            created->context,
            GGML_TYPE_F32,
            static_cast<int64_t>(cols)
        );
    } else {
        created->input = ggml_new_tensor_2d(
            created->context,
            GGML_TYPE_F32,
            static_cast<int64_t>(cols),
            static_cast<int64_t>(batch_count)
        );
    }
    if (created->input == nullptr) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate matvec input tensor"
        );
    }
    created->input->data = nullptr;
    created->result = ggml_mul_mat(created->context, matrix, created->input);
    if (
        created->result == nullptr
        || created->result->ne[0] != static_cast<int64_t>(rows)
        || created->result->ne[1] != static_cast<int64_t>(batch_count)
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
            "GGML rejected matrix-batch dimensions"
        );
    }
    created->graph = ggml_new_graph_custom(created->context, 16, false);
    if (created->graph == nullptr) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate matvec graph"
        );
    }
    ggml_build_forward_expand(created->graph, created->result);
    created->buffer = ggml_backend_alloc_ctx_tensors(
        created->context,
        backend_
    );
    if (created->buffer == nullptr) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate matvec backend buffers"
        );
    }
    created->matrix = matrix;
    created->cols = cols;
    created->rows = rows;
    created->batch_count = batch_count;
    plan = std::move(created);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::matvec(const char * name, const float * input, size_t input_count, float * output,
                       size_t output_capacity, size_t * output_count, int32_t expert) {
    if (name == nullptr || input == nullptr || output == nullptr || output_count == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "matvec requires name, input, output and count");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    if (entry->info.rank < 1 || entry->tensor->ne[0] <= 0 || entry->tensor->ne[1] <= 0) {
        // A rank-1 tensor is a projection to width one; GGML treats it as a
        // matrix with a single row, so it shares the matrix-vector path.
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec requires a non-empty matrix");
    }
    const size_t cols = static_cast<size_t>(entry->tensor->ne[0]);
    const size_t rows = static_cast<size_t>(entry->tensor->ne[1]);
    if (input_count != cols || output_capacity < rows) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec dimensions do not match tensor");
    if (entry->expert) {
        if (expert < 0) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert index is required for an expert tensor");
        const int rc = prefetch_locked(*entry, expert);
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    } else if (expert >= 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert index supplied for a dense tensor");
    }

    ggml_tensor * matrix = entry->tensor;
    std::unique_ptr<MatvecPlan> * plan_slot = &entry->dense_plan;
    if (entry->expert) {
        // The learned residency decision is physical: prefetch_locked has
        // already copied this expert's bytes into a backend buffer, and the
        // matrix-vector product reads that resident slice on every backend.
        auto slice = entry->slices.find(expert);
        if (slice == entry->slices.end() || slice->second.tensor == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "expert slice is not resident"
            );
        }
        matrix = slice->second.tensor;
        plan_slot = &slice->second.plan;
    }
    const int plan_result = ensure_matvec_plan(
        matrix,
        cols,
        rows,
        1,
        *plan_slot
    );
    if (plan_result != CASSIFI_WEIGHT_BANK_OK) return plan_result;
    MatvecPlan & plan = **plan_slot;
    ggml_backend_tensor_set(
        plan.input,
        input,
        0,
        cols * sizeof(float)
    );
    const ggml_status status = compute_graph(backend_, plan.graph, threads_);
    if (status != GGML_STATUS_SUCCESS) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "GGML backend matvec failed"
        );
    }
    ggml_backend_tensor_get(
        plan.result,
        output,
        0,
        rows * sizeof(float)
    );
    *output_count = rows;
    return CASSIFI_WEIGHT_BANK_OK;
}
int WeightBank::matvec_batch(
    const char * name,
    const float * inputs,
    size_t batch_count,
    size_t input_width,
    float * outputs,
    size_t output_capacity,
    size_t * output_count,
    int32_t expert
) {
    if (
        name == nullptr
        || inputs == nullptr
        || outputs == nullptr
        || output_count == nullptr
        || batch_count == 0
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT,
            "matvec_batch requires name, inputs, outputs, count and a non-empty batch"
        );
    }
    if (
        batch_count > static_cast<size_t>(std::numeric_limits<int64_t>::max())
        || input_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
            "matvec_batch dimensions exceed GGML limits"
        );
    }

    std::lock_guard<std::mutex> lock(mutex_);
    TensorEntry * entry = find(name);
    if (entry == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    }
    size_t written = 0;
    const int rc = matvec_batch_core(
        *entry, inputs, batch_count, input_width, outputs, output_capacity, &written, expert
    );
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    *output_count = written;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::matvec_batch_core(
    TensorEntry & entry,
    const float * inputs,
    size_t batch_count,
    size_t input_width,
    float * outputs,
    size_t output_capacity,
    size_t * output_count,
    int32_t expert
) {
    if (entry.info.rank < 1 || entry.tensor->ne[0] <= 0 || entry.tensor->ne[1] <= 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch requires a non-empty matrix");
    }
    const size_t cols = static_cast<size_t>(entry.tensor->ne[0]);
    const size_t rows = static_cast<size_t>(entry.tensor->ne[1]);
    if (input_width != cols) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch input width does not match tensor");
    }
    size_t input_count = 0;
    size_t output_value_count = 0;
    size_t input_bytes = 0;
    size_t output_bytes = 0;
    if (
        !checked_mul(batch_count, cols, input_count)
        || !checked_mul(batch_count, rows, output_value_count)
        || !checked_mul(input_count, sizeof(float), input_bytes)
        || !checked_mul(output_value_count, sizeof(float), output_bytes)
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
            "matvec_batch buffer dimensions overflow native size"
        );
    }
    if (output_capacity < output_value_count) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch output capacity is too small");
    }
    if (entry.expert) {
        if (expert < 0) {
            return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert index is required for an expert tensor");
        }
        const int rc = prefetch_locked(entry, expert);
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    } else if (expert >= 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert index supplied for a dense tensor");
    }

    try {
        ggml_tensor * matrix = entry.tensor;
        std::unordered_map<size_t, std::unique_ptr<MatvecPlan>> * plans =
            &entry.dense_batch_plans;
        if (entry.expert) {
            auto slice = entry.slices.find(expert);
            if (slice == entry.slices.end() || slice->second.tensor == nullptr) {
                return fail(
                    CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                    "expert slice is not resident"
                );
            }
            matrix = slice->second.tensor;
            plans = &slice->second.batch_plans;
        }
        auto inserted = plans->try_emplace(batch_count);
        std::unique_ptr<MatvecPlan> & plan_slot = inserted.first->second;
        const int plan_result = ensure_matvec_plan(
            matrix,
            cols,
            rows,
            batch_count,
            plan_slot
        );
        if (plan_result != CASSIFI_WEIGHT_BANK_OK) return plan_result;
        MatvecPlan & plan = *plan_slot;
        ggml_backend_tensor_set(plan.input, inputs, 0, input_bytes);
        const ggml_status status = compute_graph(backend_, plan.graph, threads_);
        if (status != GGML_STATUS_SUCCESS) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend matvec batch failed");
        }
        ggml_backend_tensor_get(plan.result, outputs, 0, output_bytes);
        *output_count = output_value_count;
        return CASSIFI_WEIGHT_BANK_OK;
    } catch (const std::bad_alloc &) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate reusable matvec batch plan"
        );
    }
}

int WeightBank::matvec_batch_experts(
    const char * name,
    const float * inputs,
    size_t batch_count,
    size_t input_width,
    const int32_t * experts,
    float * outputs,
    size_t output_capacity,
    size_t * output_count
) {
    if (
        name == nullptr
        || inputs == nullptr
        || experts == nullptr
        || outputs == nullptr
        || output_count == nullptr
        || batch_count == 0
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT,
            "matvec_batch_experts requires name, inputs, experts, outputs, count and a non-empty batch"
        );
    }
    if (
        batch_count > static_cast<size_t>(std::numeric_limits<int64_t>::max())
        || input_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
            "matvec_batch_experts dimensions exceed GGML limits"
        );
    }

    std::lock_guard<std::mutex> lock(mutex_);
    TensorEntry * entry = find(name);
    if (entry == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    }
    if (entry->info.rank < 1 || entry->tensor->ne[0] <= 0 || entry->tensor->ne[1] <= 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch_experts requires a non-empty matrix");
    }
    const size_t cols = static_cast<size_t>(entry->tensor->ne[0]);
    const size_t rows = static_cast<size_t>(entry->tensor->ne[1]);
    if (input_width != cols) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch_experts input width does not match tensor");
    }
    size_t output_value_count = 0;
    size_t output_bytes = 0;
    if (
        !checked_mul(batch_count, rows, output_value_count)
        || !checked_mul(output_value_count, sizeof(float), output_bytes)
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
            "matvec_batch_experts buffer dimensions overflow native size"
        );
    }
    if (output_capacity < output_value_count) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "matvec_batch_experts output capacity is too small");
    }

    // Partition rows by requested expert; first appearance fixes group order.
    std::vector<int32_t> distinct_experts;
    std::vector<std::vector<size_t>> row_groups;
    distinct_experts.reserve(batch_count);
    row_groups.reserve(batch_count);
    for (size_t row = 0; row < batch_count; ++row) {
        const int32_t expert = experts[row];
        size_t group = 0;
        for (; group < distinct_experts.size(); ++group) {
            if (distinct_experts[group] == expert) break;
        }
        if (group == distinct_experts.size()) {
            distinct_experts.push_back(expert);
            row_groups.emplace_back();
        }
        row_groups[group].push_back(row);
    }

    if (distinct_experts.size() == 1U) {
        size_t written = 0;
        const int rc = matvec_batch_core(
            *entry, inputs, batch_count, input_width, outputs, output_capacity, &written,
            distinct_experts[0]
        );
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
        *output_count = written;
        return CASSIFI_WEIGHT_BANK_OK;
    }

    std::vector<float> gathered_inputs;
    std::vector<float> group_outputs;
    for (size_t group = 0; group < distinct_experts.size(); ++group) {
        const std::vector<size_t> & indices = row_groups[group];
        const float * group_input = inputs;
        size_t group_count = batch_count;
        if (indices.size() != batch_count) {
            size_t gathered_values = 0;
            if (!checked_mul(indices.size(), cols, gathered_values)) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "matvec_batch_experts gathered input overflows native size"
                );
            }
            gathered_inputs.resize(gathered_values);
            for (size_t item = 0; item < indices.size(); ++item) {
                const float * source = inputs + indices[item] * input_width;
                float * destination = gathered_inputs.data() + item * input_width;
                for (size_t col = 0; col < input_width; ++col) destination[col] = source[col];
            }
            group_input = gathered_inputs.data();
            group_count = indices.size();
        }
        size_t group_value_count = 0;
        if (!checked_mul(group_count, rows, group_value_count)) {
            return fail(
                CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                "matvec_batch_experts subgroup output overflows native size"
            );
        }
        group_outputs.resize(group_value_count);
        size_t subgroup_written = 0;
        const int rc = matvec_batch_core(
            *entry, group_input, group_count, input_width, group_outputs.data(),
            group_value_count, &subgroup_written, distinct_experts[group]
        );
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
        for (size_t item = 0; item < indices.size(); ++item) {
            float * destination = outputs + indices[item] * rows;
            const float * source = group_outputs.data() + item * rows;
            for (size_t col = 0; col < rows; ++col) destination[col] = source[col];
        }
    }
    *output_count = output_value_count;
    return CASSIFI_WEIGHT_BANK_OK;
}


int WeightBank::matvec_many(
    const char * const * names,
    const int32_t * experts,
    size_t request_count,
    const float * input,
    size_t input_count,
    float * const * outputs,
    const size_t * output_capacities,
    size_t * output_counts
) {
    if (
        names == nullptr
        || experts == nullptr
        || request_count == 0
        || input == nullptr
        || outputs == nullptr
        || output_capacities == nullptr
        || output_counts == nullptr
    ) {
        return fail(
            CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT,
            "matvec_many requires names, experts, requests, input, outputs, capacities and counts"
        );
    }

    struct Request {
        TensorEntry * entry = nullptr;
        ggml_tensor * matrix = nullptr;
        size_t cols = 0;
        size_t rows = 0;
    };

    try {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<Request> requests;
        requests.reserve(request_count);

        // Validate every request before changing residency or allocating a
        // graph.  This keeps failures deterministic and avoids partial output.
        for (size_t index = 0; index < request_count; ++index) {
            if (names[index] == nullptr || outputs[index] == nullptr) {
                return fail(
                    CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT,
                    "matvec_many contains a null tensor name or output"
                );
            }
            TensorEntry * entry = find(names[index]);
            if (entry == nullptr) {
                return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
            }
            if (
                entry->info.rank < 1
                || entry->tensor->ne[0] <= 0
                || entry->tensor->ne[1] <= 0
            ) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "matvec_many requires non-empty matrices"
                );
            }
            const size_t cols = static_cast<size_t>(entry->tensor->ne[0]);
            const size_t rows = static_cast<size_t>(entry->tensor->ne[1]);
            if (input_count != cols || output_capacities[index] < rows) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "matvec_many dimensions do not match tensor"
                );
            }
            if (entry->expert) {
                if (experts[index] < 0) {
                    return fail(
                        CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                        "expert index is required for an expert tensor"
                    );
                }
                std::string reason;
                if (!validate_expert(*entry, experts[index], reason)) {
                    return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, std::move(reason));
                }
            } else if (experts[index] >= 0) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "expert index supplied for a dense tensor"
                );
            }
            requests.push_back(Request{entry, nullptr, cols, rows});
        }

        // Materialize all requested expert slices before constructing the
        // graph.  Each request then reads exactly the same resident slice as
        // the single-matvec path.
        for (size_t index = 0; index < request_count; ++index) {
            Request & request = requests[index];
            if (request.entry->expert) {
                const int rc = prefetch_locked(*request.entry, experts[index]);
                if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
                auto slice = request.entry->slices.find(experts[index]);
                if (
                    slice == request.entry->slices.end()
                    || slice->second.tensor == nullptr
                ) {
                    return fail(
                        CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                        "expert slice is not resident"
                    );
                }
                request.matrix = slice->second.tensor;
            } else {
                request.matrix = request.entry->tensor;
            }
        }

        if (input_count > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
            return fail(
                CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                "matvec_many input width exceeds GGML dimensions"
            );
        }
        size_t input_bytes = 0;
        if (!checked_mul(input_count, sizeof(float), input_bytes)) {
            return fail(
                CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                "matvec_many input size overflows native size"
            );
        }
        size_t graph_bytes = 0;
        if (!checked_mul(request_count, 4096U, graph_bytes)
            || !checked_add(kContextBytes, graph_bytes, graph_bytes)) {
            return fail(
                CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                "matvec_many graph size overflows native size"
            );
        }
        size_t graph_nodes = 0;
        if (
            !checked_mul(request_count, 2U, graph_nodes)
            || !checked_add(graph_nodes, 1U, graph_nodes)
            || graph_nodes > static_cast<size_t>(std::numeric_limits<int>::max())
        ) {
            return fail(
                CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                "matvec_many graph node count overflows native size"
            );
        }

        std::unique_ptr<GroupedMatvecPlan> plan(new (std::nothrow) GroupedMatvecPlan());
        if (plan == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "failed to allocate grouped matvec plan"
            );
        }
        ggml_init_params params{};
        params.mem_size = graph_bytes;
        params.no_alloc = true;
        plan->context = ggml_init(params);
        if (plan->context == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "failed to allocate grouped matvec context"
            );
        }
        plan->input = ggml_new_tensor_1d(
            plan->context,
            GGML_TYPE_F32,
            static_cast<int64_t>(input_count)
        );
        if (plan->input == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "failed to allocate grouped matvec input tensor"
            );
        }
        plan->input->data = nullptr;
        plan->results.reserve(request_count);
        for (const Request & request : requests) {
            ggml_tensor * result = ggml_mul_mat(
                plan->context,
                request.matrix,
                plan->input
            );
            if (
                result == nullptr
                || result->ne[0] != static_cast<int64_t>(request.rows)
            ) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "GGML rejected grouped matrix-vector dimensions"
                );
            }
            plan->results.push_back(result);
        }
        plan->graph = ggml_new_graph_custom(plan->context, graph_nodes, false);
        if (plan->graph == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "failed to allocate grouped matvec graph"
            );
        }
        for (ggml_tensor * result : plan->results) {
            ggml_build_forward_expand(plan->graph, result);
        }
        plan->buffer = ggml_backend_alloc_ctx_tensors(plan->context, backend_);
        if (plan->buffer == nullptr) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "failed to allocate grouped matvec backend buffers"
            );
        }
        ggml_backend_tensor_set(plan->input, input, 0, input_bytes);
        const ggml_status status = compute_graph(backend_, plan->graph, threads_);
        if (status != GGML_STATUS_SUCCESS) {
            return fail(
                CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
                "GGML backend grouped matvec failed"
            );
        }
        for (size_t index = 0; index < request_count; ++index) {
            size_t output_bytes = 0;
            if (!checked_mul(requests[index].rows, sizeof(float), output_bytes)) {
                return fail(
                    CASSIFI_WEIGHT_BANK_SHAPE_ERROR,
                    "matvec_many output size overflows native size"
                );
            }
            ggml_backend_tensor_get(
                plan->results[index],
                outputs[index],
                0,
                output_bytes
            );
            output_counts[index] = requests[index].rows;
        }
        return CASSIFI_WEIGHT_BANK_OK;
    } catch (const std::exception &) {
        return fail(
            CASSIFI_WEIGHT_BANK_BACKEND_ERROR,
            "failed to allocate grouped matvec state"
        );
}
}

int WeightBank::prefetch(const char * name, int32_t expert) {
    if (name == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "prefetch requires a tensor name");
    std::lock_guard<std::mutex> lock(mutex_);
    TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    return prefetch_locked(*entry, expert);
}

int WeightBank::evict(const char * name, int32_t expert) {
    if (name == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "evict requires a tensor name");
    std::lock_guard<std::mutex> lock(mutex_);
    TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    std::string reason;
    if (!validate_expert(*entry, expert, reason)) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, std::move(reason));
    entry->slices.erase(expert);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::residency(const char * name, int32_t expert, int32_t * resident, uint64_t * bytes,
                          uint64_t * hits, uint64_t * misses) const {
    if (name == nullptr || resident == nullptr || bytes == nullptr || hits == nullptr || misses == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "residency requires all output fields");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "tensor was not found");
    std::string reason;
    if (!validate_expert(*entry, expert, reason)) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, std::move(reason));
    *resident = entry->slices.find(expert) != entry->slices.end();
    *bytes = *resident ? static_cast<uint64_t>(ggml_row_size(entry->tensor->type, entry->tensor->ne[0]) * static_cast<size_t>(entry->tensor->ne[1])) : 0;
    auto hit = entry->hits.find(expert);
    auto miss = entry->misses.find(expert);
    *hits = hit == entry->hits.end() ? 0 : hit->second;
    *misses = miss == entry->misses.end() ? 0 : miss->second;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::load(const char * path, const char * backend_name, int32_t threads, WeightBank ** out) {
    if (path == nullptr || backend_name == nullptr || out == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out = nullptr;
    if (threads <= 0) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    const std::string backend(backend_name);
    if (backend != "cpu" && backend != "vulkan" && backend != "vk") return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    auto bank = std::unique_ptr<WeightBank>(new WeightBank());
    bank->backend_name_ = backend == "vk" ? "vulkan" : backend;
    bank->threads_ = threads;
    if (!bank->file_.load(path)) return CASSIFI_WEIGHT_BANK_IO_ERROR;

    gguf_init_params gguf_params{};
    gguf_params.no_alloc = true;
    gguf_context * gguf = gguf_init_from_buffer(bank->file_.data(), bank->file_.size(), gguf_params);
    if (gguf == nullptr) return CASSIFI_WEIGHT_BANK_IO_ERROR;
    const size_t data_offset = gguf_get_data_offset(gguf);
    const int64_t n_tensors = gguf_get_n_tensors(gguf);
    if (n_tensors <= 0) {
        gguf_free(gguf);
        return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
    }
    size_t context_bytes = kContextBytes;
    size_t descriptor_bytes = 0;
    if (!checked_mul(static_cast<size_t>(n_tensors), 4096, descriptor_bytes) || !checked_add(context_bytes, descriptor_bytes, context_bytes)) {
        gguf_free(gguf);
        return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
    }
    ggml_init_params context_params{};
    context_params.mem_size = context_bytes;
    context_params.no_alloc = true;
    bank->weight_context_ = ggml_init(context_params);
    if (bank->weight_context_ == nullptr) {
        gguf_free(gguf);
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    }
    if (bank->backend_name_ == "cpu") {
        bank->backend_ = ggml_backend_cpu_init();
        if (bank->backend_ == nullptr) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
        ggml_backend_cpu_set_n_threads(bank->backend_, threads);
    }
#ifdef CASSIFI_WEIGHT_BANK_HAS_VULKAN
    else {
        if (ggml_backend_vk_get_device_count() <= 0) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
        bank->backend_ = ggml_backend_vk_init(0);
        if (bank->backend_ == nullptr) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
    }
#else
    else {
        gguf_free(gguf);
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    }
#endif

    for (int64_t i = 0; i < n_tensors; ++i) {
        const char * tensor_name = gguf_get_tensor_name(gguf, i);
        const ggml_type type = gguf_get_tensor_type(gguf, i);
        const int64_t * ne = gguf_get_tensor_ne(gguf, i);
        if (tensor_name == nullptr || ne == nullptr || static_cast<int>(type) < 0 || static_cast<int>(type) >= GGML_TYPE_COUNT) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
        }
        const int64_t block = ggml_blck_size(type);
        if (block <= 0 || ne[0] <= 0 || ne[0] % block != 0) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
        }
        for (int dim = 0; dim < GGML_MAX_DIMS; ++dim) {
            if (ne[dim] <= 0 || ne[dim] > std::numeric_limits<int32_t>::max()) {
                gguf_free(gguf);
                return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
            }
        }
        const size_t offset = gguf_get_tensor_offset(gguf, i);
        const size_t size = gguf_get_tensor_size(gguf, i);
        size_t absolute = 0;
        if (!checked_add(data_offset, offset, absolute) || absolute > bank->file_.size() || size > bank->file_.size() - absolute) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_IO_ERROR;
        }
        ggml_tensor * tensor = ggml_new_tensor(bank->weight_context_, type, GGML_MAX_DIMS, ne);
        if (tensor == nullptr) {
            gguf_free(gguf);
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
        TensorEntry entry;
        entry.tensor = tensor;
        entry.source_offset = absolute;
        entry.source_size = size;
        // GGUF expert banks are rank-3; rank-4 vision convolutions are dense.
        entry.expert = ne[2] > 1 && ne[3] == 1;
        entry.info.rank = GGML_MAX_DIMS;
        while (entry.info.rank > 1 && ne[entry.info.rank - 1] == 1) --entry.info.rank;
        for (uint32_t dim = 0; dim < GGML_MAX_DIMS; ++dim) entry.info.dims[dim] = ne[dim];
        entry.info.ggml_type = static_cast<int32_t>(type);
        size_t elements = 1;
        for (int dim = 0; dim < GGML_MAX_DIMS; ++dim) {
            if (!checked_mul(elements, static_cast<size_t>(ne[dim]), elements)) {
                gguf_free(gguf);
                return CASSIFI_WEIGHT_BANK_SHAPE_ERROR;
            }
        }
        entry.info.element_count = elements;
        entry.info.byte_size = size;
        if (bank->backend_name_ == "cpu" || entry.expert) {
            tensor->data = const_cast<uint8_t *>(bank->file_.data() + absolute);
        }
        bank->tensors_.emplace(tensor_name, std::move(entry));
    }
    gguf_free(gguf);

    if (bank->backend_name_ == "vulkan") {
        bank->weight_buffer_ = ggml_backend_alloc_ctx_tensors(bank->weight_context_, bank->backend_);
        if (bank->weight_buffer_ == nullptr && std::any_of(bank->tensors_.begin(), bank->tensors_.end(), [](const auto & item) { return !item.second.expert; })) {
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
        for (auto & item : bank->tensors_) {
            TensorEntry & entry = item.second;
            if (!entry.expert) {
                if (entry.tensor->buffer == nullptr || entry.tensor->data == nullptr) {
                    return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
                }
                ggml_backend_tensor_set(entry.tensor, bank->file_.data() + entry.source_offset, 0, entry.source_size);
            }
        }
    }
    *out = bank.release();
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::resource_wait(size_t requested_bytes, const char * operation) const {
    size_t free_bytes = 0;
    size_t total_bytes = 0;
    ggml_backend_dev_t device = backend_ == nullptr ? nullptr : ggml_backend_get_device(backend_);
    if (device != nullptr) ggml_backend_dev_memory(device, &free_bytes, &total_bytes);
    std::string message = operation == nullptr ? "Vulkan allocation" : operation;
    message += " resource wait: requested_bytes~=" + std::to_string(requested_bytes);
    message += " free_bytes=" + std::to_string(free_bytes);
    message += " total_bytes=" + std::to_string(total_bytes);
    return fail(CASSIFI_WEIGHT_BANK_RESOURCE_WAIT, std::move(message));
}

int WeightBank::validate_device_epoch(const std::shared_ptr<DeviceEpochState> & epoch, bool mutate) const {
    if (backend_name_ != "vulkan" || backend_ == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE, "device epochs require the weight bank's Vulkan backend");
    }
    if (epoch == nullptr || epoch->owner != this || !epoch->open || epoch->backend != backend_) {
        return fail(CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED, "device epoch is closed or belongs to another weight bank");
    }
    if (mutate && epoch->finished) {
        return fail(CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED, "device epoch has already been finalized");
    }
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::validate_device_value(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & value
) const {
    const int epoch_rc = validate_device_epoch(epoch, false);
    if (epoch_rc != CASSIFI_WEIGHT_BANK_OK) return epoch_rc;
    if (value == nullptr || value->context == nullptr || value->buffer == nullptr ||
        value->tensor == nullptr || value->count == 0) {
        return fail(CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED, "device activation handle is closed or empty");
    }
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::make_device_value(
    const std::shared_ptr<DeviceEpochState> & epoch, size_t count,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr || count == 0 ||
        count > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device activation width is invalid");
    }
    size_t bytes = 0;
    if (!checked_mul(count, sizeof(float), bytes)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device activation byte count overflows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    try {
        value = std::shared_ptr<DeviceTensorValue>(new (std::nothrow) DeviceTensorValue());
        if (value == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device activation owner");
        }
        ggml_init_params params{};
        params.mem_size = kContextBytes;
        params.no_alloc = true;
        value->context = ggml_init(params);
        if (value->context == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device activation context");
        }
        value->tensor = ggml_new_tensor_1d(value->context, GGML_TYPE_F32, static_cast<int64_t>(count));
        if (value->tensor == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device activation tensor");
        }
        auto & spares = epoch->spare_buffers[count];
        if (!spares.empty()) {
            value->buffer = spares.back();
            spares.pop_back();
            epoch->spare_bytes -= ggml_backend_buffer_get_size(value->buffer);
            if (ggml_backend_tensor_alloc(
                    value->buffer, value->tensor,
                    ggml_backend_buffer_get_base(value->buffer)) != GGML_STATUS_SUCCESS) {
                return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to rebind device activation buffer");
            }
        } else {
            value->buffer = ggml_backend_alloc_ctx_tensors(value->context, epoch->backend);
            if (value->buffer == nullptr) return resource_wait(bytes, "activation buffer");
        }
        value->epoch = epoch;
        value->count = count;
        epoch->values.emplace_back(value);
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to register device activation buffer");
    }
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_epoch_begin(
    const float * initial_planes, size_t plane_value_count, size_t mode_count, int32_t gain_ppm,
    std::shared_ptr<DeviceEpochState> * out_epoch
) {
    if (out_epoch == nullptr || initial_planes == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device epoch begin requires planes and an output handle");
    }
    out_epoch->reset();
    if (mode_count == 0 || mode_count > static_cast<size_t>(std::numeric_limits<int32_t>::max()) + 1U ||
        mode_count > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        gain_ppm < 0 || gain_ppm > 1'000'000) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device epoch mode count or gain is outside supported bounds");
    }
    size_t expected_count = 0;
    size_t plane_bytes = 0;
    size_t total_bytes = 0;
    if (!checked_mul(mode_count, size_t{4}, expected_count) ||
        plane_value_count != expected_count ||
        !checked_mul(mode_count, sizeof(float), plane_bytes) ||
        !checked_mul(expected_count, sizeof(float), total_bytes)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device epoch plane count does not match four F32 planes");
    }
    for (size_t i = 0; i < expected_count; ++i) {
        if (!std::isfinite(initial_planes[i])) {
            return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device epoch planes contain nonfinite values");
        }
    }
    std::lock_guard<std::mutex> lock(mutex_);
    if (backend_name_ != "vulkan" || backend_ == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE, "device epochs require a Vulkan weight bank");
    }
    std::shared_ptr<DeviceEpochState> epoch;
    try {
        epoch = std::shared_ptr<DeviceEpochState>(new (std::nothrow) DeviceEpochState());
        if (epoch == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device epoch owner");
        }
        epoch->owner = this;
        epoch->backend = backend_;
        epoch->threads = threads_;
        epoch->mode_count = mode_count;
        epoch->gain_ppm = gain_ppm;
        ggml_init_params params{};
        params.mem_size = kContextBytes;
        params.no_alloc = true;
        epoch->field_context = ggml_init(params);
        if (epoch->field_context == nullptr) {
            epoch->close();
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device field context");
        }
        for (size_t plane = 0; plane < epoch->planes.size(); ++plane) {
            epoch->planes[plane] = ggml_new_tensor_2d(
                epoch->field_context, GGML_TYPE_F32, 1, static_cast<int64_t>(mode_count));
            if (epoch->planes[plane] == nullptr) {
                epoch->close();
                return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate one of four device field planes");
            }
        }
        epoch->field_buffer = ggml_backend_alloc_ctx_tensors(epoch->field_context, epoch->backend);
        if (epoch->field_buffer == nullptr) {
            epoch->close();
            return resource_wait(total_bytes, "four-plane membrane buffer");
        }
        for (size_t plane = 0; plane < epoch->planes.size(); ++plane) {
            ggml_backend_tensor_set(
                epoch->planes[plane],
                initial_planes + plane * mode_count,
                0,
                plane_bytes
            );
        }
        device_epochs_.erase(
            std::remove_if(
                device_epochs_.begin(),
                device_epochs_.end(),
                [](const std::weak_ptr<DeviceEpochState> & existing) {
                    const auto state = existing.lock();
                    return state == nullptr || !state->open;
                }
            ),
            device_epochs_.end()
        );
    } catch (const std::exception &) {
        if (epoch != nullptr) epoch->close();
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device epoch state");
    }
    *out_epoch = std::move(epoch);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_epoch_upload(
    const std::shared_ptr<DeviceEpochState> & epoch, const float * values, size_t count,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (values == nullptr || out_value == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device upload requires source values and an output handle");
    }
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (count == 0 || count > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device upload width is invalid");
    }
    for (size_t i = 0; i < count; ++i) {
        if (!std::isfinite(values[i])) {
            return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device upload contains nonfinite values");
        }
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    ggml_backend_tensor_set(value->tensor, values, 0, count * sizeof(float));
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_tensor_count(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & value, size_t * out_count
) const {
    if (out_count == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device tensor count requires an output pointer");
    std::lock_guard<std::mutex> lock(mutex_);
    const int rc = validate_device_value(epoch, value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    *out_count = value->count;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_tensor_download(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & value, float * out, size_t capacity, size_t * out_count
) const {
    if (out == nullptr || out_count == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device download requires an output buffer and count");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const int rc = validate_device_value(epoch, value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (capacity < value->count) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device download capacity is too small");
    ggml_backend_tensor_get(value->tensor, out, 0, value->count * sizeof(float));
    *out_count = value->count;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_tensor_download_many(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::vector<std::shared_ptr<DeviceTensorValue>> & values,
    float * out, size_t capacity, size_t * out_count,
    size_t * value_offsets, size_t * value_counts
) const {
    if (out_count == nullptr || value_offsets == nullptr || value_counts == nullptr ||
        (!values.empty() && out == nullptr)) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "batched device download requires buffers and metadata arrays");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const int rc = validate_device_epoch(epoch, false);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t total = 0;
    for (const auto & value : values) {
        const int value_rc = validate_device_value(epoch, value);
        if (value_rc != CASSIFI_WEIGHT_BANK_OK) return value_rc;
        if (!checked_add(total, value->count, total)) {
            return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "batched device download size overflows");
        }
    }
    if (capacity < total || total > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "batched device download capacity or tensor width is invalid");
    }
    if (total == 0) {
        *out_count = 0;
        return CASSIFI_WEIGHT_BANK_OK;
    }

    size_t total_bytes = 0;
    size_t context_extra = 0;
    size_t node_capacity = 0;
    size_t doubled_nodes = 0;
    if (!checked_mul(total, sizeof(float), total_bytes) ||
        !checked_mul(values.size(), size_t{1024}, context_extra) ||
        !checked_mul(values.size(), size_t{2}, doubled_nodes) ||
        !checked_add(doubled_nodes, size_t{8}, node_capacity) ||
        node_capacity > static_cast<size_t>(std::numeric_limits<int>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "batched device download graph size overflows");
    }
    try {
        DeviceGraphWorkspace workspace;
        if (!workspace.init(context_extra)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate batched device download context");
        }
        ggml_tensor * packed = ggml_new_tensor_1d(
            workspace.context, GGML_TYPE_F32, static_cast<int64_t>(total));
        if (packed == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate batched device download tensor");
        }
        std::vector<ggml_tensor *> roots;
        roots.reserve(values.size());
        size_t offset = 0;
        for (const auto & value : values) {
            ggml_tensor * destination = ggml_view_1d(
                workspace.context, packed, static_cast<int64_t>(value->count), offset * sizeof(float));
            ggml_tensor * copy = destination == nullptr
                ? nullptr
                : ggml_cpy(workspace.context, value->tensor, destination);
            if (copy == nullptr) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected batched device download shape");
            }
            roots.push_back(copy);
            offset += value->count;
        }
        if (!workspace.build(roots, node_capacity)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build batched device download graph");
        }
        if (!workspace.allocate(epoch->backend)) {
            return resource_wait(device_context_bytes(workspace.context), "batched capture staging buffer");
        }
        if (!workspace.compute(epoch->backend, epoch->threads)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend batched device download graph failed");
        }
        ggml_backend_tensor_get(packed, out, 0, total_bytes);
        offset = 0;
        for (size_t i = 0; i < values.size(); ++i) {
            value_offsets[i] = offset;
            value_counts[i] = values[i]->count;
            offset += values[i]->count;
        }
        *out_count = total;
        return CASSIFI_WEIGHT_BANK_OK;
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate batched device download state");
    }
}

int WeightBank::device_epoch_snapshot(
    const std::shared_ptr<DeviceEpochState> & epoch,
    float * planes, size_t plane_capacity, size_t * out_count
) {
    if (planes == nullptr || out_count == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device epoch snapshot requires a plane buffer and count");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t count = 0;
    if (!checked_mul(epoch->mode_count, size_t{4}, count) || plane_capacity < count) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device epoch snapshot capacity is too small");
    }
    const size_t plane_bytes = epoch->mode_count * sizeof(float);
    for (size_t plane = 0; plane < epoch->planes.size(); ++plane) {
        ggml_backend_tensor_get(
            epoch->planes[plane],
            planes + plane * epoch->mode_count,
            0,
            plane_bytes
        );
    }
    *out_count = count;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_epoch_finish(
    const std::shared_ptr<DeviceEpochState> & epoch,
    float * final_planes, size_t plane_capacity, size_t * out_count
) {
    if (final_planes == nullptr || out_count == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device epoch finish requires a plane buffer and count");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t count = 0;
    if (!checked_mul(epoch->mode_count, size_t{4}, count) || plane_capacity < count) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device epoch final-plane capacity is too small");
    }
    const size_t plane_bytes = epoch->mode_count * sizeof(float);
    for (size_t plane = 0; plane < epoch->planes.size(); ++plane) {
        ggml_backend_tensor_get(
            epoch->planes[plane],
            final_planes + plane * epoch->mode_count,
            0,
            plane_bytes
        );
    }
    epoch->finished = true;
    *out_count = count;
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_epoch_close(const std::shared_ptr<DeviceEpochState> & epoch) {
    if (epoch == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    if (epoch->owner != this) {
        epoch->close();
        return CASSIFI_WEIGHT_BANK_OK;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    epoch->close();
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_tensor_view(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, size_t element_offset, size_t count,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device view requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (count == 0 || element_offset > input->count || count > input->count - element_offset ||
        count > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device subvector view is outside its source activation");
    }
    size_t byte_offset = 0;
    if (!checked_mul(element_offset, sizeof(float), byte_offset)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device subvector offset overflows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    try {
        value = std::shared_ptr<DeviceTensorValue>(new (std::nothrow) DeviceTensorValue());
        if (value == nullptr) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device view owner");
        ggml_init_params params{};
        params.mem_size = kContextBytes;
        params.no_alloc = true;
        value->context = ggml_init(params);
        if (value->context == nullptr) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device view context");
        value->tensor = ggml_view_1d(
            value->context, input->tensor, static_cast<int64_t>(count), byte_offset);
        ggml_tensor * allocation_anchor = ggml_new_tensor_1d(value->context, GGML_TYPE_F32, 1);
        if (value->tensor == nullptr || allocation_anchor == nullptr) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device subvector descriptor");
        }
        value->buffer = ggml_backend_alloc_ctx_tensors(value->context, epoch->backend);
        if (value->buffer == nullptr) return resource_wait(sizeof(float), "device view descriptor");
        value->count = count;
        value->parent = input;
        epoch->values.emplace_back(value);
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to register device subvector view");
    }
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_embedding(
    const std::shared_ptr<DeviceEpochState> & epoch, const char * name, uint64_t token,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (name == nullptr || out_value == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device embedding requires a tensor name and output handle");
    }
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    TensorEntry * entry = find(name);
    if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "device embedding tensor was not found");
    if (entry->expert || entry->tensor == nullptr || entry->info.rank < 2 ||
        token >= static_cast<uint64_t>(entry->tensor->ne[1]) ||
        token > static_cast<uint64_t>(std::numeric_limits<int32_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device embedding token is outside a resident dense rank-2 tensor");
    }
    const size_t width = static_cast<size_t>(entry->tensor->ne[0]);
    if (width == 0) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device embedding width is empty");
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, width, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device embedding graph context");
    ggml_tensor * index = ggml_new_tensor_1d(workspace.context, GGML_TYPE_I32, 1);
    ggml_tensor * row = index == nullptr ? nullptr : ggml_get_rows(workspace.context, entry->tensor, index);
    ggml_tensor * flat = row == nullptr ? nullptr : ggml_reshape_1d(workspace.context, row, static_cast<int64_t>(width));
    ggml_tensor * copy = flat == nullptr ? nullptr : ggml_cpy(workspace.context, flat, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected resident device embedding shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 32)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device embedding graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "embedding gather graph");
    const int32_t index_value = static_cast<int32_t>(token);
    ggml_backend_tensor_set(index, &index_value, 0, sizeof(index_value));
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device embedding graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_matvec(
    const std::shared_ptr<DeviceEpochState> & epoch, const char * name,
    const std::shared_ptr<DeviceTensorValue> & input, int32_t expert,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (name == nullptr || out_value == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device matvec requires a tensor name and output handle");
    }
    const char * names[1] = {name};
    const int32_t experts[1] = {expert};
    std::vector<std::shared_ptr<DeviceTensorValue>> outputs;
    const int rc = device_matvec_many(epoch, names, experts, 1, input, &outputs);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    *out_value = std::move(outputs[0]);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_matvec_many(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const char * const * names, const int32_t * experts, size_t request_count,
    const std::shared_ptr<DeviceTensorValue> & input,
    std::vector<std::shared_ptr<DeviceTensorValue>> * out_values
) {
    if (names == nullptr || experts == nullptr || request_count == 0 || out_values == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device matvec_many requires names, experts, requests and outputs");
    }
    out_values->clear();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    struct Request {
        TensorEntry * entry = nullptr;
        ggml_tensor * matrix = nullptr;
        size_t cols = 0;
        size_t rows = 0;
    };
    try {
        std::vector<Request> requests;
        requests.reserve(request_count);
        for (size_t i = 0; i < request_count; ++i) {
            if (names[i] == nullptr) {
                return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device matvec_many contains a null tensor name");
            }
            TensorEntry * entry = find(names[i]);
            if (entry == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "device projection tensor was not found");
            if (entry->info.rank < 1 || entry->tensor->ne[0] <= 0 || entry->tensor->ne[1] <= 0) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device matvec requires a non-empty matrix");
            }
            const size_t cols = static_cast<size_t>(entry->tensor->ne[0]);
            const size_t rows = static_cast<size_t>(entry->tensor->ne[1]);
            if (input->count != cols) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device matvec input width does not match matrix");
            if (entry->expert) {
                std::string reason;
                if (!validate_expert(*entry, experts[i], reason)) {
                    return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, std::move(reason));
                }
            } else if (experts[i] >= 0) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "expert index supplied for a dense device projection");
            }
            requests.push_back(Request{entry, nullptr, cols, rows});
        }

        for (size_t i = 0; i < request_count; ++i) {
            Request & request = requests[i];
            if (request.entry->expert) {
                rc = prefetch_locked(*request.entry, experts[i]);
                if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
                const auto slice = request.entry->slices.find(experts[i]);
                if (slice == request.entry->slices.end() || slice->second.tensor == nullptr) {
                    return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "selected expert slice is not resident");
                }
                request.matrix = slice->second.tensor;
            } else {
                request.matrix = request.entry->tensor;
            }
        }

        size_t context_extra = 0;
        size_t graph_nodes = 0;
        if (!checked_mul(request_count, size_t{4096}, context_extra) ||
            !checked_mul(request_count, size_t{2}, graph_nodes) ||
            !checked_add(graph_nodes, size_t{8}, graph_nodes) ||
            graph_nodes > static_cast<size_t>(std::numeric_limits<int>::max())) {
            return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device matvec_many graph size overflows");
        }
        std::vector<std::shared_ptr<DeviceTensorValue>> values;
        std::vector<ggml_tensor *> roots;
        values.reserve(request_count);
        roots.reserve(request_count);
        for (const Request & request : requests) {
            std::shared_ptr<DeviceTensorValue> value;
            rc = make_device_value(epoch, request.rows, &value);
            if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
            values.push_back(std::move(value));
        }

        DeviceGraphWorkspace workspace;
        if (!workspace.init(context_extra)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device projection graph context");
        }
        for (size_t i = 0; i < request_count; ++i) {
            ggml_tensor * projection = ggml_mul_mat(workspace.context, requests[i].matrix, input->tensor);
            if (projection == nullptr || projection->ne[0] != static_cast<int64_t>(requests[i].rows) ||
                static_cast<size_t>(ggml_nelements(projection)) != requests[i].rows) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device projection dimensions");
            }
            ggml_tensor * copy = ggml_cpy(workspace.context, projection, values[i]->tensor);
            if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device projection output shape");
            roots.push_back(copy);
        }
        if (!workspace.build(roots, graph_nodes)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device projection graph");
        }
        if (!workspace.allocate(epoch->backend)) {
            return resource_wait(device_context_bytes(workspace.context), "projection graph");
        }
        if (!workspace.compute(epoch->backend, epoch->threads)) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device projection graph failed");
        }
        *out_values = std::move(values);
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device matvec_many state");
    }
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_unary(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, int operation,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device unary operation requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (operation != 0 && operation != 1) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "unsupported device unary operation");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device unary graph context");
    ggml_tensor * result = operation == 0
        ? ggml_silu(workspace.context, input->tensor)
        : ggml_sigmoid(workspace.context, input->tensor);
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device unary activation");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 16)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device unary graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "unary graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device unary graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_scale(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, float scale,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device scale requires an output handle");
    out_value->reset();
    if (!std::isfinite(scale)) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device scale must be finite");
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device scale graph context");
    ggml_tensor * result = ggml_scale(workspace.context, input->tensor, scale);
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device scale shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 16)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device scale graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "scale graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device scale graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_low_rank_affine(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, const char * method_id,
    const float * a, size_t input_width, size_t rank, const float * b,
    size_t output_width, const float * bias,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr || method_id == nullptr || method_id[0] == '\0' ||
        a == nullptr || b == nullptr || bias == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "low-rank affine requires method identity and coefficient arrays");
    }
    out_value->reset();
    if (input_width == 0 || rank == 0 || output_width == 0 ||
        input_width > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        rank > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        output_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "low-rank affine dimensions are invalid");
    }
    size_t acount = 0, bcount = 0, total = 0;
    if (!checked_mul(input_width, rank, acount) ||
        !checked_mul(rank, output_width, bcount) ||
        !checked_add(acount, bcount, total) ||
        !checked_add(total, output_width, total) || total > 16U * 1024U * 1024U) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "low-rank affine coefficients exceed the bounded size limit");
    }
    for (size_t i = 0; i < acount; ++i) if (!std::isfinite(a[i]))
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "low-rank affine A contains a non-finite value");
    for (size_t i = 0; i < bcount; ++i) if (!std::isfinite(b[i]))
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "low-rank affine B contains a non-finite value");
    for (size_t i = 0; i < output_width; ++i) if (!std::isfinite(bias[i]))
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "low-rank affine bias contains a non-finite value");

    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (input->count % input_width != 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "low-rank affine input is not a whole number of rows");
    }
    const size_t rows = input->count / input_width;
    size_t output_count = 0;
    if (rows == 0 || !checked_mul(rows, output_width, output_count) ||
        output_count > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "low-rank affine output size overflows");
    }
    std::string key(method_id);
    AffineCoefficients * coeff = nullptr;
    auto found = epoch->affine_coefficients.find(key);
    if (found != epoch->affine_coefficients.end()) {
        coeff = found->second.get();
        if (coeff->input_width != input_width || coeff->rank != rank ||
            coeff->output_width != output_width) {
            return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "method identity was reused with different low-rank affine dimensions");
        }
        // Compare in logical order using owned copies: a repeated key is immutable.
        for (size_t r = 0; r < rank; ++r) for (size_t i = 0; i < input_width; ++i)
            if (coeff->a_values[r * input_width + i] != a[i * rank + r])
                return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "method identity was reused with different A coefficients");
        for (size_t o = 0; o < output_width; ++o) for (size_t r = 0; r < rank; ++r)
            if (coeff->b_values[o * rank + r] != b[r * output_width + o])
                return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "method identity was reused with different B coefficients");
        if (!std::equal(coeff->bias_values.begin(), coeff->bias_values.end(), bias))
            return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "method identity was reused with different bias coefficients");
    } else {
        std::unique_ptr<AffineCoefficients> created(new (std::nothrow) AffineCoefficients());
        if (!created) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate low-rank affine coefficient owner");
        coeff = created.get();
        coeff->input_width = input_width;
        coeff->rank = rank;
        coeff->output_width = output_width;
        try {
            coeff->a_values.resize(acount);
            coeff->b_values.resize(bcount);
            coeff->bias_values.assign(bias, bias + output_width);
            for (size_t r = 0; r < rank; ++r) for (size_t i = 0; i < input_width; ++i)
                coeff->a_values[r * input_width + i] = a[i * rank + r];
            for (size_t o = 0; o < output_width; ++o) for (size_t r = 0; r < rank; ++r)
                coeff->b_values[o * rank + r] = b[r * output_width + o];
        } catch (const std::exception &) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to retain low-rank affine coefficients");
        }
        ggml_init_params params{};
        params.mem_size = kContextBytes;
        params.no_alloc = true;
        coeff->context = ggml_init(params);
        if (coeff->context == nullptr) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate low-rank affine tensor context");
        coeff->a = ggml_new_tensor_2d(coeff->context, GGML_TYPE_F32,
            static_cast<int64_t>(input_width), static_cast<int64_t>(rank));
        coeff->b = ggml_new_tensor_2d(coeff->context, GGML_TYPE_F32,
            static_cast<int64_t>(rank), static_cast<int64_t>(output_width));
        coeff->bias = ggml_new_tensor_1d(coeff->context, GGML_TYPE_F32, static_cast<int64_t>(output_width));
        if (coeff->a == nullptr || coeff->b == nullptr || coeff->bias == nullptr)
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate low-rank affine tensors");
        coeff->buffer = ggml_backend_alloc_ctx_tensors(coeff->context, epoch->backend);
        if (coeff->buffer == nullptr)
            return resource_wait((total * sizeof(float)), "low-rank affine coefficients");
        ggml_backend_tensor_set(coeff->a, coeff->a_values.data(), 0, acount * sizeof(float));
        ggml_backend_tensor_set(coeff->b, coeff->b_values.data(), 0, bcount * sizeof(float));
        ggml_backend_tensor_set(coeff->bias, coeff->bias_values.data(), 0, output_width * sizeof(float));
        try {
            epoch->affine_coefficients.emplace(std::move(key), std::move(created));
        } catch (const std::exception &) {
            return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to cache low-rank affine coefficients");
        }
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, output_count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate low-rank affine graph context");
    ggml_tensor * rows_input = ggml_reshape_2d(workspace.context, input->tensor,
        static_cast<int64_t>(input_width), static_cast<int64_t>(rows));
    ggml_tensor * hidden = rows_input == nullptr ? nullptr : ggml_mul_mat(workspace.context, coeff->a, rows_input);
    ggml_tensor * projected = hidden == nullptr ? nullptr : ggml_mul_mat(workspace.context, coeff->b, hidden);
    ggml_tensor * summed = projected == nullptr ? nullptr : ggml_add(workspace.context, projected, coeff->bias);
    ggml_tensor * copy = summed == nullptr ? nullptr : ggml_cpy(workspace.context, summed, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected low-rank affine dimensions");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 32)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build low-rank affine graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "low-rank affine graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML low-rank affine graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_binary(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & left,
    const std::shared_ptr<DeviceTensorValue> & right, bool multiply,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device binary operation requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, left);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, right);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (left->count != right->count && (!multiply || right->count != 1)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device binary operands must have equal widths");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, left->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device binary graph context");
    ggml_tensor * result = multiply
        ? ggml_mul(workspace.context, left->tensor, right->tensor)
        : ggml_add(workspace.context, left->tensor, right->tensor);
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device binary shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 16)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device binary graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "binary graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device binary graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_concat(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & left,
    const std::shared_ptr<DeviceTensorValue> & right,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device concat requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, left);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, right);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t count = 0;
    if (!checked_add(left->count, right->count, count)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device concat width overflows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device concat graph context");
    ggml_tensor * joined = ggml_concat(workspace.context, left->tensor, right->tensor, 0);
    ggml_tensor * copy = joined == nullptr ? nullptr : ggml_cpy(workspace.context, joined, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device concat shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 24)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device concat graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "concat graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device concat graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_norm_rows(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, size_t row_width,
    float epsilon, bool sum_squares, const char * weight_name,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device row normalization requires an output handle");
    out_value->reset();
    if (row_width == 0 || !std::isfinite(epsilon) || epsilon < 0.0f) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device row normalization width or epsilon is invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (input->count % row_width != 0 ||
        row_width > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        input->count / row_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device row normalization dimensions do not divide the input");
    }
    TensorEntry * weight = nullptr;
    if (weight_name != nullptr) {
        weight = find(weight_name);
        if (weight == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "device row normalization weight was not found");
        if (weight->expert || weight->tensor == nullptr || weight->tensor->type != GGML_TYPE_F32 ||
            weight->info.element_count != row_width) {
            return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device row normalization weight must be a resident F32 vector matching the row width");
        }
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device row-normalization graph context");
    const int64_t rows = static_cast<int64_t>(input->count / row_width);
    const int64_t width = static_cast<int64_t>(row_width);
    ggml_tensor * matrix = ggml_reshape_2d(workspace.context, input->tensor, width, rows);
    ggml_tensor * squares = matrix == nullptr ? nullptr : ggml_sqr(workspace.context, matrix);
    ggml_tensor * sums = squares == nullptr ? nullptr : ggml_sum_rows(workspace.context, squares);
    ggml_tensor * reduced = sums;
    if (reduced != nullptr && !sum_squares) {
        reduced = ggml_scale(workspace.context, reduced, 1.0f / static_cast<float>(row_width));
    }
    ggml_tensor * epsilon_value = ggml_new_tensor_1d(workspace.context, GGML_TYPE_F32, 1);
    ggml_tensor * shifted = (reduced == nullptr || epsilon_value == nullptr)
        ? nullptr
        : ggml_add(workspace.context, reduced, epsilon_value);
    ggml_tensor * denominator = shifted == nullptr ? nullptr : ggml_sqrt(workspace.context, shifted);
    ggml_tensor * normalized = denominator == nullptr ? nullptr : ggml_div(workspace.context, matrix, denominator);
    ggml_tensor * weighted = normalized;
    if (weighted != nullptr && weight != nullptr) {
        weighted = ggml_mul(workspace.context, weighted, weight->tensor);
    }
    ggml_tensor * flat = weighted == nullptr ? nullptr : ggml_reshape_1d(workspace.context, weighted, static_cast<int64_t>(input->count));
    ggml_tensor * copy = flat == nullptr ? nullptr : ggml_cpy(workspace.context, flat, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device row-normalization shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 48)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device row-normalization graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "row-normalization graph");
    ggml_backend_tensor_set(epsilon_value, &epsilon, 0, sizeof(epsilon));
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device row-normalization graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_mul_rows(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input,
    const std::shared_ptr<DeviceTensorValue> & row_scales, size_t row_width,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device row multiply requires an output handle");
    out_value->reset();
    if (row_width == 0 || row_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device row multiply width is invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, row_scales);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (input->count % row_width != 0 ||
        input->count / row_width != row_scales->count ||
        input->count / row_width > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device row scales do not match the input rows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device row-multiply graph context");
    ggml_tensor * matrix = ggml_reshape_2d(
        workspace.context, input->tensor, static_cast<int64_t>(row_width),
        static_cast<int64_t>(row_scales->count)
    );
    ggml_tensor * scales = ggml_reshape_2d(
        workspace.context, row_scales->tensor, 1, static_cast<int64_t>(row_scales->count)
    );
    ggml_tensor * result = (matrix == nullptr || scales == nullptr)
        ? nullptr
        : ggml_mul(workspace.context, matrix, scales);
    ggml_tensor * flat = result == nullptr ? nullptr : ggml_reshape_1d(workspace.context, result, static_cast<int64_t>(input->count));
    ggml_tensor * copy = flat == nullptr ? nullptr : ggml_cpy(workspace.context, flat, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device row-multiply shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 32)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device row-multiply graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "row-multiply graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device row-multiply graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_exp_clipped(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, float lower, float upper,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device clipped exponential requires an output handle");
    out_value->reset();
    if (!std::isfinite(lower) || !std::isfinite(upper) || lower > upper) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device clipped exponential bounds are invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device clipped-exponential graph context");
    ggml_tensor * clipped_input = ggml_dup(workspace.context, input->tensor);
    ggml_tensor * clipped = clipped_input == nullptr
        ? nullptr
        : ggml_clamp(workspace.context, clipped_input, lower, upper);
    ggml_tensor * result = clipped == nullptr ? nullptr : ggml_exp(workspace.context, clipped);
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device clipped-exponential shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 24)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device clipped-exponential graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "clipped-exponential graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device clipped-exponential graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_softplus(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device softplus requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device softplus graph context");
    ggml_tensor * result = ggml_softplus(workspace.context, input->tensor);
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device softplus shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 24)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device softplus graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "softplus graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device softplus graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_probability(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, bool positive_normalize,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device probability operation requires an output handle");
    out_value->reset();
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device probability graph context");
    ggml_tensor * result = nullptr;
    if (positive_normalize) {
        ggml_tensor * positive_input = ggml_dup(workspace.context, input->tensor);
        ggml_tensor * positive = positive_input == nullptr
            ? nullptr
            : ggml_clamp(workspace.context, positive_input, 0.0f, std::numeric_limits<float>::max());
        ggml_tensor * total = positive == nullptr ? nullptr : ggml_sum(workspace.context, positive);
        result = total == nullptr ? nullptr : ggml_div(workspace.context, positive, total);
    } else {
        result = ggml_soft_max(workspace.context, input->tensor);
    }
    ggml_tensor * copy = result == nullptr ? nullptr : ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device probability shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 32)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device probability graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "probability graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device probability graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_recurrent_conv(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & history, const char * kernel_name,
    size_t channels, std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (kernel_name == nullptr || out_value == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device recurrent convolution requires a kernel name and output handle");
    }
    out_value->reset();
    if (channels == 0 || channels > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device recurrent convolution channel width is invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, history);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (history->count % channels != 0) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent history is not channel-aligned");
    }
    TensorEntry * kernel = find(kernel_name);
    if (kernel == nullptr) return fail(CASSIFI_WEIGHT_BANK_NOT_FOUND, "device recurrent convolution kernel was not found");
    if (kernel->expert || kernel->tensor == nullptr || kernel->tensor->type != GGML_TYPE_F32 ||
        kernel->info.rank < 2 || kernel->tensor->ne[1] != static_cast<int64_t>(channels)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent convolution kernel must be resident F32 [taps, channels]");
    }
    const size_t kernel_size = static_cast<size_t>(kernel->tensor->ne[0]);
    size_t expected_kernel_count = 0;
    if (kernel_size == 0 || !checked_mul(kernel_size, channels, expected_kernel_count) ||
        kernel->info.element_count != expected_kernel_count) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent convolution kernel dimensions are invalid");
    }
    const size_t history_rows = history->count / channels;
    if (history_rows == 0) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent convolution history is empty");
    const size_t tap_count = std::min(history_rows, kernel_size);
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, channels, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t extra_bytes = 0;
    size_t node_capacity = 0;
    if (!checked_mul(tap_count, static_cast<size_t>(4096), extra_bytes) ||
        !checked_mul(tap_count, static_cast<size_t>(8), node_capacity) ||
        !checked_add(node_capacity, static_cast<size_t>(16), node_capacity)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent convolution graph size overflows");
    }
    DeviceGraphWorkspace workspace;
    if (!workspace.init(extra_bytes)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device recurrent-convolution graph context");
    ggml_tensor * accumulated = nullptr;
    for (size_t tap = 0; tap < tap_count; ++tap) {
        const size_t history_row = history_rows - 1 - tap;
        const size_t history_offset = history_row * channels * sizeof(float);
        const size_t kernel_offset = (kernel_size - 1 - tap) * kernel->tensor->nb[0];
        ggml_tensor * sample = ggml_view_1d(
            workspace.context, history->tensor, static_cast<int64_t>(channels), history_offset
        );
        ggml_tensor * kernel_column = ggml_view_2d(
            workspace.context, kernel->tensor, 1, static_cast<int64_t>(channels),
            kernel->tensor->nb[1], kernel_offset
        );
        ggml_tensor * contiguous_kernel = kernel_column == nullptr ? nullptr : ggml_cont(workspace.context, kernel_column);
        ggml_tensor * kernel_vector = contiguous_kernel == nullptr
            ? nullptr
            : ggml_reshape_1d(workspace.context, contiguous_kernel, static_cast<int64_t>(channels));
        ggml_tensor * contribution = (sample == nullptr || kernel_vector == nullptr)
            ? nullptr
            : ggml_mul(workspace.context, sample, kernel_vector);
        accumulated = contribution == nullptr
            ? nullptr
            : (accumulated == nullptr ? contribution : ggml_add(workspace.context, accumulated, contribution));
        if (accumulated == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device recurrent-convolution tap shapes");
    }
    ggml_tensor * copy = ggml_cpy(workspace.context, accumulated, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device recurrent-convolution output shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, node_capacity)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device recurrent-convolution graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "recurrent-convolution graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device recurrent-convolution graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_recurrent_state_op(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & state,
    const std::shared_ptr<DeviceTensorValue> & keys_or_queries,
    const std::shared_ptr<DeviceTensorValue> & deltas, int operation,
    size_t value_heads, size_t key_heads, size_t value_dim, size_t key_dim,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device recurrent-state operation requires an output handle");
    out_value->reset();
    if (operation < 0 || operation > 2 || value_heads == 0 || key_heads == 0 ||
        value_dim == 0 || key_dim == 0 || value_heads < key_heads ||
        value_heads % key_heads != 0 ||
        value_heads > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        key_heads > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        value_dim > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        key_dim > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device recurrent-state dimensions are invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, state);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, keys_or_queries);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (operation == 1) {
        rc = validate_device_value(epoch, deltas);
        if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    }
    size_t matrix_count = 0;
    size_t state_count = 0;
    size_t key_count = 0;
    size_t result_count = 0;
    if (!checked_mul(value_dim, key_dim, matrix_count) ||
        !checked_mul(value_heads, matrix_count, state_count) ||
        !checked_mul(key_heads, key_dim, key_count) ||
        !checked_mul(value_heads, value_dim, result_count)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent-state dimensions overflow");
    }
    if (state->count != state_count || keys_or_queries->count != key_count ||
        (operation == 1 && deltas->count != result_count)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent-state tensors do not match declared dimensions");
    }
    const size_t output_count = operation == 1 ? state_count : result_count;
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, output_count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t extra_bytes = 0;
    size_t node_capacity = 0;
    if (!checked_mul(value_heads, static_cast<size_t>(4096), extra_bytes) ||
        !checked_mul(value_heads, static_cast<size_t>(10), node_capacity) ||
        !checked_add(node_capacity, static_cast<size_t>(32), node_capacity)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device recurrent-state graph size overflows");
    }
    DeviceGraphWorkspace workspace;
    if (!workspace.init(extra_bytes)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device recurrent-state graph context");
    std::vector<ggml_tensor *> roots;
    try {
        roots.reserve(value_heads);
        for (size_t head = 0; head < value_heads; ++head) {
            const size_t key_head = head % key_heads;
            const size_t state_offset = head * matrix_count * sizeof(float);
            const size_t key_offset = key_head * key_dim * sizeof(float);
            ggml_tensor * state_matrix = ggml_view_2d(
                workspace.context, state->tensor, static_cast<int64_t>(key_dim),
                static_cast<int64_t>(value_dim), key_dim * sizeof(float), state_offset
            );
            ggml_tensor * key_vector = ggml_view_1d(
                workspace.context, keys_or_queries->tensor,
                static_cast<int64_t>(key_dim), key_offset
            );
            if (state_matrix == nullptr || key_vector == nullptr) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device recurrent-state input views");
            }
            if (operation == 1) {
                ggml_tensor * delta_vector = ggml_view_1d(
                    workspace.context, deltas->tensor, static_cast<int64_t>(value_dim),
                    head * value_dim * sizeof(float)
                );
                ggml_tensor * key_column = ggml_reshape_2d(
                    workspace.context, key_vector, static_cast<int64_t>(key_dim), 1
                );
                ggml_tensor * delta_row = delta_vector == nullptr
                    ? nullptr
                    : ggml_reshape_2d(workspace.context, delta_vector, 1, static_cast<int64_t>(value_dim));
                ggml_tensor * repeated_key = (key_column == nullptr)
                    ? nullptr
                    : ggml_repeat(workspace.context, key_column, state_matrix);
                ggml_tensor * outer = (repeated_key == nullptr || delta_row == nullptr)
                    ? nullptr
                    : ggml_mul(workspace.context, repeated_key, delta_row);
                ggml_tensor * updated = outer == nullptr
                    ? nullptr
                    : ggml_add(workspace.context, state_matrix, outer);
                ggml_tensor * destination = ggml_view_2d(
                    workspace.context, value->tensor, static_cast<int64_t>(key_dim),
                    static_cast<int64_t>(value_dim), key_dim * sizeof(float), state_offset
                );
                ggml_tensor * copy = (updated == nullptr || destination == nullptr)
                    ? nullptr
                    : ggml_cpy(workspace.context, updated, destination);
                if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device recurrent-state update shapes");
                roots.push_back(copy);
            } else {
                ggml_tensor * prediction = ggml_mul_mat(workspace.context, state_matrix, key_vector);
                ggml_tensor * destination = ggml_view_1d(
                    workspace.context, value->tensor, static_cast<int64_t>(value_dim),
                    head * value_dim * sizeof(float)
                );
                ggml_tensor * copy = (prediction == nullptr || destination == nullptr)
                    ? nullptr
                    : ggml_cpy(workspace.context, prediction, destination);
                if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device recurrent-state projection shapes");
                roots.push_back(copy);
            }
        }
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device recurrent-state graph nodes");
    }
    if (!workspace.build(roots, node_capacity)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device recurrent-state graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "recurrent-state graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device recurrent-state graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_rope(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & input, int64_t position,
    const int32_t * sections, size_t section_count, double base,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr || (section_count != 0 && sections == nullptr)) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device RoPE requires valid section metadata and an output handle");
    }
    out_value->reset();
    if (!std::isfinite(base) || base <= 0.0 ||
        position < std::numeric_limits<int32_t>::min() ||
        position > std::numeric_limits<int32_t>::max() ||
        section_count > 64) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device RoPE position, base, or section count is invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    if (input->count > static_cast<size_t>(std::numeric_limits<int32_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device RoPE head width exceeds GGML's paired-dimension limit");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, input->count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    const size_t configured_sections = section_count == 0 ? 1 : section_count;
    size_t extra_bytes = 0;
    size_t node_capacity = 0;
    if (!checked_mul(configured_sections + 1, static_cast<size_t>(2048), extra_bytes) ||
        !checked_mul(configured_sections + 1, static_cast<size_t>(12), node_capacity) ||
        !checked_add(node_capacity, static_cast<size_t>(32), node_capacity)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device RoPE graph size overflows");
    }
    DeviceGraphWorkspace workspace;
    if (!workspace.init(extra_bytes)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device RoPE graph context");
    ggml_tensor * position_tensor = ggml_new_tensor_1d(workspace.context, GGML_TYPE_I32, 1);
    if (position_tensor == nullptr) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device RoPE position tensor");
    std::vector<ggml_tensor *> pieces;
    try {
        pieces.reserve(configured_sections + 1);
        size_t offset = 0;
        for (size_t index = 0; index < configured_sections && offset < input->count; ++index) {
            const int32_t raw_section = section_count == 0
                ? static_cast<int32_t>(std::min(input->count, static_cast<size_t>(std::numeric_limits<int32_t>::max())))
                : sections[index];
            if (raw_section <= 0) continue;
            const size_t section_length = static_cast<size_t>(raw_section);
            const size_t section_count_in_input = std::min(section_length, input->count - offset);
            const size_t rotated_count = section_count_in_input & ~static_cast<size_t>(1);
            ggml_tensor * piece = nullptr;
            if (rotated_count != 0) {
                const double adjusted_base = std::pow(base, static_cast<double>(rotated_count) / static_cast<double>(section_length));
                const float rope_base = static_cast<float>(adjusted_base);
                if (!std::isfinite(adjusted_base) || !std::isfinite(rope_base) || rope_base <= 0.0f) {
                    return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device RoPE adjusted section base is not representable");
                }
                ggml_tensor * segment = ggml_view_1d(
                    workspace.context, input->tensor, static_cast<int64_t>(rotated_count),
                    offset * sizeof(float)
                );
                ggml_tensor * rotated = segment == nullptr ? nullptr : ggml_rope_ext(
                    workspace.context, segment, position_tensor, nullptr,
                    static_cast<int>(rotated_count), GGML_ROPE_TYPE_NORMAL, 0,
                    rope_base, 1.0f, 0.0f, 1.0f, 0.0f, 0.0f
                );
                if (rotated == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device RoPE section shape");
                piece = rotated;
            }
            if (rotated_count < section_count_in_input) {
                ggml_tensor * tail = ggml_view_1d(
                    workspace.context, input->tensor,
                    static_cast<int64_t>(section_count_in_input - rotated_count),
                    (offset + rotated_count) * sizeof(float)
                );
                if (tail == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device RoPE odd-tail view");
                piece = piece == nullptr ? tail : ggml_concat(workspace.context, piece, tail, 0);
            }
            if (piece == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML failed to compose a device RoPE section");
            pieces.push_back(piece);
            offset += section_count_in_input;
        }
        size_t total_covered = 0;
        for (const ggml_tensor * piece : pieces) {
            if (!checked_add(total_covered, static_cast<size_t>(piece->ne[0]), total_covered)) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device RoPE section coverage overflows");
            }
        }
        if (total_covered < input->count) {
            ggml_tensor * remainder = ggml_view_1d(
                workspace.context, input->tensor,
                static_cast<int64_t>(input->count - total_covered), total_covered * sizeof(float)
            );
            if (remainder == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device RoPE remainder view");
            pieces.push_back(remainder);
        }
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device RoPE graph nodes");
    }
    ggml_tensor * result = pieces.front();
    for (size_t index = 1; index < pieces.size(); ++index) {
        result = ggml_concat(workspace.context, result, pieces[index], 0);
        if (result == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device RoPE concatenation");
    }
    ggml_tensor * copy = ggml_cpy(workspace.context, result, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device RoPE output shape");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, node_capacity)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device RoPE graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "RoPE graph");
    const int32_t position_value = static_cast<int32_t>(position);
    ggml_backend_tensor_set(position_tensor, &position_value, 0, sizeof(position_value));
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device RoPE graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_attention_scores(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & query,
    const std::shared_ptr<DeviceTensorValue> & key_cache,
    size_t kv_head, size_t kv_heads, size_t head_dim, float scale,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device attention scores require an output handle");
    out_value->reset();
    if (kv_heads == 0 || head_dim == 0 || kv_head >= kv_heads ||
        head_dim > static_cast<size_t>(std::numeric_limits<int64_t>::max()) ||
        !std::isfinite(scale)) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device attention-score dimensions or scale are invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, query);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, key_cache);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t head_stride = 0;
    size_t stride_bytes = 0;
    size_t head_offset = 0;
    if (query->count != head_dim || !checked_mul(kv_heads, head_dim, head_stride) ||
        key_cache->count % head_stride != 0 ||
        !checked_mul(head_stride, sizeof(float), stride_bytes) ||
        !checked_mul(kv_head, head_dim, head_offset) ||
        !checked_mul(head_offset, sizeof(float), head_offset)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device attention key cache shape does not match the query head");
    }
    const size_t sequence = key_cache->count / head_stride;
    if (sequence == 0 || sequence > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device attention key cache has no valid sequence rows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, sequence, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device attention-score graph context");
    ggml_tensor * view = ggml_view_2d(
        workspace.context, key_cache->tensor, static_cast<int64_t>(head_dim),
        static_cast<int64_t>(sequence), stride_bytes, head_offset
    );
    ggml_tensor * contiguous = view == nullptr ? nullptr : ggml_cont(workspace.context, view);
    ggml_tensor * scores = contiguous == nullptr ? nullptr : ggml_mul_mat(workspace.context, contiguous, query->tensor);
    ggml_tensor * scaled = scores == nullptr ? nullptr : ggml_scale(workspace.context, scores, scale);
    ggml_tensor * copy = scaled == nullptr ? nullptr : ggml_cpy(workspace.context, scaled, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device attention-score shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 32)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device attention-score graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "attention-score graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device attention-score graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_attention_context(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & probabilities,
    const std::shared_ptr<DeviceTensorValue> & value_cache,
    size_t kv_head, size_t kv_heads, size_t value_dim,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (out_value == nullptr) return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device attention context requires an output handle");
    out_value->reset();
    if (kv_heads == 0 || value_dim == 0 || kv_head >= kv_heads ||
        value_dim > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device attention-context dimensions are invalid");
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, probabilities);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, value_cache);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t head_stride = 0;
    size_t stride_bytes = 0;
    size_t head_offset = 0;
    if (!checked_mul(kv_heads, value_dim, head_stride) ||
        value_cache->count % head_stride != 0 ||
        !checked_mul(head_stride, sizeof(float), stride_bytes) ||
        !checked_mul(kv_head, value_dim, head_offset) ||
        !checked_mul(head_offset, sizeof(float), head_offset)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device attention value-cache shape is invalid");
    }
    const size_t sequence = value_cache->count / head_stride;
    if (sequence == 0 || sequence != probabilities->count ||
        sequence > static_cast<size_t>(std::numeric_limits<int64_t>::max())) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device attention probabilities do not match value-cache sequence rows");
    }
    std::shared_ptr<DeviceTensorValue> value;
    rc = make_device_value(epoch, value_dim, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    DeviceGraphWorkspace workspace;
    if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device attention-context graph context");
    ggml_tensor * view = ggml_view_2d(
        workspace.context, value_cache->tensor, static_cast<int64_t>(value_dim),
        static_cast<int64_t>(sequence), stride_bytes, head_offset
    );
    ggml_tensor * contiguous_rows = view == nullptr ? nullptr : ggml_cont(workspace.context, view);
    ggml_tensor * transposed = contiguous_rows == nullptr ? nullptr : ggml_transpose(workspace.context, contiguous_rows);
    ggml_tensor * contiguous_matrix = transposed == nullptr ? nullptr : ggml_cont(workspace.context, transposed);
    ggml_tensor * context = contiguous_matrix == nullptr
        ? nullptr
        : ggml_mul_mat(workspace.context, contiguous_matrix, probabilities->tensor);
    ggml_tensor * copy = context == nullptr ? nullptr : ggml_cpy(workspace.context, context, value->tensor);
    if (copy == nullptr) return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device attention-context shapes");
    std::vector<ggml_tensor *> roots{copy};
    if (!workspace.build(roots, 40)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device attention-context graph");
    if (!workspace.allocate(epoch->backend)) return resource_wait(device_context_bytes(workspace.context), "attention-context graph");
    if (!workspace.compute(epoch->backend, epoch->threads)) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend device attention-context graph failed");
    *out_value = std::move(value);
    return CASSIFI_WEIGHT_BANK_OK;
}

int WeightBank::device_exchange(
    const std::shared_ptr<DeviceEpochState> & epoch, const char * site,
    const std::shared_ptr<DeviceTensorValue> & input,
    std::shared_ptr<DeviceTensorValue> * out_value,
    std::shared_ptr<DeviceTensorValue> * out_scale,
    std::shared_ptr<DeviceTensorValue> * out_delta
) {
    if (site == nullptr || out_value == nullptr || out_scale == nullptr || out_delta == nullptr) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device exchange requires a site name and three output handles");
    }
    out_value->reset();
    out_scale->reset();
    out_delta->reset();
    size_t site_length = 0;
    while (site_length <= 512 && site[site_length] != '\0') ++site_length;
    if (site_length == 0 || site_length > 512) {
        return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device exchange site must contain 1 to 512 UTF-8 bytes");
    }
    for (size_t i = 0; i < site_length; ++i) {
        if (static_cast<unsigned char>(site[i]) < 32U) {
            return fail(CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT, "device exchange site contains a control byte");
        }
    }
    std::lock_guard<std::mutex> lock(mutex_);
    int rc = validate_device_epoch(epoch, true);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    rc = validate_device_value(epoch, input);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    size_t chunk_numerator = 0;
    if (!checked_add(input->count, epoch->mode_count - 1, chunk_numerator)) {
        return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device exchange chunk count overflows");
    }
    const size_t chunk_count = chunk_numerator / epoch->mode_count;
    std::shared_ptr<DeviceTensorValue> output;
    rc = make_device_value(epoch, input->count, &output);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> scale_capture;
    rc = make_device_value(epoch, 1, &scale_capture);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    std::shared_ptr<DeviceTensorValue> delta_capture;
    rc = make_device_value(epoch, input->count, &delta_capture);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    try {
        for (size_t chunk_index = 0; chunk_index < chunk_count; ++chunk_index) {
            size_t start = 0;
            if (!checked_mul(chunk_index, epoch->mode_count, start) || start >= input->count) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "device exchange chunk offset is invalid");
            }
            const size_t chunk_width = std::min(epoch->mode_count, input->count - start);
            size_t mode_offset = 0;
            if (!site_mode_offset(site, site_length, chunk_index, epoch->mode_count, &mode_offset)) {
                return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to map device exchange site to membrane modes");
            }
            std::vector<int32_t> row_indices(chunk_width);
            size_t mode = mode_offset;
            for (size_t i = 0; i < chunk_width; ++i) {
                row_indices[i] = static_cast<int32_t>(mode);
                ++mode;
                if (mode == epoch->mode_count) mode = 0;
            }

            DeviceGraphWorkspace workspace;
            if (!workspace.init()) return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device exchange graph context");
            ggml_tensor * indices = ggml_new_tensor_1d(
                workspace.context, GGML_TYPE_I32, static_cast<int64_t>(chunk_width));
            ggml_tensor * input_view = ggml_view_1d(
                workspace.context,
                input->tensor,
                static_cast<int64_t>(chunk_width),
                start * sizeof(float)
            );
            ggml_tensor * input_rows = input_view == nullptr
                ? nullptr
                : ggml_reshape_2d(workspace.context, input_view, 1, static_cast<int64_t>(chunk_width));
            ggml_tensor * scale = scale_capture->tensor;
            if (chunk_index == 0) {
                ggml_tensor * mean_square = ggml_mean(
                    workspace.context, ggml_sqr(workspace.context, input->tensor));
                scale = mean_square == nullptr
                    ? nullptr
                    : ggml_clamp(
                        workspace.context,
                        ggml_sqrt(workspace.context, mean_square),
                        1.0e-6f,
                        std::numeric_limits<float>::max()
                    );
            }
            ggml_tensor * drive = input_rows == nullptr || scale == nullptr
                ? nullptr
                : ggml_tanh(workspace.context, ggml_div(workspace.context, input_rows, scale));
            ggml_tensor * yang = indices == nullptr
                ? nullptr
                : ggml_get_rows(workspace.context, epoch->planes[1], indices);
            ggml_tensor * yin = indices == nullptr
                ? nullptr
                : ggml_get_rows(workspace.context, epoch->planes[2], indices);
            ggml_tensor * positive = drive == nullptr ? nullptr : ggml_relu(workspace.context, drive);
            ggml_tensor * negative = drive == nullptr
                ? nullptr
                : ggml_relu(workspace.context, ggml_scale(workspace.context, drive, -1.0f));
            ggml_tensor * next_yang = yang == nullptr || positive == nullptr
                ? nullptr
                : ggml_add(
                    workspace.context,
                    ggml_scale(workspace.context, yang, 15.0f / 16.0f),
                    ggml_scale(workspace.context, positive, 1.0f / 16.0f)
                );
            ggml_tensor * next_yin = yin == nullptr || negative == nullptr
                ? nullptr
                : ggml_add(
                    workspace.context,
                    ggml_scale(workspace.context, yin, 15.0f / 16.0f),
                    ggml_scale(workspace.context, negative, 1.0f / 16.0f)
                );
            ggml_tensor * difference = next_yang == nullptr || next_yin == nullptr
                ? nullptr
                : ggml_sub(workspace.context, next_yang, next_yin);
            ggml_tensor * gain_scale = scale == nullptr
                ? nullptr
                : ggml_scale(
                    workspace.context,
                    scale,
                    static_cast<float>(epoch->gain_ppm) / 1'000'000.0f
                );
            ggml_tensor * delta = difference == nullptr || gain_scale == nullptr
                ? nullptr
                : ggml_mul(workspace.context, difference, gain_scale);
            ggml_tensor * exchanged = input_rows == nullptr || delta == nullptr
                ? nullptr
                : (epoch->gain_ppm == 0 ? input_rows : ggml_add(workspace.context, input_rows, delta));
            ggml_tensor * output_rows = exchanged == nullptr
                ? nullptr
                : ggml_reshape_1d(workspace.context, exchanged, static_cast<int64_t>(chunk_width));
            ggml_tensor * output_view = ggml_view_1d(
                workspace.context,
                output->tensor,
                static_cast<int64_t>(chunk_width),
                start * sizeof(float)
            );
            ggml_tensor * output_copy = output_rows == nullptr || output_view == nullptr
                ? nullptr
                : ggml_cpy(workspace.context, output_rows, output_view);
            ggml_tensor * delta_view = ggml_view_1d(
                workspace.context,
                delta_capture->tensor,
                static_cast<int64_t>(chunk_width),
                start * sizeof(float)
            );
            ggml_tensor * delta_copy = delta == nullptr || delta_view == nullptr
                ? nullptr
                : ggml_cpy(workspace.context, delta, delta_view);
            ggml_tensor * scale_copy = chunk_index == 0 && scale != nullptr
                ? ggml_cpy(workspace.context, scale, scale_capture->tensor)
                : nullptr;
            ggml_tensor * next_observation = indices == nullptr || drive == nullptr
                ? nullptr
                : ggml_set_rows(workspace.context, epoch->planes[0], drive, indices);
            ggml_tensor * write_yang = indices == nullptr || next_yang == nullptr
                ? nullptr
                : ggml_set_rows(workspace.context, epoch->planes[1], next_yang, indices);
            ggml_tensor * write_yin = indices == nullptr || next_yin == nullptr
                ? nullptr
                : ggml_set_rows(workspace.context, epoch->planes[2], next_yin, indices);
            ggml_tensor * write_delta = indices == nullptr || delta == nullptr
                ? nullptr
                : ggml_set_rows(workspace.context, epoch->planes[3], delta, indices);
            if (indices == nullptr || output_copy == nullptr || delta_copy == nullptr ||
                next_observation == nullptr || write_yang == nullptr || write_yin == nullptr ||
                write_delta == nullptr || (chunk_index == 0 && scale_copy == nullptr)) {
                return fail(CASSIFI_WEIGHT_BANK_SHAPE_ERROR, "GGML rejected device membrane exchange graph shapes");
            }
            std::vector<ggml_tensor *> roots{
                output_copy, delta_copy, next_observation, write_yang, write_yin, write_delta,
            };
            if (scale_copy != nullptr) roots.push_back(scale_copy);
            if (!workspace.build(roots, 96)) {
                return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to build device membrane exchange graph");
            }
            if (!workspace.allocate(epoch->backend)) {
                return resource_wait(device_context_bytes(workspace.context), "membrane exchange graph");
            }
            ggml_backend_tensor_set(indices, row_indices.data(), 0, chunk_width * sizeof(int32_t));
            if (!workspace.compute(epoch->backend, epoch->threads)) {
                return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "GGML backend membrane exchange graph failed");
            }
        }
    } catch (const std::exception &) {
        return fail(CASSIFI_WEIGHT_BANK_BACKEND_ERROR, "failed to allocate device membrane exchange state");
    }
    *out_value = std::move(output);
    *out_scale = std::move(scale_capture);
    *out_delta = std::move(delta_capture);
    return CASSIFI_WEIGHT_BANK_OK;
}
} // namespace


struct cassifi_weight_bank { std::shared_ptr<WeightBank> impl; };
struct cassifi_device_epoch {
    std::shared_ptr<DeviceEpochState> impl;
};

namespace {

std::mutex shared_banks_mutex;
std::unordered_map<std::string, std::weak_ptr<WeightBank>> shared_banks;

std::string shared_bank_key(const char * path, const char * backend, int32_t threads) {
    std::error_code error;
    auto normalized = std::filesystem::absolute(path, error);
    const std::string model_path = error ? std::string(path) : normalized.lexically_normal().string();
    const std::string selected_backend = std::string(backend) == "vk" ? "vulkan" : backend;
    return model_path + "\n" + selected_backend + "\n" + std::to_string(threads);
}

}


struct cassifi_device_tensor {
    std::shared_ptr<DeviceEpochState> epoch;
    std::shared_ptr<DeviceTensorValue> value;
};

namespace {

cassifi_device_tensor_t * make_device_tensor_handle(
    const std::shared_ptr<DeviceEpochState> & epoch,
    const std::shared_ptr<DeviceTensorValue> & value
) {
    auto * handle = new (std::nothrow) cassifi_device_tensor_t;
    if (handle == nullptr) return nullptr;
    handle->epoch = epoch;
    handle->value = value;
    return handle;
}

int get_device_input(
    const cassifi_device_epoch_t * epoch,
    const cassifi_device_tensor_t * tensor,
    std::shared_ptr<DeviceTensorValue> * out_value
) {
    if (epoch == nullptr || epoch->impl == nullptr || tensor == nullptr || out_value == nullptr) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
    if (epoch->impl != tensor->epoch || tensor->value == nullptr) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
    if (!epoch->impl->open || epoch->impl->owner == nullptr) {
        return CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    }
    *out_value = tensor->value;
    return CASSIFI_WEIGHT_BANK_OK;
}

int finish_device_output(
    const cassifi_device_epoch_t * epoch,
    const std::shared_ptr<DeviceTensorValue> & value,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    if (epoch == nullptr || epoch->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    if (value == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

template<typename Operation>
int with_device_input(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor, Operation operation
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = operation(epoch->impl, input_value, &value);
    return rc == CASSIFI_WEIGHT_BANK_OK ? finish_device_output(epoch, value, out_tensor) : rc;
}

template<typename Operation>
int with_two_device_inputs(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * first,
    const cassifi_device_tensor_t * second, cassifi_device_tensor_t ** out_tensor,
    Operation operation
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> first_value;
    std::shared_ptr<DeviceTensorValue> second_value;
    int handle_rc = get_device_input(epoch, first, &first_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    handle_rc = get_device_input(epoch, second, &second_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = operation(epoch->impl, first_value, second_value, &value);
    return rc == CASSIFI_WEIGHT_BANK_OK ? finish_device_output(epoch, value, out_tensor) : rc;
}

template<typename Operation>
int with_three_device_inputs(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * first,
    const cassifi_device_tensor_t * second, const cassifi_device_tensor_t * third,
    cassifi_device_tensor_t ** out_tensor, Operation operation
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> first_value;
    std::shared_ptr<DeviceTensorValue> second_value;
    std::shared_ptr<DeviceTensorValue> third_value;
    int handle_rc = get_device_input(epoch, first, &first_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    handle_rc = get_device_input(epoch, second, &second_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    handle_rc = get_device_input(epoch, third, &third_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = operation(epoch->impl, first_value, second_value, third_value, &value);
    return rc == CASSIFI_WEIGHT_BANK_OK ? finish_device_output(epoch, value, out_tensor) : rc;
}

} // namespace

extern "C" {

int cassifi_weight_bank_vulkan_memory(size_t * out_free_bytes, size_t * out_total_bytes) {
    if (out_free_bytes == nullptr || out_total_bytes == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_free_bytes = 0;
    *out_total_bytes = 0;
#ifdef CASSIFI_WEIGHT_BANK_HAS_VULKAN
    if (ggml_backend_vk_get_device_count() <= 0) return CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE;
    ggml_backend_t backend = ggml_backend_vk_init(0);
    if (backend == nullptr) return CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE;
    ggml_backend_dev_t device = ggml_backend_get_device(backend);
    if (device != nullptr) ggml_backend_dev_memory(device, out_free_bytes, out_total_bytes);
    ggml_backend_free(backend);
    return device == nullptr || *out_total_bytes == 0 ? CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE : CASSIFI_WEIGHT_BANK_OK;
#else
    return CASSIFI_WEIGHT_BANK_DEVICE_UNAVAILABLE;
#endif
}

int cassifi_weight_bank_load(const char * path, const char * backend, int32_t threads, cassifi_weight_bank_t ** out_bank) {
    if (out_bank == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_bank = nullptr;
    if (path == nullptr || backend == nullptr || threads <= 0) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
    std::shared_ptr<WeightBank> shared;
    try {
        const std::string key = shared_bank_key(path, backend, threads);
        std::lock_guard<std::mutex> lock(shared_banks_mutex);
        auto found = shared_banks.find(key);
        if (found != shared_banks.end()) shared = found->second.lock();
        if (shared == nullptr) {
            WeightBank * loaded = nullptr;
            const int rc = WeightBank::load(path, backend, threads, &loaded);
            if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
            shared.reset(loaded);
            shared_banks[key] = shared;
            for (auto it = shared_banks.begin(); it != shared_banks.end();) {
                if (it->second.expired()) it = shared_banks.erase(it);
                else ++it;
            }
        }
        auto * wrapper = new (std::nothrow) cassifi_weight_bank_t;
        if (wrapper == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        wrapper->impl = std::move(shared);
        *out_bank = wrapper;
        return CASSIFI_WEIGHT_BANK_OK;
    } catch (const std::bad_alloc &) {
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    } catch (const std::exception &) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
}

void cassifi_weight_bank_close(cassifi_weight_bank_t * bank) {
    delete bank;
}

const char * cassifi_weight_bank_last_error(const cassifi_weight_bank_t * bank) {
    return bank == nullptr || bank->impl == nullptr ? "weight bank is null" : bank->impl->last_error();
}

int cassifi_weight_bank_tensor_info(const cassifi_weight_bank_t * bank, const char * name, cassifi_weight_tensor_info_t * out_info) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->tensor_info(name, out_info);
}
int cassifi_weight_bank_read_vector(const cassifi_weight_bank_t * bank, const char * name, float * out, size_t capacity, size_t * out_count) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->read_vector(name, out, capacity, out_count);
}
int cassifi_weight_bank_read_tensor_f32(const cassifi_weight_bank_t * bank, const char * name, float * out, size_t capacity, size_t * out_count) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->read_tensor_f32(name, out, capacity, out_count);
}
int cassifi_weight_bank_read_embedding(const cassifi_weight_bank_t * bank, const char * name, uint64_t token, float * out, size_t capacity, size_t * out_count) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->read_embedding(name, token, out, capacity, out_count);
}
int cassifi_weight_bank_matvec(const cassifi_weight_bank_t * bank, const char * name, const float * input, size_t input_count, float * output, size_t output_capacity, size_t * output_count, int32_t expert) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->matvec(name, input, input_count, output, output_capacity, output_count, expert);
}
int cassifi_weight_bank_matvec_many(
    const cassifi_weight_bank_t * bank,
    const char * const * names,
    const int32_t * experts,
    size_t request_count,
    const float * input,
    size_t input_count,
    float * const * outputs,
    const size_t * output_capacities,
    size_t * output_counts
) {
    return bank == nullptr || bank->impl == nullptr
        ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT
        : bank->impl->matvec_many(
            names,
            experts,
            request_count,
            input,
            input_count,
            outputs,
            output_capacities,
            output_counts
        );
}
int cassifi_weight_bank_matvec_batch(
    const cassifi_weight_bank_t * bank,
    const char * name,
    const float * inputs,
    size_t batch_count,
    size_t input_width,
    float * outputs,
    size_t output_capacity,
    size_t * output_count,
    int32_t expert
) {
    return bank == nullptr || bank->impl == nullptr
        ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT
        : bank->impl->matvec_batch(
            name,
            inputs,
            batch_count,
            input_width,
            outputs,
            output_capacity,
            output_count,
            expert
        );
}
int cassifi_weight_bank_matvec_batch_experts(
    const cassifi_weight_bank_t * bank,
    const char * name,
    const float * inputs,
    size_t batch_count,
    size_t input_width,
    const int32_t * experts,
    float * outputs,
    size_t output_capacity,
    size_t * output_count
) {
    return bank == nullptr || bank->impl == nullptr
        ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT
        : bank->impl->matvec_batch_experts(
            name,
            inputs,
            batch_count,
            input_width,
            experts,
            outputs,
            output_capacity,
            output_count
        );
}
int cassifi_weight_bank_prefetch(cassifi_weight_bank_t * bank, const char * name, int32_t expert) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->prefetch(name, expert);
}
int cassifi_weight_bank_evict(cassifi_weight_bank_t * bank, const char * name, int32_t expert) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->evict(name, expert);
}
int cassifi_weight_bank_residency(const cassifi_weight_bank_t * bank, const char * name, int32_t expert, int32_t * resident, uint64_t * bytes, uint64_t * hits, uint64_t * misses) {
    return bank == nullptr || bank->impl == nullptr ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT : bank->impl->residency(name, expert, resident, bytes, hits, misses);
}

int cassifi_weight_bank_device_epoch_begin(
    cassifi_weight_bank_t * bank, const float * initial_planes, size_t plane_value_count,
    size_t mode_count, int32_t gain_ppm, cassifi_device_epoch_t ** out_epoch
) {
    if (out_epoch == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_epoch = nullptr;
    if (bank == nullptr || bank->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    std::shared_ptr<DeviceEpochState> state;
    const int rc = bank->impl->device_epoch_begin(
        initial_planes, plane_value_count, mode_count, gain_ppm, &state);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    auto * handle = new (std::nothrow) cassifi_device_epoch_t;
    if (handle == nullptr) {
        bank->impl->device_epoch_close(state);
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    }
    handle->impl = std::move(state);
    *out_epoch = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_epoch_snapshot(
    cassifi_device_epoch_t * epoch, float * planes, size_t plane_capacity, size_t * out_count
) {
    if (epoch == nullptr || epoch->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    WeightBank * owner = epoch->impl->owner;
    if (owner == nullptr) return CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    return owner->device_epoch_snapshot(epoch->impl, planes, plane_capacity, out_count);
}

int cassifi_weight_bank_device_epoch_finish(
    cassifi_device_epoch_t * epoch, float * final_planes, size_t plane_capacity, size_t * out_count
) {
    if (epoch == nullptr || epoch->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    WeightBank * owner = epoch->impl->owner;
    if (owner == nullptr) return CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    return owner->device_epoch_finish(epoch->impl, final_planes, plane_capacity, out_count);
}

void cassifi_weight_bank_device_epoch_close(cassifi_device_epoch_t * epoch) {
    if (epoch == nullptr) return;
    if (epoch->impl != nullptr) {
        WeightBank * owner = epoch->impl->owner;
        if (owner != nullptr) owner->device_epoch_close(epoch->impl);
        else epoch->impl->close();
    }
    delete epoch;
}

int cassifi_weight_bank_device_tensor_upload(
    cassifi_device_epoch_t * epoch, const float * values, size_t count, cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    if (epoch == nullptr || epoch->impl == nullptr || epoch->impl->owner == nullptr) {
        return epoch == nullptr || epoch->impl == nullptr
            ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT
            : CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    }
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_epoch_upload(epoch->impl, values, count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_tensor_view(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    size_t element_offset, size_t count, cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_tensor_view(
        epoch->impl, input_value, element_offset, count, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_tensor_count(
    const cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * tensor, size_t * out_count
) {
    std::shared_ptr<DeviceTensorValue> value;
    const int handle_rc = get_device_input(epoch, tensor, &value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    return epoch->impl->owner->device_tensor_count(epoch->impl, value, out_count);
}

int cassifi_weight_bank_device_tensor_download(
    const cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * tensor,
    float * out, size_t capacity, size_t * out_count
) {
    std::shared_ptr<DeviceTensorValue> value;
    const int handle_rc = get_device_input(epoch, tensor, &value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    return epoch->impl->owner->device_tensor_download(epoch->impl, value, out, capacity, out_count);
}

int cassifi_weight_bank_device_tensor_download_many(
    const cassifi_device_epoch_t * epoch,
    const cassifi_device_tensor_t * const * tensors, size_t tensor_count,
    float * out, size_t capacity, size_t * out_count,
    size_t * value_offsets, size_t * value_counts
) {
    if (epoch == nullptr || epoch->impl == nullptr || epoch->impl->owner == nullptr) {
        return epoch == nullptr || epoch->impl == nullptr
            ? CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT
            : CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    }
    if (tensor_count != 0 && tensors == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    try {
        std::vector<std::shared_ptr<DeviceTensorValue>> values;
        values.reserve(tensor_count);
        for (size_t i = 0; i < tensor_count; ++i) {
            std::shared_ptr<DeviceTensorValue> value;
            const int rc = get_device_input(epoch, tensors[i], &value);
            if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
            values.push_back(std::move(value));
        }
        return epoch->impl->owner->device_tensor_download_many(
            epoch->impl, values, out, capacity, out_count, value_offsets, value_counts);
    } catch (const std::exception &) {
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    }
}

void cassifi_weight_bank_device_tensor_release(cassifi_device_tensor_t * tensor) {
    delete tensor;
}
void cassifi_weight_bank_device_tensor_release_many(
    cassifi_device_tensor_t * const * tensors, size_t tensor_count
) {
    if (tensors == nullptr) return;
    for (size_t i = 0; i < tensor_count; ++i) delete tensors[i];
}

int cassifi_weight_bank_device_matvec(
    cassifi_device_epoch_t * epoch, const char * name, const cassifi_device_tensor_t * input,
    int32_t expert, cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_matvec(epoch->impl, name, input_value, expert, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_low_rank_affine(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    const char * method_id, const float * a, size_t input_width, size_t rank,
    const float * b, size_t output_width, const float * bias,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    if (epoch == nullptr || epoch->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    if (epoch->impl->owner == nullptr) return CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_low_rank_affine(
        epoch->impl, input_value, method_id, a, input_width, rank, b, output_width, bias, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    return finish_device_output(epoch, value, out_tensor);
}

int cassifi_weight_bank_device_matvec_many(
    cassifi_device_epoch_t * epoch,
    const char * const * names, const int32_t * experts, size_t request_count,
    const cassifi_device_tensor_t * input, cassifi_device_tensor_t ** out_tensors
) {
    if (epoch == nullptr || epoch->impl == nullptr || out_tensors == nullptr || request_count == 0) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
    for (size_t i = 0; i < request_count; ++i) out_tensors[i] = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::vector<std::shared_ptr<DeviceTensorValue>> values;
    const int rc = epoch->impl->owner->device_matvec_many(
        epoch->impl, names, experts, request_count, input_value, &values);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    for (size_t i = 0; i < request_count; ++i) {
        out_tensors[i] = make_device_tensor_handle(epoch->impl, values[i]);
        if (out_tensors[i] == nullptr) {
            for (size_t j = 0; j < i; ++j) {
                delete out_tensors[j];
                out_tensors[j] = nullptr;
            }
            return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
        }
    }
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_exchange(
    cassifi_device_epoch_t * epoch, const char * site, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_input_capture, cassifi_device_tensor_t ** out_tensor,
    cassifi_device_tensor_t ** out_scale, cassifi_device_tensor_t ** out_delta
) {
    if (out_input_capture == nullptr || out_tensor == nullptr || out_scale == nullptr || out_delta == nullptr) {
        return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    }
    *out_input_capture = nullptr;
    *out_tensor = nullptr;
    *out_scale = nullptr;
    *out_delta = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    std::shared_ptr<DeviceTensorValue> scale;
    std::shared_ptr<DeviceTensorValue> delta;
    const int rc = epoch->impl->owner->device_exchange(
        epoch->impl, site, input_value, &value, &scale, &delta);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * input_handle = make_device_tensor_handle(epoch->impl, input_value);
    cassifi_device_tensor_t * output_handle = make_device_tensor_handle(epoch->impl, value);
    cassifi_device_tensor_t * scale_handle = make_device_tensor_handle(epoch->impl, scale);
    cassifi_device_tensor_t * delta_handle = make_device_tensor_handle(epoch->impl, delta);
    if (input_handle == nullptr || output_handle == nullptr || scale_handle == nullptr || delta_handle == nullptr) {
        delete input_handle;
        delete output_handle;
        delete scale_handle;
        delete delta_handle;
        return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    }
    *out_input_capture = input_handle;
    *out_tensor = output_handle;
    *out_scale = scale_handle;
    *out_delta = delta_handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_silu(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_unary(epoch->impl, input_value, 0, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_sigmoid(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_unary(epoch->impl, input_value, 1, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_scale(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input, float scale,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> input_value;
    const int handle_rc = get_device_input(epoch, input, &input_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_scale(epoch->impl, input_value, scale, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_mul(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> left_value;
    std::shared_ptr<DeviceTensorValue> right_value;
    int handle_rc = get_device_input(epoch, left, &left_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    handle_rc = get_device_input(epoch, right, &right_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_binary(
        epoch->impl, left_value, right_value, true, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_add(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    std::shared_ptr<DeviceTensorValue> left_value;
    std::shared_ptr<DeviceTensorValue> right_value;
    int handle_rc = get_device_input(epoch, left, &left_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    handle_rc = get_device_input(epoch, right, &right_value);
    if (handle_rc != CASSIFI_WEIGHT_BANK_OK) return handle_rc;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_binary(
        epoch->impl, left_value, right_value, false, &value);
    if (rc != CASSIFI_WEIGHT_BANK_OK) return rc;
    cassifi_device_tensor_t * handle = make_device_tensor_handle(epoch->impl, value);
    if (handle == nullptr) return CASSIFI_WEIGHT_BANK_BACKEND_ERROR;
    *out_tensor = handle;
    return CASSIFI_WEIGHT_BANK_OK;
}

int cassifi_weight_bank_device_embedding(
    cassifi_device_epoch_t * epoch, const char * name, uint64_t token,
    cassifi_device_tensor_t ** out_tensor
) {
    if (out_tensor == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    *out_tensor = nullptr;
    if (epoch == nullptr || epoch->impl == nullptr) return CASSIFI_WEIGHT_BANK_INVALID_ARGUMENT;
    if (epoch->impl->owner == nullptr) return CASSIFI_WEIGHT_BANK_DEVICE_EPOCH_CLOSED;
    std::shared_ptr<DeviceTensorValue> value;
    const int rc = epoch->impl->owner->device_embedding(epoch->impl, name, token, &value);
    return rc == CASSIFI_WEIGHT_BANK_OK ? finish_device_output(epoch, value, out_tensor) : rc;
}

int cassifi_weight_bank_device_concat(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * left,
    const cassifi_device_tensor_t * right, cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, left, right, out_tensor,
        [](const std::shared_ptr<DeviceEpochState> & current,
           const std::shared_ptr<DeviceTensorValue> & a,
           const std::shared_ptr<DeviceTensorValue> & b,
           std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_concat(current, a, b, result);
        });
}

int cassifi_weight_bank_device_norm_rows(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    size_t row_width, float epsilon, int32_t sum_squares, const char * weight_name,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [row_width, epsilon, sum_squares, weight_name](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_norm_rows(
                current, value, row_width, epsilon, sum_squares != 0, weight_name, result
            );
        });
}

int cassifi_weight_bank_device_mul_rows(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    const cassifi_device_tensor_t * row_scales, size_t row_width,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, input, row_scales, out_tensor,
        [row_width](const std::shared_ptr<DeviceEpochState> & current,
                    const std::shared_ptr<DeviceTensorValue> & values,
                    const std::shared_ptr<DeviceTensorValue> & scales,
                    std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_mul_rows(current, values, scales, row_width, result);
        });
}

int cassifi_weight_bank_device_exp_clipped(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    float lower, float upper, cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [lower, upper](const std::shared_ptr<DeviceEpochState> & current,
                       const std::shared_ptr<DeviceTensorValue> & value,
                       std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_exp_clipped(current, value, lower, upper, result);
        });
}

int cassifi_weight_bank_device_softplus(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [](const std::shared_ptr<DeviceEpochState> & current,
           const std::shared_ptr<DeviceTensorValue> & value,
           std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_softplus(current, value, result);
        });
}

int cassifi_weight_bank_device_softmax(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [](const std::shared_ptr<DeviceEpochState> & current,
           const std::shared_ptr<DeviceTensorValue> & value,
           std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_probability(current, value, false, result);
        });
}

int cassifi_weight_bank_device_positive_normalize(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [](const std::shared_ptr<DeviceEpochState> & current,
           const std::shared_ptr<DeviceTensorValue> & value,
           std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_probability(current, value, true, result);
        });
}

int cassifi_weight_bank_device_recurrent_conv(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * history,
    const char * kernel_name, size_t channels, cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, history, out_tensor,
        [kernel_name, channels](const std::shared_ptr<DeviceEpochState> & current,
                                const std::shared_ptr<DeviceTensorValue> & value,
                                std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_recurrent_conv(current, value, kernel_name, channels, result);
        });
}

int cassifi_weight_bank_device_recurrent_predict(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * keys, size_t value_heads, size_t key_heads,
    size_t value_dim, size_t key_dim, cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, state, keys, out_tensor,
        [value_heads, key_heads, value_dim, key_dim](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & state_value,
            const std::shared_ptr<DeviceTensorValue> & keys_value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_recurrent_state_op(
                current, state_value, keys_value, {}, 0,
                value_heads, key_heads, value_dim, key_dim, result
            );
        });
}

int cassifi_weight_bank_device_recurrent_update(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * keys, const cassifi_device_tensor_t * deltas,
    size_t value_heads, size_t key_heads, size_t value_dim, size_t key_dim,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_three_device_inputs(epoch, state, keys, deltas, out_tensor,
        [value_heads, key_heads, value_dim, key_dim](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & state_value,
            const std::shared_ptr<DeviceTensorValue> & keys_value,
            const std::shared_ptr<DeviceTensorValue> & delta_value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_recurrent_state_op(
                current, state_value, keys_value, delta_value, 1,
                value_heads, key_heads, value_dim, key_dim, result
            );
        });
}

int cassifi_weight_bank_device_recurrent_readout(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * state,
    const cassifi_device_tensor_t * queries, size_t value_heads, size_t key_heads,
    size_t value_dim, size_t key_dim, cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, state, queries, out_tensor,
        [value_heads, key_heads, value_dim, key_dim](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & state_value,
            const std::shared_ptr<DeviceTensorValue> & query_value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_recurrent_state_op(
                current, state_value, query_value, {}, 2,
                value_heads, key_heads, value_dim, key_dim, result
            );
        });
}

int cassifi_weight_bank_device_rope(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * input,
    int64_t position, const int32_t * sections, size_t section_count, double base,
    cassifi_device_tensor_t ** out_tensor
) {
    return with_device_input(epoch, input, out_tensor,
        [position, sections, section_count, base](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_rope(
                current, value, position, sections, section_count, base, result
            );
        });
}

int cassifi_weight_bank_device_attention_scores(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * query,
    const cassifi_device_tensor_t * key_cache, size_t kv_head, size_t kv_heads,
    size_t head_dim, float scale, cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, query, key_cache, out_tensor,
        [kv_head, kv_heads, head_dim, scale](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & query_value,
            const std::shared_ptr<DeviceTensorValue> & keys_value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_attention_scores(
                current, query_value, keys_value, kv_head, kv_heads, head_dim, scale, result
            );
        });
}

int cassifi_weight_bank_device_attention_context(
    cassifi_device_epoch_t * epoch, const cassifi_device_tensor_t * probabilities,
    const cassifi_device_tensor_t * value_cache, size_t kv_head, size_t kv_heads,
    size_t value_dim, cassifi_device_tensor_t ** out_tensor
) {
    return with_two_device_inputs(epoch, probabilities, value_cache, out_tensor,
        [kv_head, kv_heads, value_dim](
            const std::shared_ptr<DeviceEpochState> & current,
            const std::shared_ptr<DeviceTensorValue> & probabilities_value,
            const std::shared_ptr<DeviceTensorValue> & values_value,
            std::shared_ptr<DeviceTensorValue> * result) {
            return current->owner->device_attention_context(
                current, probabilities_value, values_value,
                kv_head, kv_heads, value_dim, result
            );
        });
}
}
