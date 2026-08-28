"""Fused HIP/CUDA operations for QiField.

JIT-compiled extension with kernels for the expensive parts of field_step.
All kernels have PyTorch fallbacks for when the extension can't compile.
"""

from typing import Tuple

import torch
from torch.utils.cpp_extension import load_inline
import os
import sys
import torch.nn.functional as F

# GPU kernel source (compiled by hipcc/nvcc; PyTorch hipify maps cuda names to HIP)
CUDA_SOURCE = r"""
#include <cuda_runtime.h>
using stream_t = cudaStream_t;
#include <cmath>

#define PHI_INV 0.618033988749895f

// Fused advection kernel
__global__ void fused_advection_kernel(
    const float* __restrict__ psi,
    const float* __restrict__ p,
    float* __restrict__ psi_out,
    float* __restrict__ v_Q_out,
    int B, int N, int d
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = B * N;
    if (idx >= total) return;

    int b = idx / N;
    int n = idx % N;

    int left = (n - 1 + N) % N;
    int right = (n + 1) % N;

    float p_left = p[b * N + left];
    float p_right = p[b * N + right];
    float grad_p = (p_right - p_left) * 0.5f;
    float v_Q = -PHI_INV * grad_p;
    v_Q = fminf(fmaxf(v_Q, -1.0f), 1.0f);
    v_Q_out[b * N + n] = v_Q;

    int base = b * N * d;
    for (int d_idx = 0; d_idx < d; d_idx++) {
        float psi_c = psi[base + n * d + d_idx];
        float psi_l = psi[base + left * d + d_idx];
        float psi_r = psi[base + right * d + d_idx];

        float backward = psi_c - psi_l;
        float forward = psi_r - psi_c;
        float upwind = (v_Q > 0.0f) ? backward : forward;

        float result = psi_c + v_Q * upwind;
        psi_out[base + n * d + d_idx] = result;
    }
}

// Fused IIR update kernel
__global__ void fused_iir_update_kernel(
    const float* __restrict__ psi,
    float* __restrict__ h1,
    float* __restrict__ h2,
    const float* __restrict__ theta,
    const int* __restrict__ chakra_offsets,
    int B, int N, int d, int C, float rho
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total = B * N * d;
    if (idx >= total) return;

    int b = idx / (N * d);
    int rem = idx % (N * d);
    int n = rem / d;
    int d_idx = rem % d;

    int c = 0;
    for (int i = 0; i < C; i++) {
        if (d_idx >= chakra_offsets[i] && d_idx < chakra_offsets[i + 1]) {
            c = i;
            break;
        }
    }

    float a1 = 2.0f * rho * cosf(theta[c]);
    float a2 = -(rho * rho);
    float b0 = 0.5f;

    int psi_idx = b * N * d + n * d + d_idx;
    float psi_val = psi[psi_idx];
    int h_idx = b * N * d + n * d + d_idx;

    float h1_old = h1[h_idx];
    float h_new = b0 * psi_val + a1 * h1_old + a2 * h2[h_idx];

    h2[h_idx] = h1_old;
    h1[h_idx] = h_new;
}
extern "C" void launch_fused_advection(
    const float* psi, const float* p, float* psi_out, float* v_Q_out,
    int B, int N, int d, cudaStream_t stream
) {
    int threads = 256;
    int blocks = (B * N + threads - 1) / threads;
    fused_advection_kernel<<<blocks, threads, 0, stream>>>(psi, p, psi_out, v_Q_out, B, N, d);
}
extern "C" void launch_fused_iir_update(
    const float* psi, float* h1, float* h2,
    const float* theta, const int* chakra_offsets,
    int B, int N, int d, int C, float rho, cudaStream_t stream
) {
    int threads = 256;
    int blocks = (B * N * d + threads - 1) / threads;
    fused_iir_update_kernel<<<blocks, threads, 0, stream>>>(
        psi, h1, h2, theta, chakra_offsets, B, N, d, C, rho
    );
}
"""

