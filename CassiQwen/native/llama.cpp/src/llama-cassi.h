#pragma once

#include "../include/llama-cassi.h"

#include <memory>

struct llama_cassi_context_deleter {
    void operator()(llama_cassi_context * context) const noexcept {
        llama_cassi_free(context);
    }
};

using llama_cassi_context_ptr = std::unique_ptr<llama_cassi_context, llama_cassi_context_deleter>;
