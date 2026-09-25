#include "models.h"
#include "llama-memory-recurrent.h"
#include "llama-kv-cache.h"

void llama_model_qwen35moe::load_arch_hparams(llama_model_loader & ml) {
    ml.get_key(LLM_KV_EXPERT_FEED_FORWARD_LENGTH,        hparams.n_ff_exp, false);
    ml.get_key(LLM_KV_EXPERT_SHARED_FEED_FORWARD_LENGTH, hparams.n_ff_shexp, false);
    ml.get_key(LLM_KV_ATTENTION_LAYERNORM_RMS_EPS,       hparams.f_norm_rms_eps);

    ml.get_key_or_arr(LLM_KV_ROPE_DIMENSION_SECTIONS,    hparams.rope_sections, 4, true);

    // Load linear attention (gated delta net) parameters
    ml.get_key(LLM_KV_SSM_CONV_KERNEL,    hparams.ssm_d_conv);
    ml.get_key(LLM_KV_SSM_INNER_SIZE,     hparams.ssm_d_inner);
    ml.get_key(LLM_KV_SSM_STATE_SIZE,     hparams.ssm_d_state);
    ml.get_key(LLM_KV_SSM_TIME_STEP_RANK, hparams.ssm_dt_rank);
    ml.get_key(LLM_KV_SSM_GROUP_COUNT,    hparams.ssm_n_group);

    // NextN/MTP (Qwen3.5/3.6): extra decoder block appended beyond the main stack
    ml.get_key(LLM_KV_NEXTN_PREDICT_LAYERS, hparams.n_layer_nextn, false);
    GGML_ASSERT(hparams.n_layer_nextn < hparams.n_layer_all && "n_layer_nextn must be < n_layer_impl");

    // Mark recurrent layers (linear attention layers). MTP layers are dense
    // attention-only and must be flagged non-recurrent.
    if (!ml.get_key_or_arr(LLM_KV_ATTENTION_RECURRENT_LAYERS, hparams.is_recr_impl, hparams.n_layer_all, false)) {
        uint32_t full_attn_interval = 4;
        ml.get_key(LLM_KV_FULL_ATTENTION_INTERVAL, full_attn_interval, false);
        for (uint32_t i = 0; i < hparams.n_layer_all; ++i) {
            hparams.is_recr_impl[i] = (i < hparams.n_layer()) && ((i + 1) % full_attn_interval != 0);
        }
    }

    switch (hparams.n_layer()) {
        case 40: type = LLM_TYPE_35B_A3B; break;
        case 48: type = LLM_TYPE_122B_A10B; break;
        case 60: type = LLM_TYPE_397B_A17B; break;
        default: type = LLM_TYPE_UNKNOWN;
    }
}

void llama_model_qwen35moe::load_arch_tensors(llama_model_loader & ml) {
    LLAMA_LOAD_LOCALS;

    const bool mtp_only = (hparams.n_layer_nextn > 0) && (ml.get_weight("blk.0.attn_norm.weight") == nullptr);
    const int trunk_flags = mtp_only ? TENSOR_NOT_REQUIRED : 0;
    int mtp_flags = !ml.load_mtp ? TENSOR_SKIP : 0;

    tok_embd = create_tensor(tn(LLM_TENSOR_TOKEN_EMBD, "weight"), { n_embd, n_vocab }, 0);

    // output
    output_norm = create_tensor(tn(LLM_TENSOR_OUTPUT_NORM, "weight"), { n_embd }, 0);
    output = create_tensor(tn(LLM_TENSOR_OUTPUT, "weight"), { n_embd, n_vocab }, TENSOR_NOT_REQUIRED);

    // if output is NULL, init from the input tok embed
    if (output == NULL) {
        output = create_tensor(tn(LLM_TENSOR_TOKEN_EMBD, "weight"), { n_embd, n_vocab }, TENSOR_DUPLICATED);
    }

    auto load_block_trunk = [&](int il, int flags) {
        auto & layer = layers[il];

        const int64_t n_ff_exp   = hparams.n_ff_exp ? hparams.n_ff_exp : n_ff / n_expert_used;
        const int64_t n_ff_shexp = hparams.n_ff_shexp ? hparams.n_ff_shexp : n_ff;

        // Calculate dimensions from hyperparameters
        const int64_t head_k_dim = hparams.ssm_d_state;
        const int64_t head_v_dim = hparams.ssm_d_state;
        const int64_t n_k_heads  = hparams.ssm_n_group;
        const int64_t n_v_heads  = hparams.ssm_dt_rank;
        const int64_t key_dim    = head_k_dim * n_k_heads;
        const int64_t value_dim  = head_v_dim * n_v_heads;
        const int64_t conv_dim   = key_dim * 2 + value_dim;

        layer.attn_norm      = create_tensor(tn(LLM_TENSOR_ATTN_NORM,      "weight", il), { n_embd }, flags);
        layer.attn_post_norm = create_tensor(tn(LLM_TENSOR_ATTN_POST_NORM, "weight", il), { n_embd }, flags);

        if (!hparams.is_recr(il)) {
            // Attention layers
            create_tensor_qkv(layer, il, n_embd, n_embd_head_k * n_head * 2, n_embd_k_gqa, n_embd_v_gqa, flags);
            layer.wo = create_tensor(tn(LLM_TENSOR_ATTN_OUT, "weight", il), { n_embd_head_k * n_head, n_embd }, flags);

            // Q/K normalization for attention layers
            layer.attn_q_norm = create_tensor(tn(LLM_TENSOR_ATTN_Q_NORM, "weight", il), { n_embd_head_k }, flags);
            layer.attn_k_norm = create_tensor(tn(LLM_TENSOR_ATTN_K_NORM, "weight", il), { n_embd_head_k }, flags);
        } else {
            // Linear attention (gated delta net) specific tensors
            // Create tensors with calculated dimensions
            layer.wqkv           = create_tensor(tn(LLM_TENSOR_ATTN_QKV,       "weight", il), { n_embd, key_dim * 2 + value_dim }, TENSOR_NOT_REQUIRED);
            layer.wqkv_gate      = create_tensor(tn(LLM_TENSOR_ATTN_GATE,      "weight", il), { n_embd, value_dim }, TENSOR_NOT_REQUIRED);
            layer.ssm_conv1d     = create_tensor(tn(LLM_TENSOR_SSM_CONV1D,     "weight", il), { hparams.ssm_d_conv, conv_dim }, flags);
            layer.ssm_dt         = create_tensor(tn(LLM_TENSOR_SSM_DT,         "bias",   il), { hparams.ssm_dt_rank }, flags);
            layer.ssm_a          = create_tensor(tn(LLM_TENSOR_SSM_A_NOSCAN,             il), { hparams.ssm_dt_rank }, flags);
            layer.ssm_beta       = create_tensor(tn(LLM_TENSOR_SSM_BETA,       "weight", il), { n_embd, n_v_heads }, flags);
            layer.ssm_alpha      = create_tensor(tn(LLM_TENSOR_SSM_ALPHA,      "weight", il), { n_embd, n_v_heads }, flags);
            layer.ssm_norm       = create_tensor(tn(LLM_TENSOR_SSM_NORM,       "weight", il), { head_v_dim }, flags);
            layer.ssm_out        = create_tensor(tn(LLM_TENSOR_SSM_OUT,        "weight", il), { value_dim, n_embd }, flags);
        }

        // Routed experts
        layer.ffn_gate_inp  = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP,  "weight", il), { n_embd, n_expert }, flags);
        layer.ffn_down_exps = create_tensor(tn(LLM_TENSOR_FFN_DOWN_EXPS, "weight", il), { n_ff_exp, n_embd, n_expert }, flags);
        create_tensor_gate_up_exps(layer, il, n_embd, n_ff_exp, n_expert, flags);

        // Shared experts
        layer.ffn_gate_inp_shexp = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP_SHEXP, "weight", il), { n_embd }, flags);
        layer.ffn_gate_shexp     = create_tensor(tn(LLM_TENSOR_FFN_GATE_SHEXP,     "weight", il), { n_embd, n_ff_shexp }, flags);
        layer.ffn_up_shexp       = create_tensor(tn(LLM_TENSOR_FFN_UP_SHEXP,       "weight", il), { n_embd, n_ff_shexp }, flags);
        layer.ffn_down_shexp     = create_tensor(tn(LLM_TENSOR_FFN_DOWN_SHEXP,     "weight", il), { n_ff_shexp, n_embd }, flags);
    };

    auto load_block_mtp = [&](int il) {
        auto & layer = layers[il];

        const int64_t n_ff_exp   = hparams.n_ff_exp ? hparams.n_ff_exp : n_ff / n_expert_used;
        const int64_t n_ff_shexp = hparams.n_ff_shexp ? hparams.n_ff_shexp : n_ff;

        // MTP block looks like a full-attention Qwen3.5 decoder block with MoE FFN.
        layer.attn_norm      = create_tensor(tn(LLM_TENSOR_ATTN_NORM,      "weight", il), { n_embd }, mtp_flags);
        layer.attn_post_norm = create_tensor(tn(LLM_TENSOR_ATTN_POST_NORM, "weight", il), { n_embd }, mtp_flags);

        create_tensor_qkv(layer, il, n_embd, n_embd_head_k * n_head * 2, n_embd_k_gqa, n_embd_v_gqa, mtp_flags);
        layer.wo          = create_tensor(tn(LLM_TENSOR_ATTN_OUT,    "weight", il), { n_embd_head_k * n_head, n_embd }, mtp_flags);
        layer.attn_q_norm = create_tensor(tn(LLM_TENSOR_ATTN_Q_NORM, "weight", il), { n_embd_head_k }, mtp_flags);
        layer.attn_k_norm = create_tensor(tn(LLM_TENSOR_ATTN_K_NORM, "weight", il), { n_embd_head_k }, mtp_flags);

        // Routed experts
        layer.ffn_gate_inp  = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP,  "weight", il), { n_embd, n_expert }, mtp_flags);
        layer.ffn_down_exps = create_tensor(tn(LLM_TENSOR_FFN_DOWN_EXPS, "weight", il), { n_ff_exp, n_embd, n_expert }, mtp_flags);
        create_tensor_gate_up_exps(layer, il, n_embd, n_ff_exp, n_expert, mtp_flags);

        // Shared experts
        layer.ffn_gate_inp_shexp = create_tensor(tn(LLM_TENSOR_FFN_GATE_INP_SHEXP, "weight", il), { n_embd }, mtp_flags);
        layer.ffn_gate_shexp     = create_tensor(tn(LLM_TENSOR_FFN_GATE_SHEXP,     "weight", il), { n_embd, n_ff_shexp }, mtp_flags);
        layer.ffn_up_shexp       = create_tensor(tn(LLM_TENSOR_FFN_UP_SHEXP,       "weight", il), { n_embd, n_ff_shexp }, mtp_flags);
        layer.ffn_down_shexp     = create_tensor(tn(LLM_TENSOR_FFN_DOWN_SHEXP,     "weight", il), { n_ff_shexp, n_embd }, mtp_flags);

        // NextN-specific tensors that define the MTP block.
        layer.nextn.eh_proj          = create_tensor(tn(LLM_TENSOR_NEXTN_EH_PROJ,          "weight", il), { 2 * n_embd, n_embd }, mtp_flags);
        layer.nextn.enorm            = create_tensor(tn(LLM_TENSOR_NEXTN_ENORM,            "weight", il), { n_embd },              mtp_flags);
        layer.nextn.hnorm            = create_tensor(tn(LLM_TENSOR_NEXTN_HNORM,            "weight", il), { n_embd },              mtp_flags);
        layer.nextn.embed_tokens     = create_tensor(tn(LLM_TENSOR_NEXTN_EMBED_TOKENS,     "weight", il), { n_embd, n_vocab },     mtp_flags|TENSOR_NOT_REQUIRED);
        layer.nextn.shared_head_head = create_tensor(tn(LLM_TENSOR_NEXTN_SHARED_HEAD_HEAD, "weight", il), { n_embd, n_vocab },     mtp_flags|TENSOR_NOT_REQUIRED);
        layer.nextn.shared_head_norm = create_tensor(tn(LLM_TENSOR_NEXTN_SHARED_HEAD_NORM, "weight", il), { n_embd },              mtp_flags|TENSOR_NOT_REQUIRED);
    };

    for (int i = 0; i < n_layer; ++i) {
        load_block_trunk(i, trunk_flags);
    }
    for (int i = n_layer; i < n_layer_all; ++i) {
        load_block_mtp(i);
    }
}