# C++ host code (compiled by gcc; PyTorch hipify maps cuda names to HIP)
CPP_SOURCE = r"""
#include <torch/extension.h>
#include <c10/cuda/CUDAStream.h>
using stream_t = cudaStream_t;

// Helper to get current stream
static inline stream_t get_current_stream() {
    return at::cuda::getCurrentCUDAStream();
}

// Forward declarations of kernel launch wrappers
extern "C" {
void launch_fused_advection(const float* psi, const float* p, float* psi_out, float* v_Q_out,
                            int B, int N, int d, cudaStream_t stream);
void launch_fused_iir_update(const float* psi, float* h1, float* h2,
                             const float* theta, const int* chakra_offsets,
                             int B, int N, int d, int C, float rho, cudaStream_t stream);
}

// PyTorch wrapper for fused advection
std::tuple<torch::Tensor, torch::Tensor> fused_advection(torch::Tensor psi, torch::Tensor p) {
    TORCH_CHECK(psi.is_cuda(), "psi must be CUDA");
    TORCH_CHECK(p.is_cuda(), "p must be CUDA");

    at::DeviceGuard guard(psi.device());
    auto psi_c = psi.contiguous();
    auto p_c = p.contiguous();

    int B = psi_c.size(0);
    int N = psi_c.size(1);
    int d = psi_c.size(2);

    auto psi_out = torch::empty_like(psi_c);
    auto v_Q_out = torch::empty({B, N}, psi_c.options());

    launch_fused_advection(
        psi_c.data_ptr<float>(),
        p_c.data_ptr<float>(),
        psi_out.data_ptr<float>(),
        v_Q_out.data_ptr<float>(),
        B, N, d,
        at::cuda::getCurrentCUDAStream()
    );

    return std::make_tuple(psi_out, v_Q_out);
}

// PyTorch wrapper for fused IIR update
void fused_iir_update(
    torch::Tensor psi, torch::Tensor h1, torch::Tensor h2,
    torch::Tensor theta, torch::Tensor chakra_offsets, double rho
) {
    TORCH_CHECK(psi.is_cuda(), "psi must be CUDA");
    TORCH_CHECK(h1.is_cuda(), "h1 must be CUDA");
    TORCH_CHECK(h2.is_cuda(), "h2 must be CUDA");
    TORCH_CHECK(theta.is_cuda(), "theta must be CUDA");
    TORCH_CHECK(chakra_offsets.dtype() == torch::kInt32, "chakra_offsets must be int32");

    at::DeviceGuard guard(psi.device());
    auto psi_c = psi.contiguous();
    auto h1_c = h1.contiguous();
    auto h2_c = h2.contiguous();
    auto theta_c = theta.contiguous();
    auto offsets_c = chakra_offsets.contiguous();

    int B = psi_c.size(0);
    int N = psi_c.size(1);
    int d = psi_c.size(2);
    int C = theta_c.size(0);

    launch_fused_iir_update(
        psi_c.data_ptr<float>(),
        h1_c.data_ptr<float>(),
        h2_c.data_ptr<float>(),
        theta_c.data_ptr<float>(),
        offsets_c.data_ptr<int>(),
        B, N, d, C, (float)rho,
        at::cuda::getCurrentCUDAStream()
    );

    // Copy results back to the caller's tensors in case contiguous() produced copies.
    h1.copy_(h1_c);
    h2.copy_(h2_c);
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("fused_advection", &fused_advection, "Fused Qi advection");
    m.def("fused_iir_update", &fused_iir_update, "Fused IIR update");
}
"""

# ═══ JIT compilation ═══

_extension = None
_build_attempted = False


