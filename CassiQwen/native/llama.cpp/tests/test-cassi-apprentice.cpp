#include "llama-cassi-field.h"
#include "ggml-backend.h"
#include <nlohmann/json.hpp>

extern "C" {
#include "hash/sha256/sha256.h"
}

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using json = nlohmann::json;
constexpr float PHI = 1.618033988749895f;
constexpr float SCATTER_CEILING = 1.0e-4f;

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

std::vector<uint8_t> read_bytes(const std::filesystem::path & path) {
    std::ifstream input(path, std::ios::binary);
    require(static_cast<bool>(input), "cannot open fixture: " + path.string());
    input.seekg(0, std::ios::end);
    const std::streamoff size = input.tellg();
    require(size >= 0, "cannot size fixture: " + path.string());
    input.seekg(0, std::ios::beg);
    std::vector<uint8_t> result(static_cast<size_t>(size));
    input.read(reinterpret_cast<char *>(result.data()), static_cast<std::streamsize>(result.size()));
    require(input.good() || input.eof(), "cannot read fixture: " + path.string());
    require(static_cast<size_t>(input.gcount()) == result.size(), "short fixture read: " + path.string());
    return result;
}

std::string hex_digest(const uint8_t * data, size_t size) {
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (size_t index = 0; index < size; ++index) {
        output << std::setw(2) << static_cast<unsigned>(data[index]);
    }
    return output.str();
}

std::string sha256(const std::vector<uint8_t> & bytes) {
    std::array<uint8_t, 32> digest = {};
    sha256_hash(digest.data(), bytes.data(), bytes.size());
    return hex_digest(digest.data(), digest.size());
}

std::vector<float> as_f32(const std::vector<uint8_t> & bytes) {
    require(bytes.size() % sizeof(float) == 0, "fixture is not an f32 array");
    std::vector<float> result(bytes.size() / sizeof(float));
    std::memcpy(result.data(), bytes.data(), bytes.size());
    return result;
}

std::vector<int32_t> as_i32(const std::vector<uint8_t> & bytes) {
    require(bytes.size() % sizeof(int32_t) == 0, "fixture is not an i32 array");
    std::vector<int32_t> result(bytes.size() / sizeof(int32_t));
    std::memcpy(result.data(), bytes.data(), bytes.size());
    return result;
}

void compare_f32(
        const std::vector<float> & actual,
        const std::vector<float> & expected,
        double atol,
        double rtol,
        const std::string & label) {
    require(actual.size() == expected.size(), label + " size mismatch");
    for (size_t index = 0; index < actual.size(); ++index) {
        const double a = actual[index];
        const double e = expected[index];
        if (!std::isfinite(a) || !std::isfinite(e) || std::abs(a - e) > atol + rtol * std::abs(e)) {
            throw std::runtime_error(
                label + " differs at index " + std::to_string(index) +
                ": actual=" + std::to_string(a) + ": expected=" + std::to_string(e));
        }
    }
}

std::vector<float> state_f32(llama_cassi_field & field) {
    std::vector<uint8_t> bytes(field.state_size());
    field.state_get(bytes.data(), bytes.size());
    return as_f32(bytes);
}

std::vector<float> tensor_f32(ggml_tensor * tensor, size_t expected_count) {
    require(tensor != nullptr, "field tensor is null");
    require(static_cast<size_t>(ggml_nelements(tensor)) == expected_count, "field tensor shape mismatch");
    std::vector<float> result(expected_count);
    ggml_backend_tensor_get(tensor, result.data(), 0, result.size() * sizeof(float));
    return result;
}

double relative_error(const std::vector<float> & actual, const std::vector<float> & expected) {
    require(actual.size() == expected.size(), "relative-error shape mismatch");
    double numerator = 0.0;
    double denominator = 0.0;
    for (size_t index = 0; index < actual.size(); ++index) {
        const double difference = static_cast<double>(actual[index]) - expected[index];
        numerator += difference * difference;
        denominator += static_cast<double>(expected[index]) * expected[index];
    }
    return std::sqrt(numerator / std::max(denominator, 1.0e-24));
}

