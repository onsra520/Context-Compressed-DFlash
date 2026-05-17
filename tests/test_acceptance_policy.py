from low_tier.acceptance import greedy_exact_match


def test_accepts_full_matching_prefix():
    result = greedy_exact_match(candidate_token_ids=[1, 2, 3], greedy_token_ids=[1, 2, 3])

    assert result.accepted_token_ids == [1, 2, 3]
    assert result.reject_position is None
    assert result.candidate_exhausted is True
    assert result.rejected_token_id is None


def test_stops_on_first_mismatch():
    result = greedy_exact_match(candidate_token_ids=[1, 9, 3], greedy_token_ids=[1, 2, 3])

    assert result.accepted_token_ids == [1]
    assert result.reject_position == 1
    assert result.candidate_exhausted is False
    assert result.rejected_token_id == 9


def test_immediate_reject_reports_zero_position():
    result = greedy_exact_match(candidate_token_ids=[9, 2], greedy_token_ids=[1, 2])

    assert result.accepted_token_ids == []
    assert result.reject_position == 0
    assert result.candidate_exhausted is False
    assert result.rejected_token_id == 9


def test_empty_candidate_exhausted_with_empty_prefix():
    result = greedy_exact_match(candidate_token_ids=[], greedy_token_ids=[1, 2])

    assert result.accepted_token_ids == []
    assert result.reject_position is None
    assert result.candidate_exhausted is True