std::unique_ptr<llm_graph_context> llama_model_qwen35moe::build_arch_graph(const llm_graph_params & params) const {
    if (params.gtype == LLM_GRAPH_TYPE_DECODER_MTP) {
        return std::make_unique<graph_mtp>(*this, params);
    }
    return std::make_unique<graph>(*this, params);
}

llama_model_qwen35moe::graph::graph(const llama_model & model, const llm_graph_params & params) :
    llm_build_delta_net_base(params),
    model(model),
    qi_displacement(params.cassi_qi != nullptr ? params.cassi_qi->displacement_level : 0),
    qi_layer(params.cassi_qi != nullptr ? params.cassi_qi->layer_index : 0) {
    const int64_t n_embd_head = hparams.n_embd_head_v();

    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    if (params.gtype == LLM_GRAPH_TYPE_CASSI_SERVICE) {
        build_cassi_service(params);
        return;
    }

    int sections[4];
    std::copy(std::begin(hparams.rope_sections), std::begin(hparams.rope_sections) + 4, sections);

    ggml_tensor * cur;
    ggml_tensor * inpL;

    inpL = build_inp_embd(model.tok_embd);

    cb(inpL, "model.input_embed", -1);

    auto * inp = build_inp_mem_hybrid();

    ggml_tensor * inp_pos     = build_inp_pos();
    ggml_tensor * inp_out_ids = build_inp_out_ids();
    llm_graph_input_cassi_modal * qi_inp = nullptr;
    ggml_tensor * t_qi = nullptr;
    ggml_tensor * qi_correction = nullptr;
    ggml_tensor * qi_history_source = nullptr;
    auto qi_view_width = [&]() -> int64_t {
        const int64_t block_width = 2 * (int64_t) params.cassi_qi->wave_mode_count;
        return params.cassi_qi->row_width > 0
            ? std::min<int64_t>(params.cassi_qi->row_width, block_width)
            : (int64_t) hparams.n_embd;
    };
    auto ensure_qi_input = [&]() {
        GGML_ASSERT(params.cassi_qi != nullptr && params.cassi_qi->enabled);
        if (qi_inp != nullptr) {
            return;
        }
        const uint32_t state_mode_count = params.cassi_qi->mode_count;
        const uint32_t n_tokens = ubatch.n_tokens;
        const uint32_t n_seqs = std::max(1u, ubatch.n_seqs_unq);
        auto inp_qi = std::make_unique<llm_graph_input_cassi_modal>(
            static_cast<const llm_cassi_modal_config *>(params.cassi_qi), n_seqs);
        inp_qi->state = ggml_new_tensor_4d(ctx0, GGML_TYPE_F32,
                params.cassi_qi->state_stride, n_seqs, 1, 1);
        inp_qi->mode_params = ggml_new_tensor_4d(ctx0, GGML_TYPE_F32,
                state_mode_count, 1, 1, 1);
        inp_qi->seq_ids = ggml_new_tensor_1d(ctx0, GGML_TYPE_I32, n_tokens);
        ggml_set_input(inp_qi->state);
        ggml_set_input(inp_qi->mode_params);
        ggml_set_input(inp_qi->seq_ids);
        qi_inp = static_cast<llm_graph_input_cassi_modal *>(res->add_input(std::move(inp_qi)));
    };
    auto build_qi_state_history = [&]() -> ggml_tensor * {
        ensure_qi_input();
        const int64_t wave_mode_count = params.cassi_qi->wave_mode_count;
        const int64_t state_mode_count = params.cassi_qi->mode_count;
        ggml_tensor * state0 = ggml_view_3d(ctx0, qi_inp->state,
                2, wave_mode_count, qi_inp->state->ne[1],
                9 * sizeof(float), qi_inp->state->nb[1], 0);
        state0 = ggml_cont(ctx0, state0);
        ggml_tensor * rows = ggml_reshape_2d(
            ctx0, state0, 2 * wave_mode_count, qi_inp->state->ne[1]);
        rows = ggml_get_rows(ctx0, rows, qi_inp->seq_ids);
        if (rows->ne[0] != qi_view_width()) {
            rows = ggml_view_2d(ctx0, rows, qi_view_width(), rows->ne[1], rows->nb[1], 0);
        }
        return ggml_cont(ctx0, rows);
    };
    auto build_qi_correction = [&](ggml_tensor * source) -> ggml_tensor * {
        GGML_ASSERT(params.cassi_qi != nullptr && params.cassi_qi->enabled);
        ensure_qi_input();
        const uint32_t state_mode_count = params.cassi_qi->mode_count;
        const uint32_t wave_mode_count = params.cassi_qi->wave_mode_count;
        const uint32_t n_tokens = ubatch.n_tokens;
        const uint32_t n_seqs = std::max(1u, ubatch.n_seqs_unq);
        GGML_ASSERT(2 * wave_mode_count >= (uint32_t) hparams.n_embd);
        GGML_ASSERT(wave_mode_count <= state_mode_count);

        ggml_tensor * sense = ggml_reshape_2d(ctx0, source, hparams.n_embd, n_tokens);
        sense = ggml_rms_norm(ctx0, sense, hparams.f_norm_rms_eps);
        sense = ggml_scale(ctx0, sense, 1.0f / std::sqrt((float) hparams.n_embd));
        if (params.cassi_qi->memory_fill && n_seqs == 1) {
            const int64_t mem_modes = (int64_t) hparams.n_embd / 2;
            GGML_ASSERT(hparams.n_embd % 2 == 0 &&
                        (int64_t) wave_mode_count + mem_modes <= (int64_t) state_mode_count);
            ggml_tensor * mem = ggml_view_2d(ctx0, qi_inp->state, 2, mem_modes,
                    (size_t) 9 * sizeof(float), (size_t) wave_mode_count * 9 * sizeof(float));
            mem = ggml_cont(ctx0, mem);
            mem = ggml_reshape_1d(ctx0, mem, (int64_t) hparams.n_embd);
            mem = ggml_scale(ctx0, mem, 1.0f / std::sqrt((float) hparams.n_embd));
            ggml_tensor * wide = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, (int64_t) hparams.n_embd, n_tokens);
            sense = ggml_add(ctx0, sense, ggml_repeat(ctx0, mem, wide));
        }
        const int64_t sense_width = 2 * (int64_t) wave_mode_count;
        const int64_t fill_width = sense_width - (int64_t) hparams.n_embd;
        if (fill_width > 0) {
            if (!params.cassi_qi->fill_modes) {
                sense = ggml_pad(ctx0, sense, fill_width, 0, 0, 0);
            } else {
                const int64_t pair_width = (int64_t) hparams.n_embd - 1;
                ggml_tensor * low_in = ggml_cont(ctx0, ggml_view_2d(ctx0, sense,
                        pair_width, n_tokens, sense->nb[1], 0));
                ggml_tensor * high_in = ggml_cont(ctx0, ggml_view_2d(ctx0, sense,
                        pair_width, n_tokens, sense->nb[1], sizeof(float)));
                ggml_tensor * envelope = ggml_scale(ctx0, ggml_add(ctx0, low_in, high_in), 0.5f);
                ggml_tensor * edges = ggml_scale(ctx0, ggml_sub(ctx0, high_in, low_in), 0.5f);
                envelope = ggml_pad(ctx0, envelope, 1, 0, 0, 0);
                edges = ggml_pad(ctx0, edges, 1, 0, 0, 0);
                ggml_tensor * flipped = ggml_scale(ctx0, sense, -1.0f);
                ggml_tensor * block = ggml_concat(ctx0, envelope, edges, 0);
                block = ggml_concat(ctx0, block, flipped, 0);
                const int64_t block_width = 2 * (int64_t) hparams.n_embd;
                if (fill_width > block_width) {
                    const int64_t passes = (fill_width + block_width - 1) / block_width;
                    ggml_tensor * target = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32,
                            block_width * passes, n_tokens);
                    block = ggml_repeat(ctx0, block, target);
                }
                ggml_tensor * tail = ggml_cont(ctx0, ggml_view_2d(ctx0, block, fill_width, n_tokens,
                        block->nb[1], 0));
                sense = ggml_concat(ctx0, sense, tail, 0);
            }
            sense = ggml_cont(ctx0, sense);
        }
        cb(sense, "cassi_qi_sense_l2_padded", qi_layer);
        t_qi = ggml_cassi_qi_field_step(
            ctx0, sense, qi_inp->state, qi_inp->mode_params, qi_inp->seq_ids,
            params.cassi_qi->scale_count,
            params.cassi_qi->phi,
            params.cassi_qi->dt,
            params.cassi_qi->coupling,
            params.cassi_qi->damping_min,
            params.cassi_qi->damping_max,
            params.cassi_qi->epsilon_tau,
            params.cassi_qi->scale_ratio,
            params.cassi_qi->energy_floor,
            params.cassi_qi->read_floor,
            params.cassi_qi->scale_read_taper,
            params.cassi_qi->read_absolute,
            params.cassi_qi->memory_fill,
            params.cassi_qi->unwritten_latch,
            params.cassi_qi->steps);
        cb(t_qi, "cassi_qi_field_step", qi_layer);
        res->t_cassi_qi = t_qi;
        ggml_build_forward_expand(gf, t_qi);
        return ggml_view_2d(
            ctx0, t_qi, qi_view_width(), n_tokens,
            (size_t) 2 * wave_mode_count * sizeof(float), 0);
    };
    auto build_qi_attention_history = [&](llm_graph_input_attn_kv * attn,
            ggml_tensor * correction, ggml_tensor * positions, int il)
            -> std::pair<ggml_tensor *, ggml_tensor *> {
        GGML_ASSERT(attn != nullptr && correction != nullptr && positions != nullptr);

        ggml_tensor * cache_k = attn->mctx->get_k(ctx0, il);
        ggml_tensor * cache_v = attn->mctx->get_v(ctx0, il);
        const int64_t n_tokens = ubatch.n_tokens;
        const int64_t n_stream = cache_k->ne[3];
        GGML_ASSERT(n_stream > 0 && n_tokens % n_stream == 0);

        const int64_t hidden_width = hparams.n_embd;
        const int64_t source_width = correction->ne[0];
        GGML_ASSERT(hidden_width > 0 && source_width > 0);

        ggml_tensor * history_input = nullptr;
        const int64_t chunks = (source_width + hidden_width - 1) / hidden_width;
        for (int64_t chunk = 0; chunk < chunks; ++chunk) {
            const int64_t offset = chunk * hidden_width;
            const int64_t piece_width = std::min(hidden_width, source_width - offset);
            ggml_tensor * piece = ggml_cont(ctx0, ggml_view_2d(ctx0, correction,
                    piece_width, n_tokens, correction->nb[1], (size_t) offset * sizeof(float)));
            if (piece_width < hidden_width) {
                piece = ggml_pad(ctx0, piece, hidden_width - piece_width, 0, 0, 0);
            }
            history_input = history_input == nullptr
                ? piece
                : ggml_add(ctx0, history_input, piece);
        }
        if (chunks > 1) {
            history_input = ggml_scale(ctx0, history_input, 1.0f / std::sqrt((float) chunks));
        }
        history_input = ggml_rms_norm(ctx0, history_input, hparams.f_norm_rms_eps);
        cb(history_input, "cassi_qi_attention_history_input", il);

        const int64_t head_dim = hparams.n_embd_head_k();
        const int64_t n_head_kv = hparams.n_head_kv(il);
        const int64_t history_tokens = n_tokens / n_stream;

        ggml_tensor * history_k = build_lora_mm(model.layers[il].wk, history_input, model.layers[il].wk_s);
        history_k = ggml_reshape_3d(ctx0, history_k, head_dim, n_head_kv, n_tokens);
        history_k = build_norm(history_k, model.layers[il].attn_k_norm, nullptr, LLM_NORM_RMS, il);
        history_k = ggml_rope_multi(
                ctx0, history_k, positions, nullptr,
                n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
                ext_factor, attn_factor, beta_fast, beta_slow);
        if (attn->self_k_rot) {
            history_k = llama_mul_mat_hadamard(ctx0, history_k, attn->self_k_rot);
        }
        history_k = ggml_reshape_4d(ctx0, history_k, head_dim, n_head_kv, history_tokens, n_stream);
        history_k = ggml_cont(ctx0, history_k);
        if (history_k->type != cache_k->type) {
            history_k = ggml_cast(ctx0, history_k, cache_k->type);
        }
        history_k = ggml_cont(ctx0, history_k);

        ggml_tensor * history_v = build_lora_mm(model.layers[il].wv, history_input, model.layers[il].wv_s);
        history_v = ggml_reshape_3d(ctx0, history_v, head_dim, n_head_kv, n_tokens);
        if (attn->self_v_rot) {
            history_v = llama_mul_mat_hadamard(ctx0, history_v, attn->self_v_rot);
        }
        history_v = ggml_reshape_4d(ctx0, history_v, head_dim, n_head_kv, history_tokens, n_stream);
        if (cache_v->nb[1] > cache_v->nb[2]) {
            history_v = ggml_cont(ctx0, ggml_permute(ctx0, history_v, 2, 1, 0, 3));
        } else {
            history_v = ggml_cont(ctx0, history_v);
        }
        if (history_v->type != cache_v->type) {
            history_v = ggml_cast(ctx0, history_v, cache_v->type);
        }
        history_v = ggml_cont(ctx0, history_v);

        return { history_k, history_v };
    };
    if (params.cassi_qi != nullptr && params.cassi_qi->enabled &&
            params.cassi_qi->attention_history) {
        qi_history_source = build_qi_state_history();
    }

    // MTP/NextN layers are loaded as extra decoder blocks but not executed in the main pass.
    for (int il = 0; il < n_layer; ++il) {
        if (params.cassi_qi != nullptr && params.cassi_qi->enabled &&
                (params.cassi_qi->intervention == 1 || cparams.cassi_qi_substitute > 0.0f ||
                 cparams.cassi_qi_modulate || params.cassi_qi->attention_history) &&
                (uint32_t) il == qi_layer) {
            ggml_tensor * correction = qi_correction != nullptr ? qi_correction : build_qi_correction(inpL);
            // The seam consumes this same readout where the suppressed state write is
            // filled, so the field steps once per decode and keeps one channel per layer.
            res->t_cassi_qi_flux = correction;
            if (params.cassi_qi->intervention == 1 && params.cassi_qi->injection_scale > 0.0f) {
                // The injection adds to the n_embd-wide residual, so it reads the first n_embd
                // channels of the readout and materializes them.
                ggml_tensor * inject = ggml_cont(ctx0, ggml_view_2d(ctx0, correction,
                    hparams.n_embd, ubatch.n_tokens, correction->nb[1], 0));
                correction = ggml_scale(ctx0, inject, params.cassi_qi->injection_scale);
                inpL = ggml_add(ctx0, inpL, correction);
                cb(inpL, "cassi_qi_mid_trunk_injected", il);
            }
        }
        res->t_layer_inp[il] = inpL;

        ggml_tensor * inpSA = inpL;

        cur = build_norm(inpL, model.layers[il].attn_norm, nullptr, LLM_NORM_RMS, il);
        cb(cur, "attn_norm", il);

        ggml_build_forward_expand(gf, cur);

        // Determine layer type and build appropriate attention mechanism
        if (hparams.is_recr(il)) {
            const auto * recurrent_candidate = params.cassi_graph_site_candidate;
            if (recurrent_candidate != nullptr &&
                    recurrent_candidate->kind == llm_graph_site_candidate_kind::RECURRENT &&
                    recurrent_candidate->layer == il &&
                    graph_site_candidate_eligible(*recurrent_candidate, ubatch)) {
                cur = build_layer_attn_linear_candidate(
                    inp->get_recr(), cur, il, recurrent_candidate);
            } else {
                cur = build_layer_attn_linear(inp->get_recr(), cur, il);
            }
        } else {
            // Full attention layer
            ggml_tensor * history_k = nullptr;
            ggml_tensor * history_v = nullptr;
            if (params.cassi_qi != nullptr && params.cassi_qi->enabled &&
                    params.cassi_qi->attention_history) {
                ggml_tensor * history_source = qi_correction != nullptr
                    ? qi_correction : qi_history_source;
                GGML_ASSERT(history_source != nullptr);
                const auto history = build_qi_attention_history(
                    inp->get_attn(), history_source, inp_pos, il);
                history_k = history.first;
                history_v = history.second;
            }
            const auto * attn_candidate = params.cassi_graph_site_candidate;
            if (attn_candidate != nullptr &&
                    attn_candidate->kind == llm_graph_site_candidate_kind::ATTENTION_MEMORY &&
                    attn_candidate->layer == il && history_k == nullptr && history_v == nullptr &&
                    graph_site_candidate_eligible(*attn_candidate, ubatch)) {
                cur = build_layer_attn_candidate(
                    inp->get_attn(), cur, inp_pos, sections, il, history_k, history_v, attn_candidate);
            } else {
                cur = build_layer_attn(
                    inp->get_attn(), cur, inp_pos, sections, il, history_k, history_v);
            }
        }

        if (il == n_layer - 1 && inp_out_ids && cparams.embeddings_nextn_masked) {
            cur   = ggml_get_rows(ctx0, cur, inp_out_ids);
            inpSA = ggml_get_rows(ctx0, inpSA, inp_out_ids);
        }

        // Residual connection
        cur = ggml_add(ctx0, cur, inpSA);
        cb(cur, "attn_residual", il);

        // Save the tensor before post-attention norm for residual connection
        ggml_tensor * ffn_residual = cur;

        // Post-attention norm
        ggml_tensor * attn_post_norm = build_norm(cur, model.layers[il].attn_post_norm, nullptr, LLM_NORM_RMS, il);
        cb(attn_post_norm, "attn_post_norm", il);

        const auto * site_candidate = params.cassi_graph_site_candidate;
        cur = build_layer_ffn_candidate(attn_post_norm, il, site_candidate);
        cb(cur, "ffn_out", il);
        // Residual connection for FFN - add to the tensor from before post_attention_layernorm
        cur = ggml_add(ctx0, cur, ffn_residual);
        cb(cur, "post_moe", il);

        cur = build_cvec(cur, il);
        cb(cur, "l_out", il);

        // Input for next layer
        inpL = cur;
    }
    cur = inpL;
    if (params.cassi_qi != nullptr && params.cassi_qi->enabled &&
            params.cassi_qi->intervention == 0) {
        const uint32_t wave_mode_count = params.cassi_qi->wave_mode_count;
        const uint32_t n_tokens = ubatch.n_tokens;
        const uint32_t n_seqs = std::max(1u, ubatch.n_seqs_unq);
        GGML_ASSERT(qi_layer < (uint32_t) n_layer);
        GGML_ASSERT(res->t_layer_inp[qi_layer] != nullptr);
        ggml_tensor * correction = qi_correction != nullptr
            ? qi_correction : build_qi_correction(res->t_layer_inp[qi_layer]);
        if (params.cassi_qi->displacement_level >= 6) {
            const size_t flux_bytes = (size_t) 2 * wave_mode_count * n_tokens * sizeof(float);
            ggml_tensor * state_after = ggml_view_2d(
                ctx0, t_qi, params.cassi_qi->state_stride, n_seqs,
                (size_t) params.cassi_qi->state_stride * sizeof(float), flux_bytes);
            cur = ggml_cassi_qi_emit(
                ctx0, state_after, qi_inp->seq_ids, (int64_t) model.vocab.n_tokens(),
                wave_mode_count, params.cassi_qi->scale_count, params.cassi_qi->phi,
                params.cassi_qi->scale_ratio, params.cassi_qi->read_floor);
            if (inp_out_ids != nullptr) {
                cur = ggml_get_rows(ctx0, cur, inp_out_ids);
                correction = ggml_get_rows(ctx0, correction, inp_out_ids);
            }
            // The embedding contract is n_embd wide, so the logits mode keeps that width.
            res->t_embd = ggml_view_2d(ctx0, correction, hparams.n_embd, correction->ne[1],
                correction->nb[1], 0);
            cb(cur, "cassi_qi_field_logits", -1);
            res->t_logits = cur;
            ggml_build_forward_expand(gf, cur);
            return;
        }
        cur = build_norm(cur, model.output_norm, nullptr, LLM_NORM_RMS, -1);
        cb(cur, "h_nextn", -1);
        res->t_h_nextn = cur;
        if (!cparams.embeddings_nextn_masked && inp_out_ids) {
            cur = ggml_get_rows(ctx0, cur, inp_out_ids);
        }
        cb(cur, "result_norm", -1);
        if (cur->ne[1] != correction->ne[1] && inp_out_ids != nullptr) {
            correction = ggml_get_rows(ctx0, correction, inp_out_ids);
        }
        if (params.cassi_qi->injection_scale > 0.0f) {
            // The seam adds to the n_embd-wide normed state, so it reads the first n_embd
            // channels of the readout and materializes them.
            ggml_tensor * inject = ggml_cont(ctx0, ggml_view_2d(ctx0, correction,
                hparams.n_embd, correction->ne[1], correction->nb[1], 0));
            correction = ggml_scale(ctx0, inject, params.cassi_qi->injection_scale);
            cur = ggml_add(ctx0, cur, correction);
        }
        cb(cur, "cassi_qi_injected", -1);
        res->t_embd = cur;
        cur = build_lora_mm(model.output, cur, model.output_s);
        cb(cur, "result_output", -1);
        res->t_logits = cur;
        ggml_build_forward_expand(gf, cur);
        return;
    }

    // post-norm hidden state feeds both the LM head and the MTP seed below
    cur = build_norm(cur, model.output_norm, nullptr, LLM_NORM_RMS, -1);

    cb(cur, "h_nextn", -1);
    res->t_h_nextn = cur;

    if (!cparams.embeddings_nextn_masked && inp_out_ids) {
        cur = ggml_get_rows(ctx0, cur, inp_out_ids);
    }

    cb(cur, "result_norm", -1);
    res->t_embd = cur;

    // LM head
    cur = build_head_candidate(cur, params.cassi_graph_site_candidate);

    cb(cur, "result_output", -1);
    res->t_logits = cur;

    ggml_build_forward_expand(gf, cur);
}

