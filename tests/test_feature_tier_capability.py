from htfsd.feature_tier.capability import feature_tier_readiness
from htfsd.feature_tier.contracts import FeatureDrafter, FeatureVerifier


class BackendWithoutHiddenStates:
    supports_hidden_states = False


def test_feature_tier_readiness_is_blocked_for_llama_cpp_backend():
    result = feature_tier_readiness(BackendWithoutHiddenStates())

    assert result["supports_hidden_states"] is False
    assert result["readiness"] == "blocked"
    assert result["reason"] == "hidden_states_unavailable"


def test_feature_tier_contracts_are_protocols():
    assert FeatureDrafter
    assert FeatureVerifier
