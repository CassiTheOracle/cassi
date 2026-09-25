#include "llama-cassi.h"

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void require(bool condition, const std::string & message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

llama_cassi_q_delta_result sample(
        const float * logits,
        size_t count,
        llama_token draft,
        double draw,
        uint32_t top_k = 0) {
    llama_cassi_sampler_params sampler{};
    sampler.mode = LLAMA_CASSI_SAMPLER_CATEGORICAL;
    sampler.temperature = 1.0f;
    sampler.top_k = top_k;
    sampler.draw = draw;
    llama_cassi_q_delta_result result{};
    require(
        llama_cassi_sample_q_delta(logits, count, draft, sampler, &result) == 0,
        "categorical q-delta sample failed");
    return result;
}

void verify_q_delta_edges() {
    const float equal_logits[] = {0.0f, 0.0f};
    const auto accepted = sample(equal_logits, 2, 0, 0.25);
    require(accepted.accepted && accepted.token == 0, "p(d)=0.5 acceptance failed");
    require(std::abs(accepted.target_probability - 0.5) < 1.0e-12,
        "target probability for equal logits is wrong");
    require(accepted.draws_consumed == 1, "acceptance did not consume exactly one draw");

    const auto rejected = sample(equal_logits, 2, 0, 0.75);
    require(!rejected.accepted && rejected.token == 1,
        "rejection did not sample the residual support p minus delta(d)");
    require(std::abs(rejected.target_probability - 0.5) < 1.0e-12,
        "rejection target probability is wrong");
    require(rejected.draws_consumed == 1, "rejection did not consume exactly one draw");

    const float ranked_logits[] = {5.0f, 0.0f};
    const auto zero_mass = sample(ranked_logits, 2, 1, 0.4, 1);
    require(!zero_mass.accepted && zero_mass.target_probability == 0.0 && zero_mass.token == 0,
        "p(d)=0 did not fall back to the filtered target support");

    const auto unit_mass = sample(
        ranked_logits, 2, 0, std::nextafter(1.0, 0.0), 1);
    require(unit_mass.accepted && unit_mass.target_probability == 1.0 && unit_mass.token == 0,
        "p(d)=1 was not accepted for every valid draw");

    llama_cassi_sampler_params greedy{};
    greedy.mode = LLAMA_CASSI_SAMPLER_GREEDY;
    greedy.temperature = 1.0f;
    llama_cassi_q_delta_result greedy_result{};
    require(llama_cassi_sample_q_delta(ranked_logits, 2, 1, greedy, &greedy_result) == 0,
        "greedy q-delta sample failed");
    require(!greedy_result.accepted && greedy_result.token == 0 &&
            greedy_result.target_probability == 0.0 && greedy_result.draws_consumed == 0,
        "greedy rejection did not preserve the one-hot target law");
    require(llama_cassi_sample_q_delta(ranked_logits, 2, 0, greedy, &greedy_result) == 0,
        "greedy accepted q-delta sample failed");
    require(greedy_result.accepted && greedy_result.token == 0 &&
            greedy_result.target_probability == 1.0 && greedy_result.draws_consumed == 0,
        "greedy acceptance consumed a categorical draw");
    llama_cassi_q_delta_result ignored{};
    llama_cassi_sampler_params invalid{};
    invalid.mode = LLAMA_CASSI_SAMPLER_CATEGORICAL;
    invalid.temperature = 1.0f;
    invalid.draw = 1.0;
    require(llama_cassi_sample_q_delta(equal_logits, 2, 0, invalid, &ignored) != 0,
        "out-of-range sampler draw was accepted");
}

} // namespace

int main() {
    try {
        verify_q_delta_edges();
        std::cout << "q-delta sampler behavior passed\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "FAIL test-cassi-draft-sampler: " << error.what() << "\n";
        return 1;
    }
}
