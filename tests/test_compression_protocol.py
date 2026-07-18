from ccdf.compression import CompressionConfig, ContextOnlyProtocol


def test_context_only_protocol_keeps_question_and_instruction_immutable():
    protocol = ContextOnlyProtocol("a b c", "What changed?", "Return one line.")
    rendered = protocol.render("a c")
    assert "Context:\na c" in rendered
    assert "What changed?" in rendered
    assert rendered.endswith("Return one line.")


def test_compression_config_rejects_invalid_rate():
    try:
        CompressionConfig(keep_rate=0)
    except ValueError as error:
        assert "keep_rate" in str(error)
    else:
        raise AssertionError("invalid keep rate was accepted")
