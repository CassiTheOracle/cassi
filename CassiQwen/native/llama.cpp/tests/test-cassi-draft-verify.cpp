// Draft-verify (speculative decoding verifier seam) ABI proof against a real
// Qwen3.5 GGUF.
//
// usage: test-cassi-draft-verify MODEL cpu|gpu
//
// This test is CLI opt-in and never becomes part of the default test suite.
// It exercises llama_cassi_verify_draft / llama_cassi_verify_commit /
// llama_cassi_verify_discard against a live llama_cassi_context created in
// LLAMA_CASSI_EXACT_PIPELINE mode with n_ubatch and n_rs_seq sized for the
// draft window, proving:
//
//   1. a partial-accept draft (matches for j tokens then diverges under a
//      greedy target) reports accepted_count == j and output tokens equal to
//      an independently, sequentially decoded reference; after commit the
//      checkpoint bytes equal a freshly-init'd comparison session that
//      decoded the same accepted-plus-correction sequence one token at a
//      time;
//   2. discard after verify restores checkpoint bytes identical to the
//      predecessor and leaves the session usable;
//   3. a full-accept draft yields the bonus token and matches the same
//      sequential reference;
//   4. misuse (double commit, wrong receipt hash, an undersized non-verifier
//      context) is refused with typed errors and leaves session state
//      unaffected.

#include "common.h"
#include "llama-cassi.h"
#include "llama.h"

#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;
using session_ptr = std::unique_ptr<llama_cassi_context, decltype(&llama_cassi_free)>;

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

llama_cassi_sampler_params greedy_sampler() {
    llama_cassi_sampler_params sampler{};
    sampler.mode = LLAMA_CASSI_SAMPLER_GREEDY;
    sampler.temperature = 1.0f;
    sampler.top_k = 0;
    sampler.draw = 0.0;
    return sampler;
}

session_ptr make_session(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params) {
    session_ptr session(llama_cassi_init(model, context_params, cassi_params), llama_cassi_free);
    require(session != nullptr, std::string("session initialization failed: ") + llama_cassi_last_error(nullptr));
    return session;
}

// Sequentially decode `count` tokens through the ordinary begin/next/accept
// loop (deterministic greedy sampler) and return them in order.
std::vector<llama_token> greedy_sequence(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params,
        const std::vector<llama_token> & prompt,
        size_t count) {
    session_ptr session = make_session(model, context_params, cassi_params);
    require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), static_cast<int32_t>(count) + 1) == 0,
        std::string("reference begin failed: ") + llama_cassi_last_error(session.get()));
    std::vector<llama_token> tokens;
    tokens.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        llama_cassi_token token{};
        const llama_cassi_status status = llama_cassi_next(session.get(), &token);
        require(status == LLAMA_CASSI_TOKEN || status == LLAMA_CASSI_DONE,
            std::string("reference next failed: ") + llama_cassi_last_error(session.get()));
        tokens.push_back(token.token);
        require(llama_cassi_accept(session.get(), token.token) == 0,
            std::string("reference accept failed: ") + llama_cassi_last_error(session.get()));
        if (status == LLAMA_CASSI_DONE) {
            break;
        }
    }
    require(tokens.size() == count, "reference sequence ended before reaching the requested length");
    return tokens;
}

std::vector<uint8_t> checkpoint_bytes(llama_cassi_context * session) {
    const size_t size = llama_cassi_state_size(session);
    require(size > 0, std::string("checkpoint size query failed: ") + llama_cassi_last_error(session));
    std::vector<uint8_t> bytes(size);
    require(llama_cassi_state_get(session, bytes.data(), bytes.size()) == bytes.size(),
        std::string("checkpoint export failed: ") + llama_cassi_last_error(session));
    return bytes;
}

