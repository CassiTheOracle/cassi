#include "cassi.h"
#include "common.h"
#include "llama.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using model_ptr = std::unique_ptr<llama_model, decltype(&llama_model_free)>;

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

std::vector<uint8_t> read_bytes(const std::filesystem::path & path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    require(static_cast<bool>(stream), "checkpoint could not be opened");
    const std::streamsize size = stream.tellg();
    require(size >= 0, "checkpoint size could not be read");
    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    stream.seekg(0);
    stream.read(reinterpret_cast<char *>(bytes.data()), size);
    require(stream.gcount() == size, "checkpoint could not be read completely");
    return bytes;
}

llama_context_params context_params() {
    llama_context_params params = llama_context_default_params();
    params.n_ctx = 64;
    params.n_batch = 1;
    params.n_ubatch = 1;
    params.n_seq_max = 1;
    params.n_rs_seq = 0;
    params.cassi_modal = false;
    params.cassi_field_step = false;
    params.cassi_qi_field = false;
    params.no_perf = false;
    params.samplers = nullptr;
    params.n_samplers = 0;
    return params;
}

llama_cassi_params apprentice_params(
        const std::string & model_path,
        const char * device,
        llama_cassi_teacher_policy policy) {
    llama_cassi_params params = llama_cassi_default_params();
    params.memory_bytes = 64ULL * 1024 * 1024;
    params.audit_interval = 0;
    params.teacher_policy = policy;
    params.route_policy = LLAMA_CASSI_AUTO;
    params.field_device = device;
    params.model_path = model_path.c_str();
    return params;
}

} // namespace