void set_context(llama_cassi_field & field, const std::vector<uint16_t> & symbols) {
    field.reset_context();
    for (uint16_t symbol : symbols) {
        field.sense_marker(symbol);
    }
}

cassi_query text_query() {
    cassi_query query;
    query.page = 0;
    query.byte_index = 0;
    return query;
}

cassi_observation observe_byte(llama_cassi_field & field, uint8_t byte) {
    cassi_target target;
    target.is_byte = true;
    target.byte = byte;
    return field.observe(text_query(), target);
}

uint32_t find_page(const llama_cassi_field & field, cassi_field_kind kind) {
    for (uint32_t index = 0; index < field.pages().size(); ++index) {
        if (field.page(index).kind == kind) {
            return index;
        }
    }
    throw std::runtime_error("required field page is missing");
}

cassi_observation observe_vector(
        llama_cassi_field & field,
        uint32_t page,
        const std::vector<float> & input,
        const std::vector<float> & target) {
    ggml_tensor * input_loaded = field.load_vector(input.data(), input.size());
    ggml_tensor * input_copy = field.copy_vector(input_loaded, 0);
    ggml_tensor * target_loaded = field.load_vector(target.data(), target.size());
    ggml_tensor * target_copy = field.copy_vector(target_loaded, 1);
    cassi_query query;
    query.page = page;
    query.input = input_copy;
    cassi_target value;
    value.vector = target_copy;
    return field.observe(query, value);
}

cassi_probe probe_vector(
        llama_cassi_field & field,
        uint32_t page,
        const std::vector<float> & input) {
    ggml_tensor * input_loaded = field.load_vector(input.data(), input.size());
    ggml_tensor * input_copy = field.copy_vector(input_loaded, 0);
    cassi_query query;
    query.page = page;
    query.input = input_copy;
    return field.probe(query);
}

void verify_manifest(const std::filesystem::path & directory, const json & manifest) {
    require(manifest.at("schema") == "cassi.apprentice.fixtures.v1", "fixture schema mismatch");
    require(manifest.at("profile") == "cassi.qi.apprentice-engram.v1", "fixture profile mismatch");
    for (const json & entry : manifest.at("files")) {
        const std::filesystem::path path = directory / entry.at("name").get<std::string>();
        const std::vector<uint8_t> bytes = read_bytes(path);
        require(bytes.size() == entry.at("byte_count").get<size_t>(), "fixture byte count mismatch: " + path.string());
        require(sha256(bytes) == entry.at("sha256").get<std::string>(), "fixture hash mismatch: " + path.string());
    }
}

std::vector<uint8_t> fixture_bytes(
        const std::filesystem::path & directory,
        const json & manifest,
        const std::string & name) {
    const auto & files = manifest.at("files");
    const auto found = std::find_if(files.begin(), files.end(), [&](const json & entry) {
        return entry.at("name") == name;
    });
    require(found != files.end(), "fixture manifest lacks " + name);
    return read_bytes(directory / name);
}