// Case (1) + partial vector for case (3): builds a K-token draft against the
// pending token, verifies the receipt against the independently computed
// greedy reference, commits, and compares post-commit checkpoint bytes
// against a freshly-init'd session that reached the same logical prefix by
// ordinary sequential decode.
void test_partial_accept(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params,
        const std::vector<llama_token> & prompt,
        int32_t vocab_size) {
    const std::vector<llama_token> teacher = greedy_sequence(model, context_params, cassi_params, prompt, 5);

    session_ptr session = make_session(model, context_params, cassi_params);
    require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
        std::string("partial-accept begin failed: ") + llama_cassi_last_error(session.get()));
    llama_cassi_token pending{};
    require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
        std::string("partial-accept pending next failed: ") + llama_cassi_last_error(session.get()));
    require(pending.token == teacher[0], "pending token diverged from the greedy reference");

    const llama_token wrong = static_cast<llama_token>((teacher[3] + 1) % vocab_size);
    require(wrong != teacher[3], "constructed divergent draft token collided with the reference");
    const llama_token draft_tokens[3] = { teacher[1], teacher[2], wrong };
    const double proposal_probabilities[3] = { 1.0, 1.0, 1.0 };
    const llama_cassi_sampler_params target_samplers[4] = {
        greedy_sampler(), greedy_sampler(), greedy_sampler(), greedy_sampler()
    };

    llama_cassi_draft_verify_request request{};
    request.draft_tokens = draft_tokens;
    request.proposal_probabilities = proposal_probabilities;
    request.draft_count = 3;
    request.target_samplers = target_samplers;
    request.target_sampler_count = 4;

    llama_cassi_draft_verify_receipt receipt{};
    require(llama_cassi_verify_draft(session.get(), &request, &receipt) == 0,
        std::string("verify_draft failed: ") + llama_cassi_last_error(session.get()));
    require(receipt.accepted_count == 2, "partial accept did not stop at the divergent draft token");
    require(receipt.rejected, "partial accept receipt did not report a rejection");
    require(!receipt.bonus, "partial accept receipt incorrectly reported a bonus token");
    require(receipt.output_count == 3, "partial accept receipt output count is wrong");
    require(receipt.output_tokens[0] == teacher[1] && receipt.output_tokens[1] == teacher[2] &&
            receipt.output_tokens[2] == teacher[3],
        "partial accept output tokens diverged from the sequential greedy reference");

    require(llama_cassi_verify_commit(session.get(), receipt.receipt_sha256) == 0,
        std::string("verify_commit failed: ") + llama_cassi_last_error(session.get()));

    const std::vector<llama_token> comparator_prefix(teacher.begin(), teacher.begin() + 4);
    session_ptr comparator = make_session(model, context_params, cassi_params);
    require(llama_cassi_begin(comparator.get(), prompt.data(), prompt.size(), 16) == 0,
        std::string("comparator begin failed: ") + llama_cassi_last_error(comparator.get()));
    for (const llama_token token : comparator_prefix) {
        llama_cassi_token next_token{};
        require(llama_cassi_next(comparator.get(), &next_token) == LLAMA_CASSI_TOKEN,
            std::string("comparator next failed: ") + llama_cassi_last_error(comparator.get()));
        require(next_token.token == token, "comparator sequential decode diverged from the reference");
        require(llama_cassi_accept(comparator.get(), next_token.token) == 0,
            std::string("comparator accept failed: ") + llama_cassi_last_error(comparator.get()));
    }

    const std::vector<uint8_t> committed_bytes = checkpoint_bytes(session.get());
    const std::vector<uint8_t> comparator_bytes = checkpoint_bytes(comparator.get());
    require(committed_bytes == comparator_bytes,
        "post-commit checkpoint bytes did not equal the sequential comparator checkpoint");
}

