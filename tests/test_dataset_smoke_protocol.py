from ccdf.benchmark.evaluators import (
    evaluate_gsm8k,
    evaluate_qmsum,
    validate_evaluator_fixtures,
)
from ccdf.compression import CompressionConfig, ContextOnlyProtocol
from ccdf.config import load_config


def test_evaluator_fixture_lock_and_numeric_contract():
    settings = load_config("config.yml").require("dataset_smoke.evaluators")
    assert validate_evaluator_fixtures(settings)["pass"] is True
    result = evaluate_gsm8k(
        "Final answer: 99\nwork\nFinal answer: -1,200/2",
        "-600",
        settings["gsm8k"],
    )
    assert result["label"] == "correct"
    assert result["final_answer_line_count"] == 2
    assert result["exact_text_match_diagnostic"] is False


def test_qmsum_overlap_is_a_nonsemantic_set_token_proxy():
    settings = load_config("config.yml").require("dataset_smoke.evaluators.qmsum")
    result = evaluate_qmsum("Alpha beta beta", "beta gamma", settings)
    assert result["reference_recall"] == 0.5
    assert result["reference_precision"] == 0.5
    assert result["semantic_correctness"] == "NOT_CLAIMED"
    assert result["coverage_proxy_only"] is True


def test_empty_context_renders_as_no_op_without_placeholder():
    protocol = ContextOnlyProtocol(
        "",
        "What is 1 + 1?",
        "Final answer: <number>",
        context_header="",
    )
    rendered = protocol.render("")
    assert rendered == "Question:\nWhat is 1 + 1?\n\nFinal answer: <number>"
    assert "Context" not in rendered
    config = CompressionConfig(
        chunk_size_tokens=480,
        chunk_overlap_tokens=32,
        tokenizer="compressor",
        merge_policy="newline_preserve_order",
    )
    assert config.chunk_size_tokens == 480
