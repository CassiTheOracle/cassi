#include "ggml.h"
#include "ggml-backend.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

struct Receipt {
    std::vector<float> output;
    std::vector<float> state;
    const char * backend_name = "unknown";
};

static constexpr float PHI = 1.618033988749895f;
static constexpr int M = 4;
static constexpr int S = 4;
static constexpr int B = 2;
static constexpr int T = 4;
static constexpr int STATE_STRIDE = 9 * M * S;
static constexpr int DIAG_STRIDE = 10 * S;

static bool run_backend(ggml_backend_t backend, Receipt & receipt, int horizon, bool zero_input = false, bool invalid_ids = false, float epsilon_tau = 0.1f) {
    ggml_init_params ip = {
        /* .mem_size   = */ ggml_tensor_overhead() * 16 + ggml_graph_overhead_custom(64, false),
        /* .mem_buffer = */ nullptr,
        /* .no_alloc   = */ true,
    };
    ggml_context * ctx = ggml_init(ip);
    if (!ctx) return false;
    ggml_tensor * sense = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, 2 * M, T, 1, 1);
    ggml_tensor * state = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, STATE_STRIDE, B, 1, 1);
    ggml_tensor * modes = ggml_new_tensor_4d(ctx, GGML_TYPE_F32, M, 1, 1, 1);
    ggml_tensor * ids = ggml_new_tensor_1d(ctx, GGML_TYPE_I32, T);
    ggml_tensor * out = ggml_cassi_qi_field_step(ctx, sense, state, modes, ids, S,
        PHI, 0.005f, 1.0f, 0.01f, 4.0f, epsilon_tau, 4.2360679775f, 1.0e-6f, 1.0e-4f, 1);
    if (!sense || !state || !modes || !ids || !out) { ggml_free(ctx); return false; }
    ggml_cgraph * graph = ggml_new_graph_custom(ctx, 64, false);
    ggml_build_forward_expand(graph, out);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (!buffer) { ggml_free(ctx); return false; }

    std::vector<float> sense_data(2 * M * T, 0.0f);
    std::vector<float> state_data(STATE_STRIDE * B, 0.0f);
    std::vector<float> mode_data(M, 0.0f);
    std::vector<int32_t> id_data = { 0, 1, 0, 1 };
    if (!zero_input) {
        for (size_t i = 0; i < sense_data.size(); ++i) sense_data[i] = 0.01f * float(int(i % 13) - 6);
    }
    if (invalid_ids) id_data[0] = B + 1;
    ggml_backend_tensor_set(sense, sense_data.data(), 0, sense_data.size() * sizeof(float));
    ggml_backend_tensor_set(state, state_data.data(), 0, state_data.size() * sizeof(float));
    ggml_backend_tensor_set(modes, mode_data.data(), 0, mode_data.size() * sizeof(float));
    ggml_backend_tensor_set(ids, id_data.data(), 0, id_data.size() * sizeof(int32_t));

    receipt.output.resize(ggml_nelements(out));
    receipt.backend_name = ggml_backend_name(backend);
    const size_t flux_count = 2 * M * T;
    const size_t state_count = STATE_STRIDE * B;
    bool finite = true;
    for (int event = 0; event < horizon; ++event) {
        if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS) {
            finite = false;
            break;
        }
        ggml_backend_tensor_get(out, receipt.output.data(), 0, receipt.output.size() * sizeof(float));
        for (float v : receipt.output) finite = finite && std::isfinite(v);
        if (!finite) break;
        ggml_backend_tensor_set(state, receipt.output.data() + flux_count, 0, state_count * sizeof(float));
    }
    receipt.state.assign(receipt.output.begin() + flux_count,
                         receipt.output.begin() + flux_count + state_count);
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    return finite;
}

