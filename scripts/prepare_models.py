#!/usr/bin/env python3
"""Download configured checkpoints into the required folder layout."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

from ccdf.config import load_config


def download(model_id: str, local_path: str, revision: str | None) -> None:
    destination = Path(local_path)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=destination,
        local_dir_use_symlinks=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--include-fallback", action="store_true")
    parser.add_argument("--include-compressor", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    baseline = dict(config.require("models.baseline"))
    target = dict(config.require("models.dflash.target"))
    drafter = dict(config.require("models.dflash.drafter"))
    download(baseline["model_id"], baseline["local_path"], baseline.get("revision"))
    download(target["model_id"], target["local_path"], target.get("revision"))
    download(drafter["model_id"], drafter["local_path"], drafter.get("revision"))
    if args.include_fallback:
        download(target["fallback_model_id"], target["fallback_local_path"], None)
    if args.include_compressor:
        compressor = dict(config.require("models.compressor"))
        download(compressor["model_id"], compressor["local_path"], compressor.get("revision"))


if __name__ == "__main__":
    main()
