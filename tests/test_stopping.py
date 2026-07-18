from ccdf.inference.stopping import BlockStopController


class Tokenizer:
    def decode(self, token_ids, skip_special_tokens=True):
        mapping = {1: "Final", 2: " answer:", 3: " 42"}
        return "".join(mapping.get(value, "") for value in token_ids)


def test_eos_fast_path():
    controller = BlockStopController(tokenizer=Tokenizer(), stop_token_ids=[9], max_new_tokens=10)
    assert controller.token_reason(9, 1) == "eos"


def test_gsm8k_contract_at_block_boundary():
    controller = BlockStopController(
        tokenizer=Tokenizer(), stop_token_ids=[9], max_new_tokens=10, dataset="gsm8k"
    )
    state = controller.block_boundary([1, 2, 3])
    assert state.reason == "output_contract"
