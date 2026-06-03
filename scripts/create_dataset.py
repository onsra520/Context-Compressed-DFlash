from __future__ import annotations

import argparse

from ccdf.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a processed dataset placeholder")
    parser.add_argument("--config", default="config.yml")
    args = parser.parse_args()

    load_config(args.config)
    raise NotImplementedError("Dataset creation is not wired yet; use the benchmark dataset module later.")


if __name__ == "__main__":
    main()