// Cassi apprenticeship service graph for the Qwen35 MoE trunk.
//
// One graph pass serves one homogeneous stage (EMBED / ATTENTION / FFN / HEAD)
// for a set of rows. The legacy single-row transaction (service.n_rows == 1) is
// the degenerate case of the same fused construction: the shared F32 handoff is
// [stage_width, 1], every projection below is ggml_mul_mat(A, B) with B
// [in, n_rows] and every output is [out_width, n_rows] in the identical row
// order (column r of each tensor belongs to row r end-to-end). A multi-row
// transaction (n_rows > 1) therefore reads one shared F32 input
// [stage_width, n_rows] and fuses all of the model's matrix work for the stage
// into that single pass instead of running one graph per sequence.
//
// Per-row isolation:
//   * row r is token batch_tokens[r] at position batch_pos[r] in sequence
//     batch_seq_ids[r]; the ubatch carries one token per row with
//     ubatch.seq_id[r][0] == batch_seq_ids[r], so the KV cache mask built from
//     the ubatch lets row r attend only to cells of its own sequence up to
//     batch_pos[r], and the recurrent (GDN) conv/state gathers and writes are
//     indexed by the same per-token sequence ids.
//   * rows of the same sequence cannot be fused (the second row depends on the
//     first row's state write), so a multi-row transaction is refused when two
//     rows share a sequence id.
void llama_model_qwen35moe::graph::build_cassi_service(const llm_graph_params & params) {
    if (params.cassi_service == nullptr) {
        throw std::runtime_error("invalid Cassi apprenticeship service request");
    }
    const llm_cassi_service_config & service = *params.cassi_service;
    if (service.kind == LLAMA_CASSI_TEXT) {
        throw std::runtime_error("TEXT is not a native service");
    }
    if (service.n_rows < 1) {
        throw std::runtime_error("invalid Cassi apprenticeship service request");
    }
    const uint32_t n_rows = service.n_rows;

    const auto * site_candidate = params.cassi_graph_site_candidate;

    if (n_rows == 1) {
        if (ubatch.n_tokens != 1 || ubatch.n_seq_tokens != 1 ||
                ubatch.n_seqs != 1 || ubatch.n_seqs_unq != 1) {
            throw std::runtime_error("invalid Cassi apprenticeship service request");
        }
        // A one-row candidate is admitted only at its exact service target below.
    } else {
        // homogeneous rows: one token per row, one row per unique sequence,
        // all rows named by the config.
        if (ubatch.n_tokens != n_rows || ubatch.n_seq_tokens != 1 ||
                ubatch.n_seqs != n_rows || ubatch.n_seqs_unq != n_rows ||
                ubatch.pos == nullptr || ubatch.n_seq_id == nullptr ||
                ubatch.seq_id == nullptr || ubatch.n_pos < 1) {
            throw std::runtime_error("invalid Cassi apprenticeship service request");
        }
        if (service.batch_pos == nullptr || service.batch_seq_ids == nullptr) {
            throw std::runtime_error("invalid Cassi apprenticeship service request");
        }
        for (uint32_t r = 0; r < n_rows; ++r) {
            if (ubatch.n_seq_id[r] != 1 || ubatch.seq_id[r] == nullptr ||
                    ubatch.seq_id[r][0] != service.batch_seq_ids[r] ||
                    ubatch.pos[r] != service.batch_pos[r] ||
                    service.batch_pos[r] < 0 || service.batch_seq_ids[r] < 0) {
                throw std::runtime_error("invalid Cassi apprenticeship service request");
            }
            for (uint32_t s = 0; s < r; ++s) {
                if (ubatch.seq_id[r][0] == ubatch.seq_id[s][0]) {
                    throw std::runtime_error("invalid Cassi apprenticeship service request");
                }
            }
        }
    }
    if (site_candidate != nullptr) {
        const bool exact_service_site =
            n_rows == 1 && service.layer == site_candidate->layer &&
            graph_site_candidate_eligible(*site_candidate, ubatch) &&
            ((service.kind == LLAMA_CASSI_FFN &&
                    site_candidate->kind == llm_graph_site_candidate_kind::EXPERTS) ||
             (service.kind == LLAMA_CASSI_ATTENTION &&
                    site_candidate->kind == llm_graph_site_candidate_kind::RECURRENT &&
                    service.layer >= 0 && hparams.is_recr(service.layer)));
        if (!exact_service_site) {
            throw std::runtime_error("unsupported graph-site candidate mixed with Cassi apprenticeship service");
        }
    }


    ggml_tensor * cur = nullptr;
    if (service.kind == LLAMA_CASSI_EMBED) {
        if (service.layer != -1 || service.input != nullptr) {
            throw std::runtime_error("invalid embedding service request");
        }
        if (n_rows > 1) {
            if (service.batch_tokens == nullptr || ubatch.token == nullptr) {
                throw std::runtime_error("invalid embedding service request");
            }
            for (uint32_t r = 0; r < n_rows; ++r) {
                if (ubatch.token[r] != service.batch_tokens[r] ||
                        ubatch.token[r] < 0 ||
                        (uint64_t) ubatch.token[r] >= (uint64_t) model.vocab.n_tokens()) {
                    throw std::runtime_error("invalid embedding service request");
                }
            }
        }
        // One shared embedding pass: the token rows gather into
        // [n_embd, n_rows] from a single token input, fused as GEMM RHS n_rows
        // through the stage's consumers below (when this stage is embedded
        // into a larger transaction) and returned as the stage output.
        cur = build_inp_embd(model.tok_embd);
        cb(cur, "cassi_service_embed_output", -1);
    } else {
        if (service.stage_width != 0 && service.stage_width != (uint32_t) hparams.n_embd) {
            throw std::runtime_error("invalid Cassi apprenticeship service input");
        }
        if (service.input == nullptr || service.input->type != GGML_TYPE_F32 ||
                !ggml_is_contiguous(service.input) ||
                service.input->ne[0] != hparams.n_embd ||
                service.input->ne[1] != (int64_t) n_rows ||
                service.input->ne[2] != 1 || service.input->ne[3] != 1) {
            throw std::runtime_error("invalid Cassi apprenticeship service input");
        }
        auto input = std::make_unique<llm_graph_input_cassi_service>(&service);
        input->value = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, hparams.n_embd, n_rows);
        ggml_set_input(input->value);
        cur = static_cast<llm_graph_input_cassi_service *>(res->add_input(std::move(input)))->value;
        cb(cur, "cassi_service_input", service.layer);

        if (service.kind == LLAMA_CASSI_ATTENTION) {
            if (service.layer < 0 || service.layer >= (int32_t) n_layer || params.mctx == nullptr) {
                throw std::runtime_error("invalid attention service request");
            }
            const int il = service.layer;
            auto * memory_input = build_inp_mem_hybrid();
            cur = build_norm(cur, model.layers[il].attn_norm, nullptr, LLM_NORM_RMS, il);
            cb(cur, "cassi_service_attn_norm", il);
            if (hparams.is_recr(il)) {
                // Gated delta net service: conv/state gathers and stores are
                // indexed by the per-token sequence ids of the ubatch, so each
                // row reads and writes only its own sequence's GDN/conv state.
                cur = build_layer_attn_linear_candidate(
                    memory_input->get_recr(), cur, il, site_candidate);
            } else {
                int sections[4];
                std::copy(std::begin(hparams.rope_sections), std::begin(hparams.rope_sections) + 4, sections);
                ggml_tensor * inp_pos = build_inp_pos();
                cur = build_layer_attn(memory_input->get_attn(), cur, inp_pos, sections, il, nullptr, nullptr);
            }
            cb(cur, "cassi_service_attention_delta", il);
        } else if (service.kind == LLAMA_CASSI_FFN) {
            if (service.layer < 0 || service.layer >= (int32_t) n_layer) {
                throw std::runtime_error("invalid FFN service request");
            }
            const int il = service.layer;
            cur = build_norm(cur, model.layers[il].attn_post_norm, nullptr, LLM_NORM_RMS, il);
            cb(cur, "cassi_service_ffn_norm", il);
            cur = build_layer_ffn_candidate(cur, il, site_candidate);
            cb(cur, "cassi_service_ffn_delta", il);
        } else if (service.kind == LLAMA_CASSI_HEAD) {
            if (service.layer != -1) {
                throw std::runtime_error("invalid head service request");
            }
            cur = build_norm(cur, model.output_norm, nullptr, LLM_NORM_RMS, -1);
            cb(cur, "cassi_service_head_norm", -1);
            cur = build_lora_mm(model.output, cur, model.output_s);
            cb(cur, "cassi_service_head_logits", -1);
        } else {
            throw std::runtime_error("invalid Cassi apprenticeship service kind");
        }
    }
    res->t_cassi_service = cur;
    cb(cur, "cassi_service_output", service.layer);
    ggml_build_forward_expand(gf, cur);
}

