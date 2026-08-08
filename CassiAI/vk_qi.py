#!/usr/bin/env python3
"""Vulkan QiCube — compute pipeline for 3D PDE with Qi-driven learning.

All shaders compiled to SPIR-V in shaders/*.spv.
Runs entirely on GPU with zero backward passes, zero PyTorch.

Trains continuously on all files in datasets/active/, with periodic
online generation to monitor quality.

Usage:
    python3 vk_qi.py --test
    python3 vk_qi.py --max-bytes 1000000 --epochs 3 --gen-every 200000 --generate 200
    python3 vk_qi.py --lr 0.005 --dt 0.15 --stride 2048 --epochs 5 --gen-every 100000
"""

import argparse
import math
import struct
import sys
import time
from pathlib import Path

import numpy as np
import vulkan as vk

# ── Grid constants (must match shader #defines) ──
H = W = D = 16
N_VOXELS = H * W * D  # 4096
FIELD_DIM = 128  # d per voxel
V = 256  # vocabulary
BYTE_EMBED_DIM = 128

# Shader constants
VOXEL_STRIDE = FIELD_DIM * 2  # 256
STRIDE_W = D  # 16
STRIDE_H = D * W  # 256
N_BANDS = 13  # 7 primary + 6 sub-chakra harmonics
BAND_START = [0, 2, 4, 8, 14, 24, 40, 66, 87, 100, 113, 121, 126]


PHI = (1 + math.sqrt(5)) / 2
PHI_INV = 1.0 / PHI
PI = math.pi

# ── Push constants — unified layout (all shaders use same struct) ──
# Offset | Field       | Type | Readers
# 0      | dt          | f32  | nonlinear_step, linear_step
# 4      | pass        | u32  | normalize
# 8      | breath_t    | f32  | nonlinear_step
# 12     | target_byte | u32  | qi_accum
# 16     | lr          | f32  | qi_accum
# 20     | qi_target   | f32  | qi_accum
# 24-43  | pads          | -    | [6]=HWD, [7]=temp_bits, [8]=top_k, [9-10]=unused
PUSH_FORMAT = 'fIfIff' + 'i' * 5  # 6 data + 5 pad ints = 44 bytes
PUSH_SIZE = 44


def make_push(*, pass_val=0, dt=0.2, breath_t=0.0, target_byte=0,
              lr=0.01, qi_target=0.1, temperature=0.0, top_k=0, seed=0,
              rho_eps=0.95):
    """Pack push constants for all shaders (unified layout)."""
    temp_bits = struct.unpack('I', struct.pack('f', temperature))[0]
    rho_bits  = struct.unpack('I', struct.pack('f', rho_eps))[0]
    return struct.pack(PUSH_FORMAT,
        dt,             # f  [0] dt
        pass_val,       # I  [1] normalize_pass
        breath_t,       # f  [2] breath_t
        target_byte,    # I  [3] target_byte
        lr,             # f  [4] lr
        qi_target,      # f  [5] qi_target
        H * W * D,      # i  [6] HWD (unused)
        temp_bits,      # i  [7] temperature as uint-bits
        top_k,          # i  [8] top-k sampling cutoff
        seed,           # i  [9] PRNG seed for GPU sampling
        rho_bits,       # i [10] rho_eps as float-bits (qi_accum IIR damping)
    )