// Case (2): verify then discard must restore the exact predecessor
// checkpoint and leave the session usable for an ordinary accept.
void test_discard(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params,
        const std::vector<llama_token> & prompt) {
    session_ptr session = make_session(model, context_params, cassi_params);
    require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
        std::string("discard begin failed: ") + llama_cassi_last_error(session.get()));
    llama_cassi_token pending{};
    require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
        std::string("discard pending next failed: ") + llama_cassi_last_error(session.get()));

    const std::vector<uint8_t> predecessor_bytes = checkpoint_bytes(session.get());

    const llama_token draft_tokens[2] = { pending.token, pending.token };
    const double proposal_probabilities[2] = { 1.0, 1.0 };
    const llama_cassi_sampler_params target_samplers[3] = {
        greedy_sampler(), greedy_sampler(), greedy_sampler()
    };
    llama_cassi_draft_verify_request request{};
    request.draft_tokens = draft_tokens;
    request.proposal_probabilities = proposal_probabilities;
    request.draft_count = 2;
    request.target_samplers = target_samplers;
    request.target_sampler_count = 3;

    llama_cassi_draft_verify_receipt receipt{};
    require(llama_cassi_verify_draft(session.get(), &request, &receipt) == 0,
        std::string("discard verify_draft failed: ") + llama_cassi_last_error(session.get()));

    require(llama_cassi_verify_discard(session.get(), receipt.receipt_sha256) == 0,
        std::string("verify_discard failed: ") + llama_cassi_last_error(session.get()));

    const std::vector<uint8_t> restored_bytes = checkpoint_bytes(session.get());
    require(restored_bytes == predecessor_bytes,
        "discard did not restore the exact predecessor checkpoint bytes");

    require(llama_cassi_accept(session.get(), pending.token) == 0,
        std::string("post-discard accept failed: ") + llama_cassi_last_error(session.get()));
}

// Case (3): a fully-accepted draft yields the bonus token and matches the
// sequential greedy reference.
void test_full_accept(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params,
        const std::vector<llama_token> & prompt) {
    const std::vector<llama_token> teacher = greedy_sequence(model, context_params, cassi_params, prompt, 5);

    session_ptr session = make_session(model, context_params, cassi_params);
    require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
        std::string("full-accept begin failed: ") + llama_cassi_last_error(session.get()));
    llama_cassi_token pending{};
    require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
        std::string("full-accept pending next failed: ") + llama_cassi_last_error(session.get()));
    require(pending.token == teacher[0], "full-accept pending token diverged from the greedy reference");

    const llama_token draft_tokens[3] = { teacher[1], teacher[2], teacher[3] };
    const double proposal_probabilities[3] = { 1.0, 1.0, 1.0 };
    const llama_cassi_sampler_params target_samplers[4] = {
        greedy_sampler(), greedy_sampler(), greedy_sampler(), greedy_sampler()
    };
    llama_cassi_draft_verify_request request{};
    request.draft_tokens = draft_tokens;
    request.proposal_probabilities = proposal_probabilities;
    request.draft_count = 3;
    request.target_samplers = target_samplers;
    request.target_sampler_count = 4;

    llama_cassi_draft_verify_receipt receipt{};
    require(llama_cassi_verify_draft(session.get(), &request, &receipt) == 0,
        std::string("full-accept verify_draft failed: ") + llama_cassi_last_error(session.get()));
    require(receipt.accepted_count == 3, "full accept did not accept every draft token");
    require(!receipt.rejected, "full accept receipt incorrectly reported a rejection");
    require(receipt.bonus, "full accept receipt did not report a bonus token");
    require(receipt.output_count == 4, "full accept receipt output count is wrong");
    require(receipt.output_tokens[0] == teacher[1] && receipt.output_tokens[1] == teacher[2] &&
            receipt.output_tokens[2] == teacher[3] && receipt.output_tokens[3] == teacher[4],
        "full accept output tokens (including bonus) diverged from the sequential greedy reference");

    require(llama_cassi_verify_commit(session.get(), receipt.receipt_sha256) == 0,
        std::string("full-accept verify_commit failed: ") + llama_cassi_last_error(session.get()));
}