void verify_reference_fixtures(
        const std::filesystem::path & directory,
        const std::string & device,
        double atol,
        double rtol) {
    std::ifstream manifest_stream(directory / "cases.json");
    require(static_cast<bool>(manifest_stream), "cannot open cases.json");
    json manifest;
    manifest_stream >> manifest;
    verify_manifest(directory, manifest);

    const json & geometry = manifest.at("geometry");
    require(geometry.at("scales") == 4 && geometry.at("batch") == 1, "fixture field rank mismatch");
    require(geometry.at("pages").size() == 1, "fixture must contain exactly one page");
    const json & page = geometry.at("pages").at(0);
    require(page.at("kind") == 0 && page.at("layer") == -1 && page.at("width") == 512 && page.at("entries") == 8,
        "fixture page mismatch");

    cassi_field_config config;
    config.layers = 1;
    config.embedding_width = 1024;
    config.vocabulary_size = 260;
    config.memory_bytes = geometry.at("field_bytes").get<uint64_t>();
    config.device = device;
    config.fixture_entries = 8;

    llama_cassi_field sensed(config);
    require(sensed.modes() == geometry.at("modes").get<uint64_t>() &&
            sensed.field_bytes() == geometry.at("field_bytes").get<uint64_t>(),
        "native fixture geometry differs from reference");
    std::array<uint8_t, 32> profile = {};
    sensed.profile_sha256(profile.data());
    require(hex_digest(profile.data(), profile.size()) == manifest.at("profile_sha256").get<std::string>(),
        "native fixture profile hash differs from reference");

    const std::vector<int32_t> events = as_i32(fixture_bytes(directory, manifest, "sense-events.i32"));
    require(events.size() == manifest.at("cases").at("sense_events").get<size_t>(), "sense-event count mismatch");
    for (int32_t event : events) {
        require(event >= 0 && event < 260, "fixture sense event is invalid");
        sensed.sense_marker(static_cast<uint16_t>(event));
    }
    compare_f32(
        state_f32(sensed),
        as_f32(fixture_bytes(directory, manifest, "sense-state.f32")),
        atol,
        rtol,
        "reference sense state");

    llama_cassi_field exact(config);
    for (int32_t event : events) {
        exact.sense_marker(static_cast<uint16_t>(event));
    }
    const uint8_t expected_byte = manifest.at("cases").at("exact_byte").get<uint8_t>();
    const cassi_observation first = observe_byte(exact, expected_byte);
    const cassi_observation second = observe_byte(exact, expected_byte);
    require(!first.merged && second.merged && second.entry == first.entry, "fixture exact observations did not merge");
    compare_f32(
        state_f32(exact),
        as_f32(fixture_bytes(directory, manifest, "exact-state.f32")),
        atol,
        rtol,
        "reference exact state");
    const cassi_probe probe = exact.probe(text_query());
    require(probe.status == CASSI_PROBE_FIELD_EXACT && probe.byte == expected_byte, "fixture exact decision mismatch");

    const std::vector<float> expected_encoded_interleaved =
        as_f32(fixture_bytes(directory, manifest, "exact-probe.f32"));
    require(expected_encoded_interleaved.size() == 512 * 2, "fixture encoded target shape mismatch");
    std::vector<float> expected_encoded(2 * 512);
    for (size_t mode = 0; mode < 512; ++mode) {
        expected_encoded[mode] = expected_encoded_interleaved[2 * mode];
        expected_encoded[512 + mode] = expected_encoded_interleaved[2 * mode + 1];
    }
    compare_f32(tensor_f32(probe.target, expected_encoded.size()), expected_encoded, atol, rtol, "reference probe target");
}

void verify_exact_associations(const cassi_field_config & config) {
    llama_cassi_field field(config);
    const std::vector<uint16_t> key_a = { 258, 17, 65 };
    const std::vector<uint16_t> key_b = { 258, 23, 66 };
    const std::vector<uint16_t> key_c = { 258, 91, 67 };

    set_context(field, key_a);
    observe_byte(field, 17);
    observe_byte(field, 17);
    set_context(field, key_b);
    observe_byte(field, 231);
    observe_byte(field, 231);

    set_context(field, key_a);
    const cassi_probe probe_a = field.probe(text_query());
    set_context(field, key_b);
    const cassi_probe probe_b = field.probe(text_query());
    set_context(field, key_c);
    const cassi_probe unrelated = field.probe(text_query());
    require(probe_a.status == CASSI_PROBE_FIELD_EXACT && probe_a.byte == 17, "first exact association failed");
    require(probe_b.status == CASSI_PROBE_FIELD_EXACT && probe_b.byte == 231, "second exact association failed");
    require(unrelated.status == CASSI_PROBE_NEEDS_TEACHER, "unrelated key did not request teacher");

    llama_cassi_field zeroed(config);
    set_context(zeroed, key_a);
    require(zeroed.probe(text_query()).status == CASSI_PROBE_NEEDS_TEACHER,
        "zeroed field retained a learned response");
}

