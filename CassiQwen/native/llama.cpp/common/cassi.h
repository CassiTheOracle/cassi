#pragma once

#include "llama-cassi.h"

#include <nlohmann/json.hpp>

#include <memory>
#include <string>
#include <vector>

struct common_params;

void common_cassi_prepare_defaults(common_params & params);
void common_cassi_validate_params(const common_params & params);
class common_cassi_owner {
public:
    common_cassi_owner(
        const std::string & state_path,
        bool initialize,
        bool read_only,
        const std::string & receipt_path);
    ~common_cassi_owner();

    common_cassi_owner(const common_cassi_owner &) = delete;
    common_cassi_owner & operator=(const common_cassi_owner &) = delete;

    bool load(llama_model * model, llama_context_params native_params, llama_cassi_params params);
    llama_cassi_context * context() const;

    bool publish(bool force = false);
    bool write_failed() const;
    const std::string & error() const;

    nlohmann::ordered_json receipt(
        const char * status,
        const char * error_code,
        const std::vector<llama_token> & emitted) const;
    bool write_receipt(const nlohmann::ordered_json & value);

private:
    struct impl;
    std::unique_ptr<impl> pimpl;
};
