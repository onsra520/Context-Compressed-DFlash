from __future__ import annotations

# STATUS: skeleton-only probe. This checks config/import wiring only and does not run real Gate 0.

import argparse

from ccdf.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="CCDF synthetic probe")
    parser.add_argument("--config", default="config.yml")
    args = parser.parse_args()

    config = load_config(args.config)
    print("Loaded config keys:", ", ".join(sorted(config)))
    print("Skeleton import/config check completed. Real Gate 0 has NOT been run.")


if __name__ == "__main__":
    main()