void verify_bounded_vectors(const cassi_field_config & config) {
    llama_cassi_field field(config);
    const uint32_t page = find_page(field, CASSI_FIELD_FFN);
    const std::array<float, 4> norms = { 0.0f, 0.1f, 1.0f, 100.0f };
    std::array<std::vector<float>, 4> keys;
    std::array<std::vector<float>, 4> targets;
    for (size_t index = 0; index < norms.size(); ++index) {
        keys[index].assign(config.embedding_width, 0.0f);
        targets[index].assign(config.embedding_width, 0.0f);
        keys[index][16 + index] = 0.5f;
        targets[index][0] = norms[index];
        observe_vector(field, page, keys[index], targets[index]);
        observe_vector(field, page, keys[index], targets[index]);
    }
    for (size_t index = 0; index < norms.size(); ++index) {
        const cassi_probe probe = probe_vector(field, page, keys[index]);
        require(probe.status == CASSI_PROBE_FIELD_EXACT && probe.target != nullptr,
            "bounded vector did not reach exact recall at index " + std::to_string(index) +
            ", status=" + std::to_string(static_cast<int>(probe.status)));
        const std::vector<float> restored = tensor_f32(probe.target, config.embedding_width);
        const double tolerance = norms[index] == 0.0f ? 1.0e-6 : 1.0e-4;
        require(relative_error(restored, targets[index]) <= tolerance,
            "bounded vector magnitude did not reconstruct");
    }

    const std::vector<float> valid_state = state_f32(field);
    const uint64_t revision = field.field_revision();
    for (float invalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity() }) {
        std::vector<float> value(config.embedding_width, 0.0f);
        value[0] = invalid;
        bool rejected = false;
        try {
            field.load_vector(value.data(), value.size());
        } catch (const std::exception &) {
            rejected = true;
        }
        require(rejected && state_f32(field) == valid_state && field.field_revision() == revision,
            "nonfinite vector was accepted or changed field state");
    }

    std::vector<float> invalid_state = valid_state;
    const cassi_field_page & descriptor = field.page(page);
    const uint64_t target_mode = descriptor.memory_offset() + 2ULL * descriptor.width;
    const uint64_t modes = field.modes();
    for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
        invalid_state[(static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + 0) * modes + target_mode] = PHI;
        invalid_state[(static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + 2) * modes + target_mode] = 1.0f;
    }
    bool norm_rejected = false;
    try {
        field.state_set(invalid_state.data(), invalid_state.size() * sizeof(float), revision);
    } catch (const std::exception &) {
        norm_rejected = true;
    }
    require(norm_rejected && state_f32(field) == valid_state && field.field_revision() == revision,
        "near-unit encoded norm was accepted or changed the field");
}

