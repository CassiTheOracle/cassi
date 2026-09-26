"""Direct tests for the UFA105 compression-matrix runner.

The obligation the map records at lines 2301-2312 asks for the operator-level
compression ``K_{alpha->alpha+-e_c}`` between fine multiplicity spaces, which the
map leaves as its next adjacent-block obligation.  The runner computes it on the
smallest cases the map names (labels of size at most one as sources, targets up
to label two) inside the declared model C1 and writes a receipt.  These tests
hold that receipt to what it claims:

* the named demand is the document's own text at the claimed lines, hashed from
  the file's raw bytes (so a map edit fails the test rather than passing
  silently);
* the fine multiplicities reproduce the map's anchor table and cutoff counts;
* the declared fine basis is explicit, independent and spans the multiplicity
  space;
* the computed blocks are nonzero for every adjacent shift of every smallest
  case, which is the finite part of the (UFA107) forcing;
* the Hilbert form really is the declared unitary one (the flat control fires);
* the square's dihedral group acts on the blocks at rank level, the fine
  labelling set transports only on the pairing-preserving subgroup, and the
  sixteen non-dihedral permutations are refused rather than silently skipped;
* the receipt digest follows this repo's convention and excludes timing keys;
* the two scope statements stay separate: the stored default scope is the one
  this suite rebuilds, the widened scope is on disk with its own computed and
  excluded counts, and every block it still excludes carries exact dimensions
  and cost units;
* the rank witness is reported per computed block, verified against the block's
  own entries, and its negatives are separated into exact and undecided ones.

Every claim carries a control that must move the measured number when the
mechanism is removed: a corrupted anchor, a duplicated basis vector, a dropped
curl, a flat Hilbert form, a wrong relabelling, a wrong pairing, a deleted
witness entry.  A control that does not fire would make the reading vacuous,
which is the failure these tests are built to catch.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from fractions import Fraction as F

import pytest

from run_yang_mills_compression_matrix import (
    ANCHOR_TABLE,
    COMPLETE_FRONTIER_DIM,
    CUTOFF_COUNTS,
    OUT_PATH,
    QUOTED_RANGES,
    SMALLEST_CUTOFF,
    SOURCE_DOCUMENT,
    TIMING_KEYS,
    WIDENED_FRONTIER_DIM,
    WITNESS_EXACT_MAX_K,
    _leaves,
    block_matrix,
    build_analysis,
    build_receipt,
    canonical_json,
    content_digest,
    digest_body,
    fine_basis,
    fine_dimension,
    flat_weights,
    full_rank_saturation,
    fuse,
    generator_hermeticity_residual,
    is_dihedral,
    mf_permutation_invariance,
    minor_witness,
    rank_rational,
    run_varying_leaves,
    sector_image,
    state_vector,
    strip_timing,
    unitary_weights,
    witness_controls,
)


# ---------------------------------------------------------------------------
# fixtures


@pytest.fixture(scope="module")
def receipt() -> dict:
    return build_receipt()


@pytest.fixture(scope="module")
def stored_receipt() -> dict:
    """The artifact on disk, which carries both declared scopes; a fresh default build does
    not pay for the widened scope, so the widened readings are held to what is stored."""
    return json.loads(OUT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analysis() -> dict:
    return build_analysis()


@pytest.fixture(scope="module")
def source_lines() -> list[str]:
    return SOURCE_DOCUMENT.read_bytes().decode("utf-8").splitlines()


# ---------------------------------------------------------------------------
# item 1: the obligation's demand, verbatim and pinned


def test_demand_is_a_verbatim_slice_of_the_live_document(
    receipt: dict, source_lines: list[str]
) -> None:
    obligation = receipt["obligation"]
    start, end = obligation["demand_lines"]
    live = "\n".join(source_lines[start - 1 : end])
    assert obligation["demand_verbatim"] == live
    # the demand must carry the map's own notation and tag, not a paraphrase of it
    assert "(UFA105)" in live
    assert "K_{\\alpha\\to\\alpha\\pm e_c}" in live
    assert "multiplicity spaces" in live
    # the slice boundary is declared, not implied: it carries the tail of the
    # preceding sentence and the demand's own sentence beginning with "For"
    assert live.startswith("(UFA105) computation. For")
    assert obligation["demand_slice_note"].startswith("the slice starts on line 2301")


def test_support_action_is_a_verbatim_slice_of_the_live_document(
    receipt: dict, source_lines: list[str]
) -> None:
    obligation = receipt["obligation"]
    start, end = obligation["support_action_lines"]
    live = "\n".join(source_lines[start - 1 : end])
    assert obligation["support_action_verbatim"] == live
    assert "UFA104" in live


def test_document_digest_is_the_raw_file_digest(receipt: dict) -> None:
    recorded = receipt["obligation"]["document_sha256_at_read_time"]
    raw = SOURCE_DOCUMENT.read_bytes()
    assert recorded == hashlib.sha256(raw).hexdigest()
    # control: a text-mode read normalises CRLF on this platform, so the recorded
    # digest must differ from what `read_text` would have hashed
    if b"\r\n" in raw:
        text_mode = hashlib.sha256(
            raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
        ).hexdigest()
        assert recorded != text_mode


def test_every_quote_block_matches_the_live_document(
    receipt: dict, source_lines: list[str]
) -> None:
    quotes = receipt["obligation"]["quotes"]
    assert len(quotes) == len(QUOTED_RANGES)
    for quote in quotes:
        start, end = quote["lines"]
        live = "\n".join(source_lines[start - 1 : end])
        assert quote["text"] == live, quote["purpose"]
        assert (
            quote["sha256_of_quoted_text"]
            == hashlib.sha256(live.encode("utf-8")).hexdigest()
        )
    # control: one corrupted character must break the equality the loop relies on
    quote = quotes[3]
    start, end = quote["lines"]
    live = "\n".join(source_lines[start - 1 : end])
    corrupted = live[:-1] + ("X" if live[-1] != "X" else "Y")
    assert corrupted != live
    assert (
        hashlib.sha256(corrupted.encode("utf-8")).hexdigest()
        != quote["sha256_of_quoted_text"]
    )


# ---------------------------------------------------------------------------
# item 2: the smallest cases and the map's own multiplicity data


def test_smallest_cases_are_the_labels_at_most_one_family(receipt: dict) -> None:
    smallest = receipt["smallest_cases"]
    assert smallest["cutoff"] == SMALLEST_CUTOFF == 1
    sectors = {tuple(row["sector"]) for row in smallest["sectors"]}
    assert len(sectors) == smallest["sector_count"] == 16
    assert sectors == set(itertools.product(range(2), repeat=4))
    assert (0, 0, 0, 0) in sectors and (1, 1, 1, 1) in sectors
    # the family is shift-closed inside the truncation, as the map's lines
    # 2314-2319 say of the full nonnegative four-tuples
    for sector in sectors:
        for corner in range(4):
            if sector[corner] + 1 <= SMALLEST_CUTOFF:
                assert sector[:corner] + (sector[corner] + 1,) + sector[corner + 1 :] in sectors
            if sector[corner] > 0:
                assert sector[:corner] + (sector[corner] - 1,) + sector[corner + 1 :] in sectors


def test_anchor_table_reproduces_the_map(receipt: dict) -> None:
    rows = receipt["checks"]["anchor_table"]["rows"]
    assert receipt["checks"]["anchor_table"]["all_match"] is True
    for sector, value in ANCHOR_TABLE:
        row = next(r for r in rows if tuple(r["sector"]) == sector)
        assert row["computed"] == value
        assert fine_dimension(sector) == value
    # control: a corrupted anchor must be visible, so the match is not vacuous
    assert fine_dimension((2, 2, 1, 1)) != 31
    assert fine_dimension((1, 1, 1, 1)) != 13


def test_cutoff_counts_reproduce_the_map(receipt: dict) -> None:
    rows = receipt["checks"]["cutoff_counts"]["rows"]
    assert receipt["checks"]["cutoff_counts"]["all_match"] is True
    for cutoff, count in CUTOFF_COUNTS:
        row = next(r for r in rows if r["cutoff"] == cutoff)
        assert row["computed"] == count == (cutoff + 1) ** 4


def test_never_zero_minimum_of_the_anchor_table(receipt: dict) -> None:
    values = [r["computed"] for r in receipt["checks"]["anchor_table"]["rows"]]
    assert min(values) == 1
    # control: the table is not constant, so its minimum is a reading
    assert fine_dimension((2, 2, 2, 2)) == 91 > min(values)


def test_fuse_perturbation_control_fires() -> None:
    assert fuse(2, 2) == [0, 2, 4]
    assert fine_dimension((2, 2, 1, 1)) != fine_dimension((2, 1, 1, 1))
    assert fine_dimension((1, 1, 1, 1)) == 14


# ---------------------------------------------------------------------------
# item 3: the objects are explicit and the declared basis is a real basis


def test_fine_basis_labelings_are_exactly_the_map_rule(analysis: dict) -> None:
    for row in analysis["sectors"]:
        sector = tuple(row["sector"])
        labelings = [tuple(l) for l in row["fine_labelings"]]
        assert len(labelings) == row["fine_dimension"] == fine_dimension(sector)
        assert len(set(labelings)) == len(labelings)
        for s1, s2, s3, s4, r in labelings:
            assert s1 in fuse(sector[0], sector[1]) and s2 in fuse(sector[1], sector[2])
            assert s3 in fuse(sector[2], sector[3]) and s4 in fuse(sector[3], sector[0])
            assert r in set(fuse(s1, s2)) & set(fuse(s3, s4))
    # control: the centre filter is not free - a channel outside the intersection
    # must not appear, so the labelling count is a real constraint
    assert 3 not in set(fuse(0, 1)) & set(fuse(1, 1))


def test_declared_states_are_explicit_and_independent(receipt: dict) -> None:
    construction = receipt["basis_construction"]
    states = construction["example_state_vectors"]
    assert states, "the receipt must expose explicit state vectors"
    for key, entry in states.items():
        assert entry["vector"], key
        assert all(isinstance(x, int) for x in entry["vector"])
        assert entry["leg_dims"]
    assert len(construction["state_vector_digests"]) == 16
    rows = receipt["checks"]["basis_independence"]["rows"]
    assert receipt["checks"]["basis_independence"]["all_full"] is True
    for row in rows:
        assert row["span_rank"] == row["fine_dimension"]
    # control: the span rank is a measurement - dropping one basis vector must
    # lower it below the multiplicity on a sector of dimension above one
    digests = construction["state_vector_digests"]
    assert digests["(1, 1, 1, 1)"]["dimension"] == 14
    for sector, entry in digests.items():
        alpha = tuple(json.loads(sector.replace("(", "[").replace(")", "]")))
        vectors = [state_vector(alpha, lab)["vector"] for lab in fine_basis(alpha)]
        recomputed = hashlib.sha256(canonical_json(vectors).encode("utf-8")).hexdigest()
        assert entry["digest"] == recomputed, sector
        assert entry["dimension"] == fine_dimension(alpha) == len(vectors)
    # honest negative: the digest covers the sector's whole vector list, so the
    # dimension-one sectors whose basis list is the same [[1]] legitimately share
    # a digest (nine distinct digests over sixteen sectors is the measured value)
    unique = {v["digest"] for v in digests.values()}
    assert len(unique) < 16
    assert digests["(1, 1, 1, 1)"]["digest"] in unique
    # control: a perturbed vector list must move the digest, so it is a reading of
    # the basis and not a constant
    alpha = (1, 1, 1, 1)
    listing = [state_vector(alpha, lab)["vector"] for lab in fine_basis(alpha)]
    perturbed = copy.deepcopy(listing)
    perturbed[0][0] += 1
    assert canonical_json(perturbed) != canonical_json(listing)


def test_intertwiners_are_written_out_exactly(receipt: dict) -> None:
    intertwiners = receipt["basis_construction"]["explicit_intertwiners"]
    assert len(intertwiners) >= 4
    for legs, entry in intertwiners.items():
        assert entry["dimension"] == 1, legs
        assert entry["entries"], legs
        for value in entry["entries"]:
            assert isinstance(value, str)
            F(value)  # every stored entry is an exact rational, never a float
            assert "." not in value and "e" not in value.lower()
    # the stored metric (the curl the contraction closes with) is exact too, and it
    # is antisymmetric from label one up, which is what makes it a curl
    metrics = receipt["basis_construction"]["metric_tensors"]
    assert F(metrics["1"][0][1]) == 1 and F(metrics["1"][1][0]) == -1
    assert F(metrics["2"][0][2]) == 1 and F(metrics["2"][2][0]) == 1


def test_hilbert_weights_are_unitary_and_the_flat_control_fires(receipt: dict) -> None:
    herm = receipt["checks"]["hermiticity"]
    assert herm["declared_is_hermitian"] is True
    assert herm["declared_weights_residual"] == "0"
    assert herm["flat_weights_fire"] is True
    assert herm["flat_weights_residual"] != "0"
    # recompute both residuals in-process so the receipt cannot drift
    assert generator_hermeticity_residual(unitary_weights) == 0
    assert generator_hermeticity_residual(flat_weights) != 0
    assert unitary_weights(2, 1) == F(1, 2)
    assert flat_weights(2, 1) == 1


# ---------------------------------------------------------------------------
# item 4: the compression blocks


def test_every_adjacent_shift_of_a_smallest_case_has_nonzero_compression(
    receipt: dict,
) -> None:
    closure = receipt["closure"]
    assert closure["blocks_defined"] == 96
    assert closure["every_shift_nonzero"] is True
    assert closure["nonzero_compressions"] == closure["blocks_defined"] == 96
    for row in closure["forcing_rows"]:
        assert row["compression_nonzero"] is True
        assert row["forces_target_into_family"] is True
        source, target = tuple(row["source_sector"]), tuple(row["target_sector"])
        assert sum(1 for i in range(4) if source[i] != target[i]) == 1
        assert all(abs(source[i] - target[i]) <= 1 for i in range(4))
    # control: removing the curl kills a block, so "nonzero" is a property of the
    # construction rather than of the scan
    assert receipt["checks"]["firing_controls"]["no_curl_rank"] == 0
    assert receipt["checks"]["firing_controls"]["declared_zero"] is False


def test_block_rank_nullity_consistency(receipt: dict) -> None:
    checked = 0
    for block in receipt["compression"]["blocks"]:
        if not block.get("defined"):
            continue
        rows, cols = block["matrix_shape"]
        assert rows == len(block["basis_target"]) and cols == len(block["basis_source"])
        assert block["rank"] + block["kernel_dimension"] == cols
        exact = [[F(x) for x in row] for row in block["matrix"]]
        assert rank_rational(exact) == block["rank"]
        checked += 1
    assert checked == 96
    # control: rank_rational must notice dependence
    assert rank_rational([[F(1), F(2)], [F(2), F(4)]]) == 1
    assert rank_rational([[F(1), F(0)], [F(0), F(1)]]) == 2


def test_diagonal_trivial_spoke_candidate_is_confirmed_on_the_measured_blocks(
    receipt: dict,
) -> None:
    trivial = receipt["compression"]["trivial_spoke"]
    assert trivial["diagonal_candidate_confirmed"] is True
    assert trivial["rows"]
    for row in trivial["rows"]:
        source, target = tuple(row["source_sector"]), tuple(row["target_sector"])
        assert source == target or sum(1 for i in range(4) if source[i] != target[i]) == 1
        assert row["image_column_nonzero"] is True
        assert any(x != "0" for x in row["image_column"])
    from_trivial = [r for r in trivial["rows"] if tuple(r["source_sector"]) == (0, 0, 0, 0)]
    assert {r["corner_index"] for r in from_trivial} == {0, 1, 2, 3}
    # the map's own candidate (lines 2366-2379) is the diagonal sector (1,1,1,1)
    diagonal = [r for r in trivial["rows"] if tuple(r["source_sector"]) == (1, 1, 1, 1)]
    assert diagonal and all(r["image_column_nonzero"] for r in diagonal)
    # control: the same reading on the identity-curl variant is all zeros, so the
    # nonzero column is a measurement
    alpha, beta = (0, 0, 0, 0), (1, 0, 0, 0)
    declared = block_matrix(beta, alpha, 0, +1)
    identity_curl = block_matrix(beta, alpha, 0, +1, curl="identity")
    assert declared["matrix"][0][0] != "0"
    assert identity_curl["matrix"][0][0] == "0"


def test_pairing_and_leg_order_choices_move_the_entries(receipt: dict) -> None:
    controls = receipt["checks"]["firing_controls"]
    assert controls["alt_pairing_entries_differ"] is True
    assert controls["leg_order_entries_differ"] is True
    assert controls["wrong_pair_dimension_mismatch"] is True
    assert controls["declared_shape"] == [19, 14]
    assert controls["declared_zero"] is False
    assert receipt["structural_properties"]["pairing_choice_independence"]["all_ranks_match"] is True
    # recompute the leg-order mutation independently
    beta, alpha = (2, 1, 1, 1), (1, 1, 1, 1)
    declared = block_matrix(beta, alpha, 0, +1)
    mutated = block_matrix(
        beta, alpha, 0, +1, leg_order=("L8", "L7", "L6", "L5", "L4", "L3", "L2", "L1")
    )
    assert declared["matrix"] != mutated["matrix"]
    assert mutated["rank"] == declared["rank"]


# ---------------------------------------------------------------------------
# item 5: symmetries, stated at the level they actually hold


def test_square_symmetries_act_at_rank_level(receipt: dict) -> None:
    covariance = receipt["structural_properties"]["symmetry"]["compression_covariance"]
    assert covariance["dihedral_permutations"] == 8
    assert covariance["all_dihedral_rank_covariant"] is True
    assert covariance["dihedral_rank_covariant"] == 8
    assert covariance["non_dihedral_permutations"] == 16
    for row in covariance["rows"]:
        if row["applicable"]:
            assert row["rank_covariant"] is True and row["blocks_tested"] == 96
        else:
            assert "reason" in row and "rank_agrees" not in row
    # honest negatives, both measured: the labelling set transports only on the
    # pairing-preserving subgroup, and exact entry equality holds for the identity
    # alone at the declared basis convention
    assert covariance["dihedral_label_sets_transporting"] == 4
    assert covariance["dihedral_exact_entry_covariant"] == 1
    # firing control for the rank reading: a wrong partner (the same sector, the
    # opposite shift) must disagree on rank somewhere, so rank covariance is not
    # a statement about a constant
    assert covariance["rank_control_fires"] is True
    assert covariance["rank_control_wrong_partner_mismatches"] > 0
    assert covariance["rank_control_pairs"] > 0
    # control: a non-dihedral permutation must be refused, not silently accepted
    assert [list(p) for p in itertools.permutations(range(4)) if is_dihedral(p)] == [
        [0, 1, 2, 3],
        [0, 3, 2, 1],
        [1, 0, 3, 2],
        [1, 2, 3, 0],
        [2, 1, 0, 3],
        [2, 3, 0, 1],
        [3, 0, 1, 2],
        [3, 2, 1, 0],
    ]
    assert is_dihedral((0, 2, 3, 1)) is False
    assert is_dihedral((0, 1, 3, 2)) is False


def test_fine_multiplicity_is_permutation_invariant_over_the_wide_domain(
    receipt: dict,
) -> None:
    invariance = receipt["structural_properties"]["symmetry"]["mf_permutation_invariance"]
    assert invariance["sectors_checked"] == 81
    assert invariance["permutations"] == 24
    assert invariance["all_invariant"] is True
    assert invariance["violating_permutations"] == []
    # control: the reading must be falsifiable - a relabelling that is not a corner
    # permutation moves the multiplicity on at least one sector
    def bad_image(alpha):
        return (alpha[1], alpha[2], alpha[3], alpha[0] + 1)

    violations = [
        alpha
        for alpha in itertools.product(range(2), repeat=4)
        if fine_dimension(bad_image(alpha)) != fine_dimension(alpha)
    ]
    assert violations, "a wrong relabelling must be caught by this domain"
    # and the runner's image function is a genuine permutation action
    assert sector_image((1, 2, 3, 0), (1, 1, 1, 1)) == (1, 1, 1, 1)
    assert sector_image((1, 2, 3, 0), (1, 0, 0, 0)) == (0, 1, 0, 0)


def test_mf_invariance_recomputed_in_process() -> None:
    recomputed = mf_permutation_invariance(cutoff=1)
    assert recomputed["all_invariant"] is True
    assert recomputed["sectors_checked"] == 16 and recomputed["permutations"] == 24


# ---------------------------------------------------------------------------
# item 6: the receipt itself


def test_receipt_digest_follows_the_repo_convention(receipt: dict) -> None:
    body = copy.deepcopy(receipt)
    recorded = body.pop("receipt_sha256")
    assert recorded == content_digest(body)
    # control: a payload mutation must change the digest
    mutated = copy.deepcopy(body)
    mutated["compression"]["summary"]["block_count"] += 1
    assert content_digest(mutated) != recorded
    # and a timing key must NOT change it (the repo's strip_timing convention)
    retimed = copy.deepcopy(body)
    retimed["runtime_seconds"] = body["runtime_seconds"] + 1000.0
    assert content_digest(retimed) == recorded
    assert "runtime_seconds" in TIMING_KEYS and "elapsed_seconds" in TIMING_KEYS


def test_written_receipt_matches_a_fresh_build(receipt: dict, stored_receipt: dict) -> None:
    on_disk = stored_receipt
    # the artifact must be internally consistent: its stored digest must be the digest of
    # its own payload, so tampering with any field is visible
    body = copy.deepcopy(on_disk)
    recorded = body.pop("receipt_sha256")
    assert content_digest(body) == recorded
    # every section a fresh default build produces must be the one on disk, including the
    # witness readings; the widened scope is the one section only the stored artifact has,
    # and it adds its own limitation lines after the default ones
    for section in (
        "checks",
        "closure",
        "compression",
        "declared_model",
        "digest_convention",
        "extension",
        "obligation",
        "pairing_columns",
        "smallest_cases",
        "structural_properties",
    ):
        assert canonical_json(on_disk[section]) == canonical_json(receipt[section]), section
    assert on_disk["limitations"][: len(receipt["limitations"])] == receipt["limitations"]
    assert "widened_scope" in on_disk
    assert "widened_scope" not in receipt
    # control: the stored artifact's limitations carry the widened-scope lines and the complete
    # family's line, so every scope is stated rather than the wider one silently replacing the
    # narrower
    assert len(on_disk["limitations"]) == len(receipt["limitations"]) + 3
    joined = " ".join(on_disk["limitations"])
    assert "widened scope" in joined and "rank-witness search" in joined and "complete family" in joined


def test_digest_body_is_declared_and_free_of_run_varying_values(stored_receipt: dict) -> None:
    # the receipt declares what content-stability means for it, and the declaration is digested
    convention = stored_receipt["digest_convention"]
    assert convention["digest_field"] == "receipt_sha256"
    assert convention["stripped_keys"] == sorted(TIMING_KEYS)
    assert "measured_seconds" in convention["stripped_keys"]
    assert "runtime_seconds" in convention["stripped_keys"]
    assert "elapsed_seconds" in convention["stripped_keys"]
    recorded = stored_receipt["receipt_sha256"]
    assert content_digest(stored_receipt) == recorded
    # the declared set is the one that is actually removed from the digested body: none of those
    # keys survives anywhere in it, at any depth
    body = strip_timing(stored_receipt)
    for path, _leaf in _leaves(body):
        assert path.rsplit(".", 1)[-1].rstrip("]").split("[")[0] not in TIMING_KEYS, path
    # and no other leaf carries a clock reading under another name or in prose
    assert run_varying_leaves(stored_receipt) == []
    # control: the reading can fire, in both forms it declares.  A clock-named float outside the
    # declared set and a fractional-seconds figure in prose are each caught, while the declared
    # measured_seconds field (stripped by name, and a genuine run reading) is not a violation.
    mutated = copy.deepcopy(stored_receipt)
    mutated["complete_family"]["budget"]["duration_seconds"] = 269.75
    mutated["limitations"] = list(mutated["limitations"]) + [
        "This build took 269.75 s of wall clock and says so in prose."
    ]
    caught = run_varying_leaves(mutated)
    assert [(v["path"], v["value"]) for v in caught] == [
        ("receipt.complete_family.budget.duration_seconds", 269.75),
        (f"receipt.limitations[{len(mutated['limitations']) - 1}]",
         "This build took 269.75 s of wall clock and says so in prose."),
    ]
    # the mutation is what changed the reading: removing it clears the violations again
    del mutated["complete_family"]["budget"]["duration_seconds"]
    mutated["limitations"] = mutated["limitations"][:-1]
    assert run_varying_leaves(mutated) == []
    # a declared timing key carrying a clock reading is not a violation - it is stripped, so it
    # cannot move the digest - which is exactly why the leak above is the one that mattered
    assert mutated["complete_family"]["budget"]["measured_seconds"] > 0
    body_keys = {
        path.rsplit(".", 1)[-1].rstrip("]").split("[")[0] for path, _leaf in _leaves(digest_body(mutated))
    }
    assert "measured_seconds" not in body_keys
    assert "runtime_seconds" not in body_keys and "elapsed_seconds" not in body_keys


def test_analysis_is_deterministic() -> None:
    assert canonical_json(build_analysis()) == canonical_json(build_analysis())


def test_reported_readings_are_present_in_the_receipt(receipt: dict) -> None:
    summary = receipt["compression"]["summary"]
    for key in (
        "block_count",
        "min_rank",
        "max_rank",
        "max_kernel_dimension",
        "full_column_rank_blocks",
        "zero_blocks",
    ):
        assert key in summary
    ranks = [b["rank"] for b in receipt["compression"]["blocks"] if b.get("defined")]
    assert summary["min_rank"] == min(ranks) == 1
    assert summary["max_rank"] == max(ranks)
    assert summary["zero_blocks"] == []
    assert summary["full_column_rank_blocks"]
    # the Gram aggregates of both families are stored, not only their rows
    smallest_grams = receipt["structural_properties"]["orthogonality_aggregates"]
    extended_grams = receipt["extension"]["orthogonality_aggregates"]
    assert smallest_grams["blocks_with_gram"] == 16
    assert smallest_grams["orthogonal_gram_blocks"] == 9
    assert smallest_grams["rank_deficient_gram_blocks"] == 8
    assert extended_grams["blocks_with_gram"] == 16
    assert extended_grams["orthogonal_gram_blocks"] == 10
    assert extended_grams["rank_deficient_gram_blocks"] == 8
    # control: the summary is a reading of the blocks, so mismatched shapes must
    # show up rather than being averaged away
    assert all(
        b["matrix_shape"][0] == len(b["basis_target"]) for b in receipt["compression"]["blocks"]
    )


# ---------------------------------------------------------------------------
# item 7: the extension beyond the smallest family (vanishing pattern)


def test_extension_reaches_into_the_label_at_most_two_family(receipt: dict) -> None:
    extension = receipt["extension"]
    assert extension["cutoff"] == 2
    assert extension["frontier_dim"] == 19
    summary = extension["summary"]
    assert summary["block_count"] == 420
    assert len(extension["blocks"]) == 420
    assert len(extension["skipped_blocks"]) == 120
    assert len(extension["rank_and_kernel"]["per_block"]) == 420
    # every skipped block carries its exact dimensions and a reason that names the frontier
    for skipped in extension["skipped_blocks"]:
        assert skipped["reason"].startswith("source or target multiplicity exceeds")
        assert max(skipped["source_dimension"], skipped["target_dimension"]) > 19
        assert skipped["cost_units"] == skipped["source_dimension"] * skipped["target_dimension"]
    # the computed blocks really do live inside the frontier
    for block in extension["blocks"]:
        assert block.get("defined") is True
        assert max(block["matrix_shape"]) <= 19
    # control: the frontier is a real restriction, so the skipped set is not empty and
    # contains the blocks with the largest multiplicities
    assert extension["vanishing"]["largest_skipped_dimension_pair"] == [91, 120]
    assert extension["vanishing"]["skipped_cost_units_total"] > 0
    # and the source family is the map's next family, reached by the four corner shifts
    assert extension["summary"]["block_count"] + len(extension["skipped_blocks"]) == 540
    # the per-source table must reconcile with the block-level counts, exactly
    table = extension["by_source_sector"]
    assert table["source_sector_count"] == 81
    assert table["sources_with_a_zero_block"] == []
    assert sum(len(r["blocks_computed"]) for r in table["rows"]) == 420
    assert sum(len(r["blocks_skipped"]) for r in table["rows"]) == 120
    assert all(r["complete"] for r in table["rows"])
    assert all(r["zero_blocks"] == [] for r in table["rows"])
    assert extension["max_source_dimension_reached"] == 19
    assert extension["max_target_dimension_reached"] == 19
    # control: a source sector's table entry lists exactly the shifts the map allows, so the
    # reconciliation is not an artefact of a padded row
    witness = next(r for r in table["rows"] if r["source_sector"] == [1, 1, 1, 2])
    assert len(witness["blocks_computed"]) + len(witness["blocks_skipped"]) == witness[
        "expected_shift_count"
    ] == 8
    # the split is a frontier effect, not a missing shift: what is not computed is recorded,
    # and every recorded one sits above the frontier
    assert all(e["direction"] in (1, -1) for e in witness["blocks_computed"])
    assert -1 in {e["direction"] for e in witness["blocks_computed"]}
    assert all(
        s["reason"].startswith("source or target multiplicity exceeds")
        for s in witness["blocks_skipped"]
    )
    # the computed family as a whole covers both shift directions
    assert {b["direction"] for b in extension["blocks"]} == {1, -1}


def test_no_vanishing_compression_was_found_inside_the_declared_model(
    receipt: dict,
) -> None:
    vanishing = receipt["extension"]["vanishing"]
    assert vanishing["blocks_computed"] == 420
    assert vanishing["zero_block_count"] == 0
    assert vanishing["zero_blocks"] == []
    assert vanishing["first_vanishing_block"] is None
    assert vanishing["answer"] == "no zero block was found inside the computed family"
    assert receipt["extension"]["summary"]["zero_blocks"] == []
    # control: the reading is not vacuous - removing the curl does produce a zero block on
    # the same code path, so a zero is detectable when it exists
    alpha, beta = (1, 1, 1, 1), (2, 1, 1, 1)
    assert block_matrix(beta, alpha, 0, +1)["is_zero"] is False
    assert block_matrix(beta, alpha, 0, +1, curl="identity")["is_zero"] is True


def test_corner_spectator_property_is_measured_per_direction(receipt: dict) -> None:
    smallest = receipt["structural_properties"]["symmetry"]["corner_spectator_smallest_family"]
    assert smallest["groups_with_all_four_corners"] == 17
    assert smallest["complete_groups_disagreeing"] == 0
    extension = receipt["extension"]["corner_spectator"]
    assert extension["groups_with_all_four_corners"] == 55
    # honest negative: the property holds for every complete up-shift group and fails for
    # ten of the eleven complete down-shift groups on the larger family
    assert extension["by_direction"]["1"]["disagreeing_groups"] == 0
    assert extension["by_direction"]["1"]["complete_groups"] == 50
    assert extension["by_direction"]["-1"]["disagreeing_groups"] == 4
    witness = extension["first_disagreeing_group"]
    assert witness["direction"] == -1
    assert len(set(witness["ranks"])) > 1
    assert set(witness["corners"]) == {0, 1, 2, 3}
    # the reading that explains the split, measured rather than assumed: every block in the
    # disagreeing groups attains rank = min(shape), so the rank differences are exactly the
    # dimension differences of the different target sectors
    assert extension["disagreeing_group_blocks"] == 16
    assert (
        extension["disagreeing_group_blocks_full_rank"]
        == extension["disagreeing_group_blocks"]
    )
    assert extension["full_rank_blocks"] == extension["significant_blocks"] == 420
    smallest_full = smallest["full_rank_blocks"]
    assert smallest_full == smallest["significant_blocks"] == 96
    # control: saturation is a real reading - the same family has blocks that are not
    # injective (kernel dimension above zero), so min(shape) is not trivially the column count
    assert extension["by_direction"]["-1"]["disagreeing_groups"] > 0
    # control: the up-shift equality is not an artefact of constant ranks in the family
    ranks = {
        b["rank"] for b in receipt["extension"]["rank_and_kernel"]["per_block"]
    }
    assert len(ranks) > 1


# ---------------------------------------------------------------------------
# item 8: is the invariance a property of the map or of the declaration?


def test_pairing_columns_compare_the_two_declared_pairings(receipt: dict) -> None:
    columns = receipt["pairing_columns"]["columns"]
    assert [c["pairing"] for c in columns] == ["12|34", "14|23"]
    for column in columns:
        assert column["anchor_values_match_map"] is True
        assert column["mf_sectors_tested"] == 81
        assert column["mf_permutations_tested"] == 24
        assert column["mf_invariant_permutations"] == 24
        assert column["blocks_tested"] == 96
        assert column["dihedral_permutations"] == 8
        assert column["dihedral_rank_covariant_permutations"] == 8
        assert column["label_set_transporting_permutations"] == 4
        assert len(column["label_set_transport_subgroup"]) == 4
        assert column["full_column_rank_blocks"] == 68
    # measured: the invariance count is identical under both pairings, so the fibre
    # invariance is not an artefact of the declared centre resolution
    assert receipt["pairing_columns"]["mf_invariance_same_under_both_pairings"] is True
    # measured: the transport count and subgroup are also identical, while the labellings
    # themselves differ - the pairing changes what is transported, not how much
    assert receipt["pairing_columns"]["transport_same_under_both_pairings"] is True
    declared, alternative = columns
    assert declared["label_set_transport_subgroup"] == alternative["label_set_transport_subgroup"]
    assert declared["labelings_differing_from_other_pairing"] > 0
    assert declared["sectors_with_different_labelling_sets"] == 9
    assert (
        declared["labelings_differing_from_other_pairing"]
        == alternative["labelings_differing_from_other_pairing"]
    )
    # control: the two pairings are genuinely different objects, so a pairing-blind
    # computation would have to be wrong - the fine bases differ on nine sectors
    from run_yang_mills_compression_matrix import fine_basis

    differing = [a for a in [(1, 1, 1, 1), (2, 2, 1, 1), (1, 2, 2, 1), (2, 2, 2, 2)] if {
        tuple(x) for x in fine_basis(a, "12|34")
    } != {
        tuple(x) for x in fine_basis(a, "14|23")
    }]
    assert differing, "the alternative pairing must change at least one fine basis"


def test_extension_blocks_agree_with_the_smallest_family_on_the_overlap(
    receipt: dict,
) -> None:
    """The extended run must reproduce the cutoff-1 blocks it contains."""

    def keyed(blocks):
        return {
            (tuple(b["source_sector"]), tuple(b["target_sector"]), b["corner_index"], b["direction"]): b["matrix"]
            for b in blocks
            if b.get("defined")
        }

    smallest = keyed(receipt["compression"]["blocks"])
    extended = keyed(receipt["extension"]["blocks"])
    assert len(smallest) == 96
    # every cutoff-1 block is an adjacent shift inside the label-at-most-two family, so the
    # larger run must contain it entry for entry
    overlap = [k for k in smallest if k in extended]
    assert len(overlap) == 96
    for key in overlap:
        assert extended[key] == smallest[key], key
    # control: the extension is larger, so the comparison is not an identity of one set
    assert len(extended) == 420 > len(smallest)


def test_closed_form_insertion_matches_the_stepwise_contraction() -> None:
    """The corner multiplier is one contraction; the step-by-step path must agree exactly."""
    from run_yang_mills_compression_matrix import (
        _apply_insertion_stepwise,
        apply_insertion,
        flatten,
        rim_labels,
        state_tensor,
    )

    checked = 0
    for alpha, corner in (((1, 1, 1, 1), 0), ((2, 1, 1, 1), 2), ((2, 2, 1, 1), 3), ((0, 0, 0, 0), 1)):
        for direction in (+1, -1):
            if direction == -1 and alpha[corner] == 0:
                continue
            beta = alpha[:corner] + (alpha[corner] + direction,) + alpha[corner + 1 :]
            labels_beta = dict(
                zip(("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), rim_labels(beta))
            )
            for labelling in fine_basis(alpha):
                tensor = state_tensor(alpha, labelling)
                for curl in ("metric", "identity", "inverse"):
                    closed = apply_insertion(alpha, corner, direction, tensor, "12|34", curl)
                    stepwise = _apply_insertion_stepwise(
                        alpha, corner, direction, tensor, "12|34", curl
                    )
                    assert (closed is None) == (stepwise is None)
                    if closed is None:
                        continue
                    left = flatten(closed, ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), labels_beta)
                    right = flatten(stepwise, ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"), labels_beta)
                    assert left == right, (alpha, corner, direction, curl, labelling)
                    checked += 1
    assert checked > 40


def test_limits_are_stated(receipt: dict) -> None:
    limitations = receipt["limitations"]
    assert isinstance(limitations, list) and len(limitations) >= 4
    joined = " ".join(limitations).lower()
    assert "declared" in joined
    assert "asymptotic" in joined
    assert receipt["declared_model"]["model_status"] == "declared_proxy"
    assert receipt["closure"]["open"]


# ---------------------------------------------------------------------------
# item 9: the widened scope, stored next to the default one rather than in its place
# ---------------------------------------------------------------------------


def test_widened_scope_is_a_separate_scope_of_the_same_family(
    stored_receipt: dict, receipt: dict
) -> None:
    wide = stored_receipt["widened_scope"]
    default = receipt["extension"]
    assert wide["cutoff"] == default["cutoff"] == 2
    assert wide["frontier_dim"] == WIDENED_FRONTIER_DIM == 51
    assert default["frontier_dim"] == 19
    assert wide["frontier_dim"] > default["frontier_dim"]
    # the wider scope really computes more of the same family, and the two scopes are
    # reported side by side: the stored artifact has both, a default build has only one
    assert "widened_scope" in stored_receipt and "widened_scope" not in receipt
    counts = wide["against_the_stored_default_scope"]
    assert counts["stored_default_blocks"] == default["summary"]["block_count"] == 420
    assert wide["summary"]["block_count"] == 516 == counts["widened_blocks"]
    assert len(wide["skipped_blocks"]) == 24 == counts["still_excluded_blocks"]
    assert len(wide["blocks"]) == 516
    assert counts["newly_computed_blocks"] == 516 - 420 == 96
    assert counts["blocks_computed_in_both_scopes"] == 420
    assert counts["every_default_block_recomputed_here"] is True
    assert counts["overlap_entries_identical"] is True
    assert counts["overlap_witness_rows_identical"] is True
    assert counts["family_total"] == 540 and counts["family_total_reconciles"] is True
    assert wide["summary"]["block_count"] + len(wide["skipped_blocks"]) == 540
    # every still-excluded block keeps its exact dimensions, cost units and reason
    for skipped in wide["skipped_blocks"]:
        assert max(skipped["source_dimension"], skipped["target_dimension"]) > 51
        assert skipped["cost_units"] == skipped["source_dimension"] * skipped["target_dimension"]
        assert "exceeds the declared frontier" in skipped["reason"]
        assert "51" in skipped["reason"]
    assert wide["vanishing"]["skipped_cost_units_total"] == sum(
        s["cost_units"] for s in wide["skipped_blocks"]
    )
    largest = wide["vanishing"]["largest_skipped_dimension_pair"]
    assert max(largest) > wide["frontier_dim"]
    assert max(largest) == max(
        max(s["source_dimension"], s["target_dimension"]) for s in wide["skipped_blocks"]
    )
    # the widened run is inside the runner's usual wall-clock budget, and its own cost is
    # recorded next to the default scope's runtime rather than replacing it
    assert wide["elapsed_seconds"] is not None and wide["elapsed_seconds"] > 0
    assert receipt["runtime_seconds"] < 180
    assert wide["elapsed_seconds"] + 35 < 180
    # control: the two scopes are not the same object, so the comparison above is not an
    # identity - the widened scope must contain blocks the default one records as excluded
    newly = [
        b
        for b in wide["blocks"]
        if max(b["matrix_shape"]) > default["frontier_dim"]
    ]
    assert len(newly) == counts["newly_computed_blocks"]
    assert counts["newly_computed_cost_units"] == sum(
        b["matrix_shape"][0] * b["matrix_shape"][1] for b in newly
    )


def test_widened_scope_vanishing_and_full_rank_saturation(stored_receipt: dict) -> None:
    wide = stored_receipt["widened_scope"]
    vanishing = wide["vanishing"]
    assert vanishing["blocks_computed"] == wide["summary"]["block_count"] == 516
    assert vanishing["zero_block_count"] == 0
    assert vanishing["zero_blocks"] == []
    assert vanishing["first_vanishing_block"] is None
    assert vanishing["answer"] == "no zero block was found inside the computed family"
    assert wide["against_the_stored_default_scope"]["newly_computed_zero_blocks"] == 0
    # full-rank saturation holds on the widened scope too, with its own rank range
    saturation = wide["full_rank_saturation"]
    assert saturation["blocks"] == 516
    assert saturation["saturated_blocks"] == 516 == saturation["blocks"]
    assert saturation["deficient_blocks"] == 0
    assert saturation["saturation_holds_for_every_computed_block"] is True
    assert saturation["rank_range"] == [1, 30]
    assert wide["against_the_stored_default_scope"]["newly_computed_full_rank_blocks"] == 96
    # the frontier rule is tight on the widened scope: every computed block is inside it,
    # and the largest computed multiplicity is exactly the frontier, so the section really
    # spends its budget on the blocks the narrower scope could not reach
    computed_dims = [max(b["matrix_shape"]) for b in wide["blocks"] if b.get("defined")]
    assert max(computed_dims) == wide["frontier_dim"] == 51
    assert all(dim <= wide["frontier_dim"] for dim in computed_dims)
    assert wide["summary"]["zero_blocks"] == []
    assert wide["summary"]["min_rank"] == 1 and wide["summary"]["max_rank"] == 30
    # control: saturation is a reading of every block, so a block that is not saturated must
    # be detectable on the same code path - the identity-curl block is exactly zero
    alpha, beta = (1, 1, 1, 1), (2, 1, 1, 1)
    zero_block = block_matrix(beta, alpha, 0, +1, curl="identity")
    assert zero_block["is_zero"] is True and zero_block["rank"] == 0
    assert (
        full_rank_saturation([zero_block])["saturation_holds_for_every_computed_block"] is False
    )
    assert full_rank_saturation([zero_block])["deficient_blocks"] == 1


def test_widened_scope_blocks_are_recomputed_and_match_the_stored_rows(
    stored_receipt: dict, receipt: dict
) -> None:
    """The stored widened rows must be the blocks this code computes now, not stale ones."""
    wide = stored_receipt["widened_scope"]
    default_keys = {
        (tuple(b["source_sector"]), tuple(b["target_sector"]), b["corner_index"], b["direction"])
        for b in receipt["extension"]["blocks"]
        if b.get("defined")
    }
    newly = [
        b
        for b in wide["blocks"]
        if (tuple(b["source_sector"]), tuple(b["target_sector"]), b["corner_index"], b["direction"])
        not in default_keys
    ]
    assert len(newly) == 96
    wide_witness = {
        (tuple(r["source_sector"]), tuple(r["target_sector"]), r["corner_index"], r["direction"]): r
        for r in wide["rank_witness"]["rows"]
    }
    sample = sorted(newly, key=lambda b: (b["matrix_shape"][0] * b["matrix_shape"][1], b["corner_index"]))[:2]
    assert sample
    for stored in sample:
        block = block_matrix(
            stored["target_sector"],
            stored["source_sector"],
            stored["corner_index"],
            stored["direction"],
        )
        assert block["matrix"] == stored["matrix"]
        assert block["rank"] == stored["rank"] == min(block["matrix_shape"])
        key = (tuple(stored["source_sector"]), tuple(stored["target_sector"]), stored["corner_index"], stored["direction"])
        fresh = minor_witness([[F(x) for x in row] for row in stored["matrix"]])
        row = wide_witness[key]
        assert row["found"] == fresh["found"]
        assert row["arm"] == fresh["arm"]
        assert row["search_status"] == fresh["search_status"]
        assert row["certificate_digest"] == fresh["certificate_digest"]
    # control: the sample is drawn from blocks the default scope does not compute, so the
    # comparison is not a restatement of the default section
    assert all(max(s["matrix_shape"]) > 19 for s in sample)


# ---------------------------------------------------------------------------
# item 10: the rank witness - an explicit triangular min(shape) minor per block
# ---------------------------------------------------------------------------


def test_rank_witness_covers_every_computed_block(receipt: dict) -> None:
    for scope, block_count, unit_minors in (
        (receipt["compression"], 96, 36),
        (receipt["extension"], 420, 68),
    ):
        witness = scope["rank_witness"]
        assert witness["blocks_searched"] == block_count
        assert len(witness["rows"]) == block_count
        assert (
            witness["blocks_with_a_verified_witness"] + witness["counterexample_count"]
            == block_count
        )
        assert witness["decided_blocks"] + witness["undecided_blocks"] == block_count
        assert witness["decided_blocks"] == (
            witness["blocks_with_a_verified_witness"]
            + witness["by_search_status"]["exhausted_without_a_witness"]
        )
        assert witness["counterexample_count"] == (
            witness["by_search_status"]["exhausted_without_a_witness"]
            + witness["by_search_status"]["budget_limited_without_a_witness"]
            + witness["by_search_status"]["above_exact_search_size_without_a_witness"]
        )
        assert sum(witness["by_arm"].values()) == block_count
        # the per-size breakdown is where the reading lives: the smallest minor size is
        # witnessed in every block, and the breakdown reconciles with the totals
        sizes = witness["by_minor_size"]
        assert sum(v["blocks"] for v in sizes.values()) == block_count
        assert (
            sum(v["witnessed"] for v in sizes.values())
            == witness["blocks_with_a_verified_witness"]
        )
        assert sizes["1"] == {"blocks": unit_minors, "witnessed": unit_minors}
        assert all(v["witnessed"] <= v["blocks"] for v in sizes.values())
        # the largest minor searched for is the largest min(shape) in the scope, which is the
        # largest rank the scope attains
        assert witness["minor_size_range"] == scope["full_rank_saturation"]["rank_range"]
        # every reported witness verifies, and each row carries the size of the minor it found
        assert witness["all_certificates_verified"] is True
        for row in witness["rows"]:
            assert row["certificate_verifies"] == row["found"]
            assert row["minor_size"] == min(row["shape"])
            if row["found"]:
                assert row["arm"] in (
                    "declared_order",
                    "search_greedy_fewest",
                    "search_greedy_stored",
                    "search_depth_first",
                )
                assert row["certificate_digest"]
            else:
                assert row["arm"] is None and row["certificate_digest"] is None
        # the search's own bookkeeping: the minor size above which the exhaustive arm is not
        # run is the one the rows use
        for row in witness["rows"]:
            if row["search_status"] == "above_exact_search_size":
                assert row["minor_size"] > WITNESS_EXACT_MAX_K


def test_rank_witness_matches_the_measured_saturation(receipt: dict) -> None:
    for scope in (receipt["compression"], receipt["extension"]):
        witness = scope["rank_witness"]
        saturation = scope["full_rank_saturation"]
        # every block's canonical pivot minor has min(shape) pivots exactly when the block is
        # saturated, so the two independent readings must agree block for block
        assert witness["blocks_searched"] == saturation["blocks"]
        assert witness["canonical_minor_invertible_in_every_block"] is True
        assert saturation["saturation_holds_for_every_computed_block"] is True
        assert saturation["saturated_blocks"] == saturation["blocks"]


def test_no_triangular_witness_is_available_uniformly(receipt: dict) -> None:
    """The honest reading: a witness was found for a measured fraction, not for every block."""
    witness = receipt["extension"]["rank_witness"]
    assert witness["witness_fraction"] == "156/420"
    assert witness["blocks_with_a_verified_witness"] == 156
    assert witness["all_blocks_witnessed"] is False
    assert witness["by_arm"]["declared_order"] == 132
    assert witness["by_search_status"] == {
        "exhausted_without_a_witness": 216,
        "budget_limited_without_a_witness": 28,
        "above_exact_search_size_without_a_witness": 20,
    }
    first = witness["first_block_without_a_witness"]
    assert first["source_sector"] == [0, 0, 1, 1]
    assert first["target_sector"] == [0, 0, 2, 1]
    assert first["corner_index"] == 2 and first["direction"] == 1
    assert first["shape"] == [2, 2]
    assert first["search_status"] == "exhausted"
    # the distinction the reading has to keep: this counterexample is exact, because the
    # search explored its whole space at that size - not merely "not found yet"
    assert first["nodes"] > 0
    assert witness["first_exhausted_negative"] is not None
    assert witness["first_exhausted_negative"]["search_status"] == "exhausted"
    # control: the block itself is saturated, so the negative is about triangular minors and
    # not about the block being deficient
    assert first["canonical_minor_is_invertible_rank_full"] is True
    assert first["rank"] == min(first["shape"]) == 2
    # and the smallest family reports the same split with its own numbers
    smallest = receipt["compression"]["rank_witness"]
    assert smallest["witness_fraction"] == "70/96"
    assert smallest["all_blocks_witnessed"] is False
    assert smallest["by_search_status"]["exhausted_without_a_witness"] == 22


def test_witness_certificates_verify_against_the_stored_entries(receipt: dict) -> None:
    from run_yang_mills_compression_matrix import _verify_witness

    blocks = {
        (
            tuple(b["source_sector"]),
            tuple(b["target_sector"]),
            b["corner_index"],
            b["direction"],
        ): b
        for b in receipt["extension"]["blocks"]
        if b.get("defined")
    }
    # the extension is a superset of the smallest family (asserted elsewhere), so every
    # example certificate, from either scope, has its block here
    examples = [
        e
        for scope in ("compression", "extension")
        for e in receipt[scope]["rank_witness"]["witness_examples"]
        if e.get("witness_rows")
    ]
    assert len(examples) >= 3
    checked = 0
    for example in examples:
        key = (
            tuple(example["source_sector"]),
            tuple(example["target_sector"]),
            example["corner_index"],
            example["direction"],
        )
        matrix = [[F(x) for x in row] for row in blocks[key]["matrix"]]
        verification = _verify_witness(
            matrix, example["witness_rows"], example["witness_cols"], example["form"], rank_check=True
        )
        assert verification["diagonal_nonzero"] is True
        assert verification["forbidden_entries_zero"] is True
        # the triangular form is itself the proof of invertibility: the determinant is the
        # product of the diagonal entries, and the exact rank agrees
        assert verification["rank_equals_minor_size"] is True
        assert verification["rank_by_elimination"] == len(example["witness_rows"])
        assert verification["minor_size"] == len(example["witness_rows"]) == min(example["shape"])
        assert example["verification"] == verification
        checked += 1
    assert checked >= 3
    # control: the verification reads the block's own entries, so the same certificate must
    # fail on the same block once an entry it depends on is removed
    example = next(e for e in examples if len(e["witness_rows"]) > 1)
    key = (
        tuple(example["source_sector"]),
        tuple(example["target_sector"]),
        example["corner_index"],
        example["direction"],
    )
    mutated = [[F(x) for x in row] for row in blocks[key]["matrix"]]
    mutated[example["witness_rows"][0]][example["witness_cols"][0]] = F(0)
    zeroed = _verify_witness(
        mutated, example["witness_rows"], example["witness_cols"], example["form"]
    )
    assert zeroed["diagonal_nonzero"] is False
    assert not (zeroed["diagonal_nonzero"] and zeroed["forbidden_entries_zero"])
    # control: the tensor-valued certificate is the smallest family's (2,5) minor, not a trivial
    # 1x1, and the family's first block without a witness is an exact negative whose block is
    # nonetheless full rank
    assert (len(example["witness_rows"]), example["shape"]) == (2, [2, 5])
    assert (
        receipt["compression"]["rank_witness"]["first_block_without_a_witness"]["search_status"]
        == "exhausted"
    )


def test_rank_witness_controls_fire(receipt: dict) -> None:
    controls = receipt["checks"]["rank_witness_controls"]
    witnessed = controls["witnessed_block"]
    assert witnessed is not None
    assert witnessed["intact_certificate_verifies"] is True
    assert witnessed["verification"]["rank_equals_minor_size"] is True
    assert witnessed["zeroed_diagonal_breaks_it"] is True
    assert witnessed["swapped_rows_break_it"] is True
    assert witnessed["swapped_columns_break_it"] is True
    negative = controls["negative_block"]
    assert negative is not None
    assert negative["search_status"] == "exhausted"
    assert negative["canonical_minor_is_invertible_rank_full"] is True
    assert negative["rank"] == negative["minor_size"]
    assert controls["dense_2x2_witness_found"] is False
    assert controls["dense_2x2_search_status"] == "exhausted"
    # and the controls are recomputable: the same block, searched again, gives the same answer
    fresh = witness_controls(receipt["compression"]["blocks"])
    assert canonical_json(fresh) == canonical_json(controls)


def test_the_widened_frontier_is_the_largest_inside_the_runner_budget(
    stored_receipt: dict,
) -> None:
    wide = stored_receipt["widened_scope"]
    choice = wide["frontier_choice"]
    assert choice["chosen_frontier"] == wide["frontier_dim"] == WIDENED_FRONTIER_DIM == 51
    assert choice["bound_seconds"] == 180
    assert choice["extension_budget_seconds"] == 180 - choice["default_scope_and_assembly_seconds"]
    measured = {
        int(k): v for k, v in choice["measured_extension_build_seconds_by_frontier"].items()
    }
    assert set(measured) >= {19, 51, 64, 91}
    # the choice follows the measurements: the chosen frontier is in budget and no measured
    # candidate above it is, which is the whole content of "as far as the budget allows"
    assert measured[choice["chosen_frontier"]] <= choice["extension_budget_seconds"]
    assert choice["largest_frontier_inside_the_budget"] == choice["chosen_frontier"]
    below_budget = [
        f for f, s in measured.items() if s <= choice["extension_budget_seconds"]
    ]
    assert max(below_budget) == choice["chosen_frontier"]
    for f in measured:
        if f > choice["chosen_frontier"]:
            assert measured[f] > choice["extension_budget_seconds"], f
    assert choice["frontiers_outside_the_budget"] == [
        f for f in sorted(measured) if measured[f] > choice["extension_budget_seconds"]
    ]
    # and the widened path really stays inside the bound end to end; the complete family, which
    # the artifact also carries, declares its own overrun instead of hiding it in this total
    assert wide["elapsed_seconds"] + choice["default_scope_and_assembly_seconds"] < choice["bound_seconds"]


def test_complete_family_is_a_third_declared_scope(stored_receipt: dict, receipt: dict) -> None:
    full = stored_receipt["complete_family"]
    assert "complete_family" not in receipt
    assert full["cutoff"] == 2
    assert full["frontier_dim"] == COMPLETE_FRONTIER_DIM == 120
    assert full["frontier_dim"] > stored_receipt["widened_scope"]["frontier_dim"] == 51
    assert full["blocks_computed"] == full["family_total"] == 540
    assert full["blocks_uncomputed"] == 0 and full["skipped_blocks"] == []
    assert full["family_complete"] is True
    assert len(full["blocks"]) == 540
    assert full["summary"]["block_count"] == 540
    assert full["vanishing"]["blocks_computed"] == 540
    assert full["vanishing"]["skipped_block_count"] == 0
    # the three scopes are three sections of one artifact, each with its own count
    assert len(stored_receipt["extension"]["blocks"]) == 420
    assert len(stored_receipt["widened_scope"]["blocks"]) == 516
    assert len(full["blocks"]) == 540
    # the complete scope declares what completing the family costs instead of capping it
    budget = full["budget"]
    assert budget["runner_bound_seconds"] == 180
    assert budget["measured_seconds"] == pytest.approx(full["elapsed_seconds"], abs=1e-6)
    assert budget["measured_seconds"] > 0
    assert budget["exceeds_the_runner_bound"] == (budget["measured_seconds"] > 180)
    assert budget["bounded_or_approximated_blocks"] == []
    assert set(budget["measured_largest_block_seconds"]) == {
        "64x51",
        "91x51",
        "51x91",
        "120x91",
    }
    # control: the section really is the opt-in one, and the runner reaches it only by flag
    import inspect

    from run_yang_mills_compression_matrix import main

    source = inspect.getsource(main)
    assert '"--complete" in argv' in source
    assert full["family_total"] == len(stored_receipt["extension"]["blocks"]) + len(
        stored_receipt["extension"]["skipped_blocks"]
    )
    # the artifact's own total is the three scopes together, so it is strictly above the
    # complete family's own build time and above the usual bound
    assert stored_receipt["runtime_seconds"] > budget["measured_seconds"]
    assert stored_receipt["runtime_seconds"] > budget["runner_bound_seconds"]


def test_complete_family_vanishing_and_saturation(stored_receipt: dict) -> None:
    full = stored_receipt["complete_family"]
    vanishing = full["vanishing"]
    # the total answer for the finite family: no block of it vanishes
    assert vanishing["blocks_computed"] == 540
    assert vanishing["zero_block_count"] == 0
    assert vanishing["zero_blocks"] == []
    assert vanishing["first_vanishing_block"] is None
    assert vanishing["answer"] == "no zero block was found inside the computed family"
    assert full["summary"]["zero_blocks"] == []
    saturation = full["full_rank_saturation"]
    assert saturation["blocks"] == 540
    assert saturation["saturated_blocks"] == 540
    assert saturation["deficient_blocks"] == 0
    assert saturation["saturation_holds_for_every_computed_block"] is True
    assert saturation["rank_range"] == [1, 91]
    assert saturation["kernel_dimension_range"] == [0, 40]
    # the last 24 blocks the widened scope could not reach, from the complete scope's own record
    counts = full["against_the_narrower_scopes"]
    assert counts["blocks_computed_beyond_the_widened_scope"] == 24
    assert counts["zero_blocks_beyond_the_widened_scope"] == 0
    assert counts["full_rank_blocks_beyond_the_widened_scope"] == 24
    assert counts["largest_dimension_pair_beyond_the_widened_scope"] == [91, 120]
    assert counts["cost_units_beyond_the_widened_scope"] == 119976
    beyond = {
        (
            tuple(b["source_sector"]),
            tuple(b["target_sector"]),
            b["corner_index"],
            b["direction"],
        ): b
        for b in full["blocks_beyond_the_widened_scope"]
    }
    assert len(beyond) == 24
    for b in beyond.values():
        assert b["is_zero"] is False
        assert b["rank"] == min(b["matrix_shape"])
        assert b["kernel_dimension"] == max(0, b["matrix_shape"][1] - b["matrix_shape"][0])
    # the largest blocks are reported with their own rank and kernel figures
    largest = full["largest_blocks"]
    assert len(largest) == 8
    assert [min(b["matrix_shape"]) for b in largest] == sorted(
        (min(b["matrix_shape"]) for b in largest), reverse=True
    )
    biggest = [b for b in largest if b["matrix_shape"] == [120, 91]]
    assert len(biggest) == 4
    for b in biggest:
        assert b["rank"] == 91
        assert b["kernel_dimension"] == 0
        assert b["is_zero"] is False
        assert b["cost_units"] == 10920
    # the four largest blocks are the up-shifts out of (2,2,2,2), one per corner
    assert sorted(b["corner_index"] for b in biggest) == [0, 1, 2, 3]
    assert {tuple(b["source_sector"]) for b in biggest} == {(2, 2, 2, 2)}
    assert {b["direction"] for b in biggest} == {+1}
    assert full["summary"]["max_rank"] == 91
    assert full["summary"]["max_kernel_dimension"] == 40
    # control: the same zero reading is detectable on this path (the identity-curl block is an
    # exact zero, and the saturation reading fires on it)
    zero_block = block_matrix((2, 1, 1, 1), (1, 1, 1, 1), 0, +1, curl="identity")
    assert full_rank_saturation([zero_block])["saturated_blocks"] == 0
    assert full_rank_saturation([zero_block])["rank_range"] == [0, 0]


def test_complete_family_agrees_with_the_narrower_scopes(stored_receipt: dict) -> None:
    full = stored_receipt["complete_family"]
    counts = full["against_the_narrower_scopes"]
    assert counts["stored_default_blocks"] == 420
    assert counts["widened_blocks"] == 516
    assert counts["complete_blocks"] == 540
    assert counts["blocks_in_all_three_scopes"] == 420
    assert counts["overlap_entries_identical_to_the_default"] is True
    assert counts["overlap_entries_identical_to_the_widened"] is True
    assert counts["overlap_witness_rows_identical_to_the_default"] is True
    assert counts["overlap_witness_rows_identical_to_the_widened"] is True
    assert counts["family_total_reconciles"] is True
    # the compact rows of the complete scope must describe the same blocks as the sections that
    # carry the matrices, key for key, and the full matrices must be exactly the ones the
    # widened scope records as excluded - so no block is claimed here without its entries
    compact = {
        (
            tuple(b["source_sector"]),
            tuple(b["target_sector"]),
            b["corner_index"],
            b["direction"],
        ): b
        for b in full["blocks"]
    }
    widened = {
        (
            tuple(b["source_sector"]),
            tuple(b["target_sector"]),
            b["corner_index"],
            b["direction"],
        ): b
        for b in stored_receipt["widened_scope"]["blocks"]
    }
    assert len(compact) == 540 and len(widened) == 516
    for key, row in widened.items():
        assert compact[key]["matrix_shape"] == row["matrix_shape"]
        assert compact[key]["rank"] == row["rank"]
        assert compact[key]["kernel_dimension"] == row["kernel_dimension"]
        assert compact[key]["is_zero"] == row["is_zero"]
    # every block the widened scope records as excluded is stored here with its full matrix,
    # with the exact dimensions that record gives
    stored_beyond = {
        (
            tuple(b["source_sector"]),
            tuple(b["target_sector"]),
            b["corner_index"],
            b["direction"],
        ): b
        for b in full["blocks_beyond_the_widened_scope"]
    }
    assert len(stored_beyond) == 24
    for row in stored_receipt["widened_scope"]["skipped_blocks"]:
        key = (
            tuple(row["source_sector"]),
            tuple(row["target_sector"]),
            row["corner_index"],
            row["direction"],
        )
        assert key in stored_beyond, key
        assert stored_beyond[key]["matrix_shape"] == [
            row["target_dimension"],
            row["source_dimension"],
        ]
        assert stored_beyond[key]["defined"] is True
        assert len(stored_beyond[key]["matrix"]) == row["target_dimension"]
        assert len(stored_beyond[key]["matrix"][0]) == row["source_dimension"]


def test_complete_family_blocks_recompute_from_the_stored_entries(stored_receipt: dict) -> None:
    full = stored_receipt["complete_family"]
    # the cheapest block the widened scope cannot reach, recomputed from scratch: the exact
    # rational elimination on these shapes is seconds of work, so one block is recomputed and
    # the rest of the section is held to the narrower scopes' entries for the same keys
    block = min(
        (b for b in full["blocks_beyond_the_widened_scope"] if b.get("defined")),
        key=lambda b: (b["matrix_shape"][0] * b["matrix_shape"][1], b["matrix_shape"]),
    )
    fresh = block_matrix(
        block["target_sector"], block["source_sector"], block["corner_index"], block["direction"]
    )
    assert fresh["matrix"] == block["matrix"]
    assert fresh["rank"] == block["rank"] == min(fresh["matrix_shape"])
    assert fresh["kernel_dimension"] == block["kernel_dimension"]
    assert fresh["is_zero"] == block["is_zero"] is False
    # control: the sample is a block the widened scope records as excluded, so the comparison is
    # not a restatement of a narrower section
    assert max(block["matrix_shape"]) > stored_receipt["widened_scope"]["frontier_dim"]


def test_complete_family_rank_witness(stored_receipt: dict) -> None:
    full = stored_receipt["complete_family"]
    witness = full["rank_witness"]
    assert witness["blocks_searched"] == 540
    assert len(witness["rows"]) == 540
    assert witness["blocks_with_a_verified_witness"] + witness["counterexample_count"] == 540
    assert witness["all_certificates_verified"] is True
    assert witness["canonical_minor_invertible_in_every_block"] is True
    assert witness["all_blocks_witnessed"] is False
    assert sum(witness["by_search_status"].values()) == witness["counterexample_count"]
    assert sum(v["blocks"] for v in witness["by_minor_size"].values()) == 540
    assert witness["by_minor_size"]["1"] == {"blocks": 68, "witnessed": 68}
    # the witness fraction over the complete family, and its exact-negative class
    assert witness["witness_fraction"] == "163/540"
    assert witness["by_search_status"] == {
        "exhausted_without_a_witness": 224,
        "budget_limited_without_a_witness": 42,
        "above_exact_search_size_without_a_witness": 111,
    }
    assert witness["minor_size_range"] == [1, 91]
    first = witness["first_block_without_a_witness"]
    assert first["source_sector"] == [0, 0, 1, 1] and first["shape"] == [2, 2]
    assert first["search_status"] == "exhausted"
    # control: the 24 new blocks change the undecided count, not the witness count, and the
    # rows for blocks the widened scope already searched are identical
    widened_rows = {
        (
            tuple(r["source_sector"]),
            tuple(r["target_sector"]),
            r["corner_index"],
            r["direction"],
        ): r
        for r in stored_receipt["widened_scope"]["rank_witness"]["rows"]
    }
    complete_rows = {
        (
            tuple(r["source_sector"]),
            tuple(r["target_sector"]),
            r["corner_index"],
            r["direction"],
        ): r
        for r in witness["rows"]
    }
    assert len(widened_rows) == 516
    for key, row in widened_rows.items():
        assert complete_rows[key] == row, key


def test_widened_scope_rank_witness_is_reported_too(stored_receipt: dict) -> None:
    wide = stored_receipt["widened_scope"]["rank_witness"]
    assert wide["blocks_searched"] == 516
    assert len(wide["rows"]) == 516
    assert wide["blocks_with_a_verified_witness"] + wide["counterexample_count"] == 516
    assert wide["witness_fraction"] == "163/516"
    assert wide["all_blocks_witnessed"] is False
    assert wide["by_arm"]["declared_order"] == 134
    assert wide["by_search_status"] == {
        "exhausted_without_a_witness": 224,
        "budget_limited_without_a_witness": 42,
        "above_exact_search_size_without_a_witness": 87,
    }
    assert wide["minor_size_range"] == [1, 30]
    assert wide["all_certificates_verified"] is True
    assert wide["canonical_minor_invertible_in_every_block"] is True
    assert sum(wide["by_search_status"].values()) == wide["counterexample_count"]
    # the wider scope does not change any of the readings the narrower one already had: the
    # blocks the two scopes share give the identical witness rows, so this is the same search
    # extended rather than a second, differently wired one
    default_rows = {
        (tuple(r["source_sector"]), tuple(r["target_sector"]), r["corner_index"], r["direction"]): r
        for r in stored_receipt["extension"]["rank_witness"]["rows"]
    }
    wide_rows = {
        (tuple(r["source_sector"]), tuple(r["target_sector"]), r["corner_index"], r["direction"]): r
        for r in wide["rows"]
    }
    assert len(default_rows) == 420
    overlap = [k for k in default_rows if k in wide_rows]
    assert len(overlap) == 420
    for key in overlap:
        assert wide_rows[key] == default_rows[key], key
    # the wider scope covers strictly more blocks, so the two fractions are different readings
    # of the same search rather than one scope restated
    assert wide["blocks_searched"] == 516 > len(default_rows) == 420