// Case (4): misuse must be refused with typed errors and must not corrupt
// session state.
void test_misuse(
        llama_model * model,
        llama_context_params context_params,
        llama_cassi_params cassi_params,
        const std::vector<llama_token> & prompt) {
    auto build_request = [](const llama_token * draft_tokens, const double * proposal_probabilities,
                             const llama_cassi_sampler_params * target_samplers, uint32_t draft_count) {
        llama_cassi_draft_verify_request request{};
        request.draft_tokens = draft_tokens;
        request.proposal_probabilities = proposal_probabilities;
        request.draft_count = draft_count;
        request.target_samplers = target_samplers;
        request.target_sampler_count = draft_count + 1;
        return request;
    };

    // Double commit: the second commit must fail and leave the session
    // healthy for further ordinary use.
    {
        session_ptr session = make_session(model, context_params, cassi_params);
        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
            std::string("misuse(double-commit) begin failed: ") + llama_cassi_last_error(session.get()));
        llama_cassi_token pending{};
        require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
            std::string("misuse(double-commit) pending next failed: ") + llama_cassi_last_error(session.get()));
        const llama_token draft_tokens[1] = { pending.token };
        const double proposal_probabilities[1] = { 1.0 };
        const llama_cassi_sampler_params target_samplers[2] = { greedy_sampler(), greedy_sampler() };
        llama_cassi_draft_verify_request request = build_request(draft_tokens, proposal_probabilities, target_samplers, 1);
        llama_cassi_draft_verify_receipt receipt{};
        require(llama_cassi_verify_draft(session.get(), &request, &receipt) == 0,
            std::string("misuse(double-commit) verify_draft failed: ") + llama_cassi_last_error(session.get()));
        require(llama_cassi_verify_commit(session.get(), receipt.receipt_sha256) == 0,
            std::string("misuse(double-commit) first commit failed: ") + llama_cassi_last_error(session.get()));
        require(llama_cassi_verify_commit(session.get(), receipt.receipt_sha256) != 0,
            "double commit was incorrectly accepted");
        require(std::strcmp(llama_cassi_last_error(session.get()), "apprentice_draft_no_pending_transaction") == 0,
            "double commit did not report the expected typed error");
        llama_cassi_token healthy{};
        const llama_cassi_status healthy_status = llama_cassi_next(session.get(), &healthy);
        require(healthy_status == LLAMA_CASSI_TOKEN || healthy_status == LLAMA_CASSI_DONE,
            std::string("session state was corrupted by a double commit attempt: ") +
                llama_cassi_last_error(session.get()));
    }

    // Wrong receipt hash: must be refused, and the correct hash must still
    // succeed afterward, proving the failed attempt left the transaction
    // untouched.
    {
        session_ptr session = make_session(model, context_params, cassi_params);
        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
            std::string("misuse(wrong-hash) begin failed: ") + llama_cassi_last_error(session.get()));
        llama_cassi_token pending{};
        require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
            std::string("misuse(wrong-hash) pending next failed: ") + llama_cassi_last_error(session.get()));
        const llama_token draft_tokens[1] = { pending.token };
        const double proposal_probabilities[1] = { 1.0 };
        const llama_cassi_sampler_params target_samplers[2] = { greedy_sampler(), greedy_sampler() };
        llama_cassi_draft_verify_request request = build_request(draft_tokens, proposal_probabilities, target_samplers, 1);
        llama_cassi_draft_verify_receipt receipt{};
        require(llama_cassi_verify_draft(session.get(), &request, &receipt) == 0,
            std::string("misuse(wrong-hash) verify_draft failed: ") + llama_cassi_last_error(session.get()));
        const std::string wrong_hash(64, 'f');
        require(llama_cassi_verify_commit(session.get(), wrong_hash.c_str()) != 0,
            "wrong receipt hash was incorrectly accepted by commit");
        require(std::strcmp(llama_cassi_last_error(session.get()), "apprentice_draft_receipt_mismatch") == 0,
            "wrong receipt hash did not report the expected typed error");
        require(llama_cassi_verify_commit(session.get(), receipt.receipt_sha256) == 0,
            "correct receipt hash was refused after a prior wrong-hash attempt left the transaction intact");
    }

    // Non-verifier (undersized) context: verify_draft must refuse for
    // insufficient n_ubatch/n_rs_seq capacity, without disturbing the
    // pending token.
    {
        llama_context_params small_params = context_params;
        small_params.n_ubatch = 8;
        small_params.n_batch = 8;
        small_params.n_rs_seq = 2;
        session_ptr session = make_session(model, small_params, cassi_params);
        require(llama_cassi_begin(session.get(), prompt.data(), prompt.size(), 16) == 0,
            std::string("misuse(capacity) begin failed: ") + llama_cassi_last_error(session.get()));
        llama_cassi_token pending{};
        require(llama_cassi_next(session.get(), &pending) == LLAMA_CASSI_TOKEN,
            std::string("misuse(capacity) pending next failed: ") + llama_cassi_last_error(session.get()));
        const llama_token draft_tokens[3] = { pending.token, pending.token, pending.token };
        const double proposal_probabilities[3] = { 1.0, 1.0, 1.0 };
        const llama_cassi_sampler_params target_samplers[4] = {
            greedy_sampler(), greedy_sampler(), greedy_sampler(), greedy_sampler()
        };
        llama_cassi_draft_verify_request request = build_request(draft_tokens, proposal_probabilities, target_samplers, 3);
        llama_cassi_draft_verify_receipt receipt{};
        require(llama_cassi_verify_draft(session.get(), &request, &receipt) != 0,
            "undersized non-verifier context incorrectly accepted a draft verify request");
        require(std::strcmp(llama_cassi_last_error(session.get()), "apprentice_draft_verify_capacity_insufficient") == 0,
            "undersized context did not report the expected typed capacity error");
        require(llama_cassi_accept(session.get(), pending.token) == 0,
            std::string("misuse(capacity) post-refusal accept failed: ") + llama_cassi_last_error(session.get()));
    }
}

} // namespace