void verify_contradiction_and_interpolation(const cassi_field_config & config) {
    cassi_field_config contradiction_config = config;
    contradiction_config.fixture_entries = 3;
    contradiction_config.memory_bytes = (512ULL + 3ULL * (3ULL * 512ULL + 6ULL)) * 4ULL * 9ULL * sizeof(float);
    llama_cassi_field contradiction(contradiction_config);
    set_context(contradiction, { 258, 42 });
    observe_byte(contradiction, 3);
    observe_byte(contradiction, 249);
    const cassi_probe conflict = contradiction.probe(text_query());
    require(conflict.status == CASSI_PROBE_NEEDS_TEACHER && conflict.scatter > SCATTER_CEILING,
        "contradictory targets selected an insertion-order winner");

    llama_cassi_field interpolation(config);
    const uint32_t page = find_page(interpolation, CASSI_FIELD_FFN);
    const auto scalar_vector = [&](float input_value) {
        std::vector<float> result(config.embedding_width, 0.0f);
        result[0] = input_value;
        return result;
    };
    const std::vector<float> key_a = scalar_vector(-0.02f);
    const std::vector<float> key_b = scalar_vector( 0.02f);
    const std::vector<float> target_a = scalar_vector(1.0f);
    const std::vector<float> target_b = scalar_vector(1.001f);
    const cassi_observation a0 = observe_vector(interpolation, page, key_a, target_a);
    observe_vector(interpolation, page, key_a, target_a);
    const cassi_observation b0 = observe_vector(interpolation, page, key_b, target_b);
    observe_vector(interpolation, page, key_b, target_b);
    const cassi_observation audit0 = observe_vector(
        interpolation, page, scalar_vector(-0.0199f), scalar_vector(1.00001f));
    const cassi_observation audit1 = observe_vector(
        interpolation, page, scalar_vector(-0.0198f), scalar_vector(1.00002f));
    require(audit0.merged && audit1.merged && audit0.entry == a0.entry && audit1.entry == a0.entry &&
            audit0.predeposit_success && audit1.predeposit_success,
        "non-identical interpolation audits did not validate the endpoint");

    const cassi_probe proposal = probe_vector(interpolation, page, scalar_vector(0.0f));
    require(proposal.status == CASSI_PROBE_FIELD_INTERPOLATED && proposal.target != nullptr,
        "novel query did not produce field interpolation");
    require(a0.entry != b0.entry && a0.entry < proposal.weights.size() && b0.entry < proposal.weights.size(),
        "interpolation entry bookkeeping is invalid");
    const double stored_a = (1.0 + 1.0 + 1.00001 + 1.00002) / 4.0;
    const double stored_b = 1.001;
    const auto encode = [](double value) { return value / (1.0 + std::abs(value)); };
    const double wa = proposal.weights[a0.entry];
    const double wb = proposal.weights[b0.entry];
    require(wa > 0.0 && wb > 0.0, "interpolation did not use both endpoints");
    const double encoded = (wa * encode(stored_a) + wb * encode(stored_b)) / (wa + wb);
    const double expected = encoded / (1.0 - std::abs(encoded));
    const double actual = tensor_f32(proposal.target, config.embedding_width)[0];
    require(std::abs(actual - expected) <= 2.0e-5 && actual > 1.0 && actual < 1.001,
        "interpolation does not match the independent all-entry weighted target");
}