static bool check_ranges(const Receipt & receipt, float & max_abs) {
    const size_t flux_count = 2 * M * T;
    const size_t state_count = STATE_STRIDE * B;
    max_abs = 0.0f;
    for (float v : receipt.output) max_abs = std::max(max_abs, std::abs(v));
    if (max_abs > 64.0f) return false;
    for (int b = 0; b < B; ++b) {
        const size_t base = flux_count + state_count + size_t(b) * DIAG_STRIDE;
        for (int s = 0; s < S; ++s) {
            const float q = receipt.output[base + 10 * s + 1];
            const float chi = receipt.output[base + 10 * s + 2];
            const float rg = receipt.output[base + 10 * s + 5];
            const float cc = receipt.output[base + 10 * s + 6];
            const float wg = receipt.output[base + 10 * s + 7];
            const float cg = receipt.output[base + 10 * s + 8];
            const float available = receipt.output[base + 10 * s + 9];
            if (q < 0.0f || q > 1.0f || chi < 0.0f || chi > 1.0f || rg < 0.0f || rg > 1.0f ||
                cc < 0.0f || cc > 1.0f || wg < 0.0f || wg > 1.0f || cg < 0.0f || cg > 1.0f ||
                available < 0.0f || available > 1.0f) return false;
        }
    }
    for (int b = 0; b < B; ++b) {
        for (int s = 0; s < S; ++s) {
            for (int mode = 0; mode < M; ++mode) {
                const size_t epsilon_offset = size_t(b) * STATE_STRIDE +
                    size_t(s * M + mode) * 9 + 8;
                if (receipt.state[epsilon_offset] < 0.0f) return false;
            }
        }
    }
    return true;
}

static bool check_zero_availability(ggml_backend_t backend) {
    Receipt receipt;
    if (!run_backend(backend, receipt, 1, true)) return false;
    const size_t flux_count = 2 * M * T;
    const size_t state_count = STATE_STRIDE * B;
    for (size_t i = 0; i < flux_count; ++i) if (receipt.output[i] != 0.0f) return false;
    for (int b = 0; b < B; ++b) for (int s = 0; s < S; ++s) {
        const size_t off = flux_count + state_count + size_t(b) * DIAG_STRIDE + 10 * s;
        if (receipt.output[off + 5] != 0.0f || receipt.output[off + 9] != 0.0f) return false;
    }
    return true;
}
static bool check_epsilon_iir(ggml_backend_t backend) {
    Receipt receipt;
    if (!run_backend(backend, receipt, 1, false, false, 1.0f)) return false;
    for (int b = 0; b < B; ++b) {
        for (int mode = 0; mode < M; ++mode) {
            const size_t base = size_t(b) * STATE_STRIDE + size_t(mode) * 9;
            const float e_y = receipt.state[base + 0] * receipt.state[base + 0] +
                receipt.state[base + 1] * receipt.state[base + 1];
            const float e_i = receipt.state[base + 2] * receipt.state[base + 2] +
                receipt.state[base + 3] * receipt.state[base + 3];
            const float epsilon = e_y - PHI * e_i;
            const float expected = std::min(epsilon * epsilon, 64.0f);
            if (std::abs(receipt.state[base + 8] - expected) > 1.0e-5f) return false;
        }
    }
    return true;
}
static bool check_invalid_ids(ggml_backend_t backend) {
    Receipt receipt;
    if (!run_backend(backend, receipt, 1, false, true)) return false;
    for (int mode = 0; mode < M; ++mode) {
        if (receipt.output[2 * mode + 0] != 0.0f || receipt.output[2 * mode + 1] != 0.0f) return false;
    }
    return true;
}
static float max_abs_diff(
        const Receipt & lhs,
        const Receipt & rhs,
        size_t begin,
        size_t end,
        size_t * max_index = nullptr) {
    float result = 0.0f;
    size_t index = begin;
    for (size_t i = begin; i < end; ++i) {
        const float diff = std::abs(lhs.output[i] - rhs.output[i]);
        if (diff > result) {
            result = diff;
            index = i;
        }
    }
    if (max_index != nullptr) {
        *max_index = index;
    }
    return result;
}