int main(int argc, char ** argv) {
    if (argc != 4) {
        std::cerr << "usage: " << argv[0] << " MODEL OUTPUT_DIR CPU|Vulkan0\n";
        return 2;
    }
    try {
        const std::string model_path = argv[1];
        const std::filesystem::path output_dir = argv[2];
        const std::string device = argv[3];
        std::filesystem::create_directories(output_dir);
        const std::filesystem::path state = output_dir / "owner.cassiap";
        const std::filesystem::path receipt_path = output_dir / "owner.jsonl";
        for (const auto & path : {
                 state,
                 std::filesystem::path(state.string() + ".previous"),
                 std::filesystem::path(state.string() + ".lock"),
                 receipt_path }) {
            std::error_code error;
            std::filesystem::remove(path, error);
        }

        llama_backend_init();
        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = 0;
        model_ptr model(llama_model_load_from_file(model_path.c_str(), model_params), llama_model_free);
        require(model != nullptr, "model load failed");

        uint64_t learned_revision = 0;
        std::string checkpoint_hash;
        {
            common_cassi_owner owner(state.string(), true, false, receipt_path.string());
            llama_cassi_params params = apprentice_params(model_path, device.c_str(), LLAMA_CASSI_ADAPTIVE);
            require(owner.load(model.get(), context_params(), params), "owner initialization failed: " + owner.error());
            require(std::filesystem::exists(state), "initial checkpoint was not published");
            const std::vector<uint8_t> initial_checkpoint = read_bytes(state);

            bool locked = false;
            try {
                common_cassi_owner second(state.string(), false, false, std::string());
            } catch (const std::runtime_error & error) {
                locked = std::string(error.what()) == "apprentice_checkpoint_locked";
            }
            require(locked, "second writer did not fail before model/session loading");

            const llama_vocab * vocab = llama_model_get_vocab(model.get());
            const std::vector<llama_token> prompt = common_tokenize(vocab, "Persist this lesson:", true, true);
            require(!prompt.empty(), "prompt tokenization failed");
            llama_cassi_context * session = owner.context();
            require(llama_cassi_begin(session, prompt.data(), prompt.size(), 1) == 0,
                std::string("begin failed: ") + llama_cassi_last_error(session));
            llama_cassi_token token = {};
            require(llama_cassi_next(session, &token) == LLAMA_CASSI_TOKEN,
                std::string("next failed: ") + llama_cassi_last_error(session));
            require(llama_cassi_accept(session, token.token) == 0,
                std::string("accept failed: ") + llama_cassi_last_error(session));
            require(read_bytes(state) == initial_checkpoint,
                "accepted learning was published before the explicit token transaction");
            require(owner.publish(), "accepted token publication failed: " + owner.error());
            require(read_bytes(state) != initial_checkpoint,
                "accepted token publication did not make learning durable");
            require(llama_cassi_finish(session, false) == 0,
                std::string("finish failed: ") + llama_cassi_last_error(session));
            require(owner.publish(), "finished request publication failed: " + owner.error());
            require(std::filesystem::exists(state.string() + ".previous"),
                "atomic replacement did not retain the previous checkpoint");

            llama_cassi_info info = {};
            require(llama_cassi_get_info(session, &info) == 0 && info.field_revision > 0,
                "published field revision was not inspectable");
            learned_revision = info.field_revision;
            const auto receipt = owner.receipt("complete", nullptr, { token.token });
            require(receipt.at("durable").get<bool>() &&
                    receipt.at("field_revision").get<uint64_t>() == learned_revision &&
                    receipt.at("stats").at("native_cache_bytes_remaining").get<uint64_t>() == 0,
                "durable receipt did not describe the published idle state");
            checkpoint_hash = receipt.at("checkpoint_sha256").get<std::string>();
            require(checkpoint_hash.size() == 64, "checkpoint digest was not published");
            require(owner.write_receipt(receipt), "receipt append failed: " + owner.error());
        }

        {
            common_cassi_owner reader(state.string(), false, true, std::string());
            llama_cassi_params params = apprentice_params(model_path, device.c_str(), LLAMA_CASSI_NEVER);
            require(reader.load(model.get(), context_params(), params), "read-only reload failed: " + reader.error());
            llama_cassi_info info = {};
            require(llama_cassi_get_info(reader.context(), &info) == 0 && info.field_revision == learned_revision,
                "read-only reload changed field identity");
            require(reader.publish(), "unchanged read-only publication should be a no-op");
            const auto receipt = reader.receipt("complete", nullptr, {});
            require(receipt.at("checkpoint_sha256").get<std::string>() == checkpoint_hash,
                "checkpoint identity changed across owner reload");
        }

        {
            common_cassi_owner reader(state.string(), false, true, std::string());
            llama_cassi_params params = apprentice_params(model_path, device.c_str(), LLAMA_CASSI_ALWAYS);
            require(reader.load(model.get(), context_params(), params),
                "publication-failure reader load failed: " + reader.error());
            llama_cassi_context * session = reader.context();
            const llama_vocab * vocab = llama_model_get_vocab(model.get());
            const size_t state_size = llama_cassi_state_size(session);
            std::vector<uint8_t> before(state_size);
            require(llama_cassi_state_get(session, before.data(), before.size()) == before.size(),
                "publication-failure baseline export failed");
            const std::vector<llama_token> prompt =
                common_tokenize(vocab, "A rejected publication must not leak:", true, true);
            require(llama_cassi_begin(session, prompt.data(), prompt.size(), 1) == 0,
                "publication-failure begin failed");
            llama_cassi_token token = {};
            require(llama_cassi_next(session, &token) == LLAMA_CASSI_TOKEN,
                "publication-failure next failed");
            require(llama_cassi_accept(session, token.token) == 0,
                "publication-failure accept failed");
            require(!reader.publish() && reader.error() == "apprentice_checkpoint_read_only",
                "read-only publication did not fail with the stable error");
            require(llama_cassi_finish(session, true) == 0,
                "publication-failure cleanup failed");
            std::vector<uint8_t> after(state_size);
            require(llama_cassi_state_get(session, after.data(), after.size()) == after.size() &&
                    after == before,
                "failed publication left accepted learning in the reusable session");
            llama_cassi_stats stats = {};
            llama_cassi_get_stats(session, &stats);
            require(stats.committed_tokens == 0 && stats.teacher_guided_tokens == 0,
                "failed publication left a committed token in session accounting");
            require(read_bytes(state) == before,
                "failed publication changed the durable checkpoint");
        }

        {
            const std::filesystem::path previous = state.string() + ".previous";
            std::fstream stream(previous, std::ios::binary | std::ios::in | std::ios::out);
            require(static_cast<bool>(stream), "previous checkpoint could not be opened for corruption test");
            char byte = 0;
            stream.read(&byte, 1);
            require(stream.gcount() == 1, "previous checkpoint was unexpectedly empty");
            byte ^= 0x01;
            stream.seekp(0);
            stream.write(&byte, 1);
            stream.flush();
            require(static_cast<bool>(stream), "previous checkpoint corruption write failed");

            common_cassi_owner guarded(state.string(), false, false, std::string());
            llama_cassi_params params = apprentice_params(model_path, device.c_str(), LLAMA_CASSI_ADAPTIVE);
            require(!guarded.load(model.get(), context_params(), params) &&
                    guarded.error() == "apprentice_checkpoint_invalid",
                "incompatible previous checkpoint was not refused");
        }

        llama_backend_free();
        std::cout << "{\"schema\":\"cassi.apprentice.owner-test.v1\","
                  << "\"verdict\":\"PASS\","
                  << "\"field_device\":\"" << device << "\","
                  << "\"field_revision\":" << learned_revision << ","
                  << "\"checkpoint_sha256\":\"" << checkpoint_hash << "\"}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL test-cassi-apprentice-owner: " << error.what() << "\n";
        return 1;
    }
}
