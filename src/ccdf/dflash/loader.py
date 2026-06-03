from __future__ import annotations


def load_target(*args, **kwargs):
    raise NotImplementedError("load_target will be wired after the upstream split is copied in.")


def load_draft(*args, **kwargs):
    raise NotImplementedError("load_draft will be wired after the upstream split is copied in.")


def load_tokenizer(*args, **kwargs):
    raise NotImplementedError(
        "load_tokenizer will be wired after the upstream split is copied in."
    )


def load_all(*args, **kwargs):
    raise NotImplementedError("load_all will be wired after the upstream split is copied in.")