def _build_extension():
    """Lazy-build and cache the extension on first use."""
    global _extension, _build_attempted
    if _build_attempted:
        return _extension

    _build_attempted = True
    os.makedirs('logs', exist_ok=True)
    build_log = 'logs/fused_ops_build.log'

    # Suppress glog chatter during compilation
    old_glog = os.environ.get('GLOG_minloglevel')
    os.environ['GLOG_minloglevel'] = '3'

    # Redirect stdout/stderr to build log so no errors pollute training logs
    fd_stdout = os.dup(1)
    fd_stderr = os.dup(2)
    log_fd = os.open(build_log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    os.close(log_fd)

    try:
        extra_cflags = ['-O3', '-isystem', '/tmp/cassi_stubs']
        extra_cuda_cflags = ['-O3', '-isystem', '/tmp/cassi_stubs']
        if os.path.exists('/opt/rocm/include'):
            extra_cflags += ['-I/opt/rocm/include']
            extra_cuda_cflags += ['-I/opt/rocm/include']

        _extension = load_inline(
            name='cassi_fused_ops_v5',
            cpp_sources=[CPP_SOURCE],
            cuda_sources=[CUDA_SOURCE],
            extra_cflags=extra_cflags,
            extra_cuda_cflags=extra_cuda_cflags,
            with_cuda=True,
            verbose=False,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        _extension = None
    finally:
        os.dup2(fd_stdout, 1)
        os.dup2(fd_stderr, 2)
        os.close(fd_stdout)
        os.close(fd_stderr)
        if old_glog is None:
            os.environ.pop('GLOG_minloglevel', None)
        else:
            os.environ['GLOG_minloglevel'] = old_glog

    if _extension is not None:
        print("[fused_ops] JIT kernel loaded.")
    else:
        print("[fused_ops] JIT kernel build failed (see logs/fused_ops_build.log), using PyTorch fallbacks.")

    return _extension


# ═══ Python API ═══

def fused_advection(psi: torch.Tensor, p: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Fused pressure-gradient advection: grad(p) → v_Q clamp → upwind → psi += v_Q·upwind.

    Returns (psi_out, v_Q) so the same velocity can transport Qi.
    psi_out is NOT clamped; the caller clamps in qi_field.py.
    TEMPORARY: always use PyTorch fallback to ensure gradients flow through
    the field dynamics while the JIT kernel lacks a backward implementation.
    """
    return _pytorch_advection(psi, p)


def fused_iir_update(
    psi: torch.Tensor,
    h1: torch.Tensor,
    h2: torch.Tensor,
    theta: torch.Tensor,
    chakra_offsets: torch.Tensor,
    rho: float,
):
    """Fused IIR update across all C chakras in parallel.

    Replaces the sequential per-chakra loop. Modifies h1, h2 in-place.
    Falls back to PyTorch if kernel unavailable.
    """
    if not h1.is_contiguous() or not h2.is_contiguous():
        raise RuntimeError("fused_iir_update expects contiguous h1 and h2 tensors")

    ext = _build_extension()
    if ext is not None:
        try:
            ext.fused_iir_update(
                psi.contiguous(), h1, h2,
                theta.contiguous(), chakra_offsets.contiguous(),
                float(rho),
            )
            return
        except Exception:
            pass

    # PyTorch fallback — sequential per-chakra
    C = theta.size(0)
    for c in range(C):
        off = int(chakra_offsets[c].item())
        w   = int(chakra_offsets[c + 1].item()) - off
        psi_c = psi[:, :, off:off + w]
        a1 = 2.0 * rho * torch.cos(theta[c])
        a2 = -(rho ** 2)
        h1_c = h1[:, :, off:off + w]
        h2_c = h2[:, :, off:off + w]
        h_new = 0.5 * psi_c + a1 * h1_c + a2 * h2_c
        h2[:, :, off:off + w] = h1_c
        h1[:, :, off:off + w] = h_new


def _pytorch_advection(psi: torch.Tensor, p: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Pure-PyTorch pressure-gradient advection (differentiable)."""
    p_left  = torch.roll(p, shifts=1, dims=1)
    p_right = torch.roll(p, shifts=-1, dims=1)
    v_Q = -PHI_INV_FALLBACK * (p_right - p_left) / 2.0
    v_Q = v_Q.clamp(-1.0, 1.0)

    psi_left  = torch.roll(psi, shifts=1, dims=1)
    psi_right = torch.roll(psi, shifts=-1, dims=1)
    backward = psi - psi_left
    forward  = psi_right - psi
    upwind   = torch.where(v_Q.sign().unsqueeze(-1) > 0, backward, forward)

    return psi + v_Q.unsqueeze(-1) * upwind, v_Q


class FusedAdvectionFunction(torch.autograd.Function):
    """Custom autograd function: JIT kernel forward, PyTorch fallback backward."""

    @staticmethod
    def forward(ctx, psi: torch.Tensor, p: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        ext = _build_extension()
        if ext is not None:
            try:
                psi_out, v_Q = ext.fused_advection(psi.contiguous(), p.contiguous())
                ctx.save_for_backward(psi, p)
                ctx.mark_non_differentiable(v_Q)
                return psi_out, v_Q
            except Exception:
                pass

        # PyTorch fallback path (also used during backward recompute)
        psi_out, v_Q = _pytorch_advection(psi, p)
        ctx.save_for_backward(psi, p)
        ctx.mark_non_differentiable(v_Q)
        return psi_out, v_Q

    @staticmethod
    def backward(ctx, grad_psi_out, grad_v_Q):
        psi, p = ctx.saved_tensors
        psi = psi.detach().requires_grad_(True)
        p = p.detach().requires_grad_(True)
        with torch.enable_grad():
            psi_out, _ = _pytorch_advection(psi, p)
            grad_psi, grad_p = torch.autograd.grad(
                psi_out, (psi, p), grad_psi_out,
                retain_graph=False,
                create_graph=False,
                allow_unused=True,
            )
        return grad_psi, grad_p


# Constant for fallback (avoids importing cassi.cord at module level)
PHI_INV_FALLBACK = 0.618033988749895
