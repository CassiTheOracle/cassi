#include "ggml.h"
#include "ggml-backend.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

struct Receipt {
    std::vector<float> output;
    const char * backend_name;
};

static bool run_backend(ggml_backend_t backend, Receipt & receipt, int mode_count, int batch_size, int token_count, int horizon, float & max_abs_value) {
    const size_t graph_nodes = 64;
    ggml_init_params params = {
        /* .mem_size   = */ ggml_tensor_overhead() * 16 + ggml_graph_overhead_custom(graph_nodes, false),
        /* .mem_buffer = */ nullptr,
        /* .no_alloc   = */ true,
    };
    ggml_context * ctx = ggml_init(params);
    if (ctx == nullptr) {
        std::fprintf(stderr, "failed to initialize GGML context\n");
        return false;
    }

    ggml_tensor * sense = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, 2 * mode_count, token_count, 1, 1);
    ggml_tensor * state = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, 8 * mode_count, batch_size, 1, 1);
    ggml_tensor * mode_params = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, mode_count, 1, 1, 1);
    ggml_tensor * seq_ids = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, token_count);
    ggml_tensor * output = ggml_cassi_field_step(
        ctx, sense, state, mode_params, seq_ids,
        0.90f, 1.618033988749895f, 0.005f, 20.0f, 1.0f, 4);
    if (sense == nullptr || state == nullptr || mode_params == nullptr || seq_ids == nullptr || output == nullptr) {
        std::fprintf(stderr, "failed to construct field-step graph\n");
        ggml_free(ctx);
        return false;
    }

    ggml_cgraph * graph = ggml_new_graph_custom(ctx, graph_nodes, false);
    ggml_build_forward_expand(graph, output);

    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (buffer == nullptr) {
        std::fprintf(stderr, "failed to allocate backend tensors for %s\n", ggml_backend_name(backend));
        ggml_free(ctx);
        return false;
    }

    std::vector<float> sense_data(2 * mode_count * token_count);
    std::vector<float> state_data(8 * mode_count * batch_size);
    std::vector<float> mode_data(mode_count);
    std::vector<int32_t> seq_data(token_count);
    for (size_t i = 0; i < sense_data.size(); ++i) {
        sense_data[i] = (float(int(i % 17) - 8)) * 0.01f;
    }
    for (size_t i = 0; i < state_data.size(); ++i) {
        state_data[i] = (float(int(i % 11) - 5)) * 0.001f;
    }
    for (int i = 0; i < mode_count; ++i) {
        mode_data[i] = -0.01f * float(i + 1);
    }
    for (int i = 0; i < token_count; ++i) {
        seq_data[i] = i % batch_size;
    }
    ggml_backend_tensor_set(sense, sense_data.data(), 0, sense_data.size() * sizeof(float));
    ggml_backend_tensor_set(state, state_data.data(), 0, state_data.size() * sizeof(float));
    ggml_backend_tensor_set(mode_params, mode_data.data(), 0, mode_data.size() * sizeof(float));
    ggml_backend_tensor_set(seq_ids, seq_data.data(), 0, seq_data.size() * sizeof(int32_t));

    receipt.output.resize(ggml_nelements(output));
    receipt.backend_name = ggml_backend_name(backend);
    bool finite = true;
    max_abs_value = 0.0f;
    const size_t flux_count = size_t(2 * mode_count * token_count);
    const size_t state_bytes = size_t(8 * mode_count * batch_size) * sizeof(float);
    for (int iteration = 0; iteration < horizon; ++iteration) {
        ggml_status status = ggml_backend_graph_compute(backend, graph);
        if (status != GGML_STATUS_SUCCESS) {
            std::fprintf(stderr, "field-step compute failed for %s: %s\n", receipt.backend_name, ggml_status_to_string(status));
            ggml_backend_buffer_free(buffer);
            ggml_free(ctx);
            return false;
        }
        ggml_backend_tensor_get(output, receipt.output.data(), 0, receipt.output.size() * sizeof(float));
        for (float value : receipt.output) {
            finite = finite && std::isfinite(value);
            max_abs_value = std::max(max_abs_value, std::abs(value));
        }
        if (!finite) {
            std::fprintf(stderr, "field-step output is non-finite for %s at iteration %d\n", receipt.backend_name, iteration);
            break;
        }
        ggml_backend_tensor_set(state, receipt.output.data() + flux_count, 0, state_bytes);
    }
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    return finite;
}

