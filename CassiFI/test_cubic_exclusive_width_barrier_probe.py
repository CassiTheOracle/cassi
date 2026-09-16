from __future__ import annotations



import run_cubic_exclusive_width_barrier_probe as producer
import verify_cubic_exclusive_width_barrier_probe as verifier




def test_synthetic_controls_make_the_width_barrier_predicate_falsifiable() -> None:
    produced = producer.synthetic_controls()
    rebuilt = verifier.synthetic_controls()

    assert produced == rebuilt
    positive = produced["positive_general_vector_anchor"]
    negative = produced["negative_all_bases_width_two_anchor"]
    assert positive["pair_rank"] == 2
    assert positive["ordinary_all_states"] is True
    assert positive["state_profile"]["00"]["minimum_width"] == 3
    assert positive["state_profile"]["01"]["minimum_width"] == 2
    assert positive["state_profile"]["10"]["minimum_width"] == 2
    assert positive["state_profile"]["11"]["minimum_width"] == 3
    assert positive["two_sided_width_barrier"] is True
    assert negative["pair_rank"] == 2
    assert negative["two_sided_width_barrier"] is False


def test_runner_and_verifier_agree_on_frozen_seed_all_pair_censuses() -> None:
    for name, formula, ports_list in verifier.SEED_SPECS:
        assert verifier.formula_digest(formula) == (
            verifier.FROZEN_SEED_DIGESTS[name]
        )
        source = {
            "kind": "fast_frozen_seed_cross_check",
            "name": name,
        }

        produced = producer._analyze_formula(formula, source)
        rebuilt = verifier.analyze_formula(formula, source)

        exclusive_by_ports = {
            tuple(pair["ports"]): pair
            for pair in produced["pair_profile"]["exclusive_pairs"]
        }
        assert all(ports in exclusive_by_ports for ports in ports_list)

        assert produced == rebuilt
        counts = produced["pair_profile"]["counts"]
        assert counts["exclusive_pairs"] > 0
        assert counts["eligible_pairs"] == 0
        assert counts["admissible_pairs"] == 0


def test_complete_switch_population_reconstructs_independently() -> None:
    produced_formulas, produced_accounting = producer._neighbor_population()
    rebuilt_formulas, rebuilt_accounting = verifier.neighbor_population()

    assert produced_formulas == rebuilt_formulas
    assert produced_accounting == rebuilt_accounting == {
        "base_equivalent_specs": 16,
        "canonical_domain_formulas": 766,
        "distinct_nonbase_neighbors": 764,
        "duplicate_nonbase_specs": 80,
        "nonbase_switch_specs": 844,
        "raw_switch_specs": 860,
        "seed_formulas": 2,
    }
    assert 860 == 16 + 80 + 764


def test_small_deterministic_random_corpus_reconstructs_independently() -> None:
    parameters = {
        "accepted_draws": 128,
        "seed": 0xBADA55,
        "size": 12,
    }

    produced = producer.build_random_domain(**parameters)
    rebuilt = verifier.build_random_domain(**parameters)

    assert produced == rebuilt
    assert produced["generation"]["accepted_draws"] == 128
    assert produced["generation"]["unique_formulas"] == 128
    assert produced["summary"]["census_attempted_formulas"] > 0
    assert produced["summary"]["pair_cases_checked"] > 0