int main(int argc, char ** argv) {
    if (argc != 3) {
        std::cerr << "usage: " << argv[0] << " MODEL cpu|gpu\n";
        return 2;
    }

    try {
        const std::string model_path = argv[1];
        const std::string native_device = argv[2];
        require(native_device == "cpu" || native_device == "gpu", "native device must be cpu or gpu");

        ggml_backend_load_all();
        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = native_device == "gpu" ? 99 : 0;
        model_ptr model(llama_model_load_from_file(model_path.c_str(), model_params), llama_model_free);
        require(model != nullptr, "failed to load Qwen model");

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = 64;
        context_params.n_batch = 16;
        context_params.n_ubatch = 16;
        context_params.n_seq_max = 1;
        context_params.n_rs_seq = 4;
        context_params.cassi_modal = false;
        context_params.cassi_field_step = false;
        context_params.cassi_qi_field = false;
        context_params.no_perf = false;
        context_params.samplers = nullptr;
        context_params.n_samplers = 0;

        llama_cassi_params cassi_params = llama_cassi_default_params();
        cassi_params.memory_bytes = UINT64_C(256) * 1024 * 1024;
        cassi_params.audit_interval = 0;
        cassi_params.teacher_policy = LLAMA_CASSI_NEVER;
        cassi_params.route_policy = LLAMA_CASSI_EXACT_PIPELINE;
        cassi_params.field_device = native_device == "gpu" ? "Vulkan0" : "CPU";
        cassi_params.model_path = model_path.c_str();

        const llama_vocab * vocab = llama_model_get_vocab(model.get());
        const int32_t vocab_size = llama_vocab_n_tokens(vocab);
        const std::vector<llama_token> prompt = common_tokenize(vocab, "Continue briefly. Label A:", true, true);
        require(!prompt.empty(), "test prompt tokenization failed");

        test_partial_accept(model.get(), context_params, cassi_params, prompt, vocab_size);
        test_discard(model.get(), context_params, cassi_params, prompt);
        test_full_accept(model.get(), context_params, cassi_params, prompt);
        test_misuse(model.get(), context_params, cassi_params, prompt);

        std::cout << "draft verify seam behavior passed\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL test-cassi-draft-verify: " << error.what() << "\n";
        return 1;
    }
}