static bool run_resonance_backend(
    ggml_backend_t backend, Receipt & receipt, int mode_count, int batch_size, int candidate_count, float & max_abs_value) {
    ggml_init_params params = {
        /* .mem_size   = */ ggml_tensor_overhead() * 12 + ggml_graph_overhead_custom(32, false),
        /* .mem_buffer = */ nullptr,
        /* .no_alloc   = */ true,
    };
    ggml_context * ctx = ggml_init(params);
    if (ctx == nullptr) {
        return false;
    }
    ggml_tensor * field = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, 8 * mode_count, batch_size, 1, 1);
    ggml_tensor * probes = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, 2 * mode_count, candidate_count, 1, 1);
    ggml_tensor * output = ggml_cassi_field_resonance(ctx, field, probes, 1.618033988749895f, 0.05f);
    if (field == nullptr || probes == nullptr || output == nullptr) {
        ggml_free(ctx);
        return false;
    }
    ggml_cgraph * graph = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(graph, output);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (buffer == nullptr) {
        ggml_free(ctx);
        return false;
    }

    std::vector<float> field_data(8 * mode_count * batch_size);
    std::vector<float> probe_data(2 * mode_count * candidate_count);
    for (size_t i = 0; i < field_data.size(); ++i) {
        field_data[i] = float(int(i % 13) - 6) * 0.002f;
    }
    for (int candidate = 0; candidate < candidate_count; ++candidate) {
        for (int mode = 0; mode < mode_count; ++mode) {
            const float phase = 0.017f * float((candidate + 1) * (mode + 3));
            probe_data[2 * mode + 2 * mode_count * candidate] = std::cos(phase);
            probe_data[2 * mode + 1 + 2 * mode_count * candidate] = std::sin(phase);
        }
    }
    ggml_backend_tensor_set(field, field_data.data(), 0, field_data.size() * sizeof(float));
    ggml_backend_tensor_set(probes, probe_data.data(), 0, probe_data.size() * sizeof(float));

    receipt.output.resize(ggml_nelements(output));
    receipt.backend_name = ggml_backend_name(backend);
    ggml_status status = ggml_backend_graph_compute(backend, graph);
    if (status != GGML_STATUS_SUCCESS) {
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        return false;
    }
    ggml_backend_tensor_get(output, receipt.output.data(), 0, receipt.output.size() * sizeof(float));
    max_abs_value = 0.0f;
    bool finite = true;
    for (float value : receipt.output) {
        finite = finite && std::isfinite(value);
        max_abs_value = std::max(max_abs_value, std::abs(value));
    }
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    return finite;
}

int main() {
    constexpr int mode_count = 32;
    constexpr int batch_size = 2;
    constexpr int token_count = 4;

    ggml_backend_load_all();
    ggml_backend_t cpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
    if (cpu == nullptr) {
        std::fprintf(stderr, "CPU backend is unavailable\n");
        return 1;
    }

    Receipt cpu_receipt;
    float cpu_max_abs = 0.0f;
    if (!run_backend(cpu, cpu_receipt, mode_count, batch_size, token_count, 1, cpu_max_abs)) {
        ggml_backend_free(cpu);
        return 1;
    }

    ggml_backend_t gpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_GPU, nullptr);
    if (gpu == nullptr) {
        std::fprintf(stderr, "GPU backend is unavailable; Vulkan parity was not exercised\n");
        ggml_backend_free(cpu);
        return 2;
    }

    Receipt gpu_receipt;
    float gpu_max_abs = 0.0f;
    if (!run_backend(gpu, gpu_receipt, mode_count, batch_size, token_count, 1, gpu_max_abs)) {
        ggml_backend_free(gpu);
        ggml_backend_free(cpu);
        return 1;
    }

    if (cpu_receipt.output.size() != gpu_receipt.output.size()) {
        std::fprintf(stderr, "CPU/GPU output sizes differ\n");
        ggml_backend_free(gpu);
        ggml_backend_free(cpu);
        return 1;
    }

    float max_abs_diff = 0.0f;
    for (size_t i = 0; i < cpu_receipt.output.size(); ++i) {
        max_abs_diff = std::max(max_abs_diff, std::abs(cpu_receipt.output[i] - gpu_receipt.output[i]));
    }

    Receipt cpu_long_receipt;
    Receipt gpu_long_receipt;
    float cpu_long_max_abs = 0.0f;
    float gpu_long_max_abs = 0.0f;
    const int long_horizon = 10000;
    const bool cpu_long_ok = run_backend(cpu, cpu_long_receipt, mode_count, batch_size, token_count, long_horizon, cpu_long_max_abs);
    const bool gpu_long_ok = run_backend(gpu, gpu_long_receipt, mode_count, batch_size, token_count, long_horizon, gpu_long_max_abs);

    Receipt cpu_resonance;
    Receipt gpu_resonance;
    float cpu_resonance_max_abs = 0.0f;
    float gpu_resonance_max_abs = 0.0f;
    const bool cpu_resonance_ok = run_resonance_backend(cpu, cpu_resonance, mode_count, batch_size, 7, cpu_resonance_max_abs);
    const bool gpu_resonance_ok = run_resonance_backend(gpu, gpu_resonance, mode_count, batch_size, 7, gpu_resonance_max_abs);
    float resonance_max_abs_diff = 0.0f;
    if (cpu_resonance.output.size() != gpu_resonance.output.size()) {
        resonance_max_abs_diff = INFINITY;
    } else {
        for (size_t i = 0; i < cpu_resonance.output.size(); ++i) {
            resonance_max_abs_diff = std::max(
                resonance_max_abs_diff,
                std::abs(cpu_resonance.output[i] - gpu_resonance.output[i]));
        }
    }

    std::printf(
        "{\"cpu_backend\":\"%s\",\"gpu_backend\":\"%s\",\"elements\":%zu,"
        "\"max_abs_diff\":%.9g,\"short_horizon\":1,\"long_horizon\":%d,"
        "\"cpu_long_max_abs\":%.9g,\"gpu_long_max_abs\":%.9g,"
        "\"resonance_elements\":%zu,\"resonance_max_abs_diff\":%.9g}\n",
        cpu_receipt.backend_name, gpu_receipt.backend_name, cpu_receipt.output.size(),
        max_abs_diff, long_horizon, cpu_long_max_abs, gpu_long_max_abs,
        cpu_resonance.output.size(), resonance_max_abs_diff);

    ggml_backend_free(gpu);
    ggml_backend_free(cpu);
    if (!cpu_long_ok || !gpu_long_ok || !cpu_resonance_ok || !gpu_resonance_ok
        || cpu_long_max_abs > 64.0f || gpu_long_max_abs > 64.0f) {
        return 4;
    }
    if (max_abs_diff > 1.0e-5f || resonance_max_abs_diff > 1.0e-5f) {
        return 3;
    }
    return 0;

}