void verify_eviction_context_and_guidance(const cassi_field_config & config) {
    cassi_field_config eviction_config = config;
    eviction_config.fixture_entries = 2;
    eviction_config.memory_bytes = (512ULL + 2ULL * (3ULL * 512ULL + 6ULL)) * 4ULL * 9ULL * sizeof(float);
    llama_cassi_field eviction(eviction_config);
    set_context(eviction, { 258, 1 });
    observe_byte(eviction, 1);
    observe_byte(eviction, 1);
    set_context(eviction, { 258, 2 });
    observe_byte(eviction, 2);
    observe_byte(eviction, 2);
    set_context(eviction, { 258, 3 });
    const cassi_observation inserted = observe_byte(eviction, 3);
    require(inserted.evicted && eviction.engram_evictions() == 1, "capacity eviction was not counted");
    const std::vector<float> eviction_snapshot = state_f32(eviction);
    const uint64_t eviction_revision = eviction.field_revision();
    const uint64_t eviction_count = eviction.engram_evictions();
    set_context(eviction, { 258, 4 });
    const cassi_observation second_eviction = observe_byte(eviction, 4);
    require(second_eviction.evicted && eviction.engram_evictions() == eviction_count + 1,
        "second capacity eviction was not counted");
    eviction.state_set(
        eviction_snapshot.data(),
        eviction_snapshot.size() * sizeof(float),
        eviction_revision,
        eviction_count);
    require(state_f32(eviction) == eviction_snapshot &&
            eviction.field_revision() == eviction_revision &&
            eviction.engram_evictions() == eviction_count,
        "field-state restore did not restore revision and eviction accounting");
    set_context(eviction, { 258, 2 });
    const cassi_probe survivor = eviction.probe(text_query());
    require(survivor.status == CASSI_PROBE_FIELD_EXACT && survivor.byte == 2,
        "surviving association was not readable after eviction");

    cassi_field_config context_config = config;
    context_config.fixture_entries = 8;
    context_config.memory_bytes = (512ULL + 8ULL * (3ULL * 512ULL + 6ULL)) * 4ULL * 9ULL * sizeof(float);
    llama_cassi_field context(context_config);
    const std::vector<float> before = state_f32(context);
    for (uint32_t index = 0; index < 10000; ++index) {
        context.sense_marker(static_cast<uint16_t>(index % 260));
    }
    const std::vector<float> after = state_f32(context);
    const uint64_t modes = context.modes();
    const uint64_t memory_offset = context.page(0).memory_offset();
    for (uint32_t scale = 0; scale < CASSI_APPRENTICE_SCALE_COUNT; ++scale) {
        double energy = 0.0;
        for (uint64_t mode = 0; mode < context.page(0).width; ++mode) {
            const auto at = [&](uint32_t component) {
                return after[(static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * modes + mode];
            };
            const double dre = at(0) - PHI * at(2);
            const double dim = at(1) - PHI * at(3);
            const double vre = at(4) - PHI * at(6);
            const double vim = at(5) - PHI * at(7);
            energy += (dre * dre + dim * dim + vre * vre + vim * vim) / (1.0 + PHI * PHI);
            require(std::isfinite(at(8)) && at(8) >= 0.0f && at(8) <= 64.0f + 1.0e-5f,
                "epsilon invariant failed during long context sensing");
        }
        require(energy / context.page(0).width <= 8.0 + 1.0e-4,
            "mean-energy invariant failed during long context sensing");
        for (uint32_t component = 0; component < CASSI_APPRENTICE_COMPONENT_COUNT; ++component) {
            const uint64_t base = (static_cast<uint64_t>(scale) * CASSI_APPRENTICE_COMPONENT_COUNT + component) * modes;
            require(std::equal(
                    before.begin() + static_cast<std::ptrdiff_t>(base + memory_offset),
                    before.begin() + static_cast<std::ptrdiff_t>(base + modes),
                    after.begin() + static_cast<std::ptrdiff_t>(base + memory_offset)),
                "context sensing changed retained engram bytes");
        }
    }

    llama_cassi_field guided(context_config);
    const std::vector<float> guided_before = state_f32(guided);
    for (uint32_t byte = 0; byte < 256; ++byte) {
        require(guided.guide_byte(static_cast<uint8_t>(byte)) == byte, "guided byte demodulation failed");
    }
    require(state_f32(guided) == guided_before, "guided bytes changed retained state");

    std::vector<float> magnitude(config.embedding_width, 0.0f);
    magnitude[0] = 0.0f;
    magnitude[1] = 0.1f;
    magnitude[2] = -1.0f;
    magnitude[3] = 100.0f;
    ggml_tensor * source = guided.load_vector(magnitude.data(), magnitude.size());
    ggml_tensor * result = guided.guide_vector(source);
    require(relative_error(tensor_f32(result, magnitude.size()), magnitude) <= 1.0e-4,
        "guided vector failed to preserve magnitude");
}

} // namespace

int main(int argc, char ** argv) {
    if (argc != 3) {
        std::cerr << "usage: " << argv[0] << " FIXTURE_DIR CPU|Vulkan0\n";
        return 2;
    }
    const std::filesystem::path fixture_dir = argv[1];
    const std::string device = argv[2];
    const char * stage = "reference-fixtures";
    try {
        require(device == "CPU" || device == "Vulkan0", "unsupported field device");
        const double atol = 5.0e-5;
        const double rtol = 5.0e-4;
        verify_reference_fixtures(fixture_dir, device, atol, rtol);

        cassi_field_config config;
        config.layers = 1;
        config.embedding_width = 1024;
        config.vocabulary_size = 260;
        config.memory_bytes = 32ULL * 1024 * 1024;
        config.device = device;

        stage = "exact-associations";
        verify_exact_associations(config);
        stage = "bounded-vectors";
        verify_bounded_vectors(config);
        stage = "contradiction-interpolation";
        verify_contradiction_and_interpolation(config);
        stage = "eviction-context-guidance";
        verify_eviction_context_and_guidance(config);

        std::cout << "{\"schema\":\"cassi.apprentice.field-test.v1\","
                  << "\"verdict\":\"PASS\","
                  << "\"field_device\":\"" << device << "\","
                  << "\"fixture_atol\":" << atol << ","
                  << "\"fixture_rtol\":" << rtol << ","
                  << "\"context_steps\":10000,\"guided_bytes\":256}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL test-cassi-apprentice stage=" << stage << ": " << error.what() << "\n";
        return 1;
    }
}
