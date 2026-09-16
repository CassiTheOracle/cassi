#pragma once

#include "ggml.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

constexpr uint32_t CASSI_APPRENTICE_SCALE_COUNT = 4;
constexpr uint32_t CASSI_APPRENTICE_COMPONENT_COUNT = 9;
constexpr uint32_t CASSI_APPRENTICE_UNUSED_BYTE_INDEX = UINT32_MAX;

// These values are also the public llama_cassi_service_kind values.
enum cassi_field_kind : uint32_t {
    CASSI_FIELD_TEXT      = 0,
    CASSI_FIELD_EMBED     = 1,
    CASSI_FIELD_HEAD      = 2,
    CASSI_FIELD_ATTENTION = 3,
    CASSI_FIELD_FFN       = 4,
};

struct cassi_field_page {
    cassi_field_kind kind;
    int32_t layer;
    uint32_t width;
    uint32_t entries;
    uint64_t mode_offset;

    uint64_t entry_stride() const;
    uint64_t memory_offset() const;
    uint64_t mode_count() const;
};

struct cassi_field_config {
    uint32_t layers = 0;
    uint32_t embedding_width = 0;
    uint32_t vocabulary_size = 0;
    uint64_t memory_bytes = UINT64_C(1) << 30;
    std::string device = "Vulkan0";
    // Nonzero only in the private reference-fixture test object.
    uint32_t fixture_entries = 0;
};

struct cassi_query {
    uint32_t page = UINT32_MAX;
    ggml_tensor * input = nullptr;
    int32_t token = -1;
    const uint8_t * piece = nullptr;
    size_t piece_size = 0;
    uint32_t byte_index = CASSI_APPRENTICE_UNUSED_BYTE_INDEX;
    std::array<uint8_t, 4> id_prefix = {};
};

struct cassi_target {
    bool is_byte = false;
    uint8_t byte = 0;
    ggml_tensor * vector = nullptr;
};

enum cassi_probe_status : uint32_t {
    CASSI_PROBE_NEEDS_TEACHER = 0,
    CASSI_PROBE_FIELD_EXACT = 1,
    CASSI_PROBE_FIELD_INTERPOLATED = 2,
};

struct cassi_probe {
    ggml_tensor * target = nullptr;
    cassi_probe_status status = CASSI_PROBE_NEEDS_TEACHER;
    bool eligible = false;
    bool exact = false;

    bool is_byte = false;
    uint8_t byte = 0;
    uint32_t vector_length = 0;
    float scatter = 0.0f;
    float total_weight = 0.0f;
    float minimum_distance2 = 0.0f;
    std::vector<float> weights;
    std::vector<float> distances2;
};

struct cassi_observation {
    cassi_probe prediction;
    uint32_t entry = UINT32_MAX;
    bool merged = false;
    bool evicted = false;
    bool predeposit_success = false;
    float predeposit_error = 1.0f;
};


class llama_cassi_field {
public:
    explicit llama_cassi_field(const cassi_field_config & config);
    ~llama_cassi_field();

    llama_cassi_field(const llama_cassi_field &) = delete;
    llama_cassi_field & operator=(const llama_cassi_field &) = delete;

    void reset_context();
    void sense_marker(uint16_t symbol);
    void sense_token(int32_t token, const std::string & piece, bool eog);
    cassi_probe probe(const cassi_query & query);
    cassi_observation observe(const cassi_query & query, const cassi_target & target);
    uint8_t guide_byte(uint8_t byte);
    ggml_tensor * guide_vector(ggml_tensor * vector);
    ggml_tensor * add_vectors(ggml_tensor * left, ggml_tensor * right);
    ggml_tensor * copy_vector(ggml_tensor * source, uint32_t slot);
    ggml_tensor * load_vector(const float * data, size_t count);

    size_t context_snapshot_size() const;
    void context_snapshot_get(void * destination, size_t size) const;
    void context_snapshot_set(const void * source, size_t size);

    const cassi_field_config & config() const;
    const std::vector<cassi_field_page> & pages() const;
    const cassi_field_page & page(uint32_t index) const;
    uint64_t modes() const;
    uint64_t field_bytes() const;
    uint64_t minimum_field_bytes() const;
    uint64_t field_revision() const;
    uint64_t engram_evictions() const;
    const std::string & backend_name() const;

    size_t state_size() const;
    void state_get(void * destination, size_t size) const;
    void state_set(const void * source, size_t size, uint64_t revision, uint64_t evictions = 0);
    void field_sha256(uint8_t digest[32]) const;
    void profile_sha256(uint8_t digest[32]) const;

    bool page_mature(uint32_t page_index);
    uint64_t backend_allocation_bytes() const;

private:
    struct impl;
    std::unique_ptr<impl> pimpl;
};