class VkQiCube:
    """Vulkan compute pipeline for QiCube PDE engine."""

    def __init__(self, lam=0.01, lr=None, qi_target=0.1, dt=0.2, stride=1024,
                 stride_min=512, stride_max=4096, no_adaptive_stride=False,
                 alpha=0.1, train_temp=0.1, rho_eps=0.95, mem_blend=0.05, sigma_max=0.0):
        self.lam = lam
        if lr is None:
            self.lr_min = lam / 3.0 * PHI_INV * PHI_INV
            self.lr_max = lam
            self.lr = self.lr_max
        else:
            self.lr = lr
        self.qi_target = qi_target
        self.dt = dt
        self.stride = stride
        self.stride_min = stride_min
        self.stride_max = stride_max
        self.no_adaptive_stride = no_adaptive_stride
        self.step_count = 0
        self.breath_phase = 0.0
        self.readout_correct = 0
        self.readout_total = 0
        self._alpha = alpha
        self.train_temp = train_temp
        self._rho_eps = rho_eps
        self._mem_blend = mem_blend  # field_memory blend weight (0.05 = 5% persistent memory)
        self._gamma = 0.15  # input blend strength for temporal continuity

        self._sigma_max = sigma_max  # field-diffusion noise level (0=disabled)


        # ── Rolling generation context window (maintains 4096-byte buffer for sinusoidal embedding) ──
        self._gen_window = np.zeros(N_VOXELS, dtype=np.uint8)

        self._init_vulkan()
        self._load_shaders()
        self._create_pipelines()
        self.buffers = {}
        self._allocate_buffers()

        # ── Load spherical neighbor table ──
        import os
        nt_path = os.path.join(os.path.dirname(__file__), 'shaders', 'neighbor_table.bin')
        if os.path.exists(nt_path):
            with open(nt_path, 'rb') as f:
                self._upload('neighbor_table', f.read())
        else:
            print("WARNING: neighbor_table.bin not found — spherical topology disabled")
        # ── Initialize embed_proj with Hadamard matrix (deterministic, orthogonal) ──
        def hadamard(n):
            if n == 1:
                return np.array([[1.0]], dtype=np.float32)
            h = hadamard(n // 2)
            return np.block([[h, h], [h, -h]]).astype(np.float32)

        H = hadamard(BYTE_EMBED_DIM) / np.sqrt(BYTE_EMBED_DIM)  # 128×128, orthogonal
        proj_dual = np.tile(H, (2, 1)).astype(np.float32)  # 256×128: first 128 rows Yang, second 128 rows Yin
        self._upload('embed_proj', proj_dual.tobytes())


        # ── Initialize byte_embed (small random for non-trivial generation embeddings) ──
        be = np.random.randn(V, BYTE_EMBED_DIM).astype(np.float32) * 0.1

        self._upload('byte_embed', be.tobytes())

        # ── Byte prototype table — clustering groups ──
        protos = np.zeros(V, dtype=np.uint32)

        # Each byte pulled toward its class prototype (e.g., all lowercase → 'e')
        protos[97:123]  = 101   # a-z → 'e'
        protos[65:91]   = 69    # A-Z → 'E'
        protos[48:58]   = 48    # 0-9 → '0'
        protos[32]      = 32    # space → itself
        # punctuation → ','
        for r in [(33,48),(58,65),(91,97),(123,127)]:
            protos[r[0]:r[1]] = 44
        protos[0:32] = 0       # control → 0
        protos[127] = 0

        # Zero-initialize qi_output to prevent VRAM garbage (NaN on AMD) poisoning initial readouts
        self._fill_buffer('qi_output', self._buffer_sizes['qi_output'])
        self._fill_buffer('voxel_eps_memory', self._buffer_sizes['voxel_eps_memory'])
        self._fill_buffer('field_memory', self._buffer_sizes['field_memory'])
        self._upload('byte_protos', protos.tobytes())

        # ── Initialize PDE params ──
        init_params = struct.pack('f' * 15,
            0.01,                        # [0] nu — diffusion
            0.0,                         # [1] hbar
            0.0,                         # [2] mass
            -0.02,                       # [3] g — defocusing (negative)
            0.05,                        # [4] chi — dispersion (enabled)
            0.0,                         # [5] A_B — breath amplitude (0 for now)
            0.0,                         # [6] adv_strength — advection (0 for now)
            self._alpha,                 # [7] alpha — self-prediction coupling (0.1)
            0.0,                         # [8] hyper_nu — hyper-viscosity (0=off)
            0.0,                         # [9] alpha_disp — scale-dependent dispersion (0=uniform)
            0.01,                        # [10] lambda — ε-recovery
            math.exp(-PHI_INV * PHI_INV),            # [11] condensate_blend — φ⁻²-damped IIR blend rate
            math.exp(-PHI_INV * PHI_INV * PHI_INV),  # [12] boundary_decay — φ⁻³-damped decay
            0.0,                                    # [13] attention_strength — 0=disabled
            0.0)                                    # [14] sigma — noise level for field diffusion (0=off)
        self._upload('params', init_params)

        # ── Initialize new consciousness-framework buffers ──
        self._fill_buffer('self_condensate', self._buffer_sizes['self_condensate'])
        self._fill_buffer('boundary_residuals', self._buffer_sizes['boundary_residuals'])
        self._fill_buffer('qi_grad', self._buffer_sizes['qi_grad'])

        # chakra_params: identity scale (1.0 for all 13 bands × 5 params)
        cp = np.ones(N_BANDS * 5, dtype=np.float32)
        self._upload('chakra_params', cp.tobytes())

        # band_phase: φ-spaced initial phases [0, 2π/φ, 4π/φ, ..., 24π/φ] mod 2π
        bp = np.array([(2.0 * math.pi * c / PHI) % (2.0 * math.pi) for c in range(N_BANDS)], dtype=np.float32)
        self._upload('band_phase', bp.tobytes())


    # ── Vulkan init ──


    def _init_vulkan(self):
        app_info = vk.VkApplicationInfo(
            applicationVersion=1,
            engineVersion=1,
            apiVersion=vk.VK_API_VERSION)
        inst_info = vk.VkInstanceCreateInfo(pApplicationInfo=app_info)
        self.inst = vk.vkCreateInstance(inst_info, None)

        gpus = vk.vkEnumeratePhysicalDevices(self.inst)
        self.gpu = gpus[0]
        props = vk.vkGetPhysicalDeviceProperties(self.gpu)
        print(f'GPU: {props.deviceName}', file=sys.stderr)

        # Find compute queue family
        qprops = vk.vkGetPhysicalDeviceQueueFamilyProperties(self.gpu)
        for i, qp in enumerate(qprops):
            if qp.queueFlags & vk.VK_QUEUE_COMPUTE_BIT:
                self.qfam = i
                break

        qci = vk.VkDeviceQueueCreateInfo(
            queueFamilyIndex=self.qfam, queueCount=1, pQueuePriorities=[1.0])
        self.dev = vk.vkCreateDevice(
            self.gpu, vk.VkDeviceCreateInfo(pQueueCreateInfos=[qci]), None)
        self.queue = vk.vkGetDeviceQueue(self.dev, self.qfam, 0)
        self.cpool = vk.vkCreateCommandPool(
            self.dev, vk.VkCommandPoolCreateInfo(queueFamilyIndex=self.qfam), None)

    def _load_shaders(self):
        base = Path(__file__).parent / 'shaders'
        names = ['gradient_lap', 'nonlinear_step', 'linear_step',
                 'normalize', 'qi_accum', 'self_pred_feedback', 'blend_input',
                 'embed_field', 'blend_memory', 'noise_field',
                 'breath_update', 'condensate_update', 'qi_grad',
                 'wu_xing_modulate', 'boundary_update']
        self.spv = {}
        for name in names:
            path = base / f'{name}.spv'
            with open(path, 'rb') as f:
                self.spv[name] = f.read()

    def _create_pipelines(self):
        # Push constant range — all shaders use same range but interpret differently
        pc_range = vk.VkPushConstantRange(
            stageFlags=vk.VK_SHADER_STAGE_COMPUTE_BIT,
            offset=0, size=PUSH_SIZE)
        # Descriptor set layout — one SSBO per binding 0-24
        bindings = []
        for b in range(25):
            bindings.append(vk.VkDescriptorSetLayoutBinding(
                binding=b,
                descriptorType=vk.VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                descriptorCount=1,
                stageFlags=vk.VK_SHADER_STAGE_COMPUTE_BIT))
        dsl = vk.VkDescriptorSetLayoutCreateInfo(
            bindingCount=len(bindings), pBindings=bindings)
        self.ds_layout = vk.vkCreateDescriptorSetLayout(self.dev, dsl, None)

        pli = vk.VkPipelineLayoutCreateInfo(
            pPushConstantRanges=[pc_range],
            pSetLayouts=[self.ds_layout])
        self.pipeline_layout = vk.vkCreatePipelineLayout(self.dev, pli, None)
        # Create descriptor set
        pool_sizes = [vk.VkDescriptorPoolSize(
            type=vk.VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, descriptorCount=25)]
        pool = vk.vkCreateDescriptorPool(self.dev,
            vk.VkDescriptorPoolCreateInfo(
                maxSets=1, pPoolSizes=pool_sizes), None)
        self.ds = vk.vkAllocateDescriptorSets(self.dev,
            vk.VkDescriptorSetAllocateInfo(
                descriptorPool=pool, descriptorSetCount=1,
                pSetLayouts=[self.ds_layout]))[0]

        # Create compute pipeline for each shader
        self.pipelines = {}
        for name, spv in self.spv.items():
            sm = vk.vkCreateShaderModule(self.dev,
                vk.VkShaderModuleCreateInfo(codeSize=len(spv), pCode=spv), None)
            stage = vk.VkPipelineShaderStageCreateInfo(
                stage=vk.VK_SHADER_STAGE_COMPUTE_BIT,
                module=sm, pName='main')
            pipe_ptr = vk.ffi.new('VkPipeline[1]')
            vk.vkCreateComputePipelines(self.dev, vk.VK_NULL_HANDLE,
                1,
                [vk.VkComputePipelineCreateInfo(
                    stage=stage, layout=self.pipeline_layout)],
                None, pipe_ptr)
            self.pipelines[name] = pipe_ptr[0]
            vk.vkDestroyShaderModule(self.dev, sm, None)

    def _find_memory_type(self, required, preferred=0):
        mem = vk.vkGetPhysicalDeviceMemoryProperties(self.gpu)
        for i in range(mem.memoryTypeCount):
            if mem.memoryTypes[i].propertyFlags & required:
                if not preferred or mem.memoryTypes[i].propertyFlags & preferred:
                    return i
    def _allocate_buffers(self):

        nv = N_VOXELS
        d = FIELD_DIM
        sizes = {
            'neighbor_table': nv * 6 * 2 * 4,  # 6 neighbor pairs (idx+weight) × N_VOXELS
            'psi': nv * d * 2 * 4,
            'psi_prev': nv * d * 2 * 4,
            'grad_h': nv * d * 2 * 4,
            'grad_w': nv * d * 2 * 4,
            'grad_d': nv * d * 2 * 4,
            'lap': nv * d * 2 * 4,  # binding 6 — Laplacian output

            'byte_indices': N_VOXELS * 4,  # binding 15 — per-voxel byte values
            'psi_pre_pde': nv * d * 2 * 4,  # binding 16 — pre-PDE psi snapshot for Qi
            'params': 15 * 4,  # [15] floats: nu, ..., attention_strength, sigma
            'byte_embed': V * BYTE_EMBED_DIM * 4,
            'embed_proj': 2 * d * BYTE_EMBED_DIM * 4,  # dual: Yang + Yin projections
            'byte_protos': V * 4,  # byte prototype index per byte (uint32)
            'norm_constants': 4 * 4,  # [2] correct/total + [2] sat_counters (gate_weight, att_mod)
            'accum': 7 * 4,
            'voxel_energy': nv * 4,
            'voxel_eps_memory': nv * 4,
            'voxel_eps_sum': nv * 4,
            'qi_output': (20 + V + V * BYTE_EMBED_DIM) * 4,  # + _pad_proj_center[V*BYTE_EMBED_DIM]
            'field_memory': nv * d * 2 * 4,  # binding 19 — persistent per-voxel memory field
            'self_condensate': nv * d * 2 * 4,  # binding 20 — thresholded time-averaged field
            'boundary_residuals': 6 * W * D * d * 2 * 4,  # binding 21 — 6 face buffers
            'chakra_params': N_BANDS * 5 * 4,  # binding 22 — 13 bands × 5 params
            'band_phase': N_BANDS * 4,  # binding 23 — per-band breathing phase
            'qi_grad': N_VOXELS * 4,  # binding 24 — per-voxel Qi gradient magnitude
        }
        self._buffer_sizes = sizes

        total = sum(sizes.values())
        mem_type = self._find_memory_type(
            required=vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
            preferred=vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)

        self.device_mem = vk.vkAllocateMemory(self.dev,
            vk.VkMemoryAllocateInfo(allocationSize=total,
                memoryTypeIndex=mem_type), None)

        # Staging buffer for host <-> device transfers
        staging_type = self._find_memory_type(
            required=vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                    vk.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)
        self.staging_mem = vk.vkAllocateMemory(self.dev,
            vk.VkMemoryAllocateInfo(allocationSize=8 * 1024 * 1024,
                memoryTypeIndex=staging_type), None)
        self.staging = vk.vkCreateBuffer(self.dev,
            vk.VkBufferCreateInfo(
                size=8 * 1024 * 1024,
                usage=vk.VK_BUFFER_USAGE_TRANSFER_SRC_BIT |
                      vk.VK_BUFFER_USAGE_TRANSFER_DST_BIT), None)
        vk.vkBindBufferMemory(self.dev, self.staging, self.staging_mem, 0)

        offset = 0

        for name in ['psi', 'psi_prev', 'grad_h', 'grad_w', 'grad_d', 'lap',
                      'params', 'byte_embed', 'embed_proj', 'neighbor_table',
                      'byte_protos', 'norm_constants', 'accum', 'voxel_energy',
                      'qi_output', 'byte_indices', 'psi_pre_pde', 'voxel_eps_memory',
                      'voxel_eps_sum', 'field_memory',
                      'self_condensate', 'boundary_residuals', 'chakra_params',
                      'band_phase', 'qi_grad']:
            sz = sizes[name]
            buf = vk.vkCreateBuffer(self.dev,
                vk.VkBufferCreateInfo(size=sz,
                    usage=vk.VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
                          vk.VK_BUFFER_USAGE_TRANSFER_DST_BIT |
                          vk.VK_BUFFER_USAGE_TRANSFER_SRC_BIT), None)
            vk.vkBindBufferMemory(self.dev, buf, self.device_mem, offset)
            self.buffers[name] = buf
            offset += sz
        # Build descriptor writes to connect SSBOs to bindings
        buf_list = ['psi', 'psi_prev', 'grad_h', 'grad_w', 'grad_d', 'lap',
                    'params', 'byte_embed', 'embed_proj', 'neighbor_table',
                    'byte_protos', 'norm_constants', 'accum', 'voxel_energy',
                    'qi_output', 'byte_indices', 'psi_pre_pde', 'voxel_eps_memory',
                    'voxel_eps_sum', 'field_memory',
                    'self_condensate', 'boundary_residuals', 'chakra_params',
                    'band_phase', 'qi_grad']
        writes = []
        for b, name in enumerate(buf_list):
            writes.append(vk.VkWriteDescriptorSet(
                dstSet=self.ds, dstBinding=b, dstArrayElement=0,
                descriptorType=vk.VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
                descriptorCount=1,
                pBufferInfo=[vk.VkDescriptorBufferInfo(
                    buffer=self.buffers[name], offset=0, range=sizes[name])]))
        vk.vkUpdateDescriptorSets(self.dev, len(writes), writes, 0, [])

    def _upload(self, dst_buf_name, data):
        """Upload data to a GPU SSBO via staging buffer."""
        ptr = vk.vkMapMemory(self.dev, self.staging_mem, 0, len(data), 0)
        vk.ffi.memmove(ptr, data, len(data))
        vk.vkUnmapMemory(self.dev, self.staging_mem)
        self._copy_buffer(self.staging, self.buffers[dst_buf_name], 0, 0, len(data))
    def _read_result(self, buf_name, offset, size, fmt='f'):
        """Read back data from a GPU SSBO starting at `offset` bytes."""
        self._copy_buffer(self.buffers[buf_name], self.staging, offset, 0, size)
        ptr = vk.vkMapMemory(self.dev, self.staging_mem, 0, size, 0)
        data = bytes(ptr)[:size]
        vk.vkUnmapMemory(self.dev, self.staging_mem)
        return struct.unpack(fmt * (size // struct.calcsize(fmt)), data)


    def _copy_buffer(self, src, dst, src_off, dst_off, size):
        """Issue a vkCmdCopyBuffer and wait."""
        cmd = vk.vkAllocateCommandBuffers(self.dev,
            vk.VkCommandBufferAllocateInfo(
                commandPool=self.cpool,
                level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                commandBufferCount=1))[0]
        vk.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo(
            flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT))
        vk.vkCmdCopyBuffer(cmd, src, dst, 1,
            vk.VkBufferCopy(srcOffset=src_off, dstOffset=dst_off, size=size))
        vk.vkEndCommandBuffer(cmd)
        vk.vkQueueSubmit(self.queue, 1,
            vk.VkSubmitInfo(pCommandBuffers=[cmd]), vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.queue)
        vk.vkFreeCommandBuffers(self.dev, self.cpool, 1, [cmd])

    def _fill_buffer(self, name, size, value=0):
        """Fill a GPU SSBO with a 32-bit value using vkCmdFillBuffer."""
        cmd = vk.vkAllocateCommandBuffers(self.dev,
            vk.VkCommandBufferAllocateInfo(
                commandPool=self.cpool,
                level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                commandBufferCount=1))[0]
        vk.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo(
            flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT))
        vk.vkCmdFillBuffer(cmd, self.buffers[name], 0, size, value)
        vk.vkEndCommandBuffer(cmd)
        vk.vkQueueSubmit(self.queue, 1,
            vk.VkSubmitInfo(pCommandBuffers=[cmd]), vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.queue)
        vk.vkFreeCommandBuffers(self.dev, self.cpool, 1, [cmd])



    def _dispatch_batch(self, batch):
        """Record and submit multiple compute dispatches in ONE command buffer.

        batch: list of (pipeline_name, push_bytes, global_size) tuples.
        All dispatched sequentially on GPU with a single queue submit + wait.
        """
        cmd = vk.vkAllocateCommandBuffers(self.dev,
            vk.VkCommandBufferAllocateInfo(
                commandPool=self.cpool,
                level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                commandBufferCount=1))[0]
        vk.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo(
            flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT))

        for name, push_bytes, global_size in batch:
            n_groups = (global_size + 63) // 64
            vk.vkCmdBindPipeline(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                                 self.pipelines[name])
            vk.vkCmdBindDescriptorSets(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                                       self.pipeline_layout, 0, 1, [self.ds],
                                       0, [])
            push_cdata = vk.ffi.new('char[]', push_bytes)
            vk.vkCmdPushConstants(cmd, self.pipeline_layout,
                                  vk.VK_SHADER_STAGE_COMPUTE_BIT,
                                  0, len(push_bytes), push_cdata)
            vk.vkCmdDispatch(cmd, n_groups, 1, 1)

        vk.vkEndCommandBuffer(cmd)
        vk.vkQueueSubmit(self.queue, 1,
            vk.VkSubmitInfo(pCommandBuffers=[cmd]), vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.queue)
        vk.vkFreeCommandBuffers(self.dev, self.cpool, 1, [cmd])

    def _submit_batch(self, batch):
        """Record and submit mixed compute + copy + fill commands in ONE submission.

        batch: list of command dicts:
          {'type': 'dispatch', 'name': str, 'push': bytes, 'global_size': int}
          {'type': 'copy', 'src': str, 'dst': str, 'size': int,
                              'src_off': int, 'dst_off': int}
          {'type': 'fill', 'buf': str, 'size': int, 'value': int}
        All executed sequentially on GPU with a single queue submit + wait.
        """
        cmd = vk.vkAllocateCommandBuffers(self.dev,
            vk.VkCommandBufferAllocateInfo(
                commandPool=self.cpool,
                level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                commandBufferCount=1))[0]
        vk.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo(
            flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT))

        need_barrier = False
        for item in batch:
            if item['type'] == 'fill':
                vk.vkCmdFillBuffer(cmd, self.buffers[item['buf']],
                                   item.get('offset', 0), item['size'],
                                   item['value'])
                need_barrier = True
            elif item['type'] == 'copy':
                if need_barrier:
                    mem_barrier = vk.VkMemoryBarrier(
                        srcAccessMask=vk.VK_ACCESS_MEMORY_WRITE_BIT,
                        dstAccessMask=vk.VK_ACCESS_MEMORY_READ_BIT | vk.VK_ACCESS_MEMORY_WRITE_BIT)
                    vk.vkCmdPipelineBarrier(cmd,
                        vk.VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                        vk.VK_PIPELINE_STAGE_TRANSFER_BIT,
                        0, 1, [mem_barrier], 0, [], 0, [])
                    need_barrier = False
                vk.vkCmdCopyBuffer(cmd, self.buffers[item['src']],
                                   self.buffers[item['dst']], 1,
                                   vk.VkBufferCopy(
                                       srcOffset=item.get('src_off', 0),
                                       dstOffset=item.get('dst_off', 0),
                                       size=item['size']))
                need_barrier = True
            elif item['type'] == 'dispatch':
                if need_barrier:
                    mem_barrier = vk.VkMemoryBarrier(
                        srcAccessMask=vk.VK_ACCESS_MEMORY_WRITE_BIT,
                        dstAccessMask=vk.VK_ACCESS_SHADER_READ_BIT | vk.VK_ACCESS_SHADER_WRITE_BIT)
                    vk.vkCmdPipelineBarrier(cmd,
                        vk.VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                        vk.VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                        0, 1, [mem_barrier], 0, [], 0, [])
                    need_barrier = False
                n_groups = (item['global_size'] + 63) // 64
                vk.vkCmdBindPipeline(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                                     self.pipelines[item['name']])
                vk.vkCmdBindDescriptorSets(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                                           self.pipeline_layout, 0, 1, [self.ds],
                                           0, [])
                push_cdata = vk.ffi.new('char[]', item['push'])
                vk.vkCmdPushConstants(cmd, self.pipeline_layout,
                                      vk.VK_SHADER_STAGE_COMPUTE_BIT,
                                      0, len(item['push']), push_cdata)
                vk.vkCmdDispatch(cmd, n_groups, 1, 1)
                need_barrier = True

        vk.vkEndCommandBuffer(cmd)
        vk.vkQueueSubmit(self.queue, 1,
            vk.VkSubmitInfo(pCommandBuffers=[cmd]), vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.queue)
        vk.vkFreeCommandBuffers(self.dev, self.cpool, 1, [cmd])

    def _dispatch(self, name, push_bytes, global_size):
        """Dispatch a single compute shader with push constants (one submit, one wait)."""
        n_groups = (global_size + 63) // 64
        cmd = vk.vkAllocateCommandBuffers(self.dev,
            vk.VkCommandBufferAllocateInfo(
                commandPool=self.cpool,
                level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                commandBufferCount=1))[0]
        vk.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo(
            flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT))
        vk.vkCmdBindPipeline(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                             self.pipelines[name])
        vk.vkCmdBindDescriptorSets(cmd, vk.VK_PIPELINE_BIND_POINT_COMPUTE,
                                   self.pipeline_layout, 0, 1, [self.ds],
                                   0, [])
        push_cdata = vk.ffi.new('char[]', push_bytes)
        vk.vkCmdPushConstants(cmd, self.pipeline_layout,
                              vk.VK_SHADER_STAGE_COMPUTE_BIT,
                              0, len(push_bytes), push_cdata)
        vk.vkCmdDispatch(cmd, n_groups, 1, 1)
        vk.vkEndCommandBuffer(cmd)
        vk.vkQueueSubmit(self.queue, 1,
            vk.VkSubmitInfo(pCommandBuffers=[cmd]), vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.queue)
        vk.vkFreeCommandBuffers(self.dev, self.cpool, 1, [cmd])


    def run_pde(self, k_steps=5, sigma=0.0, dt=None):
        """Run the PDE pipeline for k Strang steps with optional noise.

        External scripts call this to use the PDE as a physics-informed
        denoising/generative kernel without byte ingestion.

        Args:
            k_steps: number of Strang-split PDE steps (default 5).
            sigma: noise level for field-diffusion. 0 = no noise.
            dt: timestep override (None = use self.dt).
        """
        if dt is None:
            dt = self.dt
        batch = []
        # ── Noise injection ──
        if sigma > 0.0:
            p = np.array(self._read_result('params', 0, 15*4, 'f'), dtype=np.float32)
            p[14] = sigma
            self._upload('params', p.tobytes())
            batch.append({'type': 'dispatch', 'name': 'noise_field',
                          'push': make_push(), 'global_size': N_VOXELS * FIELD_DIM * 2})
        # ── PDE integration (k Strang steps) ──
        for step in range(k_steps):
            bt = self.breath_phase + step * 0.2
            push_pde = make_push(dt=dt, breath_t=bt)
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'linear_step',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                          'push': push_pde, 'global_size': N_VOXELS * FIELD_DIM})
            push_norm = make_push(pass_val=0)
            batch.append({'type': 'dispatch', 'name': 'normalize',
                          'push': push_norm, 'global_size': N_VOXELS})
            push_norm2 = make_push(pass_val=1)
            batch.append({'type': 'dispatch', 'name': 'normalize',
                          'push': push_norm2, 'global_size': N_VOXELS})
        self._submit_batch(batch)
        self.breath_phase = (self.breath_phase + k_steps * 0.2) % (2 * math.pi)

    def ingest_window(self, data, offset, learn=True):
        """Process one 3D window of bytes via Vulkan compute pipeline."""
        window = data[offset:offset + N_VOXELS]
        # 0. Advance per-band breathing phases (before any field ops)
        self._dispatch('breath_update', make_push(dt=self.dt), N_BANDS)

        # 1. Upload byte indices and dispatch embed_field to write psi on GPU
        self._upload('byte_indices', np.frombuffer(window, dtype=np.uint8).astype(np.uint32).tobytes())
        self._dispatch('embed_field', make_push(), N_VOXELS * FIELD_DIM)

        # 1.5. Inject boundary residuals from previous window into psi face voxels
        self._dispatch('boundary_update', make_push(pass_val=0),
                       6 * 16 * 16 * FIELD_DIM)

        # 2-6. Zero accumulators + PDE + qi_accum + copy psi→psi_prev
        next_b = data[offset + N_VOXELS] if offset + N_VOXELS < len(data) else 0
        push_qi = make_push(target_byte=next_b, lr=self.lr, qi_target=self.qi_target,
                            dt=self.dt, breath_t=self.breath_phase,
                            temperature=self.train_temp if learn else 0.0,
                            rho_eps=self._rho_eps)
        sz = N_VOXELS * FIELD_DIM * 2 * 4

        batch = []
        # 2. Zero accumulators via vkCmdFillBuffer (no staging)
        batch.append({'type': 'fill', 'buf': 'accum', 'size': 28, 'value': 0})
        batch.append({'type': 'fill', 'buf': 'norm_constants', 'size': 16, 'value': 0})
        batch.append({'type': 'fill', 'buf': 'voxel_energy', 'size': N_VOXELS * 4, 'value': 0})
        batch.append({'type': 'fill', 'buf': 'voxel_eps_sum', 'size': N_VOXELS * 4, 'value': 0})

        # 2.5. Blend input with previous field state for temporal continuity
        push_blend = make_push(breath_t=self._gamma)
        batch.append({'type': 'dispatch', 'name': 'blend_input',
                      'push': push_blend, 'global_size': N_VOXELS * FIELD_DIM * 2})
        # 2.6. Blend field_memory into psi for long-timescale feedback
        if self._mem_blend > 0.0:
            push_mem = make_push(breath_t=self._mem_blend)
            batch.append({'type': 'dispatch', 'name': 'blend_memory',
                          'push': push_mem, 'global_size': N_VOXELS * FIELD_DIM * 2})
        # 2.6b. Blend self_condensate into psi (slower attractor, pass=1)
        push_cond = make_push(breath_t=0.03, pass_val=1)
        batch.append({'type': 'dispatch', 'name': 'blend_memory',
                      'push': push_cond, 'global_size': N_VOXELS * FIELD_DIM * 2})
        # 2.7. Snapshot post-blend psi for Qi + readout (before PDE decorrelation)
        batch.append({'type': 'copy', 'src': 'psi', 'dst': 'psi_pre_pde', 'size': sz})

        # 2.8. Field-diffusion noise injection (training only, when sigma_max > 0)
        if self._sigma_max > 0.0:
            sigma = np.random.uniform(0, self._sigma_max)
            p = np.array(self._read_result('params', 0, 15*4, 'f'), dtype=np.float32)
            p[14] = sigma
            self._upload('params', p.tobytes())
            batch.append({'type': 'dispatch', 'name': 'noise_field',
                          'push': make_push(), 'global_size': N_VOXELS * FIELD_DIM * 2})
        # 3. PDE integration (5 Strang steps)
        for step in range(5):
            bt = self.breath_phase + step * 0.2
            push = make_push(dt=self.dt, breath_t=bt)
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'linear_step',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                          'push': push, 'global_size': N_VOXELS * FIELD_DIM})
            push_norm = make_push(pass_val=0)
            batch.append({'type': 'dispatch', 'name': 'normalize',
                          'push': push_norm, 'global_size': N_VOXELS})
            push_norm2 = make_push(pass_val=1)
            batch.append({'type': 'dispatch', 'name': 'normalize',
                          'push': push_norm2, 'global_size': N_VOXELS})

        # 4. Qi + readout + embedder update
        batch.append({'type': 'dispatch', 'name': 'qi_accum',
                      'push': push_qi, 'global_size': N_VOXELS * FIELD_DIM})

        # 4.5. Compute per-voxel Qi gradient for attention modulation
        batch.append({'type': 'dispatch', 'name': 'qi_grad',
                      'push': make_push(), 'global_size': N_VOXELS})


        # 5. Self-predictive feedback: ψ ← ψ + α·P[ψ]
        if self._alpha > 0.0:
            batch.append({'type': 'dispatch', 'name': 'self_pred_feedback',
                          'push': make_push(),
                          'global_size': N_VOXELS * FIELD_DIM})

        # 5.5. Wu Xing dynamic modulation: write chakra_params for next window
        batch.append({'type': 'dispatch', 'name': 'wu_xing_modulate',
                      'push': make_push(), 'global_size': 1})

        # 5.6. Accumulate boundary residuals from psi face voxels (pass=1)
        batch.append({'type': 'dispatch', 'name': 'boundary_update',
                      'push': make_push(pass_val=1),
                      'global_size': 6 * 16 * 16 * FIELD_DIM})

        # 5.7. Update self-condensate: IIR-blend psi into thresholded attractor
        batch.append({'type': 'dispatch', 'name': 'condensate_update',
                      'push': make_push(), 'global_size': N_VOXELS * FIELD_DIM})


        # 6.0. Copy psi → field_memory (persistent memory field)
        batch.append({'type': 'copy', 'src': 'psi', 'dst': 'field_memory', 'size': sz})


        # 6. Copy psi → psi_prev for next window
        batch.append({'type': 'copy', 'src': 'psi', 'dst': 'psi_prev', 'size': sz})


        t0 = time.perf_counter()
        self._submit_batch(batch)
        t_batch = time.perf_counter() - t0
        qi_val, = self._read_result('qi_output', 0, 4, 'f')
        counts = self._read_result('norm_constants', 0, 16, 'I')
        correct, total = (counts[0], counts[1]) if len(counts) >= 2 else (0, 1)
        # ── M1 telemetry hook (additive-only; never affects training) ──
        if getattr(self, 'telemetry', None) is None:
            try:
                from vk_qi_telemetry import VkQiTelemetry
                self.telemetry = VkQiTelemetry(self)
            except Exception:
                self.telemetry = None
        if self.telemetry is not None:
            try:
                self.telemetry.on_window(self, qi_val)
            except Exception:
                pass

        # 7. Update persistent state
        self.step_count += 1
        if learn:
            self.readout_correct += correct
            self.readout_total += total

        self.breath_phase += self.lr * 0.1 * (qi_val - self.qi_target)
        self.breath_phase = self.breath_phase % (2 * PI)

        if self.step_count % 100 == 0:
            self.qi_target = max(0.05, self.qi_target - 1e-4)

        # Adaptive stride: scale with Qi density
        if not getattr(self, 'no_adaptive_stride', False):
            qi_ratio = qi_val / max(self.qi_target, 1e-6)
            if qi_ratio > 2.0:
                self.stride = max(self.stride_min, self.stride - 128)
            elif qi_ratio < 0.5:
                self.stride = min(self.stride_max, self.stride + 128)

        return qi_val

    # ── Generate ──

    def generate(self, num_bytes, temperature=0.8, top_k=40, sigma_scale=1.0):
        """Generate bytes from the current field state.
        Uses ancestral sampling with field diffusion if sigma_max > 0.
        Single dispatch per byte: PDE + GPU sampling + learning + copy psi→psi_prev.
        """
        out = bytearray()
        sz = N_VOXELS * FIELD_DIM * 2 * 4
        self._gen_window = np.frombuffer(
            getattr(self, '_last_train_window', b'\x00' * N_VOXELS),
            dtype=np.uint8).copy()
        # Precompute sigma schedule if using field diffusion (ancestral sampling)
        sigma_max = self._sigma_max * sigma_scale
        sigma_vals = None
        if sigma_max > 0.0:
            # Linear annealing from sigma_max to 0
            sigma_vals = [sigma_max * (1.0 - i / max(num_bytes - 1, 1))
                          for i in range(num_bytes)]
        for gen_i in range(num_bytes):
            # Upload sigma for this generation step if using noise
            if sigma_vals is not None:
                p = np.array(self._read_result('params', 0, 15*4, 'f'), dtype=np.float32)
                p[14] = sigma_vals[gen_i]
                self._upload('params', p.tobytes())
            # Single submission: zero + PDE + qi_accum (GPU samples + learns) + copy
            # 0a. Advance per-band breathing phases
            self._dispatch('breath_update', make_push(dt=self.dt), N_BANDS)

            # 0b. Inject boundary residuals from previous iteration into psi face voxels
            self._dispatch('boundary_update', make_push(pass_val=0),
                           6 * 16 * 16 * FIELD_DIM)

            batch = []
            # 1. Zero accumulators
            batch.append({'type': 'fill', 'buf': 'accum', 'size': 28, 'value': 0})
            batch.append({'type': 'fill', 'buf': 'norm_constants', 'size': 16, 'value': 0})
            batch.append({'type': 'fill', 'buf': 'voxel_energy', 'size': N_VOXELS * 4, 'value': 0})
            batch.append({'type': 'fill', 'buf': 'voxel_eps_sum', 'size': N_VOXELS * 4, 'value': 0})

            # 1.5. Blend input with previous field state for temporal continuity
            push_blend = make_push(breath_t=self._gamma)
            batch.append({'type': 'dispatch', 'name': 'blend_input',
                          'push': push_blend, 'global_size': N_VOXELS * FIELD_DIM * 2})
            # 1.6. Blend field_memory into psi for long-timescale feedback
            if self._mem_blend > 0.0:
                push_mem = make_push(breath_t=self._mem_blend)
                batch.append({'type': 'dispatch', 'name': 'blend_memory',
                              'push': push_mem, 'global_size': N_VOXELS * FIELD_DIM * 2})
            # 1.6b. Blend self_condensate into psi (slower attractor, pass=1)
            push_cond = make_push(breath_t=0.03, pass_val=1)
            batch.append({'type': 'dispatch', 'name': 'blend_memory',
                          'push': push_cond, 'global_size': N_VOXELS * FIELD_DIM * 2})
            # 1.7. Snapshot post-blend psi for Qi + readout (before PDE decorrelation)
            batch.append({'type': 'copy', 'src': 'psi', 'dst': 'psi_pre_pde', 'size': sz})

            # 1.8. Field-diffusion noise injection (generation with ancestral sampling)
            if self._sigma_max > 0.0:
                batch.append({'type': 'dispatch', 'name': 'noise_field',
                              'push': make_push(), 'global_size': N_VOXELS * FIELD_DIM * 2})

            # 2. PDE integration (5 Strang steps)
            for step in range(5):
                bt = self.breath_phase + step * 0.2
                push = make_push(dt=self.dt, breath_t=bt)
                batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                batch.append({'type': 'dispatch', 'name': 'linear_step',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                batch.append({'type': 'dispatch', 'name': 'gradient_lap',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                batch.append({'type': 'dispatch', 'name': 'nonlinear_step',
                              'push': push, 'global_size': N_VOXELS * FIELD_DIM})
                push_norm = make_push(pass_val=0)
                batch.append({'type': 'dispatch', 'name': 'normalize',
                              'push': push_norm, 'global_size': N_VOXELS})
                push_norm2 = make_push(pass_val=1)
                batch.append({'type': 'dispatch', 'name': 'normalize',
                              'push': push_norm2, 'global_size': N_VOXELS})
            push_qi = make_push(target_byte=0, lr=0.0, qi_target=self.qi_target,
                                dt=self.dt, breath_t=self.breath_phase,
                                temperature=temperature, top_k=top_k,
                                seed=self.step_count, rho_eps=self._rho_eps)
            batch.append({'type': 'dispatch', 'name': 'qi_accum',
                          'push': push_qi, 'global_size': N_VOXELS * FIELD_DIM})

            # 3.5. Compute per-voxel Qi gradient for attention modulation
            batch.append({'type': 'dispatch', 'name': 'qi_grad',
                          'push': make_push(), 'global_size': N_VOXELS})

            # 4a. Self-predictive feedback: ψ ← ψ + α·P[ψ]
            if self._alpha > 0.0:
                batch.append({'type': 'dispatch', 'name': 'self_pred_feedback',
                              'push': make_push(),
                              'global_size': N_VOXELS * FIELD_DIM})


            # 3.5. Copy psi → field_memory (persistent memory field)
            batch.append({'type': 'copy', 'src': 'psi', 'dst': 'field_memory', 'size': sz})

            # 5.5. Wu Xing dynamic modulation: write chakra_params for next window
            batch.append({'type': 'dispatch', 'name': 'wu_xing_modulate',
                          'push': make_push(), 'global_size': 1})

            # 5.6. Accumulate boundary residuals from psi face voxels (pass=1)
            batch.append({'type': 'dispatch', 'name': 'boundary_update',
                          'push': make_push(pass_val=1),
                          'global_size': 6 * 16 * 16 * FIELD_DIM})

            # 5.7. Update self-condensate: IIR-blend psi into thresholded attractor
            batch.append({'type': 'dispatch', 'name': 'condensate_update',
                          'push': make_push(), 'global_size': N_VOXELS * FIELD_DIM})

            # 4. Copy psi → psi_prev for next window
            batch.append({'type': 'copy', 'src': 'psi', 'dst': 'psi_prev', 'size': sz})

            self._submit_batch(batch)

            # 5. Read sampled byte (4 bytes at offset 12) and qi_value (4 bytes at offset 0)
            sampled = self._read_result('qi_output', 12, 4, 'I')[0]
            out.append(sampled)

            # Accuracy counters with lr=0 are self-consistency only — don't accumulate
            self.step_count += 1
            # 7. Rolling context window — embed next window on GPU
            self._gen_window[:-1] = self._gen_window[1:]
            self._gen_window[-1] = sampled
            self._upload('byte_indices', self._gen_window.astype(np.uint32).tobytes())
            self._dispatch('embed_field', make_push(), N_VOXELS * FIELD_DIM)
            self._gen_window[-1] = sampled

            # 8. Update breath phase
            qi_val, = self._read_result('qi_output', 0, 4, 'f')
            self.breath_phase += self.lr * 0.1 * (qi_val - self.qi_target)
            self.breath_phase = self.breath_phase % (2 * PI)

            # 9. Decay qi_target slowly
            if self.step_count % 100 == 0:
                self.qi_target = max(0.05, self.qi_target - 1e-4)

        return bytes(out)

    # ── Checkpoint save/load ──

    def save_checkpoint(self, path):
        """Save all persistent state to a .npz file."""
        state = {}
        for name in ['psi', 'psi_prev', 'byte_embed', 'embed_proj',
                     'params', 'voxel_eps_memory', 'field_memory',
                     'self_condensate', 'band_phase', 'chakra_params',
                     'boundary_residuals']:
            state[name] = np.array(
                self._read_result(name, 0, self._buffer_sizes[name], 'f'),
                dtype=np.float32
            )
        state['_step_count'] = np.array(self.step_count)
        state['_readout_correct'] = np.array(self.readout_correct)
        state['_readout_total'] = np.array(self.readout_total)
        state['_breath_phase'] = np.array(self.breath_phase)
        state['_qi_target'] = np.array(self.qi_target)
        state['_lr'] = np.array(self.lr)
        state['_dt'] = np.array(self.dt)
        state['_stride'] = np.array(self.stride)
        state['_alpha'] = np.array(self._alpha)
        # Read params from device to get current values
        p = np.array(self._read_result('params', 0, 15*4, 'f'), dtype=np.float32)
        state['_condensate_blend'] = np.array(p[11])
        state['_boundary_decay'] = np.array(p[12])
        state['_attention_strength'] = np.array(p[13])
        state['_sigma'] = np.array(p[14])
        # M3: psi through the φ-shell codec + certificate; scalars stay c64.
        # On any codec failure the raw psi c64 path is kept (never break checkpointing).
        try:
            from vk_qi_codec import encode as _codec_encode
            import json as _json
            packet, cert = _codec_encode(state['psi'])
            state['psi'] = np.frombuffer(packet, dtype=np.uint8)
            state['psi_codec'] = np.array(True)
            state['psi_codec_cert'] = np.frombuffer(
                _json.dumps(cert).encode('utf-8'), dtype=np.uint8)
        except Exception as e:
            print(f'  [codec] psi kept raw c64: {e}')
        np.savez(path, **state)
        print(f'Checkpoint saved: {path}')

    def load_checkpoint(self, path):
        """Load persistent state from a .npz file."""
        state = np.load(path)
        # M3: codec'd checkpoints carry psi as a packet + certificate; decode
        # transparently. Old npz (raw psi c64) loads unchanged (acceptance iii).
        codec_flag = bool(state['psi_codec']) if 'psi_codec' in state else False
        for name in ['psi', 'psi_prev', 'byte_embed', 'embed_proj',
                     'params', 'voxel_eps_memory', 'field_memory',
                     'self_condensate', 'band_phase', 'chakra_params',
                     'boundary_residuals']:
            if name in state and not (codec_flag and name == 'psi'):
                self._upload(name, state[name].tobytes())
        if codec_flag:
            from vk_qi_codec import decode as _codec_decode
            psi_flat = _codec_decode(state['psi'].tobytes())
            self._upload('psi', psi_flat.tobytes())
        self.step_count = int(state['_step_count'])
        self.readout_correct = int(state['_readout_correct'])
        self.readout_total = int(state['_readout_total'])
        self.breath_phase = float(state['_breath_phase'])
        self.qi_target = float(state['_qi_target'])
        self.lr = float(state['_lr'])
        self.stride = int(state.get('_stride', self.stride))
        self.dt = float(state['_dt'])
        # Load params[7]=alpha and params[11-13] in one upload
        self._alpha = float(state.get('_alpha', PHI_INV))
        p = np.array(self._read_result('params', 0, 15*4, 'f'), dtype=np.float32)
        p[7] = self._alpha
        p[11] = float(state.get('_condensate_blend', math.exp(-PHI_INV * PHI_INV)))
        p[12] = float(state.get('_boundary_decay', math.exp(-PHI_INV * PHI_INV * PHI_INV)))
        p[13] = float(state.get('_attention_strength', 0.0))
        p[14] = float(state.get('_sigma', 0.0))
        self._upload('params', p.tobytes())
        print(f'Checkpoint loaded: {path} (step={self.step_count})')

    def __del__(self):
        try:
            for buf in self.buffers.values():
                vk.vkDestroyBuffer(self.dev, buf, None)
            vk.vkFreeMemory(self.dev, self.device_mem, None)
            vk.vkDestroyBuffer(self.dev, self.staging, None)
            vk.vkFreeMemory(self.dev, self.staging_mem, None)
            vk.vkDestroyPipelineLayout(self.dev, self.pipeline_layout, None)
            vk.vkDestroyDescriptorSetLayout(self.dev, self.ds_layout, None)
            vk.vkDestroyCommandPool(self.dev, self.cpool, None)
            vk.vkDestroyDevice(self.dev, None)
            vk.vkDestroyInstance(self.inst, None)
        except Exception:
            pass




def _show_gen(gen, tag=''):
    """Print generation stats and a text preview."""
    printable = sum(1 for b in gen if 32 <= b < 127)
    print(f'  {tag} {len(gen)} bytes — {printable}/{len(gen)} printable '
          f'({100*printable//len(gen)}%)')
    preview = ''.join(chr(b) if 32 <= b < 127 else '?' for b in gen[:160])
    print(f'  {preview}')


def _ingest(engine, path, max_bytes, gen_every=0, gen_temp=0.7, gen_topk=30, save_every=0):
    """Ingest from a file, periodically generating if gen_every > 0.
    
    Returns number of windows processed.
    """
    if max_bytes > 0:
        with open(path, 'rb') as f:
            data = f.read(max_bytes)
    else:
        data = np.memmap(path, dtype=np.uint8, mode='r')
    print(f'Ingesting {len(data)} bytes from {path}...')
    t0 = time.time()
    offset = 0
    bytes_until_gen = gen_every
    while offset + N_VOXELS <= len(data):
        engine._cur_offset = offset  # M4 keylog: window's data offset
        qi = engine.ingest_window(data, offset, learn=True)
        offset += engine.stride
        bytes_until_gen -= engine.stride

        # Periodic generation during training
        if gen_every > 0 and bytes_until_gen <= 0:
            gen = engine.generate(200, temperature=gen_temp, top_k=gen_topk)
            _show_gen(gen, f'[gen @ win={engine.step_count}]')
            # M1 telemetry: record generation quality at this step (additive)
            if getattr(engine, 'telemetry', None) is not None:
                try:
                    engine.telemetry.on_generation(gen, engine.step_count)
                except Exception:
                    pass
            bytes_until_gen = gen_every

        if engine.step_count % 1000 == 0:
            acc = engine.readout_correct / max(engine.readout_total, 1)
            elapsed = time.time() - t0
            bps = (engine.step_count * engine.stride) / max(elapsed, 1e-6)
            print(f'  win={engine.step_count} qi={qi:.4f} acc={acc:.4f} '
                  f'et={elapsed:.1f}s ({bps:.0f} B/s)')

        # Periodic checkpoint save
        if save_every > 0 and engine.step_count % save_every == 0:
            ckpt_dir = Path('checkpoints')
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            engine.save_checkpoint(str(ckpt_dir / f'step_{engine.step_count}.npz'))
    acc = engine.readout_correct / max(engine.readout_total, 1)
    print(f'Ingest done: {engine.step_count} windows, acc={acc:.4f}')
    return engine.step_count


def _generate(engine, n, temp, top_k, out_dir='.'):
    """Generate n bytes, write to file, show preview."""
    t0 = time.time()
    gen = engine.generate(n, temperature=temp, top_k=top_k)
    t1 = time.time()
    bps = n / (t1 - t0)
    print(f'Generated {n} bytes in {t1-t0:.1f}s ({bps:.0f} B/s)')
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = f'{out_dir}/gen_{ts}_{n}.bin'
    with open(path, 'wb') as f:
        f.write(gen)
    print(f'Wrote {path}')
    _show_gen(gen)
    return gen

def main():
    parser = argparse.ArgumentParser(description='QiCube Vulkan PDE engine — continuous training')
    parser.add_argument('--test', action='store_true', help='single-window smoke test')
    parser.add_argument('--file', type=str, default=None,
                        help='byte file to ingest (default: auto-detect datasets/active/)')
    parser.add_argument('--max-bytes', type=int, default=0,
                        help='bytes to ingest per epoch (0 = all)')
    parser.add_argument('--epochs', type=int, default=1, metavar='N',
                        help='number of passes through the dataset (default 1)')
    parser.add_argument('--generate', type=int, default=0, metavar='N',
                        help='generate N bytes after training, then enter REPL')
    parser.add_argument('--gen-every', type=int, default=0, metavar='N',
                        help='generate 200 bytes every N bytes ingested during training (0 = off)')
    parser.add_argument('--temp', type=float, default=0.2, help='sampling temperature (0.0=argmax; Qi-flow best at 0.1-0.3)')
    parser.add_argument('--top-k', type=int, default=10, help='top-k sampling tokens (Qi-flow best at 10)')
    parser.add_argument('--lr', type=float, default=None, help='learning rate (overrides φ-principled λ derivation)')
    parser.add_argument('--lam', type=float, default=0.01, help='ε-recovery rate λ (φ-principled LR = λ when --lr not set)')
    parser.add_argument('--dt', type=float, default=0.2, help='PDE time step')
    parser.add_argument('--stride', type=int, default=1024, help='window stride')
    parser.add_argument('--stride-min', type=int, default=512, help='min adaptive stride')
    parser.add_argument('--stride-max', type=int, default=4096, help='max adaptive stride')
    parser.add_argument('--no-adaptive-stride', action='store_true',
                        help='disable Qi-based stride adaptation')
    parser.add_argument('--train-temp', type=float, default=0.1,
                        help='softmax temperature during training (0=argmax, 0.1=softened)')
    parser.add_argument('--alpha', type=float, default=0.1,
                        help='self-prediction coupling (0=off, 0.1=low-gain re-enable)')
    parser.add_argument('--rho-eps', type=float, default=0.95,
                        help='per-voxel IIR damping for ε² memory (0.95=heavy, 0.382=φ-scaled)')
    parser.add_argument('--mem-blend', type=float, default=0.05,
                        help='field_memory blend weight (0=off, 0.05=5%% persistent memory)')

    parser.add_argument('--save-every', type=int, default=0, metavar='N',
                        help='save checkpoint every N windows (0 = off)')
    parser.add_argument('--resume', type=str, default=None, metavar='PATH',
                        help='resume from checkpoint file')
    args = parser.parse_args()
    engine = VkQiCube(lam=args.lam, lr=args.lr, dt=args.dt, stride=args.stride,
                      stride_min=args.stride_min, stride_max=args.stride_max,
                      no_adaptive_stride=args.no_adaptive_stride,
                      alpha=args.alpha, train_temp=args.train_temp,
                      rho_eps=args.rho_eps, mem_blend=args.mem_blend)
    if args.resume:
        engine.load_checkpoint(args.resume)

    if args.test:
        data = bytes([i % 256 for i in range(5000)])
        qi = engine.ingest_window(data, 0)
        print(f'Single window: qi={qi:.4f}')
        return

    # Gather dataset files
    if args.file:
        files = [args.file]
    else:
        d = Path('datasets/active')
        if d.exists():
            files = sorted(str(f) for f in d.iterdir()
                           if f.is_file() and f.stat().st_size > 0)
        else:
            files = sorted(str(f) for f in Path('datasets').glob('*.txt')
                           if f.stat().st_size > 0)
    if not files:
        print('No dataset found. Use --file or place a file in datasets/active/.')
        return

    # ── Training epochs ──
    for epoch in range(args.epochs):
        print(f'\n{"="*60}')
        print(f'Epoch {epoch+1}/{args.epochs}')
        print(f'{"="*60}')
        for fpath in files:
            _ingest(engine, fpath, args.max_bytes,
                    gen_every=args.gen_every,
                    gen_temp=args.temp, gen_topk=args.top_k,
                    save_every=args.save_every)

    # ── Final generation ──
    if args.generate > 0:
        _generate(engine, args.generate, args.temp, args.top_k)

    # ── Interactive REPL ──
    import shlex
    print()
    print('Interactive mode — commands:')
    print('  gen N [temp] [topk]   generate N bytes')
    print('  ingest FILE [N]        ingest more data')
    print('  stats                  show engine stats')
    print('  exit / Ctrl+D          quit')
    print()
    while True:
        try:
            line = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = shlex.split(line)
        cmd = parts[0].lower()

        if cmd in ('exit', 'quit', 'q'):
            break

        elif cmd == 'gen':
            if len(parts) < 2:
                print('Usage: gen N [temp] [topk]')
                continue
            try:
                n = int(parts[1])
                temp = float(parts[2]) if len(parts) > 2 else args.temp
                topk = int(parts[3]) if len(parts) > 3 else args.top_k
            except ValueError:
                print('gen N [temp] [topk] — N int, temp float, topk int')
                continue
            print()
            _generate(engine, n, temp, topk)

        elif cmd == 'ingest':
            if len(parts) < 2:
                print('Usage: ingest FILE [N]')
                continue
            fpath = parts[1]
            maxb = int(parts[2]) if len(parts) > 2 else args.max_bytes
            if not Path(fpath).exists():
                print(f'File not found: {fpath}')
                continue
            _ingest(engine, fpath, maxb)

        elif cmd == 'stats':
            acc = engine.readout_correct / max(engine.readout_total, 1)
            print(f'  windows={engine.step_count}  qi_target={engine.qi_target:.4f}  '
                  f'breath={engine.breath_phase:.4f}')
            print(f'  readout_correct={engine.readout_correct}  readout_total={engine.readout_total}  '
                  f'acc={acc:.4f}')

        else:
            print(f'Unknown command: {cmd}')


if __name__ == '__main__':
    main()