std::pair<ggml_tensor *, ggml_tensor *> llama_model_qwen35moe::graph::build_qkvz(
                ggml_tensor * input,
                        int   il) {
    const int64_t n_seqs       = ubatch.n_seqs;
    const int64_t n_seq_tokens = ubatch.n_seq_tokens;

    ggml_tensor * qkv_mixed = build_lora_mm(model.layers[il].wqkv, input, model.layers[il].wqkv_s);
    qkv_mixed = ggml_reshape_3d(ctx0, qkv_mixed, qkv_mixed->ne[0], n_seq_tokens, n_seqs);
    cb(qkv_mixed, "linear_attn_qkv_mixed", il);

    ggml_tensor * z = build_lora_mm(model.layers[il].wqkv_gate, input, model.layers[il].wqkv_gate_s);
    cb(z, "z", il);

    return { qkv_mixed, z };
}

ggml_tensor * llama_model_qwen35moe::graph::build_norm_gated(
        ggml_tensor * input,
        ggml_tensor * weights,
        ggml_tensor * gate,
        int           layer) {
    ggml_tensor * normalized = build_norm(input, weights, nullptr, LLM_NORM_RMS, layer);
    ggml_tensor * gated_silu = ggml_silu(ctx0, gate);

    return ggml_mul(ctx0, normalized, gated_silu);
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn(
        llm_graph_input_attn_kv * inp,
        ggml_tensor *             cur,
        ggml_tensor *             inp_pos,
        int *                     sections,
        int                       il,
        ggml_tensor *              cassi_history_k,
        ggml_tensor *              cassi_history_v) {
    const int64_t n_embd_head = hparams.n_embd_head_v();
    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    // Order: joint QG projection, QG split, Q norm, KV projection, K norm, RoPE, attention

    // Qwen3Next uses a single Q projection that outputs query + gate
    ggml_tensor * Qcur_full = build_lora_mm(model.layers[il].wq, cur, model.layers[il].wq_s); // [ (n_embd_head * 2) * n_head, n_tokens ]
    cb(Qcur_full, "Qcur_full", il);

    ggml_tensor * Qcur = ggml_view_3d(ctx0, Qcur_full, n_embd_head, n_head, n_tokens,
        ggml_element_size(Qcur_full) * n_embd_head * 2,
        ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head, 0);
    cb(Qcur, "Qcur_reshaped", il);

    // Apply Q normalization
    Qcur = build_norm(Qcur, model.layers[il].attn_q_norm, nullptr, LLM_NORM_RMS, il);
    cb(Qcur, "Qcur_normed", il);

    ggml_tensor * Kcur = build_lora_mm(model.layers[il].wk, cur, model.layers[il].wk_s);
    cb(Kcur, "Kcur", il);

    ggml_tensor * Vcur = build_lora_mm(model.layers[il].wv, cur, model.layers[il].wv_s);
    cb(Vcur, "Vcur", il);

    // Apply K normalization
    Kcur = ggml_reshape_3d(ctx0, Kcur, n_embd_head, n_head_kv, n_tokens);
    Kcur = build_norm(Kcur, model.layers[il].attn_k_norm, nullptr, LLM_NORM_RMS, il);
    cb(Kcur, "Kcur_normed", il);

    ggml_tensor * gate = ggml_view_3d(ctx0, Qcur_full, n_embd_head, n_head, n_tokens,
        ggml_element_size(Qcur_full) * n_embd_head * 2,
        ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
        ggml_element_size(Qcur_full) * n_embd_head);
    gate = ggml_cont_2d(ctx0, gate, n_embd_head * n_head, n_tokens);
    cb(gate, "gate_reshaped", il);

    Vcur = ggml_reshape_3d(ctx0, Vcur, n_embd_head, n_head_kv, n_tokens);

    // Apply IMRoPE
    Qcur = ggml_rope_multi(
            ctx0, Qcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow
            );

    Kcur = ggml_rope_multi(
            ctx0, Kcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow
            );

    cb(Qcur, "Qcur", il);
    cb(Kcur, "Kcur", il);
    cb(Vcur, "Vcur", il);

    // Attention computation
    const float kq_scale = hparams.f_attention_scale == 0.0f ? 1.0f / sqrtf(float(n_embd_head)) : hparams.f_attention_scale;

    cur = build_attn(inp,
                nullptr, nullptr, nullptr,
                Qcur, Kcur, Vcur, nullptr, nullptr, nullptr, kq_scale, il,
                cassi_history_k, cassi_history_v);
    cb(cur, "attn_pregate", il);

    ggml_tensor * gate_sigmoid = ggml_sigmoid(ctx0, gate);
    cb(gate_sigmoid, "gate_sigmoid", il);

    cur = ggml_mul(ctx0, cur, gate_sigmoid);
    cb(cur, "attn_gated", il);

    cur = build_lora_mm(model.layers[il].wo, cur, model.layers[il].wo_s);
    cb(cur, "attn_output", il);

    return cur;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn_candidate(
        llm_graph_input_attn_kv * inp,
        ggml_tensor *             cur,
        ggml_tensor *             inp_pos,
        int *                     sections,
        int                       il,
        ggml_tensor *              cassi_history_k,
        ggml_tensor *              cassi_history_v,
        const llm_graph_site_candidate_config * candidate) {
    if (candidate == nullptr ||
            candidate->kind != llm_graph_site_candidate_kind::ATTENTION_MEMORY ||
            candidate->layer != il ||
            cassi_history_k != nullptr || cassi_history_v != nullptr ||
            !graph_site_candidate_eligible(*candidate, ubatch)) {
        return build_layer_attn(inp, cur, inp_pos, sections, il, cassi_history_k, cassi_history_v);
    }

    const int64_t n_embd_head = hparams.n_embd_head_v();
    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    const uint32_t kv_width = candidate->attn_kv_heads * candidate->attn_kv_head_width;
    const int64_t expected_output_width = (int64_t) hparams.n_embd + 2 * (int64_t) kv_width;

    const bool site_layout_supported =
        cur->type == GGML_TYPE_F32 &&
        ggml_is_contiguous(cur) &&
        cur->ne[0] == hparams.n_embd &&
        cur->ne[1] == 1 &&
        cur->ne[2] == 1 &&
        cur->ne[3] == 1 &&
        candidate->attn_kv_heads == (uint32_t) n_head_kv &&
        candidate->attn_kv_head_width == (uint32_t) n_embd_head &&
        graph_site_affine_layout_supported(*candidate, hparams.n_embd, expected_output_width);
    if (!site_layout_supported) {
        llm_graph_site_candidate_result receipt;
        receipt.attempted = true;
        receipt.admitted = false;
        receipt.owner_generation = candidate->owner_generation;
        receipt.refusal = "attention_site_layout_unsupported";
        res->set_graph_site_candidate_result(std::move(receipt));
        return build_layer_attn(inp, cur, inp_pos, sections, il, cassi_history_k, cassi_history_v);
    }

    ggml_tensor * successor = build_graph_site_affine(ctx0, res, cur, *candidate);
    cb(successor, "attention_successor", il);

    const size_t element_size = ggml_element_size(successor);
    ggml_tensor * hidden_successor = ggml_view_2d(ctx0, successor, hparams.n_embd, 1, successor->nb[1], 0);
    cb(hidden_successor, "attention_hidden_out", il);

    const size_t kv_offset = (size_t) hparams.n_embd * element_size;
    ggml_tensor * k_flat = ggml_view_2d(ctx0, successor, kv_width, 1, successor->nb[1], kv_offset);
    ggml_tensor * v_flat = ggml_view_2d(ctx0, successor, kv_width, 1, successor->nb[1],
        kv_offset + (size_t) kv_width * element_size);

    ggml_tensor * k_cur = ggml_reshape_3d(ctx0, ggml_cont(ctx0, k_flat), n_embd_head, n_head_kv, 1);
    ggml_tensor * v_cur = ggml_reshape_3d(ctx0, ggml_cont(ctx0, v_flat), n_embd_head, n_head_kv, 1);
    cb(k_cur, "attention_kv_k_in", il);
    cb(v_cur, "attention_kv_v_in", il);

    const auto * mctx_cur = inp->mctx;
    const auto & k_idxs = inp->get_k_idxs();
    const auto & v_idxs = inp->get_v_idxs();
    ggml_build_forward_expand(gf, mctx_cur->cpy_k(ctx0, k_cur, k_idxs, il));
    ggml_build_forward_expand(gf, mctx_cur->cpy_v(ctx0, v_cur, v_idxs, il));

    llm_graph_site_candidate_result receipt;
    receipt.attempted = true;
    receipt.admitted = true;
    receipt.owner_generation = candidate->owner_generation;
    receipt.input_tensor = cur;
    receipt.output_tensor = successor;
    // Skipped native operators: Q/K/V projection+norm, RoPE+attention, gate, wo.
    receipt.operators_omitted = 4;
    const auto & layer = model.layers[il];
    const auto add_omitted_weight = [&](const ggml_tensor * weight) {
        if (weight != nullptr) {
            ++receipt.weights_omitted;
            receipt.weight_bytes_omitted += ggml_nbytes(weight);
        }
    };
    add_omitted_weight(layer.wq);
    add_omitted_weight(layer.wk);
    add_omitted_weight(layer.wv);
    add_omitted_weight(layer.wo);
    add_omitted_weight(layer.attn_q_norm);
    add_omitted_weight(layer.attn_k_norm);
    res->set_graph_site_candidate_result(std::move(receipt));

    return hidden_successor;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn_linear(
        llm_graph_input_rs * inp,
        ggml_tensor *        cur,
        int                  il) {
    const auto * mctx_cur = inp->mctx;

    const int64_t d_inner      = hparams.ssm_d_inner;
    const int64_t n_seqs       = ubatch.n_seqs;
    const int64_t head_k_dim   = hparams.ssm_d_state;
    const int64_t num_k_heads  = hparams.ssm_n_group;
    const int64_t num_v_heads  = hparams.ssm_dt_rank;
    const int64_t head_v_dim   = d_inner / num_v_heads;
    const int64_t n_seq_tokens = ubatch.n_seq_tokens;

    GGML_ASSERT(n_seqs != 0);
    GGML_ASSERT(ubatch.equal_seqs());
    GGML_ASSERT(ubatch.n_tokens == n_seq_tokens * n_seqs);

    // Input projections
    auto qkvz = build_qkvz(cur, il);
    ggml_tensor * qkv_mixed = qkvz.first;
    ggml_tensor * z         = qkvz.second;

    ggml_tensor * beta = build_lora_mm(model.layers[il].ssm_beta, cur, model.layers[il].ssm_beta_s);
    beta = ggml_reshape_4d(ctx0, beta, 1, num_v_heads, n_seq_tokens, n_seqs);
    cb(beta, "beta", il);

    beta = ggml_sigmoid(ctx0, beta);
    cb(beta, "beta_sigmoid", il);

    ggml_tensor * alpha = build_lora_mm(model.layers[il].ssm_alpha, cur, model.layers[il].ssm_alpha_s);
    alpha = ggml_reshape_3d(ctx0, alpha, num_v_heads, n_seq_tokens, n_seqs);
    cb(alpha, "alpha", il);

    ggml_tensor * alpha_biased   = ggml_add(ctx0, alpha, model.layers[il].ssm_dt);
    ggml_tensor * alpha_softplus = ggml_softplus(ctx0, alpha_biased);
    cb(alpha_softplus, "a_softplus", il);

    ggml_tensor * gate = ggml_mul(ctx0, alpha_softplus, model.layers[il].ssm_a);  // -A_log.exp() * softplus
    cb(gate, "gate", il);

    gate = ggml_reshape_4d(ctx0, gate, 1, num_v_heads, n_seq_tokens, n_seqs);

    ggml_tensor * conv_states_all = mctx_cur->get_r_l(il);
    ggml_tensor * ssm_states_all  = mctx_cur->get_s_l(il);

    ggml_tensor * conv_kernel      = model.layers[il].ssm_conv1d;
    const int64_t conv_kernel_size = conv_kernel->ne[0];
    const int64_t conv_channels    = d_inner + 2 * hparams.ssm_n_group * hparams.ssm_d_state;

    ggml_tensor * conv_input = build_conv_state(inp, conv_states_all, qkv_mixed, conv_kernel_size, conv_channels, il);

    ggml_tensor * state = build_rs(inp, ssm_states_all, hparams.n_embd_s(), n_seqs);
    state = ggml_reshape_4d(ctx0, state, head_v_dim, head_v_dim, num_v_heads, n_seqs);
    cb(state, "state_predelta", il);

    ggml_tensor * conv_output_proper = ggml_ssm_conv(ctx0, conv_input, conv_kernel);
    cb(conv_output_proper, "conv_output_raw", il);

    ggml_tensor * conv_output_silu = ggml_silu(ctx0, conv_output_proper);
    cb(conv_output_silu, "conv_output_silu", il);

    ggml_tensor * conv_qkv_mix = conv_output_silu;

    // Calculate the total conv dimension
    int64_t qkv_dim = head_k_dim * num_k_heads * 2 + head_v_dim * num_v_heads;
    int64_t nb1_qkv = ggml_row_size(conv_qkv_mix->type, qkv_dim);

    // Extract the convolved Q, K, V from conv_output
    ggml_tensor * q_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_k_dim, num_k_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_k_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            0);

    ggml_tensor * k_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_k_dim, num_k_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_k_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            head_k_dim * num_k_heads * ggml_element_size(conv_qkv_mix));

    ggml_tensor * v_conv = ggml_view_4d(ctx0, conv_qkv_mix, head_v_dim, num_v_heads, n_seq_tokens, n_seqs,
            ggml_row_size(conv_qkv_mix->type, head_v_dim),
            nb1_qkv,
            nb1_qkv * n_seq_tokens,
            ggml_row_size(conv_qkv_mix->type, 2 * head_k_dim * num_k_heads));

    cb(q_conv, "q_conv", il);
    cb(k_conv, "k_conv", il);
    cb(v_conv, "v_conv", il);

    const float eps_norm = hparams.f_norm_rms_eps;

    q_conv = ggml_l2_norm(ctx0, q_conv, eps_norm);
    k_conv = ggml_l2_norm(ctx0, k_conv, eps_norm);

    //q_conv = ggml_cont_4d(ctx0, q_conv, head_k_dim, num_k_heads, n_seq_tokens, n_seqs);
    //k_conv = ggml_cont_4d(ctx0, k_conv, head_k_dim, num_k_heads, n_seq_tokens, n_seqs);
    //v_conv = ggml_cont_4d(ctx0, v_conv, head_v_dim, num_v_heads, n_seq_tokens, n_seqs);

    // if head keys and value keys are different, repeat to force tensors into matching shapes
    // note: need explicit repeat only if we are not using the fused GDN.
    if (num_k_heads != num_v_heads && (!cparams.fused_gdn_ar || !cparams.fused_gdn_ch)) {
        GGML_ASSERT(num_v_heads % num_k_heads == 0);
        q_conv = ggml_repeat_4d(ctx0, q_conv, head_k_dim, num_v_heads, n_seq_tokens, n_seqs);
        k_conv = ggml_repeat_4d(ctx0, k_conv, head_k_dim, num_v_heads, n_seq_tokens, n_seqs);
    }

    cb(q_conv, "q_conv_predelta", il);
    cb(k_conv, "k_conv_predelta", il);
    cb(v_conv, "v_conv_predelta", il);

    ggml_tensor * output = build_recurrent_attn(inp, ssm_states_all, q_conv, k_conv, v_conv, gate, beta, state, il);

    // z: [head_dim, n_heads, n_tokens, n_seqs] -> [n_heads * n_tokens * n_seqs, head_dim]
    ggml_tensor * z_2d = ggml_reshape_4d(ctx0, z, head_v_dim, num_v_heads, n_seq_tokens, n_seqs);

    // Apply gated normalization: self.norm(core_attn_out, z)
    ggml_tensor * attn_out_norm = build_norm_gated(output, model.layers[il].ssm_norm, z_2d, il);

    // Final reshape: [head_dim, n_heads, n_tokens, n_seqs] -> [n_tokens, n_seqs, n_heads * head_dim]
    ggml_tensor * final_output = ggml_reshape_3d(ctx0, attn_out_norm, head_v_dim * num_v_heads, n_seq_tokens, n_seqs);
    cb(final_output, "final_output", il);

    // Output projection
    cur = build_lora_mm(model.layers[il].ssm_out, final_output, model.layers[il].ssm_out_s);
    cb(cur, "linear_attn_out", il);

    // Reshape back to original dimensions
    cur = ggml_reshape_2d(ctx0, cur, n_embd, n_seq_tokens * n_seqs);

    return cur;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_attn_linear_candidate(
        llm_graph_input_rs * inp,
        ggml_tensor * cur,
        int il,
        const llm_graph_site_candidate_config * candidate) {
    // Shared exact RECURRENT site builder; a refusal receipt is already recorded
    // there, and the native linear-attention layer stays the fallback.
    ggml_tensor * site_cur = build_layer_attn_linear_site_candidate(
        model.layers[il], inp, cur, il, candidate);
    return site_cur != nullptr ? site_cur : build_layer_attn_linear(inp, cur, il);
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_ffn(ggml_tensor * cur, const int il) {
    // Check if this is an MoE layer
    GGML_ASSERT(model.layers[il].ffn_gate_inp != nullptr);

    ggml_tensor * moe_out =
        build_moe_ffn(cur,
            model.layers[il].ffn_gate_inp,
            model.layers[il].ffn_up_exps,
            model.layers[il].ffn_gate_exps,
            model.layers[il].ffn_down_exps,
            nullptr,
            n_expert, n_expert_used,
            LLM_FFN_SILU, true,
            hparams.expert_weights_scale,
            LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX, il,
            nullptr, model.layers[il].ffn_gate_up_exps,
            model.layers[il].ffn_up_exps_s,
            model.layers[il].ffn_gate_exps_s,
            model.layers[il].ffn_down_exps_s);
    cb(moe_out, "ffn_moe_out", il);

    // Add shared experts if present - following Qwen3Next reference implementation
    if (model.layers[il].ffn_up_shexp != nullptr) {
        ggml_tensor * ffn_shexp =
            build_ffn(cur,
                model.layers[il].ffn_up_shexp, NULL, model.layers[il].ffn_up_shexp_s,
                model.layers[il].ffn_gate_shexp, NULL, model.layers[il].ffn_gate_shexp_s,
                model.layers[il].ffn_down_shexp, NULL, model.layers[il].ffn_down_shexp_s,
                NULL,
                LLM_FFN_SILU, LLM_FFN_PAR, il);
        cb(ffn_shexp, "ffn_shexp", il);

        // Apply shared expert gating as in the reference implementation
        // The shared expert has its own gate that is sigmoided
        // Note: ffn_gate_inp_shexp is the shared expert gate (outputs 1 value per token)
        ggml_tensor * shared_gate = build_lora_mm(model.layers[il].ffn_gate_inp_shexp, cur);
        cb(shared_gate, "shared_expert_gate", il);

        // Apply sigmoid to the gate
        shared_gate = ggml_sigmoid(ctx0, shared_gate);
        cb(shared_gate, "shared_expert_gate_sigmoid", il);


        // Apply the gate to the shared expert output
        ffn_shexp = ggml_mul(ctx0, ffn_shexp, shared_gate);
        cb(ffn_shexp, "ffn_shexp_gated", il);

        cur = ggml_add(ctx0, moe_out, ffn_shexp);
        cb(cur, "ffn_out", il);
    } else {
        cur = moe_out;
    }

    return cur;
}

ggml_tensor * llama_model_qwen35moe::graph::build_layer_ffn_candidate(
        ggml_tensor * cur,
        int il,
        const llm_graph_site_candidate_config * candidate) {
    if (candidate == nullptr ||
            candidate->kind != llm_graph_site_candidate_kind::EXPERTS ||
            candidate->layer != il ||
            !graph_site_candidate_eligible(*candidate, ubatch)) {
        return build_layer_ffn(cur, il);
    }

    const bool site_layout_supported =
        cur->type == GGML_TYPE_F32 &&
        ggml_is_contiguous(cur) &&
        cur->ne[0] == hparams.n_embd &&
        cur->ne[1] == 1 &&
        cur->ne[2] == 1 &&
        cur->ne[3] == 1 &&
        graph_site_affine_layout_supported(*candidate, hparams.n_embd, hparams.n_embd);
    bool expected_route_supported =
        candidate->expected_expert_ids.size() == (size_t) n_expert_used;
    for (size_t i = 0; expected_route_supported &&
            i < candidate->expected_expert_ids.size(); ++i) {
        const int32_t expert_id = candidate->expected_expert_ids[i];
        if (expert_id < 0 || expert_id >= n_expert) {
            expected_route_supported = false;
            break;
        }
        for (size_t j = 0; j < i; ++j) {
            if (candidate->expected_expert_ids[j] == expert_id) {
                expected_route_supported = false;
                break;
            }
        }
    }
    const bool route_layout_supported =
        expected_route_supported && hparams.n_expert_groups <= 1 &&
        n_expert > 0 && n_expert_used > 0 && n_expert_used <= n_expert;
    if (!site_layout_supported || !route_layout_supported) {
        llm_graph_site_candidate_result receipt;
        receipt.attempted = true;
        receipt.admitted = false;
        receipt.owner_generation = candidate->owner_generation;
        receipt.refusal = !site_layout_supported
            ? "expert_site_layout_unsupported"
            : "expert_route_layout_unsupported";
        res->set_graph_site_candidate_result(std::move(receipt));
        return build_layer_ffn(cur, il);
    }

    // Preserve native router observation and expose its exact top-k ids so the
    // owner can validate the candidate route before acknowledgment.
    ggml_tensor * router_logits =
        build_lora_mm(model.layers[il].ffn_gate_inp, cur);
    ggml_tensor * router_probs = ggml_soft_max(ctx0, router_logits);
    ggml_tensor * expert_ids = ggml_argsort_top_k(ctx0, router_probs, n_expert_used);
    cb(expert_ids, "ffn_moe_topk", il);
    ggml_build_forward_expand(gf, expert_ids);

    ggml_tensor * successor = build_graph_site_affine(ctx0, res, cur, *candidate);
    llm_graph_site_candidate_result receipt;
    receipt.attempted = true;
    receipt.admitted = true;
    receipt.owner_generation = candidate->owner_generation;
    receipt.expert_ids_tensor = expert_ids;
    receipt.input_tensor = cur;
    receipt.output_tensor = successor;
    // These are the two native MoE branches that were not built.
    receipt.operators_omitted = 2;
    const auto & layer = model.layers[il];
    const auto add_omitted_weight = [&](const ggml_tensor * weight) {
        if (weight != nullptr) {
            ++receipt.weights_omitted;
            receipt.weight_bytes_omitted += ggml_nbytes(weight);
        }
    };
    if (layer.ffn_gate_up_exps != nullptr) {
        add_omitted_weight(layer.ffn_gate_up_exps);
    } else {
        add_omitted_weight(layer.ffn_gate_exps);
        add_omitted_weight(layer.ffn_up_exps);
    }
    add_omitted_weight(layer.ffn_down_exps);
    if (layer.ffn_up_shexp != nullptr) {
        add_omitted_weight(layer.ffn_gate_shexp);
        add_omitted_weight(layer.ffn_up_shexp);
        add_omitted_weight(layer.ffn_down_shexp);
        add_omitted_weight(layer.ffn_gate_inp_shexp);
    }
    res->set_graph_site_candidate_result(std::move(receipt));
    return successor;
}

ggml_tensor * llama_model_qwen35moe::graph::build_head_candidate(
        ggml_tensor * cur,
        const llm_graph_site_candidate_config * candidate) {
    if (candidate == nullptr ||
            candidate->kind != llm_graph_site_candidate_kind::EXECUTION_CHOICE ||
            candidate->layer != -1 ||
            !graph_site_candidate_eligible(*candidate, ubatch)) {
        return build_lora_mm(model.output, cur, model.output_s);
    }

    const int64_t vocab_size = model.vocab.n_tokens();
    const bool site_layout_supported =
        cur->type == GGML_TYPE_F32 &&
        ggml_is_contiguous(cur) &&
        cur->ne[0] == hparams.n_embd &&
        cur->ne[1] == 1 &&
        cur->ne[2] == 1 &&
        cur->ne[3] == 1 &&
        graph_site_affine_layout_supported(*candidate, hparams.n_embd, vocab_size);
    if (!site_layout_supported) {
        llm_graph_site_candidate_result receipt;
        receipt.attempted = true;
        receipt.admitted = false;
        receipt.owner_generation = candidate->owner_generation;
        receipt.refusal = "execution_choice_site_layout_unsupported";
        res->set_graph_site_candidate_result(std::move(receipt));
        return build_lora_mm(model.output, cur, model.output_s);
    }

    ggml_tensor * successor = build_graph_site_affine(ctx0, res, cur, *candidate);
    cb(successor, "logits", -1);

    llm_graph_site_candidate_result receipt;
    receipt.attempted = true;
    receipt.admitted = true;
    receipt.owner_generation = candidate->owner_generation;
    receipt.input_tensor = cur;
    receipt.output_tensor = successor;
    // Skipped native operator: the LM-head matmul itself.
    receipt.operators_omitted = 1;
    if (model.output != nullptr) {
        ++receipt.weights_omitted;
        receipt.weight_bytes_omitted += ggml_nbytes(model.output);
    }
    if (model.output_s != nullptr) {
        ++receipt.weights_omitted;
        receipt.weight_bytes_omitted += ggml_nbytes(model.output_s);
    }
    res->set_graph_site_candidate_result(std::move(receipt));

    return successor;
}

// LLM_GRAPH_TYPE_DECODER_MTP draft head for Qwen3.5/3.6 MoE
llama_model_qwen35moe::graph_mtp::graph_mtp(const llama_model & model, const llm_graph_params & params)
    : llm_graph_context(params) {
    GGML_ASSERT(hparams.n_layer_nextn > 0 && "QWEN35MOE MTP requires n_layer_nextn > 0");
    GGML_ASSERT(hparams.n_layer_nextn == 1 && "QWEN35MOE MTP currently only supports a single MTP block");

    const int64_t n_embd_head = hparams.n_embd_head_v();
    GGML_ASSERT(n_embd_head == hparams.n_embd_head_k());

    const int il = hparams.n_layer();
    const auto & layer = model.layers[il];

    GGML_ASSERT(layer.nextn.eh_proj    && "MTP block missing nextn.eh_proj");
    GGML_ASSERT(layer.nextn.enorm      && "MTP block missing nextn.enorm");
    GGML_ASSERT(layer.nextn.hnorm      && "MTP block missing nextn.hnorm");
    GGML_ASSERT(layer.ffn_gate_inp     && "MTP block missing ffn_gate_inp");

    int sections[4];
    std::copy(std::begin(hparams.rope_sections), std::begin(hparams.rope_sections) + 4, sections);

    // TODO: extract in a common llm_graph_context::build_inp_embd_h()
    auto inp = std::make_unique<llm_graph_input_embd_h>(hparams.n_embd);

    inp->tokens = ggml_new_tensor_1d(ctx0, GGML_TYPE_I32, n_tokens);
    ggml_set_input(inp->tokens);

    inp->embd = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, hparams.n_embd_inp(), n_tokens);
    ggml_set_input(inp->embd);

    // TODO: make static using `ggml_build_forward_select()`
    //       see llm_graph_context::build_inp_embd() for reference
    ggml_tensor * tok_embd;
    if (ubatch.token) {
        ggml_tensor * tok_embd_w = layer.nextn.embed_tokens ? layer.nextn.embed_tokens : model.tok_embd;

        tok_embd = ggml_get_rows(ctx0, tok_embd_w, inp->tokens);
    } else {
        tok_embd = inp->embd;
    }
    cb(tok_embd, "mtp_tok_embd", il);

    inp->h = ggml_new_tensor_2d(ctx0, GGML_TYPE_F32, hparams.n_embd, n_tokens);
    ggml_set_input(inp->h);
    ggml_set_name(inp->h, "mtp_h_input");

    ggml_tensor * h_embd = inp->h;

    res->add_input(std::move(inp));

    ggml_tensor * inp_pos     = build_inp_pos();
    ggml_tensor * inp_out_ids = build_inp_out_ids();

    auto * inp_attn = build_attn_inp_kv();

    ggml_tensor * h_norm = build_norm(h_embd, layer.nextn.hnorm, nullptr, LLM_NORM_RMS, il);
    cb(h_norm, "mtp_hnorm", il);

    ggml_tensor * e_norm = build_norm(tok_embd, layer.nextn.enorm, nullptr, LLM_NORM_RMS, il);
    cb(e_norm, "mtp_enorm", il);

    ggml_tensor * concat = ggml_concat(ctx0, e_norm, h_norm, /*dim=*/ 0);
    cb(concat, "mtp_concat", il);

    ggml_tensor * cur = build_lora_mm(layer.nextn.eh_proj, concat, layer.nextn.eh_proj_s);
    cb(cur, "mtp_eh_proj", il);

    ggml_tensor * inpSA = cur;

    cur = build_norm(cur, layer.attn_norm, nullptr, LLM_NORM_RMS, il);
    cb(cur, "mtp_attn_norm", il);

    ggml_tensor * Qcur_full = build_lora_mm(layer.wq, cur, layer.wq_s);
    cb(Qcur_full, "mtp_Qcur_full", il);

    ggml_tensor * Qcur = ggml_view_3d(ctx0, Qcur_full,
            n_embd_head, n_head, n_tokens,
            ggml_element_size(Qcur_full) * n_embd_head * 2,
            ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
            0);
    Qcur = build_norm(Qcur, layer.attn_q_norm, nullptr, LLM_NORM_RMS, il);
    cb(Qcur, "mtp_Qcur_normed", il);

    ggml_tensor * gate = ggml_view_3d(ctx0, Qcur_full,
            n_embd_head, n_head, n_tokens,
            ggml_element_size(Qcur_full) * n_embd_head * 2,
            ggml_element_size(Qcur_full) * n_embd_head * 2 * n_head,
            ggml_element_size(Qcur_full) * n_embd_head);
    gate = ggml_cont_2d(ctx0, gate, n_embd_head * n_head, n_tokens);
    cb(gate, "mtp_gate", il);

    ggml_tensor * Kcur = build_lora_mm(layer.wk, cur, layer.wk_s);
    Kcur = ggml_reshape_3d(ctx0, Kcur, n_embd_head, n_head_kv, n_tokens);
    Kcur = build_norm(Kcur, layer.attn_k_norm, nullptr, LLM_NORM_RMS, il);
    cb(Kcur, "mtp_Kcur_normed", il);

    ggml_tensor * Vcur = build_lora_mm(layer.wv, cur, layer.wv_s);
    Vcur = ggml_reshape_3d(ctx0, Vcur, n_embd_head, n_head_kv, n_tokens);
    cb(Vcur, "mtp_Vcur", il);

    Qcur = ggml_rope_multi(ctx0, Qcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow);
    Kcur = ggml_rope_multi(ctx0, Kcur, inp_pos, nullptr,
            n_rot, sections, rope_type, n_ctx_orig, freq_base, freq_scale,
            ext_factor, attn_factor, beta_fast, beta_slow);

    const float kq_scale = hparams.f_attention_scale == 0.0f
            ? 1.0f / sqrtf(float(n_embd_head)) : hparams.f_attention_scale;

    cur = build_attn(inp_attn,
            nullptr, nullptr, nullptr,
            Qcur, Kcur, Vcur, nullptr, nullptr, nullptr, kq_scale, il);
    cb(cur, "mtp_attn_pregate", il);

    cur = ggml_mul(ctx0, cur, ggml_sigmoid(ctx0, gate));
    cur = build_lora_mm(layer.wo, cur, layer.wo_s);
    cb(cur, "mtp_attn_out", il);

    cur = ggml_add(ctx0, cur, inpSA);
    cb(cur, "mtp_attn_residual", il);

    ggml_tensor * ffn_residual = cur;
    cur = build_norm(cur, layer.attn_post_norm, nullptr, LLM_NORM_RMS, il);
    cb(cur, "mtp_attn_post_norm", il);

    // MoE FFN — routed experts plus gated shared expert (mirrors qwen35moe).
    ggml_tensor * moe_out =
        build_moe_ffn(cur,
            layer.ffn_gate_inp,
            layer.ffn_up_exps,
            layer.ffn_gate_exps,
            layer.ffn_down_exps,
            nullptr,
            n_expert, n_expert_used,
            LLM_FFN_SILU, true,
            hparams.expert_weights_scale,
            LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX, il,
            nullptr, layer.ffn_gate_up_exps,
            layer.ffn_up_exps_s,
            layer.ffn_gate_exps_s,
            layer.ffn_down_exps_s);
    cb(moe_out, "mtp_ffn_moe_out", il);

    if (layer.ffn_up_shexp != nullptr) {
        ggml_tensor * ffn_shexp =
            build_ffn(cur,
                layer.ffn_up_shexp,   nullptr, layer.ffn_up_shexp_s,
                layer.ffn_gate_shexp, nullptr, layer.ffn_gate_shexp_s,
                layer.ffn_down_shexp, nullptr, layer.ffn_down_shexp_s,
                nullptr,
                LLM_FFN_SILU, LLM_FFN_PAR, il);
        cb(ffn_shexp, "mtp_ffn_shexp", il);

        ggml_tensor * shared_gate = build_lora_mm(layer.ffn_gate_inp_shexp, cur);
        shared_gate = ggml_sigmoid(ctx0, shared_gate);
        cb(shared_gate, "mtp_shared_expert_gate_sigmoid", il);

        ffn_shexp = ggml_mul(ctx0, ffn_shexp, shared_gate);
        cb(ffn_shexp, "mtp_ffn_shexp_gated", il);

        cur = ggml_add(ctx0, moe_out, ffn_shexp);
    } else {
        cur = moe_out;
    }
    cb(cur, "mtp_ffn_out", il);

    cur = ggml_add(ctx0, cur, ffn_residual);
    cb(cur, "mtp_post_ffn", il);

    ggml_tensor * head_norm_w = layer.nextn.shared_head_norm
            ? layer.nextn.shared_head_norm
            : model.output_norm;
    GGML_ASSERT(head_norm_w && "QWEN35MOE MTP: missing both nextn.shared_head_norm and output_norm");
    cur = build_norm(cur, head_norm_w, nullptr, LLM_NORM_RMS, -1);

    cb(cur, "h_nextn", -1);
    res->t_h_nextn= cur;

    cur = ggml_get_rows(ctx0, cur, inp_out_ids);
    cb(cur, "mtp_shared_head_norm", -1);

    ggml_tensor * head_w = layer.nextn.shared_head_head ? layer.nextn.shared_head_head : model.output;
    ggml_tensor * head_s = layer.nextn.shared_head_head ? layer.nextn.shared_head_head_s : model.output_s;
    GGML_ASSERT(head_w && "QWEN35MOE MTP: missing LM head (nextn.shared_head_head or model.output)");
    cur = build_lora_mm(head_w, cur, head_s);
    cb(cur, "result_output", -1);

    res->t_logits = cur;
    ggml_build_forward_expand(gf, cur);
}