int main() {
    ggml_backend_load_all();
    ggml_backend_t cpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_CPU, nullptr);
    if (!cpu) return 1;
    const float q_one = 1.0f / (1.0f + 1.0f / (PHI * PHI));
    const float rho_anchor = PHI;
    const float q_anchor = rho_anchor * rho_anchor /
        (rho_anchor * rho_anchor + 1.0f / (PHI * PHI));
    if (std::abs(q_one - 0.72360679775f) > 1.0e-5f ||
        std::abs(q_anchor - 0.87267879775f) > 1.0e-5f) return 1;
    Receipt cpu_receipt;
    if (!check_zero_availability(cpu)) { ggml_backend_free(cpu); return 3; }
    if (!check_invalid_ids(cpu)) { ggml_backend_free(cpu); return 4; }
    if (!check_epsilon_iir(cpu)) { ggml_backend_free(cpu); return 5; }
    if (!run_backend(cpu, cpu_receipt, 10000)) { ggml_backend_free(cpu); return 3; }
    if (cpu_receipt.output.size() != size_t(2 * M * T + STATE_STRIDE * B + DIAG_STRIDE * B)) {
        ggml_backend_free(cpu);
        return 4;
    }
    float cpu_max = 0.0f;
    if (!check_ranges(cpu_receipt, cpu_max)) { ggml_backend_free(cpu); return 4; }
    bool distinct_scales = false;
    for (int s = 1; s < S; ++s) {
        const size_t a = size_t(s - 1) * M * 9;
        const size_t b = size_t(s) * M * 9;
        distinct_scales = distinct_scales || std::memcmp(cpu_receipt.state.data() + a, cpu_receipt.state.data() + b, M * 9 * sizeof(float)) != 0;
    }
    if (!distinct_scales) { ggml_backend_free(cpu); return 5; }

    ggml_backend_t gpu = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_GPU, nullptr);
    if (!gpu) {
        std::fprintf(stderr, "GPU/Vulkan backend unavailable; CPU checks passed\n");
        ggml_backend_free(cpu);
        return 0;
    }
    Receipt gpu_receipt;
    if (!run_backend(gpu, gpu_receipt, 10000)) { ggml_backend_free(gpu); ggml_backend_free(cpu); return 6; }
    float gpu_max = 0.0f;
    if (!check_ranges(gpu_receipt, gpu_max)) { ggml_backend_free(gpu); ggml_backend_free(cpu); return 7; }
    if (cpu_receipt.output.size() != gpu_receipt.output.size()) { ggml_backend_free(gpu); ggml_backend_free(cpu); return 8; }

    Receipt cpu_one;
    Receipt gpu_one;
    if (!run_backend(cpu, cpu_one, 1) || !run_backend(gpu, gpu_one, 1)) {
        ggml_backend_free(gpu);
        ggml_backend_free(cpu);
        return 9;
    }
    const size_t flux_end = 2 * M * T;
    const size_t state_end = flux_end + STATE_STRIDE * B;
    const size_t output_end = state_end + DIAG_STRIDE * B;
    const float one_event_diff = max_abs_diff(cpu_one, gpu_one, 0, output_end);
    const float flux_diff = max_abs_diff(cpu_receipt, gpu_receipt, 0, flux_end);
    const float state_diff = max_abs_diff(cpu_receipt, gpu_receipt, flux_end, state_end);
    size_t max_index = 0;
    const float diag_diff = max_abs_diff(cpu_receipt, gpu_receipt, state_end, output_end, &max_index);
    const float max_diff = std::max(flux_diff, std::max(state_diff, diag_diff));
    std::printf(
        "{\"cpu_backend\":\"%s\",\"gpu_backend\":\"%s\",\"elements\":%zu,"
        "\"one_event_max_abs_diff\":%.9g,\"flux_max_abs_diff\":%.9g,"
        "\"state_max_abs_diff\":%.9g,\"diagnostic_max_abs_diff\":%.9g,"
        "\"max_abs_diff\":%.9g,\"max_index\":%zu,\"events\":10000}\n",
        cpu_receipt.backend_name, gpu_receipt.backend_name, cpu_receipt.output.size(),
        one_event_diff, flux_diff, state_diff, diag_diff, max_diff, max_index);
    ggml_backend_free(gpu);
    ggml_backend_free(cpu);
    return one_event_diff <= 1.0e-4f && max_diff <= 5.0e-3f ? 0 : 10;